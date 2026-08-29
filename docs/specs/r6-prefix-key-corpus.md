# R6-PREFIX-KEY — a content-addressed store for prefix planes

Status: **designed, not implemented, 2026-08-29**, on branch `agent/r6-prefix-key-corpus`.

Branch cut from `MF-SINGLE-TOKEN-LOGITS` `40eb965` — that branch's merge of `origin/main` `45ff38e`
(PR #148, R6-OLMOE-DECODE) — and therefore stacked on roadmap item **36**, whose lift of the
`T_prefix >= 2` refusal this capability depends on (2.2). The five documents this one extends are
`r6-decode-kv-step1.md`, `r6-step-n.md`, `r6-kv-persist.md`, `r6-resident-weights.md`, and
`r6-prefix-suffix-prefill.md`. "Unchanged" below means unchanged **from them**, and a row any of
them settled that this document does not restate is still in force.

Sections 1 to 10 are written **before implementation**: 1 to 4 and 6 to 9 are the **ledger**,
5 is the **verification plan**, and 10 is the **author consistency pass**. Every figure is either
quoted from a prior document with its source named, or is arithmetic on such a figure and says so,
or is this document's own measurement and is labelled as one (1.2).

**Section 11 is the successor's charter**, `R6-PREFIX-TTFT`, and is not this capability's contract.

---

## 1. Decision and boundary

### 1.1 What this capability is

`R6-KV-PERSIST` (item 29) made a prefill plane outlive its process. `R6-PREFIX-SUFFIX-PREFILL`
(item 33) made a loaded plane continuable with a **different** suffix. Between them they ship the
*execution* half of the R6 gate's second line, "repo stable prefix KV", and its own section 1.4
names the four things still missing: **a key, a store, a corpus, and a consumer**.

This capability ships the **key and the store**, and nothing else:

- **`--decode-step` gains a `STORE` operand**, a directory path, `-` for absent, mutually exclusive
  with both `KV_SAVE` and `KV_LOAD`.
- The arm **derives** a 32-byte key from the operands it already validates — the pack's
  source-identity digest, the geometry's digest, the `TOKENS` digest, `KV_WIDTH`, and the format's
  own version scalars (2.3) — and addresses one file, `<STORE>/<key-hex>.akvp`.
- **Hit** (`fs.exists` true): the container is loaded through `R6-KV-PERSIST`'s existing L1–L14
  path, then `R6-PREFIX-SUFFIX-PREFILL`'s suffix pass runs over `SUFFIX`, then the `N`-step loop.
- **Miss** (`fs.exists` false): the arm prefills `TOKENS`, **saves** the container to that exact
  path through the existing `KV_SAVE` writer, then runs the same suffix pass and the same loop.
- **The two paths produce the same document.** Outside a named exclusion list of six fields, a miss
  run and the hit run that follows it are byte-identical. That is oracle K (3.1) and it is this
  capability's acceptance rule.

**What it does not ship** is the corpus, the `MAX_PREFILL_TOKENS` lift the corpus needs, and any
TTFT claim. Section 1.2 records why that is a split rather than an omission, and section 11 is the
successor's charter.

### 1.2 The split decision, and the measurement that forced it

The work was scoped as one capability, `R6-PREFIX-KEY-CORPUS`. **It is split into two**, and the
reason is a number this document measured rather than a judgement about effort.

**This document's own probe.** `eval/prompt/canonical-v1`'s shared prefix and the three
`eval/tasks/prompt-v1/*/task-prompt.json` suffixes were tokenized with the reference model's own
vocabulary:

```sh
llama-tokenize -m ~/models/qwen2.5-coder-7b-instruct-q4_k_m.gguf -f PREFIX.txt --ids
```

where `PREFIX.txt` is `base-prompt.json`'s `text` concatenated with `repo-prompt.json`'s `text`, and
each suffix file is one `task-prompt.json`'s `text`. No chat template and no BOS were applied; this
is a **sizing** probe and not the pinned id list, which section 11.3 requires to come from the
qualification's own pinned instrument (`llama-debug --save-logits`, `*-tokens.bin`). A ±1 id
difference between the two instruments would not move any conclusion below.

| Artifact | Bytes of `text` | Tokens |
| --- | --- | --- |
| Shared prefix — `base-prompt.json` + `repo-prompt.json` | 1,735 | **370** |
| Suffix — `duration-half-away-from-zero` | 2,976 | **696** |
| Suffix — `record-codec-round-trip` | 3,810 | **825** |
| Suffix — `layer-precedence-frozen-module` | 4,771 | **1,049** |

| Task | `T_prefix` | `S` | `T + S` | prefix share of the prefill |
| --- | --- | --- | --- | --- |
| `duration-half-away-from-zero` | 370 | 696 | 1,066 | 34.71 % |
| `record-codec-round-trip` | 370 | 825 | 1,195 | 30.96 % |
| `layer-precedence-frozen-module` | 370 | 1,049 | 1,419 | 26.07 % |
| — | — | — | — | mean **30.58 %**, worst **26.07 %** |

**Two consequences, and both were unknown when the work was scoped.**

1. **The suffixes are larger than the shared prefix, by a factor of 1.9 to 2.8.** The scoping
   analysis assumed a "~1.9 kB, ~450 token" prefix and did not size the suffixes. A shared prefix
   that is 26 % of the prefill is still worth a gate — section 11.2 does the arithmetic — but it is
   not the 60–80 % share the phrase "one long stable prefix" suggests, and the design must not be
   written as though it were.
2. **`MAX_PREFILL_TOKENS` must go from 32 to at least 1,419**, not to "enough for ~450 tokens". The
   constant is read as code by **seven** `.align` modules and **three** scripts (11.1) — and cited in
   the comments of a further four — bounds a persisted header field
   (`r6-kv-persist.md` 2.3.1, offset 124), sizes a staging reservation in `model_forward`, and is
   the sequence cap `R6_SUFFIX sequence[<n>]` reports. Lifting it is a capability's worth of blast
   radius on its own.

**The split, and where the boundary is.**

| | `R6-PREFIX-KEY` (this document) | `R6-PREFIX-TTFT` (section 11) |
| --- | --- | --- |
| Ships | `STORE`, the key, the store, hit/miss, schema 6 | the `MAX_PREFILL_TOKENS` lift, the pinned corpus, the gate measurement |
| `MAX_PREFILL_TOKENS` | **32, unchanged** | 32 → **2048** (11.1) |
| Performance claim | **none**, so `CLAUDE.md`'s performance row is **not selected** and no cost ceiling is recorded | **yes**, with the ceiling recorded before its implementation (11.2) |
| Failure domain | persisted identity and the filesystem | prefill capacity and measurement |
| Consumer-complete? | **Yes** — a caller with a shared prefix at `T + S <= 32` gets keyed reuse end to end, with no path bookkeeping. This is exactly the boundary `R6-KV-PERSIST` shipped at `T <= 6` | Yes — the benchmark leg over the pinned corpus |

`CLAUDE.md` warns against splitting for its own sake and asks for "an independently usable consumer
boundary or a distinct failure domain". **Both tests pass**, and the second is the stronger: a
signed-off content-addressed store whose key is wrong is a *correctness* failure that survives on
disk, while a `MAX_PREFILL_TOKENS` that is too small is a *refusal*. Landing them together would put
one comprehensive review over a diff that mixes a new persisted identity with a seven-module constant
lift, and the review-checklist risks for the two do not overlap.

**What the split costs, stated rather than hidden.** `R6-PREFIX-KEY` ships a store whose largest
legal prefix is 32 tokens, which no real prompt reaches. Its qualification is therefore a mechanism
qualification and not a workload one, exactly as `R6-KV-PERSIST`'s was at `T <= 6`. The gate stays
unmet for one more capability. That is the price of not reviewing two failure domains in one diff,
and section 11 is written now — before this capability is implemented — so the successor is a
scheduled charter rather than a hope.

### 1.3 Why a design gate is triggered

Three of `CLAUDE.md`'s four triggers fire; the fourth is recorded as not fired, with its reason.

| Trigger | Fired | Why |
| --- | --- | --- |
| Public CLI or API surface | **Yes** | `--decode-step` gains a sixteenth operand and its arity set grows to `{5,6,7,9,10,11,12,13,14,15,16}`. `STORE` is the arm's second *conditional* operand and its first **mutually exclusive** one — it is illegal with either operand it replaces |
| Persisted or exchanged format | **Yes** | Two ways. (a) The `R6_DECODE_STEP` document goes to **schema 6**: a `store` object is added (2.7). (b) A **new persisted identity** is defined — not a new container format, but a **naming rule over the existing one**: a file's *name* now carries meaning, and a reader that computes the name differently from the writer produces a store that silently misses forever. `akvp` v1 is byte-unchanged (2.4) |
| Ownership / process / network boundary | **Yes** | The arm gains a **directory** it did not have. Until now every path operand named one file the caller chose; `STORE` names a namespace the arm populates under names the caller cannot predict. The arm becomes the store's only writer and its own reader across processes, and 2.8 states the single-writer rule that follows |
| Coordinated invariant across ≥ 3 modules | **Yes** | **This one fires where item 33's did not.** The key preimage must be formed identically by `src/kv_plane.align` (the arm's derivation), `scripts/kv_plane_reader.py` (the independent reader that checks a container is at its own name), and `scripts/run-layer-forward-smoke` (which recomputes it from the document's published digests). Three implementations of one byte layout, in three languages, is precisely the invariant a closure matrix exists for. Section 4 is built for it and 3.2's oracle D is its test |

### 1.4 Declared boundary

**In scope.** Dense Qwen2.5-Coder-7B Q4_K_M and OLMoE through the unchanged arms; **CPU only**; one
`STORE` directory supplied by the caller and already existing; one key per `(pack, geometry, TOKENS,
KV_WIDTH)`; one container per key; hit and miss; the suffix pass and the `N`-step loop unchanged;
both the streamed and the `RESIDENT=weights` legs; `T_prefix + S <= MAX_PREFILL_TOKENS` (**32**,
unchanged).

**Out of scope, declared non-goals.**

- **Any TTFT or throughput claim, and any cost ceiling.** Section 11. `CLAUDE.md`'s performance row
  is **not selected**. The runner's existing labelled TTFT *diagnostic* (item 33 section 2.10) is
  carried forward unchanged and gains a store leg, still labelled, still discharging nothing.
- **The `MAX_PREFILL_TOKENS` lift and the pinned corpus.** Section 11.
- **Inexact prefixes.** Unchanged from item 33 section 2.12: the key is over the **exact** token
  stream, `columns_persisted == token_count`, and longest-common-prefix lookup — which
  `docs/specs/align-llm.md` section 7.2 describes as the eventual semantics — is deferred (7). This
  capability is **deliberately narrower than 7.2**, and 2.3 records the field-by-field mapping so
  the narrowing is legible rather than accidental.
- **Eviction, tiering, invalidation beyond identity, generation counters, reuse policy, a size
  budget, garbage collection, or any store maintenance whatsoever.** The store grows without bound
  and the caller owns the directory. Section 7.
- **Concurrent writers.** The store is single-process (2.8). Two processes missing the same key
  concurrently is a refusal for the loser, not a merge.
- **Appending to a container, re-saving an extended plane, a quantized plane, the Metal arm, batch
  above one, a growing `KV_WIDTH`.** Unchanged non-goals.
- **Text.** Unchanged: the gate is on token ids, there is no tokenizer, and Align Request 22 stays
  `PROPOSED` and non-blocking (8).

### 1.5 What this leaves open

The R6 gate — 同一prefixを使う反復coding taskでTTFTが改善すること — is unmet. Of item 33 section
1.4's four reasons, **this capability discharges the first two** (there is now a key, and there is
now a store) and leaves the third and fourth: there is still no prefix-sharing **corpus**, and the
prefix-sharing **consumer** is still `scripts/run-decode-step`'s benchmark leg rather than
`align-coder`, which is roadmap R7 and does not exist. Section 11 discharges the third. The fourth
is R7's and is not a defect of this wave.

---

## 2. Public-contract ledger

Every surface below is exact. Fields marked `N/A` carry their reason.

### 2.1 The surface decision: `STORE`, and why the key is not an operand

Four alternatives were weighed.

| Consideration | `STORE` directory at `args[15]` (**chosen**) | A `KEY` operand the caller computes | Overload `KV_LOAD` to accept a directory | A separate `--decode-step-keyed` arm |
| --- | --- | --- | --- | --- |
| Who owns the key | **The arm.** One implementation, one preimage, one place to be wrong | The caller, in shell or Python. **Every caller re-implements the preimage**, and a caller that gets it wrong gets a silent permanent miss rather than a refusal — the worst failure shape a cache has | The arm | The arm |
| `akvp` v1 | **Byte-unchanged.** The container written on a miss is the container `KV_SAVE` writes today, at a name the arm chose | Unchanged | Unchanged | Unchanged |
| Meaning of an existing invocation | **Unchanged.** Every legal argv at fifteen operands means what it means today | Unchanged | **Changed.** `KV_LOAD` is a public operand whose value is a file; a value that is sometimes a directory is a new way for an old string to be interpreted, and `valid_path` cannot tell them apart at this pin (8) | Unchanged |
| Provenance legible in the argv | **Yes.** A directory in `STORE` and nothing in `KV_SAVE`/`KV_LOAD` says "let the arm decide" | Yes | **No** | Yes |
| Cost | One position; one `-` convention already inherited five times; one mutual-exclusion rule | One position, plus a documented preimage every consumer must implement | Zero positions, one ambiguity | Item 33 section 2.1's two grounds, unchanged: one loop and one prefill rather than two, plus the copy debt Request 49 forces |

The first row is the decision. **A content-addressed store whose address is computed outside it is
not a store**; it is a naming convention, and a naming convention with three implementations and no
oracle is what section 1.3's fourth trigger is about. `STORE` puts the preimage in one module,
publishes the resulting key in the document (2.7), and lets two independent implementations check it
(3.2).

**Why the key is nevertheless *published* rather than hidden.** `store.key` is in every document,
including error documents, so a caller can find, copy, archive, or delete the container the arm
chose without re-deriving anything. The arm owns the *derivation*; the caller owns the *file*.

### 2.2 The arm and its operands

| Field | Contract |
| --- | --- |
| Surface | `ggml-spike --decode-step` — unchanged; the first operand and nothing else selects the arm |
| Owner module | `src/decode_step.align`. `src/kv_plane.align` gains the key derivation and is **not** byte-unchanged (2.3, 4.2). `src/model_forward.align`, `src/layer_qwen2.align`, `src/layer_olmoe.align`, `src/ggml_spike.align`, `src/ggml_ffi.align`, and both shims are **byte-unchanged** |
| Operand grammar | `--decode-step PACK GEOMETRY TOKENS DOCUMENT REFERENCE TRANSCRIPT KV_WIDTH LOGITS STEPS KV_SAVE KV_LOAD RESIDENT SUFFIX STORE` |
| Arity | `args.len()` of 5, 6, 7, 9, 10, 11, 12, 13, 14, 15, or **16**. **8 is still refused** for R6's own reason. 17 and above are refused. `decode_step.align:4279`'s guard moves from `count > 15` to `count > 16` |
| How a wrong arity is reported | **No document and no error code**, unchanged: `run` returns `Err(Error.Invalid)`, the process exits non-zero, stdout is empty. `R6_ARITY` and `R6_PATH` remain prose names in comments (item 33 section 2.2) |
| `PACK` … `SUFFIX` | Unchanged from items 28, 29, 30, and 33 |
| `STORE` | `args[15]`. A **directory path**, subject to `layer_forward.valid_path` exactly as `KV_SAVE` and `KV_LOAD` are (`decode_step.align:4297,4300`), **or `-` for absent**. Absent is the default and is what every schema-5-era invocation means. A path failing `valid_path` is `Err(Error.Invalid)` with no document, identical to the two operands it sits beside |
| **Mutual exclusion** | **`STORE` non-`-` requires `KV_SAVE` and `KV_LOAD` both `-`.** Otherwise `R6_KV_ARGS`, detail `store[with_save]` or `store[with_load]`, decided in that order (2.6). This is a *third* plane provenance and it must not compete with the two explicit ones |
| **`SUFFIX` with `STORE`** | **Legal and is the point.** `SUFFIX`'s existing rule — non-`-` requires `KV_LOAD` non-`-` — is **widened** to "requires `KV_LOAD` **or** `STORE` non-`-`". Section 2.5 records this as the reversal of a recorded decision, with the reason |
| **`STORE` without `SUFFIX`** | **Legal.** It means "key the prefix itself": hit → load and run `N` steps; miss → prefill, save, run `N` steps. This is `R6-KV-PERSIST`'s own leg with automatic provenance and it is independently useful |
| Defaults | **None added.** `args.len() == 16` with `STORE` of `-` is exactly `args.len() == 15` |
| Its hazard, and how it is closed | A caller who expects reuse and mistypes the directory gets a miss, a prefill, and a saved container in a directory that does not exist — which fails (2.6, W5). More subtly, a caller who changes `KV_WIDTH` gets a permanent miss with no error. Closed the arm's way: `store.requested`, `store.key`, and `store.outcome` are published in **every** document, so "this run missed" is never silent |
| Environment | **None.** No environment fallback and no environment variable is read by the arm |
| **Prerequisite** | **Roadmap item 36 (`MF-SINGLE-TOKEN-LOGITS`).** Item 33's `T_prefix >= 2` refusal existed because a one-token prefill computed the wrong embedding row, and a store that *writes* containers must be correct at every `T_prefix` it accepts — a store that silently persists a wrong plane for `T_prefix = 1` would serve it forever. Item 36 lifts the defect and the refusal (item 33 section 11.5); this capability is stacked on it and **must not be merged before it** |

`STORE` is last for the reason `STEPS`, `RESIDENT`, and `SUFFIX` were: every earlier position is
spoken for, and moving one would change an existing invocation's meaning silently.

### 2.3 The key — preimage, derivation, and what each field rules out

**The tuple is not invented.** `r6-kv-persist.md` section 2.8 recorded it in advance, explicitly so
that a later capability would not: `(source_header_region_sha256, geometry_sha256,
token_stream_sha256, kv_width, plane_layout_version)`. This capability implements **that tuple** and
adds only fields that are already validated container identity, each with a reason below.

**The preimage — exactly 152 bytes, little-endian, one layout and no other.**

| Offset | Bytes | Type | Field | Source | What a difference rules out |
| --- | --- | --- | --- | --- | --- |
| 0 | 32 | `u8[32]` | `source_header_region_sha256` | the pack's source-identity record | A different model, transitively: alignpack 2.4.6's region is the magic, version, counts, **every metadata KV**, and every tensor-table entry |
| 32 | 32 | `u8[32]` | `geometry_sha256` | `crypto.sha256` of the exact `fs.read_file(GEOMETRY)` bytes | A different `R1_MODEL_IR` — rope base, eps, head counts, vocabulary |
| 64 | 32 | `u8[32]` | `token_stream_sha256` | `crypto.sha256` of `T_prefix` LE `u32` ids | A different prompt prefix |
| 96 | 8 | `u64` | `pack_total_bytes` | the pack header | The same GGUF packed differently or truncated |
| 104 | 4 | `u32` | `kv_width` | the `KV_WIDTH` operand | A plane of a different width — the byte image differs |
| 108 | 4 | `u32` | `token_count` | `T_prefix` | Redundant with the digest and included anyway (see below) |
| 112 | 4 | `u32` | `plane_layout_version` | `1` | A future transposed or quantized plane |
| 116 | 4 | `u32` | `element_type` | `0` = f32 | A future element type |
| 120 | 4 | `u32` | `format_version` | `1` | A future container format |
| 124 | 4 | `u32` | `key_version` | **`1`** | A future change to *this table* |
| 128 | 24 | `u8[24]` | `reserved` | all zero | — |

```text
key      = crypto.sha256(preimage)                    # 32 bytes
key_hex  = 64 lowercase hexadecimal characters
path     = STORE + "/" + key_hex + ".akvp"
```

**Four decisions in that table, recorded because a later reader will ask.**

1. **Why fields that the container would reject on anyway are in the key.** `pack_total_bytes`,
   `token_count`, `element_type`, and `format_version` are all checked by L1–L14 on load. Putting
   them in the key converts a **load-time refusal into a lookup miss**, which is what a store wants:
   a caller who repacked the model should get a clean re-prefill under a new name, not
   `R6_KV_IDENTITY("pack_total_bytes")` against a container that is simply for something else.
   `token_count` is redundant with `token_stream_sha256` and is included for the same reason
   `kv_plane` validates it separately — a length is cheaper to reason about than a digest.
2. **Why `key_version` exists.** If a later capability changes this table, every old container must
   become unreachable rather than mis-addressed. Bumping `key_version` retires the whole store
   atomically and costs four bytes. This is the field `format_version` cannot be, because the
   container format may not move when the key does.
3. **Why `crypto.sha256` and never `hash64`.** `r6-kv-persist.md` 2.3.3's rule, verbatim: the pinned
   runtime documents `core.hash`'s wyhash as "NOT cryptographic … not a stable on-disk/wire format".
   A file **name** is an on-disk format.
4. **Why the key is not the concatenated tuple itself.** A 152-byte name is legal on both targets but
   is not a name a human can compare, and a fixed 64-hex name gives every container the same length,
   which the reader (4.5) relies on to reject anything else in the directory as not-its-business.

**Mapping to `docs/specs/align-llm.md` section 7.2's `KVCacheKey`, field by field.** The narrowing
is deliberate and is recorded so it is legible rather than accidental.

| 7.2 field | This key | Disposition |
| --- | --- | --- |
| `model_id` | `source_header_region_sha256` + `pack_total_bytes` | **Covered, and more strongly.** A digest over every metadata KV and tensor-table entry identifies the model without trusting a name |
| `model_arch` | same | **Covered, transitively.** `general.architecture` is a metadata KV inside the digested region |
| `quant_type` | same | **Covered, transitively.** Per-tensor types are in the tensor table inside the digested region |
| `tokenizer_id` | **N/A — subsumed twice, and not readable at this pin** | The tokenizer's vocabulary and merges are metadata KVs inside `source_header_region_sha256`; and the operand is **token ids**, so a different tokenizer over the same text yields a different `token_stream_sha256`. Adding it as a scalar would require reading GGUF metadata the arm may not have — `REFERENCE` is optional and a load run may not have the GGUF at all (`r6-kv-persist.md` 2.4) |
| `prompt_template_version` | **N/A — subsumed, and outside this arm** | The arm consumes ids; whatever applied a chat template did so before the ids existed, so a template change moves `token_stream_sha256`. There is no template inside `--decode-step` to version |
| `prefix_token_hash` | `token_stream_sha256` | **Covered exactly** |
| `prefix_detector_version` | **N/A — there is no detector** | 7.2's key is for **longest-common-prefix** reuse, which needs a rule for *where* a prefix ends and a version for that rule. This capability is exact-prefix: the caller declares the split with `TOKENS` and `SUFFIX`, so there is nothing to detect and nothing to version. When prefix truncation lands (7), it adds this field and bumps `key_version` |
| — | `kv_width`, `plane_layout_version`, `element_type`, `format_version`, `key_version` | **Added.** 7.2 is an architectural sketch that predates the `akvp` container; these are the plane's actual byte-image parameters |

**The corpus digest is deliberately *not* in the key**, and the task that commissioned this design
proposed it, so the rejection is recorded rather than omitted. A corpus digest identifies *which
corpus a set of ids came from*. Two corpora that produce the same prefix ids **must** hit the same
container — that is what content addressing is. Putting provenance in an identity key would
partition a store by bookkeeping and silently halve its hit rate. The corpus digest belongs in the
corpus **manifest** and in the benchmark's own record (11.3), both of which this design places
there.

### 2.4 The store — layout, naming, and what it is not

| Field | Contract |
| --- | --- |
| The store is | **a directory the caller creates and owns.** The arm never creates it, never lists it, never deletes from it, and never writes anything but `<64-hex>.akvp` files into it |
| Why the arm does not create it | Two reasons, one principled and one measured. **Principled:** a directory is a namespace, and an arm that mints namespaces from a path operand is one typo from populating `/tmp/tyop/`. **Measured:** `std.fs` at pin `3a34febe` ships no directory creation (8, Request 53), so building one would mean a workaround, which `CLAUDE.md` forbids |
| Why the arm does not list it | Nothing needs listing. Lookup is `fs.exists(path)` on a name the arm computes. Listing is for **eviction and garbage collection**, which are declared non-goals (7) and are Request 53's resume condition |
| Container format | **`akvp` v1, byte-unchanged.** `src/kv_plane.align`'s writer and reader are unedited; only a new pure function is added beside them (4.2). A container written by `KV_SAVE` and a container written by a `STORE` miss are byte-identical given the same inputs, and 3.1 asserts it |
| File name | `<key_hex>.akvp`, 69 bytes. Lowercase hex; a name differing in case is a different file on a case-sensitive filesystem and the same file on a case-insensitive one, so the case is **fixed by the contract** and the reader asserts it (4.5) |
| Other files in the store | **Ignored, and not an error.** The arm addresses exactly one path and never enumerates, so a `README`, a lock file, or a container from a retired `key_version` is invisible to it. This is a property of not listing, and it is why not listing is a feature |
| Sharding | **None, and the reason is measured against a bound rather than assumed.** A flat directory is chosen because the store's realistic size is small: one container per `(model, geometry, prefix, width)`, and section 11's corpus has **one** prefix. A two-level `ab/cdef…` fan-out was considered and rejected as a format decision with no measured consumer; adding it later bumps `key_version` and is cheap. Recorded so it is not re-proposed as an oversight |
| Size on disk | One container is `plane_offset + n_layer * 2 * kv_width * n_head_kv * head_dim * 4`. On the reference model this is **29,970,432 B** at `KV_WIDTH` 256 and **470,372,352 B** at 4096 (`r6-kv-persist.md` 2.3.5, quoted). The store's total is that times the number of distinct keys, **unbounded**, and 6 risk 3 and 7 own it |

### 2.5 Lookup, hit, and miss — one document either way

The whole design turns on this table.

| | Hit | Miss |
| --- | --- | --- |
| Predicate | `fs.exists(path)` is **true** | `fs.exists(path)` is **false** |
| Plane filled by | `load_plane`, through L1–L14 unchanged | the prefill at `n_past = 0`, unchanged |
| Container | read | **written**, through the `KV_SAVE` writer at step 6a onward, unchanged |
| Then | the suffix pass at `(S, T_prefix)`, then `N` steps | the **same** suffix pass, then the **same** `N` steps |
| `kv.destination` / `kv.verdict` | as `KV_LOAD` reports today | as `KV_SAVE` reports today |
| `store.outcome` | `"hit"` | `"miss"` |
| Elapsed | one container read | one `T_prefix`-column prefill plus one container write |

**A miss is only a missing file.** This is the load-bearing rule and it preserves
`r6-kv-persist.md` 2.4's invalidation rule character for character: *every mismatch is a refusal,
never a silent re-prefill.* If a file **exists** at the key path, it is loaded and **every** L1–L14
check applies; any failure is that check's refusal — `R6_KV_MAGIC`, `R6_KV_VERSION`, `R6_KV_HEADER`,
`R6_KV_REGION`, `R6_KV_RESERVED`, `R6_KV_TRUNCATED`, `R6_KV_SIZE_MISMATCH`, `R6_KV_TOO_LARGE`,
`R6_KV_IDENTITY`, `R6_KV_DIGEST`, `R6_KV_TOKENS`, `R6_KV_GEOMETRY`, `R6_KV_NPAST`,
`R6_KV_WIDTH_MISMATCH`, `R6_KV_UNREADABLE` — and **not** a miss.

Three cases make that concrete, and 5.2 asserts all three:

- **A torn or truncated container** at the key path is `R6_KV_DIGEST("plane")` or
  `R6_KV_TRUNCATED`. It is **not** re-prefilled over. A capability that silently replaced a corrupt
  artifact would be unable to tell corruption from a bug in its own writer.
- **A key collision with different tokens** — a container at the key path whose token stream is not
  `TOKENS` — is `R6_KV_TOKENS`. Reaching it requires a SHA-256 collision or a hand-placed file; the
  check costs nothing and the refusal names the truth.
- **A container from a different model at the key path** is `R6_KV_IDENTITY("pack")`. Same reasoning.

**The reversal this capability makes, and its reason.** Item 33 section 2.3 refused `SUFFIX` without
`KV_LOAD` and recorded why: *"it has no consumer: a caller holding both lists in one process should
concatenate them and run one prefill … Building a second path with no consumer doubles the closure
matrix."* **The consumer now exists.** A keyed miss must prefill `TOKENS`, save it, and then run the
suffix — because if a miss instead prefilled `TOKENS ++ SUFFIX` in one pass, it would have no
`T_prefix`-column plane to persist, and the store would never fill. The reversal is narrow and is
kept narrow:

- The refusal `R6_KV_ARGS store[…]`/`suffix[no_load]` still forbids the *caller* from expressing
  "prefill then suffix" directly. `SUFFIX` without `KV_LOAD` **and** without `STORE` is unchanged.
- The path is reached only by the arm, only on a miss, and the caller cannot select it — provenance
  is decided by the lookup, not by an operand.
- It is therefore not "a second way to reach `n_past > 0`" in the sense item 33 rejected; it is the
  existing prefill followed by the existing suffix pass, and 3.1's oracle proves the resulting plane
  is the same one a hit produces.

### 2.6 Validation order and refusal codes

Items 28, 29, 30, and 33's steps keep their order and their codes. This capability inserts **step
2d** and **step L0**, and adds one detail to an existing code. **No new refusal code is minted**,
which 10 finding 2 records as a result rather than a goal.

| Step | Condition | Code | Detail |
| --- | --- | --- | --- |
| 2b | `KV_SAVE` and `KV_LOAD` both non-`-` | `R6_KV_ARGS` | `kv[save+load]` (unchanged) |
| 2c | `SUFFIX` non-`-` with **neither** `KV_LOAD` **nor** `STORE` | `R6_KV_ARGS` | `suffix[no_load]` (**widened**, 2.5) |
| **2d** (new) | `STORE` non-`-` with `KV_SAVE` non-`-` | `R6_KV_ARGS` | `store[with_save]` |
| **2d** (new) | `STORE` non-`-` with `KV_LOAD` non-`-` | `R6_KV_ARGS` | `store[with_load]` |
| 3 | `TOKENS` parses, `1 <= T <= MAX_PREFILL_TOKENS` | `R6_TOKENS` | `count[<n>]` (unchanged) |
| 3c | `SUFFIX` grammar, vocabulary, sequence cap `T + S <= 32` | `R6_SUFFIX` | (unchanged) |
| 6 | `T + S + N <= KV_WIDTH` | `R6_KV_WIDTH` | `kv_width[<n>]` (unchanged) |
| 6a | the three `MAX_KV_*` bounds, before any prefill | `R6_KV_TOO_LARGE` | (unchanged) |
| **L0** (new) | **the key is derived and `fs.exists(path)` is tested.** This is not a refusal — it selects the branch | — | — |
| L1–L14 | on a **hit**, unchanged and complete | every existing load-path code | unchanged |
| W1–W4 | on a **miss**, unchanged and complete | `R6_KV_EXISTS`, `R6_KV_UNWRITABLE`, `R6_KV_WRITE_FAILED`, `R6_KV_CLEANUP_FAILED` | unchanged |
| **W5** (new detail) | on a miss, the create fails because `STORE` does not exist, is not a directory, or is not writable | `R6_KV_UNWRITABLE` | **`store[create]`** |

**Ordering is total, and three orderings carry cases of their own** because they are the ones a
reader would guess wrong:

- **2d precedes every path-content check, every numeric parse, and L0.** A run whose provenance
  operands conflict is refused before a directory is touched and before a key is derived.
  `ds-store-with-save-bad-steps` asserts it.
- **L0 follows step 6a.** The key is derived only after `KV_WIDTH` is parsed and bounded, because
  `kv_width` is *in the preimage* — deriving it earlier would key on an unvalidated number.
  `ds-store-narrow-width` asserts that `R6_KV_WIDTH` precedes any store activity.
- **On a miss, W5 is reached only after the prefill.** A caller with an unwritable store pays a full
  prefill before learning it. **This is a deliberate cost and not an oversight:** the alternative is
  a pre-flight probe write, which at this pin means creating and deleting a file in the caller's
  directory on **every** run including hits, and `r6-kv-persist.md` 2.5's reasoning — a caller who
  asks for an unpersistable configuration should learn it in milliseconds — cannot be honoured
  without a directory-type predicate `std.fs` does not ship (8, Request 53). **This is Request 53's
  strongest client evidence** and 6 risk 5 owns the consequence.

**One code, three causes, and the arm cannot separate them.** `R6_KV_UNWRITABLE store[create]`
covers "the directory does not exist", "the path is a regular file", and "the directory is not
writable", because `fs.create_exclusive`'s failure at this pin does not distinguish them. The detail
names the *operand* rather than guessing the *cause*, which is the same discipline
`R6_KV_IDENTITY`'s four details follow. Recorded as a limitation with its request rather than
papered over.

### 2.7 The document — `R6_DECODE_STEP`, schema 6

`document_schema_version` goes to **6**. One object is added and no existing field changes meaning.

```json
"store": {
  "requested": 0,
  "key": "-",
  "outcome": "absent",
  "saved": 0,
  "container_bytes": 0,
  "lookup_ns": 0
}
```

| Field | Type | Contract |
| --- | --- | --- |
| `requested` | `0`/`1` | `STORE` was non-`-`. Published in **every** document including error documents, so a store run is never implicit |
| `key` | 64 hex, or `"-"` | The derived key. `"-"` when not requested **or when the run was refused before L0** — which is itself information: it says the refusal preceded key derivation |
| `outcome` | `"absent"` \| `"hit"` \| `"miss"` | `"absent"` when not requested or refused before L0 |
| `saved` | `0`/`1` | `1` only after a **complete** container write on a miss. A miss whose write failed reports `0` and the run is already refused |
| `container_bytes` | integer | The container's `total_bytes`: read on a hit, written on a miss, `0` otherwise. Equal to `kv.total_bytes`, restated here so the store object is readable alone |
| `lookup_ns` | integer | The `fs.exists` call alone. A **diagnostic**, and 2.9 records that no claim is derived from it |

**No path is published, and that is a decision.** `kv` publishes no path today and the goldens
depend on it: a document carrying `/Users/hiro/…` or a `mktemp -d` name would be machine-specific
and could not be pinned. The **key** is machine-independent — it is a digest of the pack's identity
record, the geometry's bytes, and the ids — so `store.key` is golden-stable on the hosted fixture
and on the real model alike. A caller that wants the path forms `STORE + "/" + key + ".akvp"`.

**The key is recomputable from the document alone**, because `kv` already publishes
`source_header_region_sha256`, `geometry_sha256`, `tokens_sha256`, `pack_total_bytes`,
`token_count`, `plane_layout_version`, and `format_version` (`decode_step.align:3839-3868`), and
`selection` publishes `KV_WIDTH`. This is not a coincidence to rely on but a **contract** this
document adds: 3.2's oracle D checks exactly it, and 4.8 makes the smoke recompute the key from the
document's own bytes.

### 2.8 Ownership, allocation, and cleanup

| Field | Contract |
| --- | --- |
| Key derivation | `kv_plane.derive_key(source: bytes, geometry: bytes, tokens: bytes, kv_width, token_count) -> string`. **A pure function**: it allocates one 152-byte preimage buffer and one 64-byte hex string, takes no `borrow mut`, opens nothing, and is therefore unaffected by Request 49 — which is why it belongs in `kv_plane` (the module that owns container identity) rather than in `decode_step` (4.2) |
| Preimage buffer | `buffer(152)`, freed at the function's scope end on every path |
| The three digests it consumes | **Already computed** by the existing paths: `source_header_region_sha256` by the pack open, `geometry_sha256` and `token_stream_sha256` by `r6-kv-persist.md` 2.6's steps. Key derivation adds **no new I/O and no new digest of a large region** — so Request 29 (incremental `sha256`) gains no new client here |
| Path string | Formed once, held for the run, freed at `execute`'s scope end |
| The container on a miss | Written by the unchanged `KV_SAVE` writer, which already owns `R6_KV_EXISTS`, the cleanup of a partial file (`R6_KV_CLEANUP_FAILED`), and the padding rules |
| **Single writer** | **The store is single-process, declared.** Two processes missing the same key concurrently both prefill; the second `fs.create_exclusive` fails and that run is refused with `R6_KV_EXISTS`. **The loser is not silently down-graded to a no-save run**, because a capability that silently substitutes a different outcome for the one it was asked for is the thing `r6-kv-persist.md` 2.4 forbids. Multi-process stores need a rename-based publication (`fs.rename_no_replace`, Request 14's shape) and are deferred (7) |
| Freed by | Align, at scope end, on every path. Unchanged |

### 2.9 Metrics

| Metric | Kind | Contract |
| --- | --- | --- |
| `store.outcome` | **primary, exact** | A hit or a miss. Exact, reproducible, and the only thing 3.1 asserts on |
| `store.container_bytes` | exact | A counter, not a clock |
| `store.lookup_ns`, `timings.first_token_ns`, the runner's wall clock | **diagnostic, labelled** | Carried forward from item 33 section 2.10 unchanged. **No per-token, per-second, speedup, or ppm figure is derived from any of them by this capability**, no acceptance decision is taken from them, and no roadmap gate is discharged by them. Section 11 is where they become a claim |

### 2.10 Prerequisites

| Prerequisite | State |
| --- | --- |
| Roadmap item 36, `MF-SINGLE-TOKEN-LOGITS` | **Required** (2.2). Stacked on it at `40eb965` |
| Roadmap items 29, 30, 33 | Merged (`main` at `45ff38e`) |
| An Align capability | **None.** No request is consumed and none blocks (8) |
| A new ggml op, FFI symbol, shim change, node row, slot, or op code | **None.** The graph is untouched |
| Host capacity | The existing qualification's, unchanged: `scripts/run-decode-step` refuses the resident leg below 12 GiB, plus ~30 MB per stored container |

### 2.11 Exact-prefix only

Unchanged from item 33 section 2.12 and restated because the key makes it newly tempting: RoPE
positions are absolute, so a container for `a,b,c` cannot serve prefix `a,b`. The key is over the
**whole** `TOKENS` stream, `columns_persisted == token_count` holds, and there is no truncation, no
longest-common-prefix search, and no partial hit. Section 7 defers it and 2.3 records the
`prefix_detector_version` field it will need.

---

## 3. Oracles and the acceptance rule

### 3.1 Oracle K — a hit and a miss are the same run

**The acceptance rule of this capability.** Against a fresh, empty store:

1. Run once. `store.outcome` is `"miss"`, `store.saved` is `1`, a container appears at
   `<STORE>/<key>.akvp`.
2. Run again, identical argv. `store.outcome` is `"hit"`, `store.saved` is `0`.
3. **The two documents are byte-identical after `normalize`**, outside exactly this exclusion list:

```text
store.outcome        miss -> hit
store.saved          1 -> 0
store.lookup_ns      a clock
kv.save_requested / kv.load_requested / kv.verdict / kv.destination
timings.*            clocks
pack.reader_*        the counters item 30 already excludes
```

Everything else — the logits, the decoded ids, `plane.columns_written`, `suffix.*`, the argmax,
every digest, `store.key`, `store.container_bytes` — is equal byte for byte.

**Why this is the right rule.** It is the strongest statement a store can make: *using the cache
changes nothing but the cost.* It catches a key that varies between runs, a container written with
the wrong columns, a suffix pass that behaves differently on a loaded plane than a prefilled one,
and a document that leaks a path or a clock into a field that should be stable. It subsumes the
weaker "the container round-trips", which oracle Q already covers.

**And a third run proves the container is the one `KV_SAVE` would have written.** Run the same
prompt with `KV_SAVE` to a caller-named path; the two files are **byte-identical**. That is what
makes "the `akvp` format is byte-unchanged" (2.4) a verified statement rather than a claim about the
diff.

### 3.2 Oracle D — the key is a function of the published digests, computed three ways

Section 1.3's fourth trigger is that one byte layout has three implementations. Oracle D is its test.

| Implementation | What it computes | Checked against |
| --- | --- | --- |
| `src/kv_plane.align` `derive_key` | the arm's key, published as `store.key` | — |
| `scripts/kv_plane_reader.py` | the key from the **container's own header and identity record**, independently, and asserts the file it was handed is **named** for it | the file name |
| `scripts/run-layer-forward-smoke` | the key from the **document's** published digests and scalars (2.7) | `store.key` |

Three agreements are asserted: arm ≡ document-derived, arm ≡ file name, and reader ≡ file name. A
preimage that drifts in any one of the three is caught by two of the three.

**Plus four determinism rows**, asserted on the hosted fixture, each changing exactly one preimage
field and requiring a **different** key: one token id changed; `KV_WIDTH` changed; the geometry file
changed by one byte; the pack's source record changed. And one row requiring the **same** key across
two processes with different working directories, different `STORE` paths, and a different
`DOCUMENT` path — because none of those is in the preimage.

### 3.3 Inherited oracles

All unchanged, all re-run on the store legs:

- **Oracle S** (item 33 3.2) — the keyed run is byte-equal to a single-shot prefill of
  `TOKENS ++ SUFFIX`, outside its own exclusion list. Run on **both** the hit and the miss leg,
  which is what ties the store to arithmetic rather than to itself.
- **Oracle C″** (item 33 3.3) — `--model-forward` at `TOKENS,SUFFIX` is the single-shot
  self-reference. Unchanged, and the reason the sequence cap is on `T + S`.
- **Oracle B** (item 33 3.4) — the plane round trip over `T_prefix + S` columns, inside the suffix
  pass and before the first decode step.
- **Oracle Q** (item 29 3) — `scripts/kv_plane_reader.py` independently validates the container the
  store wrote, now also checking its name (3.2).
- **Oracle A′, gate G, oracle R, oracle P** — unchanged.

### 3.4 No transcript oracle above six tokens, and it is recorded rather than worked around

`--model-forward` and `--layer-forward` refuse a prefill above six tokens **with** a transcript
oracle, as `R5_ORACLE_TRUNCATED`, detail `tokens[<n>]` (`model_forward.align:3103`,
`layer_forward.align:1603`). The tolerance oracle is therefore unavailable at any `T_prefix` this
capability's own qualification cares about, and it will be unavailable at 370 tokens for section 11.

**This is recorded, not fixed and not routed around.** Shrinking the prefix to six tokens to keep
the transcript oracle would make the measurement a number about the shrinking. The oracles that
remain — S, C″, B, Q, K, D, and the `llama-debug` logits blob (gate G1) — are byte-equality oracles
and are strictly stronger than a tolerance comparison; what is lost is the *node-by-node* view of
where a divergence began, which is a debugging affordance rather than an acceptance rule. Section 6
risk 6 owns the consequence.

### 3.5 The shipped acceptance rule

A candidate is acceptable when, at one head, on one host, in one session:

1. `gmake layer-forward-smoke` passes, including the new store block (5.1) and refusal matrix (5.2);
2. Oracle K holds on the hosted fixture **and** on the real model;
3. Oracle D's three agreements and five determinism rows hold;
4. Oracles S, C″, B, Q, A′, R, and gate G hold on both the hit and the miss leg;
5. `gmake decode-step-qualification` passes with the store leg added, on both the streamed and the
   resident legs;
6. The refusal matrix is complete: every row in 2.6 has a case that reaches it;
7. `gmake build`, `gmake check`, `gmake fmt`, `gmake format-check`, `gmake ggml-spike-smoke`,
   `gmake gate-topology-check`, `git diff --check`.

**No timing figure appears in the acceptance rule**, because this capability makes no performance
claim (1.4).

---

## 4. Closure matrix

Construction, success, failure, malformed input, early exit, cleanup, and each affected module.

### 4.1 `src/decode_step.align` — the operand, the branch, and the document

| Cell | Implementation | Regression |
| --- | --- | --- |
| Construction | `STORE` parsed at `args[15]`; arity guard `count > 16`; `valid_path` guard beside `KV_SAVE`/`KV_LOAD` | `ds-arity-16` (`NO_DOCUMENT`), `ds-arity-17`, `ds-store-path-empty` |
| Malformed input | 2.6's step 2d, both details, in order | `ds-store-with-save`, `ds-store-with-load` |
| Malformed input | step 2c widened for `SUFFIX` + `STORE` | `ds-suffix-no-load-no-store` (still refused), `ds-store-suffix` (accepted) |
| Success — hit | L0 true → the unchanged load path → suffix pass → loop | `ds-store-hit`, `ds-store-hit-suffix` |
| Success — miss | L0 false → the unchanged prefill → the unchanged writer → suffix pass → loop | `ds-store-miss`, `ds-store-miss-suffix` |
| Failure | a file at the key path failing any of L1–L14 is that code's refusal, **never** a miss | `ds-store-hit-corrupt-plane`, `ds-store-hit-wrong-tokens`, `ds-store-hit-wrong-pack` |
| Failure | a miss whose create fails: `R6_KV_UNWRITABLE store[create]` | `ds-store-unwritable` |
| Failure | a miss whose key path already exists between `fs.exists` and the create: `R6_KV_EXISTS` | 5.2 records this as **not directly reachable** by a single-process case and covered by inspection plus the existing `ds-kv-save-exists` |
| Early exit | every refusal before L0 publishes `store.requested`, `key: "-"`, `outcome: "absent"` | `ds-store-narrow-width`, `ds-store-with-save-bad-steps` |
| Cleanup | the plane, the arena, the preimage buffer, the path string, freed at scope end on every path | the existing balance invariant (oracle B, item 30 4.3) |
| Document | schema 6, `render_store`, published in **every** document | every row above; the whole corpus re-baselined for the schema field |

### 4.2 `src/kv_plane.align` — the key, and why it lives here

| Cell | Implementation | Regression |
| --- | --- | --- |
| Construction | `derive_key`, a pure function over five already-computed values (2.8) | `ds-store-*` via `store.key`; oracle D's determinism rows |
| Success | one 152-byte preimage, `crypto.sha256`, 64 lowercase hex | oracle D |
| Malformed input | **N/A — none reachable.** Every input is a fixed-width value the caller cannot shape: three 32-byte digests the arm computed and two integers validated at steps 3 and 6 | recorded, not tested |
| Cleanup | the preimage buffer, freed at scope end | oracle B |
| **Why here and not `decode_step`** | This module owns container identity — the six fields, the digests, the layout. The key is the seventh statement of that identity, and putting it anywhere else would let the two drift. **Request 49 does not apply**: `derive_key` takes no `borrow mut`, which is why the boundary that Request 49 forced for the refill (item 29 2.7) does not bind here | 10 finding 3 |
| **Not changed** | the writer, the reader, the header plan, every bound, `MAX_KV_*` | asserted by oracle K step 3: a `STORE` container and a `KV_SAVE` container are byte-identical |

### 4.3 `src/model_forward.align` — byte-unchanged

Nothing in the graph, the staging reservation, or the embedding builder moves. `MAX_PREFILL_TOKENS`
is not touched (1.2). Cell recorded because section 11 changes exactly this file.

### 4.4 `src/layer_qwen2.align`, `src/layer_olmoe.align` — byte-unchanged

`MAX_PREFILL_TOKENS` stays 32 in both. Recorded for the same reason.

### 4.5 `scripts/kv_plane_reader.py` — the independent reader learns the name

| Cell | Implementation | Regression |
| --- | --- | --- |
| Construction | a second implementation of 2.3's 152-byte preimage, in Python, from the container's **own** header and identity record | oracle D |
| Success | when handed a path whose basename is 64 hex plus `.akvp`, it asserts the name equals the derived key | `ds-store-*` reader-parity rows |
| Failure | a name/key disagreement is a new reader verdict, `KEY`, in the shape its existing coarse verdicts have | a hand-built case: a valid container renamed |
| Malformed input | a basename that is not 64-hex-plus-`.akvp` — the reader reports `KEY` only when asked to check the name, and validates the container regardless, because it must stay usable on a `KV_SAVE` artifact | the existing `KV_SAVE` reader cases, unchanged |
| **Why the reader and not only the smoke** | `r6-kv-persist.md` 5.2.1's rule: an arm and an independent reader that disagree are a format with two meanings. A **name** is now part of the format's meaning | 5.2.1's parity table gains one row |

### 4.6 `src/ggml_spike.align`, `src/ggml_ffi.align`, both shims — byte-unchanged

The dispatch arm forwards `args` and does not enumerate arity (`ggml_spike.align:1610`, quoted from
item 33). No FFI symbol, op code, or shim function is added.

### 4.7 `scripts/layer_forward_fixture.py` — unchanged

No new reference activation is needed: the store's hosted cases reuse item 33's synthetic
prefix/suffix pair. **This is the golden hazard's mitigation and it is stated as one** (5.3).

### 4.8 `scripts/run-layer-forward-smoke` — the hosted owner

| Cell | Implementation | Regression |
| --- | --- | --- |
| Construction | a **sixth block**: a temporary store directory per case, removed after | the block's own teardown |
| Success | oracle K's three runs; oracle D's three agreements and five determinism rows | 5.1 |
| Failure | 2.6's refusal matrix, every row | 5.2 |
| Cleanup | the store directory and every container removed; the block asserts the directory is empty of `.akvp` files before it removes it | the block's own teardown |
| **Key recomputation** | the block recomputes the key from the **document's** published digests (2.7) in Python and compares to `store.key` | oracle D |

### 4.9 `scripts/run-decode-step` — the real-model qualification

| Cell | Implementation | Regression |
| --- | --- | --- |
| Construction | a store directory under the existing `work_dir`, created with `mkdir -p` as the persist root already is (`:269`) | — |
| Success | for prompt 1, split at `j` as item 33's suffix leg already does: run twice against a fresh store and assert oracle K; then assert the container is byte-identical to a `KV_SAVE` of the same prefix | the qualification's own assertions |
| Diagnostic | the TTFT trio gains a fourth leg — the keyed hit — still labelled, still deriving no figure | 2.9 |
| **Cost** | **two extra `--decode-step` invocations per leg**, at `N = 1`. At item 30's measured `N = 1` elapsed (5.0–6.8 s per invocation) this is **under 30 s** added to a qualification whose cap is 1800 s and whose interleaved run took 827 s | 6 risk 7 |

### 4.10 Cells with no counterpart, named

| Cell | Why there is none |
| --- | --- |
| `decode_step` × "malformed key" | The key is derived, never parsed. There is no input that can malform it (4.2) |
| `kv_plane` × "the store is full / quota exceeded" | Presents as a failed create and is `R6_KV_UNWRITABLE store[create]`, indistinguishable from the other three causes at this pin (2.6). Request 53 |
| Any module × "concurrent miss" | Declared out of scope (2.8). Not reachable from a single-process case and not simulated |
| `model_forward`, `layer_qwen2`, `layer_olmoe`, `ggml_*` × every cell | Byte-unchanged (4.3, 4.4, 4.6) |

---

## 5. Verification plan

### 5.1 The hosted owner — what the sixth block gains

`gmake layer-forward-smoke`, synthetic geometry, no real model, no ggml (stub shim). Item 33's
synthetic prefix/suffix pair, `T_prefix = 2`, `S = 1`, `KV_WIDTH = 8`, `n_layer = 2`, `n_head_kv =
1`, `head_dim = 4`, `n_vocab = 32` — the configuration `r6-kv-persist.md` 2.3.5 measures at a
4,608-byte container.

| Row | Asserts |
| --- | --- |
| `ds-store-miss` | first run: `outcome: "miss"`, `saved: 1`, a container exists at the key path |
| `ds-store-hit` | second run: `outcome: "hit"`, `saved: 0` |
| `ds-store-oracle-k` | the two documents equal outside 3.1's exclusion list |
| `ds-store-vs-kv-save` | the container is byte-identical to a `KV_SAVE` of the same prefix |
| `ds-store-suffix` | `STORE` + `SUFFIX`, hit and miss, both equal to item 33's `ds-suffix-*` comparand |
| `ds-store-no-suffix` | `STORE` alone: hit and miss both equal `ds-kv-load-*` / `ds-kv-save-*` |
| `ds-store-key-document` | the key recomputed from the document equals `store.key` |
| `ds-store-key-name` | the reader's key equals the file name |
| `ds-store-key-tokens`, `-width`, `-geometry`, `-pack` | one field changed → a different key |
| `ds-store-key-stable` | different cwd, `STORE`, and `DOCUMENT` → the same key |
| `ds-store-resident` | `RESIDENT=weights` with `STORE`: oracle K and oracle R both hold |

### 5.2 The refusal matrix

Every row of 2.6, each asserting code, detail, and that the document carries `store.requested` with
the right `key`/`outcome`:

`ds-store-with-save`, `ds-store-with-load`, `ds-store-with-save-bad-steps` (2d precedes the numeric
parse), `ds-store-narrow-width` (`R6_KV_WIDTH` precedes L0, `key: "-"`), `ds-store-unwritable`
(`R6_KV_UNWRITABLE store[create]` against a directory that does not exist), `ds-store-file-not-dir`
(same code, same detail, against a regular file — asserting the three causes are **not**
distinguished), `ds-store-hit-corrupt-plane` (`R6_KV_DIGEST("plane")`, **not** a miss),
`ds-store-hit-wrong-tokens` (`R6_KV_TOKENS`), `ds-store-hit-wrong-pack`
(`R6_KV_IDENTITY("pack")`), `ds-suffix-no-load-no-store` (`R6_KV_ARGS suffix[no_load]`, unchanged),
`ds-arity-16`, `ds-arity-17` (both `NO_DOCUMENT`), `ds-store-path-empty` (`NO_DOCUMENT`).

The three "hit-but-broken" rows are built by writing a good container, then corrupting it **in
place** at its key path — which is the only way to reach them, and is exactly the point: the key
addresses a file that may be anything.

### 5.3 Predicted golden movement, and the cross-platform hazard

**Predicted.** The `document_schema_version` field moves 5 → 6 in **every** document row of the
decode-step corpus, and every row gains a `store` object at its default. That is a whole-corpus
re-baseline of a mechanical kind, and it must be verified mechanically — a diff in which any row
changes in **any other field** is a failure, and 12 (at implementation time) records the check.
About 24 new rows are added by 5.1 and 5.2.

**The cross-platform golden hazard, and why this capability does not touch it.** Pinned goldens must
never carry activation bytes from a prefill of four or more tokens, because floating-point
association order differs across hosts; hosted cases stay synthetic and short and the real model is
**qualification-only**. This capability:

- adds **no** new activation bytes to any golden — 4.7 is unchanged and the store rows reuse item
  33's existing synthetic pair at `T_prefix = 2`, `S = 1`;
- adds a golden surface that is **digests and integers only** — `store.key` is a SHA-256 over exact
  bytes and `store.container_bytes` is a count, and neither has a floating-point input.

**The store's golden surface is therefore platform-independent by construction**, which is a
property worth stating because section 11's lift does not have it and must earn it differently.

### 5.4 The real-model qualification

`gmake decode-step-qualification`, opt-in, real ggml, real model, real instrument, on the reference
host. Prompt 1 (`def add(a, b):`, `T = 6`), split at `j = 3`. Both the streamed and the resident
legs. Asserts oracle K, `ds-store-vs-kv-save`'s byte equality, oracle S on both the hit and the miss
leg, and the reader's name check. Adds under 30 s (4.9).

### 5.5 Commands

```sh
export LIBRARY_PATH=/opt/homebrew/lib:/opt/homebrew/opt/openssl@3/lib:/opt/homebrew/opt/zstd/lib
export ALIGN_LLM_GGML_INCLUDE=/opt/homebrew/include ALIGN_LLM_GGML_LIB=/opt/homebrew/lib
export ALIGN_LLM_GGUF_MODEL="$HOME/models/qwen2.5-coder-7b-instruct-q4_k_m.gguf"
export ALIGN_LLM_LLAMA_DEBUG=/opt/homebrew/bin/llama-debug
export ALIGN_LLM_LLAMA_EVAL_CALLBACK="$(scripts/llama-eval-callback-toolchain ensure instrument)"
gmake build && gmake check && gmake fmt && gmake format-check
gmake layer-forward-smoke          # the owner
gmake ggml-spike-smoke
gmake gate-topology-check
gmake decode-step-qualification    # focused, real model, both legs
git diff --check
python3 scripts/pre-pr --owner-test layer-forward-smoke -- gmake layer-forward-smoke
```

`gmake ci` is **not** selected: this capability changes no aggregate membership, no check topology,
and no integration behaviour.

---

## 6. Risks

| # | Risk | Disposition |
| --- | --- | --- |
| 1 | **The three preimage implementations drift.** The classic content-addressing failure: the writer names a file one way, a later reader computes another, and the store misses forever with no error | Oracle D's three-way agreement (3.2), plus the reader's name check being part of oracle Q. Two of three catch any single drift. **This is the risk section 1.3's fourth trigger names** |
| 2 | **A silent permanent miss from a field the caller changed innocently.** Changing `KV_WIDTH` from 256 to 512 retires every container, correctly and invisibly | `store.outcome` is in every document and the runner prints it. Accepted: a miss is correct here, and the alternative — a key that ignores `kv_width` — would load a plane of the wrong byte image |
| 3 | **The store grows without bound.** No eviction, no GC, no size budget (1.4). One container is 30 MB at `KV_WIDTH` 256 and 470 MB at 4096 | Accepted and declared. The store is a caller-owned directory; the caller deletes it. Section 7 defers eviction and Request 53 is its prerequisite. **The runner's store lives under `work_dir` and is removed with it** |
| 4 | **A miss writes a container for a plane that is wrong.** If the prefill were incorrect, the store would persist the error and serve it forever — worse than recomputing it | This is why item 36 is a hard prerequisite (2.2). Beyond it: oracle S on the **miss** leg compares the run against a single-shot, and oracle Q validates the container independently. A wrong plane fails both before it is reused |
| 5 | **A caller with an unwritable store pays a full prefill before learning it** (2.6) | Accepted, with its cause named as Request 53. Bounded: it is one prefill, the refusal is exact, and a pre-flight probe write would cost every run including hits |
| 6 | **No transcript oracle above six tokens** (3.4) | Accepted and recorded. Byte-equality oracles remain; what is lost is node-level divergence localisation |
| 7 | **Qualification cost creep.** Item 30's qualification already runs 827 s against an 1800 s cap | Measured, not assumed: 4.9 bounds the addition at under 30 s. If the measured addition exceeds 120 s, the store leg moves to prompt 1 only and the fact is recorded |
| 8 | **Schema 6 re-baselines the whole corpus** (5.3), and a mechanical re-baseline is where an unrelated change hides | Verified mechanically rather than by eye: every row must differ **only** in `document_schema_version` and the added `store` object |
| 9 | **`fs.exists` is a TOCTOU window.** Between the lookup and the create, another process may write the file | Declared single-process (2.8). The window is closed correctly rather than ignored: `fs.create_exclusive` fails and the run is **refused**, never silently down-graded |

---

## 7. Deferred and declared limitations

| Deferred | Reason, and what it will need |
| --- | --- |
| **Longest-common-prefix lookup and prefix truncation** | `align-llm.md` 7.2's eventual semantics. Needs `columns_persisted != token_count`, which the `akvp` v1 identity checks forbid today (item 33 2.12), and `prefix_detector_version` in the key (2.3), and therefore `key_version` 2 |
| **Eviction, garbage collection, a size budget, a reuse policy, a generation counter** | Needs directory listing (Request 53) and a measured policy. `r3-residency-sim.md` 8.3's negative result is the standing warning that an eviction rule needs its own gate and its own hit-rate metric, not an assumption |
| **DRAM and NVMe tiering** | R6 gate lines 3 and 4. Nothing here forecloses them; the store is a flat directory of complete containers |
| **Invalidation beyond identity** | Every mismatch is a refusal (2.5). Time-based, generation-based, and content-watch invalidation are not designed |
| **Multi-process stores** | Needs rename-based publication (`fs.rename_no_replace`, Request 14's shape) and a temp-file convention |
| **Appending to a container; re-saving an extended plane** | `r6-kv-persist.md` 7, unchanged |
| **The `MAX_PREFILL_TOKENS` lift, the pinned corpus, and the TTFT claim** | Section 11 |
| **Directory sharding** | 2.4, with its reason |

---

## 8. Align capability requests

Classified per `CLAUDE.md`. **None blocks this capability. One new request is proposed.**

| Gap | Classification | Status |
| --- | --- | --- |
| **No directory creation, no directory listing, and no file-type predicate in `std.fs`** | **Genuine Align gap, not yet recorded** | **Request 53, `PROPOSED`, `medium`, non-blocking.** Proposed below |
| No read-only random-access open (`fs.open_ro`), no `fs.size` | Genuine Align gap, recorded | **Request 21, `PROPOSED`.** Inherited through the container path, which this capability does not touch. No new client shape |
| No exclusive random-access create | Genuine Align gap, recorded | **Request 30, `PROPOSED`.** Third client. The store's miss path is the documented check-then-create, and **no workaround is built**; 6 risk 9 records the window it leaves and closes it as a refusal |
| No `fsync`/`F_FULLFSYNC` | Genuine Align gap, recorded | **Request 31, `PROPOSED`, stays non-blocking.** A store makes its *first* correction owed: item 29 argued 31 stays low priority because a torn container costs one re-prefill. With a store the torn container is **found again** by key on every later run — but it is still detected by `R6_KV_DIGEST("plane")` and is still one re-prefill after the caller deletes it. **31 stays low and non-blocking**; the reason is recorded so a later reader does not raise it on the store's account alone |
| One-shot `crypto.sha256` only | Genuine Align gap, recorded | **Request 29, `PROPOSED`.** **No new client**: key derivation digests 152 bytes and reuses three digests the arm already computed (2.8) |
| Indexing arrays of Move element types (`array<string>`) | Genuine Align gap, recorded | **Request 22, `PROPOSED`, stays non-blocking.** The key's inputs are fixed-width digests and integers, and the operands are token ids. **No new client shape.** Section 11.3 states exactly why the corpus keeps it non-blocking |
| Cross-module `borrow mut` argument lifetimes | Genuine Align gap, recorded | **Request 49, `PROPOSED`.** A **negative** client worth recording: `derive_key` is pure, so the boundary Request 49 forced on the refill did not bind here, and the key lives in the module that owns identity (4.2) |
| `buffer(cap)` cannot report a failed reservation; `buffer` append-only; `borrow mut buffer` rebind | Genuine Align gaps, recorded | Requests **35, 38, 39**, `PROPOSED`, inherited unchanged. The 152-byte preimage allocates nothing of interest |
| Non-`Copy` capture in `spawn` closures | Genuine Align gap, recorded | **Request 41, `PROPOSED`.** Relevant only to parallelising the qualification, which is not attempted |

### Request 53 (draft) — `std.fs`: directory creation, listing, and a file-type predicate

```text
Status: PROPOSED
Priority: medium
Blocking: no
Blocked gate or slice: none today. It becomes blocking for the deferred store-eviction /
  garbage-collection capability (section 7), which cannot enumerate what it must evict.
Independent work that may continue: all of R6-PREFIX-KEY and all of R6-PREFIX-TTFT.
Resume condition: schedule an eviction, GC, or size-budget capability over the R6 prefix store.
Align commit or pull request: none
align-llm verification: N/A
```

**Evidence at this pin.** `std.fs` as consumed by this repository is `create_exclusive`, `exists`,
`open_rw`, `read_file`, `write_file`. There is no `create_dir`, no `read_dir`, and no predicate
distinguishing a regular file from a directory from a missing path.

**Three concrete consequences in this capability, none of them hypothetical:**

1. The arm cannot create its own store and so requires a caller-created directory (2.4).
2. `R6_KV_UNWRITABLE store[create]` cannot name its cause: "no such directory", "that is a file",
   and "not writable" are one refusal (2.6).
3. The failure is reported **after** a full prefill, because a pre-flight check would need either a
   type predicate or a probe write in the caller's directory on every run (2.6, 6 risk 5).

**Proposed surface, Align-consistent and deliberately minimal:**

```text
fs.create_dir(path: str) -> Result<(), Error>        # one level, fails if it exists
fs.read_dir(path: str) -> Result<array<string>, Error>
fs.is_dir(path: str) -> Result<bool, Error>
```

**Acceptance criteria.** `fs.is_dir` distinguishes the three causes above so
`R6_KV_UNWRITABLE store[create]` can carry a cause; `fs.read_dir` enumerates a store of at least
10,000 entries without unbounded allocation; both respect the retained-root discipline Request 18
describes. **`fs.read_dir` returning `array<string>` intersects Request 22** — indexing arrays of
Move element types — and that intersection is part of this request rather than a surprise for its
consumer.

**Numbering, and it is a live hazard.** At this branch's base the register runs 1–52 (52 is item
31's `Option` partial move) and the next free number is **53**. Parallel branches are expected to
claim 53. **This must be re-checked when the branch merges `origin/main`** — by `git merge`, never a
rebase — and if the register has moved, this request and every cross-reference move with it.

---

## 9. Reconciliation drafts

To be written into their owning documents at implementation time.

### 9.1 `docs/specs/roadmap.md` — item **37**

> 37. **R6-PREFIX-KEY — a content-addressed store for prefix planes.** Design and results in
> [`r6-prefix-key-corpus.md`](r6-prefix-key-corpus.md). `--decode-step` gains a sixteenth operand,
> `STORE`, a directory that is mutually exclusive with `KV_SAVE` and `KV_LOAD`. The arm **derives**
> the key `r6-kv-persist.md` section 2.8 recorded in advance — `(source_header_region_sha256,
> geometry_sha256, token_stream_sha256, kv_width, plane_layout_version)`, plus `pack_total_bytes`,
> `token_count`, `element_type`, `format_version`, and a `key_version` — as a SHA-256 over a
> 152-byte preimage, and addresses `<STORE>/<key-hex>.akvp`. **A hit loads; a miss prefills, saves,
> and continues**, and the two produce byte-identical documents outside six fields — oracle K, the
> capability's acceptance rule. **A miss is only a missing file**: a container that exists and fails
> any identity check is that check's refusal and never a silent re-prefill, which keeps item 29's
> invalidation rule character for character. The `akvp` v1 format is **byte-unchanged** and the
> qualification asserts a `STORE` container is byte-identical to a `KV_SAVE` one. Schema **6** adds a
> `store` object published in every document including error documents; **no path is published**, so
> the key — a digest, not a clock or a machine path — is golden-stable. One byte layout has three
> implementations (the arm, `kv_plane_reader.py`, and the smoke recomputing it from the document's
> own published digests) and oracle D asserts all three agree. **No new refusal code is minted**:
> step 2d adds two `R6_KV_ARGS` details and a miss whose create fails is `R6_KV_UNWRITABLE
> store[create]` — one code for three causes the pin cannot separate, which is Request 53's client
> evidence. Owner `gmake layer-forward-smoke`; focused `gmake decode-step-qualification`, under 30 s
> added. **No TTFT or throughput claim and no cost ceiling** — `CLAUDE.md`'s performance row is not
> selected; the runner's TTFT trio gains a fourth leg and stays a labelled diagnostic. Stacked on
> item 36, whose lift of the `T_prefix >= 2` refusal a store that *writes* containers requires. One
> new Align request, **53** (`std.fs` directory operations), `PROPOSED` and non-blocking. **What it
> leaves open:** the R6 gate asks that TTFT improve on repeated coding tasks sharing a prefix. This
> discharges two of item 33 section 1.4's four reasons — there is now a key and a store — and leaves
> the corpus and the consumer. `MAX_PREFILL_TOKENS` is still **32**, so the largest legal prefix is
> 32 tokens and no real prompt reaches it; the shared prefix of `eval/prompt/canonical-v1` measures
> **370 tokens** against suffixes of 696, 825, and 1,049 (section 1.2). Item 38, R6-PREFIX-TTFT,
> lifts the cap, pins the corpus, and takes the gate measurement.

The R6 section's **未達** paragraph gains one sentence:

> item 37（R6-PREFIX-KEY）はprefix planeのcontent-addressed storeを実装し、keyとstoreという
> 欠けていた4つのうち2つを埋めた——しかしcorpusとconsumerは依然として存在せず、TTFTの主張もしない。
> `MAX_PREFILL_TOKENS`が32のままであるため実際のpromptは1つも入らない。

### 9.2 `HANDOFF.md` — the active block

Replaces the `MF-SINGLE-TOKEN-LOGITS` block when that merges; until then this branch is stacked and
the handoff records both.

> ## Active: R6-PREFIX-KEY (2026-08-29)
>
> Branch `agent/r6-prefix-key-corpus`, cut from `agent/mf-single-token-logits` `40eb965` — that
> branch's merge of `origin/main` `45ff38e` (PR #148). **Stacked on roadmap item 36 and must not
> merge before it**: a store that writes containers requires item 36's fix, because item 33's
> `T_prefix >= 2` refusal existed only because a one-token prefill computed the wrong embedding row,
> and a store would persist that wrong plane and serve it forever.
>
> Roadmap item **37**. Design gate fires on all four `CLAUDE.md` triggers — new CLI operand, new
> persisted identity (a naming rule over an unchanged format), a directory the arm populates, and one
> byte layout with three implementations. `docs/specs/r6-prefix-key-corpus.md` is authoritative.
>
> **Split, and it is a measured decision.** The work was scoped as `R6-PREFIX-KEY-CORPUS`. This
> document's own tokenization probe measured `eval/prompt/canonical-v1`'s shared prefix at **370
> tokens** and the three `prompt-v1` suffixes at **696 / 825 / 1,049** — the suffixes are 1.9x to
> 2.8x the prefix, and `T + S` reaches **1,419**. `MAX_PREFILL_TOKENS` is **32**, read as code by
> seven modules and three scripts and bound into a persisted header field, so lifting it is a capability's
> worth of blast radius. Section 1.2 splits on the failure-domain test: persisted identity here,
> prefill capacity and measurement in **item 38, R6-PREFIX-TTFT**, whose charter is section 11 and
> is written already.
>
> **Design complete, implementation not started.** No code is written. `docs/specs/r6-prefix-key-corpus.md`
> only.
>
> **Next actions, in order.** (1) Land item 36. (2) Implement section 2's ledger — `STORE` at
> `args[15]`, `kv_plane.derive_key`, the L0 branch, schema 6. (3) The sixth smoke block (5.1) and the
> refusal matrix (5.2). (4) `kv_plane_reader.py`'s name check. (5) `gmake layer-forward-smoke`, then
> `gmake decode-step-qualification`. (6) `python3 scripts/pre-pr --owner-test layer-forward-smoke --
> gmake layer-forward-smoke` and one comprehensive review.
>
> **Blockers.** None. Item 36's two real-model legs are waiting on host memory, which blocks item 36's
> publication and therefore this branch's merge, not its implementation.
>
> **New Align request 53** (`std.fs` directory operations), `PROPOSED`, non-blocking. The register's
> next free number must be re-checked at merge.

### 9.3 `docs/align-development.md` — the `--decode-step` arm

The heading at `:2001` gains `R6-PREFIX-KEY`; the arity sentence at `:2036` gains "or sixteen"; and
one invocation line is added after the `SUFFIX` line at `:2053`:

```text
./ggml-spike --decode-step PACK GEOM.json TOKENS DOC.json REF.gguf TRANSCRIPT.txt KV_WIDTH LOGITS.bin STEPS -       -       weights SUFFIX  STORE_DIR
```

with a short paragraph: `STORE` is a directory **the caller must create**; the arm derives the
container's name from the pack, the geometry, `TOKENS`, and `KV_WIDTH`, loads it if it is there and
writes it if it is not, and publishes the key it used in `store.key` on every run. It is mutually
exclusive with `KV_SAVE` and `KV_LOAD`. The TTFT paragraph at `:2158` gains: the store discharges
the *lookup* half item 33 lacked, and the trio's fourth leg remains a labelled diagnostic because
`MAX_PREFILL_TOKENS` is 32 and no real prompt fits.

### 9.4 `docs/align-requests.md`

Request **53** as drafted in section 8. One client line each on Requests **30** (third client) and
**49** (a negative client). One correction owed on Request **31**, drafted in section 8's table:
a store finds a torn container again by key on every later run, and 31 nevertheless stays low and
non-blocking because `R6_KV_DIGEST("plane")` detects it and the cost is one re-prefill after the
caller deletes the file.

---

## 10. Author consistency pass

One ledger-to-prose pass, performed before implementation. Five findings; all are applied above.

1. **The `SUFFIX` + `STORE` combination contradicted item 33's recorded refusal.** The first draft
   simply allowed it. Item 33 section 2.3 *refused* `SUFFIX` without `KV_LOAD` and recorded a reason
   — "it has no consumer". Silently widening a rule whose reason is recorded is how two documents
   come to disagree. **Applied:** 2.5 states it as a reversal, names the consumer that now exists,
   and keeps the reversal narrow — the caller still cannot express the combination; only the arm
   reaches it, on a miss.

2. **The refusal matrix was drafted with a new code, `R6_STORE`.** Checking the inventory
   (`kv_plane.align`) found `R6_KV_UNWRITABLE`, `R6_KV_WRITE_FAILED`, `R6_KV_EXISTS`, and
   `R6_KV_ARGS` already covering every condition. Item 28's rule — two codes for one condition is how
   two documents come to disagree — applies. **Applied:** 2.6 mints **no** new code; `R6_KV_ARGS`
   gains two details and `R6_KV_UNWRITABLE` gains one.

3. **The key was first placed in `decode_step`, beside the operand.** That splits container identity
   across two modules. **Applied:** 4.2 puts `derive_key` in `kv_plane`, and records that Request 49
   — which forced the *opposite* boundary for the refill in item 29 — does not bind, because the
   function is pure and takes no `borrow mut`. The asymmetry is stated rather than left to look
   inconsistent.

4. **The commissioning task proposed a corpus digest in the key, and the first draft included it.**
   It is wrong: two corpora producing the same ids must hit the same container, and provenance in an
   identity key silently partitions the store. **Applied:** 2.3 rejects it explicitly, with the
   reason, and routes the digest to the manifest (11.3) — a rejection recorded rather than an
   instruction quietly dropped.

5. **`tokenizer_id` and `prompt_template_version` were drafted as GGUF metadata scalars in the
   preimage**, as the commissioning task proposed. Reading them requires the GGUF, which a load run
   may not have — `REFERENCE` is optional and `r6-kv-persist.md` 2.4 built the whole model-identity
   argument on exactly that. **Applied:** 2.3 records both as `N/A`, **subsumed twice** — once by
   `source_header_region_sha256`, whose digested region contains every metadata KV, and once by
   `token_stream_sha256`, because a different tokenizer over the same text yields different ids. The
   narrower key is also the stronger one.

**One thing this pass could not settle and has left as a risk rather than a decision.** 6 risk 7
bounds the qualification's added cost at "under 30 s" by arithmetic on item 30's `N = 1` figures.
That is an estimate on a host whose `N = 1` elapsed varied 4.95–9.55 s across item 30's four runs.
The risk row states the fallback (move the store leg to prompt 1 only) and the threshold (120 s)
rather than asserting the estimate.

---

## 11. Next — `R6-PREFIX-TTFT` (roadmap item 38)

**This section is a charter, not a contract.** It is written now so the split (1.2) is a schedule
rather than a hope. Its own design gate fires and it needs its own ledger before implementation.

### 11.1 The lift — `MAX_PREFILL_TOKENS` 32 → 2048

**The constant.** The largest measured `T + S` is **1,419** (1.2). **2048** is proposed: it clears
that with headroom for item 34's `canonical-v1e` second family, it is a power of two, and it keeps
`T + S + N <= MAX_ATTENTION_WIDTH` (4096) with more than a factor of two of slack.

**Every consumer, enumerated now so the successor's blast radius is not a discovery:**

| Consumer | Effect of 32 → 2048 |
| --- | --- |
| `src/layer_qwen2.align:68`, `src/layer_olmoe.align:75` | the two declarations |
| `src/layer_forward.align:314`, `src/moe_layer_forward.align:387` | the prefill count guards |
| `src/model_forward.align:3335` | **the embedding staging reservation**, `row_bytes * MAX_PREFILL_TOKENS`. Qwen2.5-Coder-7B: `14,336 x 2048 = 29,360,128 B` (28 MiB). OLMoE: `8,192 x 2048 = 16,777,216 B` (16 MiB). Both are small beside the 4.68 GB arena and neither approaches the host's limit |
| `src/decode_step.align:1835` | the `R6_SUFFIX sequence[<n>]` cap |
| `src/kv_plane.align:519` | the header's `token_count` bound — **a persisted-format field** (`r6-kv-persist.md` 2.3.1, offset 124). A container written at `token_count = 370` is **unreadable** by a build whose cap is 32, so the lift is a one-way compatibility step and the successor's ledger must say so |
| `src/kv_plane.align` token stream region | `token_count * 4` grows from ≤128 B to ≤8,192 B. No layout rule moves; `identity_offset` is already `align_up(192 + token_count * 4, 8)` |
| `scripts/kv_plane_reader.py:45`, `scripts/run-decode-step:306,1296`, `scripts/run-layer-forward-smoke` (five sites) | the mirrored constants and the cap-boundary cases, which move from "33 repetitions of token id 1" to 2,049 |
| `R5_ORACLE_TRUNCATED` | **unchanged at six tokens.** The transcript oracle stays unavailable (3.4) and the successor must not lift it to chase one |
| The plane | `KV_WIDTH` must reach `T + S + N`. At 1,419 + 1 the smallest adequate width is 1,536: `1,536 x 114,688 = 176,160,768 B` (168 MiB), under `MAX_KV_PLANE_BYTES` (512 MiB) and under `MAX_ATTENTION_WIDTH`. At 4096 the container is 470,372,352 B, still under both |

**The cross-platform golden hazard is the successor's central risk, not this one's.** 5.3 records
that this capability adds no activation bytes to any golden. A cap of 2048 makes it *possible* to
pin a long prefill's activations, and the rule must be restated and enforced there: **hosted goldens
stay synthetic and short; anything at four or more tokens of real-model activation is
qualification-only.** The cap-boundary cases (2,049 ids) are **refusals** and carry no activation
bytes, so they are safe; the danger is a well-meaning "let's pin the 370-token prefix's logits" row.

### 11.2 The gate measurement — ceiling, floor, and a pre-committed verdict

**The metric.** `timings.first_token_ns` at `STEPS = 1`, no transcript, no logits blob,
`RESIDENT=weights` on both legs.

**The two legs, paired per suffix.**

- **(a) single-shot** — prefill `TOKENS ++ SUFFIX`, one token.
- **(b) keyed hit** — `STORE` with a warm store: load, suffix pass, one token.

**The floor — 150,000 ppm, adopted from `r6-resident-weights.md` section 3.4 rather than replaced.**
That document made itself the owner of Track B decode-time performance and wrote: *"A later Track B
performance capability records its ceiling against the baseline and floor defined here, or replaces
them with reasons."* The floor is a **fraction of a fixed task**, calibrated at 150,000 ppm just
above that document's measured 114,000 ppm run-to-run noise on the `N = 16` decode loop. TTFT is a
different fixed task, so the number is **re-derived rather than assumed**, and the successor's first
implementation step is a baseline probe that measures it. Two reasons to expect it holds: the TTFT
fixed task at `T + S ≈ 1,200` is *longer* than the `N = 16` decode loop and dominated by a single
compute term rather than sixteen weight sweeps, so its relative noise should be **smaller**, not
larger. If the probe measures otherwise, the successor records a replacement floor **with the
measurement**, before implementation.

The roadmap's own R6 gate sentence — 同一prefixを使う反復coding taskでTTFTが改善すること — states no
threshold. **Both apply, and they are different questions:** the roadmap gate asks whether TTFT
*improves*, which is answered by a separated interval; `CLAUDE.md`'s performance row asks whether the
improvement clears a shipping floor. A result can pass the first and fail the second, and the
successor must report both rather than collapse them.

**The ceiling, in closed form, with the one unmeasured term named.**

```text
ceiling_ppm  =  (T / (T + S))  x  (prefill compute / single-shot TTFT)  x  1e6
                 -  (container read / single-shot TTFT) x 1e6
```

The first factor is **measured** (1.2): 0.34709, 0.30962, 0.26075 per task; mean **0.30582**, worst
**0.26075**. So even if prefill compute were 100 % of TTFT and the container read were free, the
ceiling would be **305,821 ppm at the mean and 260,747 ppm at the worst suffix**. It is strictly
below both, because the fixed cost is not zero: `r6-resident-weights.md` 5.8.1 measured `N = 1`
resident elapsed at 5.819 s and 6.800 s with 0.865 s and 0.939 s of compute at `T = 6`, so roughly
**4.9–5.9 s** of process start, pack open, geometry load, and arena fill is paid by **both** legs.

**The precondition this makes falsifiable, which is the point of writing it now.** For the mean task
to clear a 150,000 ppm floor, prefill compute must be at least `150,000 / 305,821 = 49.0 %` of
single-shot TTFT; for the **worst** suffix, `150,000 / 260,747 = 57.5 %`. With ~5.4 s of fixed cost
that means prefill compute of roughly **5.2 s at `T + S = 1,195`** and **7.3 s at 1,419** — that is,
**this arm's resident prefill must run at or below roughly 200 tokens per second on the reference
host.** Faster than that and the gate cannot be met on this corpus at this prefix share, whatever
the implementation does.

**So the successor's first implementation step is a probe, not code** — the shape
`r6-resident-weights.md` 5.7 (cell RW-P1) already established. One resident prefill at
`T + S ≈ 1,200`, three repeats, reporting elapsed and compute. Its number sets the ceiling, and the
ceiling is recorded in the ledger row **before** implementation, as `CLAUDE.md`'s performance row
requires. If the probe shows the precondition fails, **the honest outcome is to publish that and not
build the measurement** — the corpus's prefix share would be the binding constraint, and the answer
would be a corpus with a longer shared prefix (a repository preamble, file headers) rather than a
faster store.

**Pre-committed verdict rule**, written before any number exists so it cannot be chosen afterwards:

| Verdict | Rule |
| --- | --- |
| **MET** | The jackknife-minimum paired reduction (11.4) is **> 0** under **both** cache protocols, **and** the worse protocol's jackknife minimum is **>= the floor** |
| **NOT_MET** | The jackknife maximum is **< the floor** under either protocol — the floor is excluded |
| **INDETERMINATE** | Anything else, including a reduction separated from zero but straddling the floor. **The roadmap gate is not discharged**, the point estimate and the interval are published, and R6 turns to tiering or a longer-prefix corpus with a measured reason |

An INDETERMINATE result is a real outcome and not a failure to measure. Item 33 published a
*direction* and discharged nothing; this must be able to do the same.

**The cost, which is not the gate but is reported beside it.** A miss costs a `T_prefix`-column
prefill **plus** a 168 MiB container write, and a hit costs a 168 MiB container read. Item 33
section 1.4's correction 9 is the standing warning: it measured the container read to be a real
exchange and not free arithmetic, on a **six-token** prompt. At 370 tokens the trade is far more
favourable, but it must be **measured**, and the successor reports the read as a named term of the
subtraction rather than absorbing it.

### 11.3 The corpus — pinned, pre-tokenized, and why Request 22 stays non-blocking

**Location and shape.** `eval/kv/prefix-corpus-v1/`:

```text
manifest.json          schema, provenance, and one entry per id list
shared-prefix.ids      the T_prefix ids, one decimal per line
<task-id>.suffix.ids   one per task
```

**`manifest.json` records, for every entry:** the source artifact and **its** `content_sha256`
(`base-prompt.json`, `repo-prompt.json`, `task-prompt.json` all carry one already), the id list's own
`content_sha256`, the id count, and — once, for the corpus — the instrument (`llama-debug` build id
and `.llama-revision`), the model file's `sha256`, the pack's `source_header_region_sha256`, and the
exact command. A corpus that drifts from the prompts it was tokenized from is then a **detected**
inconsistency rather than a silent one, and the check is a static consistency check the successor's
preflight can run without a model.

**The ids come from the pinned instrument, not from this document's probe.** Section 1.2's
`llama-tokenize` figures are sizing. `scripts/run-decode-step` already extracts ids from
`llama-debug --save-logits`'s `*-tokens.bin` by unpacking `<i` int32 (`:282-308`); the corpus is
generated by that same path and checked in, so the qualification reads ids from a file instead of
running a tokenizer.

**Why Request 22 stays non-blocking, exactly.** Request 22 is indexing arrays of Move element types
(`array<string>`), and its own entry names a **tokenizer or vocabulary-inspection capability** as the
first consumer that makes it blocking. Nothing in this wave is that consumer:

- `--decode-step` takes **token ids as operands**. It does not tokenize, detokenize, or read a
  vocabulary.
- The corpus makes that *cheaper*, not merely tolerable: pinning the ids removes even the
  qualification's per-run tokenizer invocation, so the arm's distance from a vocabulary grows rather
  than shrinks.
- The GGUF surface at this pin reads `tokenizer.ggml.tokens`' declared **length** only, and
  `check_index` rejects `array<string>` indexing outright — so there is no partial Align-side
  tokenizer to build, and building one against a proposed API is forbidden.

The first consumer that makes 22 blocking is R7's text path, which needs a detokenizer to produce
text. **Reclassify then, not now.** If `fs.read_dir` (Request 53) is implemented as
`Result<array<string>, Error>` it becomes a second client of 22 — recorded in 8 rather than left for
its implementer to find.

**`canonical-v1e`.** Item 34's second prompt family, if it lands first, doubles the suffix count and
materially improves 11.4's jackknife, which is weak at three clusters. The successor should take it
if it is available and proceed with three suffixes if it is not, recording which.

### 11.4 The measurement protocol

- **Design.** Paired per `(suffix, repeat)`; `K = 5` repeats; **legs interleaved**, `repeat`
  outside and `leg` inside — `r6-resident-weights.md` 3.4 measurement risk 4's shipped mitigation,
  adopted rather than re-derived, because taking all of one leg then all of the other confounds the
  leg with the clock.
- **Statistic.** The paired reduction in ppm of single-shot TTFT, per suffix. With **three**
  clusters a cluster-robust interval is not credible, so the conservative figure is a
  **leave-one-suffix-out jackknife minimum**, which is R3's own precedent (`roadmap.md` quotes
  "jackknife最小186‰"). Report the mean, every individual pair, and the jackknife minimum; the
  verdict quotes the minimum.
- **Cold-cache protocol — what is actually feasible on this host, stated rather than assumed.**
  `sudo purge` is the macOS way to evict the page cache and **it needs sudo, which autonomous work
  does not have**. It is therefore not used, and no result pretends to a purged cache. Two protocols
  are run instead and **both** must clear the floor:

  | Protocol | Method | Direction of bias, stated |
  | --- | --- | --- |
  | **W — warm** | A fresh process per run; the page cache is left as the previous run left it | A warm cache makes the 168 MiB container read cheap, which **flatters the keyed leg**. It also makes the 4.68 GB pack read cheap, which is common to both legs and cancels in the pairing. **Net bias: toward MET** |
  | **C — evicted** | Between runs, read an unrelated file larger than physical memory (~20 GiB on a 16 GiB host, ~10 s at the 2.12 GB/s item 30 measured) to force eviction | This evicts the **pack** too, so both legs re-read 4.68 GB and pay ~2.2 s each. That inflates the denominator and **dilutes** the ratio. **Net bias: toward NOT_MET** |

  The claim is the **worse of the two**, which brackets the honest answer between a protocol biased
  each way without ever claiming a cache state that was not achieved. If the two protocols disagree
  about the verdict, the result is **INDETERMINATE** and the disagreement is the finding.
- **What is recorded around every timed run.** `vm_stat`'s compressor counters, per
  `r6-resident-weights.md` 3.4 risk 2's *shipped* rule — **recorded and reported, never used to
  discard or retake a run**.
- **The standing unmitigated clause**, carried forward verbatim: every run is on one machine in one
  thermal environment, and nothing establishes the result on a fanned host, a larger host, or a Linux
  page cache.

### 11.5 What the successor must settle that this document does not

1. Its own ledger, closure matrix, and consistency pass — the lift is a coordinated invariant across
   seven modules and three scripts and earns its own design gate.
2. The baseline probe (11.2) and the ceiling derived from it, **before** implementation.
3. Whether the container write on a miss belongs in the measured path at all, or whether the gate is
   about the hit leg alone. This document's view is that both must be reported, because a store whose
   misses cost more than they save is a pessimization at low reuse — but it is the successor's row.
4. Whether `canonical-v1e` is available, and what three clusters versus six does to 11.4.
5. `KV_WIDTH` for the corpus: 1,536 is the smallest adequate width and 2,048 the smallest power of
   two. The choice moves the container by 56 MiB and belongs with the measurement.

---

## 12. Implementation deviations from the committed ledger

Sections 1 to 10 are **committed at `8238df6`** and are not edited. Everything the implementation
did differently is here, with its reason, and each is either a correction of a ledger statement that
was wrong or a choice the ledger left underspecified.

### D1 — `src/model_forward.align` is **not** byte-unchanged; it gains five `Outcome` fields

Section 4.3 says the module is byte-unchanged, and section 2.7 requires a `store` object in every
`R6_DECODE_STEP` document. Both cannot hold: `model_forward.Outcome` is the single record
`src/decode_step.align` renders its document from, and every prior capability's fields — `kv_*`
(item 29), `resident_*` (item 30), `suffix_*` (item 33) — live there for the reason item 29's section
2.9 records, that a second by-value record doubles the plumbing for a handful of scalars.

**Applied:** `Outcome` gains `store_requested`, `store_outcome`, `store_saved`, `store_key`, and
`store_lookup_ns`, plus their five initializers in `empty_outcome`. **Nothing else in the module
moves** — not the graph, not the staging reservation, not the embedding builder, not
`MAX_PREFILL_TOKENS`, and no renderer of that module. The intent section 4.3 was protecting is
therefore intact and is asserted rather than claimed: `--model-forward`, `--model-forward-gpu`,
`--layer-forward`, `--moe-layer-forward`, `--moe-model-forward`, and `--moe-decode-step` all
re-emitted their goldens byte-unchanged: **seven of the repository's eight golden corpora are
untouched in the diff** and only `scripts/decode-step-golden.jsonl` moves.

### D2 — `derive_key` takes six arguments, not section 2.8's five

Section 2.8 writes the signature as
`derive_key(source, geometry, tokens, kv_width, token_count) -> string`, but section 2.3's preimage
carries `pack_total_bytes` at offset 96 and the arm must supply it. The shipped signature is

```text
kv_plane.derive_key(borrow source_digest: slice<u8>, borrow geometry_digest: slice<u8>,
                    borrow token_stream: slice<u8>, kv_width: i64, token_count: i64,
                    pack_total_bytes: i64) -> string
```

`token_stream` is the **bytes** — `token_count` little-endian `u32` ids — and the function digests
them itself, so one function owns the whole preimage and no caller can hand it a digest of something
else. Every other property section 2.8 states holds: it is pure, takes no `borrow mut`, opens
nothing, allocates one 152-byte buffer freed at its own scope end, and is unaffected by Request 49.
The empty string is its one failure channel and every caller refuses on it (`R4_WINDOW_UNAVAILABLE`,
detail `store_key`), which no input can reach.

### D3 — oracle K's exclusion list is oracle Q's set plus three store fields

Section 3.1 lists six exclusions and glosses `pack.reader_*` as "the counters item 30 already
excludes". Taken literally the list is short by the blocks a **load** run legitimately does not
produce — `graph`, `schedule`, `lifetime`, `reference`, `weights`, `plane.source`, `head.node_count`,
`window.reuse_count`, `window.member_placements` — because a keyed miss **is** a save run and a keyed
hit **is** a load run, which is exactly what item 29's oracle Q already compares.

**Applied:** oracle K is implemented as oracle Q's `normalize_persist` plus `store.outcome`,
`store.saved`, and `store.lookup_ns`. `store.key` and `store.container_bytes` stay **inside** the
comparison — they are what catches a key that varies between runs or a container written with the
wrong layout — and a witness assertion checks that the exclusion list did not empty the comparison
(`decode`, `steps[0].sha256`, `output`, `oracle_logits`, `plane.roundtrip_bytes_compared`, and both
store fields must still be present). The hosted block also asserts the two stronger statements the
short list was reaching for: a keyed miss equals `ds-kv-save-ok` and a keyed hit equals
`ds-kv-load-ok`, outside the `store` object the other side did not ask for.

### D4 — `kv.save_requested` / `kv.load_requested` report the **lookup's** direction

Section 2.5's table says the two legs report `kv.verdict` and `kv.destination` "as `KV_SAVE`/
`KV_LOAD` reports today", and section 3.1 excludes `kv.save_requested` and `kv.load_requested` —
which are only worth excluding if they move. They do: after L0 the arm sets `kv_load_requested` on a
hit and `kv_save_requested` on a miss, so the run **is** the load run or the save run from that point
on and every line below L0 is unchanged. This is what makes D3's two comparisons against
`ds-kv-save-ok` / `ds-kv-load-ok` meaningful rather than accidental.

### D5 — `store.container_bytes` is rendered from `kv.total_bytes` rather than stored twice

Section 2.7 defines it as "the container's `total_bytes` … equal to `kv.total_bytes`, restated here".
It is rendered directly from that field under `if store.requested`, so the two cannot disagree; there
is no sixth `Outcome` field. `0` when no store was requested, exactly as specified.

Two consequences of tying it to `kv.total_bytes` are stated rather than left to be discovered. A
**refused hit** — a container at the key path that fails an identity check — publishes the size the
container's own header declared, because the header was read before the refusal; and a **miss whose
write failed** publishes the size the writer planned, because `plan_header` runs before
`fs.create_rw`. In both cases `saved` is `0` and `error_code` is set, so no reader can mistake either
for a container that exists; the alternative — zeroing the field on any refusal — would have made
`store.container_bytes` disagree with `kv.total_bytes` beside it, which is the one thing this field
exists to avoid.

### D6 — the concurrent loser overwrites; it is not refused with `R6_KV_EXISTS`

Section 2.8 says two processes missing the same key concurrently leave the loser refused with
`R6_KV_EXISTS`. That is not what this pin does. The `R6_KV_EXISTS` guard is step 6b's `fs.exists` on
the **`KV_SAVE` operand**, which precedes L0 and cannot see a path the key has not yet produced; and
`write_container` opens with `fs.create_rw`, which truncates. So a second process that missed the
same key writes over the first's container.

**It is benign and it is recorded rather than hidden**: the key is a function of the content, so both
processes write byte-identical bytes at identical offsets, and the store is declared single-process
(section 2.8) exactly so that this is not load-bearing. Closing it properly needs an exclusive
positional constructor, which is **Align Request 30**, and R6-PREFIX-KEY is filed there as its third
client with this shape as the evidence. Section 4.1 already records `R6_KV_EXISTS` as not reachable
from a single-process case; this deviation says why it is not reachable from a concurrent one either.

**Three further corrections this deviation owns, because they are the same statement in three
places.**

1. **Section 1.4's non-goal is corrected with section 2.8's row.** "Two processes missing the same
   key concurrently is a refusal for the loser, not a merge" (`:150`) states the same outcome
   section 2.8 states, and it is wrong for the same reason: the loser is neither refused nor merged,
   it **overwrites**. The non-goal itself stands unchanged — concurrent writers are out of scope and
   nothing here makes them supported — and only its description of what happens moves.
2. **`fs.create_exclusive` is named three times and is never used.** Sections 2.6 (`:391`), 2.8
   (`:442`), and 6 risk 9 (`:767`) attribute the create's behaviour to it. The writer opens with
   **`fs.create_rw`** (`kv_plane.align` W1), which is `O_RDWR|O_CREAT|O_TRUNC` — the misattribution
   is the whole mechanism of this deviation, and `decode_step.align:3481` already carries the
   correct comparison beside step 6b. Every statement those three places make about the *failure
   detail* is still true: `fs.create_rw`'s failure at this pin also cannot separate "no such
   directory", "that is a file", and "not writable", so `store[create]` remains one code for three
   causes and Request 53 remains its client evidence.
3. **Risk 9's disposition is therefore half right.** The TOCTOU window between `fs.exists` and the
   create is real and is *not* closed by a refusal; it is closed by the content addressing, which
   makes the racing writes identical. The declared single-process scope (section 2.8) and Request 30
   are what the disposition should have named, and the reader that races an `O_TRUNC` inside that
   scope is out of scope by the same declaration.

### D7 — the real-model store leg runs at the suffix leg's split and at its residency

Section 5.4 specifies prompt 1 at `j = 3` on "both the streamed and the resident legs". The shipped
leg runs on the **first split of every persistence-leg prompt** (four by default,
`ALIGN_LLM_STORE_PROMPTS` moves it, `=1` is section 6 risk 7's recorded fallback), at whatever
`SUFFIX_RESIDENT` the host selected — resident on a capable host, streamed otherwise — rather than
both legs on one prompt. Two reasons: four prompts at one residency costs the same two invocations
per prompt section 4.9 budgeted and covers four distinct key preimages instead of one, which is what
a **key** wants exercised; and both residency legs are covered hosted, where `ds-store-resident-miss`
/ `-hit` carry oracle K and oracle R at no model cost.

**The measured addition is *not* recorded yet, and this sentence is a forward reference rather than
a result.** It belongs in section 13.6 against risk 7's 120 s threshold; 13.6 records that the
qualification has not run, so no measurement of this leg exists and no claim about its cost is made
here. The run is a precondition of publication (section 3.5), so the reference cannot outlive the
pull request: it is discharged by 13.6's own table or the capability does not ship.

### D8 — the qualification's store leg is the TTFT "fourth leg", and it is one run per prompt

Section 4.9 says the TTFT trio gains a fourth leg. The trio is three `STEPS = 1` invocations repeated
three times per prompt; adding a fourth member would cost three more invocations per prompt against
risk 7's budget of two. **Applied:** the store leg's own miss and hit are wall-clock timed with the
same `time_invocation` wrapper and reported as `R6PK … timings DIAGNOSTIC`, one run each, explicitly
**not** presented as a fourth point on the trio's line — they run at `DECODE_STEPS` with a transcript
and a logits blob, which is what buys oracle K, oracle S on both legs, gate G1 on both legs, and
oracle B in the same two invocations. No rate, speedup, or per-token figure is derived from any of
them, which is the property section 2.9 requires.

### D9 — the hosted key-determinism rows carry no golden row

Section 5.1 lists `ds-store-key-tokens`, `-width`, `-geometry`, `-pack`, and `-stable` as rows. They
are implemented as asserted-but-not-pinned cases, the precedent `BOUNDARY_CASES` set for the same
reason: what they assert is a **key**, and the key is asserted directly and three ways. Pinning four
more whole documents would add golden bytes that say nothing the assertion does not. The four
one-field-changed keys and the miss's key are checked pairwise distinct, each against this block's
own independent preimage implementation and against the document's, and `ds-store-key-stable` runs
from a different working directory with a different `STORE` and a different `DOCUMENT` and must
produce the same key **and a byte-identical container**.

### D10 — two hosted cases needed `TRANSCRIPT` set to `-`

`ds-store-key-width` and `ds-store-key-tokens` change `KV_WIDTH` and the token list, and the hosted
transcript is the instrument's own four graphs for `3,17,5` at width 8. Supplying it would refuse the
run at `R6_KV_WIDTH` (the transcript carries the width) or compare against the wrong prompt's graphs,
before the key these rows exist to compare had been compared. Both take `-`, which is the convention
`ds-suffix-*` already uses for the same reason.

### D11 — the reader checks the name automatically when the name is store-shaped

Section 4.5 asks for the check "when handed a path whose basename is 64 hex plus `.akvp`" and a
`KEY` verdict. Shipped as both: the check is automatic on a store-shaped basename and can be demanded
on any path with `--check-name`, which is what the real-model qualification passes. A container the
caller named itself is validated exactly as before, so the reader stays usable on a `KV_SAVE`
artifact. The reader also **recomputes** the token-stream digest from the stream rather than reading
the identity record's `tokens` slot, so a container whose slot disagrees with its own stream cannot
be addressed by a name that matches the slot; the slot is still checked separately as `DIGEST`.

### D12 — the over-arity row moves up one and a sixteen-operand `NO_DOCUMENT` row replaces it

Section 4.1 lists `ds-arity-16` and `ds-arity-17` together. Sixteen operands is now **legal**, so the
over-arity row moves up one exactly as it did in each prior capability (`ds-arity-12` →
`ds-arity-14` → `ds-arity-15` → `ds-arity-16` → **`ds-arity-17`**), and the sixteen-operand
no-document case is `ds-store-path-empty`, whose sixteenth operand fails `valid_path`. Both carry no
golden bytes, so the move costs nothing.

### D13 — oracle S needed one field beyond item 33's exclusion set, with a compensating assertion

Section 3.3 carries oracle S forward "unchanged" and asks for it on **both** the hit and the miss
leg. Run on a miss it fails on `weights.wrap_count`, and legitimately: that counter is one streamed
window wrap per graph, and a miss runs one graph set more than a single-shot — its own prefill of
`T_prefix`, which is the whole reason a miss exists. Item 33's own pairs never met it because a
*load* run builds no prefill graph, so its suffix pass exactly replaces the single-shot's prefill.

**Applied:** `weights.wrap_count` is excluded and the exact identity is asserted in its place —
`miss.wrap_count == single.wrap_count + (n_layer + 2)` and `hit.wrap_count == single.wrap_count`,
with the term `0` on a resident leg, where the arena is wrapped once at run scope. This follows item
33's own rule for a growing exclusion list (its section 11, findings 1 and 2): every addition is a
recorded finding with a compensating assertion, never a quiet pop.

### D14 — a keyed miss with a suffix saves **before** the suffix pass, and that moved one call site

Section 2.5 says a miss "prefills `TOKENS`, **saves** the container to that exact path through the
existing `KV_SAVE` writer, then runs the same suffix pass". The shipped arm's `KV_SAVE` call site is
**after** the suffix pass, and that was correct for every run before this one: `SUFFIX` is illegal
beside `KV_SAVE` (steps 2b and 2c), so no saving run had ever had a suffix pass to be after. **A
store miss is the first run that has both**, and the first implementation inherited the position.

The consequence was real and was caught by this capability's own container assertions rather than by
review: a container written after the pass carries `T_prefix + S` columns of plane and the **suffix
pass's** logits under a header that declares `columns_persisted = T_prefix` and a `prefill_argmax`
from the wrong vector. It round-trips through the arm — the plane digest covers whatever was written
— so oracle K passed; but the container was not the `KV_SAVE` container of the same prefix, the
independent reader refuses it as `ZEROTAIL`, and the key would have bound a **prefix** to a plane
containing one particular suffix, which is precisely what content addressing must not do.

**Applied:** `schedule_decode` gains one guarded call site immediately after the prefill's own digest
block and before the suffix pass, taken only when `store_mode && suffix_count > 0`; the existing site
skips exactly that case. The regression is `ds-store-suffix-vs-kv-save`, which asserts the keyed
container is byte-identical to the one `ds-suffix-save-prefix` writes for the same two ids at the
same width **and** that the independent reader accepts it. On the defect the two digests differ and
`kv.prefill_argmax` is 24 (the suffix pass's) instead of 27 (the prefill's); the real-model leg's
own reader `--check-name` and container comparison would have caught it too.

**And section 3.1 overstates oracle K, which this defect proves rather than argues.** 3.1's "why
this is the right rule" names, among what oracle K catches, "**a container written with the wrong
columns**". D14 *is* a container written with the wrong columns, and oracle K passed on it. The
reason is structural and is worth stating exactly, because it bounds what the acceptance rule can
mean: oracle K compares a **hit** against the **miss that filled it**, and the hit is served by the
same arm that wrote the container. A plane that is wrong but **self-consistent** — one the writer's
own header describes and the reader's own digest covers — reproduces itself on the way back and the
two documents agree. Oracle K is a *round-trip* property, and a round trip cannot see an error the
writer and the reader share.

**What owns that class instead**, and it is already shipped rather than proposed: the two
**container-identity** assertions. `ds-store-vs-kv-save` and `ds-store-suffix-vs-kv-save` compare
the keyed container by SHA-256 against the container `KV_SAVE` writes for the same prefix — a
comparand produced by a *different* operand path, so it does not share the defect — and
`scripts/kv_plane_reader.py` refuses the plane from the specification, in another language, without
the arm's assumptions. Those two caught D14; oracle K did not. Section 3.1's exclusion list is
unchanged and its other four claims stand; only the "wrong columns" clause is corrected, and the
correction is that **oracle K's strength is byte-equality between two runs, and the container's
correctness is asserted against an independent comparand and an independent reader.** Section 13.4's
fifth mutant is the standing regression for exactly this, and it dies on the container assertions.

### D15 — the field that moves 5 → 6 is the document's `schema_version`

Sections 2.7 (`:398`), 5.3 (`:707`), and 6 risk 8 (`:766`) all name the moving field
`document_schema_version`. **That is a different field.** The document's own is `schema_version`
(`decode_step.align` renders `{"schema_version":6,…}`); `document_schema_version` is a **container
header field at offset 136, frozen at 3**, and `r6-prefix-suffix-prefill.md` section 2.9 settled its
contract: it records the `R6_DECODE_STEP` schema the *format was defined against*, not the schema
the writer currently emits, and it deliberately does **not** move when the document schema does —
the document has been 4 and 5 with the constant unmoved, and moving it would refuse every existing
container for no safety gain.

The three statements are therefore right about the change and wrong about the name. This capability
leaves the header field at 3 and `kv_plane`'s header plan is absent from the diff. The name matters
here more than in the documents that inherited it, because **both** fields are live in one design:
the container's is validated on load and is not in the key (D17), and the document's is not in the
container at all. `docs/specs/roadmap.md` item 37 and section 13.3 are not frozen and are corrected
in place; these three are recorded here.

### D16 — W5 maps a second code, `store[cleanup]`, and the moved call site gains its own row

Section 2.6's W5 row maps one writer code under a store. **`R6_KV_CLEANUP_FAILED` needed the same
mapping and did not have it.** It is the one writer code whose detail is the **destination itself**:
`kv_plane.align`'s W4 reports `bounded_detail(destination)` so that a `KV_SAVE` caller learns which
partial file it must remove by hand. Under a store that destination is the arm's own derived name,
and section 2.7's "no path is published" governs a refusal detail exactly as it governs a document
field — the leak would have made `error_detail` a function of the caller's `STORE` directory, which
is precisely what mutant 4 exists to kill in the document. Every other writer code is already safe:
`R6_KV_WRITE_FAILED` reports `error_name@offset`, `R6_KV_SIZE_MISMATCH` reports a pair of counts,
and `R6_KV_UNWRITABLE` is W5's existing `store[create]`.

**Applied:** one more guarded branch beside `store[create]`, reporting the operand as
`store[cleanup]`. The caller loses nothing — `store.key` is published, so the file it may need to
remove is `STORE + "/" + key + ".akvp"`.

**It is unreachable by fixture at this pin, and that is inherited rather than new.** Reaching it
needs a filesystem that accepts a create, refuses a write, and then refuses the removal;
`scripts/run-layer-forward-smoke` already records `R6_KV_WRITE_FAILED` as deferred as a case for the
first half of that (alignpack reaches it only through an opt-in `hdiutil` volume) and defers
`R6_KV_CLEANUP_FAILED` and `R6_KV_SIZE_MISMATCH` behind it. The forced-stub and unwritable-directory
mechanisms cannot produce it: a directory that refuses the `unlink` refuses the `create` first. The
mapping is therefore asserted by inspection, exactly as `R6_KV_EXISTS`'s unreachability is (section
4.1, D6), and it ships because the alternative is a known path leak behind an unlikely failure.

**What *was* reachable and had no row is now one.** A keyed miss **with a suffix** saves at D14's
moved call site, so its create failure is reported from a site no prior capability could reach —
`SUFFIX` was illegal beside `KV_SAVE`, and section 5.2's `ds-store-unwritable` and
`ds-store-file-not-dir` both run without one. `ds-store-suffix-unwritable` closes it: same code, same
detail, and the assertions that make it a statement about *ordering* rather than a duplicate — the
document publishes `suffix.requested: 1` with `completed: 0` and `graph_count: 0`, so the arm refused
**before** the pass rather than running it and failing afterwards, and the key it published is the
**prefix**'s `f8881c20…`, the same one `ds-store-suffix-miss` writes. It is the sixteenth store case
and the tenth store refusal, and it is the reason section 13's counts moved by one.

### D17 — `document_schema_version` is not in the preimage, and its coupling is now written down

Section 2.3's decision 1 states the rule the preimage follows: a field the load path would **refuse**
on belongs in the key, so that a caller whose inputs moved gets a clean miss instead of an identity
refusal against a container that is simply for something else. **`document_schema_version` is such a
field and is not in the preimage.** `kv_plane.align:41` freezes it at 3 and the load path refuses a
container whose header disagrees (`R6_KV_HEADER("document_schema_version")`), so two containers
differing only in it would share one key and the loser would be refused rather than missed.

**It cannot happen at this pin, and the reason is a coupling rather than an accident**, so the
coupling is now stated in the code at `KEY_VERSION` and here: the constant is frozen at 3, this
writer is its only producer, and **a change to `DOCUMENT_SCHEMA_VERSION` must bump `FORMAT_VERSION`
— which *is* in the preimage at offset 120 — or `KEY_VERSION`, in the same commit.** That is a real
constraint on a future capability and it is cheap to honour, because `r6-kv-persist.md` already
requires a `format_version` bump for any header change and `r6-prefix-suffix-prefill.md` section 2.9
already requires this field not to move for a document bump.

**The preimage is not changed, and that is the decision.** Spending four of the twenty-four reserved
bytes on the field would move **every existing key** — the hosted `ab1a4ebf…`, the qualification's,
and any container a caller has already stored — to buy a distinction that the coupling already makes
impossible. Key stability wins; the coupling is the compensating control and this deviation is its
record.

### D18 — three preimage slots are constants in the arm, and 2.7 needs two of them out of band

Section 2.3's table sources `plane_layout_version`, `element_type`, and `format_version` from the
container's own parameters. In the arm they are the module's **constants**
(`kv_plane.align:890-893` at this head, `:864-867` before D19's guard: `PLANE_LAYOUT_VERSION`,
`ELEMENT_TYPE_F32`, `FORMAT_VERSION`, and `KEY_VERSION` beside them), not values read from a file
— which is correct for a *miss*, where no container exists yet, and is a real narrowing on a
*hit*, where the arm keys on what it believes rather than on what the file says.

**The compensating check is shipped and is worth naming, because it is what makes the narrowing
safe:** `scripts/kv_plane_reader.py` binds all three from the **container's decoded header**
(`:307-309`, out of `decode_header`'s `format_version`, `element_type`, and `plane_layout_version`)
and derives the key from those, then asserts the file it was handed is named for it. So the
constants are checked against real header bytes in another language, by the leg of oracle D that
does not share the arm's assumptions — and mutant 1 (a preimage field dropped in the reader) is the
standing regression for that leg. A container whose header disagreed with the arm's constants would
also be refused by L1–L14 before it could be served, so the store cannot serve one; what the reader
adds is that it cannot be *named* for one either.

**Section 2.7's "the key is recomputable from the document alone" is therefore too strong, and the
correction is small.** The document publishes the three digests, `pack_total_bytes`, `token_count`,
`plane_layout_version`, `format_version`, and `KV_WIDTH`. It publishes neither `element_type` nor
`key_version` — the `kv` block has no field for either. Both are supplied **out of band** by the
recomputing implementation as the contract's constants, `0` and `1`, which is exactly what
`scripts/run-layer-forward-smoke`'s and `scripts/run-decode-step`'s preimage implementations do.
The accurate statement is: **the key is recomputable from the document plus section 2.3's two
constant slots**, and a `key_version` bump is by construction not recomputable from an old document
— which is the point of having the field. Oracle D is unaffected: it asserts agreement between three
implementations of one table, and the two constants are part of that table.

### D19 — `derive_key` bounds its two narrowed scalars from above as well as below

Section 2.8 and D2 record `derive_key`'s fail-closed empty string. The shipped function checked
`kv_width` and `token_count` for negativity only, while the preimage narrows both to **four bytes**
(`as u32`, offsets 104 and 108). A value at or above 2^32 would have been silently truncated, so two
runs whose widths differ by exactly 2^32 would have addressed one container — the one failure mode a
content-addressed store must not have.

**Applied:** `if kv_width > U32_MAX || token_count > U32_MAX { return "".clone() }` in
`src/kv_plane.align`'s `derive_key`, beside the existing negativity guard, with `U32_MAX` a private
constant beside `I64_MAX`. `pack_total_bytes` needs none: it occupies eight bytes and is already
non-negative.

D2's claim that no input reaches the empty string still holds and is now a property of the guards
rather than of the callers: L0 runs after step 6a, so `kv_width` is bounded by `MAX_ATTENTION_WIDTH`
and `token_count` by `MAX_PREFILL_TOKENS` before the key is derived. The guard is what keeps that a
proof rather than a habit, and widening the slots remains a `key_version` change.

### D20 — the shipped row count, and what section 13.2's two counts include

Three counting statements need correcting together, because they are one confusion.

1. **Section 5.3 predicts "about 24 new rows"; sixteen shipped as golden rows** — the six
   `STORE_CASES` and the ten `STORE_REFUSALS` — alongside `ds-store-teardown` and the five
   key-determinism cases, which carry no golden row at all. The prediction counted section 5.1's
   and 5.2's named rows as documents; five
   of them became assertions instead (D9) and several 5.2 names are one document asserted from two
   sides. Sixteen is the number `scripts/decode-step-golden.jsonl` grew by (141 → 157), and section
   13's counts are the shipped ones.
2. **D9's `BOUNDARY_CASES` analogy is inexact in the direction that matters.** `BOUNDARY_CASES` run
   and are asserted without a golden row, which is the precedent D9 claims — but they **are** counted
   in the smoke's "documented cases" total (`len(ORDER) + len(BOUNDARY_CASES)`). The five
   key-determinism cases are in neither list: they are run, asserted, and counted in **neither** the
   documented total nor the golden total. So section 13.2's `159 documented (157 with a golden row)`
   understates what the block runs by exactly those five, and the "16 store cases" line counts only
   `STORE_CASES + STORE_REFUSALS`. Both numbers are correct for what they name; this entry is what
   they name.
3. **Section 5.1's `ds-store-key-document` did not ship under that name.** The document-derived key
   is asserted inside the `ds-store-miss` and `ds-store-hit` rows — `key_from_document(document) ==
   document["store"]["key"]`, oracle D's second leg — and the label `ds-store-key` names the
   *distinctness* check over the five preimages. Nothing is missing; one row's worth of assertions
   lives under two existing names.

### D21 — the Align request register runs 1–51 at this base, and 53 is still the number claimed

Section 8 records "the register runs 1–52 (52 is item 31's `Option` partial move) and the next free
number is **53**". At this branch's base `docs/align-requests.md` runs **1–51**: 52 is *expected*
from the parallel item-31 branch and is not present, which is why the section reserves it and takes
53 rather than 52. The reservation and the number this capability claims are both unchanged and
correct; only the description of the base is. Section 8's standing instruction is unaffected and
still binds: **both numbers must be re-checked when this branch merges `origin/main`** — by
`git merge`, never a rebase — and if the register has moved, Request 53 and every cross-reference
move with it.

---

## 13. Result

### 13.1 What shipped

`--decode-step` takes a sixteenth operand. The arm derives one key, addresses one file, and every
line after L0 is the load path or the save path this arm already shipped. The container format is
byte-unchanged and the qualification proves it by digest rather than by diff.

| Surface | Shipped |
| --- | --- |
| Operand | `STORE` at `args[15]`; arity set `{5,6,7,9,10,11,12,13,14,15,16}`; `-` is absent |
| Key | `crypto.sha256` over section 2.3's 152-byte preimage, in `kv_plane.derive_key` (D2) |
| Store | `<STORE>/<64 lowercase hex>.akvp` in a directory the caller creates |
| Refusals | **no new code**: `R6_KV_ARGS store[with_save]` / `store[with_load]`, `R6_KV_UNWRITABLE store[create]`, `R6_KV_CLEANUP_FAILED store[cleanup]` (D16), and every L1–L14 code unchanged on a broken container at a key path |
| Document | schema **6**, a six-field `store` object in every document, **no path** |
| Modules | `kv_plane` (+2 functions, 4 constants), `decode_step` (operand, 2d, L0, `render_store`), `model_forward` (+5 `Outcome` fields, D1). `model_forward`'s graph, `layer_qwen2`, `layer_olmoe`, `ggml_spike`, `ggml_ffi`, and both shims are **byte-unchanged**; `MAX_PREFILL_TOKENS` is still 32 |
| Makefile | **untouched.** No target, no aggregate membership, and no check topology moves |

### 13.2 The hosted owner — `gmake layer-forward-smoke`

`PASS`. The decode-step block reports **13 no-document cases, 159 documented cases (157 with a
golden row), 42 codes reached**, and the store block reports:

```text
decode step smoke: prefix key -- 16 store cases, oracle K byte-identical on 3 hit/miss pairs
outside 20 excluded groups, oracle D agreeing three ways over one 152-byte preimage, oracle S
byte-identical on both the hit and the miss leg against the single-shot run, 5 keys distinct on one
changed field each, a keyed container byte-identical to KV_SAVE's, 10 refusals each naming its own
detail, and three hit-but-broken containers refused rather than re-prefilled
```

**What those two counts include is D20**, because they do not include the same things: the five
key-determinism cases run and are asserted in **neither** total, and "16 store cases" is
`STORE_CASES` plus `STORE_REFUSALS` and nothing else.

- **Oracle K** holds on three pairs — plain, `+SUFFIX`, and `RESIDENT=weights` — with the witness
  assertion proving the exclusion list did not empty the comparison.
- **Oracle D**'s three agreements hold: the arm's `store.key`, the key recomputed from the
  **document's** published digests, and `scripts/kv_plane_reader.py`'s key derived from the
  **container's** own header and identity record, which also asserts the file is named for it. On
  this fixture the key is `ab1a4ebfaba7c82973c3877f96a6d98891dfe384d68098d0efd13a2296ce7dd8` and the
  container is **4,608 B**, section 2.3.5's synthetic row.
- **Five keys, five preimages**: changing one token id, `KV_WIDTH`, one byte of the geometry file, or
  the pack's stored source digest each produces a different key; a run from a different working
  directory with a different `STORE` and a different `DOCUMENT` produces the **same** key and a
  byte-identical container.
- **`STORE` ≡ `KV_SAVE` / `KV_LOAD`**: the keyed miss's document equals `ds-kv-save-ok`'s and the
  keyed hit's equals `ds-kv-load-ok`'s outside the `store` object; the keyed `+SUFFIX` hit equals
  item 33's `ds-suffix-1`; and the container's SHA-256 equals the `KV_SAVE` container's.
- **`ds-store-suffix-vs-kv-save`** — the row D14 exists for: the container a keyed miss **with a
  suffix** writes is byte-identical to the one `ds-suffix-save-prefix` writes for the same prefix,
  and the independent reader accepts it. This is what pins *when* a miss saves.
- **Oracle S holds on both legs** (3.3): the keyed `+SUFFIX` miss and hit are each byte-identical
  to the single-shot prefill of `TOKENS ++ SUFFIX`, outside item 33's own set plus the `store` block
  and **one** added field. That field is `weights.wrap_count`, and it gets a compensating assertion
  rather than a quiet addition: a **miss** wraps exactly one extra graph set — `n_layer + 2` graphs,
  its own prefix prefill — because a *load* run builds no prefill graph at all, which is why item
  33's own pairs never met this. The identity `miss == single + (n_layer + 2)` and `hit == single`
  is asserted exactly, hosted and on the real model.
- **Oracle R** holds between `ds-store-hit` and `ds-store-resident-hit`.
- **The refusal matrix is complete**: every row of section 2.6 has a case that reaches it, each
  asserting code, detail, and what `store` publishes while refusing — including
  **`ds-store-suffix-unwritable`** (D16), which reaches W5 from the call site D14 moved and asserts
  by `suffix.requested: 1` with `completed: 0` and `graph_count: 0` that the arm refused **before**
  the suffix pass, under the **prefix**'s key. W5's second mapping, `store[cleanup]`, is asserted by
  inspection: D16 records why no fixture on this pin can reach it.
- **`scripts/run-decode-step`'s own preimage implementation — oracle D's third leg on the real model
  — was cross-checked against the hosted golden documents before the model ran**: it derives
  `ab1a4ebf…` for `ds-store-miss` and `ds-store-resident-hit` and `f8881c20…` for
  `ds-store-suffix-hit`, matching the arm's published `store.key` in all three.

### 13.3 Golden movement, verified mechanically

`scripts/decode-step-golden.jsonl` goes **141 → 157** rows. A script compared every pre-existing row
against its predecessor field by field: **all 141 differ only in the document's own `schema_version`
5 → 6** — the container header's separate `document_schema_version` stays 3, which is D15 — **plus
the added default `store` object**, no row is removed, and the surviving order is unchanged. The five
other decode-step-family goldens — `layer-forward`, `model-forward`, `gpu-forward`,
`moe-layer-forward`, `moe-model-forward` — and `moe-decode-step-golden.jsonl` are **byte-unchanged**
after a full regeneration — as is `ggml-spike-golden.jsonl` — which is D1's assertion that no other
arm's document moved: seven of the eight golden corpora are byte-unchanged.

The store's golden surface is digests and integers only and is therefore platform-independent by
construction (5.3): no case adds activation bytes, and every store row's prefill is at most three
tokens.

### 13.4 Ledger mutants — five run, five dead, all at the final head

| Mutant | Result |
| --- | --- |
| One preimage field dropped in **one** implementation (`element_type` in the reader) | **DIED** — `ds-store-key-name: the independent reader refused the stored container: REJECT KEY: the container is named ab1a4ebf… and derives the key 7c3fdc0b…` |
| **A hit treated as a miss** (`store_hit = false`) — the silent re-prefill | **DIED** — `ds-store-hit` reports `outcome: "miss", saved: 1`, and, more sharply, all three hit-but-broken rows go from a refusal to `error_code: ''`: the mutant **overwrote** the corrupt, the wrong-tokens, and the wrong-pack containers instead of refusing them |
| **A wrong-key file accepted** — the key stops depending on the token stream | **DIED** — the miss writes `374a7ffe…` where the block derives `ab1a4ebf…`, and the three broken containers are again accepted rather than refused |
| **The path published** in the document (`store.key` set to `<STORE>/<key>.akvp`) | **DIED** — `store.key is '/var/folders/…/store/ab1a4ebf….akvp'` on every store row; the golden would have become a function of `mktemp -d` |
| **A miss with a suffix saves after the pass** — D14's own defect, re-injected | **DIED** — `ds-store-suffix-vs-kv-save: the keyed container is 4c6619ae… and the KV_SAVE container of the same prefix is 36405c8a… — the miss persisted the wrong plane`, and `the independent reader refused the keyed prefix container: REJECT ZEROTAIL: layer 0 k has a non-zero column at or above column 2` |

All five were re-run at the final head after the last edit, and the clean tree reports **0**
failures against their **2, 23, 9, 39, and 2**. The second and third are the two the design is most
afraid of, and both are caught by the hit-but-broken rows rather than only by a digest comparison —
which is why those rows exist. The fifth is D14's own defect, which the implementation shipped first
and these assertions caught.

**Two were re-injected at the repair head and both died again**, because the repair touched the two
things they test — the writer's refusal details and the preimage. Re-injecting D14's defect
(`store_prefix_save := false`) fails `ds-store-suffix-vs-kv-save` on both digests and on the reader's
`ZEROTAIL`, as before, and now fails a **third** way: `ds-store-suffix-unwritable` reports
`suffix.completed: 1` with `graph_count: 4`, catching the ordering directly rather than through the
container it produced (D16). A `KEY_VERSION := 2` mutant — the arm's preimage moved and the other two
implementations left alone — dies on oracle D's document-derived leg in both directions
(`fdccf8a7…` published against `ab1a4ebf…` recomputed) and takes the three hit-but-broken rows with
it: at a key the broken containers are not stored under, all three become misses that write, which is
mutant 2's signature and the reason those rows exist.

### 13.5 Verification commands and results

```text
gmake build                    ok
gmake check                    ok: checked 31 unit(s) per-unit (214-254 s over two runs)
gmake layer-forward-smoke      PASS - 13 no-document, 159 documented (157 golden) cases, 42 codes,
                               oracle K on 3 pairs, oracle D three ways, oracle S on both store
                               legs, oracle R on the resident pair, 5 distinct keys, the refusal
                               matrix complete, and every prior block unchanged (62-70 s)
gmake ggml-spike-smoke         PASS - 7 no-document, 43 documented cases, olmoe claim surface
gmake alignpack-smoke          PASS - 27 positive fixtures, 128 negative sources, 20,306
                               assertions; run as a neighbour check because this capability edits
                               the module that owns container identity
gmake gate-topology-check      PASS
gmake fmt                      leaves no diff
gmake format-check             PASS
git diff --check               clean
```

`gmake ci` is **not** selected: no aggregate membership, no check topology, and no integration
behaviour moves. No platform profile is selected: no target-local boundary moves and no
target-specific claim is made.

### 13.6 The real-model qualification — `gmake decode-step-qualification`

**Not run: the host never freed.** The leg is implemented, its analysis block is dry-run (below), and
the run was armed to fire automatically the moment the host cleared — it never did. Host memory was
polled from **18:30 to 20:01, ninety-one minutes**, against this session's 6 GB coordination floor;
available memory measured **3.2 to 4.97 GB** the whole time and never reached the floor, while
concurrent Docker-in-Docker preflight containers from other work on the same box went from one to
three and back to two. No process was killed and nothing was run below the floor: the reference model
is 4.68 GB and both instruments load it, so a run at 3.7 GB would have measured the swap rather than
the store.

Nothing about the implementation is waiting on this, and the hosted owner is the capability's own
narrow owner. **This is the focused qualification, it is the last piece of section 3.5's acceptance
rule, and it must be run — and its result recorded here — before the pull request.**

What it will assert, per prompt of the persistence leg's four, at the suffix leg's first split
(D7, D8):

- a keyed **miss** — prefill the prefix, save under the derived name, suffix pass, `N` steps — then a
  keyed **hit** in a separate process, both timed with the runner's own `time_invocation` wrapper;
- **oracle K** between them, over oracle Q's exclusion set plus the store's three moving fields, with
  the same vacuity guard the hosted block uses;
- **oracle D**'s document-derived leg in a third implementation of the preimage, plus
  `scripts/kv_plane_reader.py --check-name` against the container's own bytes;
- **oracle S** on **both** legs against the single-shot run of the whole prompt, with D13's
  compensating `weights.wrap_count` identity;
- **gate G1** — `oracle_logits: IDENTICAL` against `llama-debug --save-logits` — on both legs;
- **oracle B** — `plane.roundtrip_verdict: IDENTICAL` — on both legs;
- the store holds **exactly one** file and it is named for the key the document published;
- the container is **byte-identical** to the `KV_SAVE` container the suffix leg wrote for the same
  prefix — the real-model half of D14's regression;
- `first_token_ns`, the invocation wall clock, and `store.lookup_ns`, all printed as
  `DIAGNOSTIC`, with **no rate, speedup, or per-token figure derived and no TTFT claim**.

**The analysis block was dry-run before the model run, and it is not merely written.** Its three
`N/A` paths (`ALIGN_LLM_STORE_PROMPTS=0`, `ALIGN_LLM_SUFFIX_SPLITS=0`, and no documents) each exit 0
with an explicit line; and driven over the **hosted golden documents** — `ds-store-suffix-miss` as
the miss, `ds-store-suffix-hit` as the hit, `ds-kv-args-dash-dash` as the single-shot comparand, and
`ds-suffix-1` as the explicit `KV_LOAD` run — it reports

```text
R6PK case1 key f8881c20575590e4 oracle K IDENTICAL, oracle S IDENTICAL on both legs, gate G1
IDENTICAL on both legs, oracle B IDENTICAL over 1152 bytes, container 4608 B
```

with **one** failure, and it is the expected one: those hosted rows carry no `LOGITS` blob, so
`oracle_logits.present` is false and the gate-G1 assertion fires. The real-model leg supplies the
blob `llama-debug --save-logits` wrote. Oracle K, oracle S on both legs, oracle D's document-derived
key, oracle B, the store-object invariants, and the keyed-hit-versus-explicit-`KV_LOAD` comparison
all pass on real documents before a single model run.

---

## 14. Ledger and closure matrix to the final diff

Every applicable cell of sections 2 and 4, mapped to the code that implements it and the evidence
that runs it. Cells the ledger marked `N/A` keep that disposition and are not repeated.

### 14.1 The public-contract ledger (section 2)

| Ledger row | Diff | Evidence |
| --- | --- | --- |
| 2.2 `STORE` at `args[15]`, `-` for absent | `decode_step.align` `run` (`store_text`, the sixteenth `valid_path` guard) | `ds-store-*` (16 operands), `ds-store-path-empty` (`NO_DOCUMENT`) |
| 2.2 arity `{5,…,15,16}`, 8 refused, 17 refused | `decode_step.align` `run` (`count > 16`) | `ds-arity-3`, `ds-arity-8`, `ds-arity-17` |
| 2.2 mutual exclusion with `KV_SAVE` / `KV_LOAD` | `execute` step 2d, both details in operand order | `ds-store-with-save`, `ds-store-with-load`, `ds-store-with-save-bad-steps` |
| 2.2 `SUFFIX` legal with `STORE` (the recorded reversal) | `execute` step 2c, widened | `ds-store-suffix-miss`, `ds-store-suffix-hit`; `ds-suffix-no-load` still refused |
| 2.2 `STORE` without `SUFFIX` is legal | the same path with `suffix_count == 0` | `ds-store-miss`, `ds-store-hit` |
| 2.2 no defaults added; `-` at 16 ≡ 15 | `run`'s `if count >= 16 … else "-"` | the whole 141-row golden re-baseline is default `store` |
| 2.2 the hazard closed by publishing | `render_store`, called from `render` unconditionally | `record()`'s store-object assertion on **every** case |
| 2.3 the 152-byte preimage, field for field | `kv_plane.derive_key` (D2 for the signature) | oracle D three ways; the four one-field-changed keys |
| 2.3 `key_hex`, `path` | `kv_plane.store_path`, `KEY_HEX_BYTES` | `ds-store-key-name`; the store holds exactly `<key>.akvp` |
| 2.3 `crypto.sha256`, never `hash64` | `derive_key`'s two `crypto.sha256` calls | reader parity (a second `hashlib.sha256` implementation) |
| 2.4 the arm never creates, lists, or deletes | no `create_dir`/`read_dir` call exists; the smoke creates every store | `ds-store-unwritable` asserts the directory is **not** created |
| 2.4 `akvp` v1 byte-unchanged | `kv_plane`'s writer/reader/header plan untouched in the diff | `ds-store-vs-kv-save` (SHA-256 equality), and on the real model |
| 2.4 other files in the store are ignored | the arm addresses one path and never enumerates | the three broken-container directories keep exactly their file |
| 2.5 hit → L1–L14 → suffix → loop; miss → prefill → writer → suffix → loop | `execute`'s L0 + `schedule_decode` unchanged | oracle K on three pairs; `ds-store-no-suffix-*`, `ds-store-suffix` |
| 2.5 **a miss is only a missing file** | no branch turns an L1–L14 failure into a miss | `ds-store-hit-corrupt-plane`, `-wrong-tokens`, `-wrong-pack`; mutants 2 and 3 |
| 2.6 step 2d, both details | `execute` | `ds-store-with-save`, `ds-store-with-load` |
| 2.6 2d precedes the numeric parse | 2d sits above `stage_inputs` | `ds-store-with-save-bad-steps` |
| 2.6 L0 follows step 6/6a | L0 sits after `stage_inputs` and the pack identity read | `ds-store-narrow-width` (`key: "-"`, `outcome: "absent"`) |
| 2.6 W5 `R6_KV_UNWRITABLE store[create]`, one code for three causes | `save_plane`'s `store_mode` branch | `ds-store-unwritable`, `ds-store-file-not-dir`, `ds-store-suffix-unwritable` (the moved call site, D16) |
| 2.6 W5's second mapping, `R6_KV_CLEANUP_FAILED` → `store[cleanup]` (D16) | the branch beside it | inspection — unreachable by fixture at this pin, with `R6_KV_WRITE_FAILED` (D16) |
| 2.6 W5 is reached only after the prefill | the writer runs at its existing position | both rows publish `plane.source: "PREFILL"` |
| 2.7 schema 6 and the six-field `store` object | `SCHEMA_VERSION`, `render_store`, `render` | `STORE_FIELDS` set assertion on every document |
| 2.7 `key` is `"-"` before L0; `saved` only on a complete write | `render_store` + `schedule_decode`'s `store_saved` | `record()`'s four store invariants; the refusal matrix |
| 2.7 **no path published** | `render_store` writes no path field | mutant 4 |
| 2.7 the key is recomputable from the document **plus section 2.3's two constant slots** (D18) | the same digests `render_kv` already published; `element_type` and `key_version` supplied as the contract's `0` and `1` | oracle D's document-derived leg |
| 2.8 `derive_key` is pure; one 152-byte buffer | `kv_plane.derive_key` (D2) | it compiles at this pin beside Request 49's refusal |
| 2.8 no new I/O and no new large digest | the three digests are the run's own | no new `pread` in the diff |
| 2.8 single writer | declared; the window is D6 and Request 30's third client | recorded, not simulated (4.10) |
| 2.9 `store.outcome` primary and exact; `lookup_ns` diagnostic | `render_store`; `normalize` zeroes only `lookup_ns` | oracle K excludes the clock and keeps the key |
| 2.11 exact-prefix only | `derive_key` takes the whole `TOKENS` stream; L13 unchanged | `ds-store-hit-wrong-tokens` |

### 14.2 The closure matrix (section 4)

| Cell | Diff | Regression |
| --- | --- | --- |
| 4.1 construction | `run`'s guard and path check | `ds-arity-17`, `ds-store-path-empty` (D12) |
| 4.1 malformed input (2d, 2c) | `execute` | `ds-store-with-save`, `ds-store-with-load`, `ds-suffix-no-load`, `ds-store-suffix-*` |
| 4.1 success — hit / miss | `execute`'s L0 + unchanged paths | `ds-store-hit*`, `ds-store-miss*` |
| 4.1 failure — L1–L14 at a key path | no code change; the refusal stands | the three hit-but-broken rows |
| 4.1 failure — create | `save_plane`'s `store_mode` | `ds-store-unwritable`, `ds-store-file-not-dir`, `ds-store-suffix-unwritable` |
| 4.1 failure — `R6_KV_EXISTS` between `fs.exists` and the create | **not reachable single-process** (4.1's own disposition) and not reachable concurrently either (D6) | inspection + `ds-kv-save-exists` |
| 4.1 early exit | every refusal above L0 publishes `store.requested` | `ds-store-narrow-width`, `ds-store-with-save-bad-steps` |
| 4.1 cleanup | `store_path_owned` and the preimage buffer at scope end | oracle B's balance invariant, unchanged |
| 4.1 document | `render_store` in `render` | the whole corpus re-baselined and checked mechanically |
| 4.2 `derive_key` construction/success/cleanup | `kv_plane.align` | oracle D and the determinism rows |
| 4.2 malformed input `N/A` | fail-closed empty string, unreachable | recorded, not tested — as the ledger says |
| 4.2 the writer, reader, header plan, bounds unchanged | absent from the diff | `ds-store-vs-kv-save` |
| 4.3 / 4.4 / 4.6 byte-unchanged | `model_forward` gains five `Outcome` fields only (D1); the rest are absent from the diff | seven of the eight golden corpora byte-unchanged after a full regeneration |
| 4.5 the reader learns the name | `kv_plane_reader.py` (`derive_key`, `KEY`, `--check-name`) | `ds-store-key-name`, the renamed-container row, mutant 1 |
| 4.7 `layer_forward_fixture.py` unchanged | absent from the diff | the store rows reuse item 33's synthetic pair |
| 4.8 the sixth smoke block | `run-layer-forward-smoke` | 15 golden rows plus `ds-store-teardown`: every store directory holds **only** `<64-hex>.akvp` names, the arm created no directory of its own, and it replaced no caller-owned path; the directories go with the runner's `mktemp -d` tree |
| 4.9 the real-model leg | `run-decode-step` (the shell leg and a third analysis block) | section 13.6 |
