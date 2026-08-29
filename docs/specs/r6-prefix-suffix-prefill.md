# R6-PREFIX-SUFFIX-PREFILL

Status: **implemented and measured, 2026-08-29**, on branch `agent/r6-prefix-suffix-prefill`.

- Sections 1 to 4 and 6 to 9 are the **ledger**, sections 5.1 to 5.4 the **verification plan**, and
  section 10 the **author consistency pass**, all written before implementation. Every figure in
  them is either quoted from a prior document with its source named, or is arithmetic on such a
  figure and says so.
- Sections **5.5 to 5.10, 11, and 12 are the result sections** and carry measured numbers: the
  hosted owner, the hosted refusal matrix, golden movement against its prediction, mutation
  evidence, the real-model qualification, the TTFT diagnostic, what implementation found, and the
  ledger-and-closure-matrix mapping to the final diff.
- The ledger is **not** rewritten to match the result. Every plan-versus-result deviation is
  recorded in section 11 instead, so a reader comparing the design against the code finds the
  difference named rather than erased. Section 11.1 is authoritative wherever it and an earlier
  section disagree.

**Line references.** Sections 1 to 4 and 6 to 10 cite the **design pin** `origin/main` `553563e`;
sections 11 and 12 cite the **implementation head**. A line cited in an early section may have moved
by the head, and the named symbol is what is meant.

Branch `agent/r6-prefix-suffix-prefill`, cut from `origin/main` `553563e` — the merge of
`R6-RESIDENT-WEIGHTS` (PR #147). The four documents this one extends are all on `main`:

- `docs/specs/r6-decode-kv-step1.md` — the plane, its layout, the decode node table, the id/position
  split, `mf_write_mask_offset`;
- `docs/specs/r6-step-n.md` — the `N`-step loop, `capture_plane`'s `first_column`, gate G, the
  disjointness-plus-ordering invariant;
- `docs/specs/r6-kv-persist.md` — the `akvp` v1 container, `KV_SAVE`/`KV_LOAD`, oracle Q;
- `docs/specs/r6-resident-weights.md` — the `RESIDENT` operand, schema 4, the 150,000 ppm Track B
  decode-performance floor.

Those four are the ledger this one extends. "Unchanged" below means unchanged **from them**, and a
row any of them settled that this document does not restate is still in force.

## 1. Decision and boundary

### 1.1 What this capability is

`R6-KV-PERSIST` made a prefill plane outlive its process. A second process can load the plane for
**the prompt it was saved for** and decode from it. What it cannot do is the thing a shared prefix
is for: take a plane saved for a stable prefix and continue it with a *different* suffix.

Today that is not a policy gap, it is an arithmetic gap. The arm has exactly two ways to fill a
plane — compute it with a prefill at `n_past = 0`, or read it whole from a container — and exactly
two shapes of graph — a `T`-column prefill that assumes column 0 is position 0, and a one-column
decode step at `n_past > 0`. There is no graph that computes `S > 1` columns at `n_past > 0`, so
there is nothing to run over a suffix.

This capability ships that graph, and nothing else:

- **`--decode-step` gains a `SUFFIX` operand**, a token id list, `-` for absent, valid only with
  `KV_LOAD`.
- Given a container holding `T_prefix` columns for exactly the tokens in `TOKENS`, the arm loads the
  plane as it does today, then runs **one suffix pass**: a decode-shaped graph set over the `S`
  suffix tokens at positions `T_prefix .. T_prefix + S - 1`, causally masked over `[prefix +
  suffix]`, writing the suffix's K and V back into the plane at columns `T_prefix .. T_prefix + S -
  1`.
- It then continues with the existing `N`-step loop from `n_past = T_prefix + S`, unchanged.
- **Nothing is re-saved.** The container is read-only, the `akvp` format is byte-unchanged, and
  appending is deferred (section 7).

**The oracle is that this is the same run as a single-shot prefill of `TOKENS ++ SUFFIX`.** Not
close to it — byte-identical logits, byte-identical decoded ids, and a byte-identical document
outside one named exclusion list.

**The headline is how little it needs**, and it is a consequence of R6's design rather than a claim
about this one. Every row below was verified by reading the named line at `553563e`:

| Needed by a suffix prefill | State |
| --- | --- |
| A new ggml op, FFI symbol, or shim change | **None.** `op_concat` ships with R6; the suffix graph's op set is the decode graph's |
| A new node row, slot, or op code | **None.** The decode table is 38 rows (`layer_qwen2.MF_DECODE_LAYER_NODE_COUNT`, `:1697`) at `tokens = 1`; it becomes 38 rows at `tokens = S`. Slots 64/65 are the plane slots and the high-water stays 66 |
| A new mask writer | **None.** `mf_write_mask_offset(window, width, height, row_offset)` (`layer_qwen2.align:2178`) already takes both. R6 calls it at `height = 1`; the prefill calls `mf_write_mask` at `row_offset = 0`. **The suffix pass is its first caller with both non-trivial**, and the arithmetic `col <= row + row_offset` is already exactly the `S × (T_prefix + S)` causal block |
| A new plane writer | **None.** `capture_plane(.., tokens, first_column, ..)` (`decode_step.align:1048`) already takes both. The prefill calls it at `(T, 0)` (`:1006`), a decode step at `(1, n_past)` (`:1021`). **The suffix pass is its first caller with both non-trivial**, and its body is already general in `first_column` |
| A change to `src/kv_plane.align` or the `akvp` v1 format | **None**, and section 2.1 records that this is a *consequence of the surface decision* rather than luck |
| A change to `src/ggml_spike.align`, `src/ggml_ffi.align`, `scripts/ggml_shim.c` | **None.** The dispatch arm does not enumerate arity |
| A new Align language surface | **None.** Section 8 records four continuing gaps; none blocks this |

What it does need is exactly six things: a **`SUFFIX` operand**; a **`tokens` parameter on the
decode node table** (four literal `1`s and one nested call here, and a sixth site implementation
found in `mf_decode_row_tail` — section 11.1 correction 4); an **absolute base on the position
producer**; one `capture_plane` call at `(S, T_prefix)`; **`verify_plane`'s bound at `n_past +
tokens`** instead of `n_past + 1`; and **schema 5**.

### 1.2 Why a design gate is triggered

Three of `CLAUDE.md`'s four triggers fire. The fourth is recorded as **not fired**, with its reason,
rather than claimed.

| Trigger | Fired | Why |
| --- | --- | --- |
| Public CLI or API surface | **Yes** | `--decode-step` gains a fifteenth operand and its arity set grows to `{5,6,7,9,10,11,12,13,14,15}`; `SUFFIX` introduces the arm's first *conditional* operand — one whose legality depends on another operand's presence |
| Persisted or exchanged format | **Yes** | The `R6_DECODE_STEP` document goes to **schema 5**: a `suffix` object is added, and `output`/`oracle_logits` change what they describe on a suffix run (2.9). The `akvp` container is **not** touched, and 2.9 states why the two versions move independently |
| Ownership / process / network boundary | **Yes** | A loaded plane is today write-once from the arm's point of view: `load_plane` fills it and only the decode loop's one-column write-back touches it afterwards. This capability makes a **loaded** plane the destination of a multi-column write before any step runs, so the plane has two writers with two provenances in one run for the first time. Section 2.4 re-states the disjointness invariant over three ranges instead of two |
| Coordinated invariant across ≥ 3 modules | **No** | The change touches `src/decode_step.align`, `src/model_forward.align`, `src/layer_qwen2.align`, and three scripts — but the *invariant* they must agree on (the plane's layout, the slot numbering, the concat axes, the op codes) is R6's and is **unchanged**; only its consumers move. This is R6-STEP-N section 1.2's disposition and its reason has not weakened. The closure matrix in section 4 is built anyway, because a second writer into a shared buffer is precisely what a closure matrix is for |

### 1.3 Declared boundary

**In scope.** Dense Qwen2.5-Coder-7B Q4_K_M; **CPU only**; one container holding one prefill plane
at `T_prefix` columns for **exactly** the tokens in `TOKENS`; one suffix pass of `S` tokens at
`n_past = T_prefix`; the existing `N`-step loop continuing from `n_past = T_prefix + S`; the plane
held in memory for one process and never re-persisted; `KV_WIDTH` supplied by the caller exactly as
today; both the streamed and the `RESIDENT=weights` legs.

**Out of scope, declared non-goals.**

- **Re-saving anything.** `SUFFIX` with `KV_SAVE` is a refusal (2.3). A run that restores a plane,
  extends it, and persists the result is the *append* capability, deferred in
  `docs/specs/r6-kv-persist.md` section 7 and again here (section 7).
- **Inexact prefixes.** The container's token stream must equal `TOKENS` element for element and its
  `columns_persisted` must equal its `token_count`. Longest-common-prefix matching, prefix
  truncation, and any `columns_persisted != token_count` semantics are deferred (2.12, section 7).
- **A prefix key, a cache, a corpus, or a lookup.** There is still no content-addressed store and no
  way to *find* the container for a prefix; the caller names a path. Section 1.4.
- **Tiering, invalidation, eviction, session management, NVMe or GPU residency of the plane, a
  quantized plane, the Metal arm, OLMoE and any routed architecture, batch above one, a growing
  `KV_WIDTH`.** Unchanged non-goals.
- **Any TTFT or throughput *claim*.** Section 1.4 and section 2.10 record a labelled **diagnostic**.
  No acceptance decision is taken from it, no roadmap gate is discharged by it, and `CLAUDE.md`'s
  performance row is **not selected**, so no cost ceiling is recorded in a ledger row.
- **Text.** Unchanged from R6-STEP-N section 1.3: the gate is on token ids, there is no tokenizer,
  and Align Request 22 stays `PROPOSED` and non-blocking. Section 3.5 records the one place this
  capability makes the absence *cheaper* rather than worse.

### 1.4 The TTFT question, answered rather than claimed

`docs/specs/roadmap.md`'s R6 gate is one sentence — 同一prefixを使う反復coding taskでTTFTが改善する こと — over a
five-line list: session KV, repo stable prefix KV, DRAM tier, NVMe tier, invalidation.
`R6-KV-PERSIST` shipped the first. **This capability ships the *execution* half of the second and
not its *lookup* half, and therefore does not discharge the gate.** Four reasons, each concrete:

1. **There is still no key and no store.** A saved plane is found only by a caller who names its
   path. "Repeated coding tasks sharing a prefix" needs a lookup that, given a prompt, finds the
   longest saved prefix of it. `docs/specs/r6-kv-persist.md` section 2.8 already records the tuple
   such a key would be — `(source_header_region_sha256, geometry_sha256, token_stream_sha256,
   kv_width, plane_layout_version)` — and records that it is **not implemented**. That is still
   true, and this capability deliberately does not invent a second one.
2. **There is still no prefix-sharing corpus.** The four qualification prompts are independent code
   fragments at `T <= 6`. This capability's qualification *splits* each of them (5.4), which
   exercises the mechanism and is not a corpus: a corpus is many prompts sharing **one** long stable
   prefix — a repository preamble, a system prompt, a file header — and measuring TTFT on splits of
   four short independent prompts would be a number about the splitter.
3. **There is no prefix-sharing consumer.** Nothing in this repository calls `--decode-step` with a
   prefix it obtained from anywhere but its own previous invocation. `align-coder` is the consumer
   the gate is about and it does not exist yet (roadmap R7).
4. **What loading now avoids is bounded and measurable, and it is not the dominant term on this
   host.** A suffix run skips a `T_prefix`-column prefill and runs an `S`-column one instead; in
   **streamed** mode it still sweeps the weight set once per graph set, so the saving is one weight
   sweep's difference between a `T_prefix + S`-column prefill and an `S`-column one — which is *zero
   sweeps*, because a prefill of any width is one sweep. In **resident** mode
   (`R6-RESIDENT-WEIGHTS`) the sweep is paid once for the whole run either way. **So what a suffix
   run saves is `T_prefix` columns of prefill *compute*, plus the prefill pass's own pack read and
   graph construction for the prefix — and it pays a whole-container read instead** — and
   `docs/specs/r6-step-n.md` section 5.4 measured compute at 3.5–16.7 % of elapsed. Publishing that
   as a TTFT improvement would advertise a small fraction of a small fraction, plus one exchange of
   one read for another, as the answer to a gate about prefix reuse.

   *(The clause "and nothing else" stood here and in the runner's printed line until this
   document's own section 5.10 measured the exchange and contradicted it; the correction is recorded
   as section 11.1 correction 9. The conclusion — that this is not a cache — is unchanged and is in
   fact strengthened, because the difference is now named as an I/O trade on a six-token prompt
   rather than as pure arithmetic.)*

**What is measured instead, as characterization.** Exactly the two numbers `R6-KV-PERSIST` section
1.4 defined, on a third leg, all labelled diagnostic, reported as a range over three runs on one
host, with **no per-token, per-second, or speedup figure derived from any of them**:

- `timings.first_token_ns` on three runs at `STEPS = 1` with no transcript and no logits blob: (a)
  single-shot prefill of `TOKENS ++ SUFFIX`; (b) load plus suffix pass; (c) load with no suffix,
  which is `R6-KV-PERSIST`'s own leg and is carried forward unchanged so the three are comparable.
- The runner's wall clock of each whole `ggml-spike` invocation, as the outer bound including
  process start, `dyld`, and the pack open.

**The sentence that must travel with them**, and which the runner prints beside them: neither leg
skips a weight sweep, so a reader who sees leg (b) beat leg (a) is seeing reason 4's exchange —
`T_prefix` columns of prefill compute and the prefill pass's pack read and graph construction, paid
for with a container read — on a prompt of a few tokens, and not a cache.

## 2. Public-contract ledger

Every surface below is exact. Fields marked `N/A` carry their reason. Rows the four prior documents
settled are restated only when they change.

### 2.1 The surface decision: a new operand, and why `TOKENS` is not extended

Three alternatives were weighed. The decision is load-bearing for most rows below, so the reasons
are recorded rather than assumed.

| Consideration | `SUFFIX` at `args[14]` (**chosen**) | Extend `TOKENS` with a split marker (`3,17\|5,9`) | A mode value on an existing operand |
| --- | --- | --- | --- |
| The `akvp` identity checks | **Byte-unchanged.** `TOKENS` still means "the tokens whose plane this is", so L12 (`h.token_count == tokens.count`, each id equal — `decode_step.align:1414,1428-1435`) and L13 (`columns_persisted == token_count`, `:1441-1446`) hold **character for character**, and `src/kv_plane.align` is not edited | **Broken.** `tokens.count` becomes `T_prefix + S`, so L12 refuses every container it should accept. The fix is to teach three identity checks about a split — i.e. to change the format's meaning to buy an operand | Same breakage as the middle column, plus the mode word |
| Meaning of an existing invocation | **Unchanged.** Every legal argv at fourteen operands means exactly what it means today; the fifteenth position is new | **Changed.** `TOKENS`'s grammar is public and `ds-tokens-*` asserts it. A new separator is a new way for an old string to parse | Changed |
| Golden cost of the grammar change | Zero beyond schema 5. The arity ratchet moves `ds-arity-15` → `ds-arity-16`, and both are `NO_DOCUMENT` rows carrying no golden bytes (`run-layer-forward-smoke:3697-3701` documents this ratchet explicitly) | Every `ds-tokens-*` row plus the `lf-`/`mf-` families that share `parse_tokens` | As the middle column |
| Direction legible in the argv | **Yes.** A path in `KV_LOAD` and a list in `SUFFIX` says what this run is, on one line | The split is a character inside a longer string | **No.** A mode word can disagree with the operands' meaning |
| Which operand is the caller's to shorten | **`SUFFIX`.** `TOKENS` is pinned by the container it must match; if the sequence exceeds a cap, `SUFFIX` is the only operand a caller can change. This is why the sequence-cap refusal names `R6_SUFFIX` (2.3) | Ambiguous | Ambiguous |
| Cost | One position, one `-` convention already inherited from `TRANSCRIPT` (R5B), `LOGITS` (R6-STEP-N), `KV_SAVE`/`KV_LOAD` (R6-KV-PERSIST), and `RESIDENT` (R6-RESIDENT-WEIGHTS); one conditional-legality rule, which is new to this arm | — | — |

The first row is the decision. **Keeping `TOKENS` meaning "the container's tokens" is what makes
`src/kv_plane.align` byte-unchanged**, and a capability that extends a persisted format's consumer
without touching the format is strictly cheaper to review than one that does not.

**A second arm was not considered seriously and the reason is recorded so that it is not
re-proposed.** R6-STEP-N section 2.1 and R6-KV-PERSIST section 2.1 each rejected a second arm on the
same two grounds — one loop and one prefill rather than two, and the copy debt R6 section 10.6
records (seven functions already copied because Align Request 49 forbids the cross-module call) —
and neither ground has weakened. `--decode-step-suffix` would additionally fork the plane, the node
window sizing, the oracle set, and a 116-row golden.

### 2.2 The arm and its operands

| Field | Contract |
| --- | --- |
| Surface | `ggml-spike --decode-step` — unchanged; the first operand and nothing else selects the arm |
| Owner module | `src/decode_step.align`, unchanged. `src/kv_plane.align` is **byte-unchanged** (2.1). `src/ggml_spike.align` is **byte-unchanged**: it forwards `args` and does not enumerate arity (`:1610`) |
| Operand grammar | `--decode-step PACK GEOMETRY TOKENS DOCUMENT REFERENCE TRANSCRIPT KV_WIDTH LOGITS STEPS KV_SAVE KV_LOAD RESIDENT SUFFIX` |
| Arity | `args.len()` of 5, 6, 7, 9, 10, 11, 12, 13, 14, or **15**. **8 is still refused** for R6's own reason (a transcript without a width refuses itself). 16 and above are refused. `decode_step.align:3900`'s guard moves from `count > 14` to `count > 15` |
| **How a wrong arity is reported** | **No document and no error code**, unchanged and stated because prior documents named a code that does not exist: `run` returns `Err(Error.Invalid)`, the process exits non-zero, and stdout is empty (`decode_step.align:3899-3902`). `R6_ARITY` and `R6_PATH` are **prose names in comments**, not emitted codes; the smoke asserts these cases as `NO_DOCUMENT` rows. Section 10, finding 1 |
| `PACK` … `RESIDENT` | Unchanged from R6-STEP-N 2.2/2.3, R6-KV-PERSIST 2.2, and R6-RESIDENT-WEIGHTS 3.1 |
| `TOKENS` | **Unchanged in form and in meaning.** It is the **prefix**: on a load run it is what the container's token stream must equal, and on a suffix run it stays exactly that. `1 <= T_prefix <= MAX_PREFILL_TOKENS` (32) |
| `SUFFIX` | `args[14]`. A comma-separated decimal token id list in the **same grammar as `TOKENS`**, reusing `layer_forward.parse_tokens` unchanged, **or `-` for absent**. Absent is the default and is what every schema-4-era invocation means |
| **Conditional legality** | **`SUFFIX` non-`-` requires `KV_LOAD` non-`-`.** Otherwise `R6_KV_ARGS`, detail `suffix[no_load]` (2.3). This is the arm's first conditional operand and 2.3 records why the alternative was rejected |
| Defaults | **None added.** `SUFFIX` absent is `-`, and `-` is the pre-existing behaviour character for character: `args.len() == 15` with `SUFFIX` of `-` is exactly `args.len() == 14`. R6-STEP-N's `STEPS`-absent-is-1 remains the arm's only default |
| Its hazard, and how it is closed | A caller who wants a suffix and forgets the operand silently gets a plain load run. Closed the way every operand on this arm closes it: `suffix.requested` is published in **every** document, including error documents (2.9), so the suffix is never implicit in the output |
| Environment | **None.** No environment fallback, and no environment variable is read by the arm. The runner's `ALIGN_LLM_*` variables are read by `scripts/run-decode-step`, never by `main` |

`SUFFIX` is last rather than earlier for the reason `STEPS` and `RESIDENT` were: every earlier
position is spoken for, and moving one would change the meaning of an existing invocation silently.

### 2.3 `SUFFIX` — grammar, range, caps, and the refusals

| Field | Contract |
| --- | --- |
| Parse | `layer_forward.parse_tokens`, **unchanged and shared with `TOKENS`**, so the two operands cannot drift apart in what they accept. Unparseable, empty, or trailing-separator is `R6_SUFFIX` detail `suffix[<text>]`, bounded to 256 bytes by `bounded_detail` |
| Count | `S >= 1`. **`-` is how a caller says "no suffix"**; an empty string is a malformed list, not an absence, exactly as `LOGITS` distinguishes them (`ds-path-logits-empty`), and it is refused by `parse_tokens` as `suffix[]`. *(This row was drafted with a `count[0]` detail for "a non-`-` operand parsing to zero ids". That check is unreachable — `parse_tokens` refuses an empty list outright — and section 11.1 finding 3 records that it is not implemented.)* |
| **Prefix bound** (added by review repair, **lifted — see 11.5**) | ~~**`T_prefix >= 2`**, raising `R6_SUFFIX` with detail `prefix[<n>]`~~. **`T_prefix >= 1`; the refusal is gone.** The reasoning below was correct when written and stopped being true when MF-SINGLE-TOKEN-LOGITS (roadmap item 36) fixed the gather: A container written for a one-token prefix holds the wrong plane, because `model_forward.fill_members` gathers an embedding row by id only when `pieces > 1` and a one-token prefill therefore computes the embedding of token 0 whatever `TOKENS` said (11.2, `MF-SINGLE-TOKEN-LOGITS`). Oracle S's equality — this capability's own acceptance rule — would silently not hold, so the arm refuses instead of answering wrongly. Section 11.1 correction 8 records why it was a refusal here rather than a fix there, and 11.5 records the lift |
| Why `R6_SUFFIX` and not `R6_TOKENS` for the prefix bound | Because it is the **suffix** that makes the run illegal. Without the operand a one-token `KV_LOAD` run is R6-KV-PERSIST's own leg, unchanged and still accepted — it inherits the defect it always had, and this capability neither widens nor narrows that. The operand a caller must remove is `SUFFIX`, so the refusal names it, which is the same rule the sequence cap follows one row below |
| Vocabulary | `0 <= id < n_vocab` for every id, checked in the same pass that re-checks `TOKENS` after the geometry loads (`stage_inputs` step 3′, `decode_step.align:1776-1781`). `R6_SUFFIX` detail `token[<index>]`, mirroring `R6_TOKENS`'s own detail. *(This row was drafted saying `<i>` is the offending **id**. It is the offending **index**, which is what `R6_TOKENS` has always reported; the row's own "mirroring" clause is what the implementation follows. Section 11.1 finding 3.)* |
| **Sequence cap** | **`T_prefix + S <= MAX_PREFILL_TOKENS` (32).** `R6_SUFFIX` detail `sequence[<n>]`, where `<n>` is `T_prefix + S`. It implies `S <= 32` and is the tighter bound |
| Why the cap is on the **sequence** and not on `S` | Because the cap is the **oracle's**, not the arithmetic's, and it has been since R6 section 2.7. Oracle C″ (3.3) runs `--model-forward` at `TOKENS,SUFFIX` — `T_prefix + S` tokens — so a cap on `S` alone would let the arm accept a run whose own acceptance oracle it refuses. **That is the exact mistake R6-STEP-N's consistency pass caught** (its section 10, finding 2: "Oracle C′ was impossible as first drafted"), and it is caught here before implementation rather than after |
| Why `R6_SUFFIX` and not `R6_TOKENS` for the sequence cap | `R6_TOKENS` owns "the `TOKENS` operand is out of range", and on a suffix run `TOKENS` is **pinned by the container** — a caller cannot shorten it without invalidating L12. The operand a caller can act on is `SUFFIX`, so the refusal names it. One code, four details, is `R6_KV_IDENTITY`'s shape (pack / pack_total_bytes / geometry / pack_absent) and not a new pattern |
| **Plane bound** | `T_prefix + S + N <= KV_WIDTH`, raising **`R6_KV_WIDTH`**, detail `kv_width[<n>]`. This *widens an existing condition* rather than adding one: `decode_step.align:1784` reads `width < parsed.count + steps` and becomes `width < parsed.count + suffix_count + steps`. R6-STEP-N section 2.3 refused to mint a second code for "the plane is too narrow" and its reason — two codes for one condition is how two documents come to disagree — is why this one is not minted either |
| **`SUFFIX` without `KV_LOAD`** | **`R6_KV_ARGS`**, detail `suffix[no_load]` |
| Why `R6_KV_ARGS` is reused | The code already names "the operand combination selecting the plane's provenance is invalid" and already carries one detail that distinguishes its case (`kv[save+load]`). Adding a second detail is cheaper than a second code and keeps one sentence in one place. `SUFFIX` with `KV_SAVE` needs **no separate rule**: `KV_SAVE` and `KV_LOAD` are already mutually exclusive at step 2b, so `SUFFIX` + `KV_SAVE` implies no `KV_LOAD` and is caught by this rule with this detail |
| Why not allow `SUFFIX` without `KV_LOAD` | It would be a second way to reach `n_past > 0` — prefill `TOKENS`, then suffix-prefill `SUFFIX`, in one process — and **it has no consumer**: a caller holding both lists in one process should concatenate them and run one prefill, which is faster and is already supported. Building a second path with no consumer doubles the closure matrix, makes `plane.source` ambiguous, and is exactly what `CLAUDE.md`'s consumer-complete rule exists to prevent. It is recorded as considered and rejected rather than omitted, because it is the cheaper thing to *test* and a later reader will ask |

**Multi-invalid precedence is total and three orderings carry cases of their own**, chosen because
they are the ones a reader would guess wrong:

- `R6_KV_ARGS` (steps 2b and **2c**) precedes every path-content check and every numeric parse, so a
  run whose operand combination is invalid is refused before a file is opened and before `STEPS` or
  `SUFFIX` is parsed. `ds-suffix-no-load-bad-steps` asserts it.
- `R6_TOKENS` (step 3) precedes `R6_SUFFIX` (step **3c**), because `T_prefix` must be a number
  before `T_prefix + S` is one. `ds-suffix-and-bad-tokens` asserts it.
- `R6_SUFFIX` (3c) precedes `R6_KV_WIDTH` (6), for the same sentence, one term later.
  `ds-suffix-over-cap-and-narrow` asserts it.
- **Inside 3c**, the prefix bound used to precede the sequence cap. That bound is **lifted**
  (11.5), so 3c now decides the grammar and then the sequence cap, and `ds-suffix-prefix-one` is a
  passing oracle-S row at `T_prefix = 1` rather than a refusal. `ds-suffix-tokens-mismatch` still
  shows a step-3c-class refusal preceding L12 and every other container check.

### 2.4 The plane — a second writer, and the ordering invariant over three ranges

The plane's layout, size, element type, allocator, zero-fill, and FFI crossing are **unchanged from
R6 section 2.2**. Two rows change and one is new.

| Field | Contract |
| --- | --- |
| Allocated by | `decode_step.execute`, once, before anything, at the declared `KV_WIDTH`, zero-filled by `prime_window`. **Unchanged, never reallocated** |
| Filled by | On a suffix run, in this order and by three distinct writers: (1) `load_plane` fills columns `0 .. T_prefix-1` from the container (unchanged); (2) **the suffix pass writes columns `T_prefix .. T_prefix+S-1`** (new); (3) decode step `k` writes column `T_prefix+S+k-1` (unchanged in code, new in value) |
| Suffix write-back source | The suffix graph's **rows 12 and 10** — the post-RoPE K and the reshaped V, `{head_dim, n_head_kv, S}` — read with `slot_get` after compute. These are the same two rows the prefill reads at `t = T` and a decode step reads at `t = 1`; the suffix reads them at `t = S`. **The concat outputs (rows 16 and 22) are deliberately not the source**, unchanged from R6-STEP-N: row 22's V is transposed, so its columns are strided |
| Why the write is one call and not `S` calls | `capture_plane` computes `span := tokens * column_bytes` and `offset := first_column * column_bytes` (`decode_step.align:1060-1063`), and the plane's within-tensor order is column-major with `head_dim` fastest, so `S` consecutive columns are one contiguous byte range and rows 12/10 are one contiguous node. **One `slot_get` per layer per tensor**, exactly as the prefill does at `(T, 0)` |
| `columns_written` | `T_prefix` after the load, `T_prefix + S` after a **complete** suffix pass, `T_prefix + S + N` after a complete loop. The advance is made by the suffix pass **after its last layer**, never per layer — `capture_plane`'s own `if first_column == 0` guard (`:1095-1096`) does not fire at `first_column = T_prefix`, and this is a **feature**: the accounting stays where the prior documents put it, in the caller that knows the pass completed. `decode_step.align:1093-1095`'s comment (a per-layer advance would let a run that failed at layer 4 publish columns it did not verify) applies verbatim |
| **Ordering invariant, extended** (new) | R6-STEP-N replaced R6's *exclusion* with **disjointness plus ordering** over two ranges. This capability keeps the same shape over three. Within the suffix graph, in this order: (1) **before compute**, the plane's columns `0 .. T_prefix-1` are a `slot_set` **source**, uploaded into `MF_SLOT_KPAST`/`MF_SLOT_VPAST`; (2) compute; (3) **after compute**, the plane's columns `T_prefix .. T_prefix+S-1` — and only those — are a `slot_get` **destination**. The uploaded range and the written range are disjoint by construction, adjacent, and separated by a completed compute. No call is ever both, and no graph reads a column it also wrote. The only generalisation from R6-STEP-N is that the written range has length `S` rather than 1 |
| Verification | Oracle B, over `T_prefix + S` columns, **inside the suffix pass and before the first decode step**. `verify_plane`'s bound moves from the hardwired `columns := n_past + 1` (`decode_step.align:1121`) to `n_past + tokens`; at `tokens = 1` it is R6-STEP-N's expression character for character. Section 3.4 |
| Aliasing | Follows from the row above and is asserted rather than asserted-by-assertion: oracle B at the suffix pass compares the graph's own concatenated operands (rows 16/22) against the plane over **every column the plane holds**, so a suffix write that landed in a loaded column would change a column the same comparison covers |
| Freed by | Align, at `execute`'s scope end, on every path. Unchanged |

**The one column-accounting hazard, named because it is the shape of a prior finding.** A suffix
pass that fails at layer `j` has written columns `T_prefix .. T_prefix+S-1` for layers `0 .. j-1`
and nothing for the rest. `columns_written` stays `T_prefix`, the document reports
`suffix.columns_written = T_prefix`, no decode step runs, and the plane is freed — so no reader ever
sees the partial rows. That is R6-STEP-N section 2.8's stale-plane rule applied to a pass instead of
a step, and 2.8 below states it as such.

### 2.5 The graph — the decode table at `tokens = S`

This is the implementation, and it is a token count reaching the literals that assume one column.
The table below names **five**, in two functions; implementation found a **sixth**, in a third
(section 11.1 correction 4), and that count — six literals across three functions — is the one to
carry forward.

`layer_qwen2.mf_decode_layer_node_table(g, n_past, width)` builds 38 rows and its own comment
(`:1682-1685`) says they are "the prefill layer's thirty-six at `tokens = 1`, plus one `CONCAT` on K
and one on V". Every place that `1` is written is a place `S` belongs:

| Site | Today | Becomes |
| --- | --- | --- |
| `mf_decode_row_head(g, row)`, `:1702` | `mf_layer_row_head(g, 1, row)` | `mf_layer_row_head(g, tokens, row)` |
| `mf_decode_row_attention` row 15 (`CONT_3D` on K), `:1721` | `r.p1 = 1` | `r.p1 = tokens` |
| `mf_decode_row_attention` row 17 (`PAD` on K), `:1728` | `r.p1 = width - (n_past + 1)` | `width - (n_past + tokens)` |
| `mf_decode_row_attention` row 21 (`CONT_3D` on V), `:1751` | `r.p0 = 1` | `r.p0 = tokens` |
| `mf_decode_row_attention` row 23 (`PAD` on V), `:1763` | `r.p0 = width - (n_past + 1)` | `width - (n_past + tokens)` |

| Field | Contract |
| --- | --- |
| Signature | `mf_decode_layer_node_table(g, n_past, tokens, width)` and `mf_decode_row_attention(g, n_past, tokens, width, row)` gain one parameter each. **The decode loop passes `1` and its bytes are unchanged by construction**, exactly as `mf_write_mask` is defined as `mf_write_mask_offset`'s `row_offset = 0` case |
| Concat axes | **Unchanged and still different per tensor.** K is `{head_dim, columns, n_head_kv}` after row 15, so its axis is **1**; V is `{columns, head_dim, n_head_kv}` after row 21, so its axis is **0**. `op_concat` returns `ALIGN_GGML_SHAPE` when any axis but `dim` differs, and at `tokens = S` only the concat axis differs between the two operands, so the guard still holds |
| Node count | **38 per layer, unchanged.** No row is added, removed, or made conditional; five parameters change value in this table, and a sixth in `mf_decode_row_tail` (11.1 correction 4). `MF_DECODE_LAYER_NODE_COUNT` is not edited |
| Slots | **Unchanged.** `MF_SLOT_KPAST` 64 and `MF_SLOT_VPAST` 65 are declared at `{head_dim, n_past, n_head_kv}` and `{n_past, head_dim, n_head_kv}` by `decode_layer_inputs` (`decode_step.align:750,764-768`), which is already parameterised by `n_past` and does not mention the new token count. High-water stays 66 against a capacity of 128 |
| **The `WHEN_LAST` narrowing rows** | **Kept, and for the first time they are not the identity.** R6 kept `get_rows(x, [t-1])` at `t = 1` where it is the identity, "to keep one shape rule for both passes". At `t = S` it selects the last suffix token — which is exactly the position whose logits the run wants, and exactly what the prefill's own narrowing does at `t = T`. `out_ids` is written as `tokens.count - 1` (`decode_step.align:2731`) and is therefore `S - 1` in suffix-relative coordinates, **which is already correct**: the row index is into the pass's own `S`-row window, not into the sequence. This is the single place where a reader most naturally expects an absolute index and the correct value is relative, so 2.6 states the id/position split again for it |
| Mask | `mf_write_mask_offset(buf, KV_WIDTH, S, T_prefix)`. Row `r` unmasks `col <= r + T_prefix`: columns `0 .. T_prefix-1` open for every row, columns `T_prefix .. T_prefix+r` open (self and earlier suffix tokens), everything above `-inf`. That is the `S × (T_prefix + S)` causal block embedded in an `S × KV_WIDTH` image, **with no change to the writer**. Buffer size `KV_WIDTH * S * 4` |
| Two things about the mask writer that are **not** changed and are recorded | (a) Its doc comment at `layer_qwen2.align:2159` says "columns at or beyond `height` are `-inf` for every row", which is true only at `row_offset = 0` and becomes false for this caller. **The comment is corrected**; this repository treats comments as contract. (b) It has no `row_offset + height <= width` guard, and a caller supplying one would produce trailing all-zero rows rather than a refusal. **No guard is added to the writer**: the condition is `T_prefix + S <= KV_WIDTH`, which is a strictly weaker consequence of validation step 6's `T_prefix + S + N <= KV_WIDTH`, so the arm cannot reach it. Section 4.3 records this as a deferred cell with that reason rather than adding an unreachable check |

### 2.6 What the suffix pass computes, and what it reuses

The suffix pass is **`decode_pass` at `tokens = S`**, and the distinction between what it inherits
and what it supplies is the whole implementation.

| Object | Source on a decode step | Source on the suffix pass |
| --- | --- | --- |
| The layer graphs | `mf_decode_layer_node_table(g, n_past, 1, width)` | the same table at `tokens = S` (2.5) |
| The mask | `mf_write_mask_offset(buf, width, 1, n_past)` | `mf_write_mask_offset(buf, width, S, T_prefix)` |
| **The position image** | `[n_past]`, one i32 | **`[T_prefix .. T_prefix+S-1]`, `S` i32s.** One new producer loop, `put_u32_le((T_prefix + i) as u32)`, which is the prefill's loop (`decode_step.align:2722-2728`) with a base. The decode arm already builds an absolute-position image at `:2733-2739`, so this is an existing shape at a new width |
| **The token-ids image** | constant `0` — the row index into a one-row gathered window | **`0 .. S-1`** — the row indices into an `S`-row gathered window. **This is the prefill's `index_image` exactly**, and it is *not* the position image. R6's id/position split (`model_forward.graph_input_values`, `:1796-1806`) is what makes the two expressible at once, and this pass is the first caller for which they differ **and** both have `S` entries |
| **The embedding rows** | `decode_embed_members(g, ends, token_id)` — one row, the sampled token | **the prefill's `build_embed_members`** (`model_forward.align:1449`) at `pieces = S`, gathering by operand id. The gather is position-independent, so no change is needed to it. This is the one seam where the suffix pass takes the *prefill's* builder and the *decode's* layer table, and 4.4 is the closure cell for it |
| `out_ids` | `[0]` | `[S - 1]` — `tokens.count - 1` in the pass's own coordinates (2.5) |
| The past operands | `MF_SLOT_KPAST`/`VPAST` at `n_past = T` columns | the same slots at `n_past = T_prefix` columns. `stage_past_k`/`stage_past_v` (`decode_step.align:552,579`) are already parameterised by `n_past` |
| The write-back | `capture_plane(.., 1, n_past, ..)` | `capture_plane(.., S, T_prefix, ..)` |
| The verification | `verify_plane(.., n_past, ..)` over `n_past + 1` columns | the same function over `T_prefix + S` columns (2.4) |
| Plane, slots, backend, weight window or arena, logits buffers, `node_window` | allocated once, reused | **unchanged.** `node_window` is already sized `width * n_head_kv * head_dim * 4` — the *widest* concat operand at any point in the run — and `T_prefix + S + N <= KV_WIDTH` keeps that true |

**One graph set, not `S` of them.** The suffix pass builds `2 + n_layer` graphs (the embedding
gather, the layers, the head) — the same count as a prefill or a decode step — and computes all `S`
columns in them. It is not a loop of `S` decode steps, and 3.2's oracle is what proves the
difference does not matter arithmetically.

### 2.7 Validation order and refusal codes

R6-KV-PERSIST's steps 1–16 with L1–L14 and W1–W4 keep their order and their codes. This capability
inserts **2c** and **3c**, widens **6**, and appends **X1–X5** after L14.

| # | Step | Code | Detail |
| --- | --- | --- | --- |
| 1 | arity in {5,6,7,9,10,11,12,13,14,15} | *(no document; `Err(Error.Invalid)`)* | — |
| 2 | supplied paths valid; `-` in `TRANSCRIPT`/`LOGITS`/`KV_SAVE`/`KV_LOAD` is absent | *(no document)* | — |
| 2b | not both `KV_SAVE` and `KV_LOAD` | `R6_KV_ARGS` | `kv[save+load]` |
| **2c** | **`SUFFIX` non-`-` implies `KV_LOAD` non-`-`** | **`R6_KV_ARGS`** | **`suffix[no_load]`** |
| 2d | `RESIDENT` grammar | `R6_RESIDENT` | `resident[<text>]` |
| 3 | `TOKENS` parses, `1 <= T_prefix <= MAX_PREFILL_TOKENS` | `R6_TOKENS` | `token[<index>]` — `parse_tokens`' own index, for a bad id **and** for an over-long list; three prior documents in this family printed `count[<n>]` here and no such detail is emitted (11.1 finding 3) |
| 3b | `STEPS` parses, `1 <= N <= MAX_DECODE_STEPS` | `R6_STEPS` | `steps[<n>]` |
| **3c** | **`SUFFIX` parses; `T_prefix + S <= MAX_PREFILL_TOKENS`** (the `T_prefix >= 2` term is **lifted**, 11.5) | **`R6_SUFFIX`** | **`suffix[<text>]` / `sequence[<n>]`**, decided in that order |
| 3a–5 | geometry readable, loads, dense | unchanged | unchanged |
| 3′ | `TOKENS` **and now `SUFFIX`** re-checked against the real `n_vocab` | `R6_TOKENS` / **`R6_SUFFIX`** | `token[<index>]` |
| 6 | `KV_WIDTH` parses, **`T_prefix + S + N <= KV_WIDTH <= MAX_ATTENTION_WIDTH`** | `R6_KV_WIDTH` | `kv_width[<n>]` |
| 6a–6b, 7–8, 7b | persisted bounds, destination, pack members, pack identity | unchanged | unchanged |
| L1–L14 | the container: open, header, regions, geometry, identity, width, tokens, `columns_persisted`, digests, refill | **unchanged** | unchanged |
| **X1** | **the suffix pass's graph set runs** | `R5_*` | prefixed `suffix[]` |
| **X2** | **the suffix write-back**, columns `T_prefix .. T_prefix+S-1` | `R6_PLANE_WRITE` | `suffix[]layer[<n>]tensor[k\|v]` |
| **X3** | **oracle B over `T_prefix + S` columns** | `R6_PLANE_MISMATCH` | `suffix[]layer[<n>]tensor[k\|v]col[<n>]` |
| **X4** | **`columns_written` advances to `T_prefix + S`** | — | — |
| **X5** | **the suffix pass's last-position logits become `output.*`**; `oracle_logits` compares them against `LOGITS` | `R5_LOGITS_*` | unchanged |
| 11′–16 | decode loop from `n_past = T_prefix + S`, per-step round trip, transcript oracle, width, self-reference | **unchanged in code**; every step's `n_past` is `T_prefix + S + k - 1` | `step[<k>]` prefixed, unchanged |

**`R6_SUFFIX` is the one new code.** There is deliberately no `R6_SUFFIX_FAILED`: a suffix pass that
fails fails for a reason that already has a code, and what the pass adds is a **locator** — the
detail prefix `suffix[]`, which is eight bytes against `bounded_detail`'s unchanged 256-byte cap and
is deliberately the same shape as `step[<k>]` with no index, because there is exactly one suffix
pass.

### 2.8 Failure inside the suffix pass — what the document holds

The rule is R6-STEP-N section 2.8's, applied to a pass instead of a step: **a partial suffix pass
publishes no completion.**

| Field | On a failure inside the suffix pass |
| --- | --- |
| `status` / exit code | `error`, non-zero. `(returncode == 0) == (status == "ok")` unchanged |
| `error_code` / `error_detail` | the raising code, detail prefixed `suffix[]` |
| `suffix.requested` / `token_count` / `n_past_base` | `1`, `S`, `T_prefix` — the operands, always |
| `suffix.completed` | `0` |
| `suffix.columns_written` | `T_prefix` — the loaded plane's, unchanged by a pass that did not finish |
| `suffix.compute_ns` / `node_count` / `graph_count` / `pack_bytes` | **`0`.** The partial pass contributes no counts, for R6-STEP-N's reason: a sum that no published completion accounts for is a half-filled row wearing a different name. How far the pass got is named by `error_detail` |
| `plane.columns_written` | `T_prefix` |
| `plane.roundtrip_verdict` | `-`, unless oracle B already reported `MISMATCH`, which is sticky. **Never `IDENTICAL` on an error document** |
| `output.*`, `oracle_logits` | the **container's** persisted vector and its comparison, as on an ordinary load run. The suffix pass produced no logits, so it replaces none (2.9) |
| `decode.*`, `steps[]` | `steps_completed` 0, `steps[]` empty, `token_ids` empty — the loop never started |
| The plane | **Freed**, at `execute`'s scope end, on this path as on every other |

### 2.9 The document — `R6_DECODE_STEP`, schema 5

| Field | Contract |
| --- | --- |
| `kind` | **`R6_DECODE_STEP`, unchanged.** The document describes the same thing; how the plane reached `n_past` is a field, not a kind. A new kind would make `scripts/run-decode-step` and the fifth smoke block branch on kind for no semantic difference |
| `schema_version` | **5.** `decode_step.align:50` |
| New: the `suffix` object | Present in **every** document, including error documents, with one shape at every arity. Inserted between `kv` and `weights` in `render`, which is where `weights` itself was inserted |
| **Changed: `output` and `oracle_logits` on a suffix run** | On a **completed** suffix pass they describe the **suffix pass's last-position logits** — the logits of the sequence `TOKENS ++ SUFFIX` — and not the container's vector. `output.sha256` is that vector's digest, `output.argmax` is `d_1` for the decode loop, and `oracle_logits` compares it against the `LOGITS` blob. On a load run **without** a suffix, and on a suffix run that failed, they are the container's vector exactly as R6-KV-PERSIST section 2.8 defines. See below |
| **Changed: `plane.source`** | **Stays `"LOADED"`.** It names where the *plane* came from, and the plane came from the container; that the arm then extended it is `suffix.requested`'s sentence. Widening the enum to `"LOADED+SUFFIX"` would make every consumer of `plane.source` learn a third value to answer a question a boolean already answers |
| `decode.n_past_first` / `n_past_last` | `T_prefix + S` and `T_prefix + S + N - 1` on a suffix run. The field's *meaning* is unchanged |
| `selection.token_count` | **`T_prefix`, unchanged.** It is the `TOKENS` operand's count and `TOKENS` still means the prefix (2.1). `suffix.sequence_length` is what a reader compares against a single-shot run's `selection.token_count`, and 3.2 asserts that equality explicitly rather than leaving it to a diff |
| `plane.columns_written` | `T_prefix + S + N` on a complete run |
| `kv`, `weights`, `pack`, `model`, `schedule`, `graph`, `head`, `reference`, `timings`, `lifetime`, `abi` | **Unchanged in shape.** `kv.prefill_argmax` and `kv.logits_sha256` continue to publish the *container's* claim, which is what makes the `output` change safe: the container's vector is never lost, it moves out of `output` and stays in `kv` |
| Float fields | **Never floats on the wire, unchanged.** Every digest is a lowercase hex `sha256` over exact little-endian f32 bytes; every tolerance is in integer ten-thousandths or millionths |
| **No path-valued field** | `suffix` publishes **no path** and no token list. R6-STEP-N risk 5 names the temp-path golden class; schemas 3 and 4 were verified free of it and schema 5 keeps the property |
| Field presence | One shape at 5 operands and at 15. No conditional-presence rule |
| `normalize` | Zeroes `suffix.compute_ns` in addition to everything schema 4 already zeroes. **`suffix.node_count`, `graph_count`, `pack_bytes`, `columns_written`, `token_count`, `n_past_base`, and `sequence_length` are not normalized**: they are deterministic and they are the contract |
| Persisted identity | **Unchanged.** Nothing new is persisted; 2.1's whole point is that the `akvp` format does not move |
| **Container `document_schema_version`** | **Stays 3, and `src/kv_plane.align` is byte-unchanged.** See the finding below |
| Cache identity | **N/A, and for R6-KV-PERSIST's reason**: there is no cache. The tuple a cache key would be is recorded in that document's section 2.8 and is **not** re-derived here, so a later capability finds one recorded tuple and not two |

The `suffix` object, in declaration order:

```text
suffix.requested         0 | 1
suffix.completed         0 | 1
suffix.token_count       S, or 0 when absent
suffix.n_past_base       T_prefix, or -1 when absent
suffix.sequence_length   T_prefix + S, or -1 when absent
suffix.columns_written    T_prefix + S on a completed pass; T_prefix on a failed one; -1 when absent
suffix.first_column      T_prefix, or -1 when absent
suffix.graph_count       0 when absent
suffix.node_count        0 when absent
suffix.pack_bytes        0 when absent; exactly 0 in resident mode
suffix.compute_ns        0 when absent; zeroed by `normalize`
```

**Why `output` moves rather than a second digest being added, and what the hazard is.**

| Candidate | Rejected / chosen because |
| --- | --- |
| A new `suffix.sha256` / `suffix.argmax`, `output` keeps the container's vector | Rejected. `oracle_logits` compares `output` against the `LOGITS` blob, and on a suffix run the blob a caller supplies is `llama-debug --save-logits` for the *whole* prompt (3.5). Leaving `output` as the container's would make the arm's only external byte-exact oracle compare the wrong vector — or force a second logits oracle, which is two comparisons named the same thing |
| **`output` describes the run's own last prefill-shaped result** (chosen) | The field already means "this run's prefill logits", and on a suffix run the run's prefill *is* prefix-plus-suffix. Oracle C″ becomes a one-line comparison on an existing field (3.3), and gate G1 survives to the suffix (3.5). The container's vector is not lost: it stays in `kv.logits_sha256` and `kv.prefill_argmax`, both already published |

The hazard is that a reader who learned `output` from R6-KV-PERSIST expects the container's vector
on any `KV_LOAD` run. It is closed the way this arm closes every such hazard: `suffix.requested` and
`suffix.completed` are in **every** document, `kv.*` still carries the container's claim unchanged,
and the qualification asserts `output.argmax == kv.prefill_argmax` on a load run **without** a
suffix and asserts they **differ** on one with a suffix whose first token changes the answer — so
the distinction is a test rather than a paragraph. This is a public field's behaviour changing on a
new operand combination, which is precisely what R6-KV-PERSIST did for `reference.verdict`, and it
is recorded in the same shape.

**A latent inconsistency this capability found and does not propagate.** `src/kv_plane.align:41`
holds `DOCUMENT_SCHEMA_VERSION := 3`, is written into every container's header at offset 136, and is
**refused when it differs** (`:535-536`, `R6_KV_HEADER("document_schema_version")`). The document
schema is already **4**. So `R6-RESIDENT-WEIGHTS` bumped the document and left this constant, and
the field no longer means what `docs/specs/r6-kv-persist.md` section 2.8 says it means ("binding a
file to the document vintage that wrote it"). **This capability leaves the constant at 3**, for two
reasons: moving it would refuse every existing container, gaining nothing — the container's contents
do not depend on the document schema — and the two versions are already declared independent by that
same section. What changes is the **prose**: a one-line correction to `r6-kv-persist.md`, saying
that the field records **the document schema the format was defined against**, which is 3 and is
expected to stay 3 until a region changes. Section 10, finding 3; section 9's table records where it
landed, and section 11.3 deviation 6 records why the matching source comment was **not** written.

### 2.10 Metrics

Characterization only. **No TTFT claim, no tokens-per-second claim, no comparison to llama.cpp's
wall time, and no cost ceiling recorded in a ledger row**, because this capability makes no
performance claim and `CLAUDE.md`'s performance row is therefore not selected. `R6-RESIDENT-WEIGHTS`
section 3.4 owns Track B decode performance and defines the 150,000 ppm shipping floor; **this
capability does not clear it and does not try to**, because what it removes (1.4, reason 4) is
`T_prefix` columns of prefill compute on a fixed task whose dominant term that document already
removed.

| Metric | Source | Reported as |
| --- | --- | --- |
| Suffix pass cost | `suffix.compute_ns`, `suffix.node_count`, `suffix.graph_count` | Per prompt per split point |
| Suffix pass weight reads | `suffix.pack_bytes` | Non-zero streamed; **exactly 0** in resident mode, asserted |
| Columns extended | `suffix.token_count`, `suffix.columns_written` | Asserted exactly |
| Bytes verified by oracle B at the suffix pass | `plane.roundtrip_bytes_compared`'s first contribution | `2 · n_layer · (T_prefix + S) · n_head_kv · head_dim · 4`, asserted |
| **TTFT proxy** | `timings.first_token_ns` and the invocation wall clock, on the three legs of 1.4 | **Labelled diagnostic. The range (`min..max`) over three runs, on one host. No median, no spread, and no derived rate**, and 1.4's sentence printed beside them |

**Saturation, checked rather than assumed** (a named prior failure class). Every accumulated
quantity is `i64`. `suffix.pack_bytes` is bounded by one graph set's sweep of a pack bounded by
`MAX_KV_CONTAINER_BYTES`-independent alignpack limits and is under `10^10` on the reference model;
`suffix.compute_ns` is one pass under `10^10` ns; `suffix.node_count` is `38 · n_layer + head` under
`10^4`. `plane.roundtrip_bytes_compared` gains one term of at most `2 · 28 · 32 · 4 · 128 · 4 ≈ 3.7
× 10^6` on top of R6-STEP-N section 2.10's `3.0 × 10^10` worst case, which does not move its order
of magnitude. Nothing here saturates and no accumulator is widened.

### 2.11 Prerequisites

| Prerequisite | State |
| --- | --- |
| Everything R6, R6-STEP-N, R6-KV-PERSIST, and R6-RESIDENT-WEIGHTS list | Shipped on `main` at `553563e`, unchanged |
| `capture_plane` general in `first_column` | **Verified by reading at the pin**: `decode_step.align:1060-1086` computes `span`/`offset` from `tokens`/`first_column` and bounds-checks `offset + span > stride`. No caller uses both non-trivially today |
| `mf_write_mask_offset` general in `height` at non-zero `row_offset` | **Verified by reading at the pin**: `layer_qwen2.align:2178-2193`, `col <= row + row_offset` over `height` rows. No caller uses both non-trivially today |
| `op_concat` accepting an operand wider than one column | **Verified by reading**: the shim returns `ALIGN_GGML_SHAPE` only when an axis *other than* `dim` differs. `layer_qwen2` rows 16/22 concat on axes 1 and 0 respectively and the non-concat axes are `head_dim`/`n_head_kv`, which do not depend on the token count |
| `layer_forward.parse_tokens` reusable for a second list | **Verified**: it is already called twice on this arm (`stage_inputs` steps 3 and 3′) with different vocabulary bounds |
| A real model and instruments for the qualification | Unchanged: the pinned `llama-eval-callback` (generation `r2c-v2`), `llama-debug`, `numpy`, and the 12 GiB physical-memory preflight for the resident leg |
| Align language features | **None new.** Section 8 records four continuing gaps; none blocks this |

### 2.12 Exact-prefix only, and what that forecloses

The container's tokens must equal `TOKENS` **element for element**, and `columns_persisted` must
equal `token_count`. Both are existing checks (L12, L13) and neither moves. The consequence is worth
stating because it is the difference between this capability and the one the roadmap gate wants:

- A container saved for `a,b,c` **cannot** serve a run whose prefix is `a,b`, even though its
  columns 0 and 1 hold exactly the right bytes. Serving it would mean loading `T_prefix = 2` columns
  out of a 3-column plane, which is `columns_persisted != token_count` — a semantics
  `docs/specs/r6-kv-persist.md` section 7 already defers.
- **RoPE positions are absolute and that is why the *other* direction is impossible rather than
  merely undone.** Column `j` of a saved plane holds K roped at position `j`. A prefix can be
  *extended* at positions `T_prefix ..` — which is this capability — and can never be *re-based*:
  the same tokens at a different offset are different bytes, so there is no container that serves
  two prompts with a shared but differently-positioned span. Prefix sharing is therefore inherently
  a **left-anchored** relation, and any later cache key must be over left-anchored spans.

## 3. Oracles and the acceptance rule

R6-STEP-N's gate G, oracle B, oracle C′, and oracle A′ and R6-KV-PERSIST's oracles P and Q are
**unchanged and carry forward**. One is added, two are re-scoped, and one is explicitly not
available.

### 3.1 The question the design turns on, and how it was settled without a probe

`docs/specs/r6-decode-kv-step1.md` section 3.2 measured that llama.cpp's own single-shot `T+1`
prefill and its own incremental decode step disagree by up to 0.1699 in activations and 0.054 at the
logits, attributed to a `MUL_MAT` accumulation path that its build selects differently at seven
columns than at one (`LLAMAFILE = 1`). **The question this capability must answer is whether the
same column-count sensitivity bites a suffix pass of `S >= 2` columns compared against a single-shot
prefill of `T_prefix + S`.** If it does, oracle C″ cannot be acceptance.

**It is answered from measured evidence in the two prior documents, and the answer is no.** The
evidence is arm-internal, which is what makes it apply:

1. That same section 5.1 records three digests that are **the same 608,256 bytes**: this arm's
   `--decode-step` logits at `n_past = 6` (a **one**-column graph), this arm's `--model-forward` at
   **seven** tokens, and `llama-debug --save-logits` on the corresponding text. Its own conclusion:
   "every operand this arm hands ggml is a contiguous F32 tensor and both of its own paths take the
   same one, so its decode step lands on the prefill's answer and llama.cpp's does not."
2. `docs/specs/r6-step-n.md` section 5.1 extends that from one point to three: oracle C′ was
   byte-identical at `k ∈ {1, 8, 16}` on all four prompts, comparing this arm's **one**-column
   decode step against its own single-shot prefills at **7, 14, and 22** columns.

So the property "this arm's logits do not depend on how many columns the graph computes them in" is
**measured over 1 versus 7, 14, and 22 columns, on four prompts, on the real model, on every run of
two capabilities**. A suffix pass at `S` versus a single-shot at `T_prefix + S` is a comparison
strictly inside that range for any admissible operands (`T_prefix + S <= 32`, 2.3). **The divergence
R6 measured is llama.cpp disagreeing with itself, and both sides of oracle C″ are this arm's own
graphs, so it cannot appear there at all.** It can appear only against the transcript, which is why
oracle A′ keeps its existing status and gains nothing (3.6).

**The one honestly new thing**, stated rather than argued away: the suffix graph is the first this
arm builds with `S >= 2` columns **and** `n_past > 0`. Every prior `S >= 2` graph had `n_past = 0`
and every prior `n_past > 0` graph had one column. The attention `MUL_MAT`'s operands are the same
shapes as a `T_prefix + S` prefill's on the K/V side (both are `PAD`ded to `KV_WIDTH`) and differ
only in `Q`'s column count — which is exactly the axis the measured invariance covers. So the
combination is new and the *sensitivity* it could expose is the one already measured absent.

**The `llama-debug` probe named in the brief was not taken, and why is recorded rather than
omitted.** A run was reserved to settle this empirically; `pgrep -f llama-server` found a live
server (pid 22863) and the host is shared with other agents, so no model was loaded. It was not
needed: the question is about *this arm's* two paths, and this arm's two paths are what oracles C
and C′ already compare byte-for-byte on every qualification run. **The escalation, if oracle C″ ever
fails, is named here so it is not re-derived:** compare `--model-forward` at `T_prefix + S` against
`--model-forward` at `S` on the same trailing tokens with a zeroed plane, which isolates ggml's
column-count sensitivity from this capability's arithmetic, and only then reach for llama.cpp.

### 3.2 Oracle S — the suffix run and the single-shot run are the same run

**Internal, byte-exact, acceptance. This is the capability's headline oracle.**

For a prompt whose token list is `L` and a split index `j`, two invocations:

```text
single  ggml-spike --decode-step PACK GEOM L        DOC.one.json  REF TRANSCRIPT W LOGITS N - -        R -
suffix  ggml-spike --decode-step PACK GEOM L[:j]    DOC.sfx.json  REF TRANSCRIPT W LOGITS N - KV.akvp R L[j:]
```

With `normalize_suffix` defined as `normalize` plus dropping the keys below, the two documents must
be **byte-identical**.

```text
excluded blocks (7): kv, suffix, graph, schedule, timings, lifetime, reference
excluded fields (11): plane.source, plane.readback_ns, plane.upload_ns,
                      selection.token_count,
                      head.node_count, head.pread_ns, head.compute_ns,
                      pack.reader_pread_count, pack.reader_bytes_read,
                      window.reuse_count, window.member_placements
```

Every exclusion is justified rather than convenient, and the list is **fixed by this document** — an
exclusion list that grows during implementation is the mechanism by which an equality oracle becomes
vacuous, so a needed addition is a finding and is recorded as one (10, finding 6 reserves the
shape).

| Excluded | Why it must differ |
| --- | --- |
| `kv`, `suffix`, `plane.source` | They **are** the difference |
| `graph`, `schedule` | The suffix run builds one graph set over `S` columns where the single-shot builds one over `T_prefix + S`; node and graph counts legitimately differ. `head.node_count` follows |
| `selection.token_count` | `T_prefix` versus `T_prefix + S`, by 2.9's decision that `TOKENS` keeps its meaning. **Replaced by an explicit assertion**: `suffix_run.suffix.sequence_length == single_run.selection.token_count`. This is the one exclusion that removes a *semantic* field, so it is compensated rather than merely justified |
| `timings`, `lifetime`, `plane.*_ns`, `head.pread_ns`, `head.compute_ns` | Wall clock, and ggml object counts that follow the graph count |
| `pack.reader_*`, `window.*` | The two runs read different member sets: the suffix run loads a plane instead of computing `T_prefix` columns |
| `reference` | R5B's byte comparison against the source GGUF lives inside the prefill pass. R6-KV-PERSIST already set `reference.verdict` to `"-"` on a load run and a suffix run is a load run, so the single-shot's `"IDENTICAL"` and the suffix run's `"-"` are the existing, settled difference |

**What that leaves inside the comparison is the point**, and it is more than oracle Q leaves:
**`output` in full — the suffix pass's own logits against the single-shot prefill's**, which is
oracle C″ (3.3) *inside* oracle S; `oracle_logits` in full, so gate G1 is compared on both sides;
`decode` in full including `token_ids`; every object of `steps[]` including each step's `sha256`,
`argmax`, `n_past`, `plane_column_written`, and complete `oracle` sub-object;
`plane.columns_written`, `roundtrip_verdict`, `roundtrip_bytes_compared`, and every
`first_mismatch_*`; `oracle_decode` in full; and `model`, `head`, `abi`, `weights`.

A one-lane error anywhere in the suffix pass — a mask row off by one, a position off by one, a
write-back at the wrong column, a concat on the wrong axis — changes `output.sha256` and therefore
`steps[0].token_id` and every step after it.

### 3.3 Oracle C″ — the single-shot self-reference

**Internal, byte-exact, acceptance.** `--model-forward` at `TOKENS,SUFFIX` and the same `KV_WIDTH`,
with `-` in the transcript position, must produce logits **byte-identical** to the suffix run's
`output.sha256`.

It is R6-STEP-N's oracle C′ with the checkpoint moved from a decode step to the suffix pass, it runs
on the **existing** instrument, and 3.1 is the argument for why it is acceptance rather than
characterization. It is retained **in addition to** oracle S, which contains it, for two reasons:
oracle S compares two `--decode-step` runs and would pass if both were wrong in the same way, while
C″ compares against a *different arm* built from the prefill row table rather than the decode one;
and C″ is the oracle that fails informatively when oracle S fails, because it isolates the suffix
pass's logits from the loop that follows.

R6-STEP-N's oracle C′ at `k ∈ {1, ⌈N/2⌉, N}` is **unchanged and still runs**, now at
`TOKENS,SUFFIX,d_1..d_k` — which is why 2.3's sequence cap matters and why the runner, not the arm,
must keep `T_prefix + S + N <= MAX_PREFILL_TOKENS` for its own checkpoints (5.4).

### 3.4 Oracle B — the plane round trip, over `T_prefix + S` columns

**Internal, byte-exact, acceptance, unchanged in kind.** After the suffix write-back and **before**
the first decode step, the K and V the suffix graph actually consumed — its two `CONCAT` nodes (rows
16/22) read back with `slot_get` — must be byte-identical to the plane over columns `0 ..
T_prefix+S-1`, on every layer. Two things follow from the prior design and neither is new:

1. It **includes the columns just written**, because the write-back precedes the verification. The
   columns the graph produced (rows 12/10) and the columns the plane holds are compared through a
   *different* node, so a suffix write-back one lane off, in the wrong tensor, or at the wrong
   column dies in the suffix pass rather than in step 1 or never.
2. It **re-verifies the loaded columns**, so a container that decoded correctly and a refill that
   landed correctly are re-checked by the arithmetic that consumes them.

`verify_plane`'s bound moves from `n_past + 1` to `n_past + tokens`; at `tokens = 1` it is
R6-STEP-N's expression unchanged, which is what keeps every existing step's byte count identical.
`roundtrip_verdict` is `IDENTICAL` iff the suffix pass's comparison and every step's was.

### 3.5 Gate G, re-rooted — and the leg that gets *cheaper*

Gate G is unchanged in method and re-rooted in one place.

- **G1 — the byte-exact root.** On a suffix run, `oracle_logits` compares the **suffix pass's**
  logits against a `llama-debug --save-logits` blob. **The blob is the one the existing
  qualification already has**, because it is `llama-debug` on the *whole prompt text*, and `TOKENS
  ++ SUFFIX` is the whole prompt's id list by construction (5.4). So G1 survives to the suffix at
  **zero additional `llama-debug` cost**, and `d_1` is again the argmax of a vector proved
  byte-identical to llama.cpp's.
- **This is where the missing detokenizer stops mattering, and it is worth naming.**
  `docs/specs/r6-step-n.md` section 3.3 records that the external text leg stays hand-measured
  because turning decoded ids back into text needs Request 22. A **suffix is not decoded** — it is
  an operand, obtained by splitting an id list the instrument printed — so no detokenization is
  required and no hypothetical surface is consumed. **Request 22's status does not change**, and
  this capability adds no client to it.
- **G2 — `d_1 .. d_N` through the `embd` fingerprint**, against transcript graph `k+1`. Unchanged,
  including the per-run collision measurement by `scripts/decode_step_fingerprint.py` and the
  per-step membership check. The suffix pass has no transcript counterpart (3.6) and G2 does not
  compare it.
- **G3** remains named, costed, and **not taken**, on R6-STEP-N's terms.

### 3.6 Oracle A′ — what it compares, and what has no counterpart

**Unchanged for the decode steps.** Structural at every step, numeric only at step 1 under
R6-STEP-N's admission rule, characterization at steps 2..N with its measured reason. The step index
to transcript-graph mapping is unchanged: this arm's step `k` still compares against graph `k+1`.

**The suffix pass has no transcript counterpart, and this is a declared absence rather than an
omission.** The R2C-patched `llama-eval-callback` computes one prefill graph for the whole prompt
and then `N` decode graphs; it has no way to be told "prefill these `T_prefix` tokens, stop, then
prefill these `S` more", because that would require it to persist a KV cache across two invocations,
which is the capability *this repository* just built and llama.cpp's instrument has no operand for.
So:

- Oracle A′ **does not compare the suffix graph** against anything external.
- What replaces it is **not weaker in the dimension that matters**: the suffix pass's logits are
  compared byte-for-byte against `--model-forward` (C″), against the single-shot `--decode-step`
  (S), and — through `oracle_logits` — against `llama-debug --save-logits`, which is an **external,
  byte-exact** reference for the whole sequence. The suffix pass is therefore the only graph in this
  arm's history whose external acceptance is byte identity with no tolerance at all.
- What is genuinely lost is per-node attribution *inside* the suffix pass: when C″ fails, the
  document says the logits differ and not which node first did. The named diagnostic route is
  recorded in section 7 rather than built: `--model-forward` at `S` tokens with a transcript
  compares node by node, and the split `T_prefix = 0` degenerate case makes a suffix pass and a
  prefill the same graph.

### 3.7 The shipped acceptance rule, stated once

Sections 3.2 to 3.6, 4, and 5 refer to this rule; they do not restate it. `scripts/run-decode-step`
implements it and its comment quotes it.

> For every prompt and every split index `j`, all of the following, unconditionally:
>
> 1. **R6-KV-PERSIST section 3's rule, in full**, on the save run and the plain load run — which
>    includes R6-STEP-N section 3.5's rule in full. Unchanged, and it is what makes the container
>    this capability consumes a verified artifact rather than an assumption.
> 2. **Oracle S.** `normalize_suffix(DOC.sfx) == normalize_suffix(DOC.one)`, and
>    `DOC.sfx.suffix.sequence_length == DOC.one.selection.token_count`.
> 3. **Oracle C″.** `DOC.sfx.output.sha256` equals `--model-forward`'s `output.sha256` at
>    `TOKENS,SUFFIX` and the same width.
> 4. **Oracle B.** `plane.roundtrip_verdict == "IDENTICAL"` over a positive byte count whose first
>    term is `2 · n_layer · (T_prefix + S) · n_head_kv · head_dim · 4`.
> 5. **Gate G.** `oracle_logits.verdict == "IDENTICAL"` and `byte_identical` on the suffix run over
>    the whole prompt's blob (G1); G2 at every decode step; `decode.token_ids` equal element for
>    element to the single-shot run's.
> 6. **The suffix pass's accounting.** `suffix.completed == 1`, `suffix.token_count == S`,
>    `suffix.n_past_base == kv.columns_persisted == kv.token_count == selection.token_count`,
>    `suffix.columns_written == T_prefix + S`, `plane.columns_written == T_prefix + S + N`, and
>    `suffix.pack_bytes == 0` on the resident leg.
> 7. **Every refusal case yields exactly its named code**, and no refusal leaves a file behind or a
>    plane unfreed. The authoritative matrix is **section 5.6**, the shipped result; section 5.2 is
>    the prediction it supersedes, and section 11.1 finding 3 records where the two differ.
> 8. **Determinism.** Three consecutive suffix runs byte-identical after `normalize`.
>
> `timings.first_token_ns` and the invocation wall clocks of 1.4's three legs are **reported** and no
> acceptance decision is taken from any of them.

The rule is unconditional over **every** split index the operand grammar admits, `1 <= j < |L|`.
It shipped with one exception — `T_prefix >= 2`, refused rather than silently excepted — and that
exception is **gone**: MF-SINGLE-TOKEN-LOGITS (roadmap item 36) fixed the one-token embedding gather
it stood in for, and section 11.5 records the lift with its evidence. `ds-suffix-prefix-one` is now
rule 2's own `T_prefix = 1` witness.

### 3.8 The tolerance rule

| Comparison | Rule | Value | Derivation |
| --- | --- | --- | --- |
| Oracle S | **byte identity** of the normalized document | 0 | Two spellings of one computation. A tolerance would only admit a bug |
| Oracle C″ | **byte identity** of 608,256 logit bytes | 0 | 3.1's measured column-count invariance is what makes it available |
| Oracle B | **byte identity** | 0 | Unchanged from R6 |
| Gate G1 | **byte identity**, then integer equality of the argmax | 0 | Unchanged from R6 |
| Gate G2 | exact, conditional on the measured fingerprint injectivity | 0 | Unchanged from R6-STEP-N |
| Oracle A′, per element / per sum / step-1 admission | absolute 1 ten-thousandth / 1000 millionths or 10 ppm / 5000 ten-thousandths | unchanged | Inherited; **applies to no comparison this capability adds** |

**Every comparison this capability adds is byte identity or integer equality, and no new tolerance
is introduced.** That is the same sentence R6-KV-PERSIST's section 3 ends on, and it is true here
for the same reason: the suffix pass either reproduces a computation this arm can already perform
another way, or it does not.

## 4. Closure matrix

Every cell names an implementation and an exact regression, or is marked `N/A` or **deferred** with
a reason. `T_prefix` is the prefix length, `S` the suffix length, `N` the step count, `k` a step
index.

### 4.1 `src/decode_step.align` — the operand, the validation, and the pass

| Phase | Implementation | Regression |
| --- | --- | --- |
| Formation / validation | `run` bumps `count > 15`, extracts `suffix_text := if count >= 15 { args[14] } else { "-" }` with **no `valid_path` line** (it is a list, not a path — `RESIDENT`'s precedent); `execute` gains one `str` parameter, raises step 2c, and publishes `o.suffix_requested` before any path work; `stage_inputs` gains step 3c and widens step 6 | `ds-suffix-no-load`, `ds-suffix-and-save`, `ds-suffix-empty`, `ds-suffix-garbage`, `ds-suffix-trailing`, `ds-suffix-over-vocab`, `ds-suffix-over-cap`, `ds-suffix-narrow-width`, and the three precedence cases of 2.3 |
| Construction | one new `suffix_detail(value)` builder; one new `CODE_SUFFIX`; `decode_pass` gains a `tokens: i64` parameter; the suffix pass is **one call to it at `tokens = S`** before the loop, and the loop's calls pass `1` | `ds-suffix-1`, `ds-suffix-2`, `ds-suffix-3`; every existing engine row byte-unchanged but for schema and the `suffix` object (5.3) |
| Success | load → suffix pass → write-back → oracle B → `output`/`oracle_logits` → `N`-step loop → document, `status: ok`, exit 0 | `ds-suffix-3`; qualification asserts 3.7 |
| Failure | any seam code from inside the pass, detail prefixed `suffix[]` | `ds-force-compute-suffix` (a forced build keyed on a graph with `tokens > 1` **and** `n_past > 0`, so it fires in the suffix pass and in no prefill and no step) → `R5_COMPUTE` detail `suffix[]...` |
| Malformed input | validation steps 2c, 3c, 3′, 6 | the malformed-input row above |
| Early exit | a failed pass publishes `suffix.completed = 0`, `suffix.columns_written = T_prefix`, zero counts, no steps, a non-`IDENTICAL` round trip, the **container's** `output`, and still frees the plane | `ds-force-compute-suffix` asserts all six; `record()`'s universal `(returncode == 0) == (status == "ok")` on every case |
| Cleanup | the plane and every per-pass buffer are ordinary `buffer`s at `execute`/`schedule_decode` scope; ggml contexts, buffers, and gallocrs balanced after `1 + N` graph sets | `lifetime.*_created == *_freed` and `graph_balance_failures == 0` asserted per case; in resident mode the run-scope wrap's own counter pair is unmoved |
| Move-in/out, source nulling, replacement, return | **N/A — no ownership transfer is added.** The pass writes into the caller's existing `mut plane: buffer` through the existing `capture_plane`, and its scalars travel in `model_forward.Outcome` fields as `weights`' nine do. No value is moved out of a record and no source is nulled | stated, with reason |

### 4.2 The KV plane, extended before the loop

| Phase | Implementation | Regression |
| --- | --- | --- |
| Construction | `buffer(plane_bytes)` at the declared `KV_WIDTH`, zero-filled, once. **Unchanged** | `plane.bytes`/`stride` on every engine row |
| Success | `load_plane` writes `0 .. T_prefix-1`; the suffix pass writes `T_prefix .. T_prefix+S-1` from rows 12/10 at `t = S`; step `k` writes `T_prefix+S+k-1` | `plane.columns_written == T_prefix + S + N`; oracle B at the pass and at every step |
| Failure — write-back short | `slot_nbytes` on rows 12/10 must equal `S * column_bytes` | `R6_PLANE_WRITE` detail `suffix[]layer[<n>]tensor[k\|v]`. **Deferred as a case**, on R6-STEP-N section 7's terms exactly: the arm's own sizing makes it unreachable and no forced build produces it |
| Failure — round trip | `compare_past_k`/`compare_past_v` over `T_prefix + S` columns | **new** `ds-force-suffix-writeback-offset` shifts the pass's first written column by one and must report `R6_PLANE_MISMATCH suffix[]layer[0]tensor[k]col[<T_prefix>]` — the column index is `T_prefix`, which is what proves the *first suffix* column is compared and not only the loaded ones |
| Malformed input | `T_prefix + S + N > KV_WIDTH` refused before the load | `ds-suffix-narrow-width` |
| Early exit | a failed pass leaves columns `>= T_prefix` unpublished; nothing reads them | `ds-force-compute-suffix` asserts `columns_written == T_prefix` |
| Cleanup | freed at scope end on every path | as 4.1 |
| **Ordering / aliasing** | upload `0 .. T_prefix-1` → compute → write `T_prefix .. T_prefix+S-1` → verify `0 .. T_prefix+S-1`. Three ranges, two disjoint, one comparison covering all (2.4) | `ds-force-suffix-writeback-offset`; a write into an uploaded column changes a column oracle B compares in the same pass |

### 4.3 `src/layer_qwen2.align`

| Phase | Implementation | Regression |
| --- | --- | --- |
| Construction | one `tokens` parameter on `mf_decode_layer_node_table` and `mf_decode_row_attention`; five literal `1`s become `tokens` (2.5); `mf_decode_row_head` forwards it. **No new row, op, slot, selector, constant, or mask writer** | `ds-suffix-*` engine cases; every existing decode row byte-unchanged, because the loop passes `1` |
| Success | the table at `tokens = S`, the mask at `(S, T_prefix)` | oracle S and oracle C″; `ds-force-mask-offset` (R6's) retained and still fires |
| Failure | N/A — both are pure and total over their inputs | stated, with reason |
| Malformed input | N/A — `n_past` and `tokens` are computed by the arm and bounded by validation steps 3c and 6 | stated, with reason |
| Early exit / Cleanup | N/A — pure, allocates nothing | stated, with reason |
| **Deferred cell** | `mf_write_mask_offset` has no `row_offset + height <= width` guard (2.5). **Not added**: step 6's `T_prefix + S + N <= KV_WIDTH` strictly implies it, so no input reaches it, and an unreachable check with no forced build is the cell R6 and R6-STEP-N both decline to add | named, with reason |
| **Non-regression** | `MAX_PREFILL_TOKENS`, `MAX_DECODE_STEPS`, `MAX_ATTENTION_WIDTH`, `MF_DECODE_LAYER_NODE_COUNT`, the prefill row table, `WHEN_WIDE`, `mf_write_mask`, `layer_olmoe.align` — all **untouched** | `scripts/layer-forward-golden.jsonl`, `model-forward-golden.jsonl`, `gpu-forward-golden.jsonl`, `moe-layer-forward-golden.jsonl`, `moe-model-forward-golden.jsonl`, `ggml-spike-golden.jsonl` — every other golden in `scripts/` — **byte-unchanged** (5.3) |

### 4.4 `src/model_forward.align`

| Phase | Implementation | Regression |
| --- | --- | --- |
| Construction | eleven new `Outcome` fields for the `suffix` object; one new position producer taking a base; **`build_embed_members` reused unchanged** at `pieces = S` | `ds-suffix-3`'s golden is the shape |
| **The seam this module owns** | The suffix pass takes the **prefill's** embedding-member builder and the **decode's** layer node table. That pairing is new and is the one place a wrong choice is silent: using `decode_embed_members` would gather one row for `S` tokens and produce a shape error, and using the prefill's layer table would compute the right shapes at the wrong positions and produce a plausible wrong number | `ds-suffix-2` and `ds-suffix-3` differ from `ds-suffix-1` exactly in `S`, so a builder that ignores `S` fails them and passes `ds-suffix-1` |
| Why `Outcome` fields and not a column set | The `suffix` object is **eleven scalars, not an array**: there is exactly one suffix pass. R6-STEP-N's `StepColumns` exists because `steps[]` is `N` rows. Adding eleven scalars grows `Outcome` by 88 bytes against the 1,384 the compiler already reports, which is the same trade `weights`' nine scalars took | the compiler's own size warning, unchanged in count |
| Success | the prefill path is byte-unchanged; `graph_input_values`'s id/position split is R6's, unchanged | `model-forward-golden.jsonl` byte-unchanged |
| Failure | a `suffix` field published without `suffix.completed` | asserted in `render`: `completed == 1` implies `columns_written == n_past_base + token_count` or the document is not written |
| Malformed input / Early exit / Cleanup | unchanged | existing `mf-*` cases |

### 4.5 `src/kv_plane.align` and `scripts/kv_plane_reader.py` — byte-unchanged

| Phase | Implementation | Regression |
| --- | --- | --- |
| **All phases** | **N/A — byte-unchanged, and 2.1 records that this is the surface decision's purpose rather than a happy accident.** `TOKENS` still means the container's tokens, so L12 and L13 hold character for character; no region, offset, digest, alignment rule, or reserved value moves; `format_version` stays 1 and `DOCUMENT_SCHEMA_VERSION` stays 3 (2.9) | The **51** `KV_REFUSALS` rows carried forward from the design pin — **52** at the implementation head, the one addition being this capability's own `ds-suffix-tokens-mismatch` — and the independent reader's acceptance of every saved container, all passing **without a diff to check**, which is the evidence that this row is honest |

### 4.6 `src/ggml_ffi.align`, both shims, `src/ggml_spike.align` — byte-unchanged

| Phase | Implementation | Regression |
| --- | --- | --- |
| **All phases** | **N/A — byte-unchanged.** No new op, no new symbol, no new wrapper. `op_concat` ships with R6 and accepts an operand of any width on its non-concat axes; `slot_get`/`slot_set`/`slot_mark_output` carry every crossing the pass needs; the two rows the write-back marks are rows the graph already builds. The dispatch arm forwards `args` and does not enumerate arity | The shared-region byte-identity check (`run-layer-forward-smoke:57-64`), the `unsafe`/`extern` confinement scans (`:75-86`), the no-`malloc` scan (`:65-68`), and `ds-arm-unknown-flag` |

**The only exception is the test double.** `scripts/ggml_shim_stub.c` gains one forced-build arm for
`ds-force-compute-suffix` (4.1) and one for `ds-force-suffix-writeback-offset` (4.2), which are
inputs to the **stub** and never to an ordinary build — the same shape and the same justification
`R6-RESIDENT-WEIGHTS` section 5.9 deviation 1 records.

### 4.7 `scripts/layer_forward_fixture.py` — the suffix reference

| Phase | Implementation | Regression |
| --- | --- | --- |
| Construction | `model_layer` gains `first_position` and an optional past-plane operand, so it can build the `{width, S}` offset mask and rope at `T_prefix + r`; `write_decode_corpus` emits **two new containers** (at `T_prefix = 2` for tokens `[3,17]` and at `T_prefix = 1` for `[3]`) and **one new prefill reference** at the five-token list of 5.1 | the emitted transcripts and containers, consumed by `ds-suffix-1/2/3` |
| **Why the generator must be changed at all** | Verified by reading: `model_layer`'s positions are hardwired `list(range(t))` (`:1006`), its mask is strictly lower-triangular over `[0, t)` (`:1082`), and it **never reads** `planes` — it only appends to it (`:1053`). `model_decode_layer` reads the plane but is hardwired to `t = 1` (`:1340-1350`). So no existing function computes `S > 1` columns at `n_past > 0`, and the reference for this capability is genuinely new rather than a re-parameterisation | stated, with the lines |
| **Why the hosted splits are `(2,1)`, `(1,2)`, and `(2,3)`** | The first two split the **existing** `MODEL_TOKENS = [3,17,5]`, so their single-shot comparand is the **existing** `ds-engine-ok` document and costs no new reference at all — three ways of reaching one state must produce one document. The third has `T_prefix > 1` **and** `S > 1`, which neither of the first two has, and it is the only one that needs a new five-token reference. A fourth split adds no closure cell | `ds-suffix-1`, `ds-suffix-2`, `ds-suffix-3` |
| **The suffix ids must not be degenerate** | `MODEL_DECODE_RESEEDED_ROWS` already re-seeds row 24 so the decode chain is `24 → 9 → 27` rather than a fixed point (R6-STEP-N section 4.7). The five-token list of 5.1 is chosen so that its argmax differs from the three-token list's, or `ds-suffix-3` would pass for an arm that ignored the last two suffix tokens. The generator asserts it as it emits | the generator's own `assert`, and the smoke's re-check on the file it reads |
| Failure | N/A — the generator is total over its own fixed inputs and reads no external file | stated, with reason |
| Malformed input | mutated containers | the existing `KV_MUTATIONS` corpus, unchanged; a suffix run reaches it through the same L1–L14 |
| Early exit / Cleanup | argv guard unchanged; writes into the harness-owned `OUTDIR` | stated, with reason |

### 4.8 `scripts/run-layer-forward-smoke` and `scripts/run-decode-step`

| Phase | Implementation | Regression |
| --- | --- | --- |
| Construction | the fifth block's `ds()` helper gains a `suffix=None` keyword appending the fifteenth operand; the five case tables gain 4.1's cases; `record()`'s identity assertion moves to `schema_version != 5`; `normalize` gains `suffix.compute_ns`; a new `normalize_suffix` (3.2) beside `normalize_persist` and `normalize_resident` | the block's own `SystemExit(1)` |
| Success | `scripts/decode-step-golden.jsonl` matches case for case at schema 5 | golden compare |
| Failure | any case's document differs, or a code differs from the table's expectation | `describe_difference` |
| Malformed input | the `NO_DOCUMENT` table, with `ds-arity-15` → `ds-arity-16` | zero golden bytes, per the ratchet comment at `:3697-3701` |
| Early exit | the smoke never skips; the qualification prints one `N/A` line and exits 0 | `run-decode-step`'s `na()` |
| Cleanup | the qualification removes every container, transcript, and document on every exit path including a signal, and restores the unforced shim | `trap cleanup EXIT HUP INT TERM`, unchanged; the free-space reserve is re-checked in 5.4 |
| **Shared process state** | **N/A.** Each `ggml-spike` invocation is an independent process with its own backend, contexts, plane, and arena. The one process-global input is the shim build, which the trap restores | stated, with reason |
| **Concurrent independent processes** | **Unsupported and not attempted.** Parallelising per-prompt work needs `spawn` over non-`Copy` captures, which is **Align Request 41** (`PROPOSED`); no workaround is built and no hypothetical surface is consumed | stated, with reason (section 8) |

## 5. Verification plan

| Scope | Command |
| --- | --- |
| Owner, during development | `gmake layer-forward-smoke` — the owner for R5A–R5E and every R6 capability, already in `HOSTED_CHECK_TARGETS` |
| Focused qualification | `gmake decode-step-qualification` → `scripts/run-decode-step`, opt-in, capable-only, **outside every aggregate** — unchanged |
| Publication | `python3 scripts/pre-pr --owner-test layer-forward-smoke -- gmake layer-forward-smoke` |
| Formatting | `gmake fmt` before committing Align source; `gmake format-check` and `git diff --check` clean |

**`make ci` is not selected and aggregate membership is unchanged.** No new target and no new
`.PHONY` word, so `scripts/check-gate-topology`'s byte-literal `EXPECTED` does not move; the owner
stays `layer-forward-smoke`, already a member. This is not a `.align-revision` change, not an
aggregate membership or topology change, and not a change to integration behaviour.
**`baseline-check` is `N/A`** on the same condition R6-STEP-N recorded — the `Makefile` is
byte-unchanged and `scripts/build-ggml-shim`'s two new arms are inputs to the **stub** only — and
must be re-checked at the publication head.

### 5.1 The hosted owner — what the fifth block gains

Against a two-layer synthetic model, no ggml, no llama.cpp, no GGUF, and no network. `n_layer` 2,
`n_head_kv` 1, `head_dim` 4, `n_vocab` 32, `KV_WIDTH` 8, and the block's default `STEPS` **3**,
except `ds-suffix-3` and `ds-suffix-resident`, which run at 2 because their sequence is longer.
(This paragraph was drafted as `STEPS` 2; the shipped per-case `N` is section 5.5's column.)

| Case | Prefix | Suffix | Single-shot comparand | What it is for |
| --- | --- | --- | --- | --- |
| `ds-suffix-1` | `3,17` | `5` | **`ds-engine-ok`** (`3,17,5`) | `S = 1` — the degenerate suffix, and the only one whose graph shape matches a decode step's. It must *not* be a decode step: its token is an operand, not an argmax |
| `ds-suffix-2` | `3` | `17,5` | **`ds-engine-ok`** (`3,17,5`) | `S = 2` at `T_prefix = 1` — the first pass whose second column attends to its own first |
| `ds-suffix-3` | `3,17` | `5,9,27` | `ds-suffix-single-shot` (`3,17,5,9,27`) | `T_prefix > 1` **and** `S > 1`, the only case with both; `T_prefix + S + N = 7 <= 8` |

The first two share a comparand that **already exists as a golden row**, so oracle S is asserted
three ways into two documents, and the claim "three routes to one state produce one document" is
checked rather than stated. `ds-suffix-single-shot` is the one new success document the widest case
needs. *(Shipped, this table moved in three ways — `ds-suffix-1`'s comparand, `ds-suffix-2`'s
`T_prefix`, and a fourth `RESIDENT` case — so the "first two" sentence is true of the **first only**.
Section 5.5 is the shipped matrix and 11.3 deviation 4 enumerates the three changes.)*

Plus the refusals of 5.2, the two forced builds of 4.1/4.2, and — carried forward unchanged and
re-run — `ds-force-plane-stage-offset`, `ds-force-mask-offset`, `ds-force-decode-position`, and the
**51** `KV_REFUSALS` rows this capability inherits.

**Budget.** The block gains roughly a dozen documented cases and two shim rebuilds. R6-KV-PERSIST
measured the owner at ~39 s with its own additions and R6-RESIDENT-WEIGHTS added nine more cases; a
dozen cases and two rebuilds is **an estimated +6 to +9 s**, keeping the owner a seconds-scale
hosted check, which is what admitted it to `HOSTED_CHECK_TARGETS`. If the measured cost exceeds that
materially, `ds-suffix-2` is the case to drop — it is the only one whose closure cells are a strict
subset of another's.

### 5.2 The refusal matrix

| Case | `SUFFIX` | Other | Code | Detail |
| --- | --- | --- | --- | --- |
| `ds-suffix-no-load` | `5` | `KV_LOAD` = `-` | `R6_KV_ARGS` | `suffix[no_load]` |
| `ds-suffix-and-save` | `5` | `KV_SAVE` set, `KV_LOAD` = `-` | `R6_KV_ARGS` | `suffix[no_load]` |
| `ds-suffix-no-load-bad-steps` | `5` | no load **and** `STEPS` = `0` | `R6_KV_ARGS` | `suffix[no_load]` — 2c precedes 3b |
| `ds-suffix-empty` | `""` | loaded | `R6_SUFFIX` | `suffix[]` |
| `ds-suffix-garbage` | `x` | loaded | `R6_SUFFIX` | `suffix[x]` |
| `ds-suffix-trailing` | `5,` | loaded | `R6_SUFFIX` | `suffix[5,]` |
| `ds-suffix-over-vocab` | `32` | loaded, `n_vocab` 32 | `R6_SUFFIX` | `token[32]` |
| `ds-suffix-over-cap` | 31 ids | loaded at `T_prefix = 2` | `R6_SUFFIX` | `sequence[33]` |
| `ds-suffix-and-bad-tokens` | `5` | `TOKENS` = `33` ids | `R6_TOKENS` | `count[33]` — 3 precedes 3c |
| `ds-suffix-over-cap-and-narrow` | over-cap **and** width too narrow | loaded | `R6_SUFFIX` | `sequence[<n>]` — 3c precedes 6 |
| `ds-suffix-narrow-width` | `5,9,27` | `T_prefix = 2`, `N = 2`, width `6` | `R6_KV_WIDTH` | `kv_width[6]` |
| `ds-suffix-tokens-mismatch` | `5` | container written for `3,17,5` | `R6_KV_TOKENS` | `count[3]` — **unchanged L12**, proving 4.5 |
| `ds-arity-16` | — | sixteen operands | *(none)* | `NO_DOCUMENT`, no golden bytes |

`ds-suffix-tokens-mismatch` is the case that makes 2.1's central claim testable: a container for the
*whole* list is refused by an **unmodified** check when the run supplies it as a prefix.

### 5.3 Predicted golden movement

Named before the run, so an unpredicted movement is a finding rather than noise.

| File | Predicted |
| --- | --- |
| `scripts/decode-step-golden.jsonl` | **All 116 rows change** — `schema_version` 4 → 5 and a `suffix` object of eleven fields, absent-valued on every existing row. **No existing row's other fields change**, because the loop passes `tokens = 1` and every constant is untouched. Roughly **16 rows added**; 116 → ~132 |
| `scripts/layer-forward-golden.jsonl` | **byte-unchanged** |
| `scripts/model-forward-golden.jsonl` | **byte-unchanged** |
| `scripts/gpu-forward-golden.jsonl` | **byte-unchanged** |
| `scripts/moe-layer-forward-golden.jsonl` | **byte-unchanged** |
| `scripts/moe-model-forward-golden.jsonl` | **byte-unchanged** |
| `scripts/ggml-spike-golden.jsonl` | **byte-unchanged** |

The rewrite of the arm's own golden is permitted on R6-STEP-N section 2.1's recorded exemption: it
is this capability family's own file, created by R6 and consumed by nothing else. **Every other
golden in `scripts/` must not move** — the six above, which is every one there is — and that is the
check that `layer_qwen2`'s changed literals really are gated on the new parameter.

### 5.4 The real-model qualification leg

`scripts/run-decode-step` gains one leg per prompt per split index, after the existing persistence
leg. `L` is the prompt's token id list, **read from the instrument's own stderr exactly as the
runner already reads `TOKENS`** — `number of input tokens = 6` then `750 912 2877 11 293 1648`.

```text
for j in split_points(L):
  1. save     --decode-step PACK GEOM L[:j] DOC.save.json REF -          W -      1  KV.akvp -       -  -
  2. suffix   --decode-step PACK GEOM L[:j] DOC.sfx.json  REF TRANSCRIPT W LOGITS N -       KV.akvp R  L[j:]
  3. single   --decode-step PACK GEOM L     DOC.one.json  REF TRANSCRIPT W LOGITS N -       -       R  -
  4. modelfwd --model-forward PACK GEOM L   DOC.mf.json   REF -          W                                  (oracle C'')
  5. compare  normalize_suffix(DOC.sfx) == normalize_suffix(DOC.one); sequence_length == token_count
  6. ttft     three runs each of {single, suffix, plain-load} at STEPS=1, no transcript, no logits
```

**Split points.** Two per prompt, at `j = 2` and `j = ⌈|L|/2⌉`, deduplicated — so `T <= 6` prompts
give one or two distinct splits each. `j = 2` is the smallest prefix that is not degenerate; the
midpoint is the only other point that changes both `T_prefix > 1` and `S > 1` together. **A split at
`j = |L| - 1` is deliberately not taken**: it is `S = 1`, which the hosted `ds-suffix-1` already
covers, and it would spend a real-model run on the cheapest case.

**Three things this leg gets for free**, and they are the reason its cost is bounded:

- **The `LOGITS` blob is the existing one.** `TOKENS ++ SUFFIX == L`, so `llama-debug --save-logits`
  on the prompt text is the same blob the existing qualification already produced. **No new
  `llama-debug` run.**
- **The `TRANSCRIPT` is the existing one.** The decode loop starts at `n_past = |L|` on both the
  suffix and the single-shot leg, so llama.cpp's `N + 1` graphs map to the steps identically and
  oracle A′ and gate G2 are unchanged. **No new instrument run.**
- **No detokenizer is needed** (3.5), because the split is on ids the instrument printed.

**Cost.** Per split: one `N = 1` save (≈ 5 s), one `N = 16` suffix run, one `N = 16` single-shot
run, and one `--model-forward`. R6-STEP-N measured `N = 16` at 15–31 s streamed and
R6-RESIDENT-WEIGHTS at ≈ 10 s resident, so **the suffix leg runs resident** and a split costs ≈ 5 +
10 + 10 + 5 = **30 s**. At four prompts × up to two splits that is **≈ 240 s** on top of
R6-KV-PERSIST's estimated ≈ 910 s, for **≈ 1150 s against the 1800 s cap**. *Mitigations, in order:*
the existing `ALIGN_LLM_DECODE_STEPS=8` fallback halves the two `N = 16` terms; failing that, one
split per prompt, which costs one prompt-split's coverage and **no closure cell**; failing that, the
suffix leg on two prompts. All three are recorded so the choice is not made under time pressure.

**Disk.** Up to eight extra containers of 29,970,432 B plus their documents — ≈ 240 MB above what
the run already uses. R6-KV-PERSIST raised the free-space reserve to pack + 3 GiB; **it is
unchanged**, because 240 MB fits inside that headroom and raising a reserve that already covers the
need would be a change with no cause.

### 5.5 Hosted result — the owner, at the implementation head

`gmake layer-forward-smoke` PASS. Against the two-layer synthetic model (`n_layer` 2, `n_head_kv` 1,
`head_dim` 4, `n_embd` 8, `n_vocab` 32, `KV_WIDTH` 8), with the container written by the arm's own
save direction for the prefix `3,17`:

**Section 5.1's budget, evaluated rather than left standing.** The whole runner — all six blocks,
compiler included — is **65.9 s real / 39.0 s user** at the repaired head on the reference host.
R6-KV-PERSIST measured it at ~39 s with its own additions and R6-RESIDENT-WEIGHTS added nine cases;
5.1 estimated this capability at **+6 to +9 s** for a dozen cases and two shim rebuilds. The
measurement is a whole-runner wall clock on a busier host and not a per-block delta, so it neither
confirms nor refutes the estimate to the second — what it settles is the decision the estimate
existed for: the owner is still a **seconds-scale** hosted check, well inside what admitted it to
`HOSTED_CHECK_TARGETS`, so the recorded mitigation (drop `ds-suffix-2`) is **not taken** and every
case ships.

| Case | `T_prefix` | `S` | `N` | Single-shot comparand | Oracle S | Oracle C″ | Oracle B |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `ds-suffix-1` | 2 | 1 | 3 | `ds-kv-args-dash-dash` (**an existing golden row**) | IDENTICAL | IDENTICAL | IDENTICAL, 1,152 B = 960 + 192 |
| `ds-suffix-2` | 2 | 2 | 3 | `ds-suffix-single-shot-4` (**a `BOUNDARY_CASES` run, no golden row** — 11.3 deviation 7) | IDENTICAL | IDENTICAL | IDENTICAL, 1,408 B = 1,152 + 256 |
| `ds-suffix-3` | 2 | 3 | 2 | `ds-suffix-single-shot` | IDENTICAL | IDENTICAL | IDENTICAL, 1,152 B = 832 + 320 |
| `ds-suffix-resident` | 2 | 3 | 2 | `ds-suffix-3` (oracle R) | IDENTICAL | IDENTICAL | IDENTICAL, 1,152 B |

Every extra term is exactly `2 · n_layer · (T_prefix + S) · n_head_kv · head_dim · 4` — 192, 256,
and 320 — which is the suffix pass's own verification over all `T_prefix + S` columns before the
first decode step, asserted as that arithmetic and not as an observed number.

`ds-suffix-1`'s sequence is `3,17,5`, so its decoded ids are the fixture's own reference loop's
`[24, 9, 27]` — **three routes to one state produce one document**, and the third route is compared
against a golden row this capability did not create.

`suffix.pack_bytes` is **5,952** on `ds-suffix-1`, **5,984** on `ds-suffix-2` and **6,016** on
`ds-suffix-3` — the streamed pass's own sweep, growing with `S` — and **exactly 0** on
`ds-suffix-resident`, which is R6-RESIDENT-WEIGHTS' primary metric extended to the one pass this
capability adds.

### 5.6 Hosted result — the refusal matrix

Every row refused with exactly its code and exactly its detail, and every one published
`suffix.requested = 1`, `suffix.completed = 0`, no step, and no `IDENTICAL`. This table is
`run-layer-forward-smoke`'s `SUFFIX_REFUSAL_DETAILS` tuple: the runner asserts all twelve details
below (thirteen as shipped, until 11.5 removed `ds-suffix-prefix-one`'s) and the summary line counts *that tuple* rather than `STUB_CASES` membership, so a row added
here without an assertion cannot inflate the printed claim (`ds-suffix-tokens-mismatch` rides in
`KV_REFUSALS` and is why membership was the wrong witness):

| Case | Code | Detail |
| --- | --- | --- |
| `ds-suffix-no-load` / `-and-save` / `-no-load-bad-steps` | `R6_KV_ARGS` | `suffix[no_load]` |
| `ds-suffix-empty` | `R6_SUFFIX` | `suffix[]` |
| `ds-suffix-garbage` | `R6_SUFFIX` | `suffix[x]` |
| `ds-suffix-trailing` | `R6_SUFFIX` | `suffix[5,]` |
| `ds-suffix-over-vocab` | `R6_SUFFIX` | `token[0]` — see section 11.1, finding 3 |
| `ds-suffix-over-cap` / `-over-cap-and-narrow` | `R6_SUFFIX` | `sequence[33]` |
| `ds-suffix-and-bad-tokens` | `R6_TOKENS` | `token[32]`, not section 5.2's predicted `count[33]` — section 11.1 finding 3. The refusal is raised by step **3**'s own lexical parse, before the geometry is read, so it does establish the `3 ≺ 3c` precedence section 2.3 claims: the document it produces carries `suffix.n_past_base = -1` |
| `ds-suffix-narrow-width` | `R6_KV_WIDTH` | `kv_width[6]` |
| `ds-suffix-tokens-mismatch` | `R6_KV_TOKENS` | `count[3]` — **L12 unmodified**, which is 2.1's claim |
| `ds-arity-16` | *(none)* | `NO_DOCUMENT`, no golden bytes |

The two forced builds both fail **inside the pass** and publish section 2.8's contract in full:

| Case | Code | Detail | `suffix.columns_written` | `output` |
| --- | --- | --- | --- | --- |
| `ds-force-compute-suffix` | `R5_COMPUTE` | `suffix[]layer[0]status[2]` | 2 (`= T_prefix`) | the **container's** vector |
| `ds-force-suffix-writeback-offset` | `R6_PLANE_MISMATCH` | `suffix[]layer[0]tensor[k]col[2]` | 2 | the **container's** vector |

`col[2]` is `T_prefix`, which is what proves the **first suffix** column is compared and not only
the loaded ones. Both runs freed the plane and balanced their teardown.

### 5.7 Golden movement, against the prediction

| File | Predicted | Measured |
| --- | --- | --- |
| `scripts/decode-step-golden.jsonl` | all 116 rows change in `schema_version` and the `suffix` object only; ~16 added; 116 → ~132 | **exactly that**: 116 rows change in `schema_version` 4 → 5 and the added `suffix` object and **in no other field**; **21** rows added; 116 → **137** |
| every other golden in `scripts/`: `layer-forward-golden.jsonl`, `model-forward-golden.jsonl`, `gpu-forward-golden.jsonl`, `moe-layer-forward-golden.jsonl`, `moe-model-forward-golden.jsonl`, `ggml-spike-golden.jsonl` | byte-unchanged | **byte-unchanged** |

The six unchanged goldens are the check that `layer_qwen2`'s changed literals really are gated on
the new parameter. The 21 added rows are **twelve** refusals, two single-shot/save documents, four
suffix successes, the tokens-mismatch refusal, and the two forced builds. Twenty of them shipped
at the implementation head; `ds-suffix-prefix-one` is the review repair's (11.1 correction 8) and
has since **left this matrix** — MF-SINGLE-TOKEN-LOGITS lifted the bound and the case is a passing
oracle-S row (11.5), so the matrix is twelve refusals and the corpus gained two rows beside it.

**The twenty-second row did not survive hosted CI, and deviation 7 records why.** `ds-suffix-2`'s
four-token single-shot comparand is host-dependent in the last bit, so it moves into
`BOUNDARY_CASES` — run, recorded, and asserted by oracle S within one host, but not pinned in a file
compared across two. The runner reports **139 documented cases, 137 with a golden row**, and both
prints say which count is which.

### 5.8 Mutation evidence

**Eight mutants at the repaired head, all killed by `gmake layer-forward-smoke`.** Five were
injected at the implementation head; the review injected three more against oracle S's exclusion
list, **one of which survived** and is the reason correction 11 exists. Each mutant is reverted from
a file-level backup and each is rebuilt and re-run.

| # | Mutant | Result |
| --- | --- | --- |
| 1 | Suffix positions off by one (`T_prefix + i + 1`) | **died** — oracle S and oracle C″ on every split |
| 2 | Mask `row_offset` wrong for `S > 1` (`(S, 0)` instead of `(S, T_prefix)`) | **died** — oracle S and oracle C″ on every split |
| 3 | Write-back column base wrong at `S > 1` only (`T_prefix + 1`) | **died** — `R6_PLANE_MISMATCH suffix[]layer[0]tensor[k]col[2]` on `ds-suffix-2` |
| 4 | Verify range excludes the suffix columns (`n_past + 1`, R6-STEP-N's exact old bound) | **died** — `R6_PLANE_MISMATCH suffix[]layer[0]tensor[k]col[-1]` on `ds-suffix-2` |
| 5 | `mf_decode_row_tail` row 26 back to a hardwired `1` (11.1 correction 4's sixth literal) | **died** — `R5_SHAPE suffix[]node[26]` on `ds-suffix-2`, which is the refusal that correction predicted |
| 6 | Oracle S's exclusion list widened by the **blocks** `decode`, `steps`, `output` | **died** — the witness assertion, which is the guard risk 2 asked for |
| 7 | Oracle S's exclusion list widened by the **field** `("decode", "token_ids")` | **died at the repaired head; SURVIVED at `6cef75b`** — the guard checked that the `decode` block was present, not that its fields were, and a field exclusion is the shape all five real additions took |
| 8 | Oracle S's exclusion list widened by the fields `("decode", "n_past_first")` and `("decode", "n_past_last")` | **died at the repaired head** — same class as 7 |

Mutants 3 and 4 are the ones worth reading among the arithmetic ones: both were written to be
**suffix-only**, so each is correct for every decode step and wrong only at `S > 1`, and each still
died naming the exact case and the exact column. Mutant 7 is the one worth reading overall: it is
the review's, it survived the shipped guard, and it is the exact failure mode risk 2 was written
about — an exclusion list growing by one field at a time until the oracle means nothing.

### 5.9 Real-model result — `gmake decode-step-qualification`

Reference host: Apple M1, 16 GiB, macOS. Dense Qwen2.5-Coder-7B-Instruct Q4_K_M,
`KV_WIDTH` 256, `N = 16`, `llama-debug` Homebrew build 10566 (`bb4caa754`), the R2C-patched
`llama-eval-callback` from the `r2c-v2` cache. **Exit 0.** The leg was run twice: once before the TTFT trio was corrected (section 11.3 deviation 5)
and once at the final head, and the acceptance verdicts below are identical in both. Every
pre-existing leg — gate G, oracle
A′ under its admission rule, oracle B, oracle C′, oracle Q, the independent reader, the writer's
determinism, and oracle R — passes unchanged beside the new one.

**The review repair did not re-run this leg, and the reason is that no repaired line can reach it.**
Stated so the omission is a judgement rather than a gap: the `2 <= j` guard differs from `1 <= j`
only when `⌈|L|/2⌉ == 1`, which needs `|L| <= 2`, and the four prompts tokenize to 6, 3, 3 and 3 ids
— so the five splits below are the same five; the `T_prefix >= 2` refusal cannot fire when every
split has `j >= 2`, and it is inside `if o.suffix_requested`, so the save leg is untouched; the
stub's latch reset is inside `#if defined(ALIGN_GGML_FORCE_COMPUTE_SUFFIX) || ...`, which the
qualification's real-ggml build never defines and therefore never compiles; the witness guard is in
`scripts/run-layer-forward-smoke` and this leg does not run it; and the runner's changed line is
**printed text** beside the TTFT ranges, not a measured value or a verdict. Everything else the
repair touched is a comment or a document. The verdicts and numbers below are the implementation
head's and stand at the repaired head.

Split points are `j = 2` and the midpoint, deduplicated, over the four prompts' own tokenizations:

| Split | Prompt | `T_prefix` | `S` | Oracle S | Oracle C″ | Gate G1 | Oracle B (of which the pass) | `decode.token_ids[0..3]` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| case1 split 2 | `def add(a, b):` → `750,912,2877,11,293,1648` | 2 | 4 | **IDENTICAL** | **IDENTICAL** | **IDENTICAL** | 27,295,744 B (+688,128) | `671, 26312, 264, 729` |
| case1 split 3 | the same prompt at its midpoint | 3 | 3 | **IDENTICAL** | **IDENTICAL** | **IDENTICAL** | 27,295,744 B (+688,128) | `671, 26312, 264, 729` |
| case2 split 2 | `class Foo:` → `1040,33428,25` | 2 | 1 | **IDENTICAL** | **IDENTICAL** | **IDENTICAL** | 21,446,656 B (+344,064) | `715, 262, 707, 1304` |
| case3 split 2 | `# TODO:` → `2,5343,25` | 2 | 1 | **IDENTICAL** | **IDENTICAL** | **IDENTICAL** | 21,446,656 B (+344,064) | `2691, 1159, 12239, 198` |
| case4 split 2 | `int main(` → three ids | 2 | 1 | **IDENTICAL** | **IDENTICAL** | **IDENTICAL** | 21,446,656 B (+344,064) | `526, 11844, 11, 1161` |

`+688,128` is `2 · 28 · 6 · 4 · 128 · 4` and `+344,064` is the same at three columns: the suffix
pass's own verification over all `T_prefix + S` columns, asserted as that arithmetic. Both cases
where `T_prefix + S = 6` produce the **same** four ids from two different splits, which is oracle S's
claim seen from the outside: where the split falls does not change the run.

**Coverage, stated rather than implied.** Only prompt 1 tokenizes to more than three ids, so only its
two splits have `S > 1`; the other three prompts' two split points collapse to `j = 2` with `S = 1`.
`S >= 2` at `T_prefix > 1` is therefore exercised twice on the real model and three times hosted
(`ds-suffix-2` at `S = 2`, `ds-suffix-3` and `ds-suffix-resident` at `S = 3`). A corpus of longer
prompts would exercise it more, and that is the prefix-sharing corpus section 7 defers rather than
something this leg could have had for free.

### 5.10 The TTFT proxy — a labelled diagnostic, and what it is not

Section 1.4's three legs at `STEPS = 1`, no transcript and no logits blob, three repeats each, all
three **streamed** so the trio differs in what it measures and in nothing else:

| Split | (a) single-shot `first_token_ns` | (b) load + suffix | (c) plain load |
| --- | --- | --- | --- |
| case1 split 2 (`T_prefix` 2, `S` 4) | 4.675–5.091 s | 1.799–1.843 s | 0.824–0.899 s |
| case1 split 3 (`T_prefix` 3, `S` 3) | 4.535–5.007 s | 1.684–1.686 s | 0.824–0.899 s |
| case2 split 2 (`T_prefix` 2, `S` 1) | 5.042–5.282 s | 1.858–1.910 s | 0.974–1.021 s |
| case3 split 2 (`T_prefix` 2, `S` 1) | 4.633–4.962 s | 1.846–1.897 s | 1.034–1.332 s |
| case4 split 2 (`T_prefix` 2, `S` 1) | 5.092–5.446 s | 1.850–1.925 s | 0.929–1.079 s |

Three runs each, reported as a range (`min..max`), on one host, with **no median and no spread
computed** — the runner prints the two endpoints and nothing derived from them. The invocation wall
clocks track them within about 30 ms, which is what the outer bound is for: it includes process
start, `dyld`, and the pack open on every leg.

**Measurement conditions, beside the numbers rather than in another file.** Reference host as in
5.9. **The host was under memory pressure during both qualification runs** — another agent's OLMoE
qualification had just finished — so every absolute number in this table is that host on that day.
Nothing this capability accepts on depends on it: every acceptance verdict in 5.5 to 5.9 is byte
identity or integer equality and is unaffected by load. This table is the one place in the document
where a *timing* is reported, which is exactly why the condition is recorded here.

The runner prints each range on its own line and derives **no rate, no speedup, and no per-token
figure** from any of them. The sentence that travels with them, and which the runner prints beside
them: **neither leg skips a weight sweep**, because a prefill of any width is one sweep; what (b)
removes is `T_prefix` columns of prefill compute **plus the pack read and graph construction the
prefill pass performs for the whole prompt**, and it pays a container read instead — so a reader who
sees (b) beat (a) is seeing that exchange on a prompt of a few tokens, not a cache. Leg (c) is
**not** a third point on the same line: it answers a shorter question, because it decodes from the
prompt the container was saved for rather than from a longer one.

*(Until the review repair this paragraph and the runner's printed string said the difference was
`T_prefix` columns of prefill compute "**and nothing else**", which the next paragraph — written
later, from the measurement — contradicts: two to three columns at ~0.15 s account for at most
~0.45 s of a ~3 s gap. Section 11.1 correction 9. The "not a cache" conclusion is unchanged; only
the mechanism sentence was wrong, and it was the one sentence the runner printed as product output.)*

**Why (b) beats (a) by about 3 s and why that is not a cache.** Both legs prefill: (a) computes
`T_prefix + S` columns, (b) computes `S` and reads `T_prefix` from a file. Both sweep the weight set
once, because a prefill of any width is one sweep. What (b) removes is the pack read and graph
construction the prefill pass performs for the whole prompt, and it pays a 29,970,432-byte container
read instead. It is a real difference and it is not the difference a prefix cache would make on a
long shared prefix, because these prompts are six tokens long: at `T_prefix = 2` versus `T_prefix = 3`
the (b) legs differ by about 0.15 s, which is the whole per-column term at this scale — so the
per-column term accounts for a small fraction of the gap and the exchange above accounts for the
rest.

**The R6 roadmap gate stays unmet**, and the runner says so in its own summary. There is no prefix
key, no store, no corpus, and no prefix-sharing consumer; this ships the execution half of
mechanism 2 and none of its lookup half.

## 6. Risks

1. **Oracle C″ fails because ggml's `MUL_MAT` selection is column-count-sensitive after all.** The
   design's load-bearing assumption. *Mitigation:* 3.1 grounds it in two prior documents' measured
   byte identity over 1 versus 7, 14, and 22 columns on four prompts, and names the escalation
   (`--model-forward` at `S` versus at `T_prefix + S` on a zeroed plane) so the diagnosis does not
   start from llama.cpp. *Residual:* the `S >= 2` **and** `n_past > 0` combination is genuinely new
   and the evidence is an invariance rather than a measurement of that exact pair. **This is the
   risk the first implementation checkpoint should discharge**, by running `ds-suffix-3` before any
   refusal case is written.
2. **The exclusion list of oracle S grows during implementation until the oracle is vacuous.** A
   named prior failure class: R6-KV-PERSIST's oracle Q was designed with eight exclusions and
   shipped with sixteen. *Mitigation:* 3.2 fixes the list **in this document**, states what remains
   inside it, and compensates the one semantic exclusion (`selection.token_count`) with an explicit
   equality rather than dropping it. Any addition is a finding recorded in section 10, not an edit.
3. **A vacuous suffix assertion.** `suffix.completed` could be published `1` by a pass that computed
   nothing. *Mitigation:* `render` refuses to write a document in which `completed == 1` and
   `columns_written != n_past_base + token_count` (4.4); oracle B's byte count has a term that is
   zero unless `S` columns were actually compared; and `ds-force-compute-suffix` is the case in
   which `completed` is `0`.
4. **arm64 versus x86 last-bit divergence in a hosted golden.** A named prior failure class: the
   smoke's own comment at `run-layer-forward-smoke:3862-3876` records that a 32-token digest is
   host-dependent in the last bit and must not be pinned, which is why `BOUNDARY_CASES` carry no
   golden row. *Mitigation:* **the hosted suffix cases stay at five tokens and `KV_WIDTH` 8** (5.1)
   — the same magnitude as every existing engine row — and the over-cap case `ds-suffix-over-cap` is
   a **refusal**, which produces no digest at all. No new golden row computes a digest over more
   than five columns.
   **Realized, and the mitigation was insufficient — 11.3 deviation 7.** Staying at five columns is
   not a bound on host divergence: hosted CI refused `ds-suffix-single-shot-4`, a **four**-token
   single-shot prefill, whose `.schedule[1].l_out_bit_sum` is 12,689,786,356 on macOS/arm64 against
   12,689,786,355 on Linux/x86_64. The reasoning above assumed the 32-token case was near a
   threshold; it is not — a 1-ULP disagreement is available at any width and this fixture reaches it
   at four. The case moves to `BOUNDARY_CASES`. **What a committed golden can pin is a row whose
   digests happen to agree on both hosts, which is not a property a later capability may assume**;
   the durable assertion for a multi-token prefill is a within-host comparison (oracle S, oracle R),
   and the next capability adding one should plan for the boundary list rather than the golden.
5. **Request 49 forces a workaround into the module boundary.** *Mitigation:* it does not, and the
   reason is that this capability adds no cross-module call taking `borrow mut buffer`: the suffix
   write-back goes through `capture_plane`, which is **already in `decode_step`** with the plane,
   and the pass's scalars travel in `Outcome` fields. **Cited as a continuing client; no workaround
   is built and no new request is proposed.**
6. **Saturating an `i64` accumulator.** A named prior failure class. *Mitigation:* 2.10 computes the
   worst case for every quantity the `suffix` object adds; the largest is under `10^10`.
7. **A reader mistakes `output` for the container's vector on a suffix run.** *Mitigation:* 2.9
   records the change as a public field's behaviour changing, keeps the container's claim in `kv.*`,
   and turns the distinction into two assertions rather than a paragraph.
8. **The qualification exceeds its time cap.** *Mitigation:* 5.4's three ordered fallbacks, and the
   suffix leg running resident by default rather than streamed.
9. **Instrument provenance and sampler pinning.** R6 risks 1 and 2, unchanged and still live.
   *Mitigation:* unchanged — the pinned instrument, `--temp 0 -s 0` contractual, the reference
   blob's `sha256` asserted before use.

## 7. Deferred and declared limitations

**Declared limitations.**

| Limitation | Consequence, stated plainly |
| --- | --- |
| **Exact prefixes only** | A container for `a,b,c` cannot serve a prefix of `a,b` (2.12). The relation is left-anchored and total, not longest-common-prefix |
| **Nothing is re-saved** | The extended plane dies with the process. A second suffix on the same prefix re-runs the first suffix's pass |
| **No external per-node oracle for the suffix graph** | 3.6. Byte identity against three references replaces it, and per-node attribution on a failure is a diagnostic route rather than a shipped assertion |
| Everything R6-KV-PERSIST section 7 declares — no durability, no read-only-media load, no exclusive create, no incremental digest, the symlink cleanup scope | **Unchanged and inherited**, because the container path is untouched |

**Deferred capabilities.**

- **Appending: saving the post-suffix plane at `T_prefix + S`.** The obvious next capability and the
  one that makes a suffix reusable. It needs one header decision (`columns_persisted` versus
  `token_count`) that `docs/specs/r6-kv-persist.md` section 7 already frames, plus a rule for what a
  container written by a suffix run *identifies*. Deliberately not pre-empted here.
- **A prefix key, a content-addressed store, and longest-common-prefix lookup.** The lookup half of
  roadmap R6's mechanism 2. Its key tuple is recorded once, in `r6-kv-persist.md` section 2.8, and
  is not re-derived.
- **A prefix-sharing corpus and a TTFT benchmark.** Its own capability, its own corpus, its own
  baseline, its own gate. 1.4 says why it cannot be pre-empted by splitting four short prompts.
- **DRAM/NVMe tiering, eviction, and invalidation.** Roadmap R6's remaining three lines.
- **Prefix truncation** (`columns_persisted != token_count`), which would let one container serve
  every prefix of itself.
- **MoE/OLMoE suffix prefill, the Metal arm, a quantized plane, batch above one, a growing
  `KV_WIDTH`.** Unchanged non-goals.
- **Per-node attribution inside the suffix pass** (3.6), and **`--model-forward` gaining an `n_past`
  operand**, which would give the suffix graph a transcript-comparable sibling.
- **Deferred closure cells, named rather than omitted.** `R6_PLANE_WRITE` on a short suffix
  write-back (4.2) has no forced build, on R6-STEP-N section 7's exact terms; `R6_PLANE_UNAVAILABLE`
  is deferred on R6's terms, unchanged; `mf_write_mask_offset`'s missing upper guard (4.3) is
  unreachable and is not added.

## 8. Align capability requests

Classified per `CLAUDE.md`. **None blocks this capability, and no new request is proposed.**

| Gap | Classification | Status |
| --- | --- | --- |
| A cross-module call with a `borrow mut` argument refuses every shorter-lived operand | Genuine Align gap, already recorded | **Request 49, `PROPOSED`.** One more client, and a *negative* one worth recording: this capability was able to keep the plane's byte movement and its only mutator in one module, so the gap shaped nothing here. Cited as continuing evidence; **no workaround is built** |
| Indexing arrays of Move element types (`array<string>`) | Genuine Align gap, already recorded | **Request 22, `PROPOSED`, stays non-blocking.** 3.5 records that this capability makes the tokenizer's absence *cheaper* — a suffix is an operand, not a decoded string — so it **adds no client** and consumes no hypothetical surface |
| Non-`Copy` capture in `spawn` closures (`task_group`) | Genuine Align gap, already recorded | **Request 41, `PROPOSED`.** Relevant only to parallelising the qualification, which is not attempted (4.8). No new client shape |
| `buffer(cap)` cannot report a failed reservation | Genuine Align gap, already recorded | **Request 35, `PROPOSED`, `high`.** Inherited unchanged through the resident leg; this capability allocates nothing new |
| `fsync`, read-only open, exclusive positional create, incremental digest, bounded `pread`, rebound-`buffer` release, aligned allocation | Genuine Align gaps, already recorded | Requests **31, 21, 30, 29, 38, 39, 33**, all `PROPOSED` and all inherited through the container and arena paths, which this capability does not touch. No new client evidence |

**Numbering, and it is a live hazard.** At `origin/main` `553563e` the register runs **1–51** and
the next free number is **52**. Parallel branches are expected to claim 52, which is why this
document is drafted against **53** as the next free number; **it claims neither**, because it
proposes no request. The same applies to the roadmap: `main` carries items to **30**, item 31
(`C4-REPAIR`) and item 32 (OLMoE decode) are on branches, so this capability is drafted as item
**33**. **Both must be re-checked when this branch merges `origin/main`** — by `git merge`, never a
rebase, so every stacked branch's recorded commits stay reachable — and if `main` has moved, item 33
and every cross-reference to it move with it.

## 9. Reconciliation applied — where each draft landed

**Applied.** This section was drafted as four reconciliation texts to be written into their owning
documents at implementation time, with the rule stated in the draft itself: *an earlier document in
this family reproduced its drafts here and the copies drifted from what was applied, so section 9
becomes a table of where rather than what once the work lands.* The work has landed, so the drafts
are deleted and this is that table. **The applied text is the record.** Where a reader wants to know
what a draft said, `git show` on this document's first commit has it; where a reader wants to know
what is true, the owning document has it.

| Draft | Landed in | What the applied text carries that the draft did not |
| --- | --- | --- |
| 9.1 roadmap item | `docs/specs/roadmap.md`, item **33** | the decode node table is parameterised by **six** literals across three functions, not the five the design predicted (11.1 correction 4); `ds-suffix-tokens-mismatch`; the three hosted synthetic splits; "measured on the real model at every split"; the owner's golden row count; and the review repair's `T_prefix >= 2` refusal, now recorded there as lifted by item 36 |
| 9.2 the active block | `HANDOFF.md`, `## Active: R6-PREFIX-SUFFIX-PREFILL` | the committed head and its next actions, the findings of section 11, the pre-existing defect of 11.2 and its follow-up capability, and the merge re-checks |
| 9.3 the arm's reference | `docs/align-development.md`, the `--decode-step` section | the fifteen-operand grammar, the conditional rule, the sequence cap and its oracle reason, the prefix bound, the `token[<index>]` detail shape, schema 5, the `output` move, and the exact-prefix limitation |
| 9.4 one correction | `docs/specs/r6-kv-persist.md` §2.3 header table and §2.8 schema row | that `document_schema_version` records the document schema the format was **defined against**. The draft's second half — a matching comment at `src/kv_plane.align:41` — was **not** applied, and 11.3 deviation 6 records why: it would end this document's own byte-unchanged claim for a sentence that belongs in the owning document |

Nothing in this section is authoritative. Each row's owning document is.

## 10. Author consistency pass

One pass, ledger against prose, performed before this document was finished. What it found and what
was changed:

1. **`R6_ARITY` and `R6_PATH` are not codes.** Three prior documents in this family present them in
   validation tables as though they were emitted. They are prose names: `run` returns
   `Err(Error.Invalid)` with no document and no code (`decode_step.align:3899-3902`), and the smoke
   asserts these as `NO_DOCUMENT` rows. Section 2.2 and section 2.7 now say so, rather than
   inheriting a table that would have made `ds-arity-16` look like it should carry a code and a
   golden row.
2. **The sequence cap was drafted as `S <= MAX_PREFILL_TOKENS`.** That would let the arm accept a
   run whose own oracle C″ (`--model-forward` at `T_prefix + S`) it refuses — R6-STEP-N's
   consistency pass caught exactly this class after the fact and had to move a constant. Section 2.3
   now caps the **sequence**, states that the cap is the oracle's, and records why the refusal names
   `R6_SUFFIX` rather than `R6_TOKENS`.
3. **`DOCUMENT_SCHEMA_VERSION` is 3 while the document schema is 4.** Found by checking what a 4 → 5
   bump would break. It is a latent prose inconsistency, not a defect: moving the constant would
   refuse every existing container for no safety gain. Section 2.9 states the decision, section 4.5
   claims `kv_plane.align` byte-unchanged on the strength of it, and section 9's row 9.4 records
   where the correction to the document that made the claim landed.
4. **A first draft let `SUFFIX` work without `KV_LOAD`**, because it makes the hosted smoke cheaper
   — no container needed. It was rejected: it is a second way to reach `n_past > 0` with **no
   consumer**, and it doubles the closure matrix to save fixture work. Section 2.3 records the
   rejection with its reason, and section 5.1 shows the cost was illusory anyway, because two of the
   three hosted cases reuse an existing single-shot golden row.
5. **A first draft added a `suffix.sha256` beside `output`.** It would have left `oracle_logits`
   comparing the container's vector against a whole-prompt `llama-debug` blob — a passing oracle
   over the wrong vector. Section 2.9 moves `output` instead, records it as a public field's
   behaviour changing (R6-KV-PERSIST's own precedent), and names the hazard and the two assertions
   that close it.
6. **Oracle S's exclusion list dropped `selection` wholesale in a first draft.** That removes the
   one field a reader would use to check the two runs describe the same sequence. Section 3.2
   excludes only `selection.token_count`, states why, and **compensates it with an explicit equality
   assertion** — and risk 2 records that any later addition to the list is a finding, because a
   growing exclusion list is how an equality oracle stops being one.
7. **A first draft claimed the decode node table "already generalises".** It does not: five literal
   `1`s are written into `mf_decode_row_head` and `mf_decode_row_attention`
   (`layer_qwen2.align:1702, 1721, 1728, 1751, 1763`). What generalises for free is
   `mf_write_mask_offset` and `capture_plane`, and section 1.1's table now distinguishes the two
   cases precisely rather than flattering the second into the first.
8. **A first draft asserted the TTFT saving was "one weight sweep".** It is not: a prefill of any
   width is one sweep, so a suffix run saves `T_prefix` columns of *compute* and no I/O at all — and
   in resident mode not even that. Section 1.4 reason 4 now says the smaller, true thing, which is
   also the stronger argument for why the R6 gate stays unmet.
9. **The `llama-debug` probe reserved by the brief was not taken**, and an earlier draft simply
   omitted it. Section 3.1 records that the host was busy, that the question is answerable from two
   prior documents' arm-internal measurements, and — because "we did not need it" is only credible
   with a stated alternative — names the exact escalation to run if oracle C″ ever fails.


## 11. What implementation found

One pass over the ledger against the shipped diff, and the corrections it forced. Every one is
recorded here rather than edited silently into sections 1 to 4, so a reader comparing the design
against the code finds the difference named.

### 11.1 Corrections to this document's own ledger

1. **Oracle S's exclusion list needed four more fields, and each one is compensated.** Risk 2 said
   any addition is a finding and not an edit; these are the findings. Section 3.2's list of seven
   blocks and eleven fields is **not sufficient**, because four more fields differ between a suffix
   run and its single-shot comparand for reasons that are the operands' and not the arithmetic's:
   `selection.tokens`, `selection.narrow_index`, and `selection.attention_width` describe the
   `TOKENS` operand, which is the prefix on one side and the whole list on the other; and
   `window.residual_bytes` is `n_embd · TOKENS.count · 4`, the prefill's own reservation. **None is
   dropped:** the runner asserts the prefix's list **plus the suffix ids** equals the single-shot
   run's, and that both documents' `narrow_index`, `attention_width`, and `residual_bytes` are the
   arithmetic of their own `token_count`. That is strictly more than the equality removed.
2. **`plane.roundtrip_bytes_compared` cannot be inside oracle S, and section 3.2 said it was.** The
   suffix run verifies the plane once **more** than the single-shot run does — that extra
   verification is acceptance rule 4 — so the two byte counts can never agree, and section 3.2 and
   3.7 rule 4 as drafted are mutually unsatisfiable. It is excluded and compensated by the exact
   identity `suffix == single + 2 · n_layer · (T_prefix + S) · n_head_kv · head_dim · 4`, which is a
   stronger assertion than equality would have been: it names the term rather than tolerating it.
   A **witness** assertion was added beside the list, on `ds-kv-roundtrip`'s own model, so that a
   later widening that removed `decode`, `steps`, `output`, `oracle_logits`, `oracle_decode`, or the
   plane's verdict fails rather than passes. The mutant in 5.8 is that guard, exercised.
3. **Three refusal details differ from section 5.2's matrix, and the matrix was wrong.** All three
   are the same root cause — a detail shape inherited as prose from a prior document in this family
   rather than read out of `layer_forward.parse_tokens` — and it is the same class as section 10
   finding 1, which caught `R6_ARITY`/`R6_PATH` being prose names and missed these.
   1. `ds-suffix-over-vocab` reports `token[0]` and not `token[32]`: `parse_tokens`' detail is the
      offending id's **index**, which is exactly what `R6_TOKENS` reports, and section 2.3's own
      sentence — "mirroring `R6_TOKENS`'s `token[<n>]`" — is what the implementation follows.
   2. `count[0]` is **unreachable**: `parse_tokens` refuses an empty list outright, so a non-`-`
      operand can never parse to zero ids, and `ds-suffix-empty`'s shipped detail is `suffix[]`,
      which is what section 5.2's matrix already expected. No unreachable check is added for it, and
      `src/decode_step.align`'s own comment above `CODE_SUFFIX` no longer lists it as a detail.
   3. **`ds-suffix-and-bad-tokens` reports `R6_TOKENS` `token[32]` and not `count[33]`** — found by
      the review, not by this pass. `count[<n>]` is **never emitted for `R6_TOKENS` at all**:
      `src/layer_forward.align:314-315` labels an over-long list `labelled("token", count)`, so a
      thirty-three-id `TOKENS` operand refuses at index 32. The `count[<n>]` cell is a fiction
      inherited verbatim from `docs/specs/r6-decode-kv-step1.md:169`, and section 2.7's step 3 row
      now carries the shape the code emits.
      **The precedence claim it is evidence for survives, and was checked rather than assumed.** The
      refusal is raised by step **3**'s own lexical parse — `parse_tokens(tokens_text, 9223372036854775807)`,
      before the geometry file is opened — and the shipped document proves it: `model.arch` is empty,
      `selection.token_count` is 0, and `suffix.n_past_base` is `-1`, so step 3c never ran. Section
      2.3's "`R6_TOKENS` (step 3) precedes `R6_SUFFIX` (step 3c)" and section 12.1's precedence row
      are therefore supported by this row, and the only thing that was wrong is the detail spelling.
4. **The decode node table holds `six` token-count literals, not five.** Section 2.5's table and
   section 10 finding 7 name `mf_decode_row_head` and `mf_decode_row_attention`;
   `mf_decode_row_tail`'s row 26 (`CONT_3D` on `kqv_out`, `{n_embd, 1, 1}`) is a sixth, and the
   prefill's own last attention row writes `{n_embd, tokens, 1}` there. So `mf_decode_row_tail` gains
   the parameter too — three functions, not two. At `tokens = 1` the row is unchanged; at `tokens = S`
   a hardwired `1` would have been an `R5_SHAPE` refusal rather than a wrong number, but the literal
   is corrected rather than left to the shape check, because the table is the contract.
5. **The suffix pass's three graph specs must carry `compare = false`, which no section said.**
   Section 3.6 records that the pass has no transcript counterpart, and the first implementation
   still built its specs with `compare = true` because `decode_pass` hardwired it: on a run that
   supplied a `TRANSCRIPT`, the pass reached `compare_transcript_graph` with the **empty** scan the
   loop had not yet prepared, and the process panicked with `index out of bounds: the len is 0 but
   the index is 0`. `decode_pass` now derives `compare` from the pass flag, so section 3.6's declared
   absence is a property of the code and not only of the prose.
6. **`weights.step_pack_bytes` had to stay the decode steps' own counter.** R6-RESIDENT-WEIGHTS
   section 3.4 defines it as "the pack bytes the decode **steps** alone read", and the suffix pass
   runs through the same function. `decode_pass` takes one `suffix_pass: bool` whose only effect is
   which counter its pack reads land in; `suffix.pack_bytes` is section 2.10's own row, and oracle R
   over a suffix leg excludes it for exactly the reason it already excludes the `weights` block,
   compensated by the two assertions that give the exclusion meaning (0 resident, above 0 streamed).
7. **`output`'s digest is taken twice on a suffix run, and that is what makes section 2.8 true.**
   Section 2.9 says a completed pass replaces `output` and section 2.8 says a failed one publishes
   the container's vector; a single digest site cannot do both, because a failure means the
   post-pass site never runs. The container's vector is therefore digested **before** the pass on any
   run that requests one, and a completed pass digests again over its own logits. Both forced builds
   in 5.6 assert the failed half, which was not otherwise reachable.
8. **`T_prefix = 1` is refused, and this is a contract addition made by the review repair.**
   *(Discharged: the refusal was lifted by roadmap item 36 — see 11.5. The record below stands as
   the reasoning that was correct while the defect existed.)* Section
   3.7 rule 2 is unconditional: a suffix run and the single-shot run of `TOKENS ++ SUFFIX` are the
   same run. At `T_prefix = 1` it is **not true, silently** — the container was written by a
   one-token prefill, which computes the embedding of token 0 whatever the operand said (11.2), so
   the loaded plane is the wrong plane and the suffix pass faithfully continues it. Measured on the
   hosted fixture at the implementation head: a save of `TOKENS = 3,17` truncated to one token, then
   load-plus-suffix, produced a document whose `output.sha256` differed from the single-shot run's.
   Two dispositions were available — refuse, or scope rule 2 to `T_prefix >= 2` and say so in the
   smoke's PASS text — and **refusing is chosen**, because a rule with an exception a caller cannot
   see is how an acceptance oracle stops being one, and because the exception is not this
   capability's arithmetic but a defect it neither introduced nor fixed.
   Measured on the hosted fixture at the implementation head, `KV_WIDTH` 8, `STEPS` 1, one
   `--decode-step` save at `TOKENS = 3` and then a load-plus-suffix of `17` against a single-shot of
   `3,17`:

   ```text
   save    TOKENS 3                     -> status ok, output 62a46efd..., kv SAVED
   suffix  TOKENS 3, SUFFIX 17          -> status ok, output 250562bc..., argmax 27, ids [27]
   single  TOKENS 3,17                  -> status ok, output 99781f3e..., argmax 27, ids [27]
   ```

   `250562bc... != 99781f3e...`: rule 2 fails, `status` is `ok`, and the decoded id agrees by
   coincidence — which is exactly the shape a silent violation takes. The save leg's own
   `62a46efd...` is the same digest a one-token `--model-forward` produces for **every** id (11.2),
   which is the root cause seen from this arm.
   The refusal is `R6_SUFFIX` with detail `prefix[<n>]`, raised in step 3c before the sequence cap
   (2.3, 2.7); `ds-suffix-prefix-one` is its hosted case and its golden row; `docs/align-development.md`
   documents it; and `scripts/run-decode-step`'s split guard is `2 <= j`, which never produced a
   one-token prefix but now says so (correction 10). **It narrows the accepted surface**, and the
   resume condition is the follow-up capability of 11.2: when a one-token prefill computes the right
   row, this refusal is the thing to remove, and removing it widens the surface rather than moving it.
   **That condition was met and the refusal is gone (11.5).**
9. **The sentence the runner prints beside the TTFT trio was wrong, and it was product output.**
   Section 1.4 reason 4, section 5.10, and `scripts/run-decode-step`'s printed line all said the
   difference between the single-shot leg and the suffix leg is `T_prefix` columns of prefill
   compute "**and nothing else**". Section 5.10's own next paragraph — written from the measurement
   — says the opposite and quantifies it: the observed gap is about 3 s, the per-column term is about
   0.15 s, and what (b) actually removes is the prefill pass's pack read and graph construction for
   the whole prompt, paid for with a 29,970,432-byte container read. Two to three columns cannot
   account for 3 s. All three sites now name the exchange. **The conclusion is unchanged and is
   strengthened**: an I/O trade on a six-token prompt is even less a prefix cache than pure
   arithmetic would have been, and the R6 gate stays unmet for the reasons 1.4 gives.
10. **`scripts/run-decode-step`'s split guard admitted `j = 1`.** `if 1 <= j < len(ids)` accepts the
    midpoint of a two-id prompt, which is a one-token prefix — contradicting section 5.4's stated
    "smallest split is `j = 2`" and, after correction 8, reaching a refusal. No prompt in the corpus
    tokenizes to two ids, so no run ever took it and section 5.9's five splits are unchanged; the
    guard is `2 <= j` and the invariant is now the code's rather than the corpus's.
11. **Risk 2's witness guard checked blocks where it needed fields, and a mutant survived it.** The
    guard asserted `"decode" in witness`, `"steps"` non-empty, `steps[0].sha256`, `output.sha256`,
    `oracle_logits`, `oracle_decode`, and the plane's two fields. Excluding
    `("decode", "token_ids")` — a *field*, which is the shape every one of the five real additions
    to the list took — leaves `decode` present and **passed**. The guard now names the fields:
    `decode.token_ids`, `n_past_first`, `n_past_last`, `steps_completed`; `steps[0].n_past` and
    `plane_column_written`; `output.argmax`; and `oracle_logits.verdict` and `byte_identical`. Risk
    2's whole point is that the exclusion list must not grow silently, and a block-level guard could
    not see the growth it was written for.
12. **`scripts/ggml_shim_stub.c`'s suffix latch was set and never cleared.** Both forced-build arms
    read `align_force_suffix_pass`, which was raised by the suffix pass's own mask upload and left
    raised for the rest of the process — so the comment claiming the shift is confined to the pass
    was false for any decode step that followed one. No shipped case observes it, because both
    forced builds fail inside the pass and no step runs; it is a latent trap for the next forced
    build. Every mask upload now re-decides the latch, so a decode step's one-row mask clears it.

### 11.2 A pre-existing defect this capability found and did **not** fix — `MF-SINGLE-TOKEN-LOGITS`

> **Discharged. Roadmap item 36 fixed it and section 11.5 records the lift and the corrections
> to this section's own measurements.** This section is kept as filed, because it is the record
> of what this capability found and why it refused; three of its claims turned out to be wrong
> and 11.5 names each one. Read them together.

**A one-token prompt computes the logits of token 0.** `model_forward.fill_members` gathers an
embedding row by id only when `m.pieces[at] > 1`, and `build_embed_members` sets `pieces = tokens`;
at `tokens = 1` the gather falls to the whole-member branch and reads the table's **first** row.

**Reproduction, runnable as written**, from a clean checkout at this head. It needs no model, no
network, and no ggml: the fifth smoke block's own `stub+engine` shim and the checked-in fixture
generator are the whole apparatus.

```sh
W=$(mktemp -d)
ALIGN_LLM_GGML_SHIM_DIR="$W/lib" ALIGN_LLM_GGML_FORCE=engine scripts/build-ggml-shim
export LIBRARY_PATH="$W/lib${LIBRARY_PATH:+:$LIBRARY_PATH}"   # the link step finds -lggml_shim
scripts/alignc build src/ggml_spike.align && mv -f ggml_spike "$W/ggml-spike"
python3 scripts/layer_forward_fixture.py "$W" --model >/dev/null
export DYLD_LIBRARY_PATH="$W/lib"      # LD_LIBRARY_PATH on Linux
for t in 0 3 17; do
  "$W/ggml-spike" --model-forward "$W/model-pack.alignpack" "$W/geometry.json" "$t" \
    - "$W/model-source.bin" - 8
done
```

The `--model-forward` arm takes seven operands — `PACK GEOMETRY TOKENS DOCUMENT REFERENCE
TRANSCRIPT KV_WIDTH` — and the three-operand form printed in an earlier draft of this section was
not runnable. The `engine` flavour is load-bearing: the default stub answers
`R5_GGML_UNAVAILABLE`/`stub` and computes nothing.

```text
TOKENS 0    -> status ok, output.sha256 62a46efd73d18be1..., argmax 24
TOKENS 3    -> status ok, output.sha256 62a46efd73d18be1..., argmax 24
TOKENS 17   -> status ok, output.sha256 62a46efd73d18be1..., argmax 24
TOKENS 3,17 -> status ok, output.sha256 99781f3e63a67b18..., argmax 27   (the control)
```

Three different single-token prompts, one answer; the two-token control moves, which is what makes
the one-token case a defect rather than a fixture property. It is **reachable from the shipped CLI** on
`--model-forward`, `--decode-step`, and the MoE arms, it is silent — `status: ok` — and the resident
path does **not** share it, because `stage_embed_row` gathers by id at every count. *(11.5: the
resident path shares half of it — `stage_embed_row` stages the right row, but `compare_source`
carries the same predicate, so a one-token non-zero resident run with a reference is refused with
`R5_SOURCE_DIVERGED` over a correct result.)* No golden in this
repository exercises `token_count == 1`, which is why it has been latent since R5B.

**It is not fixed here**, and the reason is the capability boundary rather than convenience: the
honest fix is a `gathered` discriminator on `model_forward.GraphMembers`, which is an R5B/R5E-owned
record with eighteen construction sites across three modules and four arms, and it needs its own
regression (a `mf-tokens-one` golden row) and its own review. Filing it under this capability would
put an R5B correctness change inside a review scoped to a suffix graph.

**What this capability does instead is depend on none of it, and now refuses rather than
inheriting it.** Section 5.1's hosted matrix as designed had a `T_prefix = 1` case (`ds-suffix-2`,
prefix `3`); it would have saved a container for a plane computed from the wrong embedding row, and
oracle S would have failed for a reason that is not this capability's. The three shipped cases are
all at `T_prefix = 2`, and the two closure cells the dropped case carried — `S >= 2`, and a suffix
column attending to an earlier suffix column — are carried by `ds-suffix-2` (`S = 2`) and
`ds-suffix-3` (`S = 3`) instead. The real-model leg is unaffected: section 5.4's smallest split is
already `j = 2`, chosen for an unrelated reason. **The review found that avoiding the case in the
corpus is not the same as refusing it on the surface** — a caller could still ask for a
`T_prefix = 1` suffix run and get a silently wrong `ok` — so 11.1 correction 8 makes it a refusal.

**It is filed as a follow-up capability, `MF-SINGLE-TOKEN-LOGITS`**, so the next action survives this
document and the `HANDOFF.md` block that will replace this one. It had **no roadmap number** when
filed — `main` carried items to 30, 31 and 32 were on branches, and this capability was drafted as
33 — and **took 36** when it was picked up. It is recorded as a named follow-up under roadmap item 33 and in
`HANDOFF.md`, and it takes its number when it is picked up.

| Field | Value |
| --- | --- |
| Name | `MF-SINGLE-TOKEN-LOGITS` |
| Owner surface | `src/model_forward.align` — `fill_members`, `build_embed_members`, `GraphMembers` |
| Blast radius | eighteen `GraphMembers` construction sites across three modules and four arms (`--layer-forward`, `--model-forward`, `--moe-model-forward`, `--decode-step`) — **measured as nine sites and four arms**, and `--layer-forward` is not one of them while `--model-forward-gpu` is (11.5) |
| Symptom | any prompt of exactly one token computes the embedding of token 0, silently, `status: ok` |
| Not shared by | the resident path: `stage_embed_row` gathers by id at every count — **half true** (11.5) |
| Why it is latent | no golden in this repository exercises `token_count == 1`; it has been so since R5B |
| Fix | a `gathered` discriminator on `GraphMembers`, so the gather is chosen by construction rather than by `pieces > 1` |
| Regression it must add | `mf-tokens-one` in `scripts/model-forward-golden.jsonl`, plus the same question asked of `--moe-model-forward` |
| Owner test | `gmake layer-forward-smoke` |
| What it unblocks here | removing this capability's `R6_SUFFIX`/`prefix[<n>]` refusal (11.1 correction 8), which **widens** the accepted surface and needs no other change — **done**, 11.5 |
| Why not fixed here | filing an R5B correctness change inside a review scoped to a suffix graph. It is a distinct failure domain, which is `CLAUDE.md`'s own reason to split |

### 11.3 Deviations from the verification plan

1. **`scripts/layer_forward_fixture.py` is byte-unchanged**, where section 4.7 planned a
   `first_position` parameter on `model_layer`, an optional past-plane operand, two new containers,
   and a new five-token prefill reference. None is needed, and the reason is that the references
   section 4.7 wanted already exist in stronger form: the prefix's container is written by the arm's
   own **save** direction, which R6-KV-PERSIST's rule already verifies end to end and which
   `ds-suffix-save-prefix` publishes as its own golden row; and the comparand for every split is a
   real single-shot `--decode-step` run plus `--model-forward` at the whole list, which is oracle C″
   and is built from the **prefill** row table rather than the decode one. A pure-Python reference
   would be a fourth implementation of a number three implementations already agree on byte for byte.
   Two of the three splits reuse a comparand that already existed as a golden row, which is what
   section 5.1 wanted from the fixture change and gets without it.
2. **The suffix position image is written in `decode_step.schedule_decode`**, beside the decode
   loop's own position loop, and not as a new producer in `src/model_forward.align` as section 4.4
   planned. It is four lines next to the three loops it is a variant of; moving it across the module
   boundary would take a `borrow mut buffer` argument, which is Request 49's refused shape.
3. **`scripts/build-ggml-shim` gains two flavour arms** beside the two stub arms section 4.6 named.
   The design named the stub's arms and not the builder's; they are the same change seen from the
   two files it must touch. `baseline-check` stays `N/A` on R6-STEP-N's condition — the `Makefile` is
   byte-unchanged and both arms are inputs to the **stub** — and must be re-checked at the
   publication head.
4. **Section 5.1's hosted matrix shipped with three changes, not one.**
   1. **No `T_prefix = 1` case**, for 11.2's reason: `ds-suffix-2` moves from prefix `3` to prefix
      `3,17`, so its `S = 2` runs at `T_prefix = 2` and needs a **new** four-token comparand,
      `ds-suffix-single-shot-4`, rather than the existing `ds-engine-ok`.
   2. **`ds-suffix-1`'s comparand is `ds-kv-args-dash-dash`, not `ds-engine-ok`.** Both are
      single-shot runs of `3,17,5`; the shipped one runs at `N = 3` and decodes `[24, 9, 27]`, the
      planned one at `N = 1` and decodes `[24]`. The suffix cases run at `N = 3`, and oracle S
      compares `decode` and every `steps[]` object in full, so the comparand must have the same step
      count. Section 5.1's sentence "the first two share a comparand that already exists as a golden
      row" is therefore true of the **first only**, and true of it against a different existing row
      than the one named.
   3. **A fourth success case was added**, `ds-suffix-resident`: `ds-suffix-3` plus one `RESIDENT`
      operand, which is oracle R's third pair and the assertion that `suffix.pack_bytes` is exactly
      0 resident and non-zero streamed (2.10). Section 5.1's table has three rows; section 5.5's has
      four.
5. **The TTFT trio's three legs all stream, and the first implementation got that wrong.** Legs (a)
   and (b) were written to take `${SUFFIX_RESIDENT}` — `weights` on a capable host — while leg (c) is
   R6-KV-PERSIST's own twelve-operand invocation with no `RESIDENT` position at all, which section
   1.4 carries forward *unchanged* precisely so the three are comparable. Two legs paying the
   arena's one-time fill and the third not is a difference in the instrument rather than in the
   thing measured. Found by reading the first run's own numbers; the runner now passes `-` on all
   three and prints leg (c) beside the other two, and section 5.9's result is the re-run at the
   corrected head. The main suffix and single-shot runs keep `${SUFFIX_RESIDENT}`, because they are
   compared only with each other.
6. **Section 9's row 9.4 correction is applied to `docs/specs/r6-kv-persist.md` only**, and not also
   as a comment at `src/kv_plane.align:41`. The two halves of that draft contradict each other: section
   2.9 and section 4.5 claim the file is **byte-unchanged**, and a comment edit would end that claim
   for a sentence that belongs in the owning document anyway. The corrected prose is in that
   document's section 2.3 header table and its section 2.8 schema row, both of which now say the
   field records the document schema the format was **defined against**.
7. **One added golden row did not survive hosted CI, and risk 4's mitigation was the wrong bound.**
   `ds-suffix-single-shot-4` — `ds-suffix-2`'s four-token single-shot comparand — is host-dependent
   in the last bit: `.schedule[1].l_out_bit_sum` **12,689,786,356** on macOS/arm64 against
   **12,689,786,355** on Linux/x86_64, with `.schedule[1].l_out_sha256` differing with it. The
   `Pinned Align compiler and supported checks` job refused the golden at the publication head
   `c91757c`. Risk 4 mitigated this by keeping every new case at or below five columns, on the
   reading that R6-RESIDENT-WEIGHTS' 32-token divergence was a long-accumulation effect; **it is
   not** — a 1-ULP disagreement is available at any width, and this fixture reaches it at four
   tokens. The case moves into `BOUNDARY_CASES`, exactly as `ds-resident-stage-full` did
   (`docs/specs/r6-resident-weights.md` section 5.9 deviation 9): it still runs under the engine
   shim, `record()` still asserts document identity, and **oracle S still compares `ds-suffix-2`
   against it** — a within-host comparison, and therefore correct on every platform. Only the
   committed row goes, because a committed row for it would be a statement about the machine that
   regenerated the file. `scripts/decode-step-golden.jsonl` is 137 rows and the removed row is the
   only difference from `c91757c`'s 138; the other twenty new rows are byte-identical, and the
   runner reports 139 documented cases with 137 golden rows.
   **Not worked around by loosening `normalize`.** Dropping `schedule[*].l_out_*` from the golden
   would hide the same divergence on every existing row, including the ones that currently agree,
   and would trade a real cross-host check for a count.

### 11.4 What did not move

`src/kv_plane.align`, `scripts/kv_plane_reader.py`, `src/ggml_ffi.align`, `scripts/ggml_shim.c`,
`src/ggml_spike.align`, `src/layer_olmoe.align`, `src/moe_model_forward.align`, the `Makefile`, and
`scripts/layer_forward_fixture.py` are **byte-unchanged**. `MF_DECODE_LAYER_NODE_COUNT` is still 38,
the slot high-water is still 66 against a capacity of 128, `MAX_PREFILL_TOKENS` is still 32, the
`akvp` container's `format_version` is still 1, and its `DOCUMENT_SCHEMA_VERSION` is still 3 —
section 2.9's decision, and section 9's row 9.4 prose correction is the only thing that moves with it.

### 11.5 The `T_prefix >= 2` bound, lifted by `MF-SINGLE-TOKEN-LOGITS` (roadmap item 36)

The refusal 11.1 correction 8 added existed for exactly one reason, and that reason is gone.
`docs/specs/mf-single-token-logits.md` is the authoritative record; this section is what changes
**here**, and it corrects three measurements 11.2 made from this capability's own vantage point.

**The fix.** `GraphMembers` carries a `gathered: bool`, `true` from `build_embed_members` whatever
the token count and `false` from every other builder, and `fill_members`/`compare_source` read
`m.gathered && at == 0` instead of `m.pieces[at] > 1`. `gathered` is true exactly where `pieces > 1`
was, so every `T >= 2` document — including all 137 rows this capability's corpus shipped — is
byte-identical.

**Three corrections to 11.2.**

1. **Nine construction sites, not eighteen.** Four in `src/model_forward.align`, four in
   `src/moe_model_forward.align`, one in `src/decode_step.align`. Eighteen was an estimate over
   three modules; the record is `pub GraphMembers` twice and one cross-module literal.
2. **Four arms, and not the four named.** `--layer-forward` and `--moe-layer-forward` are **not**
   affected — they gather unconditionally on member 0 — while `--model-forward-gpu` is, through
   `render_parts` -> `execute`. The affected set is `--model-forward`, `--model-forward-gpu`,
   `--moe-model-forward`, and `--decode-step`'s prefill.
3. **The resident path is not immune.** 11.2 said `stage_embed_row` gathers by id at every count, so
   residency does not share the defect. That is half the story: staging is correct, but
   `compare_source` carried the same predicate, so a one-token non-zero **resident** run with a
   REFERENCE was refused with `R5_SOURCE_DIVERGED` over a correct result — a false alarm on a right
   answer. Both predicates had to move together, and `ds-tokens-one-resident` is the row that pins
   it.

**What is lifted here.** Step 3c's `T_prefix >= 2` term and its `prefix[<n>]` detail are deleted
from `stage_inputs`; `R6_SUFFIX` keeps its three remaining details; `scripts/run-decode-step`'s
split guard widens from `2 <= j` to `1 <= j`, which adds no real-model run because every prompt that
leg takes is six ids or longer. Nothing replaces the check: the sequence cap is the only bound on
`T_prefix`.

**The evidence, hosted.** `ds-suffix-prefix-one` stops being a refusal and becomes rule 2's own
`T_prefix = 1` witness, joined by the two rows it needs — `ds-suffix-save-prefix-one`, a one-token
prefill save in its own process, and `ds-suffix-single-shot-2`, the two-token comparand. Both stay
at two tokens, so both carry a golden row: deviation 7's cross-platform digest drift starts at four.
Oracle S holds byte for byte and oracle C″ agrees with `--model-forward` at `3,5`:

```text
ds-suffix-save-prefix-one  TOKENS 3               -> ok, output 867ebc4e..., kv SAVED, plane 2 cols
ds-suffix-single-shot-2    TOKENS 3,5             -> ok, output 0cd795d9..., plane 5 cols
ds-suffix-prefix-one       TOKENS 3, SUFFIX 5     -> ok, output 0cd795d9..., suffix n_past_base 1
```

`867ebc4e...` is the same one-token digest `mf-tokens-one` carries on `--model-forward`, and it is
**not** the `62a46efd...` of 11.1 correction 8's transcript — that digest is now
`mf-tokens-one-zero`'s, the id-0 control, which is precisely the defect's signature.

**Mutation.** Reverting the four predicates to `m.pieces[at] > 1` kills `ds-suffix-prefix-one`
through oracle S **and** oracle C″, kills `ds-suffix-save-prefix-one`'s golden row, and kills the six
rows item 36 added — and nothing else in the six corpora. The refusal this section removes is
therefore replaced by a test rather than by an assumption.

**The corpus.** 137 rows to **141**: `ds-suffix-save-prefix-one`, `ds-suffix-single-shot-2`,
`ds-tokens-one`, `ds-tokens-one-resident` added, and `ds-suffix-prefix-one` the one changed row —
refusal to pass. Section 5.6's matrix is twelve refusals rather than thirteen.

## 12. Ledger and closure matrix to the final diff

`CLAUDE.md`'s proportional design gate, step 4: every applicable ledger row and closure cell mapped
to the shipped diff and its passing evidence, or to an explicit deferral. Line references are to the
implementation head.

### 12.1 Section 2's ledger rows

| Ledger row | Where it lands | Evidence |
| --- | --- | --- |
| 2.2 `SUFFIX` at `args[14]`, arity `{5,6,7,9,10,11,12,13,14,15}`, no path check | `decode_step.run` (`count > 15`, `suffix_text := if count >= 15 { args[14] } else { "-" }`) | `ds-arity-16` `NO_DOCUMENT`; every `ds-suffix-*` row |
| 2.2 absence is `-` and is the pre-existing behaviour | `run`'s default and `execute`'s `o.suffix_requested = suffix_text != "-"` | all 116 pre-existing golden rows unchanged but for `schema_version` and `suffix` |
| 2.3 grammar shared with `TOKENS` | `stage_inputs` step 3c calls `layer_forward.parse_tokens` twice, unchanged | `ds-suffix-empty`/`-garbage`/`-trailing` |
| 2.3 sequence cap `T_prefix + S <= 32`, detail `sequence[<n>]` | `stage_inputs` step 3c | `ds-suffix-over-cap`, `ds-suffix-over-cap-and-narrow` |
| 2.3 prefix bound `T_prefix >= 2`, detail `prefix[<n>]` (added by the review repair, 11.1 correction 8; **lifted**, 11.5) | ~~`stage_inputs` step 3c~~ — no code remains; 3c decides the grammar and then the sequence cap | `ds-suffix-prefix-one` → a passing oracle-S row at `T_prefix = 1`; `ds-suffix-tokens-mismatch` keeps the 3c ≺ L12 precedence |
| 2.3 vocabulary re-check at 3′ | `stage_inputs`, same pass as `TOKENS` | `ds-suffix-over-vocab` (detail `token[0]`, section 11 finding 3) |
| 2.3 plane bound widened, `R6_KV_WIDTH` | `stage_inputs` step 6, `width < parsed.count + suffix_count + steps` | `ds-suffix-narrow-width` |
| 2.3 `SUFFIX` without `KV_LOAD` is `R6_KV_ARGS`/`suffix[no_load]` | `execute` step 2c | `ds-suffix-no-load`, `-and-save`, `-no-load-bad-steps` |
| 2.3 precedence 2c ≺ 3b, 3 ≺ 3c, 3c ≺ 6, and `prefix` ≺ `sequence` inside 3c | the checks' order | the three precedence cases above, and `ds-suffix-and-bad-tokens`' own document (`suffix.n_past_base = -1`, empty `model`) showing step 3 refusing before 3c ran — 11.1 finding 3 |
| 2.4 three-range ordering invariant | `run_step_graph`: upload → compute → `capture_plane(S, T_prefix)` → `verify_plane(n_past + tokens)` | `ds-force-suffix-writeback-offset` at `col[2]`; the two suffix-only mutants in 5.8 |
| 2.4 `columns_written` advances after the last layer only | `schedule_decode`'s post-pass branch; `capture_plane`'s `first_column == 0` guard unchanged | `ds-force-compute-suffix` publishes 2 |
| 2.5 the decode table at `tokens = S` | `layer_qwen2.mf_decode_layer_node_table(g, n_past, tokens, width)` and its three row builders | every other golden in `scripts/` byte-unchanged, all six; `MF_DECODE_LAYER_NODE_COUNT` still 38 |
| 2.5 mask at `(S, T_prefix)`, writer unchanged | `schedule_decode`'s `suffix_mask` | the mask mutant in 5.8 |
| 2.5 `mf_write_mask_offset`'s comment corrected; no guard added | `layer_qwen2.align` doc comment | stated, with the reachability reason |
| 2.6 positions absolute, ids `0 .. S-1`, `out_ids = S - 1` | `schedule_decode`'s three suffix images | the position mutant in 5.8 |
| 2.6 the prefill's embedding builder at `pieces = S` | `decode_pass`'s `tokens_in > 1` branch | `ds-suffix-2`/`-3` differ from `ds-suffix-1` in `S` alone |
| 2.7 `R6_SUFFIX`, one new code, ~~four~~ **three** details (`suffix[<text>]`, ~~`prefix[<n>]`~~, `sequence[<n>]`, `token[<index>]`) — 11.5 | `CODE_SUFFIX`, `suffix_detail`, and two `labelled` details | 5.6's matrix, every row naming its exact detail |
| 2.7 X1–X5 and the `suffix[]` locator | `schedule_decode`'s pass block and `prefix_suffix` | both forced builds' details |
| 2.8 a partial pass publishes no completion | the pass block's failure branch | both forced builds, all six clauses |
| 2.9 schema 5, the `suffix` object in every document | `SCHEMA_VERSION`, `render_suffix`, `render` | `record()` asserts the object on all 139 documented cases (137 golden rows) |
| 2.9 `output`/`oracle_logits` move on a completed pass | the two digest sites | `output.sha256 != kv.logits_sha256` per case; the container's vector on both forced builds |
| 2.9 `plane.source` stays `"LOADED"` | unchanged | asserted per case |
| 2.9 `normalize` zeroes only `suffix.compute_ns` | the smoke's `normalize` | the golden holds the other ten |
| 2.9 container `DOCUMENT_SCHEMA_VERSION` stays 3 | `src/kv_plane.align` byte-unchanged | the **52** `KV_REFUSALS` rows still pass (51 at the design pin; the one addition is this capability's `ds-suffix-tokens-mismatch`) |
| 2.10 metrics; no cost ceiling recorded | `suffix.*` fields | 5.5's table; no performance row selected |
| 2.11 prerequisites | all verified by reading at the pin, then by running | 5.5 to 5.9 |
| 2.12 exact prefixes only | L12/L13 unmodified | `ds-suffix-tokens-mismatch` → `count[3]` |

### 12.2 Section 4's closure cells

| Cell | Disposition |
| --- | --- |
| 4.1 formation/validation, construction, success, failure, malformed input, early exit, cleanup | **all met**; the named regressions all ship, `ds-force-compute-suffix` is the failure and early-exit cell |
| 4.1 move-in/out, source nulling, replacement, return | **N/A as designed** — no ownership transfer is added |
| 4.2 the plane's seven cells | **met**; `ds-force-suffix-writeback-offset` is the round-trip cell |
| 4.2 failure — write-back short (`R6_PLANE_WRITE`) | **deferred as designed**, on R6-STEP-N section 7's terms: the arm's own sizing makes it unreachable and no forced build produces it |
| 4.3 `layer_qwen2` construction/success; failure, malformed input, early exit, cleanup `N/A` | **met as designed**; every other golden in `scripts/` is byte-unchanged, all six |
| 4.3 `mf_write_mask_offset`'s missing upper guard | **deferred as designed**, unreachable under step 6 |
| 4.4 `model_forward` construction, the seam, success, failure | **met**, except the `render`-time `completed ⇒ columns_written == n_past_base + token_count` assertion, which lives in the **smoke's** `record()` rather than in `render` — an Align `render` cannot refuse to write a document without a second failure path through a pure function, and the property is asserted on every one of the 139 documented cases instead |
| 4.4 the position producer in `model_forward` | **deviation 2**: it stays in `decode_step` beside its three siblings |
| 4.5 `kv_plane.align` and the reader byte-unchanged | **met**, with no diff to check, which is the evidence |
| 4.6 FFI, both shims, `ggml_spike.align` byte-unchanged | **met**; the stub and the builder are the recorded exception |
| 4.7 the fixture's suffix reference | **deviation 1**: `scripts/layer_forward_fixture.py` is byte-unchanged and the references are the arm's own save direction plus `--model-forward` |
| 4.8 the smoke and the runner | **met**; `normalize_suffix` ships with a witness guard the design did not ask for |
| 4.8 shared process state `N/A`, concurrency unsupported | **unchanged**; Request 41 gains no client |
