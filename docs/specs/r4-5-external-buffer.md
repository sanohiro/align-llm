# R4.5-EXTERNAL-BUFFER-SPIKE: computing a ggml matmul over an Align-owned quantized buffer

Status: design of record for the R4.5 capability.
Owner document for `docs/specs/roadmap.md` section R4.5.
Align pin: `.align-revision` = `4b515f8d37de2e9a9ba06170c5842fd12dc1cba2`.
Predecessor: [`r4-alignpack-layer-major.md`](r4-alignpack-layer-major.md), whose section 5.3 defers
this spike and whose `block_align = 4096` choice exists for it.

This document triggers the proportional design gate of `CLAUDE.md` on four counts: a new public CLI,
a new versioned exchanged document, a new ownership/FFI boundary crossing into a foreign library
that can abort the process, and a new build input (a C shim) in a repository whose hosted image does
not ship ggml. Section 3 is the single public-contract ledger, section 4 is the closure matrix, and
section 5 owns fixtures, qualification, deferrals, and candidate Align requests.

Section 2 is the probe record. It is first on purpose: every contract in section 3 was chosen after
the probe, not before it, and three of the design's decisions exist only because a probe refuted the
plan this document started with.

---

## 1. Purpose, scope, non-goals, and the gate

### 1.1 Goal

`docs/specs/roadmap.md` section R4.5 asks one question: **can quantized weights living in a buffer
Align owns be computed by the ggml backend?** If the answer is no, R5's runtime design — DRAM tier,
VRAM tier, cache slots, CPU fallback — is built on a false premise and has to be reconsidered before
any of it is written. If the answer is yes, R5 inherits a proven boundary and a measured cost.

The capability that answers it is **R4.5-EXTERNAL-BUFFER-SPIKE**: a small executable that reads one
alignpack block with one `pread` into one Align-owned buffer, hands ggml a pointer *into* that
buffer, builds a `mul_mat` against a deterministic activation, computes it on a real backend, and
emits a document that states — as data, not as prose — whether ggml computed over our bytes or over
a copy of them.

The spike is deliberately the smallest thing that can answer the question and still be a real
consumer: it reads a real pack produced by R4, it computes over a real Q4_K tensor from a real
model, and it checks its own output against the original GGUF.

### 1.2 In scope

- A standalone pack reader, `src/alignpack_read.align`, that walks an alignpack v1 container with
  `pread` and the scalar decoders **without the source GGUF**, and exposes one block and its members
  as `pub` data.
- A ggml FFI boundary, `src/ggml_ffi.align`, whose every foreign declaration names exactly one
  library: the repository's own shim.
- Two C shims, `scripts/ggml_shim.c` (real) and `scripts/ggml_shim_stub.c` (ggml-free), so the spike
  executable builds on a host that has never heard of ggml.
- One executable target `ggml-spike` from entry `src/ggml_spike.align`, its CLI, its summary block,
  and the `R4_5_EXTERNAL_BUFFER` document at `schema_version: 1`.
- An in-process reference oracle: the same tensor's bytes read from the original GGUF into a
  **ggml-allocated** buffer, computed with the same graph, compared bit-exactly.
- One owner test that runs without ggml, and one named focused qualification that runs with it.

### 1.3 Non-goals

- **No loader.** The spike reads one block on request. Residency, tiering, eviction, and cache score
  are R5's, exactly as `r4-alignpack-layer-major.md` section 5.4 says.
- **No inference.** One `mul_mat` is the whole graph. There is no attention, no KV cache, no
  sampling, and no token.
- **No dequantization in Align.** The point of the spike is that ggml's kernels read our bytes; an
  Align dequantizer would be a second implementation of a format R4 deliberately stores verbatim.
- **No new container version.** The spike is a pure reader of alignpack v1 as
  `r4-alignpack-layer-major.md` section 2.4 defines it, and it writes nothing to the pack.
- **`src/alignpack.align` is not modified.** Section 3.5 argues the case.
- **No discrete-GPU claim.** Section 2.5 measures a unified-memory GPU. A discrete device is a
  different question and section 5.4 defers it with the evidence that makes it a different question.

### 1.4 Gate statement

The roadmap's gate is four clauses. Each is discharged, deferred, or refuted **individually**, with
the probe that settles it named. A single "the spike passed" verdict would hide that one clause is
answered only for unified memory.

| Gate clause | Verdict | Evidence |
| --- | --- | --- |
| `align owns buffer lifetime` | **Dischargeable.** The bytes live in one Align `buffer` local; ggml holds a borrowed pointer and is torn down before the owner's scope ends | Section 2.3; the ordering contract and its abort case are section 3.9 |
| `no silent copy` | **Discharged.** `ggml_get_data(tensor)` equals the Align buffer's data pointer plus the member's interior offset, exactly | Section 2.3, probe 2b: `identity_weights` = `14336`, the member's own `pack_offset - block.pack_offset` |
| `quantized layout preserved` | **Discharged.** A real Q4_K tensor computes from pack bytes with **zero** differing output elements against the same tensor read from the original GGUF into a ggml-allocated buffer | Section 2.3: `differing_elements = 0` of 14,336 f32 |
| `one expert matmul succeeds` | **Dischargeable for a dense block; deferred for an expert block.** This host's model has no experts | Section 2.3 computes `blk.0.attn_q.weight`; section 5.4 records the MoE deferral, inherited from `r4-alignpack-layer-major.md` section 4.5 |

Two clauses the roadmap implies but does not write are answered here as well:

- **The DRAM half is dischargeable.** Section 2.3.
- **The VRAM half is dischargeable on this host and only because this host has unified memory.**
  Section 2.5 measured the Metal backend accepting the same host pointer with no copy and computing
  the same matmul. On a discrete device `ggml_backend_dev_buffer_from_host_ptr` has no counterpart —
  section 2.5 records the CUDA header's entire public surface as the evidence — so the honest
  verdict is *unified-memory yes, discrete unknown*, and section 5.4 keeps it deferred rather than
  claiming R4.5 answered it.

The spike is therefore **not** expected to send R5 back to the drawing board. What it changes about
R5 is narrower and is recorded in section 5.4: alignment is a *contract*, not an accident, and the
foreign side can abort the process.

---

## 2. Probe record

Everything in this section was executed on this host before section 3 was written. Commands are
given exactly as run. Probe sources live outside the work tree and are not part of the capability;
what ships is section 3's design, and section 5.2's qualification is the probe made reproducible.

### 2.1 Host, toolchain, and library topology

| Item | Value |
| --- | --- |
| Host | `MacBookAir10,1`, Apple M1, 16 GiB, macOS 26.5.2, `darwin/arm64` |
| Align compiler | the managed pinned release toolchain at `4b515f8d37de2e9a9ba06170c5842fd12dc1cba2` |
| llama.cpp | `0.2.0 (build 10566, commit bb4caa754)`, Homebrew |
| ggml | `0.21.0`, Homebrew `ggml` formula, `libggml-base.0.21.0.dylib` / `libggml.0.21.0.dylib` |
| Model | `/Users/hiro/models/qwen2.5-coder-7b-instruct-q4_k_m.gguf`, 4,683,073,536 bytes |
| Pack | built by this branch's `./main --pack`, 4,677,222,400 bytes, 58 blocks, 339 members |

**The first probe result is a topology fact that changed the design, and it is not the one the plan
expected.** The plan assumed `ggml_backend_cpu_init` and `ggml_graph_compute_with_ctx` would be
linkable. They are not.

```text
$ nm -gU /opt/homebrew/lib/libggml-base.dylib | grep -c "T _ggml_"
544
$ nm -gU /opt/homebrew/lib/libggml.dylib | grep -c "T _ggml_"
16
$ ls /opt/homebrew/lib/libggml*
libggml-base.{0.21.0,0,}.dylib   libggml.{0.21.0,0,}.dylib
$ find /opt/homebrew -name 'libggml-cpu*' -o -name 'libggml-metal*'
/opt/homebrew/Cellar/ggml/0.21.0/libexec/libggml-cpu-apple_m1.so
/opt/homebrew/Cellar/ggml/0.21.0/libexec/libggml-cpu-apple_m2_m3.so
/opt/homebrew/Cellar/ggml/0.21.0/libexec/libggml-cpu-apple_m4.so
/opt/homebrew/Cellar/ggml/0.21.0/libexec/libggml-metal.so
/opt/homebrew/Cellar/ggml/0.21.0/libexec/libggml-blas.so
$ nm -gU /opt/homebrew/Cellar/ggml/0.21.0/libexec/libggml-cpu-apple_m1.so \
    | grep -E "ggml_backend_cpu_init|ggml_graph_compute_with_ctx"
00000000000064d0 T _ggml_backend_cpu_init
00000000000060b4 T _ggml_graph_compute_with_ctx
```

There is **no** `libggml-cpu` in the link path. `libggml.dylib` is a nineteen-symbol registry whose
own exports are `dl_load_library`, `dl_get_sym`, and the `ggml_backend_{reg,dev,load,register}*`
family; the CPU, Metal, and BLAS backends are `.so` plugins under `libexec` that
`ggml_backend_load_all()` `dlopen`s at run time. `ggml_backend_cpu_init` and
`ggml_graph_compute_with_ctx` are therefore **not available to a linker** on this host.

**Consequence, and it is a good one.** The design uses the *registry* path throughout —
`ggml_backend_load_all` → `ggml_backend_dev_by_type` → `ggml_backend_dev_init` →
`ggml_backend_dev_buffer_from_host_ptr` → `ggml_backend_graph_compute`. That path is
backend-agnostic by construction, which is why section 2.5's GPU probe is three lines different from
the CPU one rather than a second implementation. `ggml_backend_cpu_buffer_from_ptr` *is* in
`libggml-base` and would have worked, but it hard-codes the CPU and skips the device's own
capability check, so the design does not use it.

### 2.2 Probe 1 — the CPU external-buffer path, from Align

A C reference (`cref.c`) established the flow, then the same flow was written in Align
(`probe1.align`) and run with the pinned compiler:

```text
$ export LIBRARY_PATH=/opt/homebrew/lib:$PWD
$ export DYLD_LIBRARY_PATH=$PWD:/opt/homebrew/lib
$ alignc run probe1.align
3                 # ggml_backend_dev_count(): BLAS, MTL0, CPU
true              # ggml_backend_buffer_get_base(buf) == our raw.alloc pointer
true              # ggml_get_data(A) == our pointer
true              # ggml_get_data(C) == our pointer + 8192
0                 # ggml_backend_graph_compute status == GGML_STATUS_SUCCESS
24                # ggml_nbytes(C)
-2.0 -6.0 -10.0 -1.0 -1.0 -1.0
```

`A` is f32 `[4, 3]`, `B` is f32 `[4, 2]`, `C = ggml_mul_mat(A, B)` is f32 `[3, 2]`. All three
tensors were created in a `no_alloc` context and placed with
`ggml_backend_tensor_alloc(buffer, tensor, addr)` at chosen offsets inside one `raw.alloc(1 MiB)`
block wrapped by
`ggml_backend_dev_buffer_from_host_ptr`. The six outputs equal the hand computation (`A` rows
`1..12`, `B` entries cycling `-1, 0, 1`) exactly.

This settles the mechanism: **`ggml_backend_tensor_alloc` is how a tensor is pointed at caller
memory**, and no `ggml_tallocr` is needed. The shim's `align_ggml_tallocr_new` wrapper, written
because `ggml_tallocr_new` returns a struct by value, turned out to be unnecessary and is not part
of section 3.4's contract.

### 2.3 Probe 2 — a real Q4_K block from a real alignpack

The pack was produced by this branch, and the member was chosen from its own document:

```text
$ ./main --pack ~/models/qwen2.5-coder-7b-instruct-q4_k_m.gguf out/qwen.alignpack out/qwen-pack.json
...
destination: WRITTEN                     # 5.9 s wall, 4,677,222,400 bytes

block 1  AttentionBlock  layer 0  pack_offset 306,606,080  pack_bytes 17,020,928  members 8
  member 1  blk.0.attn_q.weight  ggml_type 12 (Q4_K)  dims [3584, 3584]
            nbytes 7,225,344  pack_offset 306,620,416  source_offset 452,894,720
```

`ne0 = 3584`, and `3584 % 256 == 0`, so the tensor is a whole number of Q4_K super-blocks per row:
`3584 / 256 = 14` blocks × 144 bytes = 2,016 bytes per row × 3,584 rows = 7,225,344 bytes, which is
exactly the recorded `nbytes` and exactly `ggml_nbytes()` of the tensor ggml builds from the
recorded dims. That equality is itself a check that the pack's member table carries enough to size a
member from the pack alone.

**Probe 2a** read the member range directly. **Probe 2b** — the shape the design actually ships —
read the **whole block** with one `pread` and pointed the tensor at the member's interior offset,
`306,620,416 - 306,606,080 = 14,336`:

```text
$ alignc run probe3.align
pread_bytes               17020928          # one pread of the whole block
pread_ns                  4204958
nbytes_a                  7225344           # ggml_nbytes(A) == the pack's recorded nbytes
identity_weights          14336             # ggml_get_data(A) - buffer base, in bytes
identity_out              true              # ggml_get_data(C) == the Align output buffer's base
weights_align_mod_32      0
warm_status               0
compute_status            0
compute_ns                551375            # mean of 5, after one warm-up call
sha_align_owned           2ccc7dc778108df3b626128895347f203795a2d82b502805806fb8472457e044
ref_pread_bytes           7225344
bytes_equal_pack_vs_gguf  true
ref_compute_status        0
ref_compute_ns            610667
differing_elements        0                 # of 14,336 f32
first_difference          -1
```

Read this line by line, because each line is one gate clause or one design decision:

- `identity_weights 14336` is the **no-silent-copy proof**, and it is stronger than an equality
  would be. ggml is computing from a pointer 14,336 bytes into an allocation Align made and Align
  will free. A copy would have produced any other number.
- `identity_out true` means the **output** tensor is also Align-owned, which is what makes
  `sha_align_owned` computable: `crypto.sha256` needs a byte view, and there is no view over foreign
  memory. Section 3.7 turns this into the document's checksum contract.
- `bytes_equal_pack_vs_gguf true` is `crypto.constant_time_equal` over the member's 7,225,344 pack
  bytes and the same range read from the original GGUF at `source_offset`. R4's gate already
  promised this; the spike re-checks it because the reference arm's meaning depends on it.
- `differing_elements 0` is the **quantized-layout-preserved proof**. The reference arm builds an
  identical graph in a second context whose tensors are allocated by
  `ggml_backend_alloc_ctx_tensors` — ggml's own memory — and fills the weights with
  `ggml_backend_tensor_set` from the GGUF bytes. Zero of 14,336 output f32 differ **in their bit
  patterns**, compared as `i32`, not with a tolerance.
- The digest `2ccc7dc7…e044` is identical in probe 2a (member-only read) and probe 2b (whole-block
  read) and across repeated runs, which is what makes it a usable document field.

Timings, three runs of probe 2a and one of probe 2b, on a warm page cache:

| Measurement | Values |
| --- | --- |
| `pread` of the member, 7,225,344 B | 2,329,458 / 1,119,083 / 940,333 ns |
| `pread` of the whole block, 17,020,928 B | 4,204,958 ns |
| compute, Align-owned weights, mean of 5 after warm-up | 413,508 / 433,991 / 551,375 ns |
| compute, ggml-owned weights, single call | 471,792 / 459,042 / 610,667 ns |

The first compute call of a process costs about **4.6 ms** against a steady-state **0.41 ms**; the
difference is the CPU backend's thread-pool spin-up, which is why section 3.6 makes the warm-up call
part of the contract and section 3.7 reports the warm mean rather than a first-call number. A
separate C harness measured the two arms directly against each other, five iterations each after a
warm-up: **0.427 ms external, 0.423 ms internal**. There is no measurable penalty for computing out
of caller memory, which is the expected result for a backend that was handed a pointer.

### 2.4 Probe 3 — alignment, and the two aborts

Two probes were run specifically to find where the foreign side kills the process.

**`ggml_backend_cpu_buffer_from_ptr` aborts on a pointer that is not 32-byte aligned.** Not an error
return — `abort()`:

```text
$ ./misal cpu 8
try cpu off=8 ptr%16384=8
src/ggml-backend.cpp:2441: GGML_ASSERT((uintptr_t)ptr % TENSOR_ALIGNMENT == 0
                                       && "buffer pointer must be aligned") failed
```

**Align does not promise the alignment that assert requires.** Measured with the pinned compiler:

```text
$ alignc run probe_align2.align
cap        addr % 16384   addr % 32
64         9312           0
144        10496          0
2016       10496          0
4096       10496          0
14336      0              0
65536      0              0
1032192    0              0
7225344    0              0
raw.alloc(7225344) % 16384 -> 0, 0, 0, 0
raw.alloc(64)      % 32    -> 0
```

Every observed allocation happened to be 32-byte aligned, and every allocation at or above the page
size happened to be page-aligned — both are properties of this platform's `malloc`, not of Align. A
separate probe confirmed that two lowerings of the same `b.bytes()` yield the **same** pointer, so
the value is stable within a scope; nothing makes it aligned.

**Consequence: the design validates alignment before every call that could assert on it**, and
returns `R4_5_ALIGNMENT` rather than letting a `GGML_ASSERT` take the process down (section 3.8 step
9). This is the single most important thing the probes found, because the failure it prevents is a
crash with no document.

**The second abort is a lifetime abort, and it is at process exit.** An early Metal probe that
created a host-pointer buffer and never freed it aborted during `exit`:

```text
src/ggml-metal/ggml-metal-device.m:657: GGML_ASSERT([rsets->data count] == 0) failed
  ... ggml_metal_device_free ... __cxa_finalize_ranges ... exit
```

Freeing the buffer before exit removed it. Section 3.9 makes the teardown order a contract for that
reason: a leaked ggml buffer is not a leak on this backend, it is a crash.

### 2.5 Probe 4 — the GPU half, which the plan expected to be N/A

The plan predicted `ggml-metal.h` would expose no `buffer_from_ptr` and the VRAM half would be N/A.
The header prediction is **correct** and the conclusion drawn from it is **wrong**:

```text
$ grep -c "from_ptr\|from_host" /opt/homebrew/include/ggml-metal.h
0
$ nm -gU .../libexec/libggml-metal.so | grep -c "from_ptr\|from_host"
0
```

Metal exposes no *backend-specific* entry point — but the device-generic one is a capability flag,
and the Metal device sets it:

```text
$ ./metalprobe
dev BLAS  type=3  async=0  host_buffer=0  buffer_from_host_ptr=1  events=0
dev MTL0  type=1  async=1  host_buffer=0  buffer_from_host_ptr=1  events=1
dev CPU   type=0  async=0  host_buffer=0  buffer_from_host_ptr=1  events=0
metal buffer_from_host_ptr -> 0x803011f00
  base=0x802418000 mine=0x802418000 same=1
```

And it computes. The same real Q4_K block, three arms, five iterations each after a warm-up:

```text
$ ./metalq4
cpu-external: external identity=1 base=0x59f800000 ptr=0x59f800000
cpu-external: status ok, 0.427 ms/iter
cpu-internal: status ok, 0.423 ms/iter
gpu-external: external identity=1 base=0x59f800000 ptr=0x59f800000
gpu-external: status ok, 1.088 ms/iter
cpu-ext vs cpu-int differing=0 ; cpu vs gpu differing=14336 maxabsdiff=0.0290456
```

Three facts, and the third is why section 3 does not ship a GPU arm:

1. **Metal takes the pointer with no copy.** `base == ptr` for a page-aligned host allocation, on
   Apple Silicon's unified memory, through `newBufferWithBytesNoCopy` under the hood.
2. **It is 2.5× slower than the CPU here.** At `N = 4` this matmul is memory-bound and tiny; the
   number is a fact about this shape, not about Metal, and it is recorded so nobody quotes it as a
   backend comparison.
3. **GPU output is not bit-identical to CPU output** — all 14,336 elements differ, max absolute
   difference 0.029 on values of order 1. That is accumulation order, not corruption. It means the
   bit-exact reference oracle of section 3.6 **cannot** be reused for a GPU arm; a GPU arm needs a
   tolerance contract, which is a different design decision with a different acceptance rule.

Alignment differs too: Metal accepted an 8-byte-offset pointer where the CPU aborted, so the two
backends do not share a validation rule.

For a discrete device there is no equivalent at all. The complete public surface of
`/opt/homebrew/include/ggml-cuda.h` is eleven functions, and the only host-memory ones are
`ggml_backend_cuda_host_buffer_type`, `ggml_backend_cuda_register_host_buffer`, and
`ggml_backend_cuda_unregister_host_buffer` — page-locking host memory for faster *transfer*, not
computing in place. So: **unified memory, yes, measured; discrete VRAM, unanswered, and this host
cannot answer it.** Section 5.4 defers it with that evidence rather than recording a verdict.

### 2.6 What the probes settle about the Align FFI surface

Each row was verified against the pinned compiler, by compiling the case, not by reading the guide.

| Question | Answer at the pin | Evidence |
| --- | --- | --- |
| `extern "C" link("name") { … }`, called inside `unsafe` | **Works**, one library per block, several blocks compose | probe 1 links `ggml`, `ggml-base`, and the shim from three blocks |
| `raw.alloc / free / load / store / offset / null`, `p.is_null()` | **Work**, exactly the six operations plus the predicate | probe 1 |
| `slice<u8>` as an FFI parameter lowers to its data pointer | **Yes**, and two lowerings of the same `b.bytes()` give the **same** pointer | `probe_align.align`: `v1 == v2` is `true` |
| A **sub-slice** `b.bytes()[k..k+n]` lowers to `base + k` | **Yes.** This is how an interior member is addressed | probe 2b: `identity_weights` = `14336` |
| `layout(C)` struct **by value** across FFI on `arm64-apple-darwin` | **Rejected at codegen**, with an explicit diagnostic — for 16 bytes *and* 24 | section 3.1 |
| A `layout(C)` struct with a **`raw` field** | **Rejected at sema.** `struct ggml_init_params` cannot be declared in Align at all | section 3.1 |
| `bool` as an FFI return type | **Rejected at sema** | section 3.1 |
| `raw` → integer, or `==` on two `raw` values | **Absent.** The shim reports addresses as `i64` | `align_ptr_addr`, section 3.4 |
| An aligned heap allocation | **Absent.** Neither `raw.alloc(n)` nor `buffer(n)` takes an alignment | section 2.4, candidate Request 33 |
| `f.pread(b: mut buffer, off)`, `fs.open_rw`, `f.len()` | **Work**, unchanged from R4 section 2.1 | probe 2 |
| `crypto.sha256`, `crypto.constant_time_equal`, `encoding.hex_encode`, `time.instant` | **Work**, unchanged from R4 section 2.1 | probe 2 |
| Conditional compilation, target predicates, `cfg` | **Absent from the language.** Nothing can make a `link` clause conditional | section 3.2 |

---

## 3. Public-contract ledger

### 3.1 The three FFI rejections that force a C shim, verified at the pin

The plan assumed the shim existed only to wrap `ggml_init`'s 24-byte by-value struct. It is worse
than that, and the exact diagnostics matter because they are what section 5.5 asks Align to change.

**By value is rejected on this target, at 16 bytes as well as 24.** Both cases were compiled against
a real C library:

```text
$ alignc run probe_byval2.align     # layout(C) Pair { a: i64, b: i64 }  — 16 bytes
alignc: codegen failed for unit `probe_byval2`: lowering failed: extern 'some_c_fn' passes or
returns a struct by value, which is only supported on x86-64 SysV (Linux) — the target is
'arm64-apple-darwin25.5.0'; pass the struct by pointer (`raw`) instead

$ alignc run probe_byval3.align     # layout(C) Big { a: i64, b: i64, c: i64 } — 24 bytes
alignc: codegen failed for unit `probe_byval3`: lowering failed: extern 'big_fn' passes or returns
a struct by value, ... pass the struct by pointer (`raw`) instead
```

**The diagnostic's own advice does not work here, and that is the decisive finding.** It says to
pass the struct by pointer. `struct ggml_init_params` is
`{ size_t mem_size; void * mem_buffer; bool no_alloc; }` — and a `layout(C)` struct with a pointer
field cannot be *declared*:

```text
$ alignc check probe_byval.align
error: struct field type is not supported here, got raw
error: a `layout(C)` struct field must be an integer or float (got raw) — other field types are a
       later FFI slice
```

So there is no by-pointer fallback either. The struct could be assembled byte-wise with `raw.store`
— `raw` *is* an admitted store value — but `ggml_init` takes it **by value**, so an assembled buffer
cannot be passed. `ggml_init` is unreachable from Align at this pin by any route.

**`bool` is rejected as an FFI type**, which removes `ggml_backend_dev_supports_op` and every other
predicate from direct reach:

```text
$ alignc check probe_bool.align
error: 'bool' is not an FFI-safe return type for an extern (use an integer, float, `raw`,
       a `layout(C)` struct, or `()`)
```

A C shim is therefore **not a convenience**. It is the only way to call ggml from Align at this pin.
Section 5.5 records this as candidate Request 32.

### 3.2 The build-input decision

**Constraint.** `make build` builds `src/main.align`, whose import graph is linked as one
executable. A `link("ggml")` clause anywhere in that graph puts `-lggml` on every link of `main`.
Align has **no conditional compilation** (section 2.6), so a `link` clause cannot be made
conditional in source. The hosted fresh image has no ggml, no ggml headers, and no reason to grow
them.

Four candidates were considered and three are rejected:

| Candidate | Verdict |
| --- | --- |
| `main --ggml-spike …`, ggml linked into `main` | **Rejected.** Breaks `make build` and every hosted target that depends on it, on every host without ggml |
| `main --ggml-spike …`, guarded by an environment variable | **Rejected.** There is nothing to guard with: the link clause is compile-time and unconditional |
| A separate `ggml-spike` executable, linked against ggml only when present | **Rejected.** `make ggml-spike-smoke` would then have nothing to run on a hosted host, so the owner test would degrade to `alignc check`, which does not link and does not execute one line of the reader |
| **A separate `ggml-spike` executable whose Align source links exactly one library — the repository's own shim — built from the real shim when ggml is present and from a ggml-free stub otherwise** | **Chosen** |

**The decision: `src/ggml_spike.align` is its own entry and its own executable, and
`src/ggml_ffi.align` declares `link("align_ggml_shim")` and nothing else.**

This is better than the alternatives on four counts, and the fourth is why it wins:

1. **`make build` is untouched.** `src/main.align`'s import graph does not reach
   `src/ggml_ffi.align` at all. No existing target changes, and `check-gate-topology` sees one new
   hosted target and one new capable-only target.
2. **One funnel.** Every foreign call crosses at exactly one C file compiled against the host's own
   ggml headers, so ABI drift (section 5.6) has one blast radius and one place to fix.
3. **The shim can fail closed where Align cannot.** Alignment validation, `bool` translation,
   by-value struct construction, and null checks all happen in C, before the call that would abort.
4. **The owner test runs the whole CLI on a hosted host.** Linked against
   `scripts/ggml_shim_stub.c`, `ggml-spike` is a complete executable that reads packs, validates
   indices, walks the whole validation order of section 3.8, and stops at step 10 with
   `R4_5_GGML_UNAVAILABLE`. Steps 1–9 — the pack reader, every index and shape and alignment check,
   every error code the reader can raise — are exercised for real, without ggml, in hosted CI.

The stub is real code with a real contract, not a placeholder: every entry point returns the
`R4_5_GGML_UNAVAILABLE` status and writes nothing, and section 4.4 gives it its own closure column.

**Make targets.**

```text
ggml-spike-build        # alignc build src/ggml_spike.align, after making libalign_ggml_shim
ggml-spike-smoke        # hosted; stub shim; ./scripts/run-ggml-spike-smoke
ggml-spike-qualification # capable-only, opt-in; real shim; ./scripts/run-ggml-spike
```

`ggml-spike-smoke` joins `HOSTED_CHECK_TARGETS`. `ggml-spike-qualification` joins **neither** list,
exactly as `alignpack-qualification` does not (`Makefile:146-152`), and prints an explicit `N/A`
line with a reason when `ALIGN_LLM_GGML_LIB`, `ALIGN_LLM_GGML_INCLUDE`, or `ALIGN_LLM_GGUF_MODEL` is
unset or absent.

The shim is built by a Makefile rule into `build/lib/libalign_ggml_shim.{dylib,so}`, which is
`.gitignore`d; `LIBRARY_PATH` and the run-time loader path are set by the two scripts, not by a
developer's shell. Selection is by presence of `ALIGN_LLM_GGML_INCLUDE`: set → real shim, unset →
stub. There is no third state and no automatic probing of `/opt/homebrew`, because a build input
that changes with the contents of a directory is not reproducible.

### 3.3 CLI surface

```text
ggml-spike PACK.alignpack BLOCK MEMBER                     # document to stdout
ggml-spike PACK.alignpack BLOCK MEMBER DOC.json            # document to DOC.json + summary
ggml-spike PACK.alignpack BLOCK MEMBER DOC.json REF.gguf   # + the reference arm
ggml-spike PACK.alignpack BLOCK MEMBER - REF.gguf          # reference arm, document to stdout
```

Exactly three, four, or five operands. Arity is checked before any path or file work, so an arity
failure produces no output and no file. The `MAX_PATH_BYTES` lexical guard — non-empty, `<= 4096`
bytes, no NUL — applies to every path operand before anything is opened, reusing
`src/main.align:624`'s rule. `-` in the fourth position means "document to stdout" and is the R0
convention for a value that does not exist; it exists so the reference arm is reachable without
naming a document path.

**`BLOCK` and `MEMBER` are two indices, not one.** `BLOCK` indexes the block table, which
`r4-alignpack-layer-major.md` section 2.4.3 fixes as the Model IR block index. `MEMBER` is the
member's position **within that block**, in `[0, block.member_count)`, not a global member-table
index. The reason is that the spike's whole point is R4's contiguity property: it reads
`block.pack_bytes` at `block.pack_offset` with **one** `pread`, and then addresses the member at an
interior offset. A global member index would have made the block invisible, and the block is the
thing R4 built.

Both are parsed as non-negative decimal integers with no sign, no leading `+`, and no whitespace;
anything else is `R4_5_INDEX`.

**There is no `--backend` flag and no GPU arm.** Section 2.5 measured that a GPU arm needs a
different alignment rule and a tolerance-based oracle rather than the bit-exact one; adding a flag
whose two values have different acceptance contracts would be two capabilities wearing one name.
Section 5.4 defers it.

The summary block, in this exact order, printed only in the four- and five-operand forms:

```text
ggml spike:
status:            OK | ERROR
verdict:           EXTERNAL | COPIED | UNAVAILABLE
pack path:         <sanitized path>
schema:            1
block:             <integer>
member:            <integer>
name:              <member name, sanitized>
ggml type:         <integer>
dims:              <ne0>x<ne1>
member bytes:      <integer>
block bytes:       <integer>
data offset:       <integer>            # ggml_get_data(A) - buffer base, in bytes
buffer align:      <integer>            # buffer base modulo 32
pread ns:          <integer>
compute ns:        <integer>            # warm mean
output sha256:     <64 hex characters>
output bit sum:    <integer>
reference:         IDENTICAL | MISMATCH | -
first difference:  <element index, or ->
released:          <integer>            # ggml objects released, section 3.9
error:             <code>               # only when status is ERROR
detail:            <identifier>         # only when status is ERROR
```

`verdict` is the gate's second clause as a single word: `EXTERNAL` when the tensor's data pointer
lies inside the Align buffer at exactly the member's interior offset, `COPIED` when it does not,
`UNAVAILABLE` when no compute happened. Exit is R0's mapping, reused verbatim: `Ok(())` on
`status: "ok"`, `Err(Error.Invalid)` after an error document has been emitted, `Err` with no
document for an
arity, path, or OS failure. Both output forms emit **byte-identical document bytes**.

**`COPIED` is a successful run, not an error.** If a future ggml copies the bytes, the spike must
say so in a document rather than fail; a design that could only report success would not be able to
report the answer the roadmap actually asked for.

### 3.4 The shim contract — `scripts/ggml_shim.c` and `scripts/ggml_shim_stub.c`

One C translation unit, one library, no ggml type in any signature. Every function returns an
`int32_t` status or a scalar; handles cross as `void *`. `0` is success, negative values map to the
`R4_5_*` codes of section 3.8.

| Symbol | Signature | Contract |
| --- | --- | --- |
| `align_ggml_available` | `int32_t (void)` | `1` in the real shim, `0` in the stub. The **only** difference a caller can observe before any state exists |
| `align_ggml_abi_probe` | `int32_t (int32_t *tensor_align, int32_t *q4k_blck, int32_t *q4k_type_size)` | Returns `TENSOR_ALIGNMENT`, `ggml_blck_size(Q4_K)`, `ggml_type_size(Q4_K)` from the linked ggml. Section 5.6's drift guard |
| `align_ggml_backend_open` | `int32_t (void **backend, void **device)` | `ggml_backend_load_all`, then `ggml_backend_dev_by_type(GGML_BACKEND_DEVICE_TYPE_CPU)`, then `ggml_backend_dev_init(dev, NULL)`. Fails closed if either is `NULL` |
| `align_ggml_backend_close` | `void (void *backend)` | `ggml_backend_free` |
| `align_ggml_context_open` | `int32_t (void **ctx, int64_t mem_bytes)` | Wraps `ggml_init`, which is unreachable from Align (section 3.1). `no_alloc` is always true |
| `align_ggml_context_close` | `void (void *ctx)` | `ggml_free` |
| `align_ggml_type_ok` | `int32_t (int32_t type, int64_t ne0)` | `bool` translation (section 3.1). Checks the type is a valid `ggml_type`, is supported as a `mul_mat` left operand, and that `ne0 % ggml_blck_size(type) == 0` |
| `align_ggml_buffer_from_host` | `int32_t (void **buffer, void *device, const void *ptr, int64_t size)` | **Validates `(uintptr_t)ptr % TENSOR_ALIGNMENT == 0` and `size > 0` and returns a status** rather than letting `GGML_ASSERT` abort (section 2.4) |
| `align_ggml_buffer_free` | `void (void *buffer)` | `ggml_backend_buffer_free`. Mandatory, not optional (section 2.4's second abort) |
| `align_ggml_new_tensor_2d` | `int32_t (void **tensor, void *ctx, int32_t type, int64_t ne0, int64_t ne1)` | |
| `align_ggml_tensor_place` | `int32_t (void *buffer, void *tensor, const void *addr)` | `ggml_backend_tensor_alloc`, with the same alignment pre-check applied to `addr` |
| `align_ggml_alloc_remaining` | `int32_t (void **buffer, void *ctx, void *backend)` | `ggml_backend_alloc_ctx_tensors` — the activation tensor, and in the reference arm every tensor |
| `align_ggml_tensor_set` | `int32_t (void *tensor, const void *data, int64_t offset, int64_t size)` | Bounds-checked against `ggml_nbytes` before the call |
| `align_ggml_mul_mat` | `int32_t (void **out, void *ctx, void *a, void *b)` | |
| `align_ggml_compute` | `int32_t (void *backend, void *ctx, void *result)` | Builds a fresh graph, `ggml_build_forward_expand`, `ggml_backend_graph_compute`; returns the `ggml_status` |
| `align_ggml_tensor_nbytes` | `int64_t (void *tensor)` | |
| `align_ggml_tensor_data_offset` | `int64_t (void *tensor, const void *base)` | `(char *)ggml_get_data(t) - (const char *)base`. The pointer-identity verdict, computed in C because Align has neither a `raw`-to-integer cast nor `==` on `raw` |
| `align_ptr_offset` | `int64_t (const void *a, const void *b)` | Same, for buffer bases |

**The shim allocates no weight memory and owns no file.** It never calls `malloc` for anything the
document describes, never opens a path, and never reads a byte the caller did not hand it. Every
byte ggml computes over came from an Align `buffer` filled by `f.pread`. That is what makes the
"Align owns the buffer" clause true rather than nominal.

`align_ggml_abi_probe` exists because the shim is compiled against whatever ggml headers the host
has. If `TENSOR_ALIGNMENT`, `ggml_blck_size(Q4_K)`, or `ggml_type_size(Q4_K)` ever changes, the
qualification fails on the probe rather than on a wrong answer. The three expected values on this
host are `32`, `256`, and `144`.

### 3.5 The pack reader — `src/alignpack_read.align`

A new module, `pub`, owning the **standalone** walk of an alignpack v1 container:

```text
pub fn open_pack(borrow f: file) -> Result<PackIndex, Fault>
pub fn block_count(borrow x: PackIndex) -> i64
pub fn block_at(borrow x: PackIndex, index: i64) -> Result<PackBlock, Fault>
pub fn member_at(borrow x: PackIndex, borrow b: PackBlock, within: i64) -> Result<PackMember, Fault>
pub fn member_name(borrow x: PackIndex, borrow m: PackMember) -> str
```

`PackIndex` holds the decoded 128-byte header, the name stream as one owned `string`, and the block
table as `array<i64>` columns — the `GgufTable` / `BlockPlan` / `PackPlan` shape, fifth instance.
The **member table is not loaded**: `block_at` gives `member_start` and `member_count`, and
`member_at` reads exactly one 96-byte record at
`member_table_offset + (member_start + within) * 96`. That is what
`r4-alignpack-layer-major.md` section 2.4.2's fixed record widths are for, and it means a
99,139-member container costs one 96-byte read, not a table walk.

**`src/alignpack.align` is not modified, and the reason is a contract argument, not laziness.**
Section 5.4 of that document says "when R5 lands, `src/alignpack.align`'s decoder is the natural
thing to make `pub`". Its decoder is
`decode_pack(pak, window, counters, header, expected: PackPlan)`: it decodes the pack **against an
expected plan derived from the source GGUF**, because its consumer is the verifier. Making that
`pub` would export a reader that cannot read a pack unless you already have the model it came from —
precisely the property section 2.4.4 of that document
calls "the difference between a container and an index". R4.5 needs the opposite: a reader that
works from the pack alone. So R4.5 writes the reader R5 will grow into and leaves R4's verifier
decoder exactly where it is.

The cost is that the v1 field offsets are now written in two places. The design names the risk and
binds it with a regression rather than pretending it away: `run-ggml-spike-smoke` compares the
reader's decoded header, block record, and member record against `scripts/alignpack_reader.py` — the
independent Python reader R4 already ships as its oracle — on every fixture. A drift between the two
Align decoders shows up as a disagreement with a third implementation that shares no code with
either.

Codes are `R4_PACK_*`, **surfaced verbatim**, reusing R4's vocabulary because it is the same format
and a second name for `R4_PACK_MAGIC` would be a second truth. The reader raises `R4_PACK_MAGIC`,
`R4_PACK_VERSION`, `R4_PACK_HEADER`, `R4_PACK_REGION`, `R4_PACK_RESERVED`, `R4_PACK_OFFSET`,
`R4_PACK_UNREADABLE`, and `R4_WINDOW_UNAVAILABLE` with the meanings `r4-alignpack-layer-major.md`
section 2.8 gives them.

The reader validates, in this order: magic; `format_version == 1`; `header_bytes == 128` and the
three record widths; `block_align` and `member_align` powers of two in range with
`member_align <= block_align`; `flags == 0`; `f.len() == total_bytes`; region containment and
pairwise disjointness; `payload_offset` is `block_align`-aligned. It does **not** verify payload
bytes against a source, does not recompute the source-identity digest, and does not check padding —
those are
`--pack-verify`'s and remain there.

### 3.6 The computation, and what makes it reproducible

Given block `B` and member `M`:

1. One `pread` of `B.pack_bytes` at `B.pack_offset` into `weights: buffer(B.pack_bytes)`, completing
   short reads in `gguf.refill`'s discipline. `interior = M.pack_offset - B.pack_offset`.
2. `A` is a 2-D tensor of `M.ggml_type` with `ne0 = M.dim0`, `ne1 = M.dim1`, placed at
   `weights.bytes()[interior .. interior + M.nbytes]`.
3. `activation` is f32 `[M.dim0, 4]`, defined **exactly** as `act[j] = ((j mod 17) - 8) / 8` as f32,
   `j` in `[0, M.dim0 * 4)` in ggml's element order, built with `put_f32_le` and copied in with
   `align_ggml_tensor_set`.
4. `C = mul_mat(A, activation)`, f32 `[M.dim1, 4]`, placed in a **second Align-owned** buffer
   `output: buffer(M.dim1 * 4 * 4)`.
5. One warm-up `align_ggml_compute`, then five timed calls; `compute_ns` is their mean.

`N = 4` because one column is a degenerate matrix-vector shape whose kernel differs from the batched
one, and four is enough to exercise the batched path while keeping the output at 57,344 bytes —
small enough to digest and compare without a second window.

**The output tensor is Align-owned because the checksum requires it.** `crypto.sha256` takes a byte
view and there is no view over foreign memory, so a ggml-allocated output would have to be copied
into a `buffer` before it could be hashed — a copy the design would then have to explain. Owning the
output removes the copy and adds a second, independent instance of the pointer-identity property.

**Reference arm** (five-operand form only): a second context in which **every** tensor is allocated
by `align_ggml_alloc_remaining` — ggml's own memory — with the weights filled by
`align_ggml_tensor_set` from `M.nbytes` read from the GGUF at `M.source_offset`, and the identical
activation. Its output is compared to the primary arm's **bit-exactly**, as `i32` element pairs.
Before that, the pack bytes and the GGUF bytes are compared with `crypto.constant_time_equal`; if
they differ, the arm reports `R4_5_SOURCE_DIVERGED` and never runs, because a numeric comparison
between two different tensors would name the wrong cause.

The oracle is bit-exact and not tolerance-based because both arms run the same kernel on the same
backend over the same bytes. Section 2.5 measured that this is only true within one backend; a GPU
arm would need a different rule, which is why it is deferred and not flagged.

### 3.7 `R4_5_EXTERNAL_BUFFER`, `schema_version: 1`

Canonical UTF-8 JSON in declaration order, in the R0/R1/R2A/R4 shape: `schema_version`, `kind`,
paths, `status`, `error_code`, `error_detail`, then the payload objects.

```text
schema_version    1
kind              "R4_5_EXTERNAL_BUFFER"
pack_path         string
reference_path    string, "" when the reference arm did not run
status            "ok" | "error"
error_code        string, "" when ok
error_detail      string, "" when ok
verdict           "EXTERNAL" | "COPIED" | "UNAVAILABLE"

pack              format_version, block_align, member_align, block_count, member_count,
                  total_bytes, payload_offset
selection         block_index, member_index_in_block, member_index_global, name,
                  kind, layer, expert, role_id
tensor            ggml_type, n_dims, ne0, ne1, nbytes,
                  blck_size, type_size, elements_per_row_ok (bool)
buffer            block_pack_bytes, block_pack_offset, member_pack_offset, interior_offset,
                  base_alignment, tensor_data_offset, pointer_identity (bool),
                  output_bytes, output_base_alignment, output_pointer_identity (bool)
compute           backend_name, status, warmup_calls, timed_calls
output            sha256 (64 hex), bit_sum, element_count, nonfinite_count
reference         present (bool), bytes_equal (bool), verdict,
                  differing_elements, first_difference_index,
                  first_difference_primary_bits, first_difference_reference_bits
timings           pread_ns, compute_ns, reference_pread_ns, reference_compute_ns, elapsed_ns
lifetime          ggml_buffers_created, ggml_buffers_freed, contexts_created, contexts_freed,
                  backends_created, backends_freed, released_before_owner_scope_end (bool)
abi               tensor_alignment, q4k_blck_size, q4k_type_size
```

**`tensor_data_offset` and `pointer_identity` are the gate's second clause as data.**
`pointer_identity` is `tensor_data_offset == interior_offset`, computed from
`align_ggml_tensor_data_offset(tensor, weights.bytes())`. On this host, section 2.3, that is
`14336 == 14336`.

**Two checksums, and neither is a float.** This repository has no float formatting contract
(`r4-alignpack-layer-major.md` section 2.3), so "the sum of the f32 output" is not a renderable
value. Instead:

- `output.sha256` is `crypto.sha256` over the **exact little-endian f32 bytes** of the output
  tensor, hex-encoded. It is the primary checksum: bit-exact, byte-order-explicit, and it does not
  depend on any interpretation of the bits. Measured here:
  `2ccc7dc778108df3b626128895347f203795a2d82b502805806fb8472457e044`, identical across three runs
  and identical between the member-only and whole-block read shapes.
- `output.bit_sum` is the `i64` sum of the output's `element_count` **u32 bit patterns**. It is an
  exact integer, it needs no float formatting, and it is a cheap human-comparable value when two
  digests differ and someone wants to know whether the difference is one element or all of them.
- `output.nonfinite_count` counts elements whose exponent field is all ones. It is reported, never
  used as a failure condition: a NaN in an output is a fact about the weights and the activation,
  not a defect of the buffer boundary, and the spike does not get to decide otherwise.

`elements_per_row_ok` is `ne0 % blck_size == 0`, carried because a false value is exactly the
`R4_5_SHAPE` condition and a reader should not have to recompute it.

`schema_version` is `1` and nominal. A consumer keys on `kind` plus `schema_version`.

### 3.8 Validation order and error codes

First applicable row wins. Steps 1 and 2 return `Err` with no output at all. Steps 3 onward produce
a `status: "error"` document and then map to `Err(Error.Invalid)`. **No ggml state is created before
step 10, and nothing outside the process is ever written.**

1. CLI selector and exact arity — three, four, or five operands. → `R4_5_ARITY`
2. Lexical path validation of every path operand: non-empty, `<= 4096` bytes, no NUL. `-` is a valid
   fourth operand and is not a path. → `R4_5_PATH`
3. `BLOCK` and `MEMBER` parse as non-negative decimal integers. → `R4_5_INDEX`
4. Pack open (`fs.open_rw`) and header decode, then region validation, per section 3.5. →
   `R4_PACK_*` verbatim
5. `BLOCK < block_count`. → `R4_5_INDEX`, detail `block[<n>]`
6. `MEMBER < block.member_count`, and `member_start + member_count <= member_count(header)`. →
   `R4_5_INDEX`, detail `member[<n>]`
7. Member shape: `n_dims == 2`, `dim0 >= 1`, `dim1 >= 1`, `dim2 == 1`, `dim3 == 1`, `nbytes >= 1`,
   and the member's range inside its block. → `R4_5_SHAPE`
8. Window availability: `buffer(block.pack_bytes)` and `buffer(dim1 * 16)` did not degrade to
   capacity 0 (R4 section 2.1's silent-degradation case). → `R4_WINDOW_UNAVAILABLE`
9. One `pread` of the block, completing short reads. → `R4_PACK_UNREADABLE`
10. `align_ggml_available()`. → `R4_5_GGML_UNAVAILABLE`, `verdict: "UNAVAILABLE"`. **This is where
    the stub shim stops, and steps 1–9 are therefore fully reachable without ggml.**
11. `align_ggml_abi_probe`: `tensor_alignment`, `blck_size(Q4_K)`, `type_size(Q4_K)` are recorded. →
    `R4_5_ABI` if any is non-positive
12. `align_ggml_type_ok(type, ne0)`: the type is valid and usable as a `mul_mat` left operand. →
    `R4_5_TYPE_UNSUPPORTED`, detail `type[<id>]`; and `ne0 % blck_size != 0` → `R4_5_SHAPE`, detail
    `ne0[<value>]%blck[<value>]`
13. **Alignment**, before any call that can assert: the weights buffer's base **and**
    `base + interior_offset` **and** the output buffer's base are each `0 mod tensor_alignment`. →
    `R4_5_ALIGNMENT`, detail `weights` / `member` / `output`. Section 2.4 is why this step exists
14. Backend and context creation. → `R4_5_GGML_INIT`, detail `backend` / `device` / `context`
15. Buffer creation, tensor creation, placement, activation allocation and fill. → `R4_5_GGML_INIT`,
    detail naming the object
16. `align_ggml_compute`, warm-up then five timed calls; any non-zero `ggml_status`. →
    `R4_5_COMPUTE`, detail `status[<n>]`
17. Reference arm, five-operand form only: open the GGUF, read `M.nbytes` at `M.source_offset`. →
    `R4_5_SOURCE_UNREADABLE`
18. Reference arm: pack bytes equal GGUF bytes. → `R4_5_SOURCE_DIVERGED`, detail `member@<offset>`
19. Reference arm: build, compute, compare bit-exactly. → `R4_5_REFERENCE_MISMATCH`, detail
    `element[<index>]`, with both bit patterns in the document
20. Teardown in the order of section 3.9, then render, then write.

| Code | Meaning | Step | Detail |
| --- | --- | --- | --- |
| `R4_5_ARITY` | wrong operand count | 1 | `N/A` — no document exists |
| `R4_5_PATH` | a path operand is empty, too long, or contains NUL | 2 | `N/A` — no document exists |
| `R4_5_INDEX` | an index does not parse or is out of range | 3, 5, 6 | `block[<n>]` / `member[<n>]` |
| `R4_PACK_*` | a container defect, surfaced verbatim from `alignpack_read` | 4, 9 | R4's own details |
| `R4_WINDOW_UNAVAILABLE` | `buffer(N)` degraded to capacity 0 | 8 | `weights` / `output` / `activation` |
| `R4_5_SHAPE` | the member is not a 2-D tensor, or `ne0 % blck_size != 0` | 7, 12 | the field |
| `R4_5_GGML_UNAVAILABLE` | the stub shim, or no CPU device | 10 | `stub` / `device` |
| `R4_5_ABI` | `align_ggml_abi_probe` returned an implausible constant | 11 | the constant |
| `R4_5_TYPE_UNSUPPORTED` | the ggml type cannot be a `mul_mat` left operand | 12 | `type[<id>]` |
| `R4_5_ALIGNMENT` | a pointer handed to ggml would violate `TENSOR_ALIGNMENT` | 13 | `weights` / `member` / `output` |
| `R4_5_GGML_INIT` | a ggml constructor returned `NULL` | 14, 15 | the object |
| `R4_5_COMPUTE` | `ggml_backend_graph_compute` returned non-success | 16 | `status[<n>]` |
| `R4_5_SOURCE_UNREADABLE` | the reference GGUF could not be opened or read | 17 | the offset |
| `R4_5_SOURCE_DIVERGED` | pack bytes differ from GGUF bytes | 18 | `member@<offset>` |
| `R4_5_REFERENCE_MISMATCH` | an output element differs | 19 | `element[<index>]` |

**`R4_5_ALIGNMENT` is the code that would otherwise not exist**, and it is the design's answer to
section 2.4: without step 13, a misaligned buffer produces `GGML_ASSERT` and `abort()` — no
document, no error code, no diagnosis. With it, the same input produces a document naming which
pointer was wrong and by how much. On this host the condition has never been observed with a real
block, which is precisely why the fixture of section 5.1 manufactures it.

**`R4_5_COMPUTE` cannot cover every compute failure and the design says so.** `ggml_abort` is
`abort()`. A kernel that hits an internal assertion takes the process down before any status is
returned, and no Align code runs after it. Section 3.9 states the consequence.

### 3.9 Ownership, allocation, lifetime, and abort-safety

| Module | Owns | Imports |
| --- | --- | --- |
| `src/alignpack_read.align` | the standalone v1 reader, the v1 record geometry constants, the `R4_PACK_*` codes it raises | `std.fs` |
| `src/ggml_ffi.align` | **every** `extern "C"` declaration and **every** `unsafe` block in the capability, `link("align_ggml_shim")`, and a safe `Result`-returning API above them | none |
| `src/ggml_spike.align` | the CLI arity and path guards, the validation order of section 3.8, the deterministic activation, the reference arm, the document renderer, the summary block, every `R4_5_*` code | `core.json`, `std.crypto`, `std.encoding`, `std.fs`, `std.time`, `alignpack_read`, `ggml_ffi` |
| `scripts/ggml_shim.c` / `scripts/ggml_shim_stub.c` | the ggml ABI, `bool` translation, by-value struct construction, alignment pre-checks | ggml headers / nothing |

**`grep unsafe src/` must show `src/ggml_ffi.align` and nothing else.** That is the discipline
`../align/docs/guide/15-unsafe-and-ffi.md` asks for, and it is checkable.

| Value | Owner | Allocation | Release |
| --- | --- | --- | --- |
| pack `file`, reference `file` | bare locals in the arm, as `src/gguf.align:74-77` requires | one or two fds | scope `Drop` |
| `PackIndex` | one local | header scalars, one owned name-stream `string`, block-table `array<i64>` columns | scope `Drop` |
| `weights` | one bare `mut buffer` local in the arm | `buffer(block.pack_bytes)`, 17,020,928 B for the reference block, `max_block_bytes` = 447,082,496 B worst case on this model | scope `Drop`, **after** every ggml object is freed |
| `output` | one bare `mut buffer` local | `buffer(ne1 * 16)`, 57,344 B | scope `Drop`, after teardown |
| `activation` | one bare `mut buffer` local | `buffer(ne0 * 16)`, 57,344 B | scope `Drop`; ggml **copies** it in, so it is not lifetime-critical |
| reference weights | one bare `mut buffer` local, five-operand form only | `buffer(M.nbytes)` | scope `Drop` |
| ggml backend, contexts, buffers | **borrowed**, never owned by Align; held as `raw` handles | ggml's own | explicit `align_ggml_*_close` / `_free` in the order below |
| digest | one local `array<u8>` of 32 | `crypto.sha256` | scope `Drop` |
| document | one `builder` | accumulated once, declaration order | moved out by `to_string()` |

**The lifetime contract, stated as an ordering, because that is what it is.**

```text
weights: buffer  ─────────────────────────────────────────────────────────────┐
  ggml buffer over weights.bytes()  ───────────────────────────────┐          │
    tensor A placed at weights.bytes()[interior..]  ────┐          │          │
      compute                                          │          │          │
    ─────────────────────────────────────────────────── ┘          │          │
  align_ggml_buffer_free(weights buffer)  ─────────────────────────┘          │
  align_ggml_context_close, align_ggml_backend_close                          │
weights dropped at scope end  ────────────────────────────────────────────────┘
```

Every ggml object that refers to Align memory is released by an explicit call **before** the owning
`buffer` local leaves scope, and the document's `lifetime` object records the counts and the
`released_before_owner_scope_end` flag so the ordering is evidence rather than assertion. The
teardown order is: weights buffer, output buffer, activation buffer, reference buffer, contexts,
backend. It runs on **every** exit path from step 14 onward, including error paths, which is why
steps 14–19 are written as a single function whose failure paths converge on one teardown rather
than as early returns.

Section 2.4 measured why this is mandatory and not hygiene: a ggml buffer that outlives its process
teardown aborted at `exit` on the Metal backend. A leaked handle here is a crash, not a leak.

**Abort-safety, stated plainly.** Align's guarantees stop at the `unsafe` block. `ggml_abort` calls
`abort()`; a `GGML_ASSERT` inside a kernel, a device driver fault, or an out-of-memory condition
inside ggml terminates the process with no unwinding, no `Drop`, no document, and no error code. The
design's response is not to claim otherwise but to make the reachable failures unreachable:

- every pointer handed across the boundary is alignment-validated first (step 13);
- every size handed across is bounds-checked against `ggml_nbytes` in the shim;
- every constructor's return is null-checked before use (steps 14, 15);
- every type and shape is validated before the tensor is built (steps 7, 12);
- the document is rendered and written **last**, so a crash yields *no* document rather than a
  half-written one, and the caller sees a nonzero exit with the process's own abort message.

The spike writes nothing except the caller's document path, so an abort leaves no artifact to clean
up. This is the whole reason the capability is a separate short-lived executable rather than an arm
of `main`.

**Work stays bounded.** One `pread` of one block. One graph of one node. Six timed compute calls.
The reader reads one 128-byte header, `block_count` 64-byte records, and exactly one 96-byte member
record. Peak resident memory is `block.pack_bytes` plus about 115 KB, doubled in the five-operand
form by the reference arm's own `M.nbytes` buffer and ggml's copy of the weights — for
`blk.0.attn_q.weight`, 17.0 MB + 7.2 MB + 7.2 MB.

### 3.10 Ledger dimensions

| Dimension | Contract | Owner | Acceptance |
| --- | --- | --- | --- |
| Exact commands | Section 3.3, three arities | `src/ggml_spike.align` | `run-ggml-spike-smoke` covers each arity and each arity failure |
| Inputs and defaults | Pack path, two indices, optional `-`/doc path, optional GGUF | same | smoke |
| Results and errors | Section 3.8, fifteen codes, first-applicable-row order | same | smoke reaches steps 1–10; qualification reaches 11–19 |
| Multi-invalid precedence | Deterministic by step order; a pack that is both malformed and asked for an out-of-range block reports `R4_PACK_*` | same | smoke fixture `bad-header-and-bad-index` |
| Ownership and allocation | Section 3.9 table and ordering diagram | same | `lifetime` object in every document |
| Owner module | Section 3.9 module table | — | `grep unsafe src/` shows one file |
| Persisted / cache identity | `N/A` — the spike persists nothing and caches nothing. It only ever writes the caller's document path | — | — |
| Schema version | `R4_5_EXTERNAL_BUFFER`, `1`, nominal on `kind` + `schema_version` | `src/ggml_spike.align` | smoke compares whole documents against golden files |
| Validation order | Section 3.8, twenty steps | same | smoke and qualification |
| Prerequisites | ggml `0.21.0`-compatible headers and libraries for the real shim; a GGUF and a pack for the qualification | `scripts/run-ggml-spike` | explicit `N/A` line with a reason when unset |
| Build inputs | `ALIGN_LLM_GGML_INCLUDE` selects the real shim, otherwise the stub; `ALIGN_LLM_GGML_LIB` and `ALIGN_LLM_GGUF_MODEL` gate the qualification | `Makefile`, both scripts | `check-gate-topology`; the smoke asserts the stub build reports `R4_5_GGML_UNAVAILABLE` |
| Environment isolation | Neither script exports anything into `make build`'s environment; `main` never links the shim | `Makefile` | `make build` on a ggml-free host, which is the hosted default |
| Text and wire boundary | Canonical UTF-8 JSON, declaration order, R0 escaping; member names carry arbitrary bytes and are emitted through the existing JSON escaper | `src/ggml_spike.align` | golden document comparison |
| Field presence by state | `reference_*` fields present and `-`/`false`/`0` in the three- and four-operand forms; `compute`/`output` zeroed when `verdict` is `UNAVAILABLE` | same | smoke covers all three arities × ok/error |
| Minimum tool versions | ggml `0.21.0` measured; `align_ggml_abi_probe` records the three constants that matter | `scripts/ggml_shim.c` | `abi` object in every document |
| Metrics | Section 5.3 | — | qualification |
| Later-slice decisions | No backend selection, no tolerance oracle, no loader — section 5.4 | — | — |

---

## 4. Closure matrix

Every cell names an implementation owner and an exact regression before any code is written. `S` is
a step of section 3.8.

### 4.1 `src/alignpack_read.align` — the standalone reader

| Cell | Implementation | Regression |
| --- | --- | --- |
| Formation / validation | `open_pack` validates magic, version, widths, alignments, flags, `f.len()`, region containment and disjointness | `pack-bad-magic`, `pack-bad-version`, `pack-bad-widths`, `pack-bad-align`, `pack-flags-set`, `pack-len-mismatch`, `pack-region-overlap` |
| Construction | `PackIndex` freezes block-table columns once from `array_builder<i64>` | `pack-minimal` golden index |
| Success | `block_at`, `member_at`, `member_name` on a synthetic three-block pack | `pack-minimal`, compared to `scripts/alignpack_reader.py` |
| Failure | every `R4_PACK_*` path returns `Fault` with R4's own detail text | the seven fixtures above |
| Malformed input | high-bit-set `u64` fields; a `name_start + name_bytes` past the name stream; a non-monotonic `pack_offset` | `pack-u64-highbit`, `pack-name-overrun`, `pack-offset-nonmonotonic` |
| Early exit | `f.len() != total_bytes` returns before any table read | `pack-len-mismatch` asserts zero table reads via `bytes_read` |
| Move-in / out | `PackIndex`'s name stream is one owned `string`, moved in once, never cloned | compile |
| Cleanup | fd closed by scope `Drop`; no explicit close exists at this pin | — |
| Fifth-instance column shape | `array<i64>` columns behind `borrow` accessors | `model-ir-smoke` precedent; no new mechanism |

### 4.2 `src/ggml_ffi.align` — the boundary

| Cell | Implementation | Regression |
| --- | --- | --- |
| Formation | one `extern "C" link("align_ggml_shim")` block; every function returns a status or a scalar | `alignc check src/ggml_spike.align` |
| Construction | `open_backend`, `open_context` return `Result<raw, Fault>`; `NULL` becomes `R4_5_GGML_INIT` | stub build returns `R4_5_GGML_UNAVAILABLE` at S10; qualification covers real construction |
| Success | every wrapper returns `Ok` on shim status `0` | qualification |
| Failure | every negative shim status maps to exactly one `R4_5_*` code, in one `match` | `ggml-shim-status-map` unit fixture driving the stub through each status |
| Malformed input | not applicable at this layer: shapes and types are validated in `ggml_spike` before any call | `N/A` — validation is S7/S12, one layer up, so this module has no unvalidated input |
| Early exit | `available()` is the first call; nothing else runs when it is `0` | stub smoke |
| Move-in / out | handles are Copy `raw` values, never aggregated, never returned as views | compile |
| Cleanup | `close_*` / `free_*` wrappers are total and idempotent against `raw.null()` | `ggml-teardown-order` in the qualification asserts the `lifetime` counts |
| Purity | every function here contains `unsafe`, so all are inferred Impure and can never enter `par_map` | compile |

### 4.3 `src/ggml_spike.align` — the arm

| Cell | Implementation | Regression |
| --- | --- | --- |
| Formation | arity, path guards, index parse — S1–S3 | `spike-arity-2/6`, `spike-path-empty`, `spike-path-nul`, `spike-index-negative`, `spike-index-nonnumeric` |
| Construction | reader open, block and member selection — S4–S7 | `spike-block-oob`, `spike-member-oob`, `spike-shape-3d`, `spike-shape-zero` |
| Success | the whole path to a document | qualification `qwen-blk0-attn-q`; stub smoke to S10 |
| Failure | each of the fifteen codes | table in 4.6 |
| Malformed input | a pack whose member table claims a `ggml_type` that is not a `mul_mat` operand; a member whose `ne0 % blck_size != 0` | `spike-type-unsupported`, `spike-ne0-not-multiple` (both synthetic, both reachable with the stub since S12's check is in the shim — the stub implements `align_ggml_type_ok` against a checked-in table) |
| Early exit | S10 with the stub: `verdict: "UNAVAILABLE"`, `compute`/`output` zeroed, exit non-zero | `spike-stub-unavailable` golden document |
| Branch joins | every `?`, `match`, and `map_err` in S4–S19 has a named fixture in 4.6 | 4.6 |
| Move-in / out | `weights`, `output`, `activation` are bare `mut` locals; the rendered document is moved out by `to_string()` | compile |
| Replacement | none: no buffer is rebound after a ggml object refers to it — the invariant that makes the borrowed pointer valid | `ggml-pointer-stability` asserts `tensor_data_offset` is unchanged after the compute loop |
| Cleanup | one convergent teardown from S14 onward, on success and on every failure | `lifetime` counts in every document from S14 on |
| Determinism | the activation formula, `N = 4`, warm-up + five calls | `output.sha256` compared to a golden value in the qualification |

### 4.4 `scripts/ggml_shim.c` and `scripts/ggml_shim_stub.c`

| Cell | Real shim | Stub | Regression |
| --- | --- | --- | --- |
| Availability | `1` | `0` | `spike-stub-unavailable` |
| ABI probe | real constants | `32 / 256 / 144`, the checked-in expectation | qualification compares real against checked-in and fails on drift |
| Type check | `ggml_blck_size` and a `mul_mat` operand table | same table, checked in | `spike-type-unsupported` runs on both |
| Alignment pre-check | validates before `ggml_backend_dev_buffer_from_host_ptr` | validates identically, then returns unavailable | `spike-misaligned` (4.5) |
| Bounds check | against `ggml_nbytes` | against the caller's declared size | qualification |
| Construction failure | `NULL` from any ggml constructor → negative status | always unavailable | qualification |
| Cleanup | `ggml_backend_buffer_free`, `ggml_free`, `ggml_backend_free` | no-ops | `ggml-teardown-order` |
| No allocation of computed memory | asserted by review: no `malloc` in either file | same | `grep -c malloc scripts/ggml_shim*.c` is `0`, asserted by the smoke |

### 4.5 The alignment cell, which is its own row because it is the crash

| Cell | Implementation | Regression |
| --- | --- | --- |
| Weights base misaligned | S13 rejects before any ggml call | `spike-misaligned`: a fixture pack whose `block_align` is a **valid** power of two smaller than 32, so a block starts at a 16-byte boundary and S13 fires with detail `weights` |
| Member interior misaligned | S13 checks `base + interior_offset` separately | `spike-misaligned-member`: `member_align = 16` in the fixture header |
| Output base misaligned | S13 checks the output buffer | not reachable from an input; covered by a unit call of the check function with a synthetic base |
| Alignment is a platform accident | recorded, not relied on | the document's `buffer.base_alignment` is emitted on **every** run, including successful ones, so a host where it is 16 is visible in the evidence rather than a crash |

### 4.6 Error-code-to-fixture map, and the final pass

| Code | Fixture | Reachable with the stub |
| --- | --- | --- |
| `R4_5_ARITY` | `spike-arity-2`, `spike-arity-6` | yes |
| `R4_5_PATH` | `spike-path-empty`, `spike-path-nul`, `spike-path-long` | yes |
| `R4_5_INDEX` | `spike-index-negative`, `spike-index-nonnumeric`, `spike-block-oob`, `spike-member-oob` | yes |
| `R4_PACK_MAGIC` … `R4_PACK_UNREADABLE` | the seven reader fixtures of 4.1 | yes |
| `R4_WINDOW_UNAVAILABLE` | `spike-window-huge`: a fixture header claiming a `pack_bytes` past any allocation | yes |
| `R4_5_SHAPE` | `spike-shape-3d`, `spike-shape-zero`, `spike-ne0-not-multiple` | yes |
| `R4_5_GGML_UNAVAILABLE` | `spike-stub-unavailable` | yes — this is the stub |
| `R4_5_ABI` | qualification only, by inspection of the recorded constants | no |
| `R4_5_TYPE_UNSUPPORTED` | `spike-type-unsupported` | yes |
| `R4_5_ALIGNMENT` | `spike-misaligned`, `spike-misaligned-member` | yes |
| `R4_5_GGML_INIT` | qualification, by a shim built with `ALIGN_LLM_GGML_FORCE_INIT_FAILURE` | no |
| `R4_5_COMPUTE` | qualification, same mechanism | no |
| `R4_5_SOURCE_UNREADABLE` | qualification, `--reference /nonexistent` | no |
| `R4_5_SOURCE_DIVERGED` | qualification, against a truncated copy of the GGUF | no |
| `R4_5_REFERENCE_MISMATCH` | qualification, against a GGUF with one flipped payload byte | no |

Nine of the fifteen codes are reachable in hosted CI without ggml. The six that are not are exactly
the six that require a live foreign library, and each names its qualification mechanism.

**Final pass.** Before review, every cell above maps to the diff and to passing evidence, or to an
explicit deferral in section 5.4. Cells marked `N/A` state the reason inline, as 4.2's
malformed-input row does.

---

## 5. Fixtures, qualification, metrics, deferrals, and candidate requests

### 5.1 Owner — `make ggml-spike-smoke`, `scripts/run-ggml-spike-smoke`

Hosted, ggml-free, in `HOSTED_CHECK_TARGETS`. It builds the stub shim, builds `ggml-spike`, and runs
every fixture of section 4.6's "reachable with the stub" column against **synthetic** packs written
by a new `scripts/ggml_spike_fixture.py`, in the style of `scripts/gguf_fixture.py`.

The synthetic corpus is small and hand-computable: one `pack-minimal` with three blocks and five
members totaling under 64 KiB, plus one mutation per reader fixture produced by a single byte edit
on a copy of it. Every fixture's expected document is a checked-in golden file compared **byte for
byte**, so field order, presence rules, and the `-`/`false`/`0` conventions of section 3.10 are all
regressions rather than intentions.

Three assertions are not about a fixture:

- `scripts/alignpack_reader.py` decodes `pack-minimal` and its header, one block record, and one
  member record are compared field-by-field to the Align reader's document. This is the guard for
  section 3.5's two-decoders risk.
- `grep -c malloc scripts/ggml_shim*.c` is `0` in both files.
- `grep -rl unsafe src/` names exactly `src/ggml_ffi.align`.

The smoke writes into a `mktemp -d` tree outside the work tree and removes it on every exit path,
which is every existing runner's convention.

### 5.2 Named qualification — `make ggml-spike-qualification`, `scripts/run-ggml-spike`

Opt-in, capable-only, in **neither** `HOSTED_CHECK_TARGETS` nor `CAPABLE_ONLY_CHECK_TARGETS`,
exactly as `alignpack-qualification` is not (`Makefile:146-152`). It prints an explicit `N/A` line
naming the missing input and exits `0` when `ALIGN_LLM_GGML_INCLUDE`, `ALIGN_LLM_GGML_LIB`, or
`ALIGN_LLM_GGUF_MODEL` is unset, or the model is absent, or free space is under the pack's size plus
1 GiB.

Otherwise it builds the real shim, packs the model with `./main --pack` into the temporary tree,
runs

```text
ggml-spike $PACK 1 1 $DOC $ALIGN_LLM_GGUF_MODEL
```

and asserts, against the recorded values of section 2.3:

| Assertion | Expected |
| --- | --- |
| `status` | `ok` |
| `verdict` | `EXTERNAL` |
| `selection.name` | `blk.0.attn_q.weight` |
| `tensor.ggml_type` | `12` |
| `tensor.ne0`, `tensor.ne1`, `tensor.nbytes` | `3584`, `3584`, `7225344` |
| `buffer.interior_offset`, `buffer.tensor_data_offset` | `14336`, `14336` |
| `buffer.pointer_identity`, `buffer.output_pointer_identity` | `true`, `true` |
| `abi.tensor_alignment`, `abi.q4k_blck_size`, `abi.q4k_type_size` | `32`, `256`, `144` |
| `reference.bytes_equal`, `reference.verdict`, `reference.differing_elements` | `true`, `IDENTICAL`, `0` |
| `output.sha256` | `2ccc7dc778108df3b626128895347f203795a2d82b502805806fb8472457e044` |
| `lifetime.*_created == *_freed`, `released_before_owner_scope_end` | equal, `true` |

Then the four ggml-only error fixtures of section 4.6, then it removes the pack and the tree.

**`output.sha256` is asserted as an exact value and that is a deliberate, narrow claim.** It is
correct for this model, this member, this activation, this ggml version, and this CPU backend. It is
not a portable golden value, and section 5.6 records that a ggml kernel change will move it. The
assertion is written so its failure message says "the kernel or the model changed" and points here,
rather than reading as a corruption report.

### 5.3 Metrics

| Metric | Definition | Baseline on this host |
| --- | --- | --- |
| `pread_ns` | one `pread` of `block.pack_bytes` | 4,204,958 ns for 17,020,928 B — 4.0 GB/s, warm cache |
| `compute_ns` | mean of five `mul_mat` calls after one warm-up | 413,508–551,375 ns |
| external-vs-internal compute | the same graph over Align memory and over ggml memory | 0.427 ms vs 0.423 ms; **no measurable penalty** |
| first-call overhead | first compute minus warm mean | ≈ 4.6 ms vs 0.41 ms — thread-pool spin-up, which is why the warm-up call is contractual |

These are secondary metrics. R4.5 makes **no** claim on time to a passing patch and none of these
numbers is an optimization claim; they exist so R5 can size a loader against a measured boundary
rather than a guess.

### 5.4 Deferred surfaces

- **Metal and the VRAM half.** Measured working in section 2.5 and deliberately not shipped: it
  needs a different alignment rule (Metal accepted an 8-byte-offset pointer where the CPU aborted)
  and a tolerance-based oracle (all 14,336 elements differ from CPU, max 0.029), which is a
  different acceptance contract. R5 owns it, with section 2.5 as its starting evidence.
- **Discrete VRAM.** Unanswered and unanswerable here. `ggml-cuda.h`'s only host-memory entry points
  page-lock host memory for transfer; there is no `buffer_from_host_ptr` counterpart, and this host
  has no discrete device. R5's DRAM → VRAM tier is a **transfer** design there, not a
  compute-in-place one, and section 1.4 says so rather than generalizing from unified memory.
- **An expert block.** The gate's "one expert matmul" is discharged for a dense attention block.
  This host's only real model is dense; `r4-alignpack-layer-major.md` section 4.5's **MOE-PREREQ**
  is inherited unchanged, and when a real MoE GGUF exists the qualification gains one line — the CLI
  already addresses an `ExpertBlock` by its block index with no new surface.
- **The R5 loader.** The spike reads one block on request and holds it for one graph. Residency,
  eviction, cache score, and prefetch remain R5's, per `r4-alignpack-layer-major.md` section 5.4.
- **More than one node.** One `mul_mat` is the whole graph. A multi-node graph would need
  `ggml_gallocr` and an allocation plan, which is R5's problem and not the gate's question.
- **A read-only pack open.** The reader uses `fs.open_rw` because `fs.open_ro` does not exist. This
  is the **third** client for Request 21 and the first where the file being opened read-write is one
  the caller has every reason to keep immutable.

### 5.5 Candidate Align capability requests

Two genuine gaps, each verified by compiling the failing case at the pin, each **non-blocking** —
the C shim is a legitimate application-side answer, not a compatibility layer around a hypothetical
API — and each recorded because `CLAUDE.md` requires recording a language-owned requirement even
when a workaround exists. This document does not edit `docs/align-requests.md`; the orchestrator
owns the register.

#### 5.5.1 Candidate Request 32 — FFI aggregates and `bool` on AArch64

The gap is three rejections that together make a mature C library unreachable without a C shim:

1. a `layout(C)` struct cannot cross **by value** on any target but x86-64 SysV, at 16 bytes as well
   as 24 (section 3.1's two diagnostics);
2. a `layout(C)` struct cannot **contain a `raw` field**, so the by-pointer fallback the diagnostic
   recommends does not exist for any struct with a pointer member;
3. `bool` is not an FFI type, in either direction.

`struct ggml_init_params { size_t; void *; bool; }` fails all three at once, and `ggml_init` is the
sole entry point to the entire library. `align-llm` is the client, and the evidence is that
`docs/language-spec.md:778-875` already lists (1) and (3) as "deliberately out of FFI v1" while (2)
is what makes (1)'s stated workaround inapplicable.

Proposed surface, Align-consistent and unsurprising: allow `raw` as a `layout(C)` struct field;
allow `layout(C)` structs by value on AArch64 AAPCS64 under the same "reject rather than silently
pass in memory" discipline the SysV path already uses; and admit a `c_bool` FFI scalar distinct from
Align's `bool`, or define `bool`'s FFI lowering as `u8` with `0`/non-zero semantics.

Acceptance criteria: `probe_byval.align`, `probe_byval2.align`, and `probe_bool.align` compile and
run against a real C library on `arm64-apple-darwin`; the shim's `align_ggml_context_open`,
`align_ggml_type_ok`, and the by-value wrappers can be deleted, and `src/ggml_ffi.align` declares
`ggml_init` directly.

```text
Status: PROPOSED
Priority: medium
Blocking: no
Blocked gate or slice: none — the C shim is the application-side answer and R4.5 ships with it
Independent work that may continue: all of R4.5 and R5
Resume condition: an Align commit implementing any of the three parts
Align commit or pull request: none
align-llm verification: `make ggml-spike-qualification` with the shim's by-value wrappers deleted
```

#### 5.5.2 Candidate Request 33 — an aligned allocation

Neither `raw.alloc(n)` nor `buffer(n)` accepts an alignment, and `align(N)` applies to struct
storage and to numeric scalar-array bindings, not to a heap allocation of run-time size. Section 2.4
measured that every observed allocation on this host happened to satisfy ggml's 32-byte requirement
and that multi-megabyte ones happened to be page-aligned — both platform-allocator accidents. The
consequence for a DMA/SIMD/GPU client is that the only safe design is *validate and fail closed*,
which is what section 3.8 step 13 does, and a legitimate input can be rejected for a reason the
program cannot fix.

Proposed surface: `raw.alloc(n, align)` and `buffer(cap, align)`, or an `align(N)` prefix admitted
on a `buffer` binding, with the allocation failing rather than silently under-aligning. This is the
same promise `align(N)` already makes for `[align(64) S]` element stride, extended to the heap.

Acceptance criteria: a 16384-aligned `buffer` of run-time size, verified by an address probe, usable
for `ggml_backend_dev_buffer_from_host_ptr` on the Metal path where page alignment is the practical
requirement.

```text
Status: PROPOSED
Priority: medium
Blocking: no
Blocked gate or slice: the deferred Metal arm of section 5.4 would consume it first
Independent work that may continue: all of R4.5; R5's DRAM tier
Resume condition: an Align commit adding an alignment parameter to either allocator
Align commit or pull request: none
align-llm verification: a Metal arm asserting `buffer.base_alignment % 16384 == 0` without a shim allocation
```

**One guess is refuted and recorded as refuted.** The plan assumed a `ggml_tallocr` wrapper would be
needed because `ggml_tallocr_new` returns a struct by value. Section 2.2 showed
`ggml_backend_tensor_alloc` places a tensor at a chosen address directly, so no allocator object is
involved and the wrapper is not part of section 3.4. A second guess — that `ggml_backend_cpu_init`
would be linkable — was refuted by section 2.1 and changed the design to the backend registry.

### 5.6 Risks

**ABI drift is the largest one.** The shim is compiled against whatever `ggml.h` the host has, and
ggml carries no stable ABI promise: `struct ggml_tensor`'s layout is private, `TENSOR_ALIGNMENT` is
an internal constant, and `enum ggml_type`'s numbering is data in every GGUF ever written. Three
mitigations, in order of strength: no ggml type appears in any Align declaration, so drift cannot
silently change an Align signature; `align_ggml_abi_probe` records `TENSOR_ALIGNMENT`,
`ggml_blck_size(Q4_K)`, and `ggml_type_size(Q4_K)` in **every** document and the qualification
asserts them; and the shim reads no `struct ggml_tensor` field directly, using `ggml_get_data`,
`ggml_nbytes`, and `ggml_blck_size` instead of offsets. The version measured here is ggml `0.21.0`
from llama.cpp `0.2.0 (build 10566, commit bb4caa754)`; a different one is expected to work and is
not promised to.

**A ggml kernel change moves `output.sha256`.** Section 5.2 states the assertion's narrow scope and
its failure message points here.

**The backend plugin topology is a host property.** Section 2.1's `libexec` layout is Homebrew's; a
source build puts `libggml-cpu` in the link path and would make `ggml_backend_cpu_init` linkable.
The design does not depend on which is true, because it uses only the registry path, which works in
both.

**Two decoders for one format.** Section 3.5 states the choice, the argument, and the third-party
regression that binds them.

**An abort still ends the process.** Section 3.9 states it plainly and enumerates what the design
does about the reachable cases. This is a property of borrowing a C engine, not a defect that more
Align code could remove.

---

## 6. Implementation-forced corrections

Sections 1 to 5 are the design as it stood before a line was written. This section is what the
implementation refuted, and it is written the way section 2 is written: each row states what the
plan said, what the code found, and what the contract now is. Nothing here is a preference. Every
correction is a case where the plan could not be implemented as written at the pinned compiler or
against the linked ggml, and each one is bound to a passing case in section 6.2.

The five sections above are **not** rewritten. A plan that quietly becomes whatever was built stops
being evidence of anything, and the difference between the two is the useful record.

### 6.1 The corrections

| # | Section | The plan | What the implementation found | The contract now |
| --- | --- | --- | --- | --- |
| C1 | 3.4 | `align_ggml_abi_probe` returns ggml's `TENSOR_ALIGNMENT` | `TENSOR_ALIGNMENT` is **not** in any shipped public header — it is internal to `ggml-backend.cpp` and `ggml-alloc.c`. `grep -rn TENSOR_ALIGNMENT /opt/homebrew/include/*.h` is empty | `align_ggml_tensor_alignment()` reports `ggml_backend_buft_get_alignment(ggml_backend_dev_buffer_type(dev))` for the CPU device, which **is** public and **is** the value the assert uses. Measured `32`. The stub reports the checked-in `32` |
| C2 | 3.4 | one `align_ggml_abi_probe(int32_t *, int32_t *, int32_t *)` | Three out-parameters need three `raw.alloc` calls in the module whose stated contract is that it allocates nothing, and Align has no other out-parameter idiom for a scalar | Four scalar-returning queries: `align_ggml_tensor_alignment`, `align_ggml_blck_size(type)`, `align_ggml_type_size(type)`, and `align_ggml_table_drift()`. The drift guard is **widened** from three Q4_K constants to all twenty-five rows of the checked-in `mul_mat` operand table; the document gains `abi.table_drift` |
| C3 | 3.4, 4.2 | wrappers return `Result<raw, Fault>` | Rejected at the pin: `error: Result ok payload must be a scalar (composite payloads are not supported yet), got raw` | Every ggml constructor wrapper returns a bare `raw` and reports failure as a null handle. `src/ggml_spike.align` tests it with `ggml_ffi.handle_absent` at the one place that knows which object it asked for — which is also the place section 3.8 names in its detail. `raw.null()` and `.is_null()` are wrapped in `ggml_ffi` so `grep unsafe src/` still names one file |
| C4 | 3.6 | the reference arm compares two outputs bit-exactly | The reference output lives in ggml's own memory by construction, and Align can form no view over foreign memory, so there is nothing to compare on this side of the boundary | `align_ggml_tensor_get` added to both shims, wrapping the public `ggml_backend_tensor_get`. The reference output is copied into an Align buffer and compared there, which is also what makes `reference.first_difference_primary_bits` and `…_reference_bits` computable |
| C5 | 3.8 | availability is step 10; the reference read and byte check are steps 17 and 18 | Two independent problems. Section 4.3 and 4.6 require the type, shape, and alignment checks to be **stub-reachable**, which an availability stop at step 10 makes impossible. And a reference failure at step 17 or 18 would abandon live ggml buffers holding pointers into Align allocations about to be dropped | Order is: 1–9 unchanged; **10** reference read; **11** reference byte equality; **12** ABI probe; **13** type; **14** alignment; **15** availability; 16–18 construction and compute; 19 reference compute and compare; 20 teardown. `R4_5_SOURCE_UNREADABLE` and `R4_5_SOURCE_DIVERGED` therefore **become** stub-reachable, and no reference failure can leave a ggml object behind |
| C6 | 3.3 | the summary block is printed "in the four- and five-operand forms" | `-` in the fourth position means "document to stdout", so the five-operand `- REF` form would interleave a positional summary with the machine form | The summary accompanies a document written to a **named path**. `-` selects the machine form: the document alone. `run-ggml-spike-smoke` asserts the three-operand, `-`, and file forms emit identical document bytes |
| C7 | 3.9 | — | Two mechanics at the pin. `buffer` exposes no `.capacity()`. And a Borrow argument crossing an FFI wrapper must be a *stable named local or field*, not a temporary: `ggml_ffi.buffer_from_host(device, weights.bytes(), n)` is rejected | The arm takes `weights_view`, `output_view`, `activation_view`, and `member_span` **once**, immediately after the block `pread`, and passes those. That is also exactly section 4.3's replacement invariant — no buffer is rebound after a ggml object refers to it — enforced by the compiler rather than by review |
| C8 | 3.8 step 8, 4.6 | `spike-window-huge` reaches `R4_WINDOW_UNAVAILABLE` from "a fixture header claiming a `pack_bytes` past any allocation" | `buffer(N)` at this pin is an **advisory** capacity hint that grows lazily. `buffer(4611686018427387904)` followed by one `put_u8` publishes length 1 and does not fail. No fixture can make a reservation degrade | `R4_WINDOW_UNAVAILABLE` is **not reachable from an input**. It is retained as `read_exact`'s fail-closed answer to a zero-length read at an offset already proved inside the file — a file that shrank underneath, or a genuine allocation failure. `spike-window-huge` is replaced by `spike-dimension-bound`, which refuses an implausible `ne0`/`ne1` with `R4_5_SHAPE` **before** any window loop starts, so work stays bounded for the reason the window check existed. `scripts/run-alignpack-smoke` already prints its own window-unavailable `N/A` line for the same class of reason |
| C9 | 3.8 step 13, 4.5 | the weights base, `base + interior_offset`, and the output base are each `0 mod tensor_alignment`, or `R4_5_ALIGNMENT` | Section 2.4 measured `raw.alloc` returning 32-aligned addresses and concluded alignment was a platform accident. It is worse: a 192-byte Align `buffer` on this host comes back **32-aligned on one run and 16-aligned on the next**. The plan's rule refuses a legitimate small tensor for a reason the program can fix itself, and it refuses it nondeterministically | The arm **compensates** rather than refusing: both device-visible windows are over-reserved by `MAX_TENSOR_ALIGNMENT = 64` and ggml is handed an aligned **interior range** of each, at `buffer.weights_pad` and `buffer.output_pad` — two new document fields. **C14 corrects this row's own repair**, which compensated only the output side and left the gate `(base_alignment + interior_offset) % tensor_alignment != 0` — still the allocator's answer, not the container's. `buffer.base_alignment` and `buffer.output_base_alignment` are emitted on **every** run, which is what section 4.5 asked them for |
| C10 | 5.1 | "every fixture's expected document is a checked-in golden file compared byte for byte" | Three groups of fields are properties of the run and not of the contract: `timings.*`, the two `mktemp -d` paths, and — per C9 — the four allocator-dependent `buffer` fields | One golden, `scripts/ggml-spike-golden.jsonl`, one line per case holding the exact document string. The runner rewrites those values **in place** — never reordering, adding, or dropping a field — and compares the rest byte for byte, so field order, field presence, and the `-`/`false`/`0` conventions remain regressions. The four allocator fields get a separate exact invariant instead: each base is in `[0, tensor_alignment)`, each pad is the distance from it to the next boundary, and the member's absolute address is on a boundary whenever the run continued past step 14 |
| C11 | 4.6 | `R4_5_REFERENCE_MISMATCH` is reached "against a GGUF with one flipped payload byte" | It is not producible by mutating an input. The byte-equality precheck of step 11 stops a divergent reference first and reports `R4_5_SOURCE_DIVERGED` — which is the **correct** cause, and is exactly why that check exists | `R4_5_REFERENCE_MISMATCH` is the code for a divergence the byte check cannot explain: a nondeterministic or mis-dispatched kernel. The qualification reaches it with `ALIGN_LLM_GGML_FORCE=reference`, a shim rebuilt to perturb one byte of the copied-out reference output, and asserts the comparison names the exact element. The plan's flipped-byte input is exercised too, as `R4_5_SOURCE_DIVERGED` |
| C12 | 4.6 | `spike-path-nul` | `execve` cannot carry a NUL inside an argument, so the CLI's NUL rule has no process-boundary input | The NUL clause stays as a fail-closed lexical guard. The reachable `R4_5_PATH` fixtures are `spike-path-empty`, `spike-path-long`, `spike-doc-path-empty`, and `spike-reference-path-empty` |
| C13 | 3.2, 3.5, 3.7 | `ggml-spike-build`; `member_name(x, m) -> str`; the `PackIndex` owns the name stream | The target is named after the executable, as `build` is after `main`. A `str` sliced out of a resident name stream by container-supplied byte offsets **aborts** if a corrupted offset lands mid-scalar, and holding a 16 MiB stream to read one name contradicts the module's own one-record discipline | The target is `ggml-spike`. `PackIndex` owns **no** name stream; `member_name` does one bounded `pread` of at most `MAX_NAME_BYTES` and decodes it with `as_str()`, returning `Text { text, valid }` so invalid UTF-8 is data rather than an invented code. `open_pack`, `member_at`, and `member_name` take a `Counters`, which is what makes `pack-len-mismatch`'s "zero table reads" checkable. The document gains `pack.reader_pread_count`, `pack.reader_bytes_read`, `selection.name_valid`, `abi.table_drift`, `buffer.weights_pad`, and `buffer.output_pad`; `align_ggml_backend_name` was added because a `const char *` cannot become an Align `str` at this pin |
| C14 | 3.8 step 13, 4.5, 6.1 C9 | C9's compensation makes `R4_5_ALIGNMENT` a container property | It did not. `weights_pad` was computed and published but nothing was placed at it: the block still began at the weights buffer's byte 0, so the gate `(base_alignment + interior_offset) % tensor_alignment != 0` still asked what the **allocator** returned. Measured at `6b19163`: `ggml-spike pack-minimal 0 0`, a member at interior offset **0** — as aligned as a container can make it — was refused `R4_5_ALIGNMENT`/`member` on 20 of 20 runs because the allocator handed back a 16-mod-32 base; so were interior 0 of block 2 and interior 64 of its second member. `spike-block-zero` and `spike-misaligned-member` were therefore goldens over an allocator accident, and a host whose base is 0 would have produced the opposite verdict for both | The block is **landed on a boundary** rather than measured against one. The weights window is over-reserved by `MAX_TENSOR_ALIGNMENT` too; one byte is published to make the base measurable, `weights_pad = MAX_TENSOR_ALIGNMENT - (base mod MAX_TENSOR_ALIGNMENT)` in `[1, 64]` is written as zeros, and the block is read in **behind** it by `alignpack_read.read_append` — the symmetric twin of `output_pad`, and the reason that reader function exists. The compensation modulus is `MAX_TENSOR_ALIGNMENT` because step 12 has not yet said what `tensor_alignment` is and every value step 12 admits divides it. The gate is then the container's own property and nothing else: **`interior_offset % tensor_alignment != 0`**, detail `member`, the same verdict on every host and every run. Detail `weights` and detail `output` survive as the fail-closed answer to a window that moved under its own pad — `align_mod` is re-measured on the exact ranges handed to ggml — and are **unreachable** by construction; nothing observed has ever produced one. `buffer.tensor_data_offset` is now measured from **block byte 0**, not from the buffer's base, so it remains the member's own interior offset (`14336` on the real model) whatever pad the allocator forced. The cost is one copy of the block into the compensated window, which is what `pread_ns` now includes |
| C15 | 3.8 step 10, 4.6 | the reference read is `R4_5_SOURCE_UNREADABLE` | Only when the *open* failed. The read itself went to `alignpack_read.read_exact`, whose zero-length answer at an offset it was told is resident is `R4_WINDOW_UNAVAILABLE` — the container reader blaming this side's allocator. So an empty, short, or simply wrong reference file reported a window failure for a range the pack claimed about a file the caller merely named. Measured at `6b19163`: an empty reference, one truncated exactly at the member's `source_offset`, and one truncated mid-member all reported `R4_WINDOW_UNAVAILABLE` | `read_reference` bounds `source_offset + nbytes <= handle.len()` **before** the `pread` and reports `R4_5_SOURCE_UNREADABLE` with detail `source@<offset>+<bytes>/<file length>`, which tells the three cases apart without a second run. The fixtures are `spike-reference-empty`, `spike-reference-eof`, and `spike-reference-mid-member`, all stub-reachable, joining `spike-reference-missing` on section 4.6's row |
| C16 | 3.7, 3.10 | `compute`/`output` are zeroed when `verdict` is `UNAVAILABLE` | `output.element_count` was not: it was published at the window reservation, so an `UNAVAILABLE` document carried a non-zero element count beside an empty digest and a zero bit sum — a description of an output that does not exist | `element_count` is published with the digest and the sums it counts, after the compute loop, and is `0` on every document that never computed. The count is carried as a local until then |
| C17 | 3.4, 3.7 | `tensor.blck_size` / `type_size` and `abi.q4k_*` are sizes | A geometry query answers with a size **or** with a negative shim status, and `spike-type-unsupported`'s golden published `blck_size: -3` — `R4_5_TYPE_UNSUPPORTED`'s status value read as a block size. The same class covers `abi.tensor_alignment`, which the real shim answers with `-1` or `-2` when the CPU device or its buffer type is absent | A status is not a size: every geometry answer is read raw for the check that owns it and published through one clamp, so the document carries `0` for "not established" and never an `R4_5_*` value in a size field. `spike-type-unsupported` still reports `R4_5_TYPE_UNSUPPORTED`, with `blck_size: 0`; an implausible alignment is still `R4_5_ABI`, whose detail names the raw status |
| C18 | 3.4, 3.8 | `STATUS_BOUNDS` is a shim status with its own meaning | `code_for` mapped it to `R4_5_GGML_INIT`, so a copy that would exceed `ggml_nbytes` was reported as a constructor returning `NULL` | It maps to `R4_5_SHAPE`, with the wrapper's `label` as the detail. A bounds refusal is the container's declared size and ggml's own size disagreeing, which is exactly what step 16's `ggml_nbytes(A) != member.nbytes` check reports under the same code |
| C19 | 3.9, 5.1 | `grep -rl unsafe src/` names exactly `src/ggml_ffi.align` | It does not and cannot: the sibling modules discuss the boundary in prose and `src/prompt_verifier_smoke.align` names an `unsafe_workspace` parameter. The runner already asserted the right thing — an `unsafe {` block opener, and an `extern "C"` line — while two module headers claimed the word-level version | The assertion is block-level and the module headers say so. `scripts/run-ggml-spike-smoke` greps `src/` for `unsafe[[:space:]]*\{` and for `^[[:space:]]*extern[[:space:]]+"C"` and requires each list to be `src/ggml_ffi.align` alone. Sections 3.9, 4.3, and 5.1's wording is the plan's; this row is the correction |
| C20 | 3.2 | `check-gate-topology` sees "one new hosted target and one new capable-only target" | There is no new capable-only target. `ggml-spike-qualification` is in **neither** `HOSTED_CHECK_TARGETS` nor `CAPABLE_ONLY_CHECK_TARGETS`, exactly as section 5.2 and the `Makefile` say and exactly as `alignpack-qualification` is not | One new hosted target, `ggml-spike-smoke`. The qualification is opt-in, in no list and no aggregate, and `ggml-spike` is a build target rather than a check |
| C21 | 3.5, 3.8 | the reader raises eight `R4_PACK_*` codes; `R4_5_INDEX`'s detail is `block[<n>]` / `member[<n>]` | The reader also raises `R4_PACK_TRUNCATED` — for a file shorter than the header, for `f.len() != total_bytes`, and for every region-containment failure — which section 3.5's list omits. And a *parse* failure at step 3 has no index to name, so it emits the sanitized operand itself (`-1`, `1x`, `01`, `99999999999999999999`) | The reader's code set is the eight of section 3.5 plus `R4_PACK_TRUNCATED`, with `r4-alignpack-layer-major.md` section 2.8's meaning. `R4_5_INDEX`'s detail is the sanitized operand when the operand did not parse (step 3) and `block[<n>]` / `member[<n>]` when it parsed and was out of range (steps 5 and 6). Both forms are goldens |
| C22 | 5.1, 3.2 | the owner runs anywhere `make` and a C compiler run | It did not run in the fresh worker image. That image ships a **curated tool set** (`image/fresh/Dockerfile`): 32 system binaries plus the toolchain forwarders, and neither `sort` nor `uname` is among them. `scripts/run-ggml-spike-smoke` sorted `grep -rl` output with `sort` and `scripts/build-ggml-shim` selected the library suffix with `uname -s`, so the aggregate died at `./scripts/run-ggml-spike-smoke: line 55: sort: command not found`, `make[1]: *** [Makefile:179: ggml-spike-smoke] Error 127` — the first `capable-checks` member of this capability to run under that PATH | The two static scans sort through a `sorted_paths` helper built on `python3`, which the curated set does ship, and compare against the path list without the trailing separator; the shim builder selects its suffix and its install-name/soname flag from bash's own `OSTYPE`, which needs no tool at all. Verified by running `make ggml-spike-smoke` with `PATH` restricted to exactly that tool set, and unchanged on macOS, where the `.dylib` and `-install_name` arm still ships |
| C23 | 5.1, 3.2 | the owner may build its shim and its executable in the work tree, because both are `.gitignore`d | `.gitignore` is not the constraint. The fresh worker mounts `/workspace` over an overlay and, after the aggregate exits, lists the overlay's upper directory and fails unless the **only** entry is `main` (`scripts/fresh-align-compiler`: `if any(name != "main" for name in names): fail("CHILD", "aggregate")`). `build/lib/libalign_ggml_shim.so` and the `ggml-spike` binary were two more, so the aggregate failed **after every check inside it had passed**, with no captured stdout or stderr to name a cause — even under `ALIGN_LLM_AGGREGATE_DIAGNOSTIC=1`, because the child had succeeded | The owner builds into its own `mktemp -d` tree: `scripts/build-ggml-shim` takes `ALIGN_LLM_GGML_SHIM_DIR` (default `build/lib`, unchanged for `make ggml-spike`), and the executable `alignc` writes next to the invocation is moved to `${work_dir}/ggml-spike` in the same step, which is also where the fixtures already live. The work tree is byte-identical before and after a run, verified with `git status --porcelain --ignored` |

**Net effect on section 4.6's count.** Ten of the fifteen codes are reachable in hosted CI without
ggml, not nine: `R4_5_SOURCE_UNREADABLE` and `R4_5_SOURCE_DIVERGED` are gained from C5 and
`R4_WINDOW_UNAVAILABLE` is lost to C8. Four of the remaining five need a live foreign library and
each names its mechanism; the fifth, `R4_WINDOW_UNAVAILABLE`, is not reachable from any input. C15
adds three fixtures to `R4_5_SOURCE_UNREADABLE` without changing the count, and C14 does not change
it either — it makes two of the ten deterministic rather than allocator-dependent.

**How C22 and C23 were found.** Preflight, not review, and one at a time: the exact-head
`scripts/pre-pr` run failed in its `fresh-installed` phase with the worker aggregate's output
suppressed. C22's failing command became visible under `ALIGN_LLM_AGGREGATE_DIAGNOSTIC=1`; C23's did
not, because with C22 repaired every check in the aggregate passed and the failure was the
supervisor's own post-run workspace scan, which produces no child output at all. They are the two
corrections in this table that no host-side run could have produced: every host this capability was
developed on has a full coreutils and an ordinary writable work tree. Both are now checkable without
a 26-minute preflight — `make ggml-spike-smoke` with `PATH` restricted to the curated tool set, and
`git status --porcelain --ignored` before and after a run.

**How C14 and C15 were found.** Both are review findings against the implementation at `6b19163`,
not against the plan, and both were reproduced before they were repaired: 20 consecutive runs of
three legal members at interior offsets 0, 0, and 64 all reported `R4_5_ALIGNMENT`/`member`, and
three references that exist but cannot supply the member's range all reported
`R4_WINDOW_UNAVAILABLE`. The repairs are verified the same way — the same inputs, the same runs.

### 6.2 Cell-to-case map

Every cell of section 4, mapped to the case that exercises it or to an explicit `N/A` with its
reason. `smoke` is `make ggml-spike-smoke`; `qual` is `make ggml-spike-qualification`.

**A compile-only cell cites `smoke`, not `make check`.** `make check` checks `src/main.align`'s
import graph, which does not reach `src/alignpack_read.align`, `src/ggml_ffi.align`, or
`src/ggml_spike.align` — that is section 3.2's whole point. The build that compiles all three is the
one `make ggml-spike-smoke` performs before it runs a fixture, so a cell whose evidence is "this
compiles" names the smoke.

**4.1 — `src/alignpack_read.align`**

| Cell | Case | Where |
| --- | --- | --- |
| Formation / validation | `pack-bad-magic`, `pack-bad-version`, `pack-bad-widths`, `pack-bad-align`, `pack-flags-set`, `pack-len-mismatch`, `pack-region-overlap` | smoke |
| Construction | `spike-stub-unavailable` golden, plus the reader-parity block | smoke |
| Success | `spike-stub-unavailable` (interior offset 2304) and `spike-block-zero` (interior offset **0**, the case C14 made reachable); twenty-two fields compared to `scripts/alignpack_reader.py` | smoke |
| Failure | the seven above plus `pack-reserved-block`, `pack-reserved-member`, `pack-missing` | smoke |
| Malformed input | `pack-u64-highbit`, `pack-name-overrun`, `pack-offset-nonmonotonic` | smoke |
| Early exit | `pack-len-mismatch` asserts `pack.reader_pread_count == 1` | smoke |
| Move-in / out | `PackIndex` owns no name stream after C13; the block columns are frozen once from `array_builder<i64>` | smoke (the build) |
| Cleanup | fd closed by scope `Drop`; no explicit close exists at this pin | `N/A` — unchanged from the plan |
| Fifth-instance column shape | `array<i64>` columns behind `borrow` accessors, no new mechanism | smoke (the build) |

**4.2 — `src/ggml_ffi.align`**

| Cell | Case | Where |
| --- | --- | --- |
| Formation | one `extern "C" link("align_ggml_shim")` block; the smoke asserts no other file in `src/` holds an extern block or an unsafe block | smoke |
| Construction | null handles become `R4_5_GGML_INIT` at the caller (C3); `forced init` reaches it against a live ggml | smoke, qual |
| Success | the primary arm of the qualification | qual |
| Failure | `code_for` is one `match`; `spike-type-unsupported` and `spike-misaligned-member` drive two of its arms through the stub, `forced init` and `forced compute` two more | smoke, qual |
| Malformed input | `N/A` — shapes and types are validated one layer up, at steps 7 and 13, so this module has no unvalidated input. Unchanged from the plan |  |
| Early exit | `spike-stub-unavailable`: `available()` is `0` and nothing else runs | smoke |
| Move-in / out | handles are Copy `raw`, never aggregated, never returned as views | smoke (the build) |
| Cleanup | `close_*` / `free_*` are total against a null handle; the qualification asserts `lifetime` buffers 4/4, contexts 2/2, backends 1/1 | qual |
| Purity | every function here contains `unsafe`, so all are inferred Impure | smoke (the build) |

**4.3 — `src/ggml_spike.align`**

| Cell | Case | Where |
| --- | --- | --- |
| Formation | `spike-arity-2`, `spike-arity-3`, `spike-arity-6`, `spike-path-empty`, `spike-path-long`, `spike-doc-path-empty`, `spike-reference-path-empty`, `spike-index-negative`, `spike-index-nonnumeric`, `spike-index-leading-zero`, `spike-index-huge` | smoke |
| Construction | `spike-block-oob`, `spike-member-oob`, `spike-shape-3d`, `spike-shape-zero`, `spike-dimension-bound` | smoke |
| Success | the qualification's `blk.0.attn_q.weight` arm; `spike-stub-unavailable` to step 15 | smoke, qual |
| Failure | ten codes in the smoke, four more in the qualification, one not input-reachable (C8); `R4_5_SOURCE_UNREADABLE`'s three bounded-range fixtures are C15's | smoke, qual |
| Malformed input | `spike-type-unsupported`, `spike-ne0-not-multiple` — both against the stub's checked-in table | smoke |
| Early exit | `spike-stub-unavailable` golden: `verdict: "UNAVAILABLE"`, `compute`/`output` zeroed — `element_count` included, after C16 — exit non-zero; and every documented case asserts `lifetime` is all zeros, because a stub build stops before the first constructor | smoke |
| Branch joins | every documented case is a golden line; thirty-three of them | smoke |
| Move-in / out | `weights`, `output`, `activation` are bare `mut` locals; the document is moved out by `to_string()` | smoke (the build) |
| Replacement | the views are taken once (C7) and `tensor_data_offset` is re-read after the compute loop and compared to the value recorded before it | qual |
| Cleanup | one convergent teardown from step 16 onward; `lifetime` counts in every document | qual |
| Determinism | `output.sha256` asserted as an exact value; it matched section 2.3's probe digest exactly | qual |

**4.4 — the two C files**

| Cell | Case | Where |
| --- | --- | --- |
| Availability | `spike-stub-unavailable` (`0`); the qualification's primary arm (`1`) | smoke, qual |
| ABI probe | `abi.tensor_alignment/q4k_blck_size/q4k_type_size/table_drift` asserted `32 / 256 / 144 / -1` against the linked ggml, and against all twenty-five table rows (C2) | qual |
| Type check | `spike-type-unsupported` and `spike-ne0-not-multiple` run against the stub; the qualification runs the same predicate against real `ggml_blck_size` | smoke, qual |
| Alignment pre-check | `spike-misaligned-member`; the shim's own second gate is unreachable behind it by construction | smoke |
| Bounds check | `align_ggml_tensor_set` and `align_ggml_tensor_get` against `ggml_nbytes` | qual |
| Construction failure | `ALIGN_LLM_GGML_FORCE=init` → `R4_5_GGML_INIT` | qual |
| Cleanup | `lifetime` counts equal and `released_before_owner_scope_end` true; no abort at `exit` | qual |
| No allocation of computed memory | `grep malloc scripts/ggml_shim*.c` is empty, asserted by the smoke; the shared contract region is asserted byte-identical between the two files | smoke |

**4.5 — the alignment cell**

| Cell | Case | Where |
| --- | --- | --- |
| Weights base misaligned | `N/A` — not reachable from an input (C9, C14). The base is the Align allocator's, not the container's: the arm over-reserves the weights window and lands **block byte 0** at `weights_pad`, so no base this allocator can return is refused. Detail `weights` survives only for a window that moved under its own pad, re-measured with `align_mod` on the exact range handed to ggml, and has never been observed |  |
| Member interior misaligned | `spike-misaligned-member`, a pack with the legal `member_align = 16` placing a member at interior offset 2320: `2320 % 32 = 16`, so it is `R4_5_ALIGNMENT`/`member` on every host and every run, independent of what the allocator returned (C14). The counter-case is `spike-block-zero`, interior offset `0`, which reaches step 15 on every run — it reported `R4_5_ALIGNMENT` on 20 of 20 runs before C14 | smoke |
| Output base misaligned | `N/A` — not reachable from an input; the arm over-reserves and places the tensor at `output_pad`. Detail `output` is the same unreachable fail-closed re-measurement as the weights row | smoke |
| Alignment is a platform accident | `buffer.base_alignment` and `buffer.output_base_alignment` are emitted on every run, and the pads with them. Measured **varying across runs of the same input** — `weights_pad` alternates between 16 and 48 for one fixture while its verdict does not move — which is stronger evidence than section 2.4 had, and is exactly why the verdict must not depend on it | smoke, qual |

**4.6 — error code to fixture**

| Code | Case | Stub |
| --- | --- | --- |
| `R4_5_ARITY` | `spike-arity-2`, `spike-arity-3`, `spike-arity-6` | yes |
| `R4_5_PATH` | `spike-path-empty`, `spike-path-long`, `spike-doc-path-empty`, `spike-reference-path-empty` (C12) | yes |
| `R4_5_INDEX` | `spike-index-negative`, `spike-index-nonnumeric`, `spike-index-leading-zero`, `spike-index-huge`, `spike-block-oob`, `spike-member-oob` | yes |
| `R4_PACK_*` | the eleven reader fixtures plus `pack-missing` | yes |
| `R4_WINDOW_UNAVAILABLE` | `N/A` — not input-reachable (C8); `spike-dimension-bound` covers the bounded-work reason it existed | no |
| `R4_5_SHAPE` | `spike-shape-3d`, `spike-shape-zero`, `spike-dimension-bound`, `spike-ne0-not-multiple` | yes |
| `R4_5_GGML_UNAVAILABLE` | `spike-stub-unavailable` | yes |
| `R4_5_ABI` | qualification, by asserting the four recorded constants and the whole table | no |
| `R4_5_TYPE_UNSUPPORTED` | `spike-type-unsupported` | yes |
| `R4_5_ALIGNMENT` | `spike-misaligned-member`, deterministically after C14; details `weights` and `output` are not input-reachable | yes |
| `R4_5_GGML_INIT` | qualification, `ALIGN_LLM_GGML_FORCE=init` | no |
| `R4_5_COMPUTE` | qualification, `ALIGN_LLM_GGML_FORCE=compute` | no |
| `R4_5_SOURCE_UNREADABLE` | `spike-reference-missing`, `spike-reference-empty`, `spike-reference-eof`, `spike-reference-mid-member` (C15); qualification, absent reference | yes (C5) |
| `R4_5_SOURCE_DIVERGED` | `spike-reference-diverged`; qualification, the pack as its own reference | yes (C5) |
| `R4_5_REFERENCE_MISMATCH` | qualification, `ALIGN_LLM_GGML_FORCE=reference` (C11) | no |

---

## 7. Delivered surface, evidence, and what the client learned about Align

### 7.1 What shipped

| File | Role |
| --- | --- |
| `src/alignpack_read.align` | the standalone alignpack v1 reader (section 3.5) |
| `src/ggml_ffi.align` | the **only** module with an `extern` declaration or an `unsafe` block |
| `src/ggml_spike.align` | the CLI, the validation order, the activation, the reference oracle, the document |
| `scripts/ggml_shim.c` | the real shim, compiled against the host's ggml headers |
| `scripts/ggml_shim_stub.c` | the ggml-free stub; the fenced shared region is byte-identical to the real one |
| `scripts/build-ggml-shim` | selects the shim by `ALIGN_LLM_GGML_INCLUDE`, builds into the ignored `build/lib/` |
| `scripts/ggml_spike_fixture.py` | the synthetic alignpack corpus, encoded from the format document |
| `scripts/run-ggml-spike-smoke` | the hosted owner |
| `scripts/run-ggml-spike` | the opt-in qualification |
| `scripts/ggml-spike-golden.jsonl` | thirty-three golden documents |
| `Makefile`, `scripts/check-gate-topology`, `.gitignore` | `ggml-spike`, `ggml-spike-smoke`, `ggml-spike-qualification`; the hosted list in both places; `build/` and the two executable names |

`src/main.align`, `src/alignpack.align`, `src/gguf.align`, and `src/model_ir.align` are **unmodified**.
`make build` links no ggml on any host.

### 7.2 Verification

| Command | Result |
| --- | --- |
| `gmake check` | `ok: checked 29 unit(s) per-unit` |
| `gmake build` | `built executable: main` — unchanged, no ggml on the link line |
| `gmake ggml-spike` (stub) | built; `ALIGN_LLM_GGML_INCLUDE` unset selects `ggml_shim_stub.c` |
| `gmake ggml-spike` (real) | built against `/opt/homebrew/include` and `/opt/homebrew/lib` |
| `gmake ggml-spike-smoke` | `7 no-document cases, 33 documented cases, reader parity, shared shim contract, and lifetime PASS`; consecutive runs identical |
| `gmake ggml-spike-qualification` | `PASS`; numbers in 7.3 |
| `gmake alignpack-smoke` | `20 positive fixtures, 106 negative sources, 14979 assertions … PASS` |
| `gmake gguf-smoke`, `model-ir-smoke`, `expert-trace-smoke` | `PASS`, unchanged |
| `gmake gate-topology-check` | `check gate topology: PASS` |
| `gmake format-check`, `gmake fmt` | clean; `fmt` is a no-op on the three new modules |
| `git diff --check` | clean |

`python3 scripts/check-gate-topology --self-test` fails identically on an unmodified checkout of
`main` in this environment (`lifecycle_errors=('runner-RuntimeError', 'sigkill-PermissionError')`);
it is a sandbox signal-permission limitation, not a property of this change. The Makefile's
`gate-topology-check` target, which is the one in `HOSTED_CHECK_TARGETS`, passes.

### 7.3 The qualification, on the real model

`qwen2.5-coder-7b-instruct-q4_k_m.gguf`, 4,683,073,536 bytes; pack 4,677,222,400 bytes written to a
temporary directory outside the work tree and **removed**, with `reclaimed 4677222400 bytes` printed
by the trap. Selection: block 1, member 1 — `blk.0.attn_q.weight`, Q4_K, `3584 x 3584`, 7,225,344 B.

| Measurement | Value |
| --- | --- |
| `verdict` | **`EXTERNAL`** |
| `buffer.interior_offset` / `buffer.tensor_data_offset` | `14336` / `14336` — **the gate's no-silent-copy clause, discharged** |
| `buffer.pointer_identity` / `output_pointer_identity` | `true` / `true` |
| `buffer.base_alignment` / `weights_pad` / `output_base_alignment` / `output_pad` | `0` / `64` / `0` / `0` on the post-C14 run — a page-aligned base, so the block was landed one full compensation window in |
| `compute.backend_name` | `CPU`, reached through the registry (`load_all` → `dev_by_type` → `dev_init`) |
| `output.sha256` | `2ccc7dc778108df3b626128895347f203795a2d82b502805806fb8472457e044` — **bit-identical to section 2.3's probe digest** |
| `output.bit_sum` / `element_count` / `nonfinite_count` | `30595536514321` / `14336` / `0` |
| `reference.verdict` / `bytes_equal` / `differing_elements` | `IDENTICAL` / `true` / **`0` of 14,336** — **quantized-layout-preserved, discharged** |
| `abi` | `tensor_alignment 32`, `q4k_blck_size 256`, `q4k_type_size 144`, `table_drift -1` across all 25 rows |
| `timings.pread_ns` | `6,829,084` for 17,020,928 B on the final post-C14 run — 2.49 GB/s, warm cache, and it now **includes** the copy of the block into the compensated window (C14). The pre-C14 number, one `pread` and no copy, was `5,080,833` — 3.35 GB/s |
| `timings.compute_ns` | `435,075` — warm mean of five after one warm-up (`464,258` on the first post-C14 run, `550,308` pre-C14; the spread across runs is larger than any difference between them) |
| `timings.reference_pread_ns` / `reference_compute_ns` | `2,387,125` / `584,292` — the ggml-owned arm is again the slower one |
| `timings.elapsed_ns` | `316,991,959` end to end, including registry load and the reference arm; `133,918,250` and `149,779,625` on the other two post-C14 runs, and the spread is host load, not the boundary |
| `lifetime` | buffers `4/4`, contexts `2/2`, backends `1/1`, `released_before_owner_scope_end true`; no abort at `exit` |
| forced failures | `init -> R4_5_GGML_INIT`, `compute -> R4_5_COMPUTE`, `reference -> R4_5_REFERENCE_MISMATCH` |
| named `N/A` lines | expert block, GPU arm, discrete VRAM — each printed with its reason and its section reference |

The qualification was run twice before the review repair and three times after it, end to end, on
the real model. Every run reproduced `sha256 2ccc7dc7…e044`, `interior_offset == tensor_data_offset ==
14336`, `IDENTICAL` with `differing_elements 0`, and balanced lifetime counts; the pre-repair runs
measured `pread 5,080,833 / 6,287,208 ns`, `compute 550,308 / 517,075 ns`, and
`reference compute 560,792 / 538,125 ns`. Every run removed the pack — `reclaimed 4677222400
bytes` — and left no file behind in the temporary directory.

**C14's compensation costs one copy and does not move the answer.** `tensor_data_offset` is still
`14336`, still equal to `interior_offset`, and still `EXTERNAL`, because the offset is measured from
block byte 0 and block byte 0 is now the thing that was aligned. What it costs is visible in
`pread_ns` and nowhere else: 6,829,084 and 6,997,417 ns against 5,080,833 ns for the same 17,020,928
bytes, the difference being one 17 MB copy into the compensated window. The digest and the reference
verdict are bit-identical across the change.

The external-versus-internal compute comparison is the answer the roadmap needed: **435,075 ns over
Align-owned memory against 584,292 ns over ggml-owned memory on the final run, 464,258 against
750,625 ns on the first post-repair run, and 550,308 against 560,792 ns before it.** There is no
penalty for computing
out of caller memory, which is the expected result for a backend that was handed a pointer, and it
is now measured by the shipped capability rather than by a probe.

### 7.4 What this client learned about Align

`CLAUDE.md` requires recording a language-owned requirement even when a workaround exists. This
document does not edit `docs/align-requests.md`; the orchestrator owns the register. Classified:

**Genuine Align gaps, confirmed or newly found.**

1. **FFI aggregates and `bool` on AArch64** — section 5.5.1's candidate Request 32, confirmed
   unchanged at the pin. It is the whole reason `scripts/ggml_shim.c` exists.
2. **An aligned heap allocation** — section 5.5.2's candidate Request 33, and the evidence is now
   **stronger than section 2.4's**. The same `buffer` reservation came back 32-aligned on one run
   and 16-aligned on the next, on the same host, for the same input; the shipped arm's own
   `weights_pad` alternates between 16 and 48 across runs of one fixture. Corrections C9 and C14 are
   the shipped workaround, and the price is now measured: an over-reservation and an interior offset
   on **both** device-visible windows, plus one copy of the block into the aligned window, in every
   consumer that hands memory to a device. C14 also records what the absence of the language feature
   nearly cost — a verdict that depended on the allocator's mood rather than on the container.
3. **A `Result` ok payload must be a scalar.** `Result<raw, Fault>` and `Result<buffer, Fault>` are
   both rejected at the pin. The consequence for an FFI wrapper is that a fallible constructor
   cannot return a handle *and* a reason; it must return a null sentinel and let the caller invent
   the reason (correction C3). The consequence for a reader is that a function cannot return an
   owned window at all, so `read_reference` takes a `borrow mut buffer` out-parameter.
4. **`buffer(N)` is an advisory hint with no accessor and no failure signal.** There is no
   `.capacity()`, a reservation of any size succeeds, and a program cannot ask whether the window it
   asked for exists before it fills it. `R4_WINDOW_UNAVAILABLE` is therefore a code no client can
   test (correction C8), and `scripts/run-alignpack-smoke` had already reached the same conclusion
   from the other direction.
5. **`fs.open_ro` does not exist.** Section 5.4 already records this as Request 21's third client;
   the spike opens a multi-gigabyte pack it has every reason to keep immutable with `O_RDWR`.

**Application concerns, not language gaps.**

- A Borrow argument crossing an FFI wrapper must be a stable named local. This is a legible
  restriction with a legible fix, and it made section 4.3's replacement invariant a compile-time
  property instead of a review item — the diagnostic improved the design.
- `array_builder<T>` has no random-access accessor, so a monotonicity check over a column being
  built carries its own one-value cursor. Local and cheap.
- "huge struct copy" warnings on `borrow`-passed records are pre-existing repository-wide noise
  (`src/alignpack.align` alone emits 85) and are a diagnostic about the shape of the record, not a
  defect introduced here.
