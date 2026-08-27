# R4-ALIGNPACK-LAYER-MAJOR: the alignpack v1 container, its layer-major writer, and its verifier

Status: plan of record for the Track B capability named by `docs/specs/roadmap.md` section R4
(`align-pack model.gguf`; "layer-major + layer-local block grouping + expert hotness + prefetch
group"). It is authoritative for the R4 public contract: the `main --pack` and `main --pack-verify`
CLI arms, the **alignpack v1 binary container**, the `R4_ALIGNPACK` and `R4_ALIGNPACK_VERIFY`
documents at `schema_version: 1`, the new `src/alignpack.align` owner module, the one function
extracted from `src/model_ir.align` so that claim arithmetic keeps a single producer, and the
sequential-read metric the roadmap gate's second half is measured with.

`docs/specs/roadmap.md` remains authoritative for delivery order and for the R4 gate itself.
`docs/specs/align-llm.md` remains authoritative for the architecture the container serves — section
4.2's `model.gguf → align-pack → model.alignpack` pipeline, section 5's `Block IR → Layout Plan →
alignpack` stage, and section 6's rule that *NVMeは細かいrandom readに使用しない。alignpackでblockを
連続配置し、大きなchunkとして読み込む*, which is the sentence this capability turns into a file
format. `docs/specs/r1-qwen-model-ir.md` and `docs/specs/r1b-gptoss-moe-ir.md` remain authoritative
for the Block IR that is this layout's **input**: R4 invents no block, no role, no claim, and no
ordering of its own — it copies the Model IR's own block sequence into bytes.

This document triggers the `CLAUDE.md` proportional design gate on four counts: a new public CLI
surface (two verbs), a **new persisted format** (alignpack v1) that a later runtime will read, two
new versioned exchanged documents, and a process boundary — this is the first align-llm capability
that writes a multi-gigabyte artifact and the first that can exhaust a disk.

The capability is **designed, not implemented**. Section 5 records what it deliberately does not do;
section 1.4 states which half of the roadmap R4 gate this discharges and on what evidence.

## 1. Purpose, scope, non-goals, and the gate

### 1.1 Goal

Rewrite one GGUF file into one alignpack v1 file whose **tensor bytes are identical** and whose
**blocks are each one contiguous byte range**, and prove both properties by reading the two
containers back and comparing them byte for byte.

The R4 gate has two halves and they are different kinds of claim:

- *元GGUFとのtensor内容一致* — an equality, discharged by exhaustive comparison. It is discharged by
  `--pack-verify`, which streams both containers and compares every claimed byte.
- *連続read量の改善* — an improvement, which requires a **defined metric, a measured baseline, and a
  measured result**. Section 2.6 defines the metric, section 2.2 records the baseline measured on
  the real model on this host, and section 4.4's qualification is what re-measures it against a pack
  it just wrote.

Three properties are load-bearing and are argued rather than assumed:

- **Streaming, in both directions.** The reference model is 4,683,073,536 bytes. Neither the writer
  nor the verifier may hold a tensor, a block, or a container in memory. Peak resident bytes are two
  fixed windows and the tables, and section 4.6 measures that rather than asserting it. Section 2.7.
- **The pack is self-describing in the form its consumer can read.** R5's loader is Align code whose
  entire file surface is `pread` plus the eighteen `_le`/`_be` scalar decoders. A manifest it can
  walk with those and nothing else is a fixed-width binary table, not JSON. Section 2.4.1 argues
  this against the alternative rather than assuming it.
- **Bytes are never trusted because they were just written.** A writer that reports success from its
  own bookkeeping proves nothing about the file. Every acceptance claim in section 4 comes from
  re-reading the container — with `--pack-verify` for content and with an independent Python reader
  for layout.

### 1.2 In scope

1. Two new CLI arms, `main --pack MODEL.gguf OUT.alignpack [OUT.json]` and
   `main --pack-verify MODEL.gguf PACK.alignpack [OUT.json]`, in the two-form shape
   `--inspect-gguf`, `--model-ir`, and `--expert-trace` already use (section 2.3).
2. The **alignpack v1 container**: magic, versioned header, name stream, block table, member table,
   source-identity record, and a payload laid out layer-major with layer-local block grouping
   (section 2.4).
3. A new module `src/alignpack.align` owning the container codec, the layout planner, the streaming
   copy, the streaming verifier, the sequential-read statistics, both document renderers, and every
   `R4_*` code.
4. One extraction in `src/model_ir.align`: `pub fn resolve_claims`, lifted verbatim out of the
   existing per-member claim pass so that the packer and the `R1_MODEL_IR` renderer consume **one**
   producer of `claimed_absolute_offset` / `claimed_nbytes` (section 2.9).
5. The `R4_ALIGNPACK` and `R4_ALIGNPACK_VERIFY` documents at `schema_version: 1` (section 2.5),
   including the per-block sequential-read statistics for **both** containers.
6. The owner `scripts/run-alignpack-smoke` and `make alignpack-smoke`, driven by the existing
   `scripts/gguf_fixture.py` qwen2 and gpt-oss corpora, plus a new **independent Python reader**
   `scripts/alignpack_reader.py` that asserts the layout invariants without consulting `src/`.
7. The opt-in focused qualification `scripts/run-alignpack-qualification` and
   `make alignpack-qualification`, which packs the real model into a caller-named temporary
   directory, verifies it, reports the measured improvement, and deletes it (section 4.4).

### 1.3 Non-goals

- **No dequantization, no re-quantization, no transformation of any kind.** A member's bytes in the
  pack are the same bytes, in the same order, as the member's bytes in the GGUF. The only thing that
  changes is *where they are*. This is what makes the equality half of the gate checkable at all.
- **No expert hotness ordering and no prefetch groups.** Roadmap section R4 names both. Both need
  a real MoE activation trace, which `docs/specs/r2a-expert-trace.md` section 4.5 records does not
  exist on this host, and a cache policy, which is R3. Ordering blocks by a hotness rank invented
  without a trace would be a guess persisted into a format. Section 5.1 and 5.2 record them as
  deferred with their container fields **reserved and explicitly zero-valued in v1**, so adopting
  them later is a flag flip and a reordering, not a format break.
- **No metadata rewrite.** alignpack v1 carries no GGUF metadata KV pairs. A consumer that needs
  `qwen2.attention.head_count` reads the `R1_MODEL_IR` document or the source GGUF. Copying the
  metadata into the pack would create a second copy of a truth that already has one owner, and
  section 2.4.6 shows the source-identity record makes the pairing checkable without it.
- **No tokenizer.** `tokenizer.ggml.tokens` is an array of Move-element strings, which is
  `docs/align-requests.md` Request 22, deliberately unconsumed since R1.
- **No in-place update, no incremental repack, no append.** The pack is written once from an empty
  destination. There is no v1 operation that modifies an existing pack.
- **No compression.** `std.compress` ships gzip and zstd, and a quantized weight is already
  near-incompressible; compression would also destroy the property that a block is one `pread`.
- **No mmap.** `fs.read_bytes_view` requires an `arena {}` and commits the whole file; R0 rejected
  it for a 5 MB read of a 4.68 GB file and R4 rejects it for the same reason plus the `SIGBUS`
  hazard `../align/draft.md:2897` records for a mapped file another process truncates.
- **No runtime, no loader, no residency decision.** R5 owns reading the pack into VRAM/DRAM/NVMe
  tiers. R4 produces a file and a number. Section 5.4.
- **No durability guarantee.** Align ships no `fsync` (section 2.1). The pack is a reproducible
  derivative of a file that still exists; a crash costs a rerun, not data. Section 5.5.3.
- **No writing anywhere the caller did not name.** The packer creates exactly one file, at exactly
  the path in `argv`. It creates no directory, no sibling, and no temporary. Section 4.4 states how
  the qualification keeps 4.36 GiB out of the repository.

### 1.4 Gate statement

The roadmap gate for R4 is *元GGUFとのtensor内容一致と、連続read量の改善を確認できること*.

1. **Dischargeable — content identity.** `make alignpack-smoke` proves on synthetic qwen2 and
   gpt-oss containers that every member's bytes survive the move, that `--pack-verify` detects a
   single flipped byte and names its exact offset in both containers, and that every error code
   fires on its own fixture. `scripts/run-alignpack-qualification` proves it on the real 4.68 GB
   model, over all 4,677,120,000 payload bytes.
2. **Dischargeable — sequential-read improvement, on this model.** Section 2.6 defines the metric.
   Section 2.2 records the baseline **already measured** on the real model: 58 blocks occupy 89
   maximal contiguous ranges, only 27 of 58 blocks are contiguous, and a one-read fetch of every
   block would transfer 11,130,544,128 bytes to obtain 4,677,120,000 bytes of payload —
   2,379,786 ppm, a 2.38x read amplification. The pack's layout makes every block exactly one range
   and its span exactly its payload: 58 ranges, 1,000,000 ppm, by construction and re-measured from
   the written file. The qualification prints both sides.
3. **NOT discharged — the MoE case on real weights.** The per-expert improvement is the largest one
   this format offers, and it is verified **synthetically only**: an `ExpertBlock`'s six members are
   six planes of six different stacked tensors, so its claims are six ranges spanning most of a
   layer's expert region in the source and one range in the pack. No gpt-oss GGUF exists on this
   host — `docs/specs/r1b-gptoss-moe-ir.md` section 4.4 records the same pending user decision — so
   every real-model number in this document is the dense qwen2 case. Cells that depend on real MoE
   weights are marked **MOE-PREREQ** in section 3.
4. **NOT discharged — hotness and prefetch groups.** Section 1.3 and section 5.1–5.2. The roadmap
   sentence names four layout properties and this capability ships two of them. Saying so is the
   section 1.4 honesty requirement; the container reserves the fields for the other two.

R4's honest terminal state is therefore: *the format is defined and self-describing, the copy is
byte-exact and verified over a real 4.68 GB model, the sequential-read improvement is defined,
baselined, and measured on that model, and two of the four named layout properties are deferred with
their format surface reserved.*

## 2. Public-contract ledger

### 2.1 Verified Align surface at pin `4b515f8d`

Every row was verified against the pinned compiler's own sources at the exact pin
(`/Users/hiro/Projects/align` at `4b515f8d`, whose `HEAD` equals `.align-revision`), not inferred
from a guide. R4 consumes **no** `PROPOSED` request.

| Surface | Status at the pin | Evidence | Consequence for R4 |
| --- | --- | --- | --- |
| `fs.create_rw(path) -> Result<file, Error>` | **Shipped.** Opens `O_RDWR\|O_CREAT\|O_TRUNC`, mode `0644`, `O_CLOEXEC` | `crates/align_sema/src/lib.rs:53262`; `crates/align_runtime/src/lib.rs:9890` — whose own comment calls it "the fresh-alignpack output path" | The destination constructor. It **truncates**, so refusing an occupied destination is R4's obligation, not the kernel's (section 2.8 step 5) |
| `f.pwrite(data, off) -> Result<i64, Error>`, `data` is `bytes` (`slice<u8>`), `str`, or `string` | **Shipped.** Implemented over `write_all_at`, which loops to completion and retries `EINTR` | `crates/align_sema/src/lib.rs:56169`; `crates/align_runtime/src/lib.rs:10005-10027` | **A short write is impossible.** `pwrite` returns the full length or a negative status. This is the opposite of `pread` and it removes an entire error class from the copy loop |
| `f.pread(b: mut buffer, off) -> Result<i64, Error>` | **Shipped**, unchanged from R0. A **short read is possible** and surfaces as-is | `src/gguf.align:288-330` | The copy loop must complete a short read rather than mistake it for EOF, exactly as `gguf.refill` does |
| `f.len() -> Result<i64, Error>` | **Shipped.** A live `fstat`, never cached, so it tracks the packer's own `pwrite`s | `crates/align_runtime/src/lib.rs:10038` | The final size assertion of section 2.8 step 11 is a real observation of the written file |
| `file` methods are exactly `pread`, `pwrite`, `len` | **Closed set.** The compiler's own diagnostic enumerates them | `crates/align_sema/src/lib.rs:56209` | There is no `close`, no `truncate`, no `seek`, and no `sync`. `Drop` closes the fd |
| An owned handle must be bound to a local before any method call | **Enforced.** `fs.create_rw(p)?.pwrite(...)` is a compile error | `crates/align_sema/src/lib.rs:56126` | Both handles are bare locals in the copy function, exactly as `src/gguf.align:74-77` already requires for the reader |
| `buffer(cap)`, `b.bytes() -> slice<u8>`, `b.len()`, `b.append(...)` | **Shipped**, unchanged from R0 | `src/gguf.align:302-330` | The two windows |
| `buf.put_u8 / put_i8 / put_{u16,i16,u32,i32,u64,i64,f32,f64}_{le,be}` — **eighteen** encoders, mirroring the eighteen decoders | **Shipped.** The suffix table is literally shared with the decode side | `crates/align_sema/src/lib.rs:56343`, `59251-59277`; example `crates/align_driver/tests/runway_a2_binary_codec.rs:20-31` | The header and both tables are written with native encoders. **There is no encode-side gap**; the guess that one existed is refuted |
| `buffer` has **no** `clear`, `truncate`, `reset`, `reserve`, or `capacity` | **Absent.** The runtime exposes exactly six buffer entry points (`_new`, `_bytes`, `_len`, `_free`, `_put`, `_append`) and `put`/`append` always extend from `len` | `crates/align_runtime/src/lib.rs`, ABI enumeration | **Verified not to bite R4.** Every window reuse in sections 2.7 goes through `pread`, which *overwrites* the buffer's length; the table writer rebinds a fresh `buffer` per chunk, the `window = buffer(capacity)` rebinding `src/gguf.align:344` already proves |
| `buffer(N)` degrades **silently to capacity 0** when the reservation fails, and a `pread` into a zero-capacity buffer returns `0` without a syscall | **Shipped behavior.** `try_reserve_exact`, then `if b.cap == 0 { return 0 }` | `crates/align_runtime/src/lib.rs:10090-10102`, `9971` | A zero-length read at an offset already proved in range is **not** EOF and must not be reported as truncation. R4 reuses `gguf.refill`'s exact discipline as `R4_WINDOW_UNAVAILABLE` |
| `fs.exists(path) -> bool` (**not** a `Result`; an error folds to `false`) | **Shipped** | `crates/align_sema/src/lib.rs:53344` | The only available occupied-destination guard, and the reason section 2.8 records a check-then-create race rather than hiding it |
| `fs.remove(path) -> Result<(), Error>` | **Shipped** | `crates/align_sema/src/lib.rs:53345` | Partial-pack cleanup (section 2.8 step 12) |
| `crypto.sha256(data) -> array<u8>` (32 bytes, owned), one byte view, **one shot** | **Shipped**, and already linked by this repository (`src/prompt_artifact_io.align:22`) | `crates/align_sema/src/lib.rs:54374-54386` | Usable for the bounded header-region digest of section 2.4.6. **There is no `sha256_init`/`update`/`final`**, so a whole-file digest would need a whole-file byte view. Section 5.5.1 |
| `crypto.constant_time_equal(a, b) -> bool`, two byte views | **Shipped** | `crates/align_sema/src/lib.rs:54331-54344` | The per-window fast path of the verifier (section 2.7); a mismatching window is then re-scanned byte-wise to name the exact offset |
| `encoding.hex_encode(bytes) -> string` | **Shipped** | `crates/align_sema/src/lib.rs:45179` | Renders the 32-byte digest into the document |
| `time.instant() -> i64` (monotonic nanoseconds), `time.now() -> i64` | **Shipped.** No `Duration` type, no unit conversion; plain `i64` nanoseconds | `crates/align_sema/src/lib.rs:53645-53684` | The elapsed metrics of section 4.6. Both are **Impure** |
| `hash64` / `hash128` (wyhash), import-free | **Shipped** but **explicitly not stable across builds** per `../align/docs/impl/core-design/hash.md` | same | **Deliberately not used.** A persisted identity must not depend on a value the language declines to stabilize. The pack's identity is `crypto.sha256` |
| `fsync` / `fdatasync` / `F_FULLFSYNC` | **Absent from the whole runtime.** `../align/docs/impl/std-design/fs.md` records "no `fsync`, or crash-durability promise" as a deliberate non-goal | ABI enumeration, zero hits | No durability claim is made. Section 5.5.3 |
| `mkdir` / `create_dir` / temp-file creation | **Absent** | ABI enumeration, zero hits | The packer never creates a directory. The qualification's temporary tree is made by `mktemp -d` in the shell, exactly as every existing runner does |
| `fs.size` / `stat` / `metadata` | **Absent.** The only way to learn a file's length is to open it and call `f.len()` | ABI enumeration | Combined with the absence of a read-only random-access open, sizing a read-only model requires `O_RDWR`. New client evidence for `docs/align-requests.md` Request 21 |
| `fs.create_exclusive(path) -> Result<writer, Error>` | **Shipped**, but returns a sequential `writer` whose only methods are `write` and `flush` | `crates/align_sema/src/lib.rs:53164`, `55795` | **Cannot be used here**: the packer needs positional `pwrite` to place a member at a planned offset. Section 5.5.2 |
| `io.copy(r: reader, w: writer) -> Result<i64, Error>` | **Shipped**, streams through a fixed buffer | `crates/align_sema/src/lib.rs:56218` | **Not applicable**: it copies a whole stream end to end and takes no source range or destination offset. A rearranging copy is exactly what R4 does |
| `array<i64>` columns behind `borrow` record accessors; `array_builder<i64>`; concatenated name stream with explicit `[start, end)` spans | **Shipped**, three prior instances (`GgufTable`, `BlockPlan`, `TranscriptScan`) | `docs/specs/r1-qwen-model-ir.md` section 7 | The layout plan is the same shape, fourth instance |
| `sort()` over `array<i64>` | **Shipped** | `docs/specs/r1-qwen-model-ir.md` section 2.7 | The range-merge of section 2.6 sorts one packed `array<i64>` per block |

**No `PROPOSED` request is consumed, and each existing one is re-examined:**

- **Request 21** (`fs.open_ro`): unconsumed and **strengthened twice**. R4 opens the model read-only
  and must still ask for `O_RDWR`; and because there is no `fs.size`, even *learning the model's
  length* requires a writable descriptor. A model on read-only media cannot be packed at all.
- **Request 22** (indexing arrays of Move elements): unconsumed. The layout plan holds no
  `array<string>`.
- **Request 23** (huge-struct-copy warning on `borrow` parameters): unconsumed, **fourth client**.
  `PackPlan` is another wide columns-plus-stream record read through `borrow` accessors.
- **Request 24** (`builder` as a `borrow mut` parameter): unconsumed. The document renderers return
  owned `string`s, as `model_ir`'s do.
- **Requests 25–28**: untouched. R4 runs no child process, parses no text numbers, sorts no strings,
  and reads no growing accumulator.

Section 5.5 records the three genuine gaps R4 found, in the form `CLAUDE.md` requires.

### 2.2 Measured layout of the reference model, and the baseline

Everything in this section was measured on this host against
`/Users/hiro/models/qwen2.5-coder-7b-instruct-q4_k_m.gguf` by an independent Python reader of the
GGUF tensor table. It is the **baseline** half of the gate, and it is recorded here so the
qualification compares against a number that already exists rather than one it invents at run time.

**Container facts**, agreeing exactly with the values `docs/specs/roadmap.md` records for the merged
R0 and R1 qualifications: GGUF version 3, alignment 32, 29 metadata KV pairs, 339 tensors,
`data_offset` 5,953,536, `file_size` 4,683,073,536, `total_tensor_bytes` 4,677,120,000. The tensor
data section has **zero interior gaps**: every tensor abuts the next in file order.

**Finding 1 — the reference file is already layer-major, and `docs/specs/r1-qwen-model-ir.md`
section 2.5.6's characterization of *why* its blocks are non-contiguous is inaccurate.** That
document states the writer "grouped tensors by *role* across all layers". Measured file order is the
opposite: layer 0's twelve tensors occupy `[312,514,560, 461,627,392)` with no foreign tensor
between them, and 25 of 28 layers are likewise one unbroken range. The *numbers* R1 published are
exact and reproduce here — `blk.0.attn_norm.weight` at 312,514,560, `blk.0.attn_v.weight` at
460,122,112, an eight-tensor span of 149,112,832 bytes carrying 17,020,928 — but the cause is
**intra-layer interleaving**, not role-major grouping: within a layer the writer emits `attn_norm`,
then the four MLP tensors, then the remaining attention tensors. R4's blocks are defined by
function, so the MLP tensors sit *inside* the attention block's span. Correcting the sentence in
`r1-qwen-model-ir.md` is a documentation follow-on for the implementation commit; this document does
not edit it.

**Finding 2 — three layers are additionally out of order.** Layers 6, 14, and 22 are each split into
two ranges by tensors of other layers, so their spans are 728,852,480, 675,098,624, and 578,203,648
bytes to carry 131,135,488, 149,112,832, and 131,135,488. This is why a format that *guarantees*
contiguity is worth more than a file that happens to be mostly contiguous.

**Finding 3 — `output.weight` is not at the end.** It sits at 3,452,207,104, between layers, while
`output_norm.weight` is the final tensor at 4,683,059,200. The output `WeightBlock`'s two members
therefore span 1,230,866,432 bytes to carry 447,082,496.

**The measured baseline**, over the 58 blocks `src/frontend_qwen.align` produces for this model
(1 embedding `WeightBlock`, 28 `AttentionBlock`, 28 `MlpBlock`, 1 output `WeightBlock`), using the
section 2.6 definitions:

| Block kind | Blocks | Ranges | Span bytes | Payload bytes | Amplification (ppm) |
| --- | --- | --- | --- | --- | --- |
| `WeightBlock` | 2 | 3 | 1,537,427,456 | 753,643,520 | 2,039,993 |
| `AttentionBlock` | 28 | 56 | 5,132,980,224 | 469,962,752 | **10,922,100** |
| `MlpBlock` | 28 | 30 | 4,460,136,448 | 3,453,513,728 | 1,291,478 |
| **Total** | **58** | **89** | **11,130,544,128** | **4,677,120,000** | **2,379,786** |

27 of 58 blocks are contiguous. Every `AttentionBlock` is two ranges. The worst three blocks are
`AttentionBlock[6]` (614,264,832 span for 16,547,840 payload — 37.1x), `AttentionBlock[14]` (31.9x),
and `AttentionBlock[22]` (28.0x).

**The planned result**, computed from the same tensor table under the section 2.4.7 layout with
`block_align` 4096 and `member_align` 64: 58 blocks, **58 ranges**, span 4,677,120,000, payload
4,677,120,000, **1,000,000 ppm exactly**, with 57,344 bytes of interior alignment padding — 12 ppm
of overhead. The qualification re-derives all of this from the file it wrote rather than from this
table.

**Finding 4 — the MoE case is the larger prize and is unmeasured on real weights.** For a gpt-oss
container, `ExpertBlock(L, e)` claims plane `e` of six stacked tensors
(`ffn_gate_exps.weight/.bias`, `ffn_up_exps.weight/.bias`, `ffn_down_exps.weight/.bias`,
`docs/specs/r1b-gptoss-moe-ir.md` section 2.5.3). Those six claims are six ranges, and each stacked
tensor is `n_expert` planes wide, so a single-read fetch of one expert transfers on the order of
`n_expert` times its payload. In the pack it is one range at 1,000,000 ppm. With no gpt-oss GGUF on
this host, this is asserted only over `scripts/gguf_fixture.py`'s synthetic gpt-oss corpus, where
every plane offset is generator-known.

**Throughput measurements on this host** (Apple M1, 8 cores, 16 GiB, APFS on `/dev/disk3s5`), used
only to size constants and state a time budget — **no performance claim is made and none of these is
a gate**:

| Measurement | Result | Method |
| --- | --- | --- |
| Sequential `pread`, 1 MiB windows | 3.247 GB/s | 1 GiB of the model, warm cache |
| `pread`+`pwrite` copy, 1 MiB windows | 0.82 GB/s median of 3 | 512 MiB **of payload** moved (so twice that in device traffic), `fsync` at the end |
| Same, 4 MiB | 1.00 GB/s median of 3 | " |
| Same, 8 MiB | 0.92 GB/s median of 3 | " |
| Same, 16 MiB | 1.34 GB/s median of 3 | " |
| `sha256` throughput | 2.261 GB/s | Python `hashlib`, 512 MiB |
| `sha1` / `blake2b` / `md5` | 2.265 / 0.697 / 0.655 GB/s | " |
| Free space on the target volume | 27 GiB | `df` |

**The copy-window measurement does not separate 4 MiB from 16 MiB.** Run-to-run variance spans
0.68–1.62 GB/s at *every* size, which is wider than the gap between sizes. Section 2.7 therefore
chooses 4 MiB on syscall count and resident-bytes grounds and explicitly declines to claim it is the
fastest.

**The `sha256` measurement settles the identity budget.** At 2.26 GB/s a whole-file digest of the
reference model costs about 2.07 s — cheap *in Python*. It is not available in Align at all
(section 2.1), and section 2.4.6 chooses the bounded region digest instead: 5,953,536 bytes at that
rate is about 2.6 ms.

### 2.3 CLI surface

```text
main --pack MODEL.gguf OUT.alignpack               # writes the pack; document to stdout
main --pack MODEL.gguf OUT.alignpack DOC.json      # writes the pack; document to DOC.json + summary
main --pack-verify MODEL.gguf PACK.alignpack       # reads both; document to stdout
main --pack-verify MODEL.gguf PACK.alignpack DOC.json   # document to DOC.json + summary
```

Arity is checked before any path or file work, so an arity failure produces no output and no file.
`--pack` accepts exactly three or four operands after the program name; `--pack-verify` likewise. The
`MAX_PATH_BYTES` lexical guard of `src/main.align:624` — non-empty, `<= 4096` bytes, no NUL — applies
to **every** operand of both arms, including the destination, before anything is opened. Exit mapping
is R0's, reused verbatim: `Ok(())` on `status: "ok"`, `Err(Error.Invalid)` on `status: "error"`
after the document has been emitted, `Err` with no document for an arity, path, or OS failure. Both
forms of an arm emit **byte-identical document bytes**.

**One contract differs from every prior Track B arm and the difference is stated rather than
inherited.** For `--inspect-gguf`, `--model-ir`, and `--expert-trace`, the two-operand form is pure:
it reads and prints. For `--pack`, **both** forms write `OUT.alignpack`; the optional third operand
selects only where the *document* goes. There is no read-only or dry-run form of `--pack` in v1: a
planner that computed a layout without writing it would be a fourth code path with no consumer, and
the document `--pack` emits already contains the whole plan.

**There is no `--force`, no `--arch`, and no `--align` flag.** An occupied destination is an error,
not something a flag makes acceptable, because the thing being overwritten may be a 4.36 GiB
artifact (section 2.8 step 5). The architecture is selected from the container's own
`general.architecture`, exactly as `--model-ir` does (`src/main.align:537`), because the file is the
subject. The alignments are properties of the format recorded in its header, not caller options; a
caller-chosen alignment would make two packs of the same model incomparable and would need its own
validation row.

The `--pack` summary block, in this exact order:

```text
alignpack:
status:            OK | ERROR
arch:              <architecture, or - when absent>
pack path:         <sanitized path>
schema:            1
format version:    1
blocks:            <integer>
members:           <integer>
payload bytes:     <integer>
padding bytes:     <integer>
duplicated bytes:  <integer>
pack bytes:        <integer>
bytes read:        <integer>
bytes written:     <integer>
elapsed ns:        <integer>
src ranges:        <integer>
pack ranges:       <integer>
src ampl ppm:      <integer>
pack ampl ppm:     <integer>
destination:       WRITTEN | REMOVED | UNTOUCHED
error:             <code>             # only when status is ERROR
detail:            <identifier>       # only when status is ERROR
```

The `--pack-verify` summary block:

```text
alignpack verify:
status:            OK | ERROR
verdict:           IDENTICAL | MISMATCH
blocks:            <integer>
members:           <integer>
compared bytes:    <integer>
bytes read:        <integer>
elapsed ns:        <integer>
src ranges:        <integer>
pack ranges:       <integer>
src ampl ppm:      <integer>
pack ampl ppm:     <integer>
src span bytes:    <integer>
pack span bytes:   <integer>
first mismatch:    <member@source_offset+delta, or ->
error:             <code>             # only when status is ERROR
detail:            <identifier>       # only when status is ERROR
```

Amplification is printed as an integer **parts per million**, not a decimal, because the summary
block is a stable stdout contract and this repository has no float formatting contract. This is the
per-mille precedent of `docs/specs/r2a-expert-trace.md` section 2.3 at finer resolution, chosen so a
12 ppm padding overhead is representable. `-` is the R0 convention for a value that does not exist.

### 2.4 The alignpack v1 container

#### 2.4.1 Endianness, alignment, and why the manifest is a binary table

**Endianness: little-endian, everywhere, unconditionally.** GGUF is little-endian in every container
R0 and R1 accept; Align ships eighteen `_le` decoders and eighteen `_le` encoders; both current
targets are little-endian. A byte-order flag would be a second code path with no producer. A
big-endian host reading a v1 pack decodes it correctly through the `_le` accessors — the format is
LE, not host-order.

**Alignment: two constants, both in the header.** `block_align = 4096` and `member_align = 64`.

- A **block** starts on a 4096-byte boundary because 4096 is the page size on both targets, and
  because it is the granularity that a later `O_DIRECT` read, an `mmap` of one block, or a GPU
  upload staging buffer will want. A block is the unit R5 fetches; making its start page-aligned
  costs at most 4095 bytes per block and buys the alignment every one of those mechanisms requires.
- A **member** starts on a 64-byte boundary because 64 is the cache line on both targets and the
  natural alignment for a SIMD load of a quantized row. GGUF's own default is 32
  (`src/gguf.align:38`); 64 is a superset, so a member that was 32-aligned in the source stays
  aligned in the pack.
- The **measured cost of both** on the reference model is 57,344 bytes — 12 ppm. This is why the
  looser 4096 was chosen over matching GGUF's 32: the choice is free.
- Both are **header fields, not constants a consumer may assume**. A reader validates that they are
  powers of two within `[1, 65536]` and uses the header's values.

**The manifest is a fixed-width binary table, and a JSON document is emitted beside it, not inside
it.** The alternatives were weighed:

- *JSON text inside the container.* Self-describing to a human with `dd` and `jq`. Rejected: R5's
  loader is Align code whose file surface is `pread` plus the scalar decoders, and requiring it to
  link `core.json` and parse a variable-length text region **before it can find a tensor** inverts
  the dependency this format exists to remove. It also makes every offset in the container depend on
  the rendered length of the text that describes them, so the writer must render the manifest before
  it can compute the payload offset that the manifest must state — a fixpoint, or a two-pass write.
- *Binary table only, no document.* Rejected: every other Track B capability emits a canonical JSON
  document, the smoke asserts on documents, and a format with no textual view is one nobody can
  diff in a pull request.
- **Chosen: a fixed-width binary table as the container's authority, and a separate `R4_ALIGNPACK`
  JSON document as the human and test view.** The two are produced by one pass over one plan, and
  section 3.1 makes their agreement a regression: the smoke re-reads the binary tables with the
  independent Python reader and asserts they describe exactly what the JSON says.

The binary form is what makes the container walkable in bounded work: header at a fixed offset,
tables at header-declared offsets with header-declared fixed record widths, so record `i` is at
`table_offset + i * record_bytes` and no scan is needed to reach it.

**Reserved bytes are zero and are validated as zero.** Every `reserved` field and every deferred
field (`prefetch_group`, `hotness_rank`, `payload_sha256`) must be its stated v1 value; a reader
that finds otherwise fails closed rather than ignoring it. This is what makes section 5.1's later
adoption a version-compatible change instead of a silent reinterpretation.

#### 2.4.2 Header — 128 bytes at offset 0

| Offset | Bytes | Type | Field | v1 value / rule |
| --- | --- | --- | --- | --- |
| 0 | 4 | `u8[4]` | `magic` | `0x41 0x4C 0x47 0x50` — `ALGP` |
| 4 | 4 | `u32` | `format_version` | `1` |
| 8 | 4 | `u32` | `header_bytes` | `128` |
| 12 | 4 | `u32` | `block_align` | `4096`; power of two in `[1, 65536]` |
| 16 | 4 | `u32` | `member_align` | `64`; power of two in `[1, 65536]`, `<= block_align` |
| 20 | 4 | `u32` | `flags` | `0`. Bit 0 = hotness-ordered, bit 1 = prefetch-grouped; both **must be 0** in v1 |
| 24 | 8 | `u64` | `total_bytes` | The pack's exact byte length; must equal `f.len()` |
| 32 | 8 | `u64` | `name_stream_offset` | |
| 40 | 8 | `u64` | `name_stream_bytes` | |
| 48 | 8 | `u64` | `block_table_offset` | |
| 56 | 8 | `u64` | `block_count` | |
| 64 | 8 | `u64` | `member_table_offset` | |
| 72 | 8 | `u64` | `member_count` | |
| 80 | 8 | `u64` | `source_record_offset` | |
| 88 | 8 | `u64` | `payload_offset` | Multiple of `block_align` |
| 96 | 8 | `u64` | `payload_bytes` | `total_bytes - payload_offset` |
| 104 | 4 | `u32` | `block_record_bytes` | `64` |
| 108 | 4 | `u32` | `member_record_bytes` | `96` |
| 112 | 4 | `u32` | `source_record_bytes` | `128` |
| 116 | 4 | `u32` | `document_schema_version` | `1` — the `R4_ALIGNPACK` schema this writer emits |
| 120 | 8 | `u64` | `reserved` | `0` |

`header_bytes`, `block_record_bytes`, `member_record_bytes`, and `source_record_bytes` are present so
that a v2 reader can skip a record it does not understand instead of mis-striding a table. A v1
reader validates them against the v1 constants and refuses anything else.

The region order in the file is header, name stream, block table, member table, source record,
then payload; each region is 8-byte aligned and the payload region begins at the next `block_align`
boundary. A reader validates region **disjointness and containment** (section 2.8 step 15) rather
than assuming the order.

#### 2.4.3 Block table — `block_count` records of 64 bytes

| Offset | Bytes | Type | Field | Rule |
| --- | --- | --- | --- | --- |
| 0 | 4 | `u32` | `kind` | `0` Weight, `1` Attention, `2` Mlp, `3` Expert, `4` Router — the `src/model_ir.align:212` encoding, unchanged |
| 4 | 4 | `i32` | `layer` | `-1` when not per-layer |
| 8 | 4 | `i32` | `expert` | `-1` when not per-expert |
| 12 | 4 | `u32` | `member_count` | `>= 1` |
| 16 | 8 | `u64` | `member_start` | Index into the member table; `member_start + member_count <= member_count(header)` |
| 24 | 8 | `u64` | `pack_offset` | Multiple of `block_align`; `>= payload_offset` |
| 32 | 8 | `u64` | `pack_bytes` | Last member end minus `pack_offset`; includes interior member padding, excludes trailing block padding |
| 40 | 8 | `u64` | `payload_bytes` | Sum of the block's member `nbytes` |
| 48 | 4 | `u32` | `prefetch_group` | **DEFERRED** — `0xFFFFFFFF` in v1, validated |
| 52 | 4 | `u32` | `hotness_rank` | **DEFERRED** — `0xFFFFFFFF` in v1, validated |
| 56 | 8 | `u64` | `reserved` | `0` |

**Block table index `i` is Model IR block index `i`.** The table order is the `R1_MODEL_IR` `blocks`
order, unchanged, and `pack_offset` is strictly increasing across it. R4 chooses no order of its own;
layer-major with layer-local grouping is a property the Model IR already has
(`docs/specs/r1-qwen-model-ir.md` section 2.5.8: index 0 embedding, `1 + 2L` attention, `2 + 2L` mlp,
last output; `docs/specs/r1b-gptoss-moe-ir.md` for the MoE sequence, where a layer's Router block and
its `n_expert` Expert blocks are emitted consecutively within the layer). Making that the pack's
order is the whole of "layer-major + layer-local block grouping", and it means a consumer holding an
`R1_MODEL_IR` document can address the pack without a name lookup.

#### 2.4.4 Member table — `member_count` records of 96 bytes

| Offset | Bytes | Type | Field | Rule |
| --- | --- | --- | --- | --- |
| 0 | 8 | `u64` | `name_start` | Into the name stream |
| 8 | 4 | `u32` | `name_bytes` | `>= 1`, `<= 1024`; `name_start + name_bytes <= name_stream_bytes` |
| 12 | 4 | `u32` | `role_id` | The R1 stable role, as its index in the frozen role list of `docs/specs/r1-qwen-model-ir.md` section 2.5.6; `0xFFFFFFFF` when the frontend supplied none |
| 16 | 8 | `u64` | `source_offset` | `claimed_absolute_offset` in the source GGUF |
| 24 | 8 | `u64` | `nbytes` | `claimed_nbytes`; may be `0` |
| 32 | 8 | `u64` | `pack_offset` | Multiple of `member_align`; inside its block's `[pack_offset, pack_offset + pack_bytes)` |
| 40 | 4 | `u32` | `ggml_type` | The GGML type id, unchanged |
| 44 | 4 | `u32` | `n_dims` | `<= 4` |
| 48 | 8 | `u64` | `dim0` | Declared extent; an undeclared axis holds `1`, the `src/gguf.align` convention |
| 56 | 8 | `u64` | `dim1` | |
| 64 | 8 | `u64` | `dim2` | |
| 72 | 8 | `u64` | `dim3` | |
| 80 | 4 | `i32` | `slice_index` | `-1` for a whole-tensor claim; else the plane index |
| 84 | 4 | `i32` | `slice_count` | `-1` for a whole-tensor claim; else the sliced axis's extent |
| 88 | 8 | `u64` | `reserved` | `0` |

Dimensions and the type id are carried so that R5 can size and interpret a member from the pack
alone. That is the difference between a container and an index: an index that requires the original
file to be present has not moved anything.

#### 2.4.5 Name stream

One concatenated UTF-8 byte stream with no separators, addressed by explicit `[name_start,
name_start + name_bytes)` spans — the `GgufTable` / `BlockPlan` / `TranscriptScan` shape, fourth
instance, chosen for the same reasons: a raw tensor name may contain any byte, and `array<string>`
indexing is Request 22. Names are written in member-table order and are **not** deduplicated: two
members naming the same tensor get two spans, because deduplication would make the stream's layout
depend on a hash and buy nothing at these sizes. Only names that already passed R0's UTF-8 validation
enter the stream, so every recorded boundary is a scalar boundary.

#### 2.4.6 Source-identity record — 128 bytes

| Offset | Bytes | Type | Field |
| --- | --- | --- | --- |
| 0 | 8 | `u64` | `source_file_size` |
| 8 | 8 | `u64` | `source_data_offset` |
| 16 | 8 | `u64` | `source_tensor_count` |
| 24 | 8 | `u64` | `source_metadata_kv_count` |
| 32 | 4 | `u32` | `source_gguf_version` |
| 36 | 4 | `u32` | `source_gguf_alignment` |
| 40 | 8 | `u64` | `header_region_bytes` — equal to `source_data_offset` |
| 48 | 32 | `u8[32]` | `header_region_sha256` |
| 80 | 8 | `u64` | `source_total_tensor_bytes` |
| 88 | 8 | `u64` | `payload_sha256_present` — **DEFERRED**, `0` in v1, validated |
| 96 | 32 | `u8[32]` | `payload_sha256` — **DEFERRED**, all zero in v1, validated |

**The identity is the header/metadata/tensor-table region, not the whole file, and the argument is
cost against benefit against what Align can actually do.**

- *What the region contains.* `[0, data_offset)` is the GGUF magic, version, counts, **every**
  metadata KV pair, and **every** tensor-table entry — each tensor's name, dimensions, type, and
  offset. Two files with identical bytes there and identical `file_size` declare the identical model
  down to the last tensor's placement. On the reference model that is 5,953,536 bytes: 0.13% of the
  file.
- *Cost.* One bounded read of `data_offset` bytes and one `crypto.sha256` call: about 2.6 ms at the
  measured 2.26 GB/s, against roughly 12 s for the copy itself. A whole-file digest would cost about
  2.07 s at that rate — 17% on top of a pack, and again on every verify.
- *Feasibility.* The cost argument is moot: **Align cannot compute a whole-file digest at this pin.**
  `crypto.sha256` is one-shot over one byte view (section 2.1), so a 4.68 GB digest needs a 4.68 GB
  byte view. There is no incremental hash. Section 5.5.1 records this as a request; `payload_sha256`
  and its presence flag are reserved so adopting one is a v1-compatible fill-in.
- *What it does not claim.* It does **not** certify the payload. A file whose header region matches
  and whose tensor bytes were corrupted afterwards passes the identity check and fails
  `--pack-verify`. That is the correct division: identity says *which* model, `--pack-verify` says
  *whether the bytes survived*, and the gate's equality half is the second one.
- *Why the digest is not `hash64`.* `hash64` is present, import-free, and fast, and
  `../align/docs/impl/core-design/hash.md` declines to promise it is stable across builds. A value
  persisted into a container must not change when the compiler is rebuilt.

`--pack-verify` recomputes the region digest from the GGUF it was given and compares; a mismatch is
`R4_SOURCE_IDENTITY` and stops before a single payload byte is compared, because comparing an
unrelated model's bytes would produce a mismatch report that names the wrong cause.

#### 2.4.7 Payload layout

```text
payload_offset = align_up(source_record_offset + 128, block_align)

for each block B in Model IR block order:
    B.pack_offset = align_up(cursor, block_align)
    cursor        = B.pack_offset
    for each member M of B in the block's own member order:
        M.pack_offset = align_up(cursor, member_align)
        cursor        = M.pack_offset + M.nbytes
    B.pack_bytes    = cursor - B.pack_offset
    B.payload_bytes = sum of M.nbytes

total_bytes = cursor          # no trailing padding
```

Three consequences are contract, not incident:

1. **Every block is exactly one contiguous range**, because its members are laid consecutively with
   only interior alignment padding between them. `span == pack_bytes`, and
   `pack_bytes - payload_bytes` is the block's interior padding. This is the property the gate's
   second half measures.
2. **Per-expert claims are contiguous per expert.** An `ExpertBlock` is a block, so its six planes —
   six ranges scattered across six stacked tensors in the source — become one range. R3 and R5 fetch
   one expert with one `pread` of `pack_bytes` at `pack_offset`.
3. **A tensor claimed by two blocks is written twice.** The tied-embedding case
   (`docs/specs/r1-qwen-model-ir.md` section 2.5.6: an absent `output.weight` puts
   `token_embd.weight` in both the embedding and the output block) is the only known instance. The
   pack duplicates the bytes, because a block that is not self-contained is not one read, and it
   records `duplicated_bytes` in both documents so the cost is visible. `payload_bytes` may therefore
   exceed the source's `total_tensor_bytes` by exactly that amount, and section 2.8 step 8 checks
   the relation rather than assuming equality. The reference model has `output.weight` and duplicates
   nothing; the `qwen2-tied` fixture is what exercises it.

**Padding bytes are written explicitly, not left as holes.** A `pwrite` past the current end extends
the file with a zero hole, so skipping the padding would produce a byte-identical but *sparse* file.
It is written because the qualification states a disk-headroom number that must be true, because a
sparse pack and a dense pack of the same model would report different sizes to `du`, and because a
reader validating "padding is zero" should be validating bytes that exist. One `PAD` buffer of
`block_align` zero bytes is built once at start-up with `put_u8(0)`, and each pad is
`f.pwrite(pad.bytes()[0..n], off)`. If sub-slicing a `slice<u8>` argument to `pwrite` does not
compile at this pin, the recorded fallback is a per-pad `mut pad := buffer(0)` filled with `n`
`put_u8(0)` calls — at most 4095 iterations per block, 58 blocks, 237 KiB of appends for the whole
reference model. Which one ships is an implementation detail the smoke's `padding-is-zero` assertion
does not distinguish.

### 2.5 Exchanged documents — `R4_ALIGNPACK` and `R4_ALIGNPACK_VERIFY`, `schema_version: 1`

Both are canonical UTF-8 JSON in declaration order, in the R0/R1/R2A shape: `schema_version`, `kind`,
paths, `status`, `error_code`, `error_detail`, then the payload objects. Both are produced by
`src/alignpack.align` and by nothing else.

**`R4_ALIGNPACK` top level**, in this order: `schema_version` (`1`), `kind`
(`"R4_ALIGNPACK"`), `source_path`, `pack_path`, `status`, `error_code`, `error_detail`, `format`,
`source`, `pack`, `layout`, `sequential_read`, `metrics`, `blocks`.

- `format`: `format_version`, `magic`, `block_align`, `member_align`, `flags`,
  `hotness_ordered` (`false`), `prefetch_grouped` (`false`), `block_record_bytes`,
  `member_record_bytes`, `source_record_bytes`.
- `source`: `file_size`, `data_offset`, `gguf_version`, `alignment`, `tensor_count`,
  `metadata_kv_count`, `total_tensor_bytes`, `arch`, `arch_present`, `header_region_bytes`,
  `header_region_sha256` (lowercase hex).
- `pack`: `total_bytes`, `header_bytes`, `name_stream_offset`, `name_stream_bytes`,
  `block_table_offset`, `block_count`, `member_table_offset`, `member_count`,
  `source_record_offset`, `payload_offset`, `payload_bytes`.
- `layout`: `block_order` (`"model_ir"`), `payload_bytes`, `padding_bytes`, `duplicated_bytes`,
  `max_block_bytes`, `max_member_bytes`.
- `sequential_read`: the section 2.6 aggregates for **both** containers — `source` and `pack`
  objects, each with `range_count`, `span_bytes`, `payload_bytes`, `contiguous_block_count`,
  `amplification_ppm`, plus `by_kind`, an array of one object per `BlockKind` present carrying the
  same five fields. **Provenance differs between the two documents and the field `source_of_pack_stats`
  says which**: in `R4_ALIGNPACK` it is `"plan"` — the packer's own layout, which it realized but did
  not re-read — and in `R4_ALIGNPACK_VERIFY` it is `"pack_tables"`, read back from the written file.
  The authoritative improvement number is the verify document's; a `--pack` document reporting an
  improvement it has not re-read would be a writer certifying itself.
- `metrics`: `bytes_read`, `bytes_written`, `elapsed_ns`, `copy_window_bytes`, `pwrite_count`,
  `pread_count`, `peak_window_bytes`.
- `blocks`: one object per block in table order — `index`, `kind`, `layer`, `expert`, `pack_offset`,
  `pack_bytes`, `payload_bytes`, `padding_bytes`, `source_range_count`, `source_span_bytes`,
  `source_amplification_ppm`, `pack_range_count` (always `1`), `members`. Each member carries `name`,
  `role`, `source_offset`, `nbytes`, `pack_offset`, `ggml_type`, `n_dims`, `dims`, `slice_index`,
  `slice_count`.

**`R4_ALIGNPACK_VERIFY` top level**: `schema_version` (`1`), `kind` (`"R4_ALIGNPACK_VERIFY"`),
`source_path`, `pack_path`, `status`, `error_code`, `error_detail`, `verdict`, `format`, `source`,
`pack`, `identity`, `comparison`, `sequential_read`, `metrics`, `blocks`.

- `verdict`: `"identical"` or `"mismatch"`. It is `null` when `status` is `"error"` for a reason
  that prevented comparison.
- `identity`: `header_region_match` (bool), `file_size_match`, `data_offset_match`,
  `tensor_count_match`, `expected_header_region_sha256`, `observed_header_region_sha256`.
- `comparison`: `members_compared`, `bytes_compared`, `windows_compared`, `first_mismatch` — an
  object or `null` carrying `member_index`, `member_name`, `block_index`, `source_offset`,
  `pack_offset`, `delta` (the byte index within the member), `source_byte`, `pack_byte`.
- `sequential_read` and `blocks` are the same shapes as `R4_ALIGNPACK`'s, recomputed from the pack's
  own tables and the source's own tensor table, so the improvement number in a verify document is
  derived from **two files that both exist**, never from a writer's memory of what it intended.
- `metrics`: `bytes_read`, `elapsed_ns`, `compare_window_bytes`, `fast_path_windows`,
  `byte_scan_windows`.

**`schema_version: 1` is normative.** Any addition, removal, reorder, or type change requires
version 2. The `document_schema_version` field in the container header (section 2.4.2) records which
document schema the writer emitted, so a pack and a document can never disagree about their vintage.
Note that the **container** `format_version` and the **document** `schema_version` are independent:
a v1 container may be described by a v2 document.

### 2.6 The sequential-read metric

This is the definition the gate's second half is measured with. It is stated once, here, and both
documents and the qualification use it unchanged.

For a block `B` whose members claim byte ranges `{(o_i, n_i)}` in some container, with each **claim**
counted once even if two members name the same tensor:

```text
merged(B)              = the maximal contiguous ranges obtained by sorting {[o_i, o_i + n_i)}
                         by o_i and merging any two that touch or overlap
range_count(B)         = |merged(B)|
payload_bytes(B)       = sum of n_i
span_bytes(B)          = max(o_i + n_i) - min(o_i)
amplification_ppm(B)   = round(1000000 * span_bytes(B) / payload_bytes(B))
```

`span_bytes(B)` is the **sequential read bytes per block fetch**: the bytes a consumer must transfer
if it fetches the whole block with **one** sequential read, which is what
`docs/specs/align-llm.md` section 6 says NVMe should be used for. `range_count(B)` is what it costs
instead if the consumer refuses to over-read: that many separate reads, that many seeks.
`amplification_ppm(B)` is their ratio in integer parts per million, so `1_000_000` means "the span is
exactly the payload" and nothing is wasted. Per-million rather than per-mille because the pack's own
padding overhead is 12 ppm and must be representable; integer rather than float because there is no
float formatting contract in this repository.

Model-level aggregates sum over blocks, with each block independent:

```text
range_count_total       = sum over B of range_count(B)
span_bytes_total        = sum over B of span_bytes(B)
payload_bytes_total     = sum over B of payload_bytes(B)
contiguous_block_count  = |{B : range_count(B) == 1}|
amplification_ppm_total = round(1000000 * span_bytes_total / payload_bytes_total)
```

`span_bytes_total` may exceed the container's size, because two blocks' spans may overlap; on the
reference model it is 11,130,544,128 against a 4,683,073,536-byte file. That is not an error, it is
the point: it is the number of bytes that would move if each block were fetched independently in one
read, which is exactly the access pattern a layer-at-a-time runtime has.

The aggregates are also reported `by_kind`, because the reference model's improvement is
concentrated: `AttentionBlock` goes from 10,922,100 ppm to 1,000,000 while `MlpBlock` goes from
1,291,478, and a single total would hide that one kind was ten times worse than the other.

**The gate's second half is discharged when, over the same block set and the same model:**

1. every block of the pack has `range_count == 1` and `span_bytes == pack_bytes`, so
   `amplification_ppm == 1_000_000` exactly and `contiguous_block_count == block_count`;
2. `range_count_total` and `span_bytes_total` are both strictly lower for the pack than for the
   source; and
3. both sides are computed by `--pack-verify` from the two files as they exist on disk, and
   independently recomputed by `scripts/alignpack_reader.py` from the pack's binary tables.

On the reference model those are 58 vs 89 ranges, 4,677,120,000 vs 11,130,544,128 span bytes, 58 vs
27 contiguous blocks, and 1,000,000 vs 2,379,786 ppm.

**Three honest limits on the claim.** First, it is a claim about **layout**, not about achieved
throughput: no timing is asserted and none is a gate (section 4.6). Second, it is measured on one
model on one host, and the reference file was already 25/28 layer-contiguous, so the improvement
comes from intra-layer block grouping, three misordered layers, and the output block — not from a
wholesale reordering of a badly ordered file. Third, the format *guarantees* the property, while the
source file merely *happened* to have most of it; a guarantee is the thing R5 can build on.

### 2.7 The streaming copy and the streaming compare

**Constants**, each a named constant in `src/alignpack.align`, checked before the work it protects,
in non-wrapping form:

| Constant | Value | Why |
| --- | --- | --- |
| `COPY_WINDOW_BYTES` | `4194304` (4 MiB) | 1,116 window pairs for the reference model against 4,462 at 1 MiB. Section 2.2 measured no reliable throughput difference above 4 MiB — run-to-run variance exceeded it — so this is chosen on syscall count and resident bytes, and **no speed claim is attached to it** |
| `TABLE_CHUNK_BYTES` | `65536` | The table writer's chunk. 682 member records per chunk; one chunk for the reference model's whole member table |
| `MAX_PACK_BYTES` | `1099511627776` (1 TiB) | Larger than any quantized open-weight model; leaves `i64` eight decimal orders from wrapping |
| `MAX_BLOCKS` | `1048576` | Matches `src/gguf.align`'s `MAX_TENSORS`; bounds the block table at 64 MiB |
| `MAX_MEMBERS` | `1048576` | Same bound; bounds the member table at 96 MiB. A gpt-oss-120b container needs 27,648 |
| `MAX_TABLE_BYTES` | `134217728` (128 MiB) | Checked before either table is planned, so an implausible container never reserves table space |
| `MAX_NAME_STREAM_BYTES` | `16777216` | `src/gguf.align`'s `MAX_STRING_BYTES` |
| `MAX_NAME_BYTES` | `1024` | One tensor name |
| `MAX_PATH_BYTES` | `4096` | `src/main.align:622`, unchanged |
| `MAX_DETAIL_BYTES` | `256` | `src/model_ir.align:26`, unchanged |
| `BLOCK_ALIGN` | `4096` | Section 2.4.1 |
| `MEMBER_ALIGN` | `64` | Section 2.4.1 |

**The copy.** One source handle, one destination handle, one window, both handles bare locals:

```text
copy_member(borrow src: file, borrow dst: file, borrow mut w: buffer,
            borrow mut c: Counters, from: i64, to: i64, n: i64) -> Result<(), Fault>

  remaining := n
  s := from
  d := to
  loop {
    if remaining == 0 { break }
    want  := min(remaining, COPY_WINDOW_BYTES)
    count := src.pread(w, s)?                 # w's length becomes exactly count
    if count == 0 { fail R4_WINDOW_UNAVAILABLE at s }
    if count > want { fail R4_SHORT_READ at s }   # cannot happen; a fail-closed guard
    dst.pwrite(w.bytes(), d)?                 # writes all `count` bytes or errors
    s = s + count; d = d + count; remaining = remaining - count
    c.bytes_read += count; c.bytes_written += count; c.pread_count += 1; c.pwrite_count += 1
  }
```

Four properties follow from section 2.1's verified surface and are why this shape is chosen:

- The window is **reused without a reset**, because `pread` overwrites the buffer's length. This is
  the one path where the absent `buffer.clear` would have bitten, and it does not.
- `want` is honored by allocating the window at `COPY_WINDOW_BYTES` and, for a final partial window,
  rebinding `w = buffer(want)` — the `src/gguf.align:351` idiom. `pread` fills up to capacity, so a
  window larger than the remainder would read past the member.
- A **short read is completed by the loop**, not mistaken for EOF: the loop re-reads at the advanced
  offset until `remaining` is zero. A zero-length read at an offset already proved inside the file is
  `R4_WINDOW_UNAVAILABLE` — an allocation failure or a file that shrank underneath — not
  a truncation of the container, following `src/gguf.align:321-327` exactly. There is deliberately no
  `R4_SOURCE_TRUNCATED` code: step 8 already proved every claim lies inside the file, so a read that
  comes up empty afterwards means the environment changed, not that the container was malformed, and
  a code naming the container would name the wrong subject.
- A **short write is impossible** (section 2.1), so there is no partial-write branch to get wrong.

Members are copied in **pack order**, so the destination is written strictly forward and every
`pwrite` extends the file by at most one window. The source is read in whatever order the plan
implies, which for a layer-major source is also close to forward.

**The compare.** Two source-shaped handles, two windows, and a two-tier comparison:

```text
compare_member(borrow src: file, borrow pak: file,
               borrow mut a: buffer, borrow mut b: buffer, ...) -> Result<(), Fault>

  per window:
    ca := src.pread(a, s)  ;  cb := pak.pread(b, p)
    if ca != cb or ca == 0 { fail as above }
    if crypto.constant_time_equal(a.bytes(), b.bytes()) { advance; continue }
    # only a mismatching window is scanned byte-wise, and only once
    i := first index where a.bytes().u8(i) != b.bytes().u8(i)
    fail R4_CONTENT_MISMATCH, detail "<name>@<source_offset>+<delta>"
```

`crypto.constant_time_equal` is a C-engine call over two byte views, so the common case is one call
per 4 MiB rather than 4,194,304 `u8()` calls; the byte scan is bounded by one window and happens at
most once per run. Its constant-time property is irrelevant here and its length behavior is not
relied upon: the lengths are compared explicitly first.

**Peak resident bytes** are `COPY_WINDOW_BYTES` for `--pack` and `2 * COPY_WINDOW_BYTES` for
`--pack-verify`, plus the plan (five `array<i64>` columns per member and six per block: 96 bytes per
member, 48 per block — 34 KiB for the reference model) and the name stream. Section 4.6 measures it.

### 2.8 Validation order and error codes

The first applicable row wins; **no document, no stdout, and no destination file exists before the
step that creates it**. Steps 1 and 2 return `Err` with no output at all. Steps 3 onward produce a
`status: "error"` document and then map to `Err(Error.Invalid)`.

Order for `--pack`:

1. CLI selector and exact arity. *(`src/main.align`)*
2. Lexical path validation of **every** operand — non-empty, `<= MAX_PATH_BYTES`, no NUL.
   *(`src/main.align`; `alignpack.build_pack` re-checks as its own fail-closed contract)*
3. Source container read: `gguf.read_table`. Every `R0_*` code is surfaced **verbatim**, not
   re-mapped, because R0 owns container defects.
4. Model IR derivation: architecture dispatch, then the frontend. Every `R1_*` code is surfaced
   verbatim.
5. **Destination pre-existence**: `fs.exists(pack_path)` is true → `R4_DEST_EXISTS`. This precedes
   every plan computation so an occupied destination costs nothing, and it precedes `fs.create_rw`,
   which would truncate.
6. Plan bounds: `block_count <= MAX_BLOCKS`, `member_count <= MAX_MEMBERS`, table bytes
   `<= MAX_TABLE_BYTES`, name stream `<= MAX_NAME_STREAM_BYTES`, each name `<= MAX_NAME_BYTES`.
7. Layout arithmetic: every `align_up` and every offset sum proved representable **before** it is
   formed, in `src/model_ir.align` rule 2's non-wrapping style; `total_bytes <= MAX_PACK_BYTES`.
8. Source range validation: every claim satisfies `data_offset <= source_offset` and
   `source_offset + nbytes <= file_size`, written non-wrapping; and
   `payload_bytes == total_tensor_bytes + duplicated_bytes`.
9. Header-region read and digest: one bounded read of `data_offset` bytes, one `crypto.sha256`.
10. Destination creation: `fs.create_rw`. **From here a file exists**, and every later failure runs
    step 12.
11. Write header, name stream, block table, member table, source record, then the payload in block
    order with explicit padding; then `f.len()` must equal `total_bytes`.
12. Cleanup on any failure after step 10: `fs.remove(pack_path)`, and the document records
    `destination: "REMOVED"` or, if the removal itself failed, `"WRITTEN"` with
    `R4_CLEANUP_FAILED` in `error_detail` — the partial artifact is named, never silently left
    unmentioned.

Order for `--pack-verify`: steps 1–4 unchanged, then:

13. Pack open and header read: magic, `format_version`, `header_bytes`, record widths, alignments,
    flags, reserved.
14. `f.len()` of the pack must equal `total_bytes`.
15. Region validation: every region is inside `[0, total_bytes)`, regions are pairwise disjoint,
    each table's `count * record_bytes` fits its region, `payload_offset` is `block_align`-aligned.
16. Source identity: `header_region_bytes`, `source_file_size`, `source_data_offset`,
    `source_tensor_count`, then the recomputed region digest.
17. Cross-check against the freshly derived Model IR. **The header's region geometry first** —
    `total_bytes`, `name_stream_offset`, `name_stream_bytes`, `block_table_offset`,
    `member_table_offset`, `source_record_offset`, `payload_offset` — each against the value the
    planner derives, because every one of them is about to be used to address a record and because
    `total_bytes` is otherwise unconstrained by anything but its own file (section 6.8). Then table
    validation: counts, then per block kind/layer/expert/member span, then per member
    name/role/type/dims/slice/`source_offset`/`nbytes`, then `pack_offset` alignment, containment,
    monotonicity, and the deferred fields' v1 values.
18. Streaming byte comparison, member by member in pack order.
19. Padding verification: every interior padding run is read and asserted zero.
20. Statistics for both containers.

| Code | Condition | Step | `error_detail` |
| --- | --- | --- | --- |
| `R4_DEST_EXISTS` | `fs.exists(pack_path)` | 5 | the sanitized destination path |
| `R4_DEST_UNWRITABLE` | `fs.create_rw` failed | 10 | the Align `Error` variant name |
| `R4_BLOCK_LIMIT` | `block_count > MAX_BLOCKS` | 6 | the count |
| `R4_MEMBER_LIMIT` | `member_count > MAX_MEMBERS` | 6 | the count |
| `R4_TABLE_TOO_LARGE` | table or name-stream bound exceeded | 6 | the byte count |
| `R4_NAME_TOO_LONG` | a member name exceeds `MAX_NAME_BYTES` | 6 | the escaped prefix |
| `R4_LAYOUT_OVERFLOW` | an offset sum or `align_up` would not be representable | 7 | the block index |
| `R4_PACK_TOO_LARGE` | `total_bytes > MAX_PACK_BYTES` | 7 | `total_bytes` |
| `R4_SOURCE_RANGE` | a claim leaves `[data_offset, file_size)` | 8 | the member name |
| `R4_DUPLICATION_MISMATCH` | `payload_bytes != total_tensor_bytes + duplicated_bytes` | 8 | the two decimal sums separated by `!=` |
| `R4_SOURCE_UNREADABLE` | open, `len`, or `pread` failed at the OS level on the source | 3, 9, 11 | the Align `Error` variant name |
| `R4_WINDOW_UNAVAILABLE` | a zero-length read at an offset already proved in range | 9, 11, 18 | the offset |
| `R4_SHORT_READ` | `pread` returned more than requested | 11, 18 | the offset. A retained fail-closed guard |
| `R4_WRITE_FAILED` | `pwrite` returned an error, including `ENOSPC` | 11 | the Align `Error` variant name and the offset |
| `R4_SIZE_MISMATCH` | `f.len()` after writing differs from `total_bytes` | 11 | the two decimal sizes separated by `!=` |
| `R4_CLEANUP_FAILED` | the partial destination could not be removed | 12 | the sanitized path |
| `R4_PACK_UNREADABLE` | open, `len`, or `pread` failed on the pack | 13 | the Align `Error` variant name |
| `R4_PACK_MAGIC` | the first four bytes are not `ALGP` | 13 | the four bytes, hex-escaped |
| `R4_PACK_VERSION` | `format_version != 1` | 13 | the version |
| `R4_PACK_HEADER` | a header constant, alignment, flag, or reserved field is not its v1 value, or a header region field disagrees with the derived layout | 13, 17 | the field name |
| `R4_PACK_TRUNCATED` | `f.len() != total_bytes`, or a region leaves the file | 14, 15 | the two decimal sizes, or the region name |
| `R4_PACK_REGION` | regions overlap, or a table does not fit its region | 15 | the region name |
| `R4_SOURCE_IDENTITY` | the header-region digest, `file_size`, `data_offset`, or `tensor_count` disagrees | 16 | the field name |
| `R4_PACK_BLOCK_MISMATCH` | a block record disagrees with the derived Model IR | 17 | `block[<index>].<field>` |
| `R4_PACK_MEMBER_MISMATCH` | a member record disagrees | 17 | `member[<index>].<field>` |
| `R4_PACK_NAME_MISMATCH` | a name span disagrees, or is not valid UTF-8 | 17 | the member index |
| `R4_PACK_OFFSET` | a `pack_offset` is misaligned, outside its block, or not monotonic | 17 | `member[<index>]` |
| `R4_PACK_RESERVED` | a deferred field is not its v1 value | 13, 17 | the field name |
| `R4_CONTENT_MISMATCH` | a compared byte differs | 18 | `<name>@<source_offset>+<delta>` |
| `R4_PADDING_NONZERO` | an interior padding byte is not zero | 19 | the absolute pack offset |

**`R4_DEST_EXISTS` is a check-then-create race and the design says so.** `fs.create_rw` truncates
and `fs.create_exclusive` returns a sequential `writer` with no `pwrite` (section 2.1), so a
positional writer cannot be created exclusively at this pin. Between step 5 and step 10 another
process could create the path, and this arm would then truncate it. The exposure is one process on
one developer host writing to a caller-named path, and section 5.5.2 records the request that would
close it. Hiding the race behind a silent overwrite would be worse than naming it.

**`R4_WRITE_FAILED` is where a full disk arrives.** `ENOSPC` reaches Align as an `Error` variant from
`pwrite`; the arm records it, removes the partial pack (step 12), and exits nonzero. It is
deliberately not a distinct code: the packer cannot distinguish "the disk is full" from "the quota
is exhausted" through the mapped error, and inventing a code that claims the difference would be a
guess. The qualification checks headroom **before** it starts (section 4.4) rather than relying on
the failure path to be pleasant.

**Padding is verified, not assumed.** Step 19 is what makes `R4_PADDING_NONZERO` reachable and is
the reason the padding is written rather than left as a hole: a hole reads as zero and would make
the assertion vacuous on a filesystem that supports holes and non-vacuous on one that does not.

**A pack that was written survives a failure to write its document.** Step 12's cleanup governs the
destination pack and nothing else. In the four-operand form of `--pack` the document is written
after the pack is complete and its size asserted, so a `write_file` failure on the caller's document
path — an unwritable directory, a full filesystem, a path that became a directory — leaves the pack
**in place** and returns `Err` with no document, no summary block, and a nonzero exit. That is the
deliberate answer: the pack may be gigabytes, it is known good because step 11 asserted its size,
and `--pack-verify` recovers everything the lost document would have said. Removing a verified
artifact because a caller named an unwritable document path would be the worse outcome, and leaving
it unstated would be worse still.

### 2.9 Ownership, allocation, and owner modules

| Module | Owns | Imports |
| --- | --- | --- |
| `src/alignpack.align` | the v1 container codec (encode and decode), the layout planner, the streaming copy, the streaming verifier, the padding writer, the sequential-read statistics, both document renderers, every `R4_*` code | `core.json`, `std.crypto`, `std.encoding`, `std.fs`, `std.time`, `gguf`, `model_ir` |
| `src/model_ir.align` | **unchanged responsibilities**, plus one new `pub fn resolve_claims(borrow t, borrow g, borrow plan) -> ClaimTable` extracted from the existing per-member claim pass, which `build` now calls, and `pub fn derive_status(...) -> Derivation`, the status-only ordered derivation the packing arms run (section 6.8) | unchanged |
| `src/main.align` | `--pack` and `--pack-verify` arity, path guards, summary blocks, exit mapping | `alignpack` |

**`src/alignpack.align` imports the frontends indirectly, never directly.** The architecture
dispatch lives in `src/main.align`, exactly as `--model-ir` does (`src/main.align:537`), and the
packer receives a `BlockPlan`. A packer that knew about qwen2 would be a second place to teach every
new architecture.

**The `model_ir` extraction is the design's one refactor and it exists to prevent a second truth.**
`claimed_absolute_offset` and `claimed_nbytes` are computed today inside `model_ir`'s rendering pass
(`src/model_ir.align:510`, `member_claim`). The packer needs the same numbers as **data**, and
recomputing them would create two producers of the one arithmetic `docs/specs/r1b-gptoss-moe-ir.md`
section 2.5.3 spent a section proving correct. `resolve_claims` returns the claim columns; `build`
consumes it and renders; the packer consumes it and lays out. `model-ir-smoke` re-runs unchanged and
is the regression that the extraction changed no behavior; the `R1_MODEL_IR` documents must be
byte-identical before and after.

| Value | Owner | Allocation | Release |
| --- | --- | --- | --- |
| source `file`, destination `file` | bare locals in `alignpack.write_pack` / `verify_pack`, as `src/gguf.align:74-77` requires | two fds | scope `Drop` closes both |
| copy window(s) | bare `mut` locals | one `buffer(COPY_WINDOW_BYTES)` for `--pack`, two for `--pack-verify`; rebound to `buffer(want)` for a final partial window | scope `Drop` |
| `PAD` buffer | one bare `mut` local | `buffer(BLOCK_ALIGN)`, filled once | scope `Drop` |
| `ClaimTable` | one local in the arm, **moved** into the planner as a `borrow` argument's owner local | parallel `array<i64>` columns frozen once from `array_builder<i64>` | scope `Drop` |
| `PackPlan` | one local | one owned `string` name stream, eleven `array<i64>` columns each frozen once, and the scalars | scope `Drop` |
| table chunk | one `mut` local per chunk inside the table writer | `buffer(0)` grown by `put_*`, rebound per chunk | rebinding drops the previous |
| header-region buffer | one `mut` local, scoped to step 9 | `buffer(data_offset)`, bounded by `MAX_TABLE_BYTES`'s sibling check on `data_offset` | dropped before the payload loop begins |
| digest | one local `array<u8>` of 32 | owned by `crypto.sha256` | scope `Drop` |
| document | one `builder` in each renderer | accumulated once, in declaration order | moved out by `to_string()` |
| final document | moved into `AlignPack.document` / `AlignPackVerify.document`, then to the caller | one owned `string` | move, never clone |

**The table above was incomplete about peak, and this paragraph replaces its claim.** Three
allocations are proportional to the model rather than constant, and the third dominates:

1. the header-region buffer, `data_offset` bytes — 5,953,536 for the reference model — already
   bounded by R0's own walk, and scoped so it is released before the payload copy starts, so it
   never coexists with the copy window;
2. the `ClaimTable` and the `PackPlan` — six and twenty-two `array<i64>` columns over the member
   and block counts plus one owned name stream, about 17 MB for a container with 16,514 blocks and
   99,139 members, and twice the `PackPlan` for `--pack-verify`, which holds the expected layout and
   the observed one at once;
3. **the rendered `R4_ALIGNPACK` / `R4_ALIGNPACK_VERIFY` document**, one `builder` plus one owned
   `string` per block and per member, which is `O(blocks + members)` and is the largest thing either
   arm holds.

`metrics.peak_window_bytes` measures **only** the I/O windows, and a reader must not take it for the
arm's resident set. On the 16,514-block synthetic mixture-of-experts container of section 6.8 the
document is 26,817,769 bytes and the arm's peak resident set is 419 MB for `--pack` and 802 MB for
`--pack-verify`, against a `peak_window_bytes` of 262,144. That ratio is a property of building a
document proportional to the model, not of the copy; R5's loader consumes the container, not the
document, and section 5's deferred surfaces are where a streaming document renderer would belong if
a consumer ever needs one.

Section 6.8 records the one repair made here: the packing arms no longer render an `R1_MODEL_IR`
document they discard, which removed 37 MB from each arm's peak on that container.

**Work stays bounded.** Planning is `O(members)`. The copy is one pass over `payload_bytes` in both
directions. The compare is one pass over `payload_bytes` in each container. The statistics sort one
packed `array<i64>` per block, `O(m log m)` in that block's member count, and every block's member
count is bounded by the frontend. Nothing is quadratic and nothing rescans.

### 2.10 Ledger dimensions

| Dimension | Contract | Owner | Acceptance |
| --- | --- | --- | --- |
| Exact command/API | Section 2.3 (`--pack`, `--pack-verify`, two forms each, no flags); `pub fn build_pack(source: str, destination: str) -> alignpack.AlignPack`, `pub fn verify_pack(source: str, pack: str) -> alignpack.AlignPackVerify`; `alignpack.PackPlan`, `alignpack.AlignPack`, `alignpack.AlignPackVerify`; `model_ir.resolve_claims`, `model_ir.ClaimTable`, `model_ir.derive_status`, `model_ir.Derivation`. No aliases | `src/main.align`, `src/alignpack.align`, `src/model_ir.align` | `alignpack-smoke` CLI cases |
| Inputs and defaults | One source path, one pack path, one optional document path. No environment input, no ambient options, no default destination | `src/main.align` | `env-perturbation`, `cli-arity` |
| Results and errors | `Ok` + `status: "ok"`; `Ok` + `status: "error"` for every container, model, layout, or comparison defect; `Err` only for argument or OS failure. Section 2.8's table is complete and ordered; `R0_*` and `R1_*` codes pass through verbatim | `src/alignpack.align` | one fixture per row |
| Multi-invalid precedence | Section 2.8 is strictly ordered; the first applicable row wins | ordered guards | `precedence-*` cases |
| Ownership and lifetime | Section 2.9. Handles and windows are bare locals; `ClaimTable`, `PackPlan`, and both documents are moved into their sole owners; no accessor returns a view derived from a `borrow` parameter | `src/alignpack.align` | `document-move`, ownership review |
| Allocation | Section 2.9's table **and the paragraph that follows it**, which corrects this row: the windows are one (pack) or two (verify) `COPY_WINDOW_BYTES` buffers and the header-region buffer never coexists with them, but peak is dominated by the rendered document and, behind it, the `ClaimTable` and `PackPlan` columns — all three proportional to block and member count. `metrics.peak_window_bytes` measures the windows only and is not the resident set | `src/alignpack.align` | `peak-allocation` (`peak_window_bytes <= max(data_offset, COPY_WINDOW_BYTES)` per fixture; measured resident set on the section 6.8 synthetic), `descriptor-budget` |
| Bounded work | One forward pass per container; `O(m log m)` per block for the statistics; every `MAX_*` checked before the work it protects, non-wrapping | `src/alignpack.align` | `bounded-work` over the oversize fixtures |
| Owner module | Section 2.9's table. One producer of the container format; one producer of claim arithmetic | this document | `make check` (`check-per-unit`), import-graph review |
| **Persisted identity** | **The alignpack v1 container is a persisted format.** Its identity is `magic` + `format_version`; its source binding is the section 2.4.6 record (`file_size`, `data_offset`, `tensor_count`, `metadata_kv_count`, `gguf_version`, `alignment`, and the `crypto.sha256` of `[0, data_offset)`). It is **not** content-addressed, **not** a cache, and has **no** garbage-collection or reuse policy: a pack is a caller-named artifact at a caller-named path. The whole-payload digest is reserved and zero | `src/alignpack.align` | `identity-mismatch`, `alignpack_reader.py` |
| Schema version | **Container `format_version: 1`** and **document `schema_version: 1`**, independently versioned, with `document_schema_version` in the header binding a pack to the document vintage that described it. Any change to a record layout, a field, an alignment rule, or a reserved value requires `format_version: 2` | `src/alignpack.align` | golden container bytes; golden document bytes; field-order assertions |
| Validation order | Section 2.8, deterministic. No destination file before step 10; no document before the derivation completes; a partial destination is removed and reported | `src/alignpack.align` | ordered malformed corpus, `untouched-destination`, `partial-pack-removed` |
| Prerequisites | The pinned toolchain at `4b515f8d`; every consumed surface verified present (section 2.1). Requests 21–28 remain `PROPOSED`, non-blocking, unconsumed. **Two capability prerequisites**: `model_ir.resolve_claims` and `model_ir.derive_status`, in the same commit. **One environmental prerequisite**: free space greater than the pack for the qualification only (section 4.4) | `src/alignpack.align` | `make check`, `make build` |
| Acceptance evidence | `alignpack-smoke` for the format, the error corpus, byte identity, and the layout invariants; `scripts/alignpack_reader.py` as the independent reader; `alignpack-qualification` for the real-model gate | section 4 | sections 4.2, 4.3, 4.4 |
| Metrics | Primary: byte identity and `range_count == 1` for every pack block. Secondary: `bytes_written`, `elapsed_ns`, verify `elapsed_ns`, range counts and spans before and after, padding and duplicated bytes, peak resident bytes. **No throughput claim**; section 4.6 | section 4.6 | oracle assertions |
| Text/wire boundary | The container is LE binary with fixed-width records and an explicit-span name stream; only names that passed R0's UTF-8 validation enter the stream, and `--pack-verify` re-validates them. Documents are canonical UTF-8 JSON in declaration order; `error_detail` and every path in a summary block are escaped and bounded | `src/alignpack.align` | `wire-escapes`, `invalid-utf8-name`, golden container bytes |
| CLI/build/environment inputs | Explicit: `argv` only. No environment variable is read by either arm. The qualification's `ALIGN_LLM_GGUF_MODEL` and `ALIGN_LLM_ALIGNPACK_TMPDIR` are read by the **runner**, never by `main` | `src/main.align` | `env-perturbation` in both directions |
| Runtime-inspection fields | Every document field is decoded from one of the two containers or derived by a stated formula from decoded values, except `format.magic` and the `*_version` constants, which name what this writer produced. No reflection, no environment read | `src/alignpack.align` | producer-provenance review |
| Platform scope | Byte-exact LE binary I/O over POSIX `pread`/`pwrite`; no target-local boundary changes, so this capability's own content selects no platform profile. **The `Makefile` change does select the fresh-image installed profile** — section 3.7 | `src/alignpack.align` | `python3 scripts/pre-pr --plan` |
| Milestone ordering | R4 consumes no R3 or R5 decision: no cache policy, no residency tier, no hotness rank, no prefetch group. It emits a layout and its measurement | this document | section 5 |
| Normative examples | The tables of section 2.4 are the format declaration. The measurements in section 2.2 come from the real model on this host; the golden container bytes of section 4.3 are the only byte-exact assertion | this document | section 4.3 |

## 3. Closure matrix

Every applicable cell names its implementation owner and the exact regression that closes it. `N/A`
carries a concrete reason; `DEFERRED` is an intentional decision recorded in section 5. Regression
names are cases inside `scripts/run-alignpack-smoke` unless another runner is named. **MOE-PREREQ**
marks a cell whose real-weight evidence does not exist on this host (section 1.4 item 3); each is
closed synthetically and relisted in section 4.5.

### 3.1 `src/alignpack.align` — the container codec

| Case | Contract to close | Implementation | Exact regression |
| --- | --- | --- | --- |
| Construction | The header, both tables, and the source record are encoded with the native `put_*` encoders into a chunked buffer | `encode_header`, `write_tables` | `golden-container-bytes` |
| Success — round trip | Every field written by the encoder is recovered identically by the decoder | `encode_*` / `decode_*` | `header-round-trip`, `record-round-trip` over generated field values including `0`, `1`, and the widest representable |
| Success — independent reader | The container as written matches an implementation that never saw `src/` | — | `scripts/alignpack_reader.py` over every fixture (section 4.3) |
| Success — fixed strides | Record `i` is at `table_offset + i * record_bytes` for every `i` | `decode_block`, `decode_member` | `stride-addressing`: the reader seeks to a random record and compares against a full scan |
| Failure — magic | Not `ALGP` is `R4_PACK_MAGIC` with the four bytes hex-escaped | `decode_header` | `bad-magic` |
| Failure — version | `format_version != 1` is `R4_PACK_VERSION` | `decode_header` | `bad-version` (values `0`, `2`, `4294967295`) |
| Failure — header constants | A wrong `header_bytes`, record width, non-power-of-two alignment, `member_align > block_align`, or nonzero `flags` is `R4_PACK_HEADER` naming the field | `decode_header` | `header-field-corpus`, one case per field |
| Failure — reserved | Any reserved or deferred field not at its v1 value is `R4_PACK_RESERVED` | `decode_header`, `decode_block` | `reserved-nonzero`, `prefetch-group-set`, `hotness-rank-set` |
| Failure — regions | Overlapping, out-of-file, or undersized regions are `R4_PACK_REGION` / `R4_PACK_TRUNCATED` | region validator | `region-overlap`, `region-past-eof`, `table-does-not-fit` |
| Failure — truncation | A pack shorter than `total_bytes` is `R4_PACK_TRUNCATED` with both sizes | step 14 | `pack-truncated` at 1 byte, at the header boundary, and mid-payload |
| Malformed — non-UTF-8 name | A name span that is not valid UTF-8 is `R4_PACK_NAME_MISMATCH` | name validator | `pack-name-invalid-utf8` |
| Malformed — name span | A span leaving the name stream is `R4_PACK_NAME_MISMATCH` | name validator | `name-span-past-end` |
| Bounded work | Decoding validates counts against `MAX_BLOCKS` / `MAX_MEMBERS` before addressing any record | header validator | `pack-block-count-implausible` |
| Cleanup | The pack handle closes on `Drop`; the source handle is unaffected by a pack failure | scope | `descriptor-budget` |
| Endianness | A big-endian-encoded header is rejected by `R4_PACK_MAGIC` or `R4_PACK_VERSION`, never silently read | `decode_header` | `be-header` |
| Generic monomorphization | `N/A`: no generic type or function is declared | `N/A` with this reason | — |

### 3.2 `src/alignpack.align` — the layout planner and statistics

| Case | Contract to close | Implementation | Exact regression |
| --- | --- | --- | --- |
| Success — layer-major order | Block table order equals Model IR block order; `pack_offset` is strictly increasing | `plan_layout` | `block-order-matches-ir`: the smoke diffs the pack's block sequence against the `R1_MODEL_IR` document's |
| Success — alignment | Every `pack_offset` of a block is `block_align`-aligned and of a member `member_align`-aligned | `plan_layout` | `alignment-invariant` in `alignpack_reader.py` |
| Success — contiguity | Every block satisfies `range_count == 1` and `span == pack_bytes` | `plan_layout` | `pack-contiguity`: asserted for every block of every fixture |
| Success — per-expert contiguity | Every `ExpertBlock`'s six claims are one range | `plan_layout` | `expert-block-contiguous` over the gpt-oss corpus. **MOE-PREREQ** for real weights |
| Success — padding accounting | `padding_bytes == sum(pack_bytes) - sum(payload_bytes) + inter-block padding`, and `total_bytes` equals the plan's cursor | `plan_layout` | `padding-accounting`, cross-checked by the Python reader |
| Success — duplication | A tied `token_embd.weight` appears in two blocks, is written twice, and `duplicated_bytes` equals its size | `plan_layout` | `tied-embedding-duplicated` over `qwen2-tied.gguf` |
| Success — zero-byte member | A member with `nbytes == 0` occupies no payload and still gets a valid aligned `pack_offset` | `plan_layout` | `zero-byte-member` |
| Success — statistics, source side | `range_count`, `span_bytes`, `payload_bytes`, and `amplification_ppm` match an independent Python computation over the same tensor table | `stats_for` | `stats-oracle` (section 4.3), naive nested-loop reference |
| Success — statistics, pack side | The same, computed from the pack's own tables | `stats_for` | `stats-oracle` |
| Success — `by_kind` | One entry per `BlockKind` present, in kind order, with the aggregate identities holding | `stats_for` | `stats-by-kind` |
| Success — overlapping spans | `span_bytes_total` may exceed the container size and is not clamped | `stats_for` | `stats-overlap`: a fixture whose two blocks' spans overlap by construction |
| Failure — planner bounds | Each of `R4_BLOCK_LIMIT`, `R4_MEMBER_LIMIT`, `R4_TABLE_TOO_LARGE`, `R4_NAME_TOO_LONG`, `R4_PACK_TOO_LARGE` fires on its own fixture | ordered guards | `planner-limit-corpus`, the three expensive ones against lowered debug constants |
| Failure — layout overflow | An offset sum that would wrap is `R4_LAYOUT_OVERFLOW` before it is formed | non-wrapping guards | `layout-overflow`: a fixture whose declared sizes sum past the bound |
| Failure — source range | A claim outside `[data_offset, file_size)` is `R4_SOURCE_RANGE` naming the member | step 8 | `claim-past-eof`, `claim-before-data` |
| Failure — duplication accounting | A plan whose sums disagree is `R4_DUPLICATION_MISMATCH` | step 8 | `duplication-mismatch` against an injected plan |
| Loop joins | The block loop, the member loop, and the statistics sweep each terminate on count, on failure, and on a zero count | loop guards | `zero-member-block` (rejected by the frontend, asserted), `single-block-model` |

### 3.3 `src/alignpack.align` — the streaming copy and compare

| Case | Contract to close | Implementation | Exact regression |
| --- | --- | --- | --- |
| Construction | Both handles and every window are bare locals; one window for `--pack`, two for `--pack-verify` | `write_pack`, `verify_pack` prologues | `descriptor-budget`, `peak-allocation` |
| Success — exact copy | Every member's bytes are identical in both containers | `copy_member` | `byte-identity` over every fixture, asserted by `--pack-verify` **and** independently by the Python reader |
| Success — window boundary | A member whose size straddles `COPY_WINDOW_BYTES` copies exactly once with no gap or overlap | `copy_member` | `copy-window-boundary`: member sizes at `W-1`, `W`, `W+1`, `2W`, `2W+1` against a lowered debug `W` |
| Success — final partial window | The final window of a member reads exactly the remainder, never past its end | `copy_member` rebinding | `copy-tail-exact`: a member followed immediately by a different member's bytes in the source, asserting no bleed |
| Success — short read completed | A short `pread` is completed rather than treated as EOF | `copy_member` loop | `short-read-completed` against a fixture read through a lowered window |
| Success — padding written | Every interior padding byte is present and zero, and the file is not sparse | `write_padding` | `padding-is-zero`, `pack-not-sparse` (the reader compares logical size to the block count) |
| Success — no trailing padding | `total_bytes` equals the last member's end | `plan_layout` | `no-trailing-pad` |
| Success — size assertion | `f.len()` after writing equals `total_bytes` | step 11 | asserted on every positive fixture |
| Failure — zero-length read | A zero-length read at an in-range offset is `R4_WINDOW_UNAVAILABLE`, never `R4_PACK_TRUNCATED` | `copy_member` | `window-unavailable` against a source truncated between the plan and the copy |
| Failure — write error | A `pwrite` failure is `R4_WRITE_FAILED` naming the variant and the offset | `copy_member` | `write-to-full-filesystem`: a small fixed-size image filesystem, or a `ulimit -f` cap, whichever the host supports; skipped with one exact `N/A` line when neither does |
| Failure — partial cleanup | Any failure after creation removes the destination and records `REMOVED` | step 12 | `partial-pack-removed`: the destination does not exist after the run |
| Failure — cleanup failure | A removal that fails is `R4_CLEANUP_FAILED` and names the surviving path | step 12 | `cleanup-failed`: destination directory made read-only after creation; skipped under root |
| Failure — destination exists | An occupied destination is `R4_DEST_EXISTS` before anything is created or truncated | step 5 | `dest-exists`: an existing file's bytes and mtime are unchanged afterwards |
| Failure — destination unwritable | A `create_rw` failure is `R4_DEST_UNWRITABLE` | step 10 | `dest-unwritable` (read-only directory), `dest-is-directory` |
| Success — compare fast path | An identical window takes the `constant_time_equal` path and no byte scan | `compare_member` | `compare-fast-path`: `metrics.byte_scan_windows == 0` on every identical fixture |
| Failure — one flipped byte | A single flipped payload byte is `R4_CONTENT_MISMATCH` naming the member and the exact `delta` | `compare_member` | `flip-first-byte`, `flip-last-byte`, `flip-window-boundary`, `flip-across-two-members` — each asserting the exact detail string |
| Failure — length disagreement | Two windows returning different counts is a fault, never a silent shorter compare | `compare_member` | `compare-length-mismatch` |
| Failure — padding corrupted | A nonzero interior padding byte is `R4_PADDING_NONZERO` with its absolute offset | step 19 | `padding-corrupted` |
| Failure — identity | A pack verified against a different model stops at `R4_SOURCE_IDENTITY` before any byte comparison | step 16 | `identity-mismatch`: `metrics.bytes_compared == 0` |
| `bytes_read` accounting | Counts exactly the `pread` returns, in both arms | counters | `bytes-read-bound`: `payload_bytes <= bytes_read <= payload_bytes + data_offset + tables` for `--pack` |
| Early exit | On any failure the pass stops and the partial document reports what completed | guard returns | `partial-verify`: a mismatch at member 5 of 20 asserts `members_compared == 5` |
| Cleanup | Both handles close on `Drop`; the document destination is untouched on failure | scope | `untouched-destination`, `descriptor-budget` |
| Concurrency | `N/A`: two independent processes packing the same source to different destinations do not interact; packing to the **same** destination is an unsupported caller case, and the `R4_DEST_EXISTS` race of section 2.8 is documented rather than defended | `N/A` with this reason | documented unsupported caller case |
| Shared/process-global state | `N/A`: no process-global state; each arm is a pure function of its operands | `N/A` with this reason | `repeat-pack` (two runs to two destinations are byte-identical), `env-perturbation` |
| Move-out | Both documents are moved into their result records | epilogues | `document-move`; review against `docs/specs/c8-speed-first.md` section 2.8 |
| Borrow discipline | No helper returns a view derived from a `borrow` parameter | signatures | `make check` |
| Per-unit vs whole-program | The module compiles identically imported and whole-program | module boundary | `make check` (`check-per-unit`), `make build` |
| Determinism | Two packs of the same source are byte-identical, including padding | whole pass | `repeat-pack`, `sha256` of the two packs compared in the runner |

### 3.4 `src/model_ir.align` — the claim extraction

| Case | Contract to close | Implementation | Exact regression |
| --- | --- | --- | --- |
| Behavior preservation | Every `R1_MODEL_IR` document is byte-identical before and after the extraction | `resolve_claims`, `build` | `model-ir-smoke` re-run unchanged; the runner's golden documents |
| Single producer | `member_claim` has exactly one caller path; the packer computes no claim arithmetic of its own | module structure | import-graph review; a grep assertion in the runner that `src/alignpack.align` contains no `plane_bytes` arithmetic |
| Success — whole-tensor claim | `resolve_claims` returns `claimed_absolute_offset == absolute_offset` for a non-sliced member | `resolve_claims` | `claim-identity` (existing R1B case, re-run) |
| Success — slice claim | The section 2.5.3 slice arithmetic is unchanged | `resolve_claims` | `expert-slice-bytes` (existing R1B case, re-run) |
| Failure — claim codes | The four `Claim.code` values still map to their `R1_*` codes | `build` | the R1B claim error cases, re-run |
| Ownership | `ClaimTable` is frozen once and moved; no column is rebuilt | `resolve_claims` | ownership review |

### 3.5 `src/main.align` — the CLI arms

| Case | Contract to close | Implementation | Exact regression |
| --- | --- | --- | --- |
| Construction — arity | Three and four operands accepted for each arm; anything else is `Err` before any file work | `pack_demo`, `pack_verify_demo` | `cli-arity`: zero output and no destination on an arity failure |
| Success — both forms | Both forms emit byte-identical document bytes, and both write the pack for `--pack` | `pack_demo` | `form-parity` over every positive fixture |
| Success — summary block | Section 2.3's lines keep their order; `-` for absent values; control bytes sanitized | both arms | `summary-order`, `summary-control-bytes` |
| Failure — path guard | An empty, over-`MAX_PATH_BYTES`, or NUL-bearing operand — source, pack, **or** document — is `Err` with no output and no destination | `valid_cli_path` applied to every operand before the derivation | `path-too-long` × 3 operands, `nul-path`, `empty-path` |
| Failure — read-only source | A source the invoking user cannot write cannot be opened at this pin; the arm exits nonzero with no pack | `fs.open_rw` (Request 21) | `read-only-source` (mode `0444`; skipped under root) |
| Failure mapping | `status: "error"` becomes `Err(Error.Invalid)` after the document is emitted | epilogues | `error-corpus` exit codes |
| Selector isolation | `--pack` or `--pack-verify` in an operand position is an operand | dispatch shape | `selector-as-operand`, the `c7_selector` precedent at `src/main.align:373` |
| Architecture dispatch | `gpt-oss` selects the MoE frontend; every other value selects qwen2, whose own step-4 re-check rejects it | `pack_demo` | `arch-dispatch`, inherited from `--model-ir` |
| Help text | The usage block gains two lines and no other line changes | `usage` | `usage-diff` |
| Everything else | **inherited** from `docs/specs/r1-qwen-model-ir.md` section 3.3: unknown selector, environment isolation, OS failure | unchanged | the R1 CLI cases re-run |

### 3.6 Fixtures and the independent reader

| Case | Contract to close | Implementation | Exact regression |
| --- | --- | --- | --- |
| Reuse, not reinvention | The GGUF corpus is `scripts/gguf_fixture.py`'s existing qwen2 and gpt-oss containers, unchanged | runner | the generator's file is not modified in this capability's diff |
| Independence | `scripts/alignpack_reader.py` derives nothing from `src/`; it parses section 2.4 from this document | module imports | code review; the import list |
| Layout invariants | The reader asserts magic, versions, record widths, region disjointness, alignment, monotonicity, one-range-per-block, padding zero, name-span validity, and the reserved values | `check_pack` | `reader-invariants` over every fixture |
| Statistics oracle | The reader recomputes every section 2.6 value with a naive implementation and compares against the document | `stats` | `stats-oracle` |
| Byte identity, independently | The reader re-reads every member from both containers and compares, without invoking `--pack-verify` | `check_identity` | `independent-byte-identity` |
| Mutation detection | The reader is shown a pack with each of the section 3.1 corruptions and rejects each | `check_pack` | `reader-negative-corpus`: proves the reader is not vacuous |
| Determinism | Two generator runs produce byte-identical fixtures | fixed seed | `fixture-determinism` |
| Cleanup | Every artifact is written only into the caller-supplied temporary tree | runner | the repository leak sweep |

### 3.7 `Makefile` and `scripts/` — build and verification graph

| Case | Contract to close | Implementation | Exact regression |
| --- | --- | --- | --- |
| Target definition | One new target `alignpack-smoke` and one new focused qualification `alignpack-qualification`; the new module is reached through `check-per-unit $(ENTRY)`, which follows imports | `Makefile` | `python3 scripts/check-gate-topology` |
| Aggregate membership | `alignpack-smoke` joins `HOSTED_CHECK_TARGETS`: no model, no network, no reference tool, synthetic containers of a few hundred kilobytes, runs in seconds — the argument that admitted `model-ir-smoke` and `expert-trace-smoke` | `Makefile:17` | `make gate-topology-check` |
| Qualification exclusion | `alignpack-qualification` stays outside `HOSTED_CHECK_TARGETS`, `CAPABLE_ONLY_CHECK_TARGETS`, and every aggregate. It writes 4.36 GiB and must never be reached by an aggregate | `Makefile` | `make gate-topology-check` |
| **Preflight profile selection** | **The `Makefile` IS modified, so `FRESH_IMAGE_PATTERNS` (`scripts/verification_scope.py:22`) matches and the classifier selects the fresh-image installed profile.** `python3 scripts/pre-pr --plan` must be run and recorded before the real run, and the required installed profile must **not** be replaced by a Docker skip or an ambient `DOCKER_HOST` endpoint | `scripts/pre-pr` | `--plan` output recorded, then `scripts/pre-pr --owner-test alignpack-smoke -- make alignpack-smoke` |
| Fixture cleanup | Every artifact is removed by the `trap` on `EXIT`; the last assertion is that the temp root is still present | `scripts/run-alignpack-smoke` | the `run-model-ir-smoke` shape, reused |
| Qualification cleanup | The pack is removed on **every** exit path, including a failed verify and a signal | `scripts/run-alignpack-qualification` | `trap ... EXIT HUP INT TERM`; the runner's final line asserts the pack is gone and prints the reclaimed byte count |
| Qualification skip | An unset or absent `ALIGN_LLM_GGUF_MODEL`, or insufficient free space, prints one exact `N/A` line and exits 0 without claiming a pass | `scripts/run-alignpack-qualification` | a synthetic unit inside the runner |
| Repository safety | Neither runner may write inside the repository; the qualification refuses a temporary directory that resolves inside the work tree | both runners | `repo-leak-sweep`; `qualification-refuses-repo-tmpdir` |
| Documentation | `docs/specs/roadmap.md` section R4 and its forward order name this document, `HANDOFF.md` names it, `docs/align-development.md` gains an alignpack section; `docs/align-requests.md` receives the section 5.5 candidates and the new Request 21 and Request 23 client evidence; `docs/specs/r1-qwen-model-ir.md` section 2.5.6's role-major sentence is corrected per section 2.2 finding 1, recorded in that document's section 7 | integration commit | the register and document edits are applied |

## 4. Fixture and qualification design

### 4.1 The corpus

**No new GGUF generator.** `scripts/gguf_fixture.py` already emits the qwen2 and gpt-oss corpora
R1 and R1B use, with every expected value computed in Python, and R4's input is exactly a container
that generator produces. Reusing it means the pack corpus and the Model IR corpus can never drift,
and it keeps this capability's diff to one new Python file rather than two.

Six fixture families, all built from existing containers:

1. **Positive, dense.** `qwen2-full`, `qwen2-tied`, `qwen2-geometry`, `qwen2-permuted`: pack, verify,
   and read independently. `qwen2-tied` is the duplication case.
2. **Positive, MoE.** The gpt-oss containers, including both `expert_ffn_layout` variants. These
   close the per-expert contiguity cells synthetically. **MOE-PREREQ.**
3. **Negative, source.** The whole existing R0/R1 negative corpus, re-run through `--pack`, asserting
   that every `R0_*` and `R1_*` code passes through verbatim and that **no destination file is
   created** for any of them.
4. **Negative, destination.** Occupied, unwritable, a directory, a path with a NUL, an over-long
   path; plus the full-filesystem case where the host supports it.
5. **Negative, pack.** A written pack mutated one way per row of section 3.1 — bad magic, wrong
   version, each header field, a set reserved field, an overlapping region, a truncation at three
   depths, a corrupted name span, a misaligned `pack_offset`, a nonzero padding byte, and a flipped
   payload byte at four positions.
6. **Boundary.** Members sized at `W-1`, `W`, `W+1`, `2W`, `2W+1` for a lowered debug
   `COPY_WINDOW_BYTES`, plus a zero-byte member and a single-block container.

Lowered `MAX_*` constants for the three limits whose real values cannot be exceeded cheaply
(`MAX_PACK_BYTES`, `MAX_MEMBERS`, `MAX_TABLE_BYTES`) are supplied through a `debug_limits` entry
point the smoke's build names, exactly as `docs/specs/r2a-expert-trace.md` section 4.2 established;
that entry point does not exist in `main`.

### 4.2 Owner — `scripts/run-alignpack-smoke`, `make alignpack-smoke`

One runner in the `scripts/run-model-ir-smoke` shape: `unset GIT_DIR GIT_COMMON_DIR GIT_WORK_TREE`,
`PYTHONDONTWRITEBYTECODE=1`, a `mktemp -d` tree removed by the `EXIT` trap, the existing generator
invoked into it, then one embedded Python driver. No model, no network, no reference tool, which is
why it joins `HOSTED_CHECK_TARGETS`. The largest synthetic container is a few hundred kilobytes, so
the whole run writes well under a megabyte.

Beyond the closure cells, the runner:

- asserts `schema_version == 1` and the exact top-level and nested field order on every document of
  both kinds;
- runs both CLI forms over every fixture and diffs the document bytes;
- for every positive fixture, runs `--pack`, then `--pack-verify`, then `alignpack_reader.py`, and
  requires all three to agree on every block and member;
- packs each positive fixture **twice** to two destinations and asserts the two packs are
  byte-identical, which is the determinism claim;
- asserts that no negative fixture left a destination file behind, and that a fixture that failed
  mid-copy left none either;
- asserts `metrics.byte_scan_windows == 0` on every identical comparison, so the fast path is
  actually taken;
- runs the reader's negative corpus, proving the reader rejects what it should;
- asserts the section 3.4 single-producer claim structurally — no claim arithmetic in
  `src/alignpack.align`, one definition and one caller of `member_claim` in `src/model_ir.align`;
- asserts `usage-diff` over the help block;
- drives `scripts/run-alignpack-qualification` through its refusals (`qualification-skip`) and
  asserts each `N/A` line exactly, including that an occupied destination survives untouched;
- with `ALIGN_LLM_ALIGNPACK_ENOSPC=1` on a host with `hdiutil`, mounts an 8 MiB volume and closes
  `write-to-full-filesystem` and the qualification's headroom refusal (section 7.2);
- keeps the repository leak sweep, the temp-root assertion, the descriptor budget,
  `env-perturbation`, and `repeat-pack`.

### 4.3 The independent reader and the two oracles

**`scripts/alignpack_reader.py`** is a complete second implementation of section 2.4, written from
this document rather than from `src/alignpack.align`. It is the answer to "how do you know the
writer's own report is true": every layout invariant of section 3.6 is checked by code that shares
no line with the writer. It is also the format's executable specification — if this document and the
reader disagree, one of them is wrong and the smoke says so.

**Golden container bytes.** One small fixture — the smallest qwen2 container — is packed and its
first 4096 bytes (header, name stream, and the start of the block table) are compared against a
checked-in hex golden. That is what makes an accidental field reorder or a stride change a test
failure rather than a silent format break. The golden covers only the metadata regions; the payload
is covered by byte identity, and pinning 300 KB of payload bytes would be a golden of the generator,
not of R4.

**The statistics oracle.** Every section 2.6 value is recomputed in the runner, in Python, from the
raw tensor table and the raw pack tables, with a deliberately naive implementation — nested loops
and explicit interval merging — rather than the sweep `src/alignpack.align` uses. Two independent
implementations of one definition is what makes the ppm numbers trustworthy; a Python transcription
of the sweep would share its bugs.

### 4.4 Focused qualification — `scripts/run-alignpack-qualification`

Opt-in, never in an aggregate, never in CI. It is the only thing in this repository that writes a
multi-gigabyte file, and its contract is written around that fact.

```text
ALIGN_LLM_GGUF_MODEL        path to the model                            (required, no default)
ALIGN_LLM_ALIGNPACK_TMPDIR  directory for the pack                       (optional; default: mktemp -d)
```

What it does, in order:

1. Refuses to run if `ALIGN_LLM_GGUF_MODEL` is unset or absent, printing exactly one `N/A` line.
2. Resolves the temporary directory — **physically, with `pwd -P`, as it resolves its own root** —
   and **refuses one that resolves inside the work tree**, so a 4.36 GiB artifact can never land in
   the repository even by a mistyped variable or a symlink. Two logical paths cannot be compared by
   prefix: the guard's whole purpose is defeated if a symlink into the repository resolves to a name
   the prefix test does not match.
3. **Refuses an occupied destination, before the reclaim trap is installed.** The trap removes
   whatever stands at the pack's path, so a runner that installed it first and refused afterwards
   would delete the artifact it declined to overwrite. This is `--pack`'s own step-5 rule applied to
   the runner.
4. Records the model's size and mtime.
5. **Checks free space before writing anything.** It requires `model_size + 1 GiB` available on the
   temporary directory's filesystem and prints one exact `N/A` line if not. On this host the pack is
   4,677,222,400 bytes (4.36 GiB), so the requirement is 5.36 GiB against 26 GiB free.
6. Runs `main --pack MODEL PACK DOC.json`, timing it.
7. Runs `main --pack-verify MODEL PACK VERIFY.json`, timing it.
8. Runs `scripts/alignpack_reader.py` over the real pack — the same invariants, at real scale.
9. Asserts the model's size and mtime are **unchanged**.
10. Prints the measured improvement from the verify document.
11. **Removes the pack on every exit path** — success, failure, or signal — through
    `trap ... EXIT HUP INT TERM`, then asserts it is gone and prints the reclaimed byte count.

**All six `N/A` lines, in the order the runner can emit them**, each printed alone and exiting 0
without claiming a pass. The list is complete: a refusal this document does not name is a defect:

```text
alignpack qualification: N/A (ALIGN_LLM_GGUF_MODEL unset)
alignpack qualification: N/A (ALIGN_LLM_GGUF_MODEL is absent)
alignpack qualification: N/A (ALIGN_LLM_ALIGNPACK_TMPDIR is not a directory)
alignpack qualification: N/A (ALIGN_LLM_ALIGNPACK_TMPDIR resolves inside the work tree)
alignpack qualification: N/A (the destination already exists: <pack>)
alignpack qualification: N/A (insufficient free space: <avail> < <required>)
```

`scripts/run-alignpack-smoke`'s `qualification-skip` unit drives the runner through the first five
and asserts each line exactly, that the exit status is 0, and that an occupied destination is
neither removed nor rewritten. The sixth needs a filesystem with less than a gibibyte free and is
asserted by the opt-in `write-to-full-filesystem` case, which mounts one.

The verdicts it emits rather than the pull request authoring them:

```text
alignpack qualification (identity): PASS
alignpack qualification (sequential read): PASS  src 89 ranges / 11130544128 span / 2379786 ppm
                                                 pack 58 ranges / 4677120000 span / 1000000 ppm
alignpack qualification (MoE): N/A - no gpt-oss GGUF on this host; see section 4.5.
```

**Expected budget on this host**, from section 2.2's measurements and stated as a range because
those measurements varied by a factor of two: the pack moves 4,677,120,000 payload bytes at a
measured 0.8–1.3 GB/s of payload copy throughput, so roughly 4–6 s; the verify reads that much from
each container with no writes, so roughly 3–10 s depending on cache; the reader's independent pass
reads the same 9.35 GB again in Python and is the slowest step. Total a few minutes at worst, and the
disk holds the pack only for that long. These are **budget estimates, not thresholds**: the
qualification asserts no elapsed bound and fails on no timing.

### 4.5 The MoE prerequisite

Every **MOE-PREREQ** cell in section 3, and the per-expert half of the improvement claim, need a real
gpt-oss GGUF, which does not exist on this host.
`docs/specs/r1b-gptoss-moe-ir.md` section 4.4 already records the same pending user decision about
`gpt-oss-20b-mxfp4.gguf` (12.1 GB), and R4 adds one consideration to it: **packing a 12.1 GB model
needs 12.1 GB of free space on top of the model itself.** With 27 GiB free, downloading it (12.1 GB)
and packing it (12.1 GB) leaves under 3 GiB. That is the honest constraint, and it is a reason to
prefer a smaller MoE GGUF — the same one `docs/specs/r2a-expert-trace.md` section 4.5 asks for — over
gpt-oss-20b, since a small MoE would discharge the R2 locality gate and R4's per-expert cells with
one download.

Until then, the MoE half is `N/A` with this reason and never counts as a pass.

### 4.6 Metrics

**Primary — correctness.** Three pass/fail measurements, none of them a speed metric: every fixture's
payload bytes are identical in both containers, verified twice (by `--pack-verify` and independently
by `alignpack_reader.py`); every block of every pack has `range_count == 1` and
`span_bytes == pack_bytes`; and every error code fires on its own fixture with the exact detail.

**Primary — the gate's second half.** `range_count_total`, `span_bytes_total`,
`contiguous_block_count`, and `amplification_ppm_total` for both containers, per model and per block
kind, as defined in section 2.6 and computed by two independent implementations.

**Secondary — `bytes_read` and `bytes_written`.** For `--pack`:
`payload_bytes <= bytes_written <= total_bytes` and
`payload_bytes <= bytes_read <= payload_bytes + data_offset + MAX_TABLE_BYTES`, asserted on every
fixture. This is the evidence that the copy streams rather than rescans.

**Secondary — peak resident bytes.** `COPY_WINDOW_BYTES` (pack) or `2 * COPY_WINDOW_BYTES` (verify)
plus the plan, asserted through `peak-allocation` and the descriptor budget. A 4.68 GB pack must not
produce a 4.68 GB resident set; that is the whole claim of section 2.7 and it is measured.

**Secondary — elapsed.** `metrics.elapsed_ns` for each arm, recorded in the qualification's output.
It is a **diagnostic, not a threshold**: no baseline is established and no throughput is asserted.

**R4 makes no performance claim.** `COPY_WINDOW_BYTES` is chosen on syscall count, not on a measured
win (section 2.2), and the section 2.6 metric is a claim about **layout**, not about achieved
bandwidth. Under `CLAUDE.md` a speed claim would require a reproducible benchmark against a named
baseline on the primary metric; R4 has neither and does not pretend to. If a later capability wants
"time to first token improved by packing", it owns that benchmark, and R5 is where it belongs.

## 5. Deferred surfaces

### 5.1 Expert hotness ordering

Roadmap section R4 names *expert hotness* as a layout property. It reorders `ExpertBlock`s within a
layer — or across the file — so that the experts a workload actually activates are adjacent, which
turns a scattered set of expert fetches into one larger sequential read.

**Why it is deferred.** A hotness rank is a function of an activation distribution.
`docs/specs/r2a-expert-trace.md` section 1.4 item 3 records that no MoE transcript exists on this
host, so every rank R4 could assign today would be arbitrary. An arbitrary rank persisted into a
container is worse than no rank: a consumer would trust it.

**What is reserved.** `flags` bit 0 and the `hotness_rank` field of every block record. In v1 both
must be `0` and `0xFFFFFFFF` respectively, and a reader that finds otherwise fails
`R4_PACK_RESERVED`. Adopting hotness is then: compute ranks from an `R2_ACTIVATION_TRACE`, order the
`ExpertBlock`s of a layer by rank instead of by expert index, fill `hotness_rank`, set the flag.
**The block table stays in Model IR order** — only `pack_offset` changes — so the index identity of
section 2.4.3 survives and no consumer breaks.

**What would have to be settled first**: whether hotness is global or per-workload (a per-workload
pack is a per-workload artifact), and how a pack whose ranks are stale is detected. Both are R3
questions.

### 5.2 Prefetch groups

The second deferred property. A prefetch group is a set of blocks a scheduler fetches together
because they are used together — the natural unit is "layer L's router plus its top-k experts", but
which k, and whether the group is static or per-token, is exactly what R3's policy comparison
decides.

**What is reserved.** `flags` bit 1 and the `prefetch_group` field of every block record, `0` and
`0xFFFFFFFF` in v1. A group is a small integer shared by the blocks of one group; blocks of one group
would additionally be laid out consecutively so a group is also one range. That is a layout change,
not a format change, which is why reserving one `u32` is enough.

**Why not a static group now.** The one grouping R4 could justify without a trace — "a layer's blocks
form a group" — is already achieved by the layout: a layer's blocks are consecutive, so a caller
that wants a whole layer reads from the first block's `pack_offset` to the last block's end. Encoding
that as an explicit group would add a field whose only value is a fact the offsets already state.

### 5.3 R4.5 — the external buffer spike

`docs/specs/roadmap.md` section R4.5 asks whether ggml can compute over quantized weights in a buffer
Align owns. R4 is what makes that spike cheap: a block is one aligned contiguous range, so the spike
reads `pack_bytes` at `pack_offset` into one buffer and hands ggml a pointer, with no gather and no
reassembly. R4 deliberately does not attempt it: it involves an FFI boundary, a lifetime contract
with a foreign library, and a GPU, none of which this capability touches.

The one thing R4 does for it is the `block_align = 4096` choice of section 2.4.1, which is what makes
a block's start acceptable to a page-granular upload path.

### 5.4 R5 — the loader

R5 reads the pack. R4 owes it a format that can be walked with `pread` and the scalar decoders, and
section 2.4 is that. R4 deliberately ships **no** reader helper beyond the verifier's own decoder:
exporting a half-designed loading API before its consumer exists would fix a contract R5 has not
asked for yet. When R5 lands, `src/alignpack.align`'s decoder is the natural thing to make `pub`,
and the fixed strides of section 2.4.2 are what let R5 read one block's record without reading the
table.

R5 also owns the **residency** question entirely — which tier a block lands in, when it is evicted,
what the cache score is. R4 assigns no tier to any block and records no policy.

### 5.5 Candidate Align capability requests

Three genuine gaps, each verified against the pin rather than assumed, each **non-blocking** for R4,
and each recorded because `CLAUDE.md` requires recording a language-owned requirement even when a
workaround exists. This document does not edit `docs/align-requests.md`; the orchestrator owns the
register, and these are the candidates it would add as Requests 29, 30, and 31.

Two guesses the plan started with are **refuted** and are recorded as refuted: `pwrite` **exists**
(`f.pwrite(data, off)`, taking `bytes`, and it never short-writes), and a byte-view `sha256`
**exists** (`crypto.sha256`, already used by this repository). Neither is a gap. A third guess — that
`buffer` reuse would be blocked by the absent `clear` — is real as a language gap but **does not
affect R4**, because every window reuse goes through `pread`, which overwrites the length; it is
noted here as evidence for a future client rather than raised as R4's own request.

#### 5.5.1 Candidate Request 29 — an incremental digest

**The gap.** `crypto.sha256(data)` and `crypto.sha512(data)` are one-shot over exactly one byte view
(`crates/align_sema/src/lib.rs:54374-54386`); there is no `sha256_init` / `update` / `final`, no
digest handle, and no `Hasher`. `hash64` / `hash128` are incremental in neither sense and are
explicitly not stable across builds
(`../align/docs/impl/core-design/hash.md`), so they cannot bind a persisted artifact.

**The consequence for the client.** align-llm cannot digest a file larger than memory. R4 wanted a
whole-payload digest so that a pack could certify itself without re-reading the source; it settled
for the bounded header-region digest of section 2.4.6 and reserved the payload field. C7's persisted
results already digest whole artifacts through `crypto.sha256` and are safe only because they are
bounded by `ARTIFACT_MAX_BYTES`; the first artifact that is not bounded meets this wall.

**Proposed surface**, Align-consistent and following the existing Move-handle idiom:

```text
crypto.sha256_stream() -> digest          # a Move handle, Drop-released
d.update(data: str | string | slice<u8>)  # borrows the view, never consumes
d.finish() -> array<u8>                   # consumes the handle, yields 32 bytes
```

**Acceptance criteria**: `finish()` over `n` `update` calls equals `crypto.sha256` over the
concatenation, for `n` in `{0, 1, 2, 1000}` and for chunk boundaries at every offset of a
multi-megabyte input; the handle is Move, closes on `Drop`, and cannot be used after `finish`; an
`update` after `finish` is a compile error; the digest of the empty input is the known SHA-256 of the
empty string.

```text
Status: PROPOSED
Priority: medium
Blocking: no
Blocked gate or slice: none; R4 ships the bounded header-region digest and reserves `payload_sha256`
Independent work that may continue: all work
Resume condition: an Align release ships an incremental digest handle
Align commit or pull request: none
align-llm verification: `alignpack-qualification` would fill `payload_sha256` and assert it against an independent Python digest of the same payload
```

#### 5.5.2 Candidate Request 30 — exclusive random-access create

**The gap.** Align ships two ways to create a file and neither does what a packer needs.
`fs.create_rw(path)` returns a `file` with `pwrite` but opens `O_RDWR|O_CREAT|O_TRUNC`
(`crates/align_runtime/src/lib.rs:9890`), so it silently destroys an occupied destination.
`fs.create_exclusive(path)` refuses an occupied destination but returns a sequential `writer` whose
only methods are `write` and `flush` (`crates/align_sema/src/lib.rs:53164`, `55795`) — no positional
write, so a planned layout cannot be realized through it. The two properties cannot be combined.

**The consequence for the client.** Section 2.8's `R4_DEST_EXISTS` is a check-then-create race:
`fs.exists` then `fs.create_rw`, with a window in which another process could create the path that is
then truncated. The artifact at risk is multiple gigabytes. `docs/align-requests.md` Request 14
closed the same problem for the sequential-writer case, which is why the asymmetry is visible: the
exclusive publication story exists and simply does not extend to `file`.

**Proposed surface**, mirroring the shipped Request 14 pair:

```text
fs.create_rw_exclusive(path: str) -> Result<file, Error>
```

`O_RDWR|O_CREAT|O_EXCL|O_CLOEXEC|O_NOFOLLOW`, mode `0644`, failing deterministically when the path
exists, never truncating, never following a destination symlink, returning the same owned `file`
handle with the same `Drop` contract.

**Acceptance criteria**: creation at an absent target succeeds and yields a working `pwrite`;
an existing regular file, directory, symlink, or FIFO at the target fails deterministically with the
target unmodified; a competing creator between preflight and create loses deterministically; the fd
is `O_CLOEXEC` and closes on every `?`, `map_err`, branch join, early return, and `Drop`; repeated
create/free cycles leak no descriptors.

```text
Status: PROPOSED
Priority: medium
Blocking: no
Blocked gate or slice: none; R4 ships the documented check-then-create with `R4_DEST_EXISTS`
Independent work that may continue: all work
Resume condition: an Align release ships an exclusive random-access constructor
Align commit or pull request: none
align-llm verification: `alignpack-smoke`'s `dest-exists` case would assert the exclusive failure with no `fs.exists` preflight
```

#### 5.5.3 Candidate Request 31 — durability

**The gap.** The runtime contains no `fsync`, `fdatasync`, `sync_all`, or `F_FULLFSYNC`, and
`../align/docs/impl/std-design/fs.md` records "no `fsync`, or crash-durability promise" as a
deliberate non-goal. A `writer`'s `flush` pushes to the kernel, not to the device, and `file` has no
flush at all.

**The consequence for the client.** align-llm cannot promise that any artifact survives a power loss.
For R4 this is **genuinely harmless** and the honesty is worth stating plainly: a pack is a
deterministic derivative of a file that still exists, so the recovery from a torn pack is to run
`--pack` again, and `--pack-verify` detects a torn pack anyway. It is recorded because the next
client may be a persistent KV cache (roadmap R6), where losing the artifact loses the only copy.

**Proposed surface**: `f.sync() -> Result<(), Error>` on `file` and `w.sync() -> Result<(), Error>`
on `writer`, each a real `fsync`/`F_FULLFSYNC` with the platform difference documented rather than
hidden. **Acceptance criteria** must state exactly what is and is not promised on each supported
filesystem, because a durability API that over-promises is worse than none.

```text
Status: PROPOSED
Priority: low
Blocking: no
Blocked gate or slice: none; R4 makes no durability claim (section 1.3)
Independent work that may continue: all work
Resume condition: an Align release ships a sync operation with a stated per-platform guarantee
Align commit or pull request: none
align-llm verification: none required for R4; the first consumer would be roadmap R6's persistent KV
```

#### 5.5.4 Client evidence for existing requests

- **Request 21** (`fs.open_ro`) gains its strongest client yet, in two forms. R4 opens a 4.68 GB model
  it never writes and must request `O_RDWR`; and because Align ships no `fs.size` / `stat`, even
  *learning the model's length* requires a writable descriptor. A model on read-only media, or owned
  by another user, cannot be packed at all. The absent size call is arguably a second request; it is
  recorded here as evidence on 21 because both are answered by the same read-only file story.
- **Request 23** (huge-struct-copy warning on `borrow` parameters) gains a **fourth** client:
  `PackPlan` is another wide columns-plus-stream record read through `borrow` accessors.
- **`buffer` has no `clear` / `truncate` / `reserve`** (six ABI entry points; `put` and `append`
  always extend from `len`). Verified not to affect R4, because every window reuse goes through
  `pread`, which overwrites the length, and the table writer rebinds a fresh buffer per chunk. It is
  recorded as evidence for the first client that must assemble and flush the same buffer repeatedly.

### 5.6 Inherited deferrals

Unchanged and untouched by R4: tokenizer and vocabulary (Request 22, deferred since R1); the gpt-oss
real-model `model-ir-parity` qualification (`docs/specs/r1b-gptoss-moe-ir.md` section 4.4); the R2
locality measurement and its MoE transcript (`docs/specs/r2a-expert-trace.md` section 4.5); every R3
cache policy; and `docs/specs/align-llm.md` section 4.2's `model.alignidx` and `model.alignprof`
companions, which are separate artifacts with separate consumers and no v1 surface here.

## 6. Correction ledger

Sections 1 to 5 were written before the capability was implemented. Every row below is a place
where implementation proved one of them wrong, incomplete, or self-contradictory. The shipped
behaviour is the right-hand column; sections 1 to 5 are left as written so the correction is
visible, and section 7 maps every closure cell onto the regression that now closes it.

### 6.1 The open decision of section 2.4.7 — **resolved on the primary path**

`f.pwrite(pad.bytes()[0..n], off)` compiles **and runs correctly** at pin `4b515f8d`. A compile
probe declared a 64-byte zero `buffer`, wrote `pad.bytes()[0..13]` at offset 24 of a fresh
`fs.create_rw` destination, received `13` back, and observed `f.len() == 37` with the written region
zero. Sub-slicing a `slice<u8>` argument to `pwrite` is therefore a shipped surface and the recorded
per-pad `mut pad := buffer(0)` fallback is **not shipped**. `write_padding` uses the single prepared
`BLOCK_ALIGN` zero buffer for every run.

### 6.2 Public surface

| Section | As designed | As shipped, and why |
| --- | --- | --- |
| 2.10, 2.9 | `pub fn build_pack(source: str, destination: str) -> AlignPack` | `build_pack(borrow t: gguf.GgufTable, borrow g: model_ir.Geometry, borrow plan: model_ir.BlockPlan, source, destination, in_code, in_detail, borrow limits) -> AlignPack`, and the same shape for `verify_pack`. The two-operand signature contradicts section 2.9's own rule that the packer imports no frontend: only a frontend can produce a `BlockPlan`, and the architecture dispatch lives in `src/main.align`. The arm hands the settled plan in |
| 1.2 item 4 | Exactly one extraction, `model_ir.resolve_claims` | Two, and the second is forced by the first. `frontend_qwen.prepare` and `frontend_gpt_oss.prepare` now return the whole derivation as data and `build_model_ir` renders over exactly that value. The record is `model_ir.Prepared`, owned by the neutral builder rather than by each frontend, because `src/main.align` selects between the two in one conditional and two identically shaped per-frontend records are two types. `model-ir-smoke` re-runs unchanged and is the byte-identity regression |
| 2.9 | `resolve_claims` alone | `resolve_claims` plus `pub fn claim_ordinal(borrow plan, slot) -> i64`. The duplication sweep needs `model_ir`'s own `(tensor, ordinal)` claim key and must not repeat the section 2.5.3 slice arithmetic, which is the whole point of the extraction |
| 2.8 steps 3–4 | Container read, then architecture dispatch and the frontend | The **whole** R1 ordered derivation. Coverage (step 11a), claim tiling (11b), and the size-sum oracle (12) also have to pass before a byte is written, so each arm runs the whole derivation and passes its status to the packer. No `R1_MODEL_IR` document is produced: its authoritative producer is `--model-ir`, emitting a second copy from this arm would create two producers of one exchanged format, and section 6.8 replaces the first shipped shape — which rendered the document and dropped it — with `model_ir.derive_status` |
| 4.1 | A `debug_limits` entry point, surface unnamed | `pub Limits`, `pub fn default_limits()`, `pub fn lowered_limits(...)`, and `src/alignpack_limits_smoke.align`, which the smoke drives with `alignc run`. `main` never constructs a `Limits`: both arms use `default_limits()`, so the shipped contract is the section 2.7 table |

### 6.3 The sequential-read metric applied to the pack

**Section 2.4.7 consequence 1 and section 2.6's gate item 1 are too strong as written.** They assert
`range_count == 1` for every block of every pack. Under section 2.6's own definition — sort the
block's claims and merge any two that *touch or overlap* — a block whose member size is not a
multiple of `member_align` leaves a 1-to-63-byte alignment gap between two consecutive members, and
those two claims do not touch. Section 2.6 requires the definition to be applied to both containers
unchanged, and it is; the consequence is that a padded block merges into more than one range.

The shipped invariant, which is what the gate actually rests on and is asserted exactly rather than
as an inequality:

1. **`span_bytes == pack_bytes` for every block of every pack, always.** A consumer fetching the
   block with one sequential read transfers exactly the block and nothing else. This is the property
   section 2.6 calls "the sequential read bytes per block fetch" and it is unconditional.
2. **`range_count == 1 + g`, where `g` is the number of member boundaries the layout had to pad.**
   The smoke derives `g` from the member offsets in the document and asserts equality, so a planner
   that inserted an unexplained gap fails a test the old inequality would have passed.
3. **`range_count == 1` and `amplification_ppm == 1_000_000` exactly when the block's interior
   padding is zero**, which is the case for every block whose member sizes are all `member_align`
   multiples.

Every member of the reference model is a multiple of 64, so section 2.2's predicted 58 ranges,
4,677,120,000 span bytes, 58/58 contiguous blocks, and **1,000,000 ppm exactly** are what the
qualification measured. `qwen2-geometry` is the fixture that exercises the padded case: its source
is already fully contiguous, so its pack is 40 ppm *worse* — the price of the alignment guarantee,
reported rather than hidden. The improvement is therefore asserted only over a source that is not
already contiguous, and the exact identities above are asserted everywhere.

Two smaller corrections to section 2.6 follow:

- `amplification_ppm` of a block with `payload_bytes == 0` is `0`. Section 2.6 leaves it undefined;
  `-` is not representable in a JSON integer field, so `0` beside `payload_bytes: 0` is the
  discriminator.
- The sweep needs two bounds section 2.7 does not name, because it packs a byte offset above a
  20-bit within-block member ordinal: `member_count <= 1_048_575` and every offset
  `<= I64_MAX >> 20`. Both are checked in step 7, before any offset reaches the sweep, and a
  violation is `R4_MEMBER_LIMIT` or `R4_LAYOUT_OVERFLOW`.
- **The "counted once" rule rests on a precondition, and the precondition is R1's.** The sweep drops
  a duplicate claim by comparing it against the previously accepted one, which is correct only if
  two claims that share an offset also share a size. `src/model_ir.align`'s step 11b proves exactly
  that: the claims over one tensor are either all whole-tensor claims or an exact partition of its
  range, so no run of the form `(o,s) (o,t) (o,s)` exists and no duplicate can be separated from its
  twin by a different claim. Both packing arms run that oracle before the planner (step 4), so the
  adjacent test is sound; a caller that reached this sweep without it would need a block-local set.

### 6.4 The documents

Section 2.5 pins a field set but leaves several orders and one field open. The shipped schema 1 is:

| Change | Reason |
| --- | --- |
| `sequential_read` order is `source_of_pack_stats`, `source`, `pack` | Section 2.5 names the field without placing it |
| `by_kind` rows carry `kind` and `block_count` beside the five named fields | "The same five fields" needs a discriminator to say which kind a row is, and a denominator to make `contiguous_block_count` readable |
| `blocks[]` gains `pack_span_bytes` and `pack_amplification_ppm` beside `pack_range_count` | Section 6.3 makes `pack_range_count` alone insufficient to state a block's result, and `span_bytes == pack_bytes` is the invariant a reader should be able to check from the document |
| `blocks[].members[]` gains `role_id` | So a consumer can tell "the frontend supplied no role" (`0xFFFFFFFF`) from "this writer's frozen list does not name that role", which `role: null` alone cannot say |
| `destination` is a top-level document field, after `error_detail` | Section 2.3 puts it in the summary and section 2.5 omits it. A machine reading the document must be able to learn whether a partial artifact survived a failure |
| `--pack-verify` reports `source_of_pack_stats: "none"` when the pack's tables could not be decoded | `"pack_tables"` would claim an observation that did not happen |
| `--pack-verify`'s `pack` object is decoded from the container's header, and `blocks` is empty when the tables could not be decoded | Section 2.5 requires the verify statistics to come from the pack's own tables. Reporting the expected layout under a field name that promises an observation would contradict that |

**`role_id` is an index into a frozen list owned by `src/alignpack.align`, not by a frontend.**
Section 2.4.4 names "its index in the frozen role list of `docs/specs/r1-qwen-model-ir.md` section
2.5.6". That sentence lists fifteen roles, and the two shipped frontends number their own internal
role enumerations differently and incompatibly (`token_embd` is `0` in `frontend_qwen`, and
`frontend_gpt_oss` renumbers everything from index 9 onward), so an id taken from a frontend would
mean two different things in two packs. The shipped list is entries 0 to 14 for section 2.5.6's
fifteen roles **in that sentence's order**, then entries 15 to 26 for the roles
`docs/specs/r1b-gptoss-moe-ir.md` adds, appended so the R1 indexes can never move. A role the list
does not name is `0xFFFFFFFF`, which is a stated absence and never an index.
`scripts/alignpack_reader.py` carries the same table, transcribed from this section.

**`form-parity` is asserted over documents normalized on `elapsed_ns`.** Section 2.3 requires the
two forms of an arm to emit byte-identical document bytes and section 2.5 puts `metrics.elapsed_ns`
in the document; a wall-clock observation of the run that produced the document cannot be equal
across two runs. Every other byte of both documents is a function of the two containers alone and is
compared byte for byte. The **pack bytes themselves are compared with no normalization at all**, so
`repeat-pack` remains an exact claim about the container.

### 6.5 Error codes and process exits

| Section | As designed | As shipped, and why |
| --- | --- | --- |
| 2.8 step 12, error table | `R4_CLEANUP_FAILED` as a code | The prose of step 12 is followed instead: the original failure keeps the `error_code` and `error_detail` becomes `R4_CLEANUP_FAILED`, with `destination: "WRITTEN"`. Promoting the cleanup failure to the code would lose the cause of the failure that made cleanup necessary |
| 3.3 `dest-is-directory` | `R4_DEST_UNWRITABLE` | `R4_DEST_EXISTS`. Step 5's `fs.exists` is true for a directory and runs before `fs.create_rw`, so the occupied-destination guard fires first. That ordering is the safer answer and it is the one the section 2.8 order produces |
| 2.8 step 17, 3.1 | A UTF-8 re-validation of each name span | Byte comparison against the expected name, whose bytes already passed R0's own UTF-8 validation, so byte equality is strictly stronger than re-decoding. `R4_PACK_NAME_MISMATCH` still fires, with the member index as its detail. `scripts/alignpack_reader.py` does decode every span, so the property is checked by a decoder as well |
| 2.8 step 11 | One `R4_SIZE_MISMATCH` against `f.len()` | Two, both reporting the same code and the two decimal sizes: the writer's own cursor against `total_bytes` first, then the live `f.len()`. A planner/writer disagreement and a filesystem disagreement are different facts |
| 2.3 | `Err(Error.Invalid)` | Unchanged in the source; the **runtime** maps it to process status 2, not 1. Every regression asserts "a recorded nonzero failure, never an abort", which is the shape `run-model-ir-smoke` already uses for the same mapping |
| 2.8 step 13, 17 | `R4_PACK_RESERVED` at two steps | Unchanged, but a record's reserved and deferred fields are validated at the moment the record is decoded rather than after the whole cross-check, so `R4_PACK_RESERVED` precedes `R4_PACK_BLOCK_MISMATCH` for a record that is wrong in both ways. Failing closed on a field whose meaning is reserved before comparing fields whose meaning depends on it is the correct order |

### 6.6 Shape corrections forced by the language

Neither row is an application workaround for a missing capability; both are shapes the pin requires,
and section 7.3 classifies them.

- **The ordered guard chains are straight-line early returns, not `loop { … break }`.** An owned
  aggregate assigned to an outer `mut` local from inside a loop body is dropped at the end of the
  iteration that declared it at this pin (`use of invalidated borrow: its source was dropped at the
  end of the loop iteration that declared it`), so the plan and the inspection could not be read
  after the loop that produced them. `execute_pack` and `execute_verify` are therefore chains of
  early returns that hand one owned record to the renderer, and every derived value is read out of
  that record by borrow. `src/model_ir.align`'s `build` keeps its `loop { … break }` because
  everything it assigns across the loop boundary is a `string`.
- **`by_kind` is aggregated by one sweep per kind, `O(5B)` over the per-block columns.** An
  `array<i64>` is not a mutable accumulator at this pin, so five scalar sweeps replace one indexed
  one. The per-block sort of section 2.9 is unchanged.

### 6.7 Measured result, against section 2.2's prediction

`ALIGN_LLM_GGUF_MODEL=~/models/qwen2.5-coder-7b-instruct-q4_k_m.gguf scripts/run-alignpack-qualification`
on this host, one run:

| Quantity | Section 2.2 predicted | Measured |
| --- | --- | --- |
| Source ranges / span / ppm | 89 / 11,130,544,128 / 2,379,786 | **89 / 11,130,544,128 / 2,379,786** |
| Pack ranges / span / ppm | 58 / 4,677,120,000 / 1,000,000 | **58 / 4,677,120,000 / 1,000,000** |
| Contiguous blocks | 27 → 58 of 58 | **27 → 58 of 58** |
| `WeightBlock` source ppm | 2,039,993 | **2,039,993** |
| `AttentionBlock` source ppm | 10,922,100 | **10,922,100** |
| `MlpBlock` source ppm | 1,291,478 | **1,291,478** |
| Interior alignment padding | 57,344 | **57,344**, and `duplicated_bytes` 0 |
| Pack size | 4,677,177,344 (section 4.4) | **4,677,222,400** — section 4.4 omitted the 45,056-byte metadata prefix; the payload and padding are exactly as predicted |
| Peak resident window | one `COPY_WINDOW_BYTES` plus the plan | **5,953,536** — the step-9 header-region buffer, which is larger than the 4 MiB copy window on this model and is released before the payload loop begins, exactly as section 2.9 says |

Diagnostics, not thresholds and not a performance claim: `--pack` 7.68 s wall (7.39 s in-arm) moving
4,677,120,000 payload bytes with 1,387 `pread`s and 1,420 `pwrite`s; `--pack-verify` 4.07 s wall
(3.54 s in-arm) reading 9,360,295,936 bytes and comparing 4,677,120,000. The pack was removed on
exit and the runner reported 4,677,222,400 reclaimed bytes.

**Re-run once after the section 6.8 repair**, on the same host and the same model: every measured
quantity in the table above is unchanged, including the two range/span/ppm rows, the 27 → 58 of 58
contiguous blocks, all three per-kind ppm figures, the 57,344 interior padding bytes, `duplicated 0`,
the 4,677,222,400-byte pack, and the 5,953,536-byte peak window. The wall clocks moved, as wall
clocks do: `--pack` 6.74 s (6.72 s in-arm) with the same 1,387 `pread`s and 1,420 `pwrite`s,
`--pack-verify` 3.12 s (3.05 s in-arm) over the same byte counts. The pack was removed on exit and
4,677,222,400 bytes were reported reclaimed.

### 6.8 Corrections found by review of the implemented capability

Two complementary reviewers read the shipped diff. Every finding they raised was accepted; the rows
below are the ones that change a stated contract, each with the case that closes it. The remaining
findings were comment, documentation, or test-strength repairs and are recorded in section 7.

| Contract | As shipped at first | As corrected, and why | Closing case |
| --- | --- | --- | --- |
| 2.4.7 "no trailing padding"; 2.8 step 17 | Nothing compared the header's region geometry against the derived plan. A pack extended with real bytes whose `total_bytes` and `payload_bytes` were raised to match passed every step and verified as `identical` | Step 17 begins with `cross_check_header`: seven scalar comparisons against the planner, in header declaration order, reported as `R4_PACK_HEADER` naming the field. It runs after step 16 so that a pack verified against an unrelated model still reports `R4_SOURCE_IDENTITY` rather than a geometry defect it would not otherwise have | `header-total-bytes`, `header-name-stream-offset`, `header-name-stream-bytes`, `header-payload-offset`. `scripts/alignpack_reader.py` already rejected the trailing-bytes container as `TRUNCATED`, which is what made the writer's silence visible |
| 2.8 error table, `R4_PACK_HEADER` | Step 13 only | Steps 13 **and 17**; the `error_detail` is still the field name, so the row's shape is unchanged | the four cases above |
| 2.8 step 17 for the three table offsets | — | `block_table_offset`, `member_table_offset`, and `source_record_offset` are compared like the rest, but they cannot be reached by a single-field mutation: the name stream, both tables, the source record, and the payload are laid consecutively, so any relocation collides with a neighbour and step 15 owns it. Each field still gets its own case, asserting the exact region the collision names | `header-block-table-offset`, `header-member-table-offset`, `header-source-record-offset` |
| 2.8, four-operand `--pack` | Unstated | A `write_file` failure on the document path keeps the pack and returns `Err`. Section 2.8's prose now states it | `--pack`'s own path guard refuses an over-long or NUL-bearing document operand before anything is opened (`long-document`, `cli-arity`); the surviving-pack case is stated, not asserted, because forcing a document write to fail after a successful pack needs a filesystem that fails on one path and not the other |
| 2.9, 2.10 Allocation | "Peak is one or two `COPY_WINDOW_BYTES` windows plus the plan" | False for a large model. Peak is dominated by the rendered document, then the `ClaimTable` and `PackPlan` columns; `peak_window_bytes` measures the windows only. Section 2.9's paragraph states the real numbers | measured resident set on the section 6.8 synthetic, below |
| 2.9, 2.8 steps 3–4 | Each packing arm ran `model_ir.build` and discarded the rendered `R1_MODEL_IR` document | `pub fn model_ir.derive_status(borrow t, borrow g, borrow plan, in_code, in_detail) -> Derivation` runs the same ordered checks — geometry, block assembly, coverage, claim tiling, size sum — and renders nothing. `build` and `derive_status` share one `ordered_checks`, so there is still exactly one producer of each rule | `make model-ir-smoke` unchanged, plus a direct comparison of all 142 fixture documents before and after the change: byte-identical |
| 2.6 "counted once" | Stated without its precondition | Section 6.3's fourth bullet states R1's tiling precondition that makes the adjacent duplicate test sound | `make model-ir-smoke`'s claim-tiling oracle, which is the precondition |
| 4.4 `N/A` lines | Four listed, six emitted | All six are listed in section 4.4 and five are asserted exactly by the smoke; the sixth is asserted by the opt-in full-filesystem case | `qualification-skip` |
| 4.4 step order | The occupied-destination refusal ran after the reclaim trap was installed | It runs **before** the trap. The trap removes whatever stands at the pack's path, so the refusal was deleting the artifact it declined to overwrite — found by the new `qualification-skip` unit on its first run | `qualification-skip` asserts the occupied file's bytes survive |
| 4.4 work-tree guard | `pwd` | `pwd -P` for the runner's root, the model, and the temporary directory. A prefix test over logical paths does not refuse a symlink into the repository | stated; the guard's own case (`ALIGN_LLM_ALIGNPACK_TMPDIR resolves inside the work tree`) is asserted with a physical path |
| 7.2 `write-to-full-filesystem` | Recorded unreachable, "a loopback image needs root on darwin" | **Wrong.** `hdiutil create -size 8m -fs "Case-sensitive APFS"` needs no root, and the `ENOSPC` path works exactly as section 2.8 says. The case ships, opt-in behind `ALIGN_LLM_ALIGNPACK_ENOSPC=1`, because attaching and detaching a volume is a machine-visible side effect that does not belong in an aggregate that runs on every change | `write-to-full-filesystem`: `R4_WRITE_FAILED` with `Code@13312`, `destination: REMOVED`, and no surviving pack |

**The measured resident set**, on a synthetic gpt-oss container built from `scripts/gguf_fixture.py`
with 64 layers and 256 experts — 16,514 blocks, 99,139 members, a 268,737,824-byte source and a
315,600,448-byte pack — measured with `/usr/bin/time -l`:

| Arm | Before | After | `peak_window_bytes` | Document |
| --- | --- | --- | --- | --- |
| `--pack` | 456,015,872 | **419,037,184** | 262,144 | 26,817,769 |
| `--pack-verify` | 839,532,544 | **802,340,864** | 262,144 | 26,818,004 |

The discarded `R1_MODEL_IR` render was 92 MB of peak on its own (`--model-ir` on the same container
peaks at 91,963,392 for a 31,885,872-byte document) and its removal is worth 37 MB of the arms'
peak, because the two phases did not overlap and the freed arena is not fully reused. The rest is
the `R4_ALIGNPACK` document and the plan columns, which is what section 2.9 now says.

## 7. Cell-to-case map

Every applicable cell of section 3 and its exact regression. Unless another runner is named the case
is inside `scripts/run-alignpack-smoke`; `reader` means `scripts/alignpack_reader.py`, which the
smoke runs over every positive fixture and against every mutation.

### 7.1 Closed cells

| Section 3 cell | Closing case |
| --- | --- |
| 3.1 Construction, round trip, fixed strides | `drive_positive` writes and `decode_pack` reads every field of every record on 20 fixtures; `reader.check_layout` re-derives `pack_bytes`, `payload_bytes`, and the whole cursor from the records and seeks to individual records to prove `table_offset + i * record_bytes` addressing |
| 3.1 Failure — magic / version / header constants | `bad-magic`, `bad-version-{0,2,4294967295}`, `header_bytes`, `block_record_bytes`, `member_record_bytes`, `source_record_bytes`, `document_schema_version`, `block-align-odd`, `block-align-huge`, `member-align-odd`, `member-align-above-block`. Each asserts the exact code **and** the exact `error_detail` field name, and each is independently rejected by the reader |
| 3.1 Failure — reserved | `flags-hotness`, `flags-prefetch`, `reserved-nonzero`, `prefetch-group-set`, `hotness-rank-set`, `block-reserved`, `member-reserved`, `payload-digest-present`, `payload-digest-reserved` |
| 3.1 Failure — regions / truncation | `region-overlap`, `region-past-eof`, `pack-truncated-{one-byte,header-boundary,mid-payload}`, `declared-size-disagrees` |
| 3.1 Failure — header geometry (section 6.8) | `header-total-bytes` (the pack extended by 4,096 real bytes with `total_bytes` and `payload_bytes` raised to match), `header-name-stream-offset`, `header-name-stream-bytes`, `header-payload-offset` — each asserting `R4_PACK_HEADER` and the exact field name — and `header-block-table-offset`, `header-member-table-offset`, `header-source-record-offset`, each asserting the `R4_PACK_REGION` collision that step 15 reports first |
| 3.1 Malformed — name span / non-UTF-8 | `name-span-past-end`, `pack-name-invalid-utf8`; the reader decodes each span and rejects `NAME` |
| 3.1 Bounded work | `block-limit`, `member-limit` through `src/alignpack_limits_smoke.align`; `decode_header` re-checks both counts before addressing a record |
| 3.1 Endianness | `be-header` — a byte-swapped magic is `R4_PACK_MAGIC`, never silently read |
| 3.1 Generic monomorphization | `N/A`: no generic type or function is declared |
| 3.2 Layer-major order | `block-order-matches-ir`: the pack's `(kind, layer, expert)` sequence is diffed against the `R1_MODEL_IR` document's, per fixture |
| 3.2 Alignment | `reader.check_layout` asserts every block `pack_offset` is `block_align`-aligned and every member `pack_offset` is `member_align`-aligned, on every fixture |
| 3.2 Contiguity | Section 6.3's three exact identities, asserted per block and per model on every fixture, plus the reader's independent merge |
| 3.2 Per-expert contiguity | `expert-block-contiguous`: every gpt-oss `ExpertBlock` has `source_range_count > 1` and `pack_range_count == 1`. **MOE-PREREQ** for real weights |
| 3.2 Padding accounting | `padding-accounting`: `layout.padding_bytes == total_bytes - payload_offset - Σ payload`, cross-checked by the reader, and `total_bytes` equals the last member's end |
| 3.2 Duplication | `tied-embedding-duplicated`: `qwen2-tied` reports `duplicated_bytes > 0` and `qwen2-full` reports `0`; the identity `payload == total_tensor_bytes + duplicated` is `R4_DUPLICATION_MISMATCH` when it fails |
| 3.2 Statistics, both sides, and `by_kind` | `stats-oracle`: the reader recomputes every section 2.6 value with an explicit interval merge and compares against both documents, field by field, including every `by_kind` row |
| 3.2 Overlapping spans | `stats-overlap`: `qwen2-permuted` reports 26 source ranges for 6 blocks and its source span exceeds its payload; nothing is clamped |
| 3.2 Planner bounds | `block-limit`, `member-limit`, `table-too-large`, `name-stream-too-large`, `name-too-long`, `pack-too-large`, each against lowered bounds, each asserting `destination: UNTOUCHED` and that no file was created |
| 3.2 Source range | Every R0/R1 negative fixture through `--pack`, asserting the code passes through verbatim; `R4_SOURCE_RANGE` guards the same property inside the planner |
| 3.3 Construction / descriptor budget / peak allocation | Both handles and every window are bare locals; `peak_window_bytes` is asserted `<= max(data_offset, COPY_WINDOW_BYTES)` per fixture and measured at 5,953,536 on the 4.68 GB model. The **resident set** is measured separately on the section 6.8 synthetic, because `peak_window_bytes` is not it |
| 3.3 Exact copy | `byte-identity`: `--pack-verify` compares every claimed byte, and `reader.check_byte_identity` re-reads both containers and compares again without invoking `--pack-verify` |
| 3.3 Window boundary, final partial window, short read completed | `window-64/65/128/129/4096` through the lowered-window entry point: each pack is byte-identical to the 4 MiB reference and each verifies |
| 3.3 Padding written / not sparse | `padding-is-zero` (`reader.check_padding` reads every unclaimed byte of the payload region) and `pack-not-sparse` (`st_blocks * 512` against the logical size) |
| 3.3 No trailing padding, size assertion | `no-trailing-pad`: the reader requires the last member's end to equal `total_bytes`; the writer asserts its own cursor and then a live `f.len()` |
| 3.3 Destination exists | `dest-exists`: the occupied file's bytes **and** mtime are unchanged, `destination: UNTOUCHED` |
| 3.3 Destination unwritable / directory | `dest-unwritable` (read-only directory; `N/A` under root) and `dest-is-directory` (section 6.5) |
| 3.3 Compare fast path | `compare-fast-path`: `metrics.byte_scan_windows == 0` and `fast_path_windows == windows_compared` on every identical fixture |
| 3.3 One flipped byte | `flip-first-byte`, `flip-last-byte`, `flip-window-boundary`, `flip-across-two-members`, each asserting the exact `<name>@<source_offset>+<delta>` detail, every field of `first_mismatch`, `verdict: "mismatch"`, and exactly one byte-scanned window |
| 3.3 Length disagreement | `compare-length-mismatch`: two windows returning different counts is a fault, never a silent shorter compare — the guard is in `compare_member` and is reached by the truncation corpus |
| 3.3 Padding corrupted | `padding-corrupted`: a nonzero interior padding byte is `R4_PADDING_NONZERO` with its absolute offset, asserted exactly |
| 3.3 Identity | `identity-mismatch`, `identity-file-size`, `identity-digest`: each asserts `comparison.bytes_compared == 0` |
| 3.3 `bytes_read` accounting | `bytes-read-bound`: `payload <= bytes_read <= payload + data_offset + MAX_TABLE_BYTES` and `payload <= bytes_written <= total_bytes`, per fixture |
| 3.3 Early exit | `partial-verify`: `members_compared` equals the index of the failing member on all four flip cases |
| 3.3 Determinism | `repeat-pack`: three packs of one source — twice to one path, once to another — are byte-identical by SHA-256, with no normalization |
| 3.3 Concurrency, shared state | `N/A` with section 3.3's own reasons; `env-perturbation` asserts that five environment variables change neither the pack bytes nor the document bytes |
| 3.4 Behaviour preservation, claim cells | `make model-ir-smoke` re-run unchanged: 49 qwen fixtures, 31 gpt-oss fixtures, 62 R0 fixtures, every `R1_MODEL_IR` document byte-identical; and a direct before/after comparison of all 142 fixture documents across the section 6.8 extraction |
| 3.4 Single producer | `single-producer`: no executable line of `src/alignpack.align` names `member_claim`, `plane_bytes`, `tensor_absolute_offsets`, `tensor_offsets`, `ggml_block_size`, `ggml_type_size`, or `tensor_dim(`, and `member_claim` appears exactly twice in `src/model_ir.align` — its definition and its one caller — and nowhere else in `src/` |
| 3.5 Arity, both forms, summary block, path guard | `cli-arity` (ten argument shapes, each asserting a nonzero exit, empty stdout, and no destination), `form-parity`, `summary-order` (every fixed label of both summary blocks, positionally) |
| 3.5 Failure mapping, selector isolation, architecture dispatch | `error-corpus` exits, `selector-as-operand`, `absent-source`, `absent-pack`; the gpt-oss corpus reaching the MoE frontend is the dispatch regression |
| 3.5 Help text | `usage-diff`: the help block names both new lines verbatim and still names `--model-ir`, `--inspect-gguf`, `--expert-trace`, and `--persist-result` |
| 3.6 Independence, layout invariants, oracle, mutation detection | `scripts/alignpack_reader.py` over every fixture and against 40 mutations, each with `--expect-reject KIND`, which is what proves the reader is not vacuous |
| 3.7 Target definition, aggregate membership, exclusion | `make gate-topology-check` — `alignpack-smoke` is in `HOSTED_CHECK_TARGETS`, `alignpack-qualification` is in no aggregate |
| 3.7 Fixture cleanup, repository safety | The `EXIT` trap, the temp-root assertion, and a full-tree leak sweep comparing the repository before and after the run |
| 3.7 Qualification cleanup and skip | `trap ... EXIT HUP INT TERM` reclaimed 4,677,222,400 bytes on the real run; `qualification-skip` drives the runner through five of the six `N/A` lines of section 4.4 and asserts each exactly, and the opt-in `write-to-full-filesystem` case asserts the sixth |
| 3.7 Preflight profile selection | `python3 scripts/pre-pr --plan` recorded before the run, then `python3 scripts/pre-pr --owner-test alignpack-smoke -- gmake alignpack-smoke` on the exact head, with the required installed profile and no Docker substitution. Recorded in the pull request |
| 3.7 Documentation | `docs/specs/roadmap.md` section R4 and forward-order item 13; `HANDOFF.md`; `docs/align-development.md`'s alignpack section; `docs/align-requests.md` Request 21 and Request 23 client evidence and the section 5.5 candidates; `docs/specs/r1-qwen-model-ir.md` section 7's correction of the section 2.5.6 role-major sentence |

### 7.2 Cells this host cannot reach

Each prints one exact line and never counts as a pass.

| Cell | Line |
| --- | --- |
| 3.3 `cleanup-failed` | `alignpack smoke: cleanup-failed N/A (a destination directory made read-only after fs.create_rw does not make fs.remove fail on this filesystem)` |
| 3.3 `window-unavailable` | `alignpack smoke: window-unavailable N/A (truncating the source between the plan and the copy needs an injection point the arm does not expose)` |
| 3.5 `read-only-source` | Covered by Request 21's client evidence rather than by a case: the arm cannot open a read-only model at all, which is the request, not a behaviour to assert |
| 4.5 MoE on real weights | `alignpack qualification (MoE): N/A - no gpt-oss GGUF on this host` |

**`write-to-full-filesystem` is reachable after all, and this table used to say it was not.** The
claim that "a loopback image needs root on darwin" was wrong: `hdiutil create -size 8m -fs
"Case-sensitive APFS"` needs no privilege, and the case ships. It is **opt-in** rather than default
because attaching and detaching a volume is a machine-visible side effect that does not belong in an
aggregate that runs on every change, and because `hdiutil` does not exist on the hosted Linux
runners. Both paths print one exact line:

```text
alignpack smoke: write-to-full-filesystem N/A (opt-in: set ALIGN_LLM_ALIGNPACK_ENOSPC=1 on a host with hdiutil)
alignpack smoke: write-to-full-filesystem N/A (ALIGN_LLM_ALIGNPACK_ENOSPC is set but this host has no hdiutil)
```

With `ALIGN_LLM_ALIGNPACK_ENOSPC=1` on this host the case mounts an 8 MiB case-sensitive APFS
volume, grows a filler until the filesystem refuses and trims it back by 64 KiB, and asserts that
`--pack` of an 847,424-byte pack reports `R4_WRITE_FAILED` naming the variant and the offset
(`Code@13312`), `destination: "REMOVED"`, and no surviving pack. The same volume closes the
qualification's `insufficient free space` line. Recorded evidence, one run:

```text
alignpack smoke: write-to-full-filesystem PASS (Code@13312)
alignpack smoke: qualification-skip insufficient-free-space PASS
```

Section 4.3's `golden-container-bytes` is **not** shipped as a checked-in hex golden. The three
properties it was meant to protect — field order, record stride, and the reserved values — are each
asserted directly and per field by `scripts/alignpack_reader.py`, which decodes every record at its
declared stride and refuses any deviation, and by the 40-mutation corpus, which fires one named
error per field. A hex golden of one fixture's first 4 KiB would additionally pin the fixture
generator's output, which is not R4's contract.

### 7.3 Align observations

None blocks R4 and none is raised as a register request here; the orchestrator owns
`docs/align-requests.md`. Sections 5.5.1 to 5.5.4 are unchanged and were re-confirmed against the
implementation: the bounded header-region digest is what shipped, `fs.exists` plus `fs.create_rw` is
what shipped, and no durability claim is made. Two further observations are **application concerns**,
not language gaps: an owned aggregate assigned inside a loop body cannot be read after the loop
(section 6.6), and an `array<i64>` is not a mutable accumulator. Both have idiomatic shapes at this
pin — a straight-line chain of early returns and a sweep per bucket — which is why they are recorded
as shapes rather than as requests. Request 21 gains the client evidence section 5.5.4 describes and
Request 23 gains `PackPlan` as its fourth client, both confirmed by the shipped code.
