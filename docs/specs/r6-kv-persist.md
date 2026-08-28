# R6-KV-PERSIST

Status: implemented and verified, 2026-08-29. Sections 5.5 to 5.7 record the results and section 11
maps every ledger row to the diff.

Stacked on `R6-STEP-N` (`docs/specs/r6-step-n.md`), whose review repair `6ca1eef` is merged into
this branch by `git merge` — never a rebase — and which is itself stacked on `R6-DECODE-KV-STEP1`
(`docs/specs/r6-decode-kv-step1.md`, `1671810`). Those two documents are the ledger this one
extends; a row either of them settled and this one does not restate is still in force, and
"unchanged" below means unchanged **from them**.

## 1. Purpose, boundary, and the gate

### 1.1 What this capability is

R6-STEP-N decodes `N` greedy steps over an Align-owned KV plane, in one process, from a prefill it
computed itself. The plane is 29,360,128 B at `KV_WIDTH` 256 on the dense Qwen2.5-Coder-7B, it is
correct — oracle B is `IDENTICAL` at every step over `114,688 · Σ(T+k)` bytes on four prompts — and
when the process exits it is gone. Every later invocation on the same prompt recomputes it.

This capability ships the smallest change that makes the plane outlive the process that built it:

- **Save.** `--decode-step` gains a `KV_SAVE` operand. After the prefill completes and its plane
  readback verifies, the arm writes an **`akvp` v1** container holding the plane, the prompt's token
  ids, the prefill's last-position logit vector, and an identity record that binds all three to the
  exact pack, geometry, width, and layout that produced them.
- **Load.** `--decode-step` gains a `KV_LOAD` operand. Given a container, the arm **skips the prefill
  entirely**, validates every identity field against the run it was asked for, fills its plane from
  the file, and runs the same N-step loop from `n_past = T`.
- **The oracle is that the two are the same run.** A fresh process loading a saved plane must decode
  the same `N` token ids, and must publish a document byte-identical to the in-process path outside
  one named exclusion list — plus R6-STEP-N's existing gate G, oracle B, and oracle C′, which carry
  forward and apply to both processes.

**What loading does *not* avoid, stated first because everything in section 1.4 follows from it.** A
load run still opens the pack and still streams the whole weight set once per decode step: the
embedding gather and every layer graph read from `PACK`, exactly as before. Loading removes **one
prefill pass** — its compute and its one weight sweep — and nothing else. `PACK` therefore stays a
mandatory operand on a load run, and the saving is bounded above by the cost of one prefill.

### 1.2 Why the design gate fires

**All four** of `CLAUDE.md`'s triggers fire, and this is the first R6 capability for which the
fourth is true rather than arguable. The table below is the count: four rows, four `Yes`.

| Trigger | Fired | Why |
| --- | --- | --- |
| Public CLI or API surface | **Yes** | `--decode-step` gains two operands and its arity set grows to {5, 6, 7, 9, 10, 11, 12, 13}; a new public module `src/kv_plane.align` exports the container's encode/decode surface |
| Persisted or exchanged format | **Yes, twice** | The `akvp` v1 container is a **new persisted format** with its own identity, schema, and validation order; and the `R6_DECODE_STEP` document goes to **schema 3** |
| Ownership / process / network boundary | **Yes** | R6 section 2.9 records "N/A — nothing is persisted" and R6-STEP-N repeats it. That row is now false. The plane crosses a **process boundary** through a file: one process owns and frees it, a different process reconstructs it, and the two are bound only by bytes on disk |
| Coordinated invariant across ≥ 3 modules | **Yes** | The plane's layout — layer-major, K then V per layer, `stride = kv_width · n_head_kv · head_dim · 4`, columns with `head_dim` fastest — is today an invariant private to `src/decode_step.align`. Persisting it publishes it, and `src/kv_plane.align`, `src/decode_step.align`, `scripts/kv_plane_reader.py`, and `scripts/layer_forward_fixture.py` must now agree on it byte for byte |

R6-STEP-N withdrew the fourth trigger with a reason (section 10.8: the invariant was R6's and
unchanged, only its consumers moved). Here the invariant itself changes status — from a private
convention to a published contract with an independent second reader — so the trigger is claimed,
and section 4's closure matrix is required rather than voluntary.

### 1.3 Declared boundary

**In scope.** Dense Qwen2.5-Coder-7B Q4_K_M; CPU only; a container holding **one** prefill plane at
one `KV_WIDTH` for one prompt; save-after-prefill and load-instead-of-prefill on the existing
`--decode-step` arm; a complete refusal matrix over a malformed, mismatched, or foreign container;
an independent Python reader; determinism of the writer proved by double-write digest equality.

**Out of scope, declared non-goals.**

- **Any durability claim.** Align has no `fsync` at this pin (section 8, Request 31). Section 7 states
  the limitation and section 6 risk 6 states what a torn file costs.
- **Any cache.** The container is a caller-named artifact at a caller-named path. There is no cache
  directory, no key derivation, no lookup, no eviction, no generation counter, no reuse policy, and
  no garbage collection. `R6_KV_*` refuses a mismatch; it never silently re-prefills.
- **Appending to, growing, or updating a saved plane.** A container is written once, whole, and is
  read-only afterwards. Saving the *post-loop* plane at `T + N` columns is deferred (section 7).
- **Prefix sharing.** Two prompts sharing a prefix get two containers with two identities. The
  longest-common-prefix question the R6 roadmap gate actually asks is a different capability with a
  different key and a different invalidation story.
- **Tiering, invalidation, session management, NVMe or GPU residency of the plane, a quantized
  plane, the Metal arm, OLMoE, batch above one, a growing `KV_WIDTH`.** Unchanged non-goals.
- **Any TTFT or throughput *claim*.** Section 1.4 and section 2.9 record a labelled **diagnostic**;
  no acceptance decision is taken from it and no roadmap gate is discharged by it.

### 1.4 The TTFT question, answered rather than claimed

`docs/specs/roadmap.md`'s R6 gate is one sentence: 同一prefixを使う反復coding taskでTTFTが改善する
こと — *TTFT improves on repeated coding tasks that share a prefix*. It sits under a five-line list:
session KV, repo stable prefix KV, DRAM tier, NVMe tier, invalidation. **This capability ships the
first of those five and does not discharge the gate.** Four reasons, each concrete:

1. **There is no prefix-sharing corpus.** The four qualification prompts are independent code
   fragments at `T ≤ 6`. "Repeated coding tasks sharing a prefix" needs a corpus in which a long
   stable prefix — a repository preamble, a system prompt, a file header — is followed by varying
   suffixes, and a key that finds the saved plane for that prefix. Neither exists. Measuring TTFT on
   a corpus that does not exhibit the property the gate names would be a number about nothing.
2. **Wall time is dominated by weight streaming, not by prefill.** R6-STEP-N section 5.4 measured
   4,370,560,992 B of pack `pread` **per decode step** and compute at 3.5 %, 10.6 %, and 16.7 % of
   elapsed at `N ∈ {1, 4, 16}`. A load run removes one prefill pass and keeps every per-step sweep,
   so the saving is bounded above by roughly one step's worth of the dominant term. Reporting that
   as a TTFT improvement would advertise a 6 % effect as the answer to a gate about prefix reuse.
3. **The page cache confounds the measurement on this host.** The second read of a 29 MB file on a
   warm host is a memory copy. Any honest figure needs a cold-cache protocol this capability does not
   own, and R6-STEP-N already records that its own timings moved by 20–40 % between two runs of the
   same head on a contended host.
4. **Four of the five listed mechanisms are absent.** With no tiering, no invalidation, and no
   session or prefix key, a saved plane is only ever found by a caller who names its path — which is
   a developer running a script, not a coding loop.

**What is measured instead, as characterization.** Two numbers, both labelled diagnostic, both
reported as a range over three runs on one host, with **no per-token, per-second, or speedup figure
derived from either**:

- `timings.first_token_ns`, published by the arm: the interval from `execute`'s first
  `time.instant()` to the instant step 1's argmax is available. It is the arm's own
  prefill-plus-first-step versus load-plus-first-step, measured inside one process, with the pack
  open and the geometry parsed on both sides.
- The runner's wall clock of the whole `ggml-spike` invocation at `STEPS = 1`, with no transcript and
  no logits blob, as the outer bound that includes process start, `dyld`, and the pack open.

**A fifth reason, found while implementing, and it points the same way.** `REFERENCE` has no `-`
form — the convention `TRANSCRIPT` and `LOGITS` use was never extended to it — so at thirteen
operands the model is always supplied, and R5B's byte comparison of every member against it lives
inside the **prefill pass**. The save direction therefore pays for a whole second sweep of the
4.68 GB GGUF that the load direction has no prefill to run. The difference between the two numbers
**overstates** what loading saves, and the runner prints that sentence beside them so the figure
never travels without it.

The analysis this design starts from argued for shipping with no timing at all, on the grounds that
a TTFT figure on a host where four fifths of elapsed is pack re-reads invites exactly the misreading
`CLAUDE.md`'s performance row exists to prevent. That argument is accepted in substance and narrowed
rather than adopted whole: the numbers are **reported** because a capability whose whole point is to
skip work should say how much work it skipped, and they are **not claimed** because the four reasons
above say why they cannot bear a claim. `CLAUDE.md`'s performance row is therefore **not selected**:
no cost ceiling is recorded in a ledger row and no benchmark gates this capability.

## 2. Public-contract ledger

Every surface below is exact. Fields marked `N/A` carry their reason.

### 2.1 The surface decision: two more operands on one arm

The alternatives were a second and third arm (`--kv-plane-write` / `--kv-plane-read`), and a single
`KV_PATH` operand with a mode word. Both are rejected, with reasons, because the decision is
load-bearing for every row below.

| Consideration | `--decode-step` + `KV_SAVE` + `KV_LOAD` (**chosen**) | Separate `--kv-plane-*` arms | One `KV_PATH` + a mode word |
| --- | --- | --- | --- |
| Code paths for the prefill and the loop | One. A save run *is* an ordinary run that also writes; a load run *is* an ordinary run whose prefill was replaced. "Loading still decodes correctly" is a property of the same loop, not of a second one | Two arms that must both build a plane, both size a node window, and both run a loop. R6-STEP-N section 2.1 rejected a second arm for exactly this reason and its reasons have not weakened | One, but the mode word is a fourth thing to validate and its two values change which operands are meaningful |
| The copy debt R6 section 10.6 records | Unchanged | Multiplied. Seven functions are already copied because Align Request 49 forbids the cross-module call; a fork forks the copies | Unchanged |
| Goldens | `scripts/decode-step-golden.jsonl` is rewritten at schema 3 — this capability's own file, exempt per R6 section 10.4 | A second golden file to maintain forever, and a second document kind | Same as chosen |
| Oracle cost | The save run and the load run produce **the same document shape**, so "byte-identical outside a named exclusion list" is a one-line comparison | Two shapes; the equality oracle becomes a field-by-field translation, which is where an oracle stops being one | Same as chosen |
| Direction is explicit in the argv | **Yes.** `-` in one position and a path in the other says which direction this run goes, and both paths present is a refusal rather than a copy | Yes | **No.** The mode word can disagree with the operand's meaning, and a reviewer reading a shell line cannot tell direction without the mode |
| Arity cost | Two more positions and one more `-` convention, already inherited by `TRANSCRIPT` (R5B) and `LOGITS` (R6-STEP-N) | None | One more position |

The `--kv-plane-*` names are additionally **not free**: `ds-arm-unknown-flag` exists precisely to
assert that an unrecognised flag is refused with no document, and R6-STEP-N had to rename its
literal once already (`--decode-steps` → `--decode-stepped`) for shipping the name it was testing
against.

### 2.2 The arm and its operands

| Field | Contract |
| --- | --- |
| Surface | `ggml-spike --decode-step` — unchanged; the first operand and nothing else selects the arm |
| Owner module | **Two.** `src/decode_step.align` owns the arm, the operands, the validation order, and the plane's residency. `src/kv_plane.align` (**new**) owns the `akvp` v1 container: its constants, its header and identity encode/decode, its region arithmetic, its digests, and every `R6_KV_*` code that names a container defect. Section 2.7 records why the split falls where it does |
| Operand grammar | `--decode-step PACK GEOMETRY TOKENS DOCUMENT REFERENCE TRANSCRIPT KV_WIDTH LOGITS STEPS KV_SAVE KV_LOAD` |
| Arity | `args.len()` of 5, 6, 7, 9, 10, 11, **12**, or **13**. **8 is still `R6_ARITY`**, for R6's own reason (a transcript without a width refuses itself). 14 and above are `R6_ARITY` |
| `PACK` | `args[2]`. **Mandatory on every run, including a load run** (section 1.1): the decode loop reads the embedding row and every layer's weights from it at every step |
| `GEOMETRY`, `TOKENS`, `DOCUMENT`, `REFERENCE`, `TRANSCRIPT`, `KV_WIDTH`, `LOGITS`, `STEPS` | Unchanged from R6-STEP-N sections 2.2 and 2.3 |
| `KV_SAVE` | `args[11]`, the destination container path, **or `-` for absent**. Absent is the default and is what every schema-2-era invocation means |
| `KV_LOAD` | `args[12]`, the source container path, **or `-` for absent**. Absent is the default |
| Defaults | R6-STEP-N added exactly one (`STEPS` absent is 1). **This capability adds none.** Both new operands are absent-by-default and their absence is the pre-existing behaviour, character for character |
| Both supplied | **`R6_KV_ARGS`**, detail `kv[save+load]`. Not a copy, not save-then-load, not load-then-resave. A run that both restores a plane and persists it is two capabilities sharing one invocation, and the second one would persist a plane it did not compute |
| Both `-` | Legal and identical to the 11-operand form. `args.len() == 12` with `KV_SAVE` of `-` is exactly `args.len() == 11` |
| Environment | **None.** Neither operand has an environment fallback, and no environment variable is read by the arm. The runner's `ALIGN_LLM_*` variables are read by `scripts/run-decode-step`, never by `main` |

`KV_SAVE` precedes `KV_LOAD` because the save direction is the one an ordinary run adds, so the
twelve-operand form is the common extension and the thirteen-operand form is the specialised one.

### 2.3 The `akvp` v1 container

**Endianness: little-endian, everywhere, unconditionally**, and there is **no byte-order flag** — the
alignpack v1 decision (`docs/specs/r4-alignpack-layer-major.md` section 2.4.1) for its reasons: GGUF
is LE, Align ships `_le` accessors, both targets are LE, and a flag would be a second code path with
no producer. **One thing is added that alignpack does not have**: an 8-byte `endian_probe` holding
`0x0102030405060708`, written LE and validated on read. It is a **canary, not a mode switch** — it
cannot select a second decode path, it costs eight bytes, and it converts "a big-endian host
silently mis-decoded every u64 in the header" into one named refusal,
`R6_KV_HEADER("endian_probe")`, before any offset derived from those u64s is used to address a
region. alignpack does not need it because its `total_bytes` versus `f.len()` check catches the same
class one step later; here the same check exists **and** the probe names the cause.

**Region order and alignment.** Header, token stream, identity record, logits, plane — in that order,
each region 8-byte aligned, the plane additionally aligned to `plane_align`, every padding byte
written explicitly and validated as zero, and **no trailing padding**.

Four properties of that order are contract, not incident:

1. **The plane is last, and `plane_offset + plane_bytes == total_bytes` exactly.** This is what makes
   the reader's chunked refill correct: `f.pread` always requests the destination buffer's whole
   capacity (verified at the pin, `crates/align_runtime/src/lib.rs:align_rt_io_file_pread`), so a
   1 MiB transient reading the plane's tail would over-read into whatever followed. With the plane
   last, the tail read is short **by exactly the remaining bytes**, and `f.len() == total_bytes`
   (validated first) makes that a proof rather than a hope.
2. **Every fixed-size region precedes the two large ones**, so a wrong, foreign, stale, or corrupt
   file is refused after reading at most 384 bytes rather than after reading 29 MB.
3. **The plane is `plane_align`-aligned** (4096, the page size on both targets), for alignpack's
   reason: a later `O_DIRECT` read, an `mmap` of the plane region, or a GPU staging upload all want
   it, and it costs a bounded 4095 bytes.
4. **Padding is written, not left as a hole, and it is zero — validated by both implementations.** A
   `pwrite` past the current end extends the file with a zero hole; a sparse file and a dense file
   of the same plane report different sizes to `du`, and a reader validating "padding is zero"
   should validate bytes that exist. One `PAD` buffer of `plane_align` zero bytes is built once and
   each pad is one `f.pwrite` of a sub-slice of it. **No digest covers the gaps**, so "padding is
   zero" is a rule or it is nothing: the arm checks the three gaps at L6 and refuses a non-zero byte
   as `R6_KV_RESERVED("padding")`, and `scripts/kv_plane_reader.py` reaches its own `RESERVED`.
   `ds-kv-padding-nonzero` is the case, and every one of the five digests still recomputes correctly
   on that file, which is what makes the rule load-bearing rather than incidental.

#### 2.3.1 Header — 192 bytes at offset 0

| Offset | Bytes | Type | Field | v1 value / rule |
| --- | --- | --- | --- | --- |
| 0 | 4 | `u8[4]` | `magic` | `0x41 0x4B 0x56 0x50` — `AKVP` |
| 4 | 4 | `u32` | `format_version` | `1` |
| 8 | 4 | `u32` | `header_bytes` | `192` |
| 12 | 4 | `u32` | `identity_record_bytes` | `192` |
| 16 | 4 | `u32` | `element_type` | `0` = f32. The only v1 value |
| 20 | 4 | `u32` | `plane_layout_version` | `1` — section 2.3.4 |
| 24 | 4 | `u32` | `flags` | `0`. No bit is defined in v1; any non-zero bit is `R6_KV_RESERVED` |
| 28 | 4 | `u32` | `plane_align` | `4096`; power of two in `[8, 65536]` |
| 32 | 8 | `u64` | `endian_probe` | `0x0102030405060708` |
| 40 | 8 | `u64` | `total_bytes` | the container's exact byte length; must equal `f.len()` |
| 48 | 8 | `u64` | `token_stream_offset` | |
| 56 | 8 | `u64` | `token_stream_bytes` | `== token_count * 4` |
| 64 | 8 | `u64` | `identity_offset` | |
| 72 | 8 | `u64` | `logits_offset` | |
| 80 | 8 | `u64` | `logits_bytes` | `== n_vocab * 4` |
| 88 | 8 | `u64` | `plane_offset` | multiple of `plane_align`, and equal to the canonical value below |
| 96 | 8 | `u64` | `plane_bytes` | `== n_layer * 2 * kv_width * n_head_kv * head_dim * 4` |
| 104 | 4 | `u32` | `n_layer` | `>= 1` |
| 108 | 4 | `u32` | `n_head_kv` | `>= 1` |
| 112 | 4 | `u32` | `head_dim` | `>= 1` |
| 116 | 4 | `u32` | `kv_width` | `1 <= kv_width <= MAX_ATTENTION_WIDTH` (4096) |
| 120 | 4 | `u32` | `columns_persisted` | `== token_count`; `>= 1` |
| 124 | 4 | `u32` | `token_count` | `1 <= token_count <= MAX_PREFILL_TOKENS` (32) |
| 128 | 4 | `u32` | `n_vocab` | `>= 1` |
| 132 | 4 | `i32` | `prefill_argmax` | `0 <= prefill_argmax < n_vocab` |
| 136 | 4 | `u32` | `document_schema_version` | `3` — the `R6_DECODE_STEP` schema this writer emits |
| 140 | 4 | `u32` | `reserved_u32` | `0` |
| 144 | 48 | `u8[48]` | `reserved` | all zero |

**There is exactly one layout, and it is a format rule.** The region order, `REGION_ALIGN`,
`plane_align`, and the two variable region sizes together determine every offset, so an `akvp` v1
container at a given `token_count`, `n_vocab`, and `plane_align` has one legal layout and no other:

```text
token_stream_offset = header_bytes                                          # 192
identity_offset     = align_up(header_bytes + token_count * 4, 8)
logits_offset       = align_up(identity_offset + identity_record_bytes, 8)
plane_offset        = align_up(logits_offset + n_vocab * 4, plane_align)
total_bytes         = plane_offset + plane_bytes
```

`src/kv_plane.align`'s `plan_header` forms these four on the writing side and its `read_header`
re-derives the same four at L7, and `scripts/kv_plane_reader.py` re-derives them independently. A
file whose regions are merely *containable, aligned, disjoint, and plane-last* — a plane pushed one
whole `plane_align` forward, say — is refused as `R6_KV_REGION("layout")` by both. Accepting it in
one implementation and refusing it in the other would be a format with two meanings;
`ds-kv-region-noncanonical` is the case.

**Why 192 rather than alignpack's 128.** Every field above is load-bearing and they sum to 144; the
remaining 48 bytes are reserve. alignpack v1 shipped a 128-byte header with a single 8-byte reserved
`u64` and section 5.1 of that document already names three deferred fields that would need it. A
192-byte header on a 29 MB artifact costs 0.0002 % and is what lets a v2 add a field without moving
a region offset. `header_bytes` is in the header for the same reason alignpack's is: so a v2 reader
can skip a header it does not fully understand instead of mis-striding the regions after it.

**`columns_persisted` is not `plane.columns_written`.** The document's `plane.columns_written` is
`T + N` after a complete loop; the header's `columns_persisted` is `T`, the prefill's column count,
because section 2.6 writes the container **before** the first decode step. The two names differ
deliberately (section 10, consistency finding 3).

#### 2.3.2 Token stream

`token_count` little-endian `u32` token ids, in prompt order, with no separators — the exact ids the
`TOKENS` operand parsed. At most 128 bytes (`MAX_PREFILL_TOKENS` is 32). It is carried, rather than
recomputed from the `TOKENS` operand at load time, because the container must be able to say *which*
prompt's plane it holds without being handed that prompt: the load path validates the operand
against the file (`R6_KV_TOKENS`), and the independent reader validates the file against nothing at
all.

#### 2.3.3 Identity record — 192 bytes

| Offset | Bytes | Type | Field |
| --- | --- | --- | --- |
| 0 | 32 | `u8[32]` | `source_header_region_sha256` |
| 32 | 32 | `u8[32]` | `geometry_sha256` |
| 64 | 32 | `u8[32]` | `token_stream_sha256` |
| 96 | 32 | `u8[32]` | `logits_sha256` |
| 128 | 32 | `u8[32]` | `plane_sha256` |
| 160 | 8 | `u64` | `pack_total_bytes` |
| 168 | 24 | `u8[24]` | `reserved` — all zero |

**Every digest is `crypto.sha256`. `hash64` appears in no persisted field, ever.** The pinned runtime
says so about itself: `core.hash`'s wyhash is documented "NOT cryptographic (not DoS-resistant, not
a stable on-disk/wire format)" at `crates/align_runtime/src/lib.rs`, and alignpack rejected it for
the same reason. A value persisted into a container must not change when the compiler is rebuilt.

#### 2.3.4 Plane layout, version 1

The plane region is the exact byte image of `src/decode_step.align`'s `buffer(plane_bytes)`:

```text
stride       = kv_width * n_head_kv * head_dim * 4        # plane_stride
plane_bytes  = n_layer * 2 * stride                       # plane_bytes_for
K of layer L at offset stride * (2 * L)
V of layer L at offset stride * (2 * L + 1)
within a tensor: column-major over kv_width columns, each n_head_kv * head_dim f32,
                 head_dim fastest
columns [0, columns_persisted) hold the prefill; columns [columns_persisted, kv_width) are zero
```

`plane_layout_version` is `1` and is a **separate** version from `format_version`, because the two can
move independently: a v2 container could add a region without changing the plane's byte order, and a
future quantized or transposed plane would change the plane's byte order without changing the
container. A reader that understands `format_version` 1 and not `plane_layout_version` 2 must
refuse, which is why the field is validated rather than ignored.

**Columns at and above `columns_persisted` are zero, and that is validated by the writer's own
source, not by re-reading.** The plane buffer is zero-filled at allocation (`prime_window`) and the
prefill writes only columns `0 .. T-1`, so the tail is zero by construction. The independent reader
checks it anyway, because a reader that trusts the writer is not independent.

#### 2.3.5 Measured sizes

| Configuration | `token_stream` | `identity` | `logits` | `plane_offset` | `plane_bytes` | `total_bytes` |
| --- | --- | --- | --- | --- | --- | --- |
| Reference model, `T = 6`, `KV_WIDTH` 256, `n_vocab` 152,064 | 192 + 24 | 216 + 192 | 408 + 608,256 | **610,304** | 29,360,128 | **29,970,432** |
| Reference model, `KV_WIDTH` 1024 | same | same | same | 610,304 | 117,440,512 | 118,050,816 |
| Reference model, `KV_WIDTH` 4096 | same | same | same | 610,304 | 469,762,048 | 470,372,352 |
| Hosted synthetic, `T = 3`, `KV_WIDTH` 8, `n_layer` 2, `n_head_kv` 1, `head_dim` 4, `n_vocab` 32 | 192 + 12 | 208 + 192 | 400 + 128 | **4096** | 512 | **4608** |

The metadata plus padding overhead is 2,048 B at the reference configuration — 0.007 % of the plane
— and 4,096 B on the 512-byte synthetic, where it is 89 % of the file. The synthetic's ratio is
stated rather than hidden: `plane_align` is a fixed cost, it is negligible at any real width, and
the smoke asserts the exact `total_bytes` on both, so a padding change is a test failure rather than
a size change nobody noticed.

### 2.4 Identity — the six fields, and what each one rules out

The container's identity answers one question: *is this file the prefill plane for the run I am
about to do?* Every field below is a separate way for the answer to be no, checked in the section
2.6 order, each naming itself.

| Field | Source | What a mismatch means | Code |
| --- | --- | --- | --- |
| **`source_header_region_sha256`** | copied verbatim from the **pack's** source-identity record (`docs/specs/r4-alignpack-layer-major.md` section 2.4.6, at `source_record_offset + 48`) | A different model | `R6_KV_IDENTITY("pack")` |
| `pack_total_bytes` | the pack header's `total_bytes` | The same GGUF, packed differently or truncated | `R6_KV_IDENTITY("pack_total_bytes")` |
| **`geometry_sha256`** | `crypto.sha256` of the exact bytes `fs.read_file(GEOMETRY)` returned | A different `R1_MODEL_IR` document — different rope base, eps, head count, vocabulary | `R6_KV_IDENTITY("geometry")` |
| **`token_stream_sha256`** + the ids | the token-stream region | A different prompt | `R6_KV_DIGEST("tokens")`, `R6_KV_TOKENS(count)` / `R6_KV_TOKENS(<i>)` |
| **`logits_sha256`** | the logits region | A corrupt or wrong prefill result | `R6_KV_DIGEST("logits")` |
| **`plane_sha256`** | the plane region | A corrupt, torn, or truncated plane | `R6_KV_DIGEST("plane")` |

Plus the six structural integers the plane's shape depends on — `n_layer`, `n_head_kv`, `head_dim`,
`kv_width`, `columns_persisted`, `token_count` — and `plane_layout_version`, `element_type`, and
`n_vocab`, each checked against the loaded geometry and the operands **before** the digests, so the
common mistake reports the field rather than an opaque digest mismatch.

**Model identity is the pack's header-region digest, not the GGUF's, and that is a decision.**

- *The arm's operand is the pack.* A load run may not have the GGUF at all; `REFERENCE` is optional
  and the qualification's own `reference.verdict` leg is the only thing that reads it. Binding to an
  operand the caller did not supply would make the identity unverifiable on the ordinary path.
- *It costs one 32-byte `pread`.* The digest already exists inside the pack; reading it is one
  bounded read at a header-declared offset. Recomputing a GGUF digest is not merely expensive but
  **impossible at this pin**: `crypto.sha256` is one-shot over exactly one byte view, so a 4.68 GB
  digest needs a 4.68 GB byte view (section 8, Request 29).
- *It transitively identifies the model.* alignpack section 2.4.6: `[0, data_offset)` is the magic,
  version, counts, every metadata KV, and every tensor-table entry; two files agreeing there and on
  `file_size` declare the identical model down to the last tensor's placement.
- *What it does **not** claim, stated because alignpack states it.* It does not certify the pack's
  **payload**. A pack whose weight bytes were corrupted after packing has the same header-region
  digest, and this arm would load a plane that matches a pack whose weights have since changed. That
  question belongs to `--pack-verify`, which owns it, and `scripts/run-decode-step` already asserts
  `reference.verdict == "IDENTICAL"` on every qualification prompt. It is a limitation, not a gap:
  filling it needs a whole-payload digest, which is Request 29.

**A digest of thirty-two zero bytes is not an identity, and is refused rather than compared.** The
pack's source-identity record is optional in alignpack's own format, and a pack that reserved it and
left it zero hands this arm an all-zero `source_header_region_sha256` — which compares **equal** to
the all-zero digest a container written against such a pack would carry, so `R6_KV_IDENTITY("pack")`
would pass over nothing. Step 7b refuses the degenerate value on both directions with
`R6_KV_IDENTITY("pack_absent")`: a container is never written with an identity that cannot
distinguish one model from another, and one is never loaded on it. `ds-kv-pack-identity-absent` is
the case, and section 11.3 deviation 4 — which made the *fixture* write a non-degenerate record — is
the same class caught one layer lower.

**Invalidation rule: every mismatch is a refusal, never a silent re-prefill.** There is no fallback
path, no "recompute on miss", and no partial acceptance. A caller that wants a prefill runs without
`KV_LOAD`. A capability that silently substitutes a different computation for the one it was asked
for is a cache, and section 1.3 declares that this is not one.

### 2.5 `MAX_KV_PLANE_BYTES` — the digest bound, and why it refuses rather than skips

| Field | Contract |
| --- | --- |
| Constant | `MAX_KV_PLANE_BYTES := 536870912` (512 MiB), `src/kv_plane.align` |
| Applies to | `plane_bytes`, on **both** directions. On a save run at step 6a, from the geometry and the operand — before the pack is opened and long before a prefill runs. On a load run again at L7, from the header, because there the number comes out of a file this process did not write |
| Failure | `R6_KV_TOO_LARGE`, detail `plane[<n>]` |
| Companion | `MAX_KV_LOGITS_BYTES := 16777216` (16 MiB); `R6_KV_TOO_LARGE` detail `logits[<n>]`. Checked at 6a and at L7, for the same reason |
| Companion | `MAX_KV_CONTAINER_BYTES := 1073741824` (1 GiB), the whole-file bound; checked at 6a and at L7 against the header's `total_bytes` before any region is addressed |
| All three on load | Checked at L7 **before** `f.len() == total_bytes`, so a header claiming an unreasonable magnitude is refused on its own claim rather than through the file's length, and a case can state the bound without materializing half a gigabyte. `ds-kv-plane-too-large` and `ds-kv-logits-too-large` are the cases; `scripts/kv_plane_reader.py` bounds all three in the same place and reaches its coarse `HEADER` |

**Why a bound exists at all.** `crypto.sha256` is one-shot over one byte view. alignpack met the same
wall and bounded its digested region at `MAX_HEADER_REGION_BYTES := 134217728` (128 MiB,
`src/alignpack.align:64`). A plane at `KV_WIDTH` 4096 on this model is 469,762,048 B, above that
precedent, so the precedent's *number* cannot be inherited and its *reasoning* must be redone.

**Why 512 MiB, and why refusing is right.**

- The plane is **already resident**: it is one `buffer` the arm holds for the whole run. Digesting it
  costs no additional residency, unlike alignpack's header region, which needed a second buffer of
  its own. So the bound is not a memory bound; it is a bound on *what this capability has reasoned
  about*.
- 512 MiB covers `KV_WIDTH` up to `MAX_ATTENTION_WIDTH` (4096) on the reference model — 448 MiB —
  with headroom. **On every geometry this capability ships against, the bound cannot fire.** It is a
  fail-fast guard against a geometry nobody measured, in the shape `MAX_DECODE_STEPS` already has:
  a typo must not allocate an hour, and a 40-layer 8-head-kv model at width 4096 must not silently
  produce a 2 GB artifact this design never considered.
- **Refusing beats skipping.** The alternative — write the container with a zeroed `plane_sha256`
  and a "digest absent" flag — was considered and rejected. A persisted artifact whose identity
  cannot be computed is not an identity; a reader would have to accept a plane on structural fields
  alone, and the one thing the digest exists to catch (a torn write, which section 6 risk 6 says is
  the realistic failure) would go undetected. alignpack could reserve `payload_sha256` because it has
  a second, complete verification arm; this capability has none.
- The existing `MAX_PLANE_BYTES := 8589934592` (8 GiB, `src/decode_step.align:76`) is the
  **in-memory** bound and is unchanged. `MAX_KV_PLANE_BYTES` is deliberately smaller and is the
  **persisted-and- digested** bound. The two are different questions and the ledger keeps them
  apart.

The bound is checked at step 6a, **before the prefill**, so a caller who asks for an unpersistable
configuration learns it in milliseconds rather than after paying for a prefill.

### 2.6 Validation order and refusal codes

R6-STEP-N's steps 1–16 keep their order and their codes. This capability inserts steps 2b, 6a, and
6b; replaces steps 9–10 on a load run with L1–L14; and appends W1–W4 to step 10 on a save run.

**The first applicable row wins, and no destination file exists before the step that creates it.**

| # | Step | Code | Detail |
| --- | --- | --- | --- |
| 1 | arity in {5,6,7,9,10,11,12,13} | `R6_ARITY` | `operands[<n>]` |
| 2 | supplied paths non-empty, no NUL, `<= MAX_PATH_BYTES`; `-` in `TRANSCRIPT`/`LOGITS`/`KV_SAVE`/`KV_LOAD` is absent, not a path | `R6_PATH` | the operand's name |
| **2b** | **not both `KV_SAVE` and `KV_LOAD`** | **`R6_KV_ARGS`** | `kv[save+load]` |
| 3 | `TOKENS` parses, `1 <= T <= MAX_PREFILL_TOKENS` | `R6_TOKENS` | `count[<n>]` |
| 3b | `STEPS` parses, `1 <= N <= MAX_DECODE_STEPS` | `R6_STEPS` | `steps[<n>]` |
| 3a–5 | geometry readable, loads, dense | unchanged | unchanged |
| 6 | `KV_WIDTH` parses, `T + N <= KV_WIDTH <= MAX_ATTENTION_WIDTH` | `R6_KV_WIDTH` | `kv_width[<n>]` |
| **6a** | **either operand present: `plane_bytes <= MAX_KV_PLANE_BYTES`, `n_vocab * 4 <= MAX_KV_LOGITS_BYTES`, `total_bytes <= MAX_KV_CONTAINER_BYTES`** | **`R6_KV_TOO_LARGE`** | `plane[<n>]` / `logits[<n>]` / `container[<n>]` |
| **6b** | **`KV_SAVE` present: `fs.exists(KV_SAVE)` is false** | **`R6_KV_EXISTS`** | the sanitized destination path |
| 7–8 | pack members, plane sizing; **plus** the pack's `source_header_region_sha256` and `total_bytes`, read once, when either operand is present | unchanged / `R6_PACK_*` | unchanged |
| **7b** | **either operand present: the pack's `source_header_region_sha256` is not thirty-two zero bytes** | **`R6_KV_IDENTITY`** | `pack_absent` |
| 9–10 | prefill pass, plane readback of columns `0 .. T-1` | unchanged | unchanged |
| — | **on `KV_LOAD`, steps 9 and 10 do not run; L1–L14 run instead** | | |
| — | **on `KV_SAVE`, W1–W4 run immediately after step 10 and before step 11′** | | |
| 11′–16 | decode loop, per-step round trip, transcript oracle, width, self-reference, logits blob | unchanged | unchanged |

**Load order, L1–L14.** Cheap first, so a wrong file costs 384 bytes; the plane's 29 MB is read only
once every field agrees.

| # | Check | Code | Detail |
| --- | --- | --- | --- |
| L1 | `fs.open_rw(KV_LOAD)` and `f.len()` succeed | `R6_KV_UNREADABLE` | the Align `Error` variant name |
| L2 | `f.len() >= header_bytes` (192) | `R6_KV_TRUNCATED` | `header` |
| L3 | `magic == AKVP` | `R6_KV_MAGIC` | the four bytes, hex-escaped |
| L4 | `format_version == 1` | `R6_KV_VERSION` | the version |
| L5 | `header_bytes`, `identity_record_bytes`, `element_type`, `plane_layout_version`, `plane_align`, `document_schema_version`, `endian_probe`; every `u64` offset/length has its high bit clear; every `u32` count against the bound this format states for it — `kv_width <= MAX_ATTENTION_WIDTH`, `token_count <= MAX_PREFILL_TOKENS`, `columns_persisted <= kv_width`, `0 <= prefill_argmax < n_vocab`, and `n_layer`/`n_head_kv`/`head_dim`/`n_vocab` `>= 1`. **Those four have no `MAX_*` of their own**; the shapes they imply are bounded at L7 by section 2.5's three bounds and settled at L8 against the loaded geometry | `R6_KV_HEADER` | the field name |
| L6 | `flags == 0`, `reserved_u32 == 0`, the 48 reserved header bytes are zero, the 24 reserved identity bytes are zero, **and the three inter-region padding runs are zero** (taken after L7, because it is the one reserved-space rule that needs L7's validated offsets) | `R6_KV_RESERVED` | the field name, or `padding` |
| L7 | `plane_bytes <= MAX_KV_PLANE_BYTES`, `logits_bytes <= MAX_KV_LOGITS_BYTES`, `total_bytes <= MAX_KV_CONTAINER_BYTES`; `f.len() == total_bytes`; every region inside `[0, total_bytes)`; regions pairwise disjoint; each region 8-byte aligned; `plane_offset % plane_align == 0`; `plane_offset + plane_bytes == total_bytes`; `token_stream_bytes == token_count * 4`; `logits_bytes == n_vocab * 4`; **and the four offsets equal section 2.3.1's canonical layout** | `R6_KV_TOO_LARGE` / `R6_KV_TRUNCATED` / `R6_KV_REGION` | `plane[<n>]` / `logits[<n>]` / `container[<n>]`, `<a>!=<b>` or the region name, `layout` |
| L8 | `n_layer`, `n_head_kv`, `head_dim`, `n_vocab`, `element_type` equal the loaded geometry's; `plane_bytes == plane_bytes_for(g, kv_width)` | `R6_KV_GEOMETRY` | the field name |
| L9 | `source_header_region_sha256` and `pack_total_bytes` equal the pack's | `R6_KV_IDENTITY` | `pack` / `pack_total_bytes` |
| L10 | `geometry_sha256` equals `crypto.sha256` of the geometry bytes this run read | `R6_KV_IDENTITY` | `geometry` |
| L11 | `kv_width` equals the `KV_WIDTH` operand | **`R6_KV_WIDTH`** | `kv_width[<file>]!=[<operand>]` |
| L12 | `token_count == T`; each id equals the `TOKENS` operand's; `token_stream_sha256` recomputes | `R6_KV_TOKENS` / `R6_KV_DIGEST` | `count[<n>]` / `<i>` / `tokens` |
| L13 | `columns_persisted == token_count` | `R6_KV_NPAST` | `columns[<n>]!=[<m>]` |
| L14 | logits region read and `logits_sha256` recomputed; `prefill_argmax` equals the argmax of the loaded vector; plane region read in `CHUNK_BYTES` rounds totalling exactly `plane_bytes`; `plane_sha256` recomputed | `R6_KV_UNREADABLE` / `R6_KV_DIGEST` / `R6_KV_TRUNCATED` / `R6_KV_HEADER` | the variant, `logits` / `plane`, `plane`, `prefill_argmax` |

**`R6_KV_WIDTH` at L11 is R6's existing code, deliberately reused.** The condition is "the plane is
not the width this run needs", and R6 already owns that sentence — R6-STEP-N section 2.3 refused to
mint a second code for the same condition on exactly this reasoning, and two codes for one condition
is how two documents come to disagree. The detail is widened to name both values.

**Save order, W1–W4**, run only after step 10 has verified the prefill plane:

| # | Step | Code | Detail |
| --- | --- | --- | --- |
| — | compute `plane_sha256`, `logits_sha256`, `token_stream_sha256`, `geometry_sha256`; assemble the complete 192-byte header and 192-byte identity record **in memory**. Nothing has touched the filesystem | — | — |
| W1 | `fs.create_rw(KV_SAVE)` | `R6_KV_UNWRITABLE` | the Align `Error` variant name |
| W2 | write header, token stream, padding, identity record, logits, padding, plane — each with one `f.pwrite` at its declared offset | `R6_KV_WRITE_FAILED` | `<Variant>@<offset>` |
| W3 | `f.len() == total_bytes` | `R6_KV_SIZE_MISMATCH` | `<a>!=<b>` |
| W4 | on any failure at or after W1: `fs.remove(KV_SAVE)` — the **destination name**, with the dangling-symlink consequence stated below; `kv.destination` becomes `"REMOVED"`, or `"WRITTEN"` with `R6_KV_CLEANUP_FAILED` in the detail | `R6_KV_CLEANUP_FAILED` | the sanitized path |

**The plane is one `pwrite`, and that is verified rather than assumed.** `f.pwrite` writes **all** of
its argument, looping over partial writes internally and retrying `EINTR`
(`align_rt_io_file_pwrite` → `write_all_at`, verified at the pin). `plane.bytes()` is exactly
`plane_bytes` long because `prime_window` appends that many zero bytes at allocation. So
`dst.pwrite(plane.bytes(), plane_offset)` is correct and complete; `COPY_WINDOW_BYTES` chunking is
alignpack's answer to a *file-to-file* copy and has no role here.

**`ENOSPC` gets no distinct code**, for alignpack's reason: the writer cannot distinguish a full disk
from an exhausted quota through the mapped error, and inventing a code that claims the difference
would be a guess. It arrives as `R6_KV_WRITE_FAILED`, the partial file is removed, and the runner
checks headroom before it starts rather than relying on the failure path to be pleasant.

**`R6_KV_EXISTS` inherits a documented race, named rather than hidden.** `fs.create_rw` is
`O_RDWR|O_CREAT|O_TRUNC` and `fs.create_exclusive` returns a sequential `writer` with no `pwrite`, so
there is **no exclusive positional constructor at this pin** (both verified at
`crates/align_sema/src/lib.rs`). Between step 6b and W1 another process could create the path, and
this arm would truncate it. The exposure is one developer host writing to a caller-named path;
Request 30 is the fix and this capability is its **second client**. Hiding the race behind a silent
overwrite would be worse than naming it. A destination that is a **symlink** is followed in both
directions, exactly as alignpack's `dest-symlink` case pins: an existing target is `R6_KV_EXISTS`
naming the link's path, and a **dangling** symlink is created through, so a caller who removes the
name it passed has not removed the container.

**One consequence of following a dangling symlink is stated rather than hidden, because W4's "every
failure removes it" is not true of it.** `fs.remove(KV_SAVE)` removes the **name** it was given.
When that name is a dangling symlink, `fs.create_rw` created the file at the link's target and
`fs.remove` unlinks the symlink, so a write failure at W2 or W3 leaves a partial container **at the
target** and `kv.destination` still reports `"REMOVED"` — which is true of the name and false of the
bytes. It is not defended, for the reason `R6_KV_EXISTS`'s race is not defended: at this pin there
is no `fs.symlink_metadata`, no `lstat`, and no `O_NOFOLLOW`, so the arm cannot distinguish a
dangling symlink from an absent path without a capability Align does not ship (section 8 records no
new request for it: refusing symlink destinations outright would also change
`ds-kv-save-exists-symlink`'s settled behaviour, which alignpack pins). The exposure is one
developer host writing to a caller-named path it chose; the honest scope of W4 is therefore **"the
destination name is removed"**, and section 7 carries it as a declared limitation.

**Multi-invalid precedence is total and asserted.** Three orderings carry cases of their own because
they are the ones a reader would guess wrong: `R6_KV_ARGS` (2b) precedes every path-content check,
so a run naming two paths is refused before either is opened; `R6_STEPS` (3b) precedes `R6_KV_WIDTH`
(6), unchanged from R6-STEP-N; and `R6_KV_TOO_LARGE` (6a) precedes `R6_KV_EXISTS` (6b), because a
configuration that can never be persisted should not report a destination conflict as its reason.

### 2.7 Ownership, allocation, and cleanup on every path

| Value | Owner | Allocation | Release |
| --- | --- | --- | --- |
| The KV plane | `mut plane: buffer` at `schedule_decode`'s scope, **unchanged** | one `buffer(plane_bytes)`, zero-filled by `prime_window` | scope `Drop`, on **every** path — success, every refusal L1–L14, every write failure W1–W4, and every step failure. R6-STEP-N section 2.8's rule is unchanged and now also covers the load and save paths |
| The destination `file` | one bare local in `kv_plane.write_container` | one fd | scope `Drop` closes it, including on the `fs.remove` path |
| The source `file` | one bare local in the load path | one fd | scope `Drop` |
| The 1 MiB refill transient | one `mut` local, `buffer(model_forward.CHUNK_BYTES)` | 1,048,576 B, refilled in place by `f.pread`, **never rebound** | scope `Drop`. Rebinding is what Request 39 measures the cost of; the shape here is `src/model_forward.align`'s, unchanged |
| The logits buffer | one `mut` local, `buffer(logits_bytes)` | `n_vocab * 4` = 608,256 B on the reference model | scope `Drop` |
| The `PAD` buffer | one `mut` local, `buffer(plane_align)`, filled once with `put_u8(0)` | 4,096 B | scope `Drop` |
| The header and identity images | two `mut` locals, `buffer(192)` each, built field by field with `put_*` before the file exists | 384 B | scope `Drop` |
| Five digests | five `array<u8>` of 32 | owned by `crypto.sha256` | scope `Drop` |
| `KvHeader` (the decoded header, all scalars) | returned **by value** from `kv_plane.read_header` | a Copy record of 26 scalars | no `Drop` |
| The partial destination file | **the filesystem**, between W1 and W3 | up to `total_bytes` | `fs.remove` at W4, reported as `kv.destination` |

**Peak.** The load path holds the plane (29 MB), the 1 MiB transient, and the logits buffer at once —
30.4 MB — and the transient and the logits buffer are released before the decode loop starts. The
save path holds the plane and the 4 KiB pad; it never holds a second copy of the plane, because the
write is one `pwrite` of the live buffer. Neither path allocates anything proportional to `N`.

**Why the module split falls where it does, and Request 49 is the reason.** `src/kv_plane.align` owns
everything that can be expressed with **borrowed views and by-value returns**: the constants, the
header and identity encode/decode, the region arithmetic, the digests, the writer (which takes the
plane as `borrow plane: slice<u8>` — a read-only view, which crosses freely), and `read_header`,
which returns a Copy `KvHeader` by value. The **plane refill** stays in `src/decode_step.align`,
because it must write into `decode_step`'s own `mut plane: buffer`, and a cross-module call taking
`borrow mut buffer` alongside this frame's other locals is exactly the shape **Request 49** refuses
(R6 section 10.6 records seven functions already copied for it, and R6-STEP-N cites it as a
continuing client). The split is therefore not aesthetic: the format's authority is one module, the
byte movement into a caller-owned buffer stays with the buffer's owner, and no workaround is built.
Section 8 records this as one more client of Request 49 rather than as a new request.

**The refill is chunked, and that is forced by the language.** Align's `buffer` is append-only —
`put_*` and `append` write at the logical length, there is no offset write, no truncate, no reset —
and `f.pread` overwrites from index 0 and always requests exactly the destination's whole capacity
(`prepare_uninit_window` calls `data.clear()`; `pread(fd, dst, b.cap, off)`). A short read therefore
cannot be resumed mid-buffer. The plane is filled in `model_forward.CHUNK_BYTES` (1 MiB) rounds
through the transient and `model_forward.window_put` → `ggml_ffi.window_copy` →
`align_ggml_window_copy`, the bounded `memcpy` R5B added for this exact reason and wired at
`src/ggml_ffi.align:259,925`. This is **Request 38's** second consumer and no new request is
proposed.

**No in-arm read-back of the metadata regions.** It was considered: `pread` the first `plane_offset`
bytes after W3 and compare against the images just written. It is **not taken**, because a read-back
of bytes this process wrote a microsecond ago proves the process's own arithmetic and nothing about
the file — and the process's own arithmetic is exactly what `scripts/kv_plane_reader.py` checks,
from this document rather than from the writer, on every saved file in the smoke. A read-back would
look like durability evidence and would not be any (section 7).

### 2.8 The document — `R6_DECODE_STEP`, schema 3

| Field | Contract |
| --- | --- |
| `kind` | **`R6_DECODE_STEP`, unchanged.** The document describes the same thing; where the plane came from is a field, not a kind |
| `schema_version` | **3** |
| New: `plane.source` | `"PREFILL"` when the prefill computed the plane, `"LOADED"` when `KV_LOAD` supplied it. Present in every document, `"-"` on a document refused before the plane exists |
| New: the `kv` object | Present in **every** document, including error documents, with one shape at every arity |
| **Changed: `reference.verdict`** | **`"-"` on a load run**, and this is a public field's behaviour changing rather than only a test exclusion. R5B's byte comparison of every pack member against the source GGUF lives **inside the prefill pass**, so a load run performs zero comparisons; before this capability `schedule_decode` set `REFERENCE_IDENTICAL` whenever `reference_present && code == 0`, which on a load run would publish a pass over nothing. The condition is now additionally `&& !loading`. `reference.present` still reports whether the operand was supplied, every count stays `0`, and the prefill path is character-for-character unchanged. The qualification asserts `reference.verdict == "IDENTICAL"` on the **save** run, where the comparison actually ran |
| `output`, `oracle_logits` | **Populated on a load run too**, from the persisted logit vector: `output.sha256` is the digest of the loaded bytes, `output.argmax` is `prefill_argmax`, and `oracle_logits` compares the loaded vector against `LOGITS` exactly as a prefill run does. This is section 2.4's whole reason for persisting the logits — see below |
| `decode`, `steps[]`, `plane`, `oracle_decode`, `model`, `selection`, `graph`, `schedule`, `head`, `timings`, `lifetime`, `abi` | Unchanged in shape from schema 2 |
| New: `timings.first_token_ns` | The interval from `execute`'s first `time.instant()` to the instant step 1's argmax is available; `0` when no step completed. Section 1.4's diagnostic. **Zeroed by `normalize`** |
| Float fields | Never floats on the wire, unchanged. Every digest is a lowercase hex `sha256`; every byte count is an integer |
| **No path-valued field** | `kv` publishes **no path**. R6-STEP-N risk 5 names the temp-path golden class, and schema 2 was verified free of it; schema 3 keeps that property. `kv.destination` publishes a verdict word, never a name |
| Persisted identity | **Section 2.4. This row replaces R6's and R6-STEP-N's `N/A — nothing is persisted`.** The container's identity is `magic` + `format_version` + `plane_layout_version`; its binding is the five digests, `pack_total_bytes`, and the nine structural integers |
| Cache identity | **N/A, and the reason is a decision rather than an absence.** There is no cache (section 1.3): the container is a caller-named artifact, found only by a caller who names its path. Were one added, its key would be `(source_header_region_sha256, geometry_sha256, token_stream_sha256, kv_width, plane_layout_version)`; that tuple is recorded here so a later capability does not invent a different one, and it is **not implemented** |
| Schema version | **Container `format_version: 1` and document `schema_version: 3`, independently versioned**, with `document_schema_version` in the container binding a file to the document vintage that wrote it — alignpack's rule, for alignpack's reason. Any change to a region, a field, an offset, an alignment rule, or a reserved value requires `format_version: 2` |
| Field presence | Every field is present in every document. No conditional-presence rule, no operand-dependent shape: schema 3 is one shape at 5 operands and at 13 |

The `kv` object, in declaration order:

```text
kv.save_requested          0 | 1
kv.load_requested          0 | 1
kv.verdict                 "-" | "SAVED" | "LOADED"
kv.destination             "-" | "WRITTEN" | "REMOVED"
kv.format_version          0 when absent
kv.plane_layout_version    0 when absent
kv.total_bytes             0 when absent
kv.header_bytes            0 when absent
kv.plane_offset            0 when absent
kv.plane_bytes             0 when absent
kv.logits_bytes            0 when absent
kv.columns_persisted       -1 when absent
kv.token_count             -1 when absent
kv.n_vocab                 -1 when absent
kv.prefill_argmax          -1 when absent
kv.pack_total_bytes        0 when absent
kv.source_header_region_sha256   "-" when absent
kv.geometry_sha256               "-" when absent
kv.tokens_sha256                 "-" when absent
kv.logits_sha256                 "-" when absent
kv.plane_sha256                  "-" when absent
kv.write_ns                0 when absent; zeroed by `normalize`
kv.read_ns                 0 when absent; zeroed by `normalize`
```

**Why the prefill logits are persisted, and why persisting only `d_1` was rejected.** The decode loop
needs its first input token, and on a load run there is no prefill to produce it — so *something*
about the prefill's output must be in the file or the container is not a resumable prefill. Three
candidates were weighed:

| Candidate | Bytes | Rejected because |
| --- | --- | --- |
| Nothing | 0 | The load run cannot start. Step 1 consumes `d_1` and there is no `d_1` |
| `prefill_argmax` only | 4 | It makes the artifact a resume token rather than a prefill result. `output.*` and `oracle_logits` would be unavailable on a load run, so **gate G1 — the byte-exact `llama-debug` comparison the whole id chain is rooted in — would be lost by loading**, and the document equality oracle would have to exclude the entire `output` block |
| **The whole last-position vector** (chosen) | `n_vocab * 4` = 608,256, **2.1 % of the plane** | — |

The chosen answer costs 2 % and buys three things: `d_1` (as `prefill_argmax`, carried redundantly
and validated against the vector's own argmax at L14 — alignpack's redundant-field discipline), a
load run that republishes `output.*` **byte-identically**, and G1 surviving the round trip. Section
3's equality oracle is a one-line comparison because of it.

### 2.9 Metrics

Characterization only. **No TTFT claim, no tokens-per-second claim, no comparison to llama.cpp's
wall time, and no cost ceiling recorded in a ledger row**, because this capability makes no
performance claim and `CLAUDE.md`'s performance row is therefore not selected.

| Metric | Source | Reported as |
| --- | --- | --- |
| Container size | `kv.total_bytes` | Asserted exactly on both configurations of section 2.3.5 |
| Metadata overhead | `kv.plane_offset` | 2,048 B at the reference configuration; 0.007 % |
| Write cost | `kv.write_ns` | Total, and against `plane_bytes` |
| Load cost | `kv.read_ns` | Total, split by the runner into "header and identity" and "plane refill" |
| Digest cost | inside `kv.write_ns` / `kv.read_ns` | Reported separately by the runner: five `crypto.sha256` calls, of which one covers 29 MB |
| Disk usage | `du -k` on the saved file, in the runner | Compared against `kv.total_bytes` — the sparse-file check that makes section 2.3's explicit padding an assertion |
| **TTFT proxy** | `timings.first_token_ns`, and the runner's invocation wall clock | Section 1.4. **Labelled diagnostic. Three runs, median and spread, one host. No derived rate** |

**Saturation, checked rather than assumed.** Every accumulated quantity is `i64` and every one is
bounded: `total_bytes <= MAX_KV_CONTAINER_BYTES` (2^30), `kv.write_ns` and `kv.read_ns` are single
intervals under 10^10 ns, and `first_token_ns` is one interval. Every file-derived sum in the region
arithmetic — `offset + length`, `align_up` — is formed with `add_checked`/`mul_checked` **before**
it is used, in `src/model_ir.align` rule 2's non-wrapping style, because Align's `i64` arithmetic
wraps silently and every one of those operands comes from a file this process did not write.

### 2.10 Prerequisites

| Prerequisite | State |
| --- | --- |
| Everything R6 and R6-STEP-N list | Shipped, unchanged |
| `R6-STEP-N` merged, or this branch stacked on its head | **Stacked** on `a9c6161`. If R6-STEP-N merges with repairs, this branch takes `git merge origin/main` — never a rebase — and re-runs its owner |
| `f.pwrite` writes all of its argument | **Verified at the pin**: `align_rt_io_file_pwrite` → `File::write_all_at`, looping to full and retrying `EINTR` |
| `f.pread`, `f.len()` | **Verified**: `pread` requests exactly `b.cap` and overwrites the buffer's length; `len()` is a live `fstat` |
| `fs.create_rw`, `fs.open_rw`, `fs.exists`, `fs.remove` | **Verified present**: `create_rw` is `O_RDWR|O_CREAT|O_TRUNC`, `open_rw` is `O_RDWR` and must exist |
| `crypto.sha256` over a byte view | **Verified present**, one-shot, accepting `str` / `string` / `slice<u8>` |
| `align_ggml_window_copy` | **Shipped** since R5B; the shim is byte-unchanged by this capability |
| Align language features | **None new.** Section 8 records every gap encountered; none blocks this capability |

## 3. Oracles and the acceptance rule

R6-STEP-N's gate G, oracle B, oracle C′, and oracle A′ are **unchanged and carry forward**. Two are
added, and one existing leg is explicitly re-scoped.

**Oracle P — the persistence round trip (internal, byte-exact, acceptance).** For each prompt, a save
run writes `plane.akvp`; a **separate process** loads it. Three independent things must agree:

1. `kv.plane_sha256` recomputed on load equals the value the save run wrote — the file's own claim.
2. `plane.roundtrip_verdict` is `IDENTICAL` at every step of the load run — so the plane the loaded
   run's *graphs consumed* matches the loaded plane, through a different node than the digest.
3. `scripts/kv_plane_reader.py`, which shares no line with `src/`, accepts the file and reports the
   same five digests, the same nine integers, and the same `total_bytes`.

**Oracle Q — the two runs are the same run (external to the container, acceptance).** With
`normalize_persist` defined as `normalize` plus dropping the keys below, the save run's and the load
run's documents must be **byte-identical**. The list is **sixteen groups**: the design named eight,
and an empirical field-by-field diff of a save-run document against a load-run document found eight
more, each a count of work the prefill did and the load run did not (section 11.3, deviation 2).
This is the shipped list, and both runners hold exactly it:

```text
excluded blocks (6): kv, graph, schedule, timings, lifetime, reference
excluded fields (10): plane.source, plane.readback_ns, plane.upload_ns,
                      head.node_count, head.pread_ns, head.compute_ns,
                      pack.reader_pread_count, pack.reader_bytes_read,
                      window.reuse_count, window.member_placements
```

Everything else is compared, and the exclusions are each justified rather than convenient:

| Excluded | Why it must differ |
| --- | --- |
| `kv`, `plane.source` | They *are* the difference |
| `graph`, `schedule` | A load run builds no prefill graph, so graph and node counts legitimately differ |
| `timings`, `lifetime`, `plane.*_ns`, `head.pread_ns`, `head.compute_ns` | Wall clock, and ggml object counts that follow the graph count |
| `head.node_count` | The prefill's own head graph, which the load run does not build |
| `pack.reader_pread_count`, `pack.reader_bytes_read` | The prefill's own weight sweep. The decode loop's reads are still compared, because they are in the same two counters and both runs perform them |
| `window.reuse_count`, `window.member_placements` | Window fills the prefill performed |
| `reference` | R5B's byte comparison against the source GGUF lives in the prefill pass, so a load run performs none of it and publishes `reference.verdict: "-"` (section 2.8, section 11.3 deviation 3). This is the **one** excluded group that is not purely a count, and it is excluded because the work behind it did not run |

**What that leaves inside the comparison is the point**: `decode` in full, including `token_ids`;
every object of `steps[]`, including each step's `sha256`, `argmax`, `n_past`,
`plane_column_written`, and complete `oracle` sub-object; `plane.columns_written`,
`roundtrip_verdict`,
`roundtrip_bytes_compared`, and every `first_mismatch_*`; **`output` and `oracle_logits`** (section
2.8); `oracle_decode` in full; and `model`, `selection`, `head`, `abi`. A one-lane error anywhere in
the persisted plane changes `steps[1].sha256` and every step after it.

**Gate G, re-scoped explicitly rather than silently.** G2 — the per-step `embd` fingerprint against
transcript graph `k+1` — applies to **both** runs unchanged. **G1 — `d_1` byte-exact against
`llama-debug --save-logits` — is asserted on the save run, where the prefill actually ran, and is
*inherited* by the load run through `oracle_logits` over the persisted vector.** That is a weaker
statement than "G1 runs twice" and it is stated as the weaker one: on the load run the compared
bytes came out of the container, so what `oracle_logits` proves there is that the container
preserved them, not that a prefill recomputed them. Both facts are wanted; conflating them would
make the load run look like it re-derived something it read.

**Determinism — the writer, by double write.** Two `--kv-save` runs on identical inputs to two
different destinations must produce files whose whole-file `sha256` are equal. Plus an
**env-perturbation** case: the same two runs under a perturbed environment (`TZ`, `LANG`, `LC_ALL`,
`SOURCE_DATE_EPOCH`, a changed `PWD`) must still agree. This is alignpack's method and it is taken
deliberately in place of a hex golden.

**There is no checked-in hex golden of the container, and that is alignpack's decision inherited with
its reasons** (`docs/specs/r4-alignpack-layer-major.md`, section 7.2): the three properties a hex
golden protects — field order, record stride, reserved values — are each asserted **per field** by
`scripts/kv_plane_reader.py` decoding every field at its declared offset, and by the mutation corpus
firing one named refusal per field. A hex golden would additionally pin the fixture generator's
output, which is not this capability's contract. The `ds-kv-*` **document** golden rows still apply
— that is JSON, not the container.

**The shipped acceptance rule, stated once.** `scripts/run-decode-step` implements it and its comment
quotes it.

> For every prompt, all of the following, unconditionally:
>
> 1. **R6-STEP-N section 3.5's rule, in full, on the save run** — gate G, oracle B, oracle C′ at
>    `k ∈ {1, ⌈N/2⌉, N}`, oracle A′ structural at every step and numeric at step 1, determinism, and
>    the `N + 1`-graph transcript count.
> 2. **The save run writes.** `kv.verdict == "SAVED"`, `kv.destination == "WRITTEN"`,
>    `kv.columns_persisted == selection.token_count`, `kv.total_bytes` equal to the file's size on
>    disk and to `du`'s report of it, and `kv.plane_bytes == plane.bytes`.
> 3. **Oracle P.** A **separate process** loads the file at the same `KV_WIDTH` and `STEPS` and
>    reports `plane.source == "LOADED"`, `kv.verdict == "LOADED"`, and `plane.roundtrip_verdict ==
>    "IDENTICAL"` at every step; `scripts/kv_plane_reader.py` accepts the file independently.
> 4. **Oracle Q.** `decode.token_ids` are equal element for element, and the two documents are
>    byte-identical after `normalize_persist`.
> 5. **Gate G on the load run.** G2 at every step; `oracle_logits.verdict == "IDENTICAL"` and
>    `byte_identical` over the persisted vector; `output.argmax == kv.prefill_argmax ==
>    steps[0].token_id`.
> 6. **Oracles B and C′ on the load run**, at the same checkpoints and with the same byte counts.
> 7. **Determinism.** Two saves are byte-identical, under an unperturbed and a perturbed environment;
>    three consecutive load runs are byte-identical after `normalize`.
> 8. **Every refusal case in section 5.2 yields exactly its named code, and no case that refuses
>    leaves a file behind.**
>
> `timings.first_token_ns` and the invocation wall clock are **reported** on both runs and no
> acceptance decision is taken from either.

**Tolerances.** Every comparison this capability adds is **byte identity or integer equality**: a
container either round-trips or it does not, and a digest either matches or it does not. No new
tolerance is introduced, and R6-STEP-N's four inherited tolerances are unchanged.

## 4. Closure matrix

Every cell names an implementation and an exact regression, or is marked `N/A` or **deferred** with
a reason. `T` is the prefill length, `N` the step count, `k` a step index.

### 4.1 `src/kv_plane.align` — the container, new module

| Phase | Implementation | Regression |
| --- | --- | --- |
| Formation / validation | `read_header(borrow f: file) -> KvHeader` decodes 192 bytes and runs L2–L7 in order, returning a Copy record whose `code`/`detail` are set on the first failure; `padding_zero(borrow f, borrow h)` runs L6's third part over the three gaps | `ds-kv-magic`, `-version`, `-header-bytes`, `-identity-record-bytes`, `-element-type`, `-layout-version`, `-plane-align`, `-endian-probe`, `-flags`, `-reserved`, `-truncated-header`, `-truncated-total`, `-longer-total`, `-region-overlap`, `-region-outside`, `-region-misaligned`, `-plane-not-last`, `-region-noncanonical`, `-padding-nonzero`, `-plane-too-large`, `-logits-too-large` |
| Construction | `write_container(dest: str, borrow h: KvHeader, borrow ids: slice<u8>, borrow logits: slice<u8>, borrow plane: slice<u8>) -> KvWrite`; every field is fixed before `fs.create_rw` | `ds-kv-save-ok`; the reader accepts the produced file |
| Success | header, token stream, identity, logits, plane written at declared offsets, padding explicit, `f.len() == total_bytes` | `ds-kv-save-ok` asserts `kv.total_bytes == 4608` on the synthetic; `du` check in the qualification |
| Failure | `fs.create_rw` fails → `R6_KV_UNWRITABLE`; a `pwrite` fails → `R6_KV_WRITE_FAILED` with `<Variant>@<offset>` | `ds-kv-save-unwritable` (destination inside a `0555` directory) → `R6_KV_UNWRITABLE`, no file. **`R6_KV_WRITE_FAILED` is deferred as a case**: reaching it needs a filesystem that accepts a create and refuses a write, which alignpack reaches only through an opt-in `hdiutil` volume — reused, not rebuilt (section 5.2) |
| Malformed input | every L2–L14 refusal, and `R6_KV_TOO_LARGE` | the full `ds-kv-*` table, section 5.2 |
| Early exit | any refusal returns before the next region is addressed; a failure after W1 removes the file | `ds-kv-save-unwritable` asserts no file; `ds-kv-save-exists` asserts the **pre-existing file is byte-unchanged** |
| Cleanup | the `file`, the `PAD` buffer, the two 192-byte images, and five digests are bare locals | `lifetime.*_created == *_freed` on every `ds-kv-*` case |
| Move-in/out, source nulling, replacement, return | **N/A — no ownership transfer is added.** `KvHeader` and `KvWrite` are Copy records returned by value; the plane and the logits arrive as `slice<u8>` borrows; no value is moved out of a record and no source is nulled. The one place a `borrow mut` would have been needed — the plane refill — is deliberately not in this module (section 2.7) | stated, with reason |

### 4.2 `src/decode_step.align` — the arm, the operands, and the refill

| Phase | Implementation | Regression |
| --- | --- | --- |
| Construction | `run` accepts arity 12 and 13, reads `args[11]`/`args[12]` with the `-` convention, refuses both (2b); `stage_inputs` gains 6a; `execute` gains 6b and the pack-identity read at 7 | `ds-arity-14`, `ds-kv-both`, `ds-kv-args-dash-dash` (legal, ≡ 11 operands), `ds-kv-too-large`, `ds-kv-save-exists` |
| Success — save | after step 10, `save_plane` assembles the header and identity and calls `kv_plane.write_container`; `kv.verdict = "SAVED"` | `ds-kv-save-ok`; qualification rule 2 |
| Success — load | `load_plane` replaces steps 9–10: `kv_plane.read_header`, L8–L13 against geometry/operands, then the chunked refill and L14 | `ds-kv-load-ok` (`plane.source == "LOADED"`, `columns_written == T + N`) |
| Failure | every `R6_KV_*` reaches the document through `fail`, and `plane.source` stays `"-"` | one case per code, section 5.2 |
| Malformed input | steps 2, 2b, 6a, 6b, L2–L14 | section 5.2's table |
| Early exit | a refusal at any L-step frees the plane, publishes `plane.columns_written == 0`, `roundtrip_verdict` not `IDENTICAL`, `decode.steps_completed == 0`, `token_ids == []`, and **no `steps[]` row** | `ds-kv-digest-plane` asserts all five |
| Cleanup | the plane, the transient, the logits buffer, and both file handles are bare locals at their scopes | `lifetime.*_created == *_freed`, `graph_balance_failures == 0`, on every case |
| **Ordering invariant** (new) | On a load run the plane is a `slot_set` **source** at step 1 having never been a `slot_get` destination in this process. R6-STEP-N's disjointness invariant is unchanged for steps `k >= 1`; what changes is that column range `[0, T)` was filled by `window_copy` before the first graph exists | `ds-kv-load-ok`'s oracle B at step 1 compares `T + 1` columns, of which `T` came from the file |
| Move-in/out | **N/A** — the plane is never moved; it is borrowed as `slice<u8>` for the write and written into via the shim for the load | stated, with reason |

### 4.3 `src/model_forward.align`

| Phase | Implementation | Regression |
| --- | --- | --- |
| Construction | `Outcome` gains the `kv_*` scalars and `plane_source`; `StepColumns` is **unchanged** — nothing here is per step | the compiler's own struct-size warning, unchanged in count (Request 23) |
| Success | `window_put` and `CHUNK_BYTES` are **reused unchanged** by the refill; the prefill path is untouched | `model-forward-golden.jsonl` **byte-unchanged** |
| Failure | a refill round whose copied byte count does not reach `plane_bytes` | `R6_KV_TRUNCATED("kv_plane")`. **No `ds-kv-*` case reaches it and none can**, and the reason is L7: the plane is the container's last region and `f.len() == total_bytes` and `plane_offset + plane_bytes == total_bytes` are both proved before a byte of the plane is read, so a container that reaches the refill has a complete plane region by construction. The cell is closed by an **injected mutant** instead — section 5.5's "plane read offset off by four", which fails `ds-kv-load-ok` with exactly this code and detail — and section 11.2 records it |
| Malformed input / Early exit / Cleanup | unchanged | existing `mf-*` cases |
| **Non-regression** | no constant, no node row, no slot, no mask writer moves | `gpu-forward-golden.jsonl`, `moe-layer-forward-golden.jsonl`, `layer-forward-golden.jsonl`, `ggml-spike-golden.jsonl` **byte-unchanged**; predicted in section 5.3 |

### 4.4 `ggml_spike`, `ggml_ffi`, the two shims, and `layer_qwen2` — byte-unchanged

| Phase | Implementation | Regression |
| --- | --- | --- |
| **All phases** | **N/A — byte-unchanged, all five.** `ggml_spike` forwards `args` to `decode_step.run` at line 1603 and holds no arity set. The shim needs no new symbol: `align_ggml_window_copy` shipped with R5B and is the refill's only crossing. `layer_qwen2` gains no constant — `MAX_KV_*` belong to the format owner, not to the model's geometry module | The shared-region byte-identity check (`run-layer-forward-smoke:61-68`), the `unsafe`/`extern` confinement scan (`:79-89`), and the no-`malloc` scan (`:69-72`) all pass **with no diff to check**, which is this row's evidence. `ds-arm-unknown-flag` on `--decode-stepped` is unchanged |

### 4.5 `scripts/kv_plane_reader.py` — the independent reader

| Phase | Implementation | Regression |
| --- | --- | --- |
| Construction | A complete second implementation of section 2.3, written **from this document** rather than from `src/kv_plane.align`. CLI: `--plane PATH` (required), `--pack`, `--geometry`, `--tokens`, `--expect-reject KIND`, `--quiet`. Exit 0 on accept-or-expected-reject, 1 otherwise | the smoke invokes it on every produced container |
| Success | decodes every header and identity field at its declared offset, recomputes all five digests, re-derives `plane_bytes` from the geometry integers, checks region containment/disjointness/alignment/order, checks that columns `>= columns_persisted` are zero, and prints the field table | `ds-kv-save-ok`; the qualification |
| Failure | one `REJECT_KINDS` word per defect class: `MAGIC VERSION HEADER RESERVED REGION TRUNCATED IDENTITY GEOMETRY TOKENS NPAST DIGEST ARGMAX ZEROTAIL` | the mutation corpus, one mutant per kind |
| Malformed input | the mutation corpus of section 5.2, applied to a known-good container | each mutant asserts **both** implementations: the arm's exact `R6_KV_*` code and `error_detail`, and the reader's coarse reject kind |
| Early exit | a missing or unreadable `--plane` exits 1 with one line and reads nothing further | `ds-kv-reader-missing` |
| Cleanup | reads only; writes nothing; opened files are closed by `with` | stated, with reason |
| **Isolation** | The reader is driven as a **subprocess, never imported** — `scripts/run-alignpack-smoke:47-48`'s rule, for its reason: a shared interpreter state would let the two implementations agree by accident | the smoke's invocation shape |

### 4.6 `scripts/layer_forward_fixture.py` — the fixture

| Phase | Implementation | Regression |
| --- | --- | --- |
| Construction | `write_decode_corpus` gains `write_kv_container(path, mutation=None)`: it emits a **known-good** `akvp` v1 container for the synthetic two-layer model from its own pure-Python prefill — the same generator that already produces the plane's expected values — and, given a mutation name, one byte-level defect | every `ds-kv-*` refusal case consumes one of its outputs |
| **The fixture is a third implementation, and that is the point** | The arm writes containers, the reader reads them, and the fixture writes them **from the same document without reading either**. A `ds-kv-load-fixture` case loads a fixture-written container and must decode the same ids as `ds-kv-load-ok` | `ds-kv-load-fixture` |
| Success | **42 files**: one known-good container, one per named mutation (**39**), one honest short-prompt container for `ds-kv-tokens-count`, and one written against a foreign geometry document | the case table |
| Failure | **N/A** — the generator is total over its own fixed inputs and reads no external file | stated, with reason |
| Malformed input | **N/A** — it produces malformed input; it consumes none | stated, with reason |
| Early exit | the argv guard rejects an option-shaped operand, as today | existing |
| Cleanup | writes into `OUTDIR`, which the harness owns and removes | stated, with reason |

### 4.7 `scripts/run-layer-forward-smoke` (fifth block) and `scripts/run-decode-step`

| Phase | Implementation | Regression |
| --- | --- | --- |
| Construction | the fifth block's case tables gain section 5.2's rows; `normalize` gains `kv.write_ns`, `kv.read_ns`, and `timings.first_token_ns`; a new `normalize_persist` adds section 3's exclusion list. **Containers are written under the smoke's existing `work_dir=$(mktemp -d)`** — the checkout is read-only and nothing is written inside it | the block's own `SystemExit(1)` |
| Success | `scripts/decode-step-golden.jsonl` matches case for case at schema 3 | golden compare |
| Failure | any document differs, or a code differs from the table's expectation | `describe_difference` |
| Malformed input | the `NO_DOCUMENT` table | `ds-arity-*`, `ds-path-*`, `ds-arm-unknown-flag` |
| Early exit | the smoke never skips; the qualification prints one `N/A` line and exits 0 | `run-decode-step`'s `na()` |
| Cleanup | the qualification removes the pack, both instrument outputs, every transcript, **and every container**, on every exit path including a signal, and restores the unforced shim | `trap cleanup EXIT HUP INT TERM`, unchanged; free-space reserve raised (section 6 risk 2) |
| **Shared process state** | **N/A.** Each `ggml-spike` invocation is an independent process. The one shared object this capability adds is a **file**, and the two processes that touch it are strictly ordered: the save process exits before the load process starts. The runner never runs them concurrently and the smoke never reuses a container path between cases | stated, with reason |
| **Concurrent independent processes** | **Unsupported and not attempted.** Two concurrent `--kv-save` runs to the same path race at `R6_KV_EXISTS` (section 2.6), which is documented rather than defended; two concurrent `--kv-load` runs of the same file are safe by inspection (both open `O_RDWR` and neither writes) but are **not tested and not promised**. Parallelising the qualification would need `spawn` over non-`Copy` captures — **Request 41** — and no workaround is built | stated, with reason |

## 5. Verification plan

| Scope | Command |
| --- | --- |
| Owner, during development | `gmake layer-forward-smoke` — already in `HOSTED_CHECK_TARGETS`; extended, not replaced |
| Focused qualification | `gmake decode-step-qualification` → `scripts/run-decode-step`, opt-in, capable-only, **outside every aggregate** — unchanged |
| Coding-baseline chain | `gmake baseline-check` **only if the diff touches `Makefile` or a build input.** As designed it does not: no new target, no new `.PHONY` word, no new source file in a build list beyond `src/kv_plane.align`, which enters through `main`'s import graph. **Re-check at the publication head**, because R5E moved `Makefile` and the baseline artifacts and this branch has not yet merged `main` |
| Publication | `python3 scripts/pre-pr --owner-test layer-forward-smoke -- gmake layer-forward-smoke` |
| Formatting | `gmake fmt` before committing Align source; `gmake format-check` and `git diff --check` clean |

**`make ci` is not selected**, and the reason is checked against its actual command graph rather than
asserted: this capability adds no target, so `scripts/check-gate-topology`'s byte-literal `EXPECTED`
does not move; the owner stays `layer-forward-smoke`, already a member; it is not a
`.align-revision` change; and it changes no aggregate membership, check topology, or integration
behaviour. It adds a new **module**, which `make check`'s per-unit compilation covers through the
existing import graph.

### 5.1 The hosted owner — what the fifth block gains

The fifth block already builds a stub shim, a synthetic two-layer alignpack corpus, an `R1_MODEL_IR`
geometry, and a synthetic transcript into `mktemp -d`, and runs 52 documented cases reaching 24
error codes without ggml, a model, a network, or a reference tool. This capability adds, in the same
block and the same temporary tree:

1. `ds-kv-save-ok` — a 13-operand save at `T = 3`, `N = 3`, `KV_WIDTH = 8`; asserts `kv.total_bytes ==
   4608`, `kv.plane_offset == 4096`, `kv.plane_bytes == 512`, `kv.columns_persisted == 3`,
   `kv.verdict == "SAVED"`, `kv.destination == "WRITTEN"`, and `du` agreeing with `total_bytes`.
2. `ds-kv-load-ok` — a separate `ggml-spike` invocation loading that file; asserts `plane.source ==
   "LOADED"`, oracle B `IDENTICAL` over the same **960 B** `ds-steps-3` reports, and `decode.token_ids`
   equal to `model-decode-tokens.txt` element for element.
3. `ds-kv-roundtrip` — oracle Q: the two documents byte-identical after `normalize_persist`.
4. `ds-kv-determinism` — two saves to two paths, `sha256` equal; then again under a perturbed
   environment.
5. `ds-kv-load-fixture` — loading the **fixture-written** container (section 4.6) and decoding the
   same three ids, which is what makes the format a shared contract rather than the arm's habit.
6. The reader run on every produced container, plus one run per mutant.
7. Section 5.2's refusal table.

**Estimated cost.** The block is 7.1 s of the owner's 34.3 s today. The additions are ~28 more
`ggml-spike` invocations at ~90 ms and ~26 Python reader invocations at ~40 ms, with **no new forced
shim build** — the expensive item, and this capability needs none, because every new refusal is
reachable from a malformed file rather than from a forced compute failure. Estimated block cost
11–12 s and owner cost ~39 s: still a seconds-scale hosted check, which is what admits it to
`HOSTED_CHECK_TARGETS`.

### 5.2 The refusal matrix

Every row asserts **both** implementations: the arm's exact `R6_KV_*` code and exact `error_detail`,
and `scripts/kv_plane_reader.py --expect-reject KIND` on the same file. Every row additionally
asserts that **no container was written** and that any pre-existing file at the destination is
byte-unchanged.

| Case | Defect | Code | Reader kind |
| --- | --- | --- | --- |
| `ds-kv-both` | `KV_SAVE` and `KV_LOAD` both paths | `R6_KV_ARGS` | N/A (no file) |
| `ds-kv-save-exists` | destination already a regular file | `R6_KV_EXISTS` | N/A |
| `ds-kv-save-exists-symlink` | destination a symlink to an existing file | `R6_KV_EXISTS` | N/A |
| `ds-kv-save-unwritable` | destination inside a `0555` directory | `R6_KV_UNWRITABLE` | N/A |
| `ds-kv-too-large` | a geometry whose `plane_bytes` exceeds `MAX_KV_PLANE_BYTES` | `R6_KV_TOO_LARGE` | N/A |
| `ds-kv-pack-identity-absent` | the **pack's** source-identity digest is thirty-two zero bytes | `R6_KV_IDENTITY` `pack_absent` | N/A (the defect is in the pack) |
| `ds-kv-load-missing` | `KV_LOAD` names nothing | `R6_KV_UNREADABLE` | N/A |
| `ds-kv-truncated-header` | file of 100 bytes | `R6_KV_TRUNCATED` `header` | `TRUNCATED` |
| `ds-kv-magic` | byte 0 flipped | `R6_KV_MAGIC` | `MAGIC` |
| `ds-kv-version` | `format_version = 2` | `R6_KV_VERSION` | `VERSION` |
| `ds-kv-header-bytes` | `header_bytes = 128` | `R6_KV_HEADER` `header_bytes` | `HEADER` |
| `ds-kv-identity-record-bytes` | `identity_record_bytes = 128` | `R6_KV_HEADER` | `HEADER` |
| `ds-kv-element-type` | `element_type = 1` | `R6_KV_HEADER` | `HEADER` |
| `ds-kv-layout-version` | `plane_layout_version = 2` | `R6_KV_HEADER` | `HEADER` |
| `ds-kv-plane-align` | `plane_align = 3` | `R6_KV_HEADER` | `HEADER` |
| `ds-kv-endian-probe` | probe byte-swapped | `R6_KV_HEADER` `endian_probe` | `HEADER` |
| `ds-kv-doc-schema` | `document_schema_version = 2` | `R6_KV_HEADER` | `HEADER` |
| `ds-kv-high-bit` | `plane_offset` with bit 63 set | `R6_KV_HEADER` `plane_offset` | `HEADER` |
| `ds-kv-flags` | `flags = 1` | `R6_KV_RESERVED` `flags` | `RESERVED` |
| `ds-kv-reserved` | a reserved header byte non-zero | `R6_KV_RESERVED` | `RESERVED` |
| `ds-kv-truncated-total` | last 64 bytes removed | `R6_KV_TRUNCATED` `<a>!=<b>` | `TRUNCATED` |
| `ds-kv-longer-total` | 64 bytes appended; the header untouched | `R6_KV_TRUNCATED` `4672!=4608` | `TRUNCATED` |
| `ds-kv-plane-too-large` | `plane_bytes` one byte above `MAX_KV_PLANE_BYTES`, declared not materialized | `R6_KV_TOO_LARGE` `plane[536870913]` | `HEADER` |
| `ds-kv-logits-too-large` | `logits_bytes` above `MAX_KV_LOGITS_BYTES`, with the matching `n_vocab` | `R6_KV_TOO_LARGE` `logits[16777220]` | `HEADER` |
| `ds-kv-region-overlap` | `identity_offset` moved into the token stream | `R6_KV_REGION` `identity` | `REGION` |
| `ds-kv-region-outside` | `plane_offset` past `total_bytes` | `R6_KV_TRUNCATED` `plane` | `REGION` |
| `ds-kv-region-misaligned` | `plane_offset` not a multiple of `plane_align` | `R6_KV_REGION` `plane` | `REGION` |
| `ds-kv-plane-not-last` | `plane_offset + plane_bytes < total_bytes` | `R6_KV_REGION` `plane` | `REGION` |
| `ds-kv-region-noncanonical` | the plane pushed one whole `plane_align` forward: containable, aligned, disjoint, plane-last, and **not** section 2.3.1's layout | `R6_KV_REGION` `layout` | `REGION` |
| `ds-kv-padding-nonzero` | one byte of the `logits -> plane` padding non-zero; **all five digests still recompute** | `R6_KV_RESERVED` `padding` | `RESERVED` |
| `ds-kv-geometry-layers` | `n_layer = 3` against a two-layer geometry | `R6_KV_GEOMETRY` `n_layer` | `GEOMETRY` |
| `ds-kv-geometry-head-dim` | `head_dim = 8` | `R6_KV_GEOMETRY` `head_dim` | `GEOMETRY` |
| `ds-kv-geometry-plane-bytes` | `plane_bytes` inconsistent with the integers | `R6_KV_GEOMETRY` `plane_bytes` | `GEOMETRY` |
| `ds-kv-identity-pack` | one byte of `source_header_region_sha256` flipped | `R6_KV_IDENTITY` `pack` | `IDENTITY` |
| `ds-kv-identity-pack-size` | `pack_total_bytes` off by one | `R6_KV_IDENTITY` `pack_total_bytes` | `IDENTITY` |
| `ds-kv-identity-geometry` | container written against a perturbed geometry | `R6_KV_IDENTITY` `geometry` | `IDENTITY` |
| `ds-kv-width-mismatch` | container at width 8, operand 16 | **`R6_KV_WIDTH`** `kv_width[8]!=[16]` | N/A (operand-relative) |
| `ds-kv-tokens-count` | a **well-formed container for a two-token prompt**, loaded by a run asking for three. Not a header patch: shortening `token_count` in place would move no region and be refused by the canonical-layout rule at L7 before L12 compared anything | `R6_KV_TOKENS` `count[2]` | `TOKENS` |
| `ds-kv-tokens-id` | third id changed | `R6_KV_TOKENS` `2` | `TOKENS` |
| `ds-kv-digest-tokens` | `token_stream_sha256` flipped | `R6_KV_DIGEST` `tokens` | `DIGEST` |
| `ds-kv-npast` | `columns_persisted = 2`, `token_count = 3` | `R6_KV_NPAST` | `NPAST` |
| `ds-kv-argmax` | `prefill_argmax` not the vector's argmax | `R6_KV_HEADER` `prefill_argmax` | `ARGMAX` |
| `ds-kv-digest-logits` | one logit byte flipped | `R6_KV_DIGEST` `logits` | `DIGEST` |
| `ds-kv-digest-plane` | one plane byte flipped | `R6_KV_DIGEST` `plane` | `DIGEST` |
| `ds-kv-zero-tail` | a column `>= columns_persisted` made non-zero | `R6_KV_DIGEST` `plane` | **`ZEROTAIL`** |
| `ds-kv-reader-missing` | reader given a path that does not exist | N/A | exit 1 |

`ds-kv-zero-tail` is the one row where the two implementations refuse for **different reasons** —
the arm through the plane digest, the reader through the zero-tail invariant — and that is
deliberate: it is the case that proves the reader is not a transcription of the arm.

**Precedence cases**, three, each asserting one ordering from section 2.6: `ds-kv-both-and-missing`
(both operands, one of them absent → `R6_KV_ARGS`), `ds-kv-too-large-and-exists`
(`R6_KV_TOO_LARGE`),
`ds-kv-magic-and-truncated` (a 100-byte file with a wrong magic → `R6_KV_TRUNCATED`, because L2
precedes L3).

#### 5.2.1 Arm-to-reader parity, rule by rule

The review asked the question directly, so the answer is a table rather than a claim: **every rule
the format states, the code the arm raises, the coarse kind `scripts/kv_plane_reader.py` reaches,
and the case.** A blank reader column is a defect the reader cannot see — an operand, a destination,
or the pack — not a rule it declines to check.

| Rule | Arm | Reader | Case |
| --- | --- | --- | --- |
| `magic == AKVP` | `R6_KV_MAGIC` | `MAGIC` | `ds-kv-magic` |
| `format_version == 1` | `R6_KV_VERSION` | `VERSION` | `ds-kv-version` |
| `header_bytes`, `identity_record_bytes`, `element_type`, `plane_layout_version`, `plane_align`, `document_schema_version`, `endian_probe` | `R6_KV_HEADER(<field>)` | `HEADER` | seven cases, one per field |
| every `u64` offset/length has its high bit clear | `R6_KV_HEADER(<field>)` | `HEADER` | `ds-kv-high-bit` |
| `n_layer`/`n_head_kv`/`head_dim`/`n_vocab` `>= 1`; `kv_width`, `token_count`, `columns_persisted`, `prefill_argmax` in range | `R6_KV_HEADER(<field>)` | `HEADER` | reached through the geometry rows below; no header-only mutant is emitted for the four `>= 1` fields because L8 settles each against the loaded geometry |
| `flags`, `reserved_u32`, 48 reserved header bytes, 24 reserved identity bytes | `R6_KV_RESERVED(<field>)` | `RESERVED` | `ds-kv-flags`, `-reserved`, `-reserved-u32`, `-identity-reserved` |
| **inter-region padding is zero** | `R6_KV_RESERVED("padding")` | `RESERVED` | `ds-kv-padding-nonzero` |
| `plane_bytes`/`logits_bytes`/`total_bytes` against section 2.5's three bounds | `R6_KV_TOO_LARGE` `plane[<n>]` / `logits[<n>]` / `container[<n>]` | `HEADER` — **a difference in vocabulary, not in which files are accepted**: the reader gives every declared-magnitude defect its coarse `HEADER`, and adding a fourteenth kind would change the reader's own contract to say nothing new | `ds-kv-plane-too-large`, `ds-kv-logits-too-large`; the container bound is checked in the same place and has no mutant, because a header claiming over 1 GiB is refused by the plane bound first |
| `f.len() == total_bytes` | `R6_KV_TRUNCATED("<a>!=<b>")` | `TRUNCATED` | `ds-kv-truncated-total` (short), `ds-kv-longer-total` (long) |
| every region inside `[0, total_bytes)` | `R6_KV_TRUNCATED(<region>)` | `REGION` | `ds-kv-region-outside`. **The one refusal where the two name different reasons and neither is wrong**: the arm reads containment as "this file is too short for what it declares" and the reader reserves `TRUNCATED` for a length disagreement and calls a bad offset a region defect. Both refuse the same file, at the same point, and the row's expectation states both |
| region 8-byte alignment; `plane_offset % plane_align` | `R6_KV_REGION(<region>)` | `REGION` | `ds-kv-region-misaligned` |
| regions pairwise disjoint | `R6_KV_REGION(<region>)` | `REGION` | `ds-kv-region-overlap` |
| `plane_offset + plane_bytes == total_bytes` | `R6_KV_REGION("plane")` | `REGION` | `ds-kv-plane-not-last` |
| `token_stream_bytes == token_count * 4`; `logits_bytes == n_vocab * 4` | `R6_KV_REGION(<region>)` | `REGION` | none, and the position is what makes that safe: both implementations check these two **before** the canonical-layout rule, so neither can reach the layout rule on an inconsistent header |
| **the four offsets are section 2.3.1's canonical layout** | `R6_KV_REGION("layout")` | `REGION` | `ds-kv-region-noncanonical` |
| `n_layer`, `n_head_kv`, `head_dim`, `n_vocab`, `element_type`, `plane_bytes` against the loaded geometry | `R6_KV_GEOMETRY(<field>)` | `GEOMETRY` | `ds-kv-geometry-layers`, `-geometry-head-dim`, `-geometry-plane-bytes` |
| pack digest and `pack_total_bytes` | `R6_KV_IDENTITY("pack")` / `("pack_total_bytes")` | `IDENTITY` | `ds-kv-identity-pack`, `-identity-pack-size` |
| the **pack's** digest is not all zero | `R6_KV_IDENTITY("pack_absent")` | — . **Asymmetric on purpose**: this is a rule about the pack, not about the container, and it fires before any container exists on a save run. The reader's `--pack` is optional and it has no container to judge here | `ds-kv-pack-identity-absent` |
| geometry digest | `R6_KV_IDENTITY("geometry")` | `IDENTITY` | `ds-kv-identity-geometry`, `-identity-foreign-geometry` |
| `kv_width` equals the operand | `R6_KV_WIDTH` | — (operand-relative; the file is well-formed) | `ds-kv-width-mismatch` |
| `token_count` and each id against the operand | `R6_KV_TOKENS` | `TOKENS` | `ds-kv-tokens-count`, `-tokens-id` |
| `columns_persisted == token_count` | `R6_KV_NPAST` | `NPAST` | `ds-kv-npast` |
| `prefill_argmax` is the persisted vector's argmax | `R6_KV_HEADER("prefill_argmax")` | `ARGMAX` | `ds-kv-argmax`. Vocabulary again: the reader gives the invariant its own kind, the arm reports the header field that is wrong |
| the three region digests recompute | `R6_KV_DIGEST("tokens"/"logits"/"plane")` | `DIGEST` | `ds-kv-digest-tokens`, `-digest-logits`, `-digest-plane` |
| columns at and above `columns_persisted` are zero | — , caught through `R6_KV_DIGEST("plane")` | `ZEROTAIL` | `ds-kv-zero-tail`. **The deliberate asymmetry**, and the only one: the reader owns an invariant the arm does not check separately, which is what proves the reader is not a transcription |
| operand, destination, and write rules — `R6_KV_ARGS`, `R6_KV_EXISTS`, `R6_KV_UNWRITABLE`, `R6_KV_UNREADABLE`, save-side `R6_KV_TOO_LARGE`, and W2–W4's three deferred codes | as named | — (no container to read) | `ds-kv-both`, `-both-and-missing`, `-save-exists`, `-save-exists-symlink`, `-save-unwritable`, `-too-large`, `-too-large-and-exists`, `-load-missing`; W2–W4 deferred (section 11.2) |

**Three asymmetries survive the audit and all three are stated above**: `ZEROTAIL` by design,
`pack_absent` because its subject is the pack, and the two vocabulary differences (`R6_KV_TRUNCATED`
vs `REGION` on containment, `R6_KV_HEADER` vs `ARGMAX`, and `R6_KV_TOO_LARGE` vs `HEADER`), where
both implementations refuse the same file at the same point and only the name differs. Nothing is
accepted by one and refused by the other.

### 5.3 Predicted golden movement

Named in advance so that an unpredicted movement is a finding rather than noise.

| File | Predicted |
| --- | --- |
| `scripts/decode-step-golden.jsonl` | every row schema 2 → 3 (a `kv` object, `plane.source`, `timings.first_token_ns`), plus ~44 new rows. 52 rows become ~96 |
| `scripts/layer-forward-golden.jsonl` | **byte-unchanged** |
| `scripts/model-forward-golden.jsonl` | **byte-unchanged** |
| `scripts/gpu-forward-golden.jsonl` | **byte-unchanged** |
| `scripts/moe-layer-forward-golden.jsonl` | **byte-unchanged** |
| `scripts/ggml-spike-golden.jsonl` | **byte-unchanged** |

`ds-arity-14` replaces `ds-arity-12` as the over-arity case; both are `NO_DOCUMENT` and carry no
golden row, so the change costs zero golden bytes.

### 5.4 The real-model qualification leg

`scripts/run-decode-step` gains one leg per prompt, after the existing `N = 16` run:

```text
1. save    ggml-spike --decode-step PACK GEOM T DOC.save.json REF TRANSCRIPT 256 LOGITS 16 KV.akvp -
2. reader  python3 scripts/kv_plane_reader.py --plane KV.akvp --pack PACK --geometry GEOM --tokens T
3. du      du -k KV.akvp against DOC.save.json's kv.total_bytes
4. load    ggml-spike --decode-step PACK GEOM T DOC.load.json REF TRANSCRIPT 256 LOGITS 16 - KV.akvp
              <- a separate process, with the same operands but the two kv positions swapped
5. compare normalize_persist(DOC.save.json) == normalize_persist(DOC.load.json)
6. repeat  a second save to KV2.akvp; sha256(KV.akvp) == sha256(KV2.akvp)
7. repeat  the same second save under a perturbed environment; same digest
8. ttft    three save runs and three load runs at STEPS=1, no transcript, no logits;
              report timings.first_token_ns and the invocation wall clock, median and spread
```

**Cost.** One extra `N = 16` run per prompt (≈ 20–30 s, section 6 risk 1), one extra `N = 1` run per
prompt per direction × 3 (≈ 6 × 5.3 s), two extra saves, and the reader. Estimated **+400 s**
against R6-STEP-N's measured 507 s, for **≈ 910 s of the 1800 s cap**. Mitigation, in order: the
`ALIGN_LLM_DECODE_STEPS=8` fallback the runner already documents halves the dominant term; failing
that, the persistence leg runs on two prompts rather than four, which costs one prompt's coverage of
oracle Q and no closure cell.

**Disk.** Four containers of 29,970,432 B, plus two determinism duplicates, plus the pack — 180 MB
above what the run already uses. The free-space reserve rises from **pack + 2 GiB to pack + 3 GiB**,
which also covers the second `N = 16` transcript per prompt.

### 5.5 Result — the hosted owner, `gmake layer-forward-smoke`, 2026-08-29

Green at the implementation head, **37.9 s** for the whole owner against 34.0 s before this
capability — inside section 5.1's 39 s estimate, and still a seconds-scale hosted check, which is
what admits it to `HOSTED_CHECK_TARGETS`. Green again at the review-repair head, which adds six
refusal cases: 69 s, measured while a real-model qualification held the CPU, against 57 s measured
the same way at the implementation head. **Only idle figures may be compared with each other**: the
comparable pair is 34.0 s and 37.9 s, and the contended pair is 57 s and 69 s. Both are recorded so
a later disagreement names its cause.

The fifth block reports:

```text
decode step smoke: 12 no-document cases (R6_ARITY, R6_PATH), 107 documented cases, 40 codes
  reached, oracle A' PASS against transcript graphs 2..4 at three step offsets, oracle B IDENTICAL
  over the whole plane including every written-back column, three steps decoding the reference
  loop's own ids, and arm-r5b-unchanged PASS
decode step smoke: akvp v1 -- 51 refusal cases each asserting the arm's code and detail and the
  independent reader's own kind over 13 reject kinds, a 4608-byte container written and reloaded in
  a separate process, a fixture-written container loaded and decoded to the same ids, oracle Q
  byte-identical outside 16 excluded groups, and four writes producing one digest
```

| Assertion | Result |
| --- | --- |
| `ds-kv-save-ok`'s container | `total_bytes` **4608**, `plane_offset` **4096**, `plane_bytes` **512**, `logits_bytes` **128**, `header_bytes` **192** — section 2.3.5's synthetic row exactly |
| The file on disk | `st_size == 4608`, and `st_blocks * 512 >= st_size`, so the container is **dense**: section 2.3's explicit padding is an assertion rather than a claim |
| `ds-kv-load-ok` | `plane.source` `LOADED`, `kv.verdict` `LOADED`, oracle B `IDENTICAL` over **960 B** and `columns_written` 6, and all eleven identity fields equal to the save run's |
| Gate G through the round trip | `output.sha256` equal on both paths; `output.argmax == kv.prefill_argmax == decode.token_ids[0]`; the three ids equal `model-decode-tokens.txt`'s `[24, 9, 27]` |
| `ds-kv-load-fixture` | The **fixture-written** container loads and decodes the same three ids with oracle B `IDENTICAL` — a third implementation of the format, which has read neither the arm nor the reader |
| Oracle Q | The save and load documents are byte-identical after `normalize_persist`, and the comparison is asserted non-vacuous: `decode`, `steps[].sha256`, `output`, `oracle_logits`, and `plane.roundtrip_bytes_compared` are all still inside it |
| Determinism | Four writes — two ordinary, one after them, one under `TZ`/`LANG`/`LC_ALL`/`SOURCE_DATE_EPOCH`/`PWD` perturbation — produce **one** `sha256` |
| Load determinism | Three consecutive load runs produce one document after `normalize` |
| The refusal matrix | **51** rows. Each asserts the arm's exact `R6_KV_*` **and** its exact `error_detail`, that no container was left behind, that the pre-existing file at an occupied destination is byte-unchanged, and — on the **41** rows whose defect is in the container — that `scripts/kv_plane_reader.py` independently reaches its own coarse kind. The other ten are operand, destination, pack, or geometry defects with nothing for the reader to judge |
| Reject kinds reached | All **13**: `MAGIC VERSION HEADER RESERVED REGION TRUNCATED IDENTITY GEOMETRY TOKENS NPAST DIGEST ARGMAX ZEROTAIL` |
| `ds-kv-zero-tail` | The arm refuses through `R6_KV_DIGEST("plane")` and the reader through `ZEROTAIL` — the one row where the two refuse for **different reasons**, which is what proves the reader is not a transcription of the arm |
| `ds-kv-reader-missing` | The reader exits 1 with one diagnostic line and reads nothing further |
| Codes reached | 40, up from 24. Sixteen of the nineteen `R6_KV_*` codes are reached; section 5.7 names the three that are deferred and why |

**Ten mutants, injected into the implementation and each run under the whole owner. All ten die.**
The first six are the implementation head's; the last four were added by the review repair, one per
rule it added, and each was run the same way — inject, `gmake layer-forward-smoke`, restore.

| Mutant | Dies as |
| --- | --- |
| A wrong pack identity accepted (L9 removed) | `ds-kv-identity-pack: expected error_code 'R6_KV_IDENTITY', got ''` |
| The plane digest skipped (L14's `region_matches` removed) | `ds-kv-digest-plane: expected error_code 'R6_KV_DIGEST', got ''` |
| The plane read offset off by four | `ds-kv-load-ok: expected error_code '', got 'R6_KV_TRUNCATED' ('kv_plane')` |
| The logits region not persisted (W2's logits `pwrite` skipped) | `ds-kv-load-ok: expected error_code '', got 'R6_KV_DIGEST' ('logits')` |
| A truncated file accepted (L7's `f.len() == total_bytes` removed) | `ds-kv-truncated-total: 'R6_KV_TRUNCATED'/'kv_plane', not 'R6_KV_TRUNCATED'/'4544!=4608'` |
| The **reader** accepting a flipped reserved byte | `ds-kv-reserved: the independent reader did not reject model-kv-reserved.akvp as RESERVED` |
| **New:** the canonical-layout rule removed (L7) | `ds-kv-region-noncanonical: expected error_code 'R6_KV_REGION', got ''` — and the document it published shows why the rule is load-bearing rather than tidy: the run **loaded the container and decoded `[24, 9, 27]` correctly** with `roundtrip_verdict: "IDENTICAL"` over 960 B, so nothing but the rule stands between the arm and a layout the independent reader refuses |
| **New:** the padding-zero check removed (L6) | `ds-kv-padding-nonzero: expected error_code 'R6_KV_RESERVED', got ''` — again a clean load, because no digest covers the gaps |
| **New:** L7's `MAX_KV_PLANE_BYTES` bound removed | `ds-kv-plane-too-large: 'R6_KV_TRUNCATED'/'plane', not 'R6_KV_TOO_LARGE'/'plane[536870913]'` — the file is still refused, by the next rule down, under the wrong name. This is the finding's exact shape: a true refusal naming the wrong reason |
| **New:** step 7b's degenerate pack-identity refusal removed | `ds-kv-pack-identity-absent: expected error_code 'R6_KV_IDENTITY', got ''` — and the container it wrote carries `source_header_region_sha256` of thirty-two zero bytes, which is the identity the rule exists to refuse |

Two are worth naming. The **reader** mutant matters most: it fails in the reader, on a file the arm
refuses correctly, which is the only way to show that the second implementation is load-bearing
rather than decorative. The **canonical-layout** and **padding** mutants matter for the same reason
in the other direction: with either rule removed the arm loads the container and decodes correctly,
so neither rule is implied by any other check and neither is redundant with a digest.

### 5.6 Result — `gmake decode-step-qualification`, the real model, 2026-08-29

Dense Qwen2.5-Coder-7B-Instruct Q4_K_M, CPU, `KV_WIDTH` 256, `N = 16`, four prompts, three runs
each, plus this capability's save/load leg on all four. Host `aarch64-apple-darwin` (Apple M1),
Homebrew ggml 0.21.0.

**Instrument provenance, stated first because the review turned on it.**
`ALIGN_LLM_LLAMA_DEBUG=/opt/homebrew/bin/llama-debug` — the **pinned Homebrew build**,
`version: 0.2.0 (build 10566, commit bb4caa754)`, the same binary R6-STEP-N section 5.1 used and the
same one `scripts/run-model-forward` resolves. `ALIGN_LLM_LLAMA_EVAL_CALLBACK` is the R2c-patched
instrument under `~/.cache/align-llm/llama.cpp/r2c-v2/<revision>-<digest>/build/bin/`, generation
`r2c-v2`. **That cache holds `llama-eval-callback` and nothing else**, which is the fact an earlier
draft of this section mistook for "this host has no `llama-debug`".

**The run exits 0.** `10 min 41 s` (641 s) of the 1800 s cap, so neither documented fallback
(`ALIGN_LLM_DECODE_STEPS=8`, then `ALIGN_LLM_KV_PERSIST_PROMPTS=2`) was taken. It was run **twice**
on this host — once at the implementation head and once at the review-repair head, which adds four
refusals to the load path — and **every correctness value reproduced exactly**: the same 64 ids, the
same four `plane_sha256`, the same byte counts, the same verdicts. Only the timings moved, and the
table below is the repair head's run.

**`oracle_logits.verdict` is `IDENTICAL` and `byte_identical` on all four prompts, on both the save
and the load path.** The arm's prefill logits are byte-equal to `llama-debug --save-logits`, so gate
G1 holds unconditionally and the whole id chain is rooted in llama.cpp's own argmax with no
tolerance.

**The one `FAIL` in the run is oracle A′ on prompt 1 at step 1, `2391/1e-4` on `ffn_inp-27`, and it
is admitted rather than tolerated** — the exact value R6-STEP-N recorded for that prompt, admitted
under R6's rule because oracle C′ at `k = 1` is byte-identical, so the divergence is llama.cpp's
decode-versus-prefill kernel selection and not this arm's arithmetic. Nothing about it is this
capability's, and the load run reports it identically because the persisted vector round-trips
byte-exactly.

**Rules 2 to 8 of section 3's acceptance rule, on every prompt.**

| Prompt | `T` | Oracle Q | Gate G (load) | Oracle B (load) | Oracle C′ (load) | Determinism |
| --- | --- | --- | --- | --- | --- | --- |
| `case1` | 6 | **IDENTICAL** | PASS (16 ids, sums agree) | IDENTICAL over 26,607,616 B | k=1, 8, 16 byte-identical | one digest |
| `case2` | 3 | **IDENTICAL** | PASS (16 ids, sums agree) | IDENTICAL over 21,102,592 B | k=1, 8, 16 byte-identical | one digest |
| `case3` | 3 | **IDENTICAL** | PASS (16 ids, sums agree) | IDENTICAL over 21,102,592 B | k=1, 8, 16 byte-identical | one digest |
| `case4` | 3 | **IDENTICAL** | PASS (16 ids, sums agree) | IDENTICAL over 21,102,592 B | k=1, 8, 16 byte-identical | one digest |

"Determinism" is three writes per prompt — two ordinary and one under a perturbed environment
(`TZ`, `LANG`, `LC_ALL`, `SOURCE_DATE_EPOCH`, `PWD`) — producing **one** whole-file `sha256`. Across
the two whole runs of the qualification the four digests were the same four, so the writer is
deterministic across processes and across runs, not only within one.

**The container, measured.**

| Prompt | Container | `du -k` | `plane_sha256` | `kv.write_ns` | `kv.read_ns` |
| --- | --- | --- | --- | --- | --- |
| `case1` | 29,970,432 B | 29,268 KiB (= 29,970,432 B) | `8257ea399420…` | 37.0 ms | 25.5 ms |
| `case2` | 29,970,432 B | 29,268 KiB (= 29,970,432 B) | `9d7e4431d1e0…` | 33.6 ms | 23.1 ms |
| `case3` | 29,970,432 B | 29,268 KiB (= 29,970,432 B) | `2f1c25fc6578…` | 30.8 ms | 23.3 ms |
| `case4` | 29,970,432 B | 29,268 KiB (= 29,970,432 B) | `67e734387ce0…` | 42.5 ms | 22.4 ms |

**29,970,432 B is section 2.3.5's predicted reference row exactly**, and `du` reports 29,268 KiB,
which is 29,970,432 B to the byte — the container is **dense**, so section 2.3's explicit padding is
an assertion rather than a claim and the qualification's disk-headroom figure is true. Metadata plus
padding is 610,304 B before the plane, of which 608,256 B is the persisted logit vector; the
non-logit overhead is **2,048 B, or 0.007 %** of the plane. Write is roughly 0.7 to 1.0 GB/s and
read roughly 1.2 to 1.3 GB/s, each including its `crypto.sha256` passes.

**Section 1.4's two labelled diagnostics.** Three runs each direction at `STEPS = 1`, no transcript,
no logits blob. Median with the observed range.

| Prompt | `timings.first_token_ns`, save | `timings.first_token_ns`, load | invocation wall, save | invocation wall, load |
| --- | --- | --- | --- | --- |
| `case1` | 4.119 s [4.003 … 4.144] | 0.658 s [0.654 … 0.716] | 4.140 s | 0.681 s |
| `case2` | 3.587 s [3.561 … 3.804] | 0.662 s [0.660 … 0.675] | 3.609 s | 0.682 s |
| `case3` | 3.014 s [2.995 … 3.023] | 0.666 s [0.659 … 0.676] | 3.033 s | 0.688 s |
| `case4` | 4.258 s [3.776 … 4.896] | 1.451 s [1.303 … 2.709] | 4.286 s | 1.481 s |

**No rate, speedup, or per-token figure is derived from these, and the R6 roadmap gate stays
unmet.** Section 1.4's four reasons stand, and its fifth applies here specifically: `REFERENCE` has
no `-` form, so the model is supplied at thirteen operands and its byte comparison runs **inside the
prefill pass**, which the load direction does not run at all — so the difference between the two
columns overstates what loading saves. The runner prints that sentence beside the numbers.
`case4`'s load spread — 1.30 s to 2.71 s across three runs — is the third of section 1.4's reasons
visible in the data: this is a contended host and the numbers are characterization, not a
measurement anyone should build on.

**The scaling row, unchanged in kind from R6-STEP-N and reported as characterization**: at
`N ∈ {1, 4, 16}` on prompt 1 the run reads 8,741,169,024 / 21,852,852,000 / 74,299,583,904 B from
the pack — the loop's `O(N × model bytes)` term, which loading does not remove and which is why
section 1.4 says a TTFT figure measured here cannot bear the gate.

### 5.7 The goldens that moved — predicted in advance, and reconciled

| File | Predicted (section 5.3) | Actual |
| --- | --- | --- |
| `scripts/decode-step-golden.jsonl` | every row schema 2 → 3, plus ~44 new rows; 52 → ~96 | Every row schema 2 → 3 (a `kv` object, `plane.source`, `timings.first_token_ns`), plus **55** new rows. **52 → 107**. The implementation head reached 101; the review repair added six rows (section 11.4) and rewrote one in place, `ds-kv-tokens-count`, whose `kv.tokens_sha256` and `kv.plane_sha256` change because the case is now an honest two-token container rather than a header patch |
| `scripts/layer-forward-golden.jsonl` | byte-unchanged | **byte-unchanged** |
| `scripts/model-forward-golden.jsonl` | byte-unchanged | **byte-unchanged** |
| `scripts/gpu-forward-golden.jsonl` | byte-unchanged | **byte-unchanged** |
| `scripts/moe-layer-forward-golden.jsonl` | byte-unchanged | **byte-unchanged** |
| `scripts/ggml-spike-golden.jsonl` | byte-unchanged | **byte-unchanged** |

The five unchanged files were **regenerated** with `ALIGN_LLM_LAYER_FORWARD_GOLDEN_UPDATE=1` and
produced no diff, which is what makes "byte-unchanged" a mechanical fact rather than a claim. It
covers two things at once: the twenty-four new `Outcome` fields, which no other arm's renderer
names; and the fixture's newly written pack source-identity record (section 11.3, deviation 4),
which changes `model-pack.alignpack`'s bytes and no document field.

`ds-arity-14` replaced `ds-arity-12` as the over-arity case, and `ds-path-kv-save-empty` and
`ds-path-kv-load-empty` joined it. All three are `NO_DOCUMENT` and carry no golden row, so the move
cost zero golden bytes, as predicted.

**Three of the nineteen `R6_KV_*` codes are not reached by the hosted owner**, each deferred with a
reason rather than omitted: `R6_KV_WRITE_FAILED` needs a filesystem that accepts a create and
refuses a write, which alignpack reaches only through an opt-in `hdiutil` volume gated on
`ALIGN_LLM_ALIGNPACK_ENOSPC` (section 4.1 marks it deferred and names that mechanism as the thing to
reuse); `R6_KV_SIZE_MISMATCH` and `R6_KV_CLEANUP_FAILED` sit behind it on the same failure path and
are deferred with it.

## 6. Risks

1. **The qualification's runtime doubles.** The persistence leg re-runs the `N = 16` loop.
   *Mitigation:* section 5.4's two-step fallback, and the `DECODE_STEPS` constant that already exists.
   *Not hidden:* R6-STEP-N section 5.4 measured why a decode run costs what it costs, and this
   capability does not change that term.
2. **Scratch-space and temp-path hazards — a named prior failure class** (R6-STEP-N risk 5,
   `docs/specs/r4-alignpack-layer-major.md` section 4.4). Every one of its members is closed
   explicitly: write only under `mktemp -d`, keeping the `align-r6-XXXXXX` basename; use `pwd -P`
   physical paths; **refuse before installing the reclaim trap**, never after; test `-L` as well as
   `-e` so a dangling symlink is not mistaken for an absent destination; `chmod -R u+rwX` before
   `rm -rf`, so the `0555` directory of `ds-kv-save-unwritable` cannot survive the cleanup; check
   free space before the first byte, at pack + 3 GiB; and publish **no path-valued field** in the
   document, so the golden cannot pick up a temp path.
3. **Silent integer overflow on file-derived arithmetic.** Every offset, length, and sum in the header
   comes from a file this process did not write, and Align's `i64` wraps silently.
   *Mitigation:* `add_checked`/`mul_checked` before every sum is formed, in `model_ir` rule 2's style;
   L5 refuses any `u64` with the high bit set before it is used; L7's containment and disjointness
   checks are written non-wrapping. `ds-kv-high-bit` is the case.
4. **An out-of-range `bytes.u64(off)` aborts the process.** The language spec is explicit: a read with
   `off < 0` or `off + width > len` **aborts**, the same fail-closed policy as `slice[i]`. A
   truncated container decoded optimistically would crash instead of refusing.
   *Mitigation:* L2 proves `f.len() >= 192` and the header buffer's own `len()` is checked before the
   first field is decoded; every later region read is preceded by its containment check at L7.
   `ds-kv-truncated-header` is the case, and it must **refuse**, not abort — the smoke asserts a
   document, which an abort cannot produce.
5. **A digest could be presented as an identity it is not.** `plane_sha256` says the plane's bytes
   survived; it says nothing about whether the plane is *correct*. *Mitigation:* the acceptance rule
   never rests on a digest alone — oracle B re-verifies the loaded plane through the graphs at every
   step, and oracle Q compares the decoded ids. A container that digests correctly and decodes
   differently fails at oracle Q.
6. **A torn container.** No `fsync` exists (section 7, Request 31), so a power loss mid-write can
   leave a file whose length matches nothing.
   *Mitigation, and the honest framing:* a plane **is a deterministic derivative** of `(pack,
   geometry, tokens, kv_width)`, all of which still exist. A torn container costs one re-prefill, and
   `R6_KV_TRUNCATED` or `R6_KV_DIGEST("plane")` detects it rather than loading it. This is also a
   **correction to Request 31's own forward text**, which predicts that R6's KV cache "is not a
   derivative of anything else and losing it loses the only copy" — see section 8.
7. **A vacuous equality oracle.** Oracle Q compares two documents after dropping sixteen key groups
   — the design named eight and an empirical field-by-field diff found eight more (section 11.3,
   deviation 2); a careless exclusion list would make it pass by comparing almost nothing.
   *Mitigation:* section 3 lists what remains **inside** the comparison rather than only what is
   outside, every exclusion is a **count of work** the load path did not do rather than a result,
   the smoke asserts positively that `decode`, `steps[].sha256`, `output`, `oracle_logits`, and
   `plane.roundtrip_bytes_compared` are still inside, and a mutant that shifts one loaded column by
   one lane changes `steps[1].sha256`, which is inside.
8. **The two-process leg could pass by accident on a warm page cache**, if the "separate process"
   were not separate. *Mitigation:* the runner invokes two `ggml-spike` processes and asserts the
   save process exited before the load process started; `plane.source == "LOADED"` in the second
   document is the assertion that the load path ran at all, and `ds-kv-load-fixture` proves the
   format is readable by something the arm did not write.
9. **Instrument provenance and sampler pinning.** R6 risks 1 and 2, unchanged and still live.

## 7. Deferred and declared limitations

**Declared limitations — each is a live Align gap with a named request, and none is worked around.**

| Limitation | Request | Consequence, stated plainly |
| --- | --- | --- |
| **No durability.** `flush` reaches the kernel, not the device; `file` has no flush or sync at all | **31**, `PROPOSED`, low, non-blocking | This capability makes **no durability claim**. Risk 6 states what a torn file costs and why it is survivable |
| **A container on read-only media cannot be loaded.** There is no `fs.open_ro` and no `fs.size`, so even *learning a file's length* needs `O_RDWR` | **21**, `PROPOSED`, medium | A plane saved to a read-only mount, a root-owned cache, or a container image layer is unreadable by this arm. This is Request 21's **strongest client yet**: unlike the GGUF, this artifact is one this repository *produces*, so the natural place to put it is exactly the shared read-only cache it cannot then read |
| **No exclusive positional create.** `create_rw` truncates; `create_exclusive` returns a sequential `writer` with no `pwrite` | **30**, `PROPOSED`, medium | `R6_KV_EXISTS` is a documented check-then-create race (section 2.6). **Second client** |
| **No incremental digest.** `crypto.sha256` is one-shot over one byte view | **29**, `PROPOSED`, medium | `MAX_KV_PLANE_BYTES` exists because of it (section 2.5), and the pack's payload cannot be digested, which is why model identity is the header-region digest (section 2.4). **Second client** |
| **No way to tell a dangling symlink from an absent path.** There is no `fs.symlink_metadata`, no `lstat`, and no `O_NOFOLLOW` at this pin | none proposed — see below | W4's cleanup removes the destination **name**. If the caller names a dangling symlink, `fs.create_rw` writes through it and `fs.remove` unlinks the symlink, so a failed write leaves a partial container at the link's target while `kv.destination` reports `"REMOVED"` (section 2.6). No request is proposed because refusing symlink destinations outright would change `ds-kv-save-exists-symlink`'s settled alignpack-inherited behaviour, and the exposure is one developer host writing to a path it chose |

**Deferred capabilities.**

- **Saving the post-loop plane** at `T + N` columns, so a session can be resumed mid-generation. It
  needs one more header field and a decision about what `columns_persisted != token_count` means;
  this capability persists the prefill because that is what a *shared prefix* is.
- **Prefix sharing and a cache.** A content-addressed store keyed on section 2.8's recorded tuple,
  longest-common-prefix lookup, and an invalidation rule. This is the capability the R6 roadmap gate
  is actually about, and section 1.4 says why it cannot be pre-empted here.
- **Tiering (DRAM/NVMe), eviction, and residency policy.** Roadmap R6's remaining three lines.
- **A whole-container digest**, once Request 29 ships: it would let a reader certify a container
  without recomputing five separate digests.
- **`R6_KV_WRITE_FAILED` as a hosted case.** It needs a filesystem that accepts a create and refuses
  a write; alignpack reaches it through an opt-in `hdiutil` volume gated on
  `ALIGN_LLM_ALIGNPACK_ENOSPC`. The correct move is to **reuse** that mechanism rather than build a
  second one, and it is deferred to whichever capability needs it first (section 4.1).
- **A TTFT benchmark.** Its own capability, its own corpus, its own baseline, its own gate.
- **The `llama-debug` text corroboration leg**, unchanged from R6 section 10.5, blocked on the same
  missing detokenizer (Request 22).

## 8. Align capability requests

Classified per `CLAUDE.md`. **None blocks this capability, and no new request is proposed.**

| Gap | Classification | Status |
| --- | --- | --- |
| No `fsync`/`fdatasync`/`F_FULLFSYNC` | Genuine Align gap, recorded | **Request 31, `PROPOSED`, stays non-blocking.** This is its **first named consumer**, exactly as its own text predicts. **One correction to that text is owed and is drafted in section 9.4:** it says the R6 KV cache "is not a derivative of anything else and losing it loses the only copy". It *is* a derivative — of `(pack, geometry, tokens, kv_width)` — so a torn container costs one re-prefill, `R6_KV_DIGEST("plane")` detects it, and **31 stays low priority and non-blocking**. Correcting the register upward would be easy and wrong |
| No read-only random-access open (`fs.open_ro`), no `fs.size` | Genuine Align gap, recorded | **Request 21, `PROPOSED`.** Strongest client to date (section 7). One line added to the register's client evidence; **no status change** |
| No exclusive random-access create | Genuine Align gap, recorded | **Request 30, `PROPOSED`.** Second client. `R6_KV_EXISTS` ships the documented check-then-create exactly as `R4_DEST_EXISTS` does, and **no workaround is built** |
| One-shot `crypto.sha256` only | Genuine Align gap, recorded | **Request 29, `PROPOSED`.** Second client. `MAX_KV_PLANE_BYTES` is the consequence and is recorded as a deliberate bound, not a hidden one |
| `buffer` is append-only; `pread` always requests the full capacity | Genuine Align gap, recorded | **Request 38, `PROPOSED`.** Second consumer of the `align_ggml_window_copy` mitigation (section 2.7). No new shim symbol is added |
| A `borrow mut buffer` rebind does not release the prior allocation | Genuine Align gap, recorded | **Request 39, `PROPOSED`.** The refill transient is refilled in place and **never rebound**, for the reason that request measures. Cited client |
| A cross-module call with a `borrow mut` argument refuses every shorter-lived operand | Genuine Align gap, recorded | **Request 49, `PROPOSED`.** This capability is one more client **and the first for which it shapes a module boundary**: the plane refill stays in `decode_step` rather than moving to `kv_plane` because of it (section 2.7). Cited as continuing evidence |
| Indexing arrays of Move element types | Genuine Align gap, recorded | **Request 22, `PROPOSED`, non-blocking.** The token stream is a fixed-width `u32` region and the digests are fixed-width slices of one string — the same avoidance R6-STEP-N deviation 1 records. Cited; no new client shape |
| Non-`Copy` capture in `spawn` closures | Genuine Align gap, recorded | **Request 41, `PROPOSED`.** Relevant only to parallelising the qualification, which is not attempted (section 4.7) |

**No new request is proposed, and the numbering is recorded because it is a live hazard.** At the
implementation head this branch's `docs/align-requests.md` ran 1–46 plus 49, with requests **47 and
48** on `main` only (R5E, PR #143). The merge of `origin/main` at `3df063b` has since brought them
in, so the register now runs **1–49** here and the next free number is **50**. It is **not claimed by
this capability**, and every gap above resolves to an existing entry.

## 9. Reconciliation drafts

**Applied, 2026-08-29.** Every draft below is now in the tree; **four** differ from their draft in
wording and one in substance, and each is noted where it occurs. The fourth wording difference is
section 9.4's `align-llm verification:` line: the draft writes `--kv-save`, which is not a surface
this capability ships, and the shipped register line writes `--decode-step KV_SAVE`. The substantive
one is section 9.4's Request 31 line: the shipped text states the correction as a correction —
naming the prediction it overturns — rather than only asserting the new fact. The wording ones are
section 9.1's code count (the shipped item says "nineteen `R6_KV_*` codes plus item 27's own
`R6_KV_WIDTH`", which is the same twenty, counted so a reader can tell which is reused), section
9.1's "384 bytes" (the shipped item says "192 bytes and one `fstat`", the cost of the **earliest**
refusals L2–L7; 384 is still the cost of the deepest cheap refusal, L9, and section 2.3's
region-order property 2 keeps that figure), and section 9.2's HANDOFF block, which records results
rather than a plan because the work is done.

Numbering assumes R6-DECODE-KV-STEP1 keeps roadmap item **27** and R6-STEP-N item **28**, which they
hold on their branches. **This must be re-checked when both merge**: this branch takes
`git merge origin/main` — never a rebase — and if `main` has moved the numbering, item 29 and every
cross-reference to it move with it.

### 9.1 `docs/specs/roadmap.md` — item 29

> 29. **R6-KV-PERSIST — the KV plane persisted to disk and reloaded in a fresh process.** Design in
>     [`r6-kv-persist.md`](r6-kv-persist.md). Items 27 and 28 build a correct KV plane and throw it
>     away when the process exits, so every invocation on the same prompt recomputes the prefill.
>     This capability ships the first of the five mechanisms the R6 gate lists — **session KV** — and
>     nothing else: `--decode-step` gains `KV_SAVE` and `KV_LOAD` operands, and a new `akvp` v1
>     container holds the prefill plane, the prompt's token ids, the prefill's last-position logit
>     vector, and an identity record binding all three to the exact pack, geometry, width, and plane
>     layout that produced them. **Every mismatch is a refusal, never a silent re-prefill**: twenty
>     `R6_KV_*` codes in a stated validation order, cheapest first, so a wrong file costs 384 bytes
>     rather than 29 MB. Acceptance is that the two paths are the same run — a separate process
>     loading a saved plane decodes the same `N` ids and publishes a byte-identical document outside
>     a named exclusion list, with item 28's gate G, oracle B, and oracle C′ carried forward and
>     asserted on both processes, and with the writer's determinism proved by double-write digest
>     equality rather than by a checked-in hex golden. Owner `gmake layer-forward-smoke`, whose fifth
>     block gains a save/load round trip, a fifty-case refusal matrix, and an independent Python reader
>     driven as a subprocess; focused `gmake decode-step-qualification`. **No TTFT claim.** The run
>     reports `timings.first_token_ns` for prefill-then-decode against load-then-decode as a labelled
>     diagnostic. **What it leaves open:** the R6 gate asks that TTFT improve on repeated coding tasks
>     *sharing a prefix*. There is no prefix-sharing corpus, no key, no lookup, and no invalidation;
>     loading removes one prefill pass and keeps every per-step weight sweep, which item 28 measured
>     at 4.37 GB per step. The gate stays unmet and the next capability toward it is prefix-keyed
>     lookup on top of resident weights.

Under **`## R6: Persistent KV` → `### Gate`**, the `**未達。**` paragraph gains one sentence:

> item 29（R6-KV-PERSIST）はKV planeをディスクに永続化し別プロセスで再読み込みする——5項目のうち
> session KVのみ——が、prefix共有・DRAM/NVMe tier・invalidationは持たず、TTFTの主張もしない。

### 9.2 `HANDOFF.md` — the active block

> ## Active: R6-KV-PERSIST (2026-08-29)
>
> Branch `agent/r6-kv-persist`, stacked on `agent/r6-step-n` at `a9c6161`, which is in review, which
> is stacked on `agent/r6-decode-kv-step1` at `1671810`. **Design only; nothing implemented and
> nothing committed.** When both land on `origin/main` this branch takes `git merge origin/main` —
> never a rebase — and reconciles roadmap numbering, request numbering, and the `baseline-check` row.
>
> **Capability.** The R6 KV plane persisted to disk and reloaded in a fresh process, dense
> Qwen2.5-Coder-7B Q4_K_M, CPU. `docs/specs/r6-kv-persist.md` is the authoritative ledger. **All
> four** of the design gate's triggers fire — a changed public CLI arm, a **new persisted format**
> plus a document schema bump, a **process ownership boundary**, and a coordinated invariant across
> three or more modules: the plane's layout stops being private to `src/decode_step.align` and
> becomes a published contract with an independent second reader.
>
> **Not started.** Everything. In implementation order:
> 1. `src/kv_plane.align` — constants, the 192-byte header, the 192-byte identity record, region
>    arithmetic with checked sums, `read_header`, `write_container`.
> 2. `src/decode_step.align` — arity 12 and 13, `R6_KV_ARGS`, steps 6a/6b, the save path after step
>    10, the load path replacing steps 9–10, the chunked refill through
>    `model_forward.window_put`, schema 3 and its `kv` object.
> 3. `scripts/kv_plane_reader.py` — written **from the spec**, never from `src/`, driven as a
>    subprocess.
> 4. `scripts/layer_forward_fixture.py` — `write_kv_container`, good plus ~24 mutants.
> 5. The fifth smoke block's ~44 cases, `normalize_persist`, and the regenerated golden.
> 6. `scripts/run-decode-step`'s save → separate-process load → compare leg, the double-write
>    determinism check, the `du` check, and the `first_token_ns` diagnostic.
>
> **Next action.** Review this design, then step 1.
>
> **Blockers.** None. R6-STEP-N's publication is a sequencing dependency, not a blocker.
>
> **Constraints.** No new Align request is proposed; number 50 stays free and must be re-checked
> after the merge, because this branch's register lacks 47 and 48. Requests 21, 29, 30, 31, 38, 39,
> and 49 each gain a cited client and **none changes status**. **No durability claim and no TTFT
> claim**; `timings.first_token_ns` is a labelled diagnostic. One correction is owed to Request 31's
> own forward text — see the spec's section 8.
>
> **Verification (planned).** `gmake fmt`, `gmake format-check`, `git diff --check`, then
> `gmake layer-forward-smoke`, then `gmake decode-step-qualification`, then
> `python3 scripts/pre-pr --owner-test layer-forward-smoke -- gmake layer-forward-smoke`.
> `make ci` is **not** selected: no target, no aggregate membership change, no topology change, no
> `.align-revision` change.

### 9.3 `docs/align-development.md` — the `--decode-step` arm

Under **The `--decode-step` arm**, the heading becomes `(R6-DECODE-KV-STEP1, R6-STEP-N,
R6-KV-PERSIST)`, the operand list is replaced, and three paragraphs are added:

> `--decode-step` is selected by its exact first operand and is five, six, seven, nine, ten, eleven,
> **twelve, or thirteen** operands. **Eight is `R6_ARITY`**, inherited verbatim from
> `--model-forward`.
>
> ```text
> ./ggml-spike --decode-step PACK GEOM.json TOKENS DOC.json REF.gguf TRANSCRIPT.txt KV_WIDTH LOGITS.bin STEPS KV.akvp -
> ./ggml-spike --decode-step PACK GEOM.json TOKENS DOC.json REF.gguf TRANSCRIPT.txt KV_WIDTH LOGITS.bin STEPS -        KV.akvp
> ```
>
> `KV_SAVE` (`args[11]`) and `KV_LOAD` (`args[12]`) each accept `-` for "absent", the convention
> `TRANSCRIPT` has used since R5B and `LOGITS` since R6-STEP-N. **Supplying both is `R6_KV_ARGS`**,
> not a copy. Neither has a default and neither is read from the environment.
>
> With `KV_SAVE`, the arm writes an **`akvp` v1** container **after the prefill and before the first
> decode step**: a 192-byte header, the prompt's token ids as little-endian `u32`, a 192-byte
> identity record of five `crypto.sha256` digests plus the pack's `total_bytes`, the prefill's
> last-position logit vector, and the plane itself, page-aligned and last. `PACK` is still required
> **with `KV_LOAD`** — loading skips the prefill, not the model: every decode step still streams the
> weights.
>
> With `KV_LOAD`, the arm validates the container against the run it was asked for — pack identity,
> geometry digest, `KV_WIDTH`, token ids, plane layout, and five digests, in that order, cheapest
> first — and refuses on any mismatch with an `R6_KV_*` code. **There is no fallback: a mismatch
> never silently re-prefills.** The document is `R6_DECODE_STEP` at **schema 3**, with a `kv` object
> and `plane.source` (`"PREFILL"` | `"LOADED"`) in every document, and `timings.first_token_ns` as a
> labelled diagnostic. **No durability is promised** — Align has no `fsync` at this pin — and a torn
> container is detected by `R6_KV_TRUNCATED` or `R6_KV_DIGEST("plane")`, costing one re-prefill.

### 9.4 `docs/align-requests.md` — three client lines and one correction

Under **Request 31**, the "Consequence for the client" paragraph's last sentence is corrected, and
the `align-llm verification:` line is updated:

> It is recorded because the next client is a persistent KV cache (roadmap item 29,
> `docs/specs/r6-kv-persist.md`). **That client has now been designed, and it corrects this
> paragraph's own prediction:** the KV container **is** a deterministic derivative — of the pack, the
> geometry document, the token ids, and `KV_WIDTH` — so a torn container costs one re-prefill, and
> `R6_KV_DIGEST("plane")` detects it rather than loading it. This request therefore **stays `low`
> and non-blocking**; the first client that would raise it is one whose artifact is not reproducible
> from inputs that still exist.
>
> `align-llm verification: R6-KV-PERSIST's `--kv-save` would call `f.sync()` before reporting
> `kv.destination: "WRITTEN"`, and `gmake layer-forward-smoke` would pass unchanged in outcome.`

Under **Requests 21, 29, 30, 38, 39, and 49**, one client line each, naming
`docs/specs/r6-kv-persist.md` and the exact section. **No `Status:`, `Priority:`, or `Blocking:` field
changes on any of the seven.**

## 10. Author consistency pass

One pass, ledger against prose, performed before this document was finished. What it found and what
changed:

1. **The load path could not start.** The first draft persisted the plane and the token ids and
   nothing else. But the decode loop's step 1 consumes `d_1`, the argmax of the *prefill's* logits,
   and a load run computes no prefill — so the container as first drafted was unloadable. The logits
   region, `n_vocab`, `prefill_argmax`, and `logits_sha256` were added, and section 2.8's table
   records the two rejected cheaper answers and what each would have cost. Without this pass the
   design would have shipped a format its own consumer cannot resume from.
2. **The equality oracle would have been much weaker.** Following from 1: with only `prefill_argmax`
   persisted, `output` and `oracle_logits` would have had to leave oracle Q's comparison, and
   **gate G1 would have been lost by loading**. Section 3 now states the re-scoping explicitly —
   G1 asserted on the save run, *inherited* by the load run — rather than letting a reader assume the
   load run re-derived what it read.
3. **Two fields called the same thing.** An early draft named the header field `columns_written`,
   which is also the document's field for `T + N`. They are different numbers — the header's is `T`,
   because the save happens before the first decode step — so the header's became
   `columns_persisted`, and section 2.3.1 says why the two differ.
4. **The digest bound was inherited rather than derived.** The draft carried alignpack's
   `MAX_HEADER_REGION_BYTES` of 128 MiB. The plane at `KV_WIDTH` 4096 is 448 MiB, so that bound would
   have refused a legal `MAX_ATTENTION_WIDTH` run. Section 2.5 derives 512 MiB from this
   capability's own facts, states that the plane is already resident so the bound is not a memory
   bound, and states why refusing beats writing a container with no identity.
5. **The chunked refill was described as optional.** An early draft said "read the plane". Align's
   `buffer` is append-only and `f.pread` always requests the full capacity, so a single-buffer read
   of a 29 MB region into a 1 MiB transient over-reads unless the plane is **last** and
   `f.len() == total_bytes` is already proved. Section 2.3's region-order property 1 and section 2.6's
   L7 were made contract because of it, and the ordering `L7 before L14` is now load-bearing rather
   than tidy.
6. **`R6_KV_WIDTH` was going to be a new code.** The draft had `R6_KV_WIDTH_MISMATCH`. R6-STEP-N
   section 2.3 already refused to mint a second code for "the plane is the wrong width" and gave the
   reason; section 2.6 reuses the existing code with a widened detail and records the decision.
7. **The fourth design-gate trigger was nearly copied rather than checked.** R6-STEP-N withdrew the
   "three or more modules" trigger with a reason. Section 1.2 re-derives it rather than copying
   either answer: it fires here because the plane's *layout* changes status from a private
   convention to a published contract with an independent reader, which is a different fact from
   R6-STEP-N's.
8. **The TTFT section claimed and disclaimed in the same breath.** An early draft both reported a
   proxy and said no claim was made, without saying why the gate cannot be met. Section 1.4 now gives
   four concrete reasons — no corpus, weight streaming dominates, page cache, four of five mechanisms
   absent — and records the source analysis's "ship no timing at all" recommendation as accepted in
   substance and narrowed, rather than silently overruled.
9. **The module split needed a reason, not a preference.** "Keep `decode_step.align` from growing"
   is not a contract. Section 2.7 states the real boundary: `kv_plane` owns everything expressible
   with borrowed views and by-value returns, and the plane refill stays with the plane's owner
   because **Request 49** refuses the cross-module `borrow mut`. That makes the split checkable.
10. **`ds-kv-zero-tail` was going to assert the same thing twice.** Both implementations would have
    reported a digest mismatch, which proves nothing about their independence. The reader now owns a
    `ZEROTAIL` invariant the arm does not check separately, so that row is the one case where the two
    refuse for different reasons — and section 5.2 says so, rather than letting it look like an
    inconsistency.
11. **Deferred cells must be marked, not omitted.** `R6_KV_WRITE_FAILED` has no hosted case: it needs
    a filesystem that accepts a create and refuses a write. Section 4.1 marks it deferred with
    alignpack's own `hdiutil` mechanism named as the thing to reuse, rather than inventing a case
    name that will not exist.

## 11. Ledger-to-diff mapping, and the deviations

One pass over the final diff, in `r6-step-n.md` section 11's shape. A cell with no counterpart in
the diff is named and given its reason rather than omitted.

### 11.1 Ledger rows to the diff

| Ledger row | Where it lives | Evidence |
| --- | --- | --- |
| 2.2 arity {5,6,7,9,10,11,12,13}; 8 still `R6_ARITY`; 14 and above `R6_ARITY` | `decode_step.run` | `ds-arity-3`, `ds-arity-8`, `ds-arity-14` (`NO_DOCUMENT`, no golden bytes) |
| 2.2 `KV_SAVE` is `args[11]`, `KV_LOAD` is `args[12]`, `-` is absent | `decode_step.run` | `ds-kv-args-dash-dash` (legal, byte-identical shape to the 11-operand form), `ds-path-kv-save-empty`, `ds-path-kv-load-empty` |
| 2.2 both supplied is `R6_KV_ARGS`, detail `kv[save+load]` | `execute`, step 2b, before `stage_inputs` | `ds-kv-both`; precedence by `ds-kv-both-and-missing` |
| 2.2 no default, no environment variable | `run` reads only `args`; `execute` reads no environment | the `kv` object is `0/0/"-"` on every pre-schema-3 arity in the golden |
| 2.2 `PACK` mandatory on a load run | `execute` opens the pack before `schedule_decode` on both paths | `ds-kv-load-ok` publishes a full `pack` block; the decode loop's own reads are in `pack.reader_bytes_read` |
| 2.3 header at offset 0, 192 bytes, every field at its declared offset | `kv_plane.encode_header_image` / `read_header` | `scripts/kv_plane_reader.py` decodes each field independently; one mutant per field in the matrix |
| 2.3 `endian_probe` is a canary, not a mode switch | `read_header` validates it and has no second decode path | `ds-kv-endian-probe` → `R6_KV_HEADER` `endian_probe` |
| 2.3 region order, 8-byte alignment, `plane_align`, plane **last**, no trailing padding | `kv_plane.plan_header` and L7 | `ds-kv-region-overlap`, `-region-outside`, `-region-misaligned`, `-plane-not-last` |
| 2.3.1 **one canonical layout**, re-derived by writer, arm, and reader from the same three helpers | `kv_plane.plan_header` and `read_header`'s L7 share `canonical_identity_offset` / `canonical_logits_offset` / `canonical_plane_offset`; `kv_plane_reader.py` re-derives all four independently | `ds-kv-region-noncanonical` → `R6_KV_REGION("layout")` / `REGION` |
| 2.3 padding written, not a hole, **and zero on both sides** | `write_container`'s `write_padding` over one `PAD` buffer; `kv_plane.padding_zero` at L6 on the load path | the smoke's `st_blocks * 512 >= st_size` check; `ds-kv-padding-nonzero` → `R6_KV_RESERVED("padding")` / `RESERVED`, on a file whose five digests all still recompute |
| 2.3.3 five digests, all `crypto.sha256`; `hash64` in no persisted field | `kv_plane.write_container`, `digest_hex`, `region_matches` | `ds-kv-digest-tokens`, `-digest-logits`, `-digest-plane`, `-identity-pack`, `-identity-geometry` |
| 2.3.4 plane layout version 1 = the arm's own buffer image | `write_container` takes `borrow plane: slice<u8>` and writes it whole | `ds-kv-load-fixture`: a container laid out by a third implementation loads and decodes the same ids |
| 2.3.5 measured sizes | `plan_header` | the synthetic row asserted exactly (4608/4096/512/128/192); the reference row in section 5.6 |
| 2.4 identity: six fields, each naming itself | L8–L14 | one matrix row per field |
| 2.4 model identity is the **pack's** header-region digest | `execute`'s 32-byte `pread` at `source_record_offset + 48` | `ds-kv-identity-pack`, `ds-kv-identity-pack-size`; the fixture now writes a non-degenerate record (deviation 4) |
| 2.4 every mismatch is a refusal, never a silent re-prefill | there is no fallback branch in `load_plane` | every matrix row publishes `decode.steps_completed == 0` and no `steps[]` row |
| 2.5 `MAX_KV_PLANE_BYTES` etc. at step 6a, before the pack is opened | `stage_inputs` | `ds-kv-too-large` (`plane[537001984]`), reached with a geometry no pack describes |
| 2.5 all three bounds re-checked on **load** at L7, ahead of the length comparison | `kv_plane.read_header` | `ds-kv-plane-too-large` (`plane[536870913]`), `ds-kv-logits-too-large` (`logits[16777220]`); both declared rather than materialized |
| 2.4 a thirty-two-zero-byte pack digest is refused, not compared | `execute`'s step 7b over `kv_plane.all_zero` | `ds-kv-pack-identity-absent` → `R6_KV_IDENTITY("pack_absent")`, asserting no container was written |
| 2.5 refusing beats skipping | no "digest absent" flag exists in the format | the reader has no path that accepts a container without recomputing all five digests |
| 2.6 validation order 1–16 with 2b, 6a, 6b inserted | `run`, `execute`, `stage_inputs` | `ds-kv-both-and-missing`, `ds-kv-too-large-and-exists` |
| 2.6 load order L1–L14, cheapest first | `load_plane` and `kv_plane.read_header` | the whole matrix; a wrong file is refused after 192 bytes and one `fstat` |
| 2.6 `R6_KV_WIDTH` reused at L11 with a widened detail | `load_plane` | `ds-kv-width-mismatch` → `kv_width[8]!=[16]` |
| 2.6 save order W1–W4; partial file removed | `kv_plane.write_container` | `ds-kv-save-unwritable` leaves no file; W4's `fs.remove` path is code-reviewed and its case is deferred (11.2) |
| 2.6 `R6_KV_EXISTS` and its documented race; symlinks followed both ways | `execute`'s step 6b over `fs.exists` | `ds-kv-save-exists`, `ds-kv-save-exists-symlink`; both assert the pre-existing file is byte-unchanged |
| 2.7 ownership and cleanup on every path | every handle and buffer is a bare local at its scope | `lifetime.*_created == *_freed` and `graph_balance_failures == 0` on every documented case |
| 2.7 the module split, and Request 49 as its reason | `src/kv_plane.align` takes only borrowed views and returns by value; the refill is `decode_step.refill` | `gmake check`/the ggml-spike build; section 8's Request 49 client line |
| 2.7 chunked refill through `window_put`, transient never rebound | `decode_step.refill` | the "plane offset off by four" mutant dies; no new shim symbol appears in the diff |
| 2.7 no in-arm read-back of the metadata regions | `write_container` returns after W3 | the reader does that job instead, on every produced container |
| 2.8 schema 3, `plane.source`, the `kv` object in **every** document at one shape | `SCHEMA_VERSION`, `render_plane`, `render_kv` | `record()` asserts `schema_version == 3`; every golden row carries the same `kv` key set |
| 2.8 no path-valued field in `kv` | `render_kv` emits verdict words only | the golden; `error_detail` is the only place a path can appear and it is placeholdered (deviation 7) |
| 2.8 `output`/`oracle_logits` populated on a load run from the persisted vector | `load_plane` fills `logits_view`; the existing digest/`compare_prefill_logits` path is unchanged | `ds-kv-load-ok` asserts `output.sha256` equal on both paths |
| 2.8 `timings.first_token_ns`, zeroed by `normalize` | `decode_loop` at step 1; `render_timings_step` | both runners' `normalize`; three-consecutive-runs checks pass |
| 2.9 saturation checked, not assumed | `add_checked`/`mul_checked` before every file-derived sum | `ds-kv-high-bit` refuses a `u64` with bit 63 set before it addresses anything |
| 3 oracle P | the save/load pair plus the independent reader | section 5.5, section 5.6 |
| 3 oracle Q | `normalize_persist` in both runners | section 5.5, section 5.6; the exclusion list grew by eight groups, eight to sixteen (deviation 2) |
| 3 gate G re-scoped: G1 asserted on the save run, inherited on the load run | `compare_prefill_logits` runs on both, over persisted bytes on the load path | section 5.6 states it as the weaker statement it is |
| 3 determinism by double write, not a hex golden | four writes in the smoke, three in the qualification | section 5.5, section 5.6 |
| 4.5 the reader is a subprocess, never imported | `read_container` shells out to `python3` | the smoke's invocation shape |
| 4.6 the fixture is a third implementation | `kv_container` in `scripts/layer_forward_fixture.py` | `ds-kv-load-fixture` |
| 4.7 containers under `mktemp -d`; the `0555` directory cannot survive cleanup | the smoke's `work_dir`; `chmod -R u+rwX` before `rm -rf` in the shell trap | the runner leaves nothing behind |
| 5 `make ci` not selected; `Makefile` untouched | no target, no `.PHONY` word, no build-list entry | `gmake gate-topology-check`; `baseline-check` `N/A` |

### 11.2 Closure matrix cells with no counterpart, named

| Cell | Why |
| --- | --- |
| 4.1 `R6_KV_WRITE_FAILED` | **Deferred, as section 4.1 records.** It needs a filesystem that accepts a create and refuses a write; alignpack reaches it only through an opt-in `hdiutil` volume gated on `ALIGN_LLM_ALIGNPACK_ENOSPC`, and the correct move is to reuse that mechanism rather than build a second one |
| `R6_KV_SIZE_MISMATCH` (W3) | Same path. It fires only when a `pwrite` succeeded and the resulting length disagrees, which needs the same filesystem |
| `R6_KV_CLEANUP_FAILED` (W4) | Same path, one step further: it needs a write failure **and** a failing `fs.remove` |
| 4.1 move-in/out, source nulling, replacement, return | `N/A` — no ownership transfer is added. `KvHeader` and `KvWrite` are returned by value; the plane and the logits arrive as `slice<u8>` borrows |
| 4.5 the reader's cleanup phase | `N/A` — it reads only, writes nothing, and closes through `with` |
| 4.6 the fixture's failure and malformed-input phases | `N/A` — it produces malformed input and consumes none, and is total over its own fixed inputs |
| 4.3 `R6_KV_TRUNCATED("kv_plane")` from the refill, as a `ds-kv-*` case | **Unreachable from a malformed container, by construction rather than by omission.** L7 proves `f.len() == total_bytes` and `plane_offset + plane_bytes == total_bytes` before the refill reads a byte, so any container that reaches the refill has a complete plane region; a file short of its own plane is refused as `R6_KV_TRUNCATED("<a>!=<b>")` at L7 (`ds-kv-truncated-total`) and one long is refused there too (`ds-kv-longer-total`). The cell is closed by an injected mutant — section 5.5's "plane read offset off by four" — which is the only way to make the refill short |
| Two concurrent `--kv-load` runs of one container | **Unsupported and not attempted** (section 4.7). Safe by inspection, not tested, and not promised; parallelising would need Request 41 |

### 11.3 Deviations from the ledger, with reasons

Eight, each recorded rather than absorbed.

1. **`write_container` takes two more borrowed views, and `KvHeader` carries `pack_total_bytes`.**
   Section 4.1 declares
   `write_container(dest, borrow h: KvHeader, borrow ids, borrow logits, borrow plane) -> KvWrite`.
   The identity record needs six values, of which two — the pack's digest and the geometry
   document's digest — are computed by the caller and cannot be derived from the three payload
   views. They are passed as `borrow pack_digest: slice<u8>` and `borrow geometry_digest:
   slice<u8>`, read-only views that cross a module boundary freely, and `pack_total_bytes` becomes a
   twenty-seventh scalar on `KvHeader` rather than a second by-value record carrying one number.
   `KvWrite` likewise returns the three digests it computed, so the caller never recomputes a
   29 MB `sha256` it has already paid for. No ownership transfer is added and no borrow rule is
   worked around.
2. **Oracle Q's exclusion list is eight groups larger than section 3 drafted — eight became sixteen
   — and every addition is work the load path legitimately did not do.** The design named `kv`,
   `plane.source`, `plane.readback_ns`, `plane.upload_ns`, `graph`, `schedule`, `timings`, and
   `lifetime`. An empirical field-by-field diff of a save-run document against a load-run document
   found **eight** more keys that differ: `pack.reader_pread_count` and `pack.reader_bytes_read`
   (the prefill's own weight reads), `head.node_count`, `head.pread_ns`, and `head.compute_ns` (the
   prefill's own head graph), `window.reuse_count` and `window.member_placements` (window fills the
   prefill performed), and the whole `reference` block. Section 3 now carries the shipped sixteen
   rather than the drafted eight, and section 6 risk 7 counts sixteen.

   **Seven of the eight are measurements of work. The eighth is a verdict, and saying otherwise
   would be false.** `reference.verdict` moved into the exclusion list, and it is a verdict rather
   than a count — so the honest statement is narrower than "no digest, id, or verdict was excluded":
   **no digest, no id, and no verdict of the decode itself was excluded**, and the one verdict that
   was is `reference.verdict`, excluded because the comparison behind it does not run on a load path
   at all (deviation 3, and section 2.8 now carries it as a public behaviour change). The
   qualification asserts it positively on the save run, so it is asserted somewhere rather than
   merely dropped. The smoke asserts explicitly that `decode`, `steps[].sha256`, `output`,
   `oracle_logits`, and `plane.roundtrip_bytes_compared` are all still **inside** the comparison,
   which is section 6 risk 7's guard against a vacuous oracle.
3. **`reference.verdict` is `"-"` on a load run, and that is a behaviour change rather than only a
   test exclusion.** R5B's byte comparison of every member against the source GGUF lives in the
   prefill pass, so a load run performs none of it. Before this change `schedule_decode` set
   `REFERENCE_IDENTICAL` whenever `reference_present && code == 0`, which on a load run would have
   published a pass over **zero comparisons**. The condition is now additionally `&& !loading`. The
   prefill path is character-for-character unchanged, and the qualification asserts
   `reference.verdict == "IDENTICAL"` on the save run, where the comparison actually ran.
4. **`scripts/layer_forward_fixture.py` now writes the pack's source-identity record.** The region
   was reserved and left zero, which made the hosted `akvp` container's model identity a digest of
   nothing: a bug that handed the writer an empty identity would have compared equal to the file's
   and passed. The record is written in `docs/specs/r4-alignpack-layer-major.md` section 2.4.6's
   field order, moves no offset, and changes no document field — proved by regenerating all six
   goldens and observing that five are byte-unchanged (section 5.7).
5. **`timings` is rendered by `decode_step.render_timings_step` rather than by
   `model_forward.render_timings`.** `first_token_ns` is this arm's field, and that renderer is
   shared with `--model-forward`, `--model-forward-gpu`, `--layer-forward`, and
   `--moe-layer-forward`. Extending it would have moved four goldens this capability promises are
   byte-unchanged, so the eight shared fields are restated in one twelve-line function and the
   promise stays mechanical.
6. **A load run publishes `graph.graph_count: 0` and `graph.node_count_total: 0`.** Section 3 says
   graph and schedule "legitimately differ"; it did not say what the load run publishes. Zero is
   the honest value — the run builds no prefill graph at all — and the fifth block asserts it
   positively rather than skipping the check, so a load run that somehow built a prefill graph is a
   failure rather than an exemption.
7. **`R6_KV_EXISTS` names the sanitized destination path in `error_detail`, and the smoke
   placeholders it.** Section 2.8's "no path-valued field" row is about the `kv` object and stays
   true. The destination is a `mktemp -d` path, so a golden row carrying it verbatim would be a
   function of the run's temporary directory — section 6 risk 2's named class. `normalize` replaces
   an `error_detail` that begins with `work_dir` by `<path>`, exactly as it already placeholders the
   five top-level path fields, and the case table asserts the placeholder so the substitution
   cannot hide a wrong detail.
8. **Section 2.5's bounds are checked twice.** Section 2.5 puts them at step 6a, which covers the
   save direction, where this process computes `total_bytes` from the geometry and the operand. On a
   load run all three numbers come out of a file this process did not write, so `read_header` checks
   them again at L7. The codes and detail shapes are the same `R6_KV_TOO_LARGE` /
   `plane[<n>]` / `logits[<n>]` / `container[<n>]`. *(At the implementation head only
   `MAX_KV_CONTAINER_BYTES` was re-checked on load; the review repair added the other two and moved
   all three ahead of the `f.len() == total_bytes` comparison — section 11.4.)*

### 11.4 The review repair, and what it added to the contract

One comprehensive review of the implementation head found one blocker, five major findings, and
thirteen minor ones across two reviewers. Every finding is dispositioned in the pull request; the
four that **changed a public promise** are recorded here, because a refusal the arm did not make
before is a contract addition and not a bug fix.

| Addition | Rule | Code and case | Why it is an addition rather than a repair |
| --- | --- | --- | --- |
| **Canonical region layout** (section 2.3.1) | The four offsets must equal the one layout the format's own arithmetic produces | `R6_KV_REGION("layout")`; `ds-kv-region-noncanonical` | The arm previously accepted any containable, aligned, disjoint, plane-last layout while `scripts/kv_plane_reader.py` re-derived the canonical one and refused everything else. Two implementations disagreeing about which files are legal is a format with two meanings; the rule is promoted rather than the reader relaxed, because the writer produces exactly one layout and determinism is already a contract |
| **Zero padding between regions** (section 2.3, property 4) | The three inter-region gaps are zero | `R6_KV_RESERVED("padding")`; `ds-kv-padding-nonzero` | Section 2.3 promised the property and only the reader enforced it. **No digest covers the gaps**, so a container carrying data there round-tripped every digest and loaded |
| **`MAX_KV_PLANE_BYTES` and `MAX_KV_LOGITS_BYTES` on load** (section 2.5) | Both bounds are re-checked at L7 against the header's own claim, before `f.len()` is compared | `R6_KV_TOO_LARGE` `plane[<n>]` / `logits[<n>]`; `ds-kv-plane-too-large`, `ds-kv-logits-too-large` | Section 2.5 said "both directions" and the load direction checked only the container bound, so an oversized declared plane was refused at L8 as `R6_KV_GEOMETRY` — a true refusal naming the wrong reason |
| **A degenerate pack identity** (section 2.4) | The pack's `source_header_region_sha256` must not be thirty-two zero bytes | `R6_KV_IDENTITY("pack_absent")`; `ds-kv-pack-identity-absent` | An all-zero digest compares equal to an all-zero digest, so `R6_KV_IDENTITY("pack")` passed over nothing. Deviation 4 fixed the *fixture* that exposed it; this fixes the *arm* |

Two further findings changed a **case** rather than a rule: `ds-kv-longer-total` covers the side of
`f.len() != total_bytes` that `ds-kv-truncated-total` did not, and `ds-kv-tokens-count` became an
honest two-token container because a header-only patch is now refused by the canonical-layout rule
before the token count is compared. `scripts/kv_plane_reader.py`'s padding refusal moved from
`REGION` to `RESERVED` so that the two implementations name the same reason, which keeps
`ds-kv-zero-tail` the **only** row where they do not.

**The remaining findings changed no contract**: section 5.6's record was re-taken with the pinned
`llama-debug` (section 5.6, and section 5.6.1 is deleted with the source-build narrative it
described), and the rest are counts, citations, and wording corrected in place — the sixteen
exclusion groups, `reference.verdict`'s row in section 2.8, section 4.3's unreachable cell, the
fourth wording deviation in section 9, and the dangling-symlink limitation in section 2.6 and
section 7.

Three rows of section 5.2's matrix were **added** rather than deviated from: `ds-kv-reserved-u32`
and `ds-kv-identity-reserved` split section 2.6's L6 into the three reserved fields it actually
covers, and `ds-kv-identity-foreign-geometry` complements `ds-kv-identity-geometry` with a container
written against a genuinely different geometry document rather than a flipped byte — the flip proves
the field is read, the foreign container proves it means what it says. The matrix ships **51** rows
against the ledger's forty: forty-five at the implementation head and six more from the review
repair (section 11.4).
