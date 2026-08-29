# R6-RESIDENT-WEIGHTS

Status: **implemented and measured, 2026-08-29**. Branch `agent/r6-resident-weights`, implemented on
`agent/r6-kv-persist` head `9699848` and then merged with that branch's review repair and its own
merge of `main` (`bdb34eb`, carrying `main` `3df063b` = R6-STEP-N #145 and R5E-MOE-MODEL-PREFILL) by
`git merge` — never a rebase. Sections 1 to 4 and 6 to 10 are the design as it was written
**before** implementation and are unchanged, so that the result can be read against the prediction.
Section 5.8 records what was built and what it measured, section 5.9 records every deviation from
this document with its reason, and section 11 gains the corrections implementation found.

**What "written before implementation" does and does not claim, stated plainly because the
repository holds no evidence for it.** Sections 1 to 4 were authored before any code existed, and
section 11's consistency pass was performed on them at that time — but this file's **first commit is
`ccd4f7e`, the implementation commit**, so nothing in Git distinguishes a ceiling recorded in
advance from one written to fit a result. The one piece of internal evidence is negative and worth
naming: section 3.4's ceiling (586,000 ppm), baseline (18.235 s from R6-STEP-N), and floor
(150,000 ppm) are **byte-identical to the version of the file that carries the measurement**, and
all three are arithmetic on R6-STEP-N's published numbers rather than on anything measured here —
the measurement of record, 412,763 ppm (section 5.8.1's run 4), is not the ceiling, does not equal
it, and sits 30 % below it, and even the highest of the four runs sits 13 % below. A
reader is entitled to treat "recorded before implementation" as an author's statement rather than as
a verified fact, and `HANDOFF.md` records the process correction: **the next Track B performance
capability commits its sections 1 to 4 before the first line of implementation**, so the ordering is
a fact about the repository instead of a claim in a document.

**Amendments to sections 1 to 4.** Those sections are not edited, so a row that the implementation
moved is marked in place with a bolded `Shipped:` note naming the deviation or correction that owns
it. The prediction stays legible and the ledger stays authoritative about what actually ships; the
`Shipped:` notes are the only text in sections 1 to 4 written after implementation.

Stacked on `R6-STEP-N` (`docs/specs/r6-step-n.md`, branch `agent/r6-step-n` head `6ca1eef`), which
is itself stacked on `R6-DECODE-KV-STEP1` (`docs/specs/r6-decode-kv-step1.md`, head `1671810`).
Those two documents are the ledger this one extends; "unchanged" below means unchanged **from
them**, and a row they hold that this document does not restate is still in force.

`R6-KV-PERSIST` is being implemented in parallel on `decode_step.decode_step`/`decode_pass`. This
document does not consume anything it introduces and does not restate anything it owns; section 9
records the merge order and the two places the diffs meet.

## 1. Decision and boundary

### 1.1 What this capability is

R6-STEP-N measured the cost of an N-step decode loop and named the term that dominates it. Its
section 5.4 is the whole motivation, restated here because every number below is calibrated against
it:

| `N` | Elapsed | Decode compute | Pack bytes read |
| --- | --- | --- | --- |
| 1 | 5.313 s | 0.183 s | 8,741,169,024 |
| 4 | 7.367 s | 0.783 s | 21,852,852,000 |
| 16 | 18.235 s | 3.049 s | 74,299,583,904 |

`(74,299,583,904 − 8,741,169,024) / 15 = 4,370,560,992` — **one 4.37 GB pass over the pack per
decode step**, and compute is 3.5 %, 10.6 %, and 16.7 % of elapsed at the three points. More than
four fifths of a sixteen-step run re-reads weights the previous step already read.

This capability removes that term. It makes the pack's weights **resident for the lifetime of one
process**, so that after one fill every decode step reads **exactly zero bytes** of weights from
disk, and prefill reads them once rather than thirty times.

**The headline is how little it needs.** The zero-copy mechanism is already the shipping primary
path, and the exploration in section 2.4 is what settles the boundary rather than an argument:

| Needed by resident weights | State |
| --- | --- |
| A new ggml symbol or shim entry point | **None.** `align_ggml_buffer_from_host` (`scripts/ggml_shim.c:849`, `ggml_backend_dev_buffer_from_host_ptr`) and `align_ggml_slot_place` (`:1162`, `ggml_backend_tensor_alloc`) already point weight tensors at interior offsets of an Align-owned `buffer` |
| A per-step copy of the weights into ggml | **None, and this is the decision.** `src/model_forward.align:1663` already *places* every weight tensor; `slot_set` is used only for activation inputs and for the reference arm |
| A new Align language surface | **None.** Section 8 records four continuing gaps; none blocks this |
| A larger `buffer` than the pin allows | **No.** Section 2.4's probe allocated 4,370,560,992 B at the pin, peak footprint 4,375,700,480 B |
| A change to the KV plane, the node tables, the slot numbering, or the op set | **None** |

What it does need is exactly four things: a **`RESIDENT` operand**, a **sum layout** where
`stage_window` currently takes a maximum, a **hoisted wrap** whose freed-object invariant is
re-established at run scope rather than per graph, and a **memory ceiling with a refusal**.

### 1.2 Why a design gate is triggered

Three of the gate's four triggers fire, and the third is the reason this document exists at all.

- **A changed public CLI surface.** `--decode-step` gains a twelfth operand and its arity set
  changes.
- **A changed exchanged format.** The `R6_DECODE_STEP` document goes to **schema 3**: a `weights`
  object is added and three counters change meaning.
- **A changed ownership/allocation boundary.** This is the load-bearing one. Today the weight
  `buffer`, its `ggml_backend_buffer` wrap, and its three contexts are created and destroyed inside
  `run_graph`/`run_step_graph` — one lifetime per graph, `16 × 30` of them at `N = 16`. This
  capability moves the `buffer` and the wrap to **run scope** while leaving the contexts per graph.
  That splits one lifetime into two with different owners, and `docs/specs/r5c-metal-prefill.md`
  section 5.4 already refused the same hoist once, for a reason this document must answer rather
  than repeat:

  > "hoisting the wrap out of the per-graph loop removes the per-layer buffer free that R5B's
  > window-reuse invariant asserts, and section 2.6 has just established that on Metal an unfreed
  > buffer aborts the process. The optimization is real, measured, and belongs in the capability
  > that also re-establishes the invariant it weakens."

  This is that capability. Section 4.3 re-establishes the invariant at the scope the hoist moves it
  to, and section 1.3 keeps the Metal arm out of scope so the abort R5C measured stays unreachable.

The fourth trigger — a coordinated invariant across three or more modules — is recorded as **not
fired**: the change touches `src/decode_step.align`, `src/model_forward.align`, and two scripts, and
the invariant those must agree on (the arena's layout and the per-graph base offsets) is created
here and owned by one module. A closure matrix is built anyway, in section 5, because a lifetime
that is split across two scopes is exactly what a closure matrix is for.

### 1.3 Declared boundary

**In scope.** Dense Qwen2.5-Coder-7B Q4_K_M; **CPU only**; the `--decode-step` arm; one process;
weights resident from before prefill until the process's own teardown, filled once, never evicted,
never invalidated, never persisted; an explicit memory ceiling and a refusal above it.

**Out of scope, declared non-goals.**

- **The Metal arm.** `--model-forward-gpu` keeps the per-graph wrap and the per-graph free,
  unchanged, because R5C section 2.6 measured that an unfreed Metal buffer aborts the process at
  `exit`. The hoist is guarded by the arm, not by a runtime device check.
- **`--model-forward` and `--moe-layer-forward`.** They pay the streaming cost once, not `N` times,
  so the ceiling in section 3.4 does not clear the floor for them. Section 7 defers them with that
  reason.
- **Eviction, tiering, prefetch, NVMe or GPU residency, a partial-residency policy.** Residency here
  is all-or-nothing for one pack in one process. Anything that chooses *what* to keep is
  `align-runtime` work and needs its own capability.
- **Resident KV.** `R6-KV-PERSIST` owns the plane. The plane is already resident by construction
  (R6 section 2.4) and this document changes nothing about it.
- **A shared or persisted weight cache across processes**, memory-mapped weights, and any use of
  `mmap`. Section 2.5 records why the OS page cache is rejected as a *claim* even though it is
  demonstrably already doing work.
- **Any tokens-per-second or TTFT claim.** This document makes a **bytes-read** claim and a bounded
  **elapsed** claim on one prompt on one host. Section 3.4 states both exactly.
- **A growing pack, a second pack in one process, or reuse of the arena across two `--decode-step`
  invocations.**

## 2. The boundary decision

The task named three candidate boundaries and asked for one. This section decides, with the
measurements that decide it.

### 2.1 The three candidates

| Candidate | What is resident | Per-step cost of weights |
| --- | --- | --- |
| **A — one Align-owned arena, tensors placed into it** (**chosen**) | Every weight member the run touches, in one `buffer`, wrapped once as one `ggml_backend_buffer` | **0 B read, 0 B copied.** Each graph creates its tensors in its own `no_alloc` context and `slot_place`s them at arena offsets |
| B — per-layer resident slices, uploaded to ggml once per step | The same bytes, in `n_layer + 2` separate buffers | 4.37 GB of `memcpy` per step, plus 30 allocations that Request 39's rebind retention makes expensive |
| C — rely on the OS page cache | Nothing this process owns | 4.37 GB of `pread` per step, unchanged; only the disk read is avoided |

### 2.2 Why B is rejected — measured, not asserted

B is the design the task's question describes: keep the bytes in an Align buffer and `slot_set` them
into each graph's ggml-owned tensors. Its cost is one 4.37 GB host copy per step. That was measured
on this host rather than estimated:

```text
$ cc -O1 -o m2 m2.c && ./m2          # 2 GiB memcpy, six iterations, Apple M1, 16 GiB
memcpy 2147483648 B in 0.1253 s -> 17.14 GB/s   (first, cold destination)
memcpy 2147483648 B in 0.0733 s -> 29.31 GB/s
memcpy 2147483648 B in 0.0764 s -> 28.09 GB/s
memcpy 2147483648 B in 0.0725 s -> 29.64 GB/s
memcpy 2147483648 B in 0.0725 s -> 29.62 GB/s
memcpy 2147483648 B in 0.0722 s -> 29.73 GB/s
```

**29.6 GB/s warm**, so 4,370,560,992 B is **0.148 s per step**. Against the streamed baseline's
0.86 s per step that is a 5.8× improvement — a real win, and **it is still the wrong design**:

- It is 0.148 s per step worse than A, which pays nothing, and the gap grows linearly with `N`.
- It needs `n_layer + 2` live buffers or one arena plus a copy; the first shape is exactly the
  allocation pattern Request 39 measured at a 6.8–8.5× resident-set inflation
  (`docs/specs/r5b-model-prefill-forward.md` section 6, correction C6).
- It abandons a property the code already has. `scripts/ggml_shim.c:1168` states it plainly: "the
  primary arm places its thirteen at interior offsets in the Align window and never writes one."
  B would make weights ggml-owned for the first time since R4.5 and would delete
  `graph_identity`'s pointer-identity oracle (`src/model_forward.align:1672`), which is the check
  that proves the placement really happened.

B is therefore recorded as the **honest alternative that a copy-based residency would cost**, and
its number, 0.148 s per step, is the one that makes A's zero legible.

### 2.3 Why A is expressible today — the shim inventory

The question "does the shim expose a way to back a ggml tensor with a persistent host buffer, or is
a new FFI wrapper needed" is answered **no new wrapper**. The two symbols that matter already ship,
and the primary weight path already uses both:

| Align wrapper | C implementation | Semantics |
| --- | --- | --- |
| `ggml_ffi.buffer_from_host(device, region, size)` (`src/ggml_ffi.align:500`) | `align_ggml_buffer_from_host` (`scripts/ggml_shim.c:849`) → `ggml_backend_dev_buffer_from_host_ptr` | **Borrow.** Wraps an Align-owned byte range as one `ggml_backend_buffer_t`; validates 32-byte alignment and returns a status instead of letting `GGML_ASSERT` abort |
| `ggml_ffi.slot_place(handle, slots, index, addr, label)` (`:727`) | `align_ggml_slot_place` (`:1162`) → `align_ggml_tensor_place` (`:904`) → `ggml_backend_tensor_alloc` | **Borrow.** Points `tensor->data` at a chosen interior address, with the same alignment pre-check |

`align_ggml_context_open` (`:819`) is already `no_alloc = true` unconditionally, which is the
precondition `ggml_backend_tensor_alloc` needs. `ggml_backend_cpu_buffer_from_ptr` is **not** called
and is not wanted: R4.5 section 2.1 records that it hard-codes the CPU and skips the device
capability check, which is why the registry path was chosen instead.

So the only thing standing between the current code and residency is that the Align `buffer` holding
the weights is sized to the **peak graph** (447,082,496 B, the head) and refilled per graph, rather
than sized to the **sum** and filled once.

### 2.4 Why A is allocatable at the pin — the probe

Request 33 and Request 35 make two claims about `buffer` that had to be checked before a 4.4 GB one
was designed around: allocation failure is unobservable (35), and `pread` requests the buffer's whole
capacity (38). One probe was run, at the pinned compiler
`3a34febe912db5096c58c74fede36ff53f223e04`, against the real
`qwen2.5-coder-7b-instruct-q4_k_m.gguf` (4,683,073,536 B).

The probe program allocates `buffer(TOTAL)` and fills it two ways: one whole-capacity `pread`, and
`CHUNK_BYTES`-sized `pread`s appended in order. It reports the published length and the elapsed
time, and it was run under `/usr/bin/time -l`.

**Result 1 — a single whole-pack `pread` is refused by the platform.**

```text
$ ./r6w_probe MODEL.gguf 4370560992 0
mode: single
pread: ERROR
        0.37 real   1556480 maximum resident set size

$ ./r6w_probe MODEL.gguf 2147483647 0        # INT_MAX
mode: single
requested: 2147483647   count: 2147483647   len: 2147483647   ns: 482214208

$ ./r6w_probe MODEL.gguf 2147483648 0        # INT_MAX + 1
mode: single
pread: ERROR
```

The boundary is **exactly `INT_MAX`**: Darwin's `pread(2)` refuses `nbyte >= 2 GiB` with `EINVAL`.
Since `align_rt_io_file_pread` always requests `b.cap` (Request 38), a `buffer` at or above 2 GiB
**cannot be filled by one `pread` at this pin on this platform**, and the failure is a returned
error rather than a short read. This is a fact about the design, not a defect: the arena is filled
in `CHUNK_BYTES` rounds, which is what `read_into_window` already does.

**Result 2 — a 4.37 GB `buffer` is allocatable, and the whole pack fits in it.**

```text
$ /usr/bin/time -l ./r6w_probe MODEL.gguf 4370560992 1048576
mode: chunked
requested: 4370560992   chunk: 1048576   reads: 4169
have: 4371513344        len: 4371513344   ns: 2064500375
        2.29 real  0.17 user  1.34 sys
        3128000512  maximum resident set size
        4375700480  peak memory footprint
        267124      page reclaims        0 swaps
```

Read straight: **`len()` published 4,371,513,344 B** — the reservation held, the appends stayed
inside it, and the peak memory footprint of 4,375,700,480 B is the arena plus the runtime. The fill
took **2.06 s at 4,169 `pread`s**, or 2.12 GB/s, from a partly cold page cache. A second run
measured 2.13 s.

Two secondary readings matter and are carried into the risks rather than dropped:

- **Max RSS (3,128,000,512 B) is below the footprint (4,375,700,480 B).** The measuring host was
  under real memory pressure — `vm_stat` reported an active compressor — so roughly 1.25 GB of the
  arena was compressed rather than held. Residency on a host in that state is partly virtual, and
  the elapsed claim in section 3.4 must report the compressor state or be taken on a quiet host.
  Risk 3.
- The first run of the same probe reported max RSS 1,436,729,344 B for the identical footprint. Max
  RSS is therefore **not** the metric; peak memory footprint is.

**What the probe does not settle**, and is named rather than assumed: whether
`ggml_backend_dev_buffer_from_host_ptr` accepts a 4.68 GB range, and whether tensors created in
*different* contexts may be placed into one buffer. Both are answered by the first implementation
step (section 5.7, cell RW-P1), which is a three-line extension of R4.5's `probe1.align`, and both
are risk 1.

### 2.5 Why C — the OS page cache — is rejected

Not because it does not work. **Because it already works, and the measurement shows that is not
enough.**

The streamed baseline reads 4,370,560,992 B per step in 0.86 s, which is **5.08 GB/s**. The probe
above measured 2.12 GB/s for a partly cold fill of the same bytes on the same host. The steady-state
decode loop is therefore already being served by the page cache at more than twice the cold rate,
and it still costs 83 % of a sixteen-step run's elapsed time. What residency removes is not the disk
read — the kernel already removed most of that — it is **4,169 syscalls and 4.37 GB of copying per
step**.

Three further reasons, in the terms `CLAUDE.md` uses:

1. **It is not a claim this repository owns.** Residency-by-page-cache has no surface, no operand,
   no counter, and no refusal. Its behaviour depends on the host's free memory, on every other
   process, and on an eviction policy this repository cannot observe, pin, or reproduce. A
   performance claim needs a reproducible baseline; "the kernel usually keeps it" is not one.
2. **It would make the metric meaningless.** Section 3.4's primary metric is pack bytes read per
   decode step, taken from a counter this arm publishes. Under C that counter stays at
   4,370,560,992 forever and the improvement is invisible to the document — which is precisely the
   situation R6-STEP-N is in today.
3. **`mmap` is the same rejection with a sharper edge.** It would hand ownership of the weight bytes
   to the kernel, make `pointer_identity_failures` a statement about a mapping rather than about an
   Align allocation, and reintroduce a page-fault cost inside `ggml_backend_graph_compute` where no
   counter can see it. `scripts/ggml_shim.c` calls no `mmap` today and this capability does not add
   one.

C is recorded here as the **rejected candidate with its reason**, per `docs/review-checklist.md`'s
requirement that a ledger name the alternatives it did not take.

### 2.6 The decision

**Candidate A.** Resident weights are **one Align-owned `buffer`**, sized to the sum of every weight
member the run touches, filled once in `CHUNK_BYTES` rounds, wrapped once by
`ggml_ffi.buffer_from_host`, and read by every graph through `ggml_ffi.slot_place` at arena offsets.
Per decode step: **0 pack bytes read, 0 weight bytes copied.**

## 3. Public-contract ledger

Fields marked `N/A` carry their reason. Rows R6 and R6-STEP-N settled are restated only when they
change.

### 3.1 The arm and the new operand

> **Shipped: `RESIDENT` is `args[13]` and the arity set is `{5, 6, 7, 9, 10, 11, 12, 13, 14}`.**
> `R6-KV-PERSIST` took `args[11]` and `args[12]` for `KV_SAVE`/`KV_LOAD` before this capability was
> implemented, so the operand moved from the twelfth position to the **fourteenth**; 8 is still
> `R6_ARITY` and **15** and above are `R6_ARITY`. Section 5.9 deviation 5 owns this. The grammar
> line below therefore reads `… STEPS KV_SAVE KV_LOAD RESIDENT`.

| Field | Contract |
| --- | --- |
| Surface | `ggml-spike --decode-step` — unchanged; the first operand and nothing else selects the arm |
| Owner module | `src/decode_step.align`. `src/ggml_spike.align` is **byte-unchanged**: the dispatch arm forwards `args` and does not enumerate arity |
| Operand grammar | `--decode-step PACK GEOMETRY TOKENS DOCUMENT REFERENCE TRANSCRIPT KV_WIDTH LOGITS STEPS RESIDENT` |
| Arity | `args.len()` of 5, 6, 7, 9, 10, 11, or **12**. **8 remains `R6_ARITY`** for R6's own reason (a transcript without a width refuses itself). 13 and above are `R6_ARITY` |
| Operands 1–10 | Unchanged from R6-STEP-N sections 2.2 and 2.3 |
| `RESIDENT` | `args[11]`. **`-` means streaming**, the shipped behaviour, and is the default when the operand is absent. **`weights` means the whole weight set is resident.** Any other value, including the empty string, is `R6_RESIDENT` with detail `resident[<text>]` bounded to 256 bytes by `bounded_detail` |
| Defaults | One, and it is the same shape R6-STEP-N recorded for `STEPS`: absent is `-`. Its hazard — a caller who wants residency and forgets the operand silently gets streaming — is closed by publishing `weights.mode` in **every** document, including error documents |
| Why an operand and not an environment variable | `docs/review-checklist.md` requires CLI, build, option, and environment inputs to be explicit and isolation tested in both directions. An environment variable would be a second, untested input path into an arm whose every other input is positional, and `scripts/run-decode-step` would have to pass it through a `trap`-cleaned subshell. `TRANSCRIPT` and `LOGITS` established the `-` convention; `RESIDENT` inherits it |
| Why a value rather than a flag | `weights` names *what* is resident. A later capability that also holds the plane or the activations across steps extends the value set (`weights+kv`) without changing the arity or the grammar. A boolean would have to be replaced |

### 3.2 The arena — layout, ownership, and lifetime

This is the ownership/allocation boundary the design gate fired on. Every field is exact.

> **Shipped: three rows below moved.** The arena is **4,677,533,696 B**, not 4,677,184,512 B — the
> draft omitted that every region starts at the container's `block_align` of 4,096 (section 11.1
> correction 7), and the headroom against `MAX_WINDOW_BYTES` is 45.6 % rather than 46 %. The layout
> is computed by a **new** function, `model_forward.plan_resident`, and not by a resident branch
> inside `stage_window`, which is byte-unchanged (section 5.9's `What was built` table). And
> `R6_RESIDENT_BUDGET` is therefore raised in `decode_step.execute` before `buffer(...)`, still
> **before any allocation**, which is the property the row is actually about.

| Field | Contract |
| --- | --- |
| What it is | One `buffer` local in `decode_step.execute`, over-reserved by `model_forward.MAX_TENSOR_ALIGNMENT` (64) exactly as the streamed window is, with the interior slice starting at the first 32-byte boundary (`base_mod`, `src/model_forward.align:327`) |
| Who allocates | `decode_step.execute`, once, after geometry and before `backend_open`. In streaming mode nothing changes and the existing per-graph window is allocated as today |
| Who frees | The owning frame, at `execute`'s exit, after the run-scope wrap is freed. There is no path on which the arena outlives its wrap; section 5.3 is the closure cell |
| Layout | `[pad][token_embd.weight][embed stage][layer 0 … layer n_layer−1][head]`, each member starting at `align_up(offset, block_align)` exactly as `plan_layer_members` already computes within a graph (`src/model_forward.align:1197`) |
| Size on the reference model | 306,561,024 (`token_embd.weight`, the full table) + 64,512 (embed stage) + 3,923,476,480 (28 layers) + 447,082,496 (head) = **4,677,184,512 B**, plus at most 64 B of base pad and at most `339 × 31` B of member pad |
| Budget | `resident_bytes <= model_forward.MAX_WINDOW_BYTES` (8,589,934,592), the **existing** constant and the existing idiom. 4.68 GB leaves 46 % headroom on the reference model |
| Refusal above the budget | `R6_RESIDENT_BUDGET`, detail `bytes[<n>]`, raised in `stage_window`'s resident branch **before any allocation** |
| Refusal on a degraded reservation | `R6_RESIDENT_UNAVAILABLE`. Request 35 makes allocation failure unobservable, so the check is on the **observable consequence**, exactly as `R4_WINDOW_UNAVAILABLE` is: after priming and filling, `weights.bytes().len()` must equal `pad + resident_bytes`. This is the same guard `src/model_forward.align:3501` already applies to the streamed window |
| What it cannot refuse | **A genuine out-of-memory host.** `buffer(cap)` degrades to `cap = 0` silently and `append` grows through Rust's infallible, abort-on-OOM path (Request 35, sibling evidence at `crates/align_runtime/src/lib.rs:10090` and `:10186`). A host that cannot hold 4.68 GB **aborts the process** rather than producing a document. This is stated, not hidden; section 3.6 is the whole answer and section 8 records it as Request 35's second client |
| Lifetime relative to graphs | The arena and its wrap live for the **whole run**; the three ggml contexts and every tensor stay **per graph**. Tensor objects are cheap (`ggml_tensor_overhead()` each) and recreating them per graph is what keeps `MAX_NODE_SLOTS` and the node tables unchanged |
| Mutation after fill | **None.** The arena is written once, by the fill, and is read-only for the rest of the run — except the 64,512-byte embed stage (section 3.3), which is rewritten per graph. Every other byte is immutable, which is what makes one wrap safe across 480 graphs |

### 3.3 The embedding row, and why "zero bytes" is exactly true

The one weight read that is *not* a fixed member is the embedding row gather:
`fill_members` reads `pieces` rows of `stride` bytes at `m.pack[at] + tokens.ids[piece] * span`
(`src/model_forward.align:2412`), so its source offset depends on the token. At 6 tokens that is
12,096 B; per decode step it is one row, 2,016 B.

2,016 B per step is not zero, and a claim of "zero bytes read per step" that quietly excluded it
would be false. The arena therefore holds **the whole `token_embd.weight` table**, 306,561,024 B,
and the gather becomes a host copy out of resident memory into a small staging region:

| Field | Contract |
| --- | --- |
| Embed stage | A dedicated arena region of `MAX_PREFILL_TOKENS × row_bytes` = `32 × 2,016` = **64,512 B**, at a fixed arena offset |
| How it is written | `ggml_ffi.window_copy(arena_view, stage_offset + i × row, arena_view, row, "embd")` — the existing bounded `memcpy` shim entry (`scripts/ggml_shim.c:422`), source and destination both inside the arena. No `pread` |
| Cost per decode step | **2,016 B copied, 0 B read.** At the measured 29.6 GB/s that is 68 ns |
| Cost per prefill | `T × 2,016 B`, at most 64,512 B |
| Why a copy and not a placement | The rows a graph gathers are non-contiguous in the table for `T > 1`, and a ggml tensor is one contiguous range. At `T = 1` a placement would work and the copy would be avoidable; one code path for both is worth 68 ns per step and is one fewer branch in the closure matrix |
| Why not `ggml_get_rows` over the resident table | It would change the graph, the node tables, and every oracle node index, for the same 68 ns. Deferred, section 7 |

**So the claim is exact:** in resident mode a decode step reads **0 bytes** from the pack and copies
**2,016 bytes** of host memory. Both numbers are published (section 3.5) rather than argued.

### 3.4 The performance claim — baseline, ceiling, floor, and metric

`CLAUDE.md`'s Performance-claim row applies, so the cost ceiling is recorded **here, before
implementation**, and the owning performance document is named.

**Who owns decode performance.** `docs/specs/c8-speed-first.md` section 1 says in its first sentence:
"C8 optimizes time to a passing patch, **not model tokens per second** or an isolated helper call."
Its 2,000 ppm floor is calibrated on a ~46 ms coder fixed task and has no relationship to a
multi-second decode loop. **No document owns Track B decode-time performance. This document becomes
that owner**, and section 3.4's floor is the first entry in it. A later Track B performance
capability records its ceiling against the baseline and floor defined here, or replaces them with
reasons.

**Baseline.** R6-STEP-N section 5.4, one prompt (`def add(a, b):`, `T = 6`), `KV_WIDTH` 256, no
transcript, no logits blob, on the reference host (Apple M1, 8 cores, 16 GiB). Re-taken on the same
host in the same session before the measured result is claimed, three runs, because section 5.4's
own note records that an earlier run of the same head gave 0.73 s per step against 0.86 s.

| Quantity | Baseline value | Source |
| --- | --- | --- |
| Elapsed at `N = 16` | **18.235 s** | 5.4 |
| Elapsed at `N = 4` / `N = 1` | 7.367 s / 5.313 s | 5.4 |
| Decode compute at `N = 16` | 3.049 s (16.7 %) | 5.4 |
| Pack bytes read, total at `N = 16` | 74,299,583,904 | 5.4 |
| Pack bytes read, marginal per step | **4,370,560,992** | 5.4, exact and identical across both runs |
| Fitted fixed cost / marginal wall per step | ≈ 4.5 s / ≈ 0.86 s | 5.4 |
| Run-to-run spread of the marginal term | 0.86 s vs 0.73 s per step on identical bytes | 5.4 |

**Primary metric — exact and noise-free.** `weights.step_pack_bytes`, the pack bytes read by the
decode steps alone. Baseline `15 × 4,370,560,992 = 65,558,414,880` at `N = 16`; **target exactly
0**. This is a counter, not a clock, and it is identical across runs, which is why it carries the
claim.

**Secondary metric — elapsed.** Elapsed at `N = 16` on the reference prompt, three runs, median
reported with the spread.

**Cost ceiling, recorded before implementation.** Of the 18.235 s at `N = 16`:

```text
  18.235 s   elapsed
−  3.049 s   decode compute, which residency does not touch
−  4.500 s   fitted fixed cost, which residency still pays (as the one-time fill)
= 10.686 s   removable
```

**Ceiling = 10.686 / 18.235 = 586,000 ppm** of the `N = 16` fixed task. Predicted result ≈ 7.6 s
elapsed. Both numbers are estimates recorded in advance so that a measured result far below them is
reported as a **ceiling-estimation miss**, per `docs/specs/c8-speed-first.md` section 1's rule,
which this document adopts unchanged.

> **Shipped: "far below" is one half, and the threshold is stated rather than left to a reader.**
> C8's rule says "far below" and its only worked precedent is its ninth capability — 10,793 ppm
> against a roughly 26,000 ppm ceiling, "more than twice", or 41 % of it. The first implementation's
> runner printed the miss for **any** shortfall at all, which would have labelled an estimate that
> was 70 % right the same way it labels one that was 41 % right, and that is the distinction the
> rule exists to draw. `scripts/run-decode-step` now prints the ceiling comparison on every run —
> a reader should never have to go and find the ceiling to know how the result sits against it — and
> applies the **miss** label only below one half of the recorded ceiling
> (`CEILING_MISS_NUMERATOR / CEILING_MISS_DENOMINATOR`). The measurement of record, 412,763 ppm, is
> 70 % of the ceiling and is therefore **not** a miss; the shortfall is the one-time fill, which the ceiling
> assumed away, and section 5.8.1 states it as a shortfall with its cause.

**Shipping floor — 150,000 ppm of the `N = 16` elapsed on the reference prompt.** Calibrated from
this wave's own measured spread rather than chosen in advance, exactly as C8's floor was:
STEP-N measured 0.86 s and 0.73 s per step **on identical byte counts**, so run-to-run noise in the
marginal term alone is `0.13 × 16 = 2.08 s`, or **114,000 ppm** of the baseline. A floor below the
noise cannot be measured. 150,000 ppm sits just above it; the recorded ceiling is 3.9× the floor.

**Measurement risk.** Three, and they are why the primary metric is bytes:

1. **Page-cache state dominates the streamed baseline.** 4.37 GB in 0.86 s is 5.08 GB/s, which is
   page-cache bandwidth, not disk; the probe measured 2.12 GB/s cold. A baseline taken on a cold
   cache would flatter residency. Mitigation: the baseline and the result are taken back to back,
   in one session, on one host, with the pack already read once.
2. **The measuring host compresses memory under pressure** (section 2.4, 1.25 GB of a 4.37 GB
   footprint compressed). A resident arena that the OS compresses is not resident. Mitigation:
   `vm_stat`'s compressor counters are recorded before and after each run and reported with the
   result; a run whose compressor activity moved materially is discarded and retaken.

   > **Shipped: reported, never discarded, and the difference matters.** The runner records the
   > compressor counters around every timed run and **prints the movement with the result**. It does
   > not discard or retake anything, and no implementation of "discard and retake" was written. That
   > is deliberate rather than an omission — a mitigation that silently drops the runs it dislikes
   > is a filter on the measurement, and this host compresses on *every* run large enough to matter,
   > so the rule as drafted would have discarded the honest data rather than the anomalous data.
   > What ships instead is the whole distribution: three repeats per point with the spread printed,
   > four full qualification runs reported with their individual ppm figures (section 5.8.1), and
   > the primary metric being a byte counter the compressor cannot move. Read the drafted sentence
   > as "recorded and reported", which is what the runner does.
3. **`N = 16` is one point on one prompt.** Mitigation: the byte metric is reported at
   `N ∈ {1, 4, 16}` as STEP-N did, and it is exact at all three.
4. **Shipped, and the design did not predict it: leg order and thermal state.** The first
   implementation took all three streamed repeats at an `N` and then all three resident ones, so the
   leg was confounded with the clock. Every mechanism that drifts monotonically over a
   twenty-minute qualification on an unfanned M1 — package temperature and the frequency ceiling it
   sets, the page cache filling, the compressor starting work — moves the second block relative to
   the first, and **the whole of that movement lands on the resident leg's side of the
   subtraction**. The mitigation is to remove the confound rather than to argue about its sign:
   `scripts/run-decode-step` now **interleaves** the legs (`repeat` outside, `mode` inside), so any
   monotone drift is common to both legs to first order, and section 5.8.1's run 4 is the
   interleaved re-measurement at the repair head. **What that run establishes is that the confound
   is gone — not how large it was.** The interleaved result landed 37,016 ppm below the lowest
   blocked run and 98,362 ppm below the highest, a range comparable to the blocked runs' own
   61,346 ppm spread; with `n = 1` interleaved run its distance from them is **not separated from
   this host's noise**, so no order effect of any particular magnitude is claimed. What can be said
   is negative and is said: **the direction this row argued from thermal drift was not confirmed.**
   Section 5.8.1 states the numbers. A second, unmitigated clause stands recorded: **every run in
   this document was taken on one machine in one thermal environment**, and nothing here establishes
   the result on a fanned host, on a host with more memory, or on a Linux page cache.

### 3.5 The document — schema 3

> **Shipped: schema 4, and a `weights` object of nine fields.** Section 9.4 named the condition and
> it held — `R6-KV-PERSIST` merged first and took 3 (section 5.9 deviation 6) — and the object
> publishes `resident_wraps_created`/`_freed` in addition to the seven rows below (section 11.1
> correction 8). Read every "3" in this table as **4**.

| Field | Contract |
| --- | --- |
| Schema | `schema` becomes **3**. `scripts/decode-step-golden.jsonl` is rewritten, on R6-STEP-N section 2.1's recorded exemption: it is this capability's own file, created by R6 and consumed by nothing else |
| `weights.mode` | `"stream"` or `"resident"`. Present in **every** document including error documents, so the mode is never implicit |
| `weights.resident_bytes` | The arena's interior size, or 0 in streaming mode |
| `weights.fill_ns`, `weights.fill_pread_count`, `weights.fill_bytes` | The one-time fill. 0 in streaming mode |
| `weights.step_pack_bytes` | Pack bytes read by decode steps only — the primary metric. Exactly 0 in resident mode |
| `weights.wrap_count` | 1 in resident mode; `graphs × (N + 1)` in streaming mode, unchanged in meaning |
| `pack.bytes_read`, `pack.pread_count` | Unchanged in meaning: totals over the whole run. In resident mode they equal the fill's own figures |
| `pointer_identity_failures` | Unchanged field, **new reach**: in resident mode every one of the 339 placements is against the arena. A non-zero value means a tensor did not land where the layout said, and it is the free structural oracle for the whole design |
| `normalize` | Zeroes `weights.fill_ns` in addition to everything R6-STEP-N section 2.9 already zeroes. `weights.fill_pread_count`, `weights.fill_bytes`, `weights.resident_bytes`, and `weights.step_pack_bytes` are **not** normalized: they are deterministic and are the claim |
| Path-valued fields | None added. The "temp-path golden" failure class stays inapplicable |

### 3.6 The memory ceiling, and what happens on a small host

Stated plainly, because the honest answer is not a clean refusal.

| Host | Behaviour |
| --- | --- |
| ≥ 12 GiB free, `RESIDENT=weights` | Resident. Measured footprint on the reference model ≈ 4.68 GB of arena plus ggml's activations plus the plane |
| Any host, `RESIDENT=-` or absent | **Streaming, unchanged.** The shipped behaviour is the default and no host regresses |
| A pack whose weight sum exceeds 8 GiB | `R6_RESIDENT_BUDGET` before any allocation. A document, not a crash |
| An 8 GiB host, `RESIDENT=weights` | **The process aborts** inside the runtime's `Vec` growth. `buffer(cap)` cannot report a failed reservation (Request 35) and `append` cannot fail. This is the one input for which this arm does not produce a document |

**Three consequences are taken rather than argued around.**

1. **Residency is opt-in and stays opt-in**, precisely because the failure mode is an abort. A
   default-on residency would turn a working streamed run on a small host into a crash.
2. **The host check lives in the runner, not in the arm.** `scripts/run-decode-step` already refuses
   to start unless the scratch root has the pack's size plus 2 GiB free; it gains a physical-memory
   preflight (`sysctl -n hw.memsize` on Darwin, `/proc/meminfo` `MemTotal` on Linux) and prints one
   explicit `N/A` line naming physical memory when the host has less than **12 GiB**, exactly as it
   does for a missing model or instrument. It never skips silently.
3. **The arm cannot make that check itself**, because Align has no host-memory inquiry. Section 8
   records that as a new capability request and records why it is non-blocking: the check has a
   correct home in the runner, and the operand is opt-in.

### 3.7 Prerequisites

| Prerequisite | State |
| --- | --- |
| Everything R6, R6-STEP-N, and R6-KV-PERSIST list | Unchanged |
| `R6-STEP-N` merged, or this branch stacked on its head | **Stacked** on `6ca1eef` |
| `R6-KV-PERSIST` | Section 9. Not a prerequisite; a merge-order constraint |
| A host with ≥ 12 GiB physical memory for the resident leg | **New.** Section 3.6; the runner prints one `N/A` line and exits 0 below it |
| Align language features | None new. Section 8 records five gaps; none blocks |

## 4. Oracles

The correctness oracle for this capability is **free**, and that is the strongest argument for the
boundary in section 2.6.

### 4.1 Oracle R — resident/streamed document equality

Run the same invocation twice, once with `RESIDENT=-` and once with `RESIDENT=weights`, and compare
the two normalized documents.

| Field | Contract |
| --- | --- |
| Assertion | Byte-identical after `normalize`, **excluding the `weights` object and `pack.pread_count`/`pack.bytes_read`**, which are the things that are supposed to differ |
| What it covers | Every decoded token id, every per-step oracle result, every plane figure, every round-trip byte count, the head's logits, and every error code and detail |
| Why it cannot pass vacuously | The excluded set is three fields and one object, enumerated in the runner rather than pattern-matched. Everything else — including `steps[i].token_id` for every `i`, which is what gate G is about — is compared. A document with a non-empty `code` compares its code and detail too, so a resident run that failed would not silently match a streamed run that succeeded |
| Cost | One extra `--decode-step` run per prompt. Section 6 costs it |

### 4.2 Oracle P — pointer identity, existing and newly load-bearing

`graph_identity` (`src/model_forward.align:1672`) already compares
`ggml_ffi.slot_data_offset(slots, at, window)` against `m.window[at]` for every placed tensor and
counts `pointer_identity_failures`. In resident mode the comparison is against the arena base and
the arena offsets, so **339 placements per graph pass assert that ggml is computing out of the
resident arena**. `pointer_identity_failures == 0` is the assertion; a resident run that silently
fell back to a copy could not satisfy it.

### 4.3 Oracle B — the balance invariant, re-established at run scope

This is the invariant R5C section 5.4 said the hoist would weaken, and it is re-established rather
than deleted.

> **Shipped: the run-scope row asserts balance, and "exactly one" only on a successful run.**
> `resident_wraps_created == resident_wraps_freed == 1` is right for a run that completes and wrong
> for one that fails before the wrap exists — it reports a leak on a teardown that was in fact
> perfect. The shipped condition is
> `created != freed || created > 1 || (code is empty && created != 1)`, which is this row on a
> successful run and pure balance on every other. Section 11.1 correction 12 owns it, and
> `ds-force-resident-wrap` is its regression.

| Scope | Assertion |
| --- | --- |
| Per graph, streaming mode | Unchanged: `ggml_buffers_created == ggml_buffers_freed`, `contexts_created == contexts_freed`, `gallocrs_created == gallocrs_freed`, checked at `src/model_forward.align:3959` and `src/decode_step.align:1509` |
| Per graph, resident mode | The same three, over the objects that are still per graph. The run-scope wrap is counted in a **separate pair**, `resident_wraps_created` / `resident_wraps_freed`, so the per-graph check keeps its exact meaning instead of being loosened |
| Run scope, resident mode | `resident_wraps_created == resident_wraps_freed == 1`, asserted after `backend_close` and before the arena's frame exits |
| Ordering | The wrap is freed **before** the arena, on every exit path including every failure path. Section 5.3 is the closure cell and it converges on one teardown, as R4.5 rule 2 requires |

### 4.4 The existing gate and oracles are unchanged

Gate G (token ids against `llama-eval-callback --temp 0 -s 0`), oracle A′ (the transcript), oracle B′
(the byte-plane self-reference), and oracle C′ (`--model-forward` checkpoints) are unchanged and are
re-run on the **resident** leg, not only on the streamed one. Oracle R above means a passing streamed
leg plus a passing oracle R implies a passing resident leg for every field either checks; the gate is
still run against the resident document so that the claim is direct rather than transitive.

### 4.5 The goldens

> **Shipped: schema 4, 116 rows, and the "no other golden moves" prediction held for all six.**
> Section 5.9 deviation 6 owns the schema number; the row count is 107 -> 115 at the implementation
> head and 116 after the review repair added one forced case. The final review's
> `ds-resident-stage-full` is a **117th documented case with no golden row** — section 5.9
> deviation 9 records why.

`scripts/decode-step-golden.jsonl` is rewritten at schema 3. No other golden moves: the `weights`
object is new, and no existing field changes value in streaming mode. Predicted in advance so the
diff is reconciled rather than explained afterwards:

| File | Change |
| --- | --- |
| `scripts/decode-step-golden.jsonl` | Every row gains `"schema": 3` and a `weights` object with `"mode": "stream"` and zeros. No row's existing field changes |
| Every other golden and fixture | **Unchanged.** Verified by the claim that no streaming-mode value moves; a differing row is a finding, not an expected churn |

## 5. Closure matrix

Construction, success, failure, malformed input, early exit, cleanup, and each affected module.

### 5.1 `src/decode_step.align` — the operand and the arena's owner

> **Shipped: the arity cell reads 14 / 8 / 15 and the last two regressions were renamed.** The
> operand is `args[13]` (section 5.9 deviation 5), so the accepted arity is **14**, 8 is still
> refused, and the over-arity case is **`ds-arity-15`**; `ds-arity-12` and `ds-arity-13` do not
> exist and were never written under those names — the over-arity case moved up one position with
> each capability that grew the grammar and carries no golden row, so the rename cost nothing.
> `ds-resident-smoke` and `ds-resident-budget` are also not the shipped names: section 5.9
> deviation 4 defers the budget case with its reason, and the construction cell's regressions are
> the `ds-resident-weights-*` pair plus the runner's independent arena recomputation. The
> early-exit cell's `ds-force-resident-wrap` **is** shipped — see section 11.1 correction 12, which
> is why it exists.

| Cell | Implementation | Regression |
| --- | --- | --- |
| Formation — arity 12 accepted, 8 still refused, 13 refused | The arity set in `decode_step`'s validation order | `ds-arity-12`, `ds-arity-8` (unchanged), `ds-arity-13` |
| Malformed input — `RESIDENT` not `-` and not `weights` | `R6_RESIDENT`, detail `resident[…]` via `bounded_detail`, raised **before** any path work | `ds-resident-unknown`, `ds-resident-empty` |
| Construction — the arena | `buffer(resident_bytes + MAX_TENSOR_ALIGNMENT)`, `fill_zero`, `base_mod`, `prime_window`, interior slice; the same six lines as `src/decode_step.align:2467`, at run scope and at the sum size | `ds-resident-smoke` (synthetic pack, hosted) |
| Failure — degraded reservation | `R6_RESIDENT_UNAVAILABLE` on `weights.bytes().len() != pad + resident_bytes` | Fail-closed, **not input-reachable**; deferred with the same reason `R4_WINDOW_UNAVAILABLE` carries (Request 35). Named in section 7 |
| Failure — over budget | `R6_RESIDENT_BUDGET` in `stage_window`'s resident branch, before allocation | `ds-resident-budget`, via the lowered-limits entry point idiom `src/alignpack_limits_smoke.align` established |
| Early exit — a failure between the fill and the wrap | One teardown, no early `return` between the arena's construction and the converged teardown | `ds-force-resident-wrap` (forced build) |
| Cleanup | Wrap freed, then backend closed, then the arena's frame exits | Oracle B, section 4.3 |
| Success | `weights.mode == "resident"`, `weights.step_pack_bytes == 0` | Oracle R |

### 5.2 `src/model_forward.align` — the layout

> **Shipped: the first two rows name functions that do not exist in that form.** `stage_window` has
> **no** resident branch and is byte-unchanged; the sum layout is a new function,
> `model_forward.plan_resident`, with `stream_layout` expressing the streamed window in the same
> shape so both modes travel one code path. `graph_weights` is likewise **byte-unchanged**
> (`src/model_forward.align:3193`): the per-graph base offset travels in the `ResidentLayout` the
> caller already holds and is applied where the view is taken, not inside that function. Three
> regressions named here were never written under these names — `ds-resident-layout` is replaced by
> the runner's independent walk of the packer's own 339 member records on the **real** model, which
> is a stronger check than a constant on a synthetic geometry, and the hosted lane asserts the same
> arithmetic structurally (`RESIDENT_TABLE_BYTES`/`RESIDENT_STAGE_BYTES` in
> `scripts/run-layer-forward-smoke`); `ds-resident-embed` is replaced by oracle R, which compares
> the two legs' **logits** and so covers the staged rows end to end rather than comparing them
> directly — and by `ds-resident-stage-full`, added by the final review, which runs oracle R over a
> resident prefill of exactly `MAX_PREFILL_TOKENS` distinct ids so that the highest slot
> `stage_embed_row` can be asked for is a shipped passing case (section 11.1 correction 13); and
> `ds-resident-smoke` (section 5.1) is replaced by `ds-resident-weights-1` and
> `ds-resident-weights-steps`. Each replacement is at least as strong as the case it stands in for,
> which is why they are recorded here rather than deferred in section 7.

| Cell | Implementation | Regression |
| --- | --- | --- |
| `stage_window`'s sum branch | Resident mode sums `layer_window_bytes`, the head, the full `token_embd.weight`, and the embed stage, and records a base offset per graph; streaming mode keeps the max sweep byte-for-byte | `ds-resident-layout` asserts the computed total against the ledger's 4,677,184,512 on the reference geometry |
| `graph_weights`'s region | `region := window[base + m.window[at] .. base + m.window[at] + span]` — one added term | Oracle P |
| `fill_members` — called once | Resident mode fills the arena once, in graph order, before the backend opens; the per-graph call is not made | Oracle R, plus `weights.fill_pread_count` |
| The embed stage | `window_copy` within the arena, section 3.3 | `ds-resident-embed`, comparing the staged rows against the streamed run's gathered rows |
| Malformed — a member whose span exceeds the arena | Existing `R5_SHAPE` and the existing slice bounds; no new code | Unchanged |
| `--model-forward` and `--model-forward-gpu` | **Byte-unchanged.** Resident mode is reachable only from the `--decode-step` arm | The existing `model-forward-qualification` and `metal-forward-qualification` are re-run unchanged |

### 5.3 `src/ggml_ffi.align`, `scripts/ggml_shim.c`, `scripts/ggml_shim_stub.c`

**Byte-unchanged, and that is a finding rather than an omission.** Section 2.3 established that
`buffer_from_host` and `slot_place` already express the whole mechanism, and `window_copy` already
expresses the embed stage. The shared-region byte-identity check between shim and stub that
`scripts/run-ggml-spike-smoke` asserts therefore does not move.

The one thing to verify, and it is verified by a probe rather than assumed (section 5.7): that
`ggml_backend_dev_buffer_from_host_ptr` accepts a 4.68 GB range and that tensors from different
contexts may be placed into one buffer.

### 5.4 `src/ggml_spike.align`, `src/layer_qwen2.align`

**Byte-unchanged.** The dispatch arm forwards `args` without enumerating arity; `MAX_NODE_SLOTS`,
the slot numbering, and the node tables are untouched because tensors stay per graph.

### 5.5 `scripts/run-decode-step` — the qualification

| Cell | Implementation |
| --- | --- |
| Physical-memory preflight | `sysctl -n hw.memsize` / `/proc/meminfo`; one `N/A` line naming physical memory below 12 GiB, exit 0 |
| Compressor state | `vm_stat` (Darwin) / `/proc/vmstat` (Linux) recorded before and after each timed run and printed with the result (section 3.4, measurement risk 2) |
| Oracle R | Each prompt runs streamed then resident and compares the two normalized documents with the three-field exclusion enumerated inline |
| Baseline and result | The `N ∈ {1, 4, 16}` scaling row is taken on **both** legs, back to back, in one session |
| Cleanup | The existing `trap cleanup` is unchanged and already covers every exit path including a signal |

### 5.6 `scripts/run-layer-forward-smoke` — the hosted fixture

The hosted lane runs against the **ggml-free stub**, so a resident-versus-streamed *numerical*
equality is not available there and is not claimed. The fifth block's synthetic-pack cases cover, and
this is stated rather than left as "characterization":

- the twelfth operand's acceptance at arity 12 and its refusal at 8 and 13;
- `R6_RESIDENT` on an unknown and on an empty value, with the bounded detail;
- `R6_RESIDENT_BUDGET` through the lowered-limits path;
- `weights.mode` present in a success document and in an error document;
- the three-consecutive-runs determinism check, unchanged, now over schema 3.

Numerical equality (oracle R) is a **capable-only qualification** oracle, exactly as gate G is.

### 5.7 Cell RW-P1 — the first implementation step is a probe

Before any of the above is written: extend R4.5's `probe1.align` by three lines to wrap a 4.68 GB
Align buffer with `buffer_from_host`, create two tensors in **two different** `no_alloc` contexts,
place both into that one buffer, compute, and free the wrap after both contexts are freed. If it
fails, the boundary in section 2.6 is wrong and B becomes the design; risk 1 records that. The probe
is cheap — R4.5's harness exists — and it is the cell that makes every other cell honest.

### 5.8 Result — what was built, and what it measured

**Cell RW-P1 first, because the whole boundary rested on it.** The probe of section 5.7 was written
and run before a line of the capability was, at the pinned compiler
`3a34febe912db5096c58c74fede36ff53f223e04`, against the real CPU device through the shipped shim.
It allocates a 4,677,184,512-byte Align `buffer`, wraps it once with
`ggml_ffi.buffer_from_host`, and then runs **two generations** of three fresh `no_alloc` contexts
each, placing one tensor from each context into that one wrap, computing, and freeing all three
contexts before the next generation starts:

```text
$ ./r6w_probe                          # probe source outside the work tree; not committed
requested: 4677184512
published: 4677184576                  # pad 64 + the whole request; the reservation held
reserve ns: 388696333
buft max size: 9223372036854775807     # the CPU buffer type reports SIZE_MAX, clamped to INT64_MAX
interior align mod 32: 0
wrap ns: 1125
wrap: ACCEPTED                         # <- risk 1, first half: a 4.68 GB range is accepted
round 1   offset a: 0            offset b: 64            offset c: 128
          compute status: 0    -2000.0 -6000.0 -10000.0 -1000.0 -1000.0 -1000.0
          pool carries the output: 1
round 2   offset a: 4000000000   offset b: 4400000000    offset c: 4677184448
          compute status: 0    -2000.0 -6000.0 -10000.0 -1000.0 -1000.0 -1000.0
          pool carries the output: 1
round 1: 1   round 2: 1
RW-P1: PASS
        0.50 real   4729257984 maximum resident set size   4699990528 peak memory footprint
```

Read line by line, because each line is one clause of risk 1:

- **`wrap: ACCEPTED`.** `ggml_backend_dev_buffer_from_host_ptr` takes a 4,677,184,512-byte range on
  this device, in 1,125 ns. The CPU buffer type reports `SIZE_MAX`, which the shim clamps to
  `INT64_MAX`, so the gate at `scripts/ggml_shim.c:872` passes rather than refusing.
- **Two context generations, one wrap.** Round 2's three tensors were created in three contexts that
  did not exist when round 1's were freed, and all three were placed into the same live wrap. That
  is exactly the lifetime split section 1.2 fired the design gate on.
- **Offsets above `INT_MAX`.** Round 2 places at 4,000,000,000, 4,400,000,000, and 4,677,184,448 and
  `ggml_get_data(t) - base` returns those numbers exactly. The interior-offset arithmetic is 64-bit
  end to end.
- **`pool carries the output: 1`.** The bytes ggml wrote are visible through Align's own view of the
  same allocation, so nothing was copied anywhere.
- The wrap was freed after both generations and the process exited 0, so the R5C abort that motivates
  keeping Metal out of scope did not appear on CPU.

The answer to RW-P1 is therefore **yes on both halves, and candidate A ships unchanged**. Candidate
B, priced at 0.148 s per step in section 2.2, was not needed.

**One thing the probe found that this document could not have predicted:** `arena` is a **reserved
word** in Align at this pin. `fn f(borrow arena: slice<u8>)` fails to parse with
`error: expected ':'` at the parameter name, and the failure cascades into a wall of top-level
errors that name every later line and not the cause. Every identifier in the implementation is
therefore `resident_*`, `pool`, or `layout`; "arena" survives only in prose. The reserved word
itself is the language's prerogative and is **not** requested. The **diagnostic** is: it names
neither the word nor, for a local binding, the right token, and it buries the one real cause under
errors on lines that contain no defect. That is Align Request 51, filed with three minimal repros
at this pin (section 8).

**What was built.** The changed surface is five files and no `Makefile` line:

| File | Change |
| --- | --- |
| `src/model_forward.align` | `Outcome` gains eight fields (`resident_mode`, `resident_bytes`, `resident_fill_ns`, `resident_fill_pread_count`, `resident_fill_bytes`, `step_pack_bytes`, `resident_wraps_created`, `resident_wraps_freed`); `ResidentLayout` plus `plan_resident`, `stream_layout`, and `empty_resident_layout`; `stage_embed_row`. `stage_window`, `graph_weights`, `graph_identity`, `graph_alignment`, `fill_members`, `read_into_window`, and `teardown_graph` are **byte-unchanged** |
| `src/decode_step.align` | the `RESIDENT` operand at `args[13]`, arity 14, `R6_RESIDENT`/`R6_RESIDENT_BUDGET`/`R6_RESIDENT_UNAVAILABLE`, `fill_resident`, the run-scope wrap and its teardown, `weights` in the document, schema 4, and one `borrow layout` plus one `resident: bool` plus one `resident_buffer: raw` threaded through `prefill_pass`, `prefill_head`, `decode_pass`, `decode_loop`, `schedule_decode`, and `run_step_graph` |
| `scripts/run-layer-forward-smoke` | eight new cases, oracle R at one and three steps, the `weights`-object assertions on **every** case, and `fill_ns` added to `normalize` |
| `scripts/run-decode-step` | the physical-memory preflight, the compressor recording, both legs of the scaling row at three runs each, oracle R on the real model, and the arena's size recomputed independently from `pack.json` |
| `scripts/ggml_shim_stub.c` | two functions, section 5.9 deviations 1 and 8 |
| `scripts/build-ggml-shim` | one forced-build flavour, `engine+resident-wrap`, section 11.1 correction 12 |

`src/ggml_ffi.align`, `scripts/ggml_shim.c`, `src/ggml_spike.align`, `src/layer_qwen2.align`, and
the `Makefile` are **byte-unchanged**, exactly as sections 5.3 and 5.4 predicted for the first four.
The `Makefile` matters on its own: no target, no `.PHONY` word, and no build-list entry moves, so
aggregate membership and check topology are unchanged by construction.

**The layout, from the pack itself.** The arena on the reference model is **4,677,533,696 B**:

| Region | Bytes |
| --- | --- |
| `token_embd.weight`, the whole table | 306,561,024 |
| the embed stage, `MAX_PREFILL_TOKENS` (32) rows of 2,016 B, rounded to `block_align` | 65,536 |
| 28 layers | 3,923,820,544 |
| the head | 447,086,592 |
| **total** | **4,677,533,696** |

`scripts/run-decode-step` recomputes this by walking the 339 member records in the packer's own
`pack.json` with the same rounding rule, and asserts the arm's `weights.resident_bytes` against it —
so the layout is agreed by two implementations that share no code rather than checked against a
constant. Section 11 correction 7 records why this is 349,184 B above the figure section 3.2
predicted.

**The primary metric, exact and noise-free.** `weights.step_pack_bytes`, on the reference prompt
(`def add(a, b):`, `T = 6`), `KV_WIDTH` 256:

| `N` | streamed | resident |
| --- | --- | --- |
| 1 | 4,370,560,992 | **0** |
| 4 | 17,482,243,968 | **0** |
| 16 | 69,928,975,872 | **0** |

The streamed figure at `N = 1` is **exactly** the 4,370,560,992 B per step section 1.1 derived from
R6-STEP-N's two byte totals, and the `N = 16` total pack read is **exactly** the 74,299,583,904 B
that document recorded. The counter reproduces the prediction to the byte, in an independent
measurement, which is the strongest available evidence that it counts what it claims to count.

**The secondary metric — elapsed, three runs per point, both legs, back to back, one session, one
host.** See section 5.8.1.

**Correctness is free, and it was measured rather than argued.** Oracle R compares the resident and
streamed documents field by field after `normalize`, excluding the `weights` object, the two pack
counters, and the per-graph `ggml_buffers_created`/`_freed` pair the hoist moves (section 5.9
deviation 2). It runs on the hosted lane at one and three steps and on the real model at
`N = 16` with the transcript, the logits blob, and the reference GGUF all supplied — so gate G,
oracle A′, oracle B, oracle C′, and the logits oracle are **re-run on the resident leg** and not
inferred from the streamed one. Oracle P's `pointer_identity_failures` is 0 over 678 placements at
`N = 1` and 5,763 at `N = 16` (`339 x 17`), every one of them against an arena offset.

**A confirmation that was not designed for and is worth stating.** The streamed leg's total pack
reads reproduce R6-STEP-N section 5.4's recorded figures **exactly, at all three points** —
8,741,169,024 at `N = 1`, 21,852,852,000 at `N = 4`, and 74,299,583,904 at `N = 16` — measured on a
different day, in a different process, by a counter this capability added. The baseline this claim
is made against is therefore the same baseline that document published, byte for byte, and not a
number that drifted between the two.

### 5.8.1 The measurement

Host: Apple M1, 8 cores, 16 GiB, macOS 26.5.2, `darwin/arm64`. Compiler pin
`3a34febe912db5096c58c74fede36ff53f223e04`, ggml 0.21.0 (Homebrew), llama.cpp `bb4caa754`
(`.llama-revision`, R2C-patched) for the transcript and Homebrew `llama-debug` build 10566 for the
logits blob. Model `qwen2.5-coder-7b-instruct-q4_k_m.gguf`, 4,683,073,536 B; pack 4,677,222,400 B,
58 blocks, 339 members, `block_align` 4,096.

The recorded run is the one taken at the **merged head** `e547cb0`, after `agent/r6-kv-persist`'s
review repair and `main` came in, because that is the head the claim is made about:

| `N` | leg | elapsed, median of 3 | spread | decode compute | `weights.step_pack_bytes` | total pack bytes read |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | streamed | 5.016 s | 4.950 .. 5.028 s | 0.169 s | 4,370,560,992 | 8,741,169,024 |
| 1 | **resident** | 5.819 s | 5.717 .. 6.367 s | 0.865 s | **0** | 4,677,156,960 |
| 4 | streamed | 7.117 s | 7.102 .. 7.197 s | 0.697 s | 17,482,243,968 | 21,852,852,000 |
| 4 | **resident** | 6.440 s | 6.092 .. 6.757 s | 0.747 s | **0** | 4,677,156,960 |
| 16 | streamed | 18.016 s | 17.577 .. 18.274 s | 2.885 s | 69,928,975,872 | 74,299,583,904 |
| 16 | **resident** | **8.808 s** | 8.215 .. 8.863 s | 2.928 s | **0** | 4,677,156,960 |

The same measurement was taken twice before the merge, on the pre-merge head, and both are reported
in the spread discussion below: 449,779 ppm on a host under memory pressure and 507,887 ppm on a
quiet one. A **fourth** run was taken after the review repair, with the legs interleaved — see
*Run 4* below, which is the measurement of record for the elapsed claim and the most conservative of
the four. **All four exceed the floor**, and the byte metric was identical in all four.

The fill is 4,669 `pread`s of 4,677,120,000 B, measured at 1.6 to 2.6 s depending on page-cache
state, and it is paid **once** whatever `N` is: the resident leg's total pack read is the same
4,677,156,960 B at `N = 1`, `N = 4`, and `N = 16`, while the streamed leg's grows by exactly
4,370,560,992 B per step.

**The floor verdict at the merged head, printed by the runner and asserted by it.** This is run 3's
output verbatim, including the ceiling wording the review later corrected — the runner's current
text is in *Run 4* below:

```text
decode step qualification: R6W floor  baseline (streamed, this session) 18016366125 ns,
  resident 8807742250 ns, removed 9208623875 ns = 511125 ppm of the fixed task
  against a 150000 ppm floor: MET
decode step qualification: R6W the recorded cost ceiling was 586000 ppm and the measured result is
  511125 ppm, so this is a **ceiling-estimation miss** and is reported as one rather than absorbed
  into a passing claim (docs/specs/c8-speed-first.md section 1)
decode step qualification: R6W arena 4677533696 B, reproduced from the pack document by an
  independent walk of its 339 member records
decode step qualification: R6W oracle R PASS -- the resident and streamed documents are
  byte-identical after normalize outside the `weights` object, `pack.reader_*`, and the per-graph
  ggml buffer pair; 16 token ids, gate G, oracle A', oracle B, and the logits oracle all re-run on
  the resident leg
```

**511,125 ppm of the `N = 16` fixed task, against a 150,000 ppm floor: MET**, at 3.4x the floor and
87 % of the 586,000 ppm ceiling this document recorded before implementation. The shortfall against
the ceiling has a named cause — the ceiling assumed the fitted 4.5 s fixed cost was entirely
unavoidable, and the measured fill is 1.6-2.6 s of it rather than zero. It is **not** a
ceiling-estimation miss under the threshold section 3.4 now states; the runner printed it as one
here because it labelled every shortfall, which is the wording the review corrected.

**Run 4, and why it is the figure this document quotes.** The three runs above all took the three
streamed repeats at an `N` and then the three resident ones, which confounds the leg with the clock
(section 3.4, measurement risk 4). The runner now **interleaves** them, and the whole scaling row
was re-taken once at the repair head, three repeats per point, same host, same prompt, same session,
827 s for the whole qualification against the 1800 s cap:

| `N` | leg | elapsed, median of 3 | spread | decode compute | `weights.step_pack_bytes` | total pack bytes read |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | streamed | 5.355 s | 4.962 .. 6.981 s | 0.168 s | 4,370,560,992 | 8,741,169,024 |
| 1 | **resident** | 6.800 s | 6.407 .. 9.550 s | 0.939 s | **0** | 4,677,156,960 |
| 4 | streamed | 7.594 s | 7.161 .. 8.323 s | 0.559 s | 17,482,243,968 | 21,852,852,000 |
| 4 | **resident** | 7.721 s | 7.699 .. 7.728 s | 1.024 s | **0** | 4,677,156,960 |
| 16 | streamed | 17.112 s | 16.824 .. 18.871 s | 3.029 s | 69,928,975,872 | 74,299,583,904 |
| 16 | **resident** | **10.049 s** | 9.757 .. 10.840 s | 3.114 s | **0** | 4,677,156,960 |

```text
decode step qualification: R6W floor  baseline (streamed, this session) 17111725584 ns,
  resident 10048637375 ns, removed 7063088209 ns = 412763 ppm of the fixed task
  against a 150000 ppm floor: MET
decode step qualification: R6W ceiling  the recorded cost ceiling was 586000 ppm and the measured
  result is 412763 ppm = 70 % of it
decode step qualification: R6W the result is below the recorded ceiling but not far below it, so it
  is **not** a ceiling-estimation miss; the shortfall is the one-time fill, which the ceiling
  assumed away (docs/specs/r6-resident-weights.md section 3.4)
```

**412,763 ppm, MET at 2.75x the floor and 70 % of the ceiling.** Every byte counter is identical
byte for byte across all four runs, including the streamed leg's reproduction of R6-STEP-N's
8,741,169,024 / 21,852,852,000 / 74,299,583,904.

**What interleaving establishes is that the confound is gone, not how large it was.** Section 3.4's
measurement risk 4 argued from thermal drift that a streamed-first order would *understate* the win.
That direction was **not confirmed**: interleaving moved the streamed leg from 18.016 s to 17.112 s
and the resident leg from 8.808 s to 10.049 s, and the interleaved result landed **37,016 ppm below
the lowest blocked run (449,779) and 98,362 ppm below the highest (511,125)** — a range comparable
to the blocked runs' own 61,346 ppm spread. With one interleaved run that distance is **not
separated from this host's noise**, so this document claims no order effect of any particular
magnitude. A page-cache and compressor mechanism is plausible — under interleaving every run is
preceded by a run of the *other* leg, so the resident leg no longer inherits a page cache that three
consecutive 4.68 GB resident fills had warmed for it, and the alternation between a 4.7 GB and a
0.5 GB footprint gives the compressor more to do on the resident side — but it was not measured and
is not asserted. **This is exactly why the confound was removed rather than reasoned about**: what
the re-measurement buys is a leg that is no longer confounded with the clock, plus the negative
finding that the predicted direction did not hold. The conservative reading is the worst of the four runs —
**412,763 ppm, 2.75x the floor** — and the claim's verdict, its `N = 16` shape, and its primary
metric are unchanged by any of it.

**Where the crossover is, stated rather than hidden, and it is not a clean number.** Residency is
**reliably slower at `N = 1`** — 5.819 s against 5.016 s at the merged head, 6.800 s against 5.355 s
interleaved, and slower on both pre-merge runs too — because the one-time fill costs more than one
step's saving. At `N = 4` it is **on the boundary and the four runs disagree about the sign**:
6.440 s against 7.117 s at the merged head (resident wins), 8.133 s against 7.146 s on the second
pre-merge run and 7.721 s against 7.594 s interleaved (streamed wins both). By `N = 16` it is
decisive on every run, and the gap grows linearly after that, because the streamed term is
`N x 4.37 GB` and the resident term is a constant.

The honest summary is therefore: **`N = 1` no, `N = 4` a coin toss on this host, `N >= 16` yes by a
factor of 1.7.** A caller doing a one-step decode should not ask for `weights`, and the operand
being opt-in is why they do not have to.

**Memory footprint**, `/usr/bin/time -l` around one whole `--decode-step` invocation:

| | streamed | resident |
| --- | --- | --- |
| peak memory footprint, `N = 16` | 504,400,576 B | 4,739,885,632 B |
| peak memory footprint, `N = 1` | 503,794,368 B | 4,736,313,856 B |
| max resident set size, `N = 1` | 537,903,104 B | 4,391,354,368 B |

That is the 9.4× growth §10 risk 7 predicted, and it is the point of the capability rather than a
surprise. Max RSS below the footprint is the compressor, exactly as section 2.4 measured; the
compressor counters recorded around every timed run are printed by the runner and any movement is
reported with the result rather than absorbed into it.

**Exact commands.**

```sh
export LIBRARY_PATH=/opt/homebrew/lib:/opt/homebrew/opt/openssl@3/lib:/opt/homebrew/opt/zstd/lib
export ALIGN_LLM_GGML_INCLUDE=/opt/homebrew/include ALIGN_LLM_GGML_LIB=/opt/homebrew/lib
export ALIGN_LLM_GGUF_MODEL="$HOME/models/qwen2.5-coder-7b-instruct-q4_k_m.gguf"
export ALIGN_LLM_LLAMA_DEBUG=/opt/homebrew/bin/llama-debug
export ALIGN_LLM_LLAMA_EVAL_CALLBACK="$(scripts/llama-eval-callback-toolchain ensure instrument)"
gmake build
gmake check
gmake fmt
gmake format-check
gmake layer-forward-smoke
gmake ggml-spike-smoke
gmake gate-topology-check
gmake decode-step-qualification     # both legs, N in {1, 4, 16}, three runs each
git diff --check
```

**Measurement risks, as they actually behaved.** Two numbering spaces meet here and the references
name both: `§3.4 risk n` is one of section 3.4's four **measurement** risks, and `§10 risk n` is one
of section 10's nine **capability** risks.

1. **Page-cache state** (§3.4 risk 1, §10 risk 5). Mitigated as designed: the baseline and the
   result are taken back to back in one session with the pack already read once, and the streamed
   leg's own `N = 16`
   elapsed reproduced R6-STEP-N's 18.235 s to within the run-to-run spread that document recorded.
   The **primary metric is bytes**, which the page cache cannot move.
2. **Memory compression** (§3.4 risk 2, §10 risk 3). Recorded before and after every timed run
   through `vm_stat`; the runner prints any movement with the result, and — as §3.4's own `Shipped`
   note records — it never discards or retakes a run on that basis. Max RSS below the peak footprint
   on this host is the compressor doing exactly what section 2.4 measured, and it is why the elapsed
   claim is secondary.
3. **One point on one prompt** (§3.4 risk 3). The byte metric is reported at
   `N ∈ {1, 4, 16}` and is exact at all three; the elapsed figure is the median of three runs with
   the spread printed.
4. **A risk this document did not predict, and what four runs of it showed.** Decode **compute**
   rose sharply in resident mode on the first qualification run — 3.477 s streamed against 4.998 s
   resident at `N = 16` — and barely moved on the second (3.109 s against 3.307 s), the third
   (2.885 s against 2.928 s), or the fourth (3.029 s against 3.114 s). Residency changes no arithmetic operation, so the first run's 1.5 s
   was a memory-system effect on a host under pressure — the streamed path's 447 MB window is
   re-touched thirty times per step and stays hot, while a 4.68 GB arena the compressor is holding
   does not — and the two later runs on a quieter host are the ones to believe. **All four are
   reported**, the elapsed figures are net of whichever occurred, and the spread across them —
   412,763, 449,779, 507,887, and 511,125 ppm — is the honest size of this host's measurement noise
   plus one method change on the secondary metric. The primary metric was **byte-identical across
   all four runs and every repeat within them**, which is why it and not the clock carries the
   claim.

### 5.9 Deviations from this document, and why

Every one is recorded here rather than left for a reviewer to find.

1. **`scripts/ggml_shim_stub.c` is not byte-unchanged.** Section 5.3 predicted it would be, and the
   real shim and `src/ggml_ffi.align` are. One function in the **test double** moved:
   `align_stub_reset_if_idle` reclaimed the engine's graph pool and tensor arena only when no context
   **and no buffer** was live. A buffer record there is a borrowed `(base, size)` over the caller's
   own memory and owns nothing in the arena, so including it made the reset depend on a lifetime it
   does not describe — and a caller holding one wrap across many graphs, which is exactly a resident
   weight arena, exhausted `ALIGN_STUB_MAX_GRAPHS` after eight graphs with every context correctly
   closed. Real ggml frees a graph with its context and has no such coupling, so the double was
   refusing a program the thing it doubles accepts. The test is now gated on contexts and gallocrs.
   The region between the two `R4.5 SHARED SHIM CONTRACT` markers is untouched, so
   `scripts/run-ggml-spike-smoke`'s shim/stub byte-identity assertion does not move.
2. **Oracle R excludes two more fields than section 4.1 enumerated.** The design named the `weights`
   object and `pack.reader_pread_count`/`reader_bytes_read`. `lifetime.ggml_buffers_created` and
   `lifetime.ggml_buffers_freed` had to join them, because hoisting the weight wrap to run scope is
   *precisely* what this capability does: the streamed leg creates and frees one wrap per graph and
   the resident leg creates and frees one for the whole run. The exclusion is narrow and compensated:
   the per-graph pair still balances and is asserted to, and `weights.resident_wraps_created` and
   `_freed` are asserted to be exactly 1 each, which is section 4.3's own run-scope invariant. The
   exclusion set is enumerated inline in both runners, never pattern-matched.
3. **`window.reuse_count` keeps counting in resident mode.** Section 4.1 did not name it, and the
   naive implementation would have made it differ (a refill per graph against no refills at all),
   which would have forced a third exclusion. It is instead incremented once per graph in **both**
   modes: the field measures the graphs that read their weights out of the one Align-owned region,
   which is what it has always reported on the streamed path and is now true of both.
4. **`R6_RESIDENT_BUDGET` is not input-reachable and its `ds-resident-budget` case is deferred.**
   Section 5.1 named the lowered-limits entry point of `src/alignpack_limits_smoke.align` as its
   route. That idiom does not reach this guard: the arena's size is the **sum** over members, and
   `alignpack_read.member_at` refuses any member whose `pack_offset + nbytes` leaves its block
   (`R4_PACK_OFFSET`) while the block table refuses any block leaving the file, so a container that
   declares an 8 GiB weight sum below 8 GiB of file cannot be built. The guard runs **before any
   allocation** and is fail-closed, and it is deferred on exactly the terms `R4_WINDOW_UNAVAILABLE`,
   `R6_PLANE_UNAVAILABLE`, and this capability's own `R6_RESIDENT_UNAVAILABLE` already carry.
   What ships in its place is stronger than a synthetic refusal would have been: the layout
   arithmetic the budget guards is asserted against an **independent second computation** from the
   packer's own document on the real 4.68 GB model.
5. **`RESIDENT` is `args[13]`, not `args[11]`.** Section 3.1 designed it at the twelfth operand
   against a head where `STEPS` was last. `R6-KV-PERSIST` took `args[11]` and `args[12]` for
   `KV_SAVE` and `KV_LOAD` before this capability was implemented, and section 9.4 is what fixed
   that merge order. The arity set is `{5, 6, 7, 9, 10, 11, 12, 13, 14}`; 8 is still `R6_ARITY` for
   R6's own reason and 15 and above are `R6_ARITY`.
6. **The document is schema 4, not 3.** Section 9.4 predicted exactly this and named the condition:
   KV-PERSIST merges first and takes 3. It did.
7. **Oracle R is a hosted oracle, not only a capable-host one.** Section 5.6 said the hosted lane
   could not compare the two legs numerically because it runs without ggml. That is wrong in this
   repository's favour: the hosted lane runs the **engine** shim, a deterministic ggml-free kernel
   set that computes real numbers from wherever the weights were placed, so oracle R runs there at
   one and three steps against the golden corpus. The correction is recorded rather than quietly
   enjoyed.

8. **`scripts/ggml_shim_stub.c` moved a second time, and `scripts/build-ggml-shim` gained a
   flavour.** Deviation 1's narrowing of `align_stub_reset_if_idle` went one step too far: it
   dropped the buffer test outright, and one buffer record in that file — the one
   `align_ggml_alloc_remaining` returns over `align_stub_arena` for the reference arm's tensors —
   genuinely *does* own arena memory. A caller that closed its context while still holding that
   record would have had the bytes under it reclaimed and handed out again. The record now carries
   an `owns_arena` flag and the reset gates on it, which is exactly the original test restricted to
   the records that own something: a resident weight wrap over the caller's own memory does not gate
   the reset and an arena-backed record does. `scripts/build-ggml-shim` gains
   `engine+resident-wrap`, the forced build correction 12's regression needs. The region between the
   two `R4.5 SHARED SHIM CONTRACT` markers is still untouched.

9. **`ds-resident-stage-full` is a documented case with no golden row, and CI is why.** The final
   review asked for a positive case at `tokens.count == MAX_PREFILL_TOKENS`, and the first version of
   it carried a golden row like every other documented case. Hosted CI refused it: the golden is
   committed once and compared byte for byte on **macOS/arm64 and on Linux/x86_64**, and a 32-token
   prefill's activations differ between the two hosts in the last bit —
   `.schedule[0].l_out_bit_sum` 538,248,184,962 against 538,248,184,963, and both step digests with
   it. Thirty-two rows of `exp` and a longer accumulation reach a host difference the three-token
   corpus never does. A golden row for it would have been a statement about the machine that
   regenerated the file, so the case runs in its own `BOUNDARY_CASES` list instead and is asserted
   by **oracle R against its streamed twin** — a within-host comparison, correct on every platform —
   plus `record()`'s document-identity assertions and a structural block. The golden therefore stays
   at 116 rows while the runner reports 117 documented cases, and the two prints say so. This is a
   real limit on what a committed golden can pin, and it is recorded rather than worked around by
   loosening `normalize`.

### 5.10 The mutants

A regression that cannot fail is not a regression. Each of these was applied to the shipped source,
run through `gmake layer-forward-smoke`, and reverted. **Six were injected and five died**; the line
that killed each of the five is named, and the sixth is recorded as unkilled rather than credited
with a kill it did not earn.

| Mutant | Caught by |
| --- | --- |
| The arena is refilled per decode step (`if !resident` removed from `decode_pass`'s layer fill) | `ds-resident-weights-1: a resident run read 4864 pack bytes in its decode steps`, plus the golden's own `weights.step_pack_bytes: 0 != 4864` and `pack.reader_bytes_read` |
| A layer's weights are filled at the wrong arena base (`layout.base[1 + (layer + 1) % n_layer]`) | `R5_SOURCE_DIVERGED layer[0]role[attn_norm]` — the byte comparison against the source GGUF, which runs against the same sub-slice the graph will read — and independently by oracle R, which reports a failed run against a passing one |
| The run-scope wrap is never freed | `the teardown did not balance` and `1 graph boundaries left a ggml object alive` — section 4.3's separate counter pair, folded into `released_before_owner_scope_end` and `graph_balance_failures` |
| The run-scope wrap is created **twice** (a second `buffer_from_host` beside the first) | The same pair. This is the half of the invariant the repaired condition's `created > 1` clause carries, and it was **not** covered before: the pre-repair `created != 1 \|\| freed != 1` also caught it, so the repair had to keep it explicitly rather than settle for `created == freed` |
| The run-scope balance condition is restored to its pre-repair form (`created != 1 \|\| freed != 1`) | `ds-force-resident-wrap: a failure before the wrap fabricated a leak`, plus the golden's own `lifetime.graph_balance_failures: 0 != 1` and `released_before_owner_scope_end: true != false`. This is the inverse mutant for correction 12 and it is what makes the repair a regression rather than an assertion |
| `stage_embed_row`'s destination bound is restored to the whole arena (`stage_at + slot * row_bytes + row_bytes > window.len()`) | Nothing in the shipped corpus, and that is the honest answer: `slot` is bounded by `tokens.count <= MAX_PREFILL_TOKENS` at both call sites, so no input reaches past the stage today, and this mutant loosens the bound rather than tightening it. The repair (section 11.1 correction 13) is a *defence in depth* against a later caller, not a fix for a reachable defect, and it is recorded as such rather than credited with a kill. The bound's **other** side is covered: `ds-resident-stage-full` runs the highest slot a caller can produce as a passing case, so a bound one row too tight dies |

The second mutant is the interesting one: it is caught by **two** independent oracles, one of which
(the source-byte comparison) predates this capability entirely and needed no change to reach it.
The sixth is the honest one: a repair whose mutant no test can kill is a repair whose value is
argued rather than measured, and saying so is cheaper than inventing a case that reaches it.

### 5.11 Ledger and closure-matrix cells mapped to the diff

`CLAUDE.md`'s proportional design gate step 4: every applicable ledger row and matrix cell mapped to
the final diff and its passing evidence, or to an explicit deferral in this plan.

**Section 3.1 — the arm and the operand.**

| Row | Diff | Evidence |
| --- | --- | --- |
| Surface, owner module | `src/decode_step.align`; `src/ggml_spike.align` byte-unchanged | `git diff --stat` shows no `src/ggml_spike.align` |
| Operand grammar, arity | `run`'s `count > 14` bound and `resident_text := if count >= 14 { args[13] } else { "-" }` | `ds-arity-15` (no document), `ds-resident-dash` (byte-identical to the thirteen-operand form) |
| `RESIDENT` values and `R6_RESIDENT` | `execute`'s check before `stage_inputs`, `resident_detail` | `ds-resident-unknown`, `ds-resident-empty`, `ds-resident-case`, `ds-resident-unknown-and-missing`, each asserting the exact detail |
| Defaults; `weights.mode` in every document | `o.resident_mode` set before any refusal; `render_weights` in `render` | `record()` asserts the `weights` object on **all 117** documented cases |
| Position | `args[13]`, section 5.9 deviation 5 | — |

**Section 3.2 — the arena.**

| Row | Diff | Evidence |
| --- | --- | --- |
| What it is, who allocates, who frees | `execute`'s `weights` buffer at `region_bytes + MAX_TENSOR_ALIGNMENT`, freed by its own frame | `ds-resident-weights-*`, oracle B |
| Layout | `model_forward.plan_resident` | `R6W arena … reproduced from the pack document by an independent walk of its 339 member records` |
| Size on the reference model | 4,677,533,696 B | the same line; section 11.1 correction 7 |
| Budget, `R6_RESIDENT_BUDGET` | `execute`, before `buffer(...)` | **deferred**, section 5.9 deviation 4 |
| `R6_RESIDENT_UNAVAILABLE` | `weights_view.len() != pad + region_bytes` | **deferred** as designed (Request 35) |
| What it cannot refuse | — | Request 35 raised to high; section 3.6 |
| Lifetime relative to graphs | `resident_buffer` at `schedule_decode` scope; three contexts still per graph | `weights.wrap_count == 1`, `lifetime.contexts_created == contexts_freed` |
| Mutation after fill | only the embed stage | `stage_embed_row`; oracle R |

**Section 3.3 — the embedding row.** `stage_embed_row` plus the `if resident` branch in
`prefill_pass` and `decode_pass`. Evidence: `weights.step_pack_bytes == 0` at every `N`, which is
false if any embedding row is read from the pack, and oracle R, which compares the resulting logits.

**Section 3.4 — the performance claim.** Baseline re-taken in-session, three runs per point, both
legs; primary metric exact at all three `N`; floor verdict printed by the runner and asserted
(`failures.append` when below). Evidence: section 5.8.1.

**Section 3.5 — the document.** `render_weights`, `SCHEMA_VERSION := 4`, `fill_ns` normalized in
both runners. Evidence: the golden's 116 rows; the programmatic old-versus-new diff showing only
`.schema_version` and `.weights` moved.

**Section 3.6 — the memory ceiling.** The runner's `RESIDENT_MIN_GIB` preflight and its `N/A` line;
`ALIGN_LLM_RESIDENT_WEIGHTS=0`. Evidence: `resident_na` is printed and the leg is skipped when the
host is too small — not exercised on this host, which reports 17,179,869,184 B.

**Section 4 — the oracles.** R: `normalize_resident` in both runners. P: `graph_identity`
unchanged, now against arena offsets. B: `resident_wraps_created`/`_freed` plus the
`graph_balance_failures` increment. Evidence: section 5.8, section 5.10's third mutant.

**Section 5 — the closure matrix.** Every cell above, plus: formation (`ds-arity-15`, `ds-arity-8`
unchanged), malformed input (four `R6_RESIDENT` cases), construction (`ds-resident-weights-*`),
early exit (`ds-force-resident-wrap`), cleanup (oracle B), success (oracle R).

**The early-exit cell, and why its first reading was wrong.** The first implementation retired
`ds-force-resident-wrap` as "unnecessary rather than deferred", on the reasoning that **no early
`return` exists** between the arena's construction and the converged teardown — `schedule_decode`
returns early only before `backend_open`, which is before the wrap is created. That reasoning is
correct about *control flow* and irrelevant to the *invariant*. A resident run does not have to
`return` early to be in the window the cell is about: it only has to **fail** there, and two inputs
reach that state — the fill raising `R4_PACK_UNREADABLE`, and `buffer_from_host` refusing. Section
11.1 correction 12 is what the missing case was hiding, and `ds-force-resident-wrap` now exists as
a forced build. The lesson is general enough to state: a closure cell asks what the invariant does
on that path, and "no early return exists" answers a different question.

## 6. Cost of the qualification

Residency makes the qualification **cheaper per resident run and more expensive per prompt**, because
each prompt now runs twice.

| Term | Estimate |
| --- | --- |
| Streamed leg, 4 prompts × 3 runs × ~40 s | ≈ 480 s, unchanged from STEP-N risk 1 |
| Resident leg, 4 prompts × 3 runs × ~12 s (predicted 7.6 s plus the 2.1 s fill) | ≈ 144 s |
| Oracle C′ `--model-forward` passes | ≈ 60 s, unchanged |
| Instrument runs at `-n 16` | ≈ 68 s, unchanged |
| Packing | ≈ 60 s, unchanged |
| **Total** | **≈ 812 s against the 1800 s cap** |

`ALIGN_LLM_DECODE_STEPS=8` remains the documented fallback and halves the first two terms.

## 7. Deferred

- **Residency for `--model-forward`, `--moe-layer-forward`, and `--layer-forward`.** They read the
  pack once, so the ceiling in section 3.4 does not clear the floor for them. The arena code is
  written in `model_forward` and would be reachable, which is precisely why the deferral is recorded
  rather than left implicit.
- **The Metal arm.** R5C section 2.6 measured the abort; re-establishing the balance invariant on a
  backend that aborts on an unfreed buffer needs its own capability and its own device probe.
- **`ggml_get_rows` over the resident embedding table**, replacing the 2,016-byte staged copy
  (section 3.3). 68 ns per step against a changed graph and every oracle node index.
- **`R6_RESIDENT_UNAVAILABLE`'s forced build.** Not input-reachable while Request 35 leaves a
  degraded reservation unobservable; deferred on exactly the terms `R4_WINDOW_UNAVAILABLE` and
  `R6_PLANE_UNAVAILABLE` are already deferred.
- **A graceful refusal on an out-of-memory host** (section 3.6). Blocked on Request 35, compensated
  by the runner's preflight and by the operand being opt-in.
- **Partial residency, eviction, tiering, prefetch, NVMe or GPU residency, and a cross-process
  weight cache.** `align-runtime` work; this capability is the measurement that motivates it.
- **Reuse of one arena across two packs or two invocations in one process.**
- **Any tokens-per-second or TTFT claim.** Section 3.4 makes a bytes claim and a bounded elapsed
  claim; a throughput claim needs its own capability and its own baseline.

## 8. Align capability requests

Classified per `CLAUDE.md`. **None blocks this capability. One new request is proposed.**

| Gap | Classification | Status |
| --- | --- | --- |
| `buffer(cap)` cannot report a failed reservation and `append` cannot fail | Genuine Align gap, already recorded | **Request 35, `PROPOSED`.** This capability is its **second and sharpest client**: at 447 MB the degrade-to-zero was an unreachable guard, at 4.68 GB it is the difference between a document and a process abort (section 3.6). Its priority is raised to **high** and this capability is added to its evidence; `Blocking: no` stands only because `RESIDENT` is opt-in and the runner preflights physical memory |
| A `buffer` cannot be filled by one `pread` above `INT_MAX`, and there is no positional write | Genuine Align gap, already recorded | **Request 38, `PROPOSED`.** New sibling evidence: section 2.4 measured Darwin's exact `pread` boundary (`2,147,483,647` accepted, `2,147,483,648` refused). A bounded-length `pread` would let the arena be filled at member offsets directly and would delete the embed stage's `window_copy`. Cited as continuing evidence; the chunked fill is not a workaround for a hypothetical surface, it is what `read_into_window` already does |
| No aligned heap allocation | Genuine Align gap, already recorded | **Request 33, `PROPOSED`.** The arena over-reserves by `MAX_TENSOR_ALIGNMENT` and starts at an aligned interior offset, exactly as R4.5 does. One more client; the compensation is unchanged |
| Rebound `buffer` allocations are retained until frame exit | Genuine Align gap, already recorded | **Request 39, `PROPOSED`.** Relevant because it is what makes candidate B's `n_layer + 2` separate buffers expensive (section 2.2). Cited as evidence; **no workaround is built**, because the chosen design allocates once |
| A cross-module call with a `borrow mut` argument refuses shorter-lived operands | Genuine Align gap, already recorded | **Request 49, `PROPOSED`.** The arena travels as a `borrow slice<u8>` plus a base offset rather than as a `borrow mut buffer` out-parameter, for exactly the reason that request describes. One more client |
| **A program cannot ask the host how much physical memory it has** | **Genuine Align standard-library gap, not previously recorded** | **New request (section 9 settles the number).** Proposed surface: `std.os.physical_memory() -> Result<i64, Error>` and `std.os.available_memory() -> Result<i64, Error>`. Acceptance: `--decode-step` refuses `RESIDENT=weights` with a document-carrying code when the host cannot hold the arena, and `scripts/run-decode-step`'s shell preflight is deleted. **`Blocking: no`** — the check has a correct home in the runner and the operand is opt-in; recorded because `CLAUDE.md` requires a genuine language-owned gap to be recorded even when a workaround exists |

> **Shipped: two new requests, not one, and the numbers are 50 and 51.** The row above is
> **Request 50**. The review added **Request 51** — *a reserved word used as an identifier should
> say so* — for the diagnostic section 5.8 records and the first implementation declined to file.
> The reasoning it declined on was right about the language and wrong about the register: a reserved
> word **is** the language's prerogative, and the request is not about the word. It is about the
> compiler reporting `expected ':'` at a parameter, `expected '{'` one token *past* a binding, and
> then a cascade of top-level errors on lines that contain no defect — with no "reserved word"
> diagnostic anywhere in the parser or lexer to emit. That is a compiler/diagnostics gap that
> `CLAUDE.md` asks to be recorded whether or not a workaround exists, and the workaround here
> (never write `arena`) does not make the next implementer's half hour cheaper. `Priority: low`,
> `Blocking: no`, three minimal repros at the pin, and no align-llm source depends on it.

**No hypothetical surface is consumed.** Every line this document specifies compiles against the
shipped pin, and the new requests are recorded without being written against.

## 9. Reconciliation

**Applied.** The drafts below were written before implementation and are kept verbatim so the
prediction can be read against the result; section 9.5 records what actually landed and where each
draft's text changed. Three numbers moved between draft and application — the arena's size
(section 11.1 correction 7), the operand's position (section 5.9 deviation 5), and the schema
(section 5.9 deviation 6) — and the applied text carries the measured values.

### 9.1 `docs/specs/roadmap.md` — item 30

Numbering assumes **R6-STEP-N holds item 28** (its section 9) and **R6-KV-PERSIST holds item 29**.
`main` carried items to 24 when the R6 branches were cut; 25, 26, and 27 are claimed by
`agent/r3-decode-residency`, `agent/r5e-moe-model-prefill`, and `agent/r6-decode-kv-step1`
respectively. **Re-check when R6-STEP-N and R6-KV-PERSIST merge**; this branch takes
`git merge origin/main` — never a rebase — and if the numbering moved, item 30 and every
cross-reference to it move with it.

> **30. R6-RESIDENT-WEIGHTS — weights resident across decode steps.**
> `--decode-step` gains a twelfth operand, `RESIDENT` (`-` or `weights`). In resident mode the whole
> weight set — every layer, the head, and the full `token_embd.weight` — is held in one Align-owned
> arena, filled once in `CHUNK_BYTES` rounds, wrapped once as one `ggml_backend_buffer`, and read by
> every graph through `ggml_backend_tensor_alloc` at arena offsets. **A decode step reads zero pack
> bytes and copies 2,016 host bytes.** No new shim symbol and no new Align surface: the zero-copy
> placement path has been the primary weight path since R4.5. Baseline is item 28's measurement
> (18.235 s and 65,558,414,880 step-read bytes at `N = 16`); the recorded ceiling is 586,000 ppm of
> that elapsed against a 150,000 ppm floor this capability's own document defines, because no
> document owned Track B decode performance before it. Acceptance is document equality between the
> streamed and resident legs plus zero pointer-identity failures, with gate G re-run on the resident
> leg. CPU only; the Metal arm keeps the per-graph wrap R5C's abort requires. Opt-in, because a host
> that cannot hold 4.68 GB aborts rather than refuses (Request 35).

### 9.2 `HANDOFF.md` — the active block

> **Active capability.** `R6-RESIDENT-WEIGHTS`, branch `agent/r6-resident-weights`, stacked on
> `agent/r6-step-n` head `6ca1eef`.
> **State.** Design complete: `docs/specs/r6-resident-weights.md`. Not implemented. The boundary is
> settled by a probe at the pin (that document, section 2.4): a 4,370,560,992 B `buffer` allocates
> with a 4,375,700,480 B peak footprint; a whole-capacity `pread` is refused above `INT_MAX`
> (`2,147,483,647` accepted, `2,147,483,648` refused), so the arena is filled in 1 MiB rounds —
> 4,169 reads, 2.06 s. Host `memcpy` measured 29.6 GB/s, which prices the rejected copy-per-step
> design at 0.148 s per step against the chosen design's zero.
> **Next actions, in order.** (1) Cell RW-P1, section 5.7: verify `buffer_from_host` accepts a
> 4.68 GB range and that two contexts may place into one wrap — if it fails the boundary changes.
> (2) `stage_window`'s sum branch and the per-graph base offset. (3) The `RESIDENT` operand, schema 3,
> and the arena's run-scope lifetime with the balance invariant re-established at run scope
> (section 4.3). (4) Oracle R in `scripts/run-decode-step`, plus the physical-memory and compressor
> preflights.
> **Blockers.** None. Request 35 makes the out-of-memory refusal impossible; compensated by the
> operand being opt-in and by the runner's 12 GiB preflight.
> **Constraints.** CPU only; the Metal arm is out of scope. The measuring host is a 16 GiB Apple M1
> that compresses memory under pressure, so every timed run records `vm_stat`'s compressor counters.
> **Merge order.** After `R6-KV-PERSIST`; see section 9.4.

### 9.3 `docs/align-development.md` — the `--decode-step` arm

Applies to the section at `docs/align-development.md:1795`, "The `--decode-step` arm
(R6-DECODE-KV-STEP1, R6-STEP-N)", whose heading gains `, R6-RESIDENT-WEIGHTS`.

> `--decode-step` is five, six, seven, nine, ten, eleven, or **twelve** operands. Eight is refused.
>
> ```text
> ./ggml-spike --decode-step PACK GEOM.json TOKENS - REF.gguf TRANSCRIPT.txt KV_WIDTH LOGITS.bin STEPS RESIDENT
> ```
>
> `RESIDENT` is `-` (stream the weights, the shipped behaviour, and the default when the operand is
> absent) or `weights` (hold the whole weight set resident for the process's lifetime). Any other
> value is `R6_RESIDENT`.
>
> In resident mode the arm allocates one arena of about 4.68 GB for the reference model, fills it
> once with about 4,700 one-mebibyte `pread`s, wraps it once, and reads every graph's weights out of
> it by pointer. A decode step then reads **zero** pack bytes. The mode, the arena's size, the fill's
> cost, and the step-read byte count are published in the document's `weights` object, which is
> present in error documents too; the document is **schema 3**.
>
> **It is opt-in and it needs memory.** A host that cannot hold the arena aborts rather than refusing,
> because Align cannot report a failed `buffer` reservation (Request 35).
> `scripts/run-decode-step` refuses to run the resident leg below 12 GiB of physical memory and
> prints one `N/A` line. `gmake decode-step-qualification` runs both legs and asserts the two
> documents are identical outside the `weights` object and the two pack counters.

### 9.4 Meeting `R6-KV-PERSIST`

The two diffs meet in exactly two places, and neither is a conflict of meaning:

| Place | Interaction |
| --- | --- |
| `decode_step.decode_step` / `decode_pass` | KV-PERSIST changes what happens to the plane between steps; this capability changes where the weights come from. The `fill_members` call sites this capability removes are inside `decode_pass`, which KV-PERSIST edits — a textual conflict, resolved by taking KV-PERSIST's body and removing the fill calls from it |
| The document's schema number and `normalize` | Both bump the schema and both add fields. **KV-PERSIST merges first and takes schema 3; this capability then takes schema 4** and its golden rewrite is done once, after the merge, not twice |

This branch takes `git merge origin/main` — never a rebase — after KV-PERSIST lands, and section 3.5's
schema number, section 4.5's golden, and section 9.1's roadmap item are re-checked then. **The
request number in section 8's last row is likewise provisional:** R6-STEP-N section 8 records 50 as
the next free number, and KV-PERSIST may take it; this capability takes the first free number at
merge time and section 8's row is updated then.

### 9.5 What was applied

| Document | Applied |
| --- | --- |
| `docs/specs/roadmap.md` | Item **30**, as section 9.1 drafted it, with the arena at 4,677,533,696 B, the operand at the fourteenth position, and the measured result and floor verdict in place of the prediction. Items 25 to 29 are unchanged; the numbering held |
| `HANDOFF.md` | A new `## Active: R6-RESIDENT-WEIGHTS` block above the R6-KV-PERSIST one, which is left byte-unchanged so the merge from `agent/r6-kv-persist` stays clean |
| `docs/align-development.md` | The `--decode-step` section's heading gains `, R6-RESIDENT-WEIGHTS`; the arity line becomes "twelve, thirteen, **or fourteen**"; a fourteen-operand invocation joins the synopsis; and a `RESIDENT` block records the operand, the arena, schema 4, the opt-in rule with its abort, the runner's 12 GiB preflight, and the CPU-only boundary |
| the merge itself | `git merge agent/r6-kv-persist` (`bdb34eb`) resolved three conflicts and nothing else: `ds()` in `scripts/run-layer-forward-smoke` gained **both** sides' keyword arguments (`pack` from KV-PERSIST's identity refusals, `resident` from this capability); `docs/align-development.md`'s `--decode-step` heading took this capability's version below R5E's incoming section; and `scripts/decode-step-golden.jsonl` was **regenerated** rather than merged. `src/decode_step.align` and `src/model_forward.align` auto-merged with no conflict and compile clean |
| `scripts/decode-step-golden.jsonl` | Regenerated with `ALIGN_LLM_LAYER_FORWARD_GOLDEN_UPDATE=1 gmake layer-forward-smoke`: **107 rows -> 115** at the implementation head and **116** after the review repair added `ds-force-resident-wrap`; the 8 new `ds-resident-*` rows plus that one, and **no row removed**. A programmatic walk of the old and new documents confirms the only fields that moved in a pre-existing row are `.schema_version` (3 -> 4) and the new `.weights` object — exactly what section 4.5 predicted, now against KV-PERSIST's post-repair corpus rather than its pre-repair one. The repair's own regeneration moved **one added row and nothing else**: a case-by-case comparison of the 115-row and 116-row files reports one addition, no removal, and no changed row. The final review's `ds-resident-stage-full` adds a 117th documented case and **no row at all** — section 5.9 deviation 9 records the cross-platform reason — so this file is byte-identical between the review-repair head and the final head. The other six goldens are byte-identical to the incoming branch's |
| `docs/align-requests.md` | **Request 50** — `std.os.physical_memory` / `available_memory` — filed with every mandatory field, `Blocking: no`, and its acceptance criteria; the review added **Request 51** — the reserved-word diagnostic — on the same terms, and corrected Request 50's `align-llm verification` line, which had named `R6_RESIDENT_HOST` as though it were a shipped code rather than this request's proposal for one. Request 35's priority is raised to **high** with this capability recorded as its second and sharpest client and the 4.68 GB abort stated. Request 38 gains section 2.4's measured Darwin `pread` boundary and this capability as its third consumer. Requests 33, 39, and 49 are cited in section 8 as continuing clients; none changes status |

## 10. Risks

1. **`ggml_backend_dev_buffer_from_host_ptr` may refuse a 4.68 GB range, or may refuse tensors from
   a second context.** The load-bearing assumption of the whole boundary. `align_ggml_buffer_from_host`
   already reports `ggml_backend_buft_get_max_size` (`scripts/ggml_shim.c:635`) and a CPU buffer type
   ordinarily reports `SIZE_MAX`, but this was **not** measured. *Mitigation:* cell RW-P1 (section 5.7)
   is the first implementation step and it is three lines of an existing probe. If it fails, candidate
   B ships instead at 0.148 s per step, which still clears the floor by a wide margin — so the risk is
   to the *size* of the win, not to the capability.
2. **Hoisting the wrap weakens an invariant that a backend depends on.** R5C measured a Metal abort on
   an unfreed buffer. *Mitigation:* CPU only (section 1.3), the hoist is guarded by the arm and not by
   a device check, and the invariant is re-established at run scope with its own counter pair
   (section 4.3) rather than deleted.
3. **The measuring host compresses the arena.** Section 2.4 measured a 3.13 GB max RSS against a
   4.38 GB footprint. A compressed arena is not resident and would show up as decompression cost
   inside compute. *Mitigation:* compressor counters recorded per run and **reported with the
   result**; nothing is discarded or retaken, for the reason section 3.4's measurement-risk 2
   `Shipped` note gives. The **primary metric is bytes read**, which is immune.
4. **An out-of-memory host aborts instead of refusing.** Section 3.6. *Mitigation:* opt-in operand,
   a 12 GiB runner preflight, Request 35 raised to high priority with this as its evidence, and the
   behaviour documented in `docs/align-development.md` rather than discovered.
5. **The baseline is page-cache dependent.** 0.86 s per step is 5.08 GB/s, page-cache bandwidth.
   *Mitigation:* baseline and result taken back to back in one session with the pack already read
   once; the byte metric carries the claim if elapsed spreads (section 3.4).
6. **A ceiling-estimation miss.** The 586,000 ppm ceiling assumes the fitted 4.5 s fixed cost is
   entirely unavoidable and that residency adds nothing but the 2.06 s fill. If the fill is slower on
   a cold cache the result lands below the ceiling. *Mitigation:* the runner prints the result as a
   percentage of the recorded ceiling on **every** run, and applies the **miss** label below one
   half of it, per `docs/specs/c8-speed-first.md` section 1's rule and its worked precedent (section
   3.4's `Shipped` note). The measurement of record, 412,763 ppm, is 70 % of the ceiling: a
   shortfall with a named cause, not a miss, and not absorbed into a passing claim either way.
7. **Peak resident set grows about tenfold**, from the measured 507,969,536 B streamed window to
   roughly 4.9 GB. *Mitigation:* it is the point of the capability, it is bounded by
   `MAX_WINDOW_BYTES` with a refusal, and it is published as `weights.resident_bytes`.
8. **Schema and golden churn twice** if this merges before KV-PERSIST. *Mitigation:* section 9.4
   fixes the merge order so the golden is rewritten once.
9. **A resident run that silently fell back to streaming would pass every existing oracle.**
   *Mitigation:* `weights.step_pack_bytes == 0` is asserted directly, and oracle P's
   `pointer_identity_failures == 0` against arena offsets cannot be satisfied by a fallback.
10. **Shipped, added by the review: every number here is from one machine in one thermal
    environment.** Four qualification runs on one 16 GiB Apple M1 with no fan, one prompt, one
    model, one page cache. Nothing in this document establishes the elapsed result on a fanned host,
    on a host with enough memory that the compressor never engages, or on a Linux page cache, and
    the crossover at `N = 4` in particular is a property of this host's ratio between a 4.68 GB fill
    and a 4.37 GB per-step sweep rather than a property of the design. *Mitigation:* the primary
    metric is a byte counter that is host-independent and was identical across all four runs; the
    elapsed claim is explicitly secondary, bounded to "the reference prompt on the reference host",
    and section 5.8.1 prints all four runs rather than a single best figure. A second host is
    deferred with the rest of the platform work rather than claimed.

## 11. Author consistency pass

One pass, ledger against prose, performed before this document was finished. What it found and what
changed:

1. **"Zero bytes per step" was false as first written.** The embedding row gather is a token-dependent
   pack read of 2,016 B per step, and the first draft's arena held only the fixed members. Section 3.3
   now holds the full `token_embd.weight` table and states both numbers — 0 read, 2,016 copied —
   rather than rounding one of them away. The arena size in section 3.2 grew by 306,561,024 B as a
   result, and section 9.1's roadmap draft was corrected to match.
2. **The cost ceiling double-counted the fill.** An earlier draft's ceiling was 15.186 s (elapsed less
   compute), which credited residency with removing the fixed cost it still pays. Section 3.4 now
   subtracts the fitted 4.5 s explicitly and the ceiling is 10.686 s / 586,000 ppm.
3. **A floor of 2,000 ppm was quoted from C8 before the ownership question was asked.** C8's section 1
   excludes model throughput in its first sentence, and its floor is calibrated on a 46 ms task.
   Section 3.4 now names this document as the owner of Track B decode performance and derives a
   150,000 ppm floor from STEP-N's own measured 114,000 ppm of run-to-run noise. A floor below the
   noise cannot be measured, and quoting the wrong document's floor would have been exactly that.
4. **The balance invariant was listed as "adjusted".** That is the word R5C's deferral warns about.
   Section 4.3 now names a separate counter pair and a run-scope assertion, so the per-graph check
   keeps its exact meaning instead of being loosened.
5. **Request 35 was first recorded as an unchanged non-blocking citation.** At 4.68 GB its consequence
   is a process abort rather than an unreachable guard, so section 8 raises its priority and section
   3.6 states the abort as a contract row instead of leaving it to be discovered.
6. **The schema number was 3 in four places and 4 in one.** Section 9.4 settles it: 3 if this merges
   first, 4 after KV-PERSIST, and the number is re-checked at merge rather than asserted now. The
   ledger says 3 and section 9.4 is the single place that qualifies it.

### 11.1 Corrections implementation found

The pass above happened before any code existed. These are what building it found, and they are
recorded here rather than folded silently into sections 1 to 4, so that the design and the result
can be read against each other.

7. **The arena's size in section 3.2 is 349,184 B low.** That row computed
   `306,561,024 + 64,512 + 3,923,476,480 + 447,082,496 = 4,677,184,512` from the members' own
   `nbytes`, and omitted that every region starts at the container's `block_align` — **4,096** on
   this pack, not 64. The measured layout is 306,561,024 + 65,536 + 3,923,820,544 + 447,086,592 =
   **4,677,533,696 B**, reproduced independently from `pack.json` by `scripts/run-decode-step`.
   Nothing downstream moves: the budget headroom against `MAX_WINDOW_BYTES` is 45.6 % instead of
   46 %, and the probe of section 2.4 allocated 4,370,560,992 B and the implementation allocates
   4,677,533,696 B, both far below it. Section 9.1's roadmap draft carried the wrong number too and
   the applied text carries the measured one.
8. **`weights.wrap_count` needed a companion.** Section 3.5 gave the `weights` object seven fields.
   The shipped object has nine: `resident_wraps_created` and `resident_wraps_freed` are published
   rather than left implicit, because section 4.3's run-scope invariant is *the* thing the R5C
   deferral asked this capability to re-establish, and an invariant a document does not publish is
   an assertion rather than evidence.
9. **The claim "339 placements per graph" in section 4.2 is a per-graph figure and the document
   publishes the run total.** `window.member_placements` is 678 at `N = 1` (two graph passes over
   the 339 members) and 11,526 at `N = 16`. The oracle is unchanged —
   `pointer_identity_failures == 0` over all of them — but the number a reader will see is not 339.
10. **Decode compute is not reliably invariant under residency.** Section 3.4's cost ceiling
    subtracted 3.049 s of decode compute as a term "which residency does not touch". Across four
    full qualification runs it moved by 44 % once (3.477 s streamed against 4.998 s resident) and by
    6 %, 1 %, and 3 % on the other three; at `N = 1` the excursion is larger and consistent
    (0.168 s streamed against 0.939 s resident on the interleaved run), which is the same
    memory-system effect at the point where the fill dominates the run. Residency changes no arithmetic, so the large excursion is a
    memory-system effect on a host under pressure, not a property of the design; all three are
    reported in section 5.8.1 and all three are netted **into** the elapsed figure, never out of it.
11. **The crossover is around `N = 4`, it is not a clean number, and the design named none.**
    Residency is reliably slower at `N = 1`. At `N = 4` the four runs **disagree about the sign** —
    resident won by 0.68 s at the merged head and lost by 0.99 s on the second pre-merge run and by
    0.13 s on the interleaved run — so `N = 4` is a coin toss on this host rather than a loss. By `N = 16` it is decisive on every run.
    Sections 1.1 and 3.4 argued the claim entirely at `N = 16` and never said where the win begins;
    section 5.8.1 now does, with the disagreement shown rather than averaged away, and it is the
    sharpest practical reason the operand is opt-in rather than a default.

### 11.2 Corrections the first comprehensive review found

The review was two independent adversarial passes over the head at `c73d4b8` — one on the
implementation and the measurement, one on the specification, the measurement, and the governance
surfaces. Twelve numbered findings and their consequences are recorded above where they belong; the
four below changed behaviour or an invariant and are numbered into the same list, because a reader
should not have to know which pass produced a correction to find it.

12. **The run-scope balance assertion fabricated a leak on every resident failure path.** It read
    `resident && (created != 1 || freed != 1)`, and the invariant it is there to protect is
    *balance*, not *presence*. Any resident run that failed before `buffer_from_host` returned —
    the fill raising `R4_PACK_UNREADABLE`, or the wrap itself being refused — created no wrap and
    freed no wrap, and the condition read that as a violation: `graph_balance_failures` rose to 1
    and `released_before_owner_scope_end` went **false** on a run whose teardown was in fact
    perfect. The counters this capability added to answer R5C's deferral would therefore have told
    a reviewer of a real out-of-memory or unreadable-pack incident that the arm leaks. The condition
    is now `created != freed || created > 1`, with a third clause keeping the original "exactly one"
    reading on a **successful** run, which is what risk 9 actually needs. Section 5.10's third,
    fourth, and fifth mutants are the regressions: the wrap never freed, the wrap created twice, and
    the pre-repair condition restored. The last of those is killed by `ds-force-resident-wrap`, the
    early-exit case section 5.11 had retired as unnecessary — the missing case and the wrong
    assertion were the same omission seen from two directions.
13. **`stage_embed_row` bounded its destination against the whole arena.** The check was
    `stage_at + slot * row_bytes + row_bytes > window.len()`, which is true for essentially every
    `slot`, because the stage is followed in the arena by 4.4 GB of layers and head. A slot past
    `MAX_PREFILL_TOKENS` would have been copied **over layer 0's resident weights** rather than
    refused. No input reaches it — `slot` is `piece < tokens.count` in the prefill and the literal
    `0` in the decode step, and `tokens.count <= MAX_PREFILL_TOKENS` is checked long before — so
    this is defence in depth and section 5.10 records honestly that no mutant of it can be killed
    by the current corpus. The function now takes the stage's own span and refuses
    `slot * row_bytes + row_bytes > stage_bytes`, which is the bound the region owns. What the
    corpus *can* pin is the other side of the bound, and now does: `ds-resident-stage-full`
    (section 5.2) is a resident prefill of exactly `MAX_PREFILL_TOKENS` distinct ids compared
    against its streamed twin by oracle R, so the highest slot either call site can produce is
    exercised as a **passing** run over bytes that are checked, and a bound one row too tight would
    be caught.
14. **`plan_resident` computed the arena's size with wrapping arithmetic.** Every other module that
    derives a size from a container's own numbers checks the product before it exists
    (`src/kv_plane.align:130`, `src/alignpack_read.align:197`, `src/alignpack.align:316`), and this
    function multiplied `e.row_bytes * MAX_PREFILL_TOKENS` and accumulated the regions with plain
    `+`. Every input is validated upstream, so nothing reaches it today; the point is that a
    fail-closed idiom used in three places and abandoned in the fourth is not an idiom. The
    arithmetic is now `mul_checked`/`add_checked`/`align_up_checked`, a term that cannot be
    represented poisons the total to `-1`, and `execute`'s existing `region_bytes <= 0` guard
    refuses the run with `R6_RESIDENT_BUDGET` before any allocation — which is, incidentally, the
    first genuinely reachable route to that code.
15. **The stub's reset gating was narrowed one step too far.** Section 5.9 deviation 8 records it:
    dropping the buffer test entirely also dropped the one buffer record that owns arena memory.
16. **`docs/align-development.md` published a pair of elapsed figures that match no recorded run.**
    "19.823 s at `N = 16` against 13.144 s resident" is 336,930 ppm, and no run in section 5.8.1
    produced it. It was neither of the two pre-merge runs and it was not the merged-head run; it
    has no artifact behind it and is treated as a drafting error rather than as a measurement,
    which is the only honest disposition for a number whose provenance cannot be established. The
    section now carries the merged-head figures that section 5.8.1 records, and the reference-host
    paragraph names the run it came from so the next reader can check it against this document.
