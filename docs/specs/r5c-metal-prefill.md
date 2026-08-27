# R5C-METAL-PREFILL-ARM: the same Align-owned window, handed to Metal

Status: design of record for the R5C capability.
Owner document for `docs/specs/roadmap.md` section R5's **required microbenchmark A**, on unified
memory.
Align pin: `.align-revision` = `4b515f8d37de2e9a9ba06170c5842fd12dc1cba2`.
Predecessor: [`r5b-model-prefill-forward.md`](r5b-model-prefill-forward.md), whose schedule, window
sizing rule, node tables, residual carry, slot store, shim contract, teardown order, and three
oracles this capability reuses **without modifying any of them**.
Inputs it consumes verbatim: [`r4-5-external-buffer.md`](r4-5-external-buffer.md) section 2.5's
Metal measurement, `r5b-model-prefill-forward.md` section 2.7's byte-identical logits vector
(`sha256` `d2e48620…`), and that document's section 3.3 operand grammar.

This document triggers the proportional design gate of `CLAUDE.md` on four counts: a new public CLI
arm, a new versioned exchanged document (`R5_MODEL_FORWARD_GPU`), a new ownership boundary (an
Align-owned window borrowed by a *device* rather than by a CPU backend), and a coordinated invariant
across four modules. Section 3 is the single public-contract ledger, section 4 is the closure
matrix, and section 5 owns fixtures, qualification, metrics, deferrals, risks, and candidate Align
requests.

Section 2 is the probe record and it is first on purpose. Every contract in section 3 was chosen
after the probe, and the acceptance tolerance of section 3.7 is a number the probe produced rather
than a number this document argued for. Six of the design's decisions exist **only** because a probe
refuted the plan this document started with: Metal turned out to be **bit-deterministic** rather than
nondeterministic, it needs **no** 16 KB alignment rule, the 447 MB window is **nowhere near** the
device's buffer limit, an oversize wrap **crashes instead of returning null**, the per-layer residual
comparison the plan intended to gate on is **dominated by a single massive-activation channel** and
cannot be a gate, and the "no-copy transfer" that R4.5 recorded as free costs a measured
**11.8 ms per window**.

---

## 1. Purpose, scope, non-goals, and the gate

### 1.1 Goal

`docs/specs/roadmap.md` section R5 requires three microbenchmarks: `A: transfer + GPU compute`,
`B: CPU compute`, `C: async prefetch + GPU compute`. R5B discharged **B** at whole-model scale and
deferred **A** and **C**, inheriting `r4-5-external-buffer.md` section 5.4's deferral with its
evidence: Metal accepts the same host pointer with no copy on unified memory, but does not produce
bit-identical output, so a GPU arm needs "a tolerance contract, which is a different design decision
with a different acceptance rule".

R5C is **that decision and only that decision**: the same thirty graphs, the same six-token prefill,
the same alignpack container, and the **same Align-owned weight window**, handed to the Metal device
through `ggml_backend_dev_buffer_from_host_ptr` instead of to the CPU backend, checked against the
byte-identical CPU logits vector R5B already publishes.

The question it answers is not "does Metal compute" — R4.5 answered that for one matmul. It is:
**when a whole twenty-eight-layer model is streamed through one Align-owned window that the GPU
borrows rather than copies, is the answer still the model llama.cpp computes, and what does the
transfer actually cost when there is no transfer?**

The capability that answers it is **R5C-METAL-PREFILL-ARM**: a new arm of the existing `ggml-spike`
executable, `--model-forward-gpu`, taking R5B's operand positions unchanged, selecting the registry's
GPU device, validating the window against that device's own buffer limit **before** the first wrap,
running R5B's schedule, and emitting an `R5_MODEL_FORWARD_GPU` document carrying the same per-layer
digests, the same lifetime counters, and a **tolerance** logits verdict whose bound section 3.7 fixes
from section 2's measurement.

### 1.2 In scope

- One new Align module, `src/gpu_forward.align`, owning the GPU arm's device selection, its device
  validation, its tolerance oracle, and its document. Section 5.5 records why it is a *new module*
  rather than four hundred more lines of `src/model_forward.align`.
- A `DeviceKind` parameter threaded through `src/model_forward.align`'s existing stages. **No stage
  changes shape**: the schedule, the window sweep, the residual carry, the narrowing, and the head
  are R5B's, called with a different device handle.
- Three new one-call wrappers in `scripts/ggml_shim.c` and `scripts/ggml_shim_stub.c` and their
  declarations in `src/ggml_ffi.align`: `device_by_kind`, `device_buft_max_size`, and
  `device_props`. Every op in all three node tables is already shipped by R5A and R5B.
- One new CLI arm, `ggml-spike --model-forward-gpu`, and the `R5_MODEL_FORWARD_GPU` document at
  `schema_version: 1`.
- Two oracles carried over **bit-exact** — the self-reference oracle (section 2.8 measured it holds
  on Metal) and the transcript oracle's grammar, coverage, and element-count rules — and one new
  **cross-device tolerance** oracle against `d2e48620…`, whose bound section 3.7 derives from
  section 2.4's measurement.
- One owner test extension that runs without ggml, without Metal, without a model, and without
  llama.cpp; and one named focused qualification that requires all four.

### 1.3 Non-goals

- **No discrete VRAM.** Unchanged from `r4-5-external-buffer.md` section 5.4 and unanswerable on this
  host: `ggml-cuda.h` has no `buffer_from_host_ptr` counterpart, only host page-locking for
  *transfer*, and there is no discrete device here. Section 5.4 keeps it `N/A` with that evidence
  rather than generalizing from unified memory.
- **No microbenchmark C.** Async prefetch needs a task that performs I/O into the Align-owned window
  while the device computes. Section 2.10 measures precisely why that is not expressible at this pin,
  and section 5.5 files it as a candidate Align request rather than building a workaround around it.
- **No KV cache, no decode, no residency policy, no MoE, no second architecture, no new container
  version, no sampling.** All inherited unchanged from `r5b-model-prefill-forward.md` section 1.3.
- **No change to `--model-forward`.** R5B's arm, its `R5_MODEL_FORWARD` document, its `IDENTICAL`
  verdict, and its checked-in goldens are **byte-unchanged** by this capability. Sections 3.1 and 3.2
  are the two decisions that guarantee it.
- **No claim that the GPU is faster.** Section 1.5 records the cost ceiling before implementation and
  section 5.3 records the measured result, which is a regression. Both are stated as outcomes of
  microbenchmark A, not as a failure of the capability.

### 1.4 Gate statement

| Gate item | Verdict | Evidence |
| --- | --- | --- |
| required microbenchmark **A** — transfer + GPU compute | **Discharged on unified memory.** The transfer is a pointer hand-off that copies **zero bytes** — 339 placements per pass, all external — and costs a measured **12.4 ms per 447 MB window wrap**, **732 ms over the shipped arm's fifty-nine wraps** (correction C7). GPU compute at the reconciliation width is **375 ms** against the CPU's **486 ms** on the same host in the same session, and end to end the two arms are **within this host's `pread` variation** of each other | **Section 7.2 (the shipped arm)**; sections 2.7 and 2.9 are the single-pass probe the design was drawn from |
| — its correctness half | **Discharged.** 152,064 logits within **0.2937** of the byte-identical CPU vector, `argmax` 671, top ten identical in order, **zero** elements over 0.5, and five consecutive runs **byte-identical to each other** | Section 2.3, section 2.4 |
| required microbenchmark **B** — CPU compute | **Discharged by R5B.** Not re-litigated here | `r5b-model-prefill-forward.md` section 1.4 |
| required microbenchmark **C** — async prefetch + GPU compute | **Deferred, with the blocker named and measured.** A spawned task cannot capture the Align-owned window: *"a lambda cannot capture the owned value 'w' yet (capture supports copy values like int/float/bool/char)"* | Section 2.10, section 5.5's candidate Request 41 |
| discrete VRAM | **`N/A`.** No such device on this host and no equivalent entry point | Section 1.3, inheriting `r4-5-external-buffer.md` section 2.5 |

The honest summary is: **R5C closes R5's microbenchmark A on unified memory, for a dense CPU-packed
model at prefill, and for nothing else.** Benchmark C remains open behind a named Align gap; discrete
VRAM remains unanswerable here; and the measured performance result is that **the device choice does
not move end-to-end prefill time on this host by more than the file read varies between runs** —
three paired runs of the shipped arm at 1.31x, 0.99x, and 1.05x, median **1.05x**, recorded as
unresolved rather than claimed (section 7.2). Section 2.9's 1.20x is the single-pass probe's figure
on a colder cache and is not the shipped arm's.

### 1.5 The recorded cost ceiling

`CLAUDE.md`'s performance-claim row requires a cost ceiling recorded **before** implementation, and
`docs/specs/c8-speed-first.md` section 1's ppm-floor rule requires that a measured result far below
its recorded ceiling be reported as a **ceiling-estimation miss** rather than quietly absorbed.

**C8's 2,000 ppm shipping floor does not apply to R5C**, for a concrete reason and not by exemption:
C8's floor is calibrated against the C8 fixed task's ~46 ms total, and R5C is not on that path at
all. Its share of time to a passing patch is **0 ppm**. Its metric is the named secondary metric
microbenchmark A. The *discipline* still applies, so the ceiling is recorded here, before
implementation:

| Quantity | Value |
| --- | --- |
| What a perfect GPU arm could remove | the CPU arm's entire compute, **500.7 ms** of a 2,074.3 ms prefill — **241,400 ppm** of the arm's own wall |
| What it cannot remove | `pread`, **1,423.8 ms**, 68.6% of the wall; the GPU does not read the file |
| Recorded expectation | **negative.** R4.5 measured Metal 2.5× slower on one small Q4_K matmul, and a six-token prefill is the same memory-bound shape twenty-eight times |
| Measured result (**section 7.2**, the shipped arm) | **−110.7 ms compute and +732.3 ms wrap** at the reconciliation width — a net regression dominated by the transfer, within the recorded expectation. Section 5.3's `+22.6 ms compute and +354.7 ms wrap = +377.3 ms, or −181,900 ppm` is the single-pass probe's arithmetic and is left as the probe record it is |

The ceiling was recorded as *negative* and the result is between parity and 1.3x slower, so this is
**not** a ceiling-estimation miss. **A "GPU slower" result is a legitimate outcome of microbenchmark A.** The
primary acceptance criterion for R5C is correctness; the timing is the measurement the benchmark
exists to publish, and publishing an unfavourable number is the benchmark working.

---

## 2. Probe record

Everything in this section was executed on this host before section 3 was written. Commands are
given exactly as run. Probe sources live outside the work tree and are not part of the capability;
what ships is section 3's design, and section 5.2's qualification is the probe made reproducible.
Every probe artifact — harnesses, logits files, node dumps — was deleted on completion.

### 2.1 Host, device, toolchain

| Item | Value |
| --- | --- |
| Host | `MacBookAir10,1`, Apple M1, 16 GiB, `darwin/arm64`, ~30 GiB free |
| Align compiler | the managed pinned release toolchain at `4b515f8d37de2e9a9ba06170c5842fd12dc1cba2` |
| ggml | `0.21.0`, Homebrew; Metal backend `dlopen`ed from `libexec/libggml-metal.so` through the registry |
| llama.cpp | `build 10566`, providing `llama-debug` and `llama-eval-callback` |
| Model | `qwen2.5-coder-7b-instruct-q4_k_m.gguf`, 4,683,073,536 bytes |

The Metal device, as the registry reports it:

```text
ggml_metal_device_init: GPU name:   MTL0 (Apple M1)
ggml_metal_device_init: GPU family: MTLGPUFamilyApple7  (1007)
ggml_metal_device_init: has unified memory    = true
ggml_metal_device_init: use residency sets    = true
ggml_metal_device_init: use shared buffers    = true
ggml_metal_device_init: has tensor            = false   # tensor API disabled for pre-M5
ggml_metal_device_init: recommendedMaxWorkingSetSize  = 12713.12 MB

BACKEND MTL0 type=1 alignment=32 max_size=9534832640 from_host_ptr=1 host_buffer=0
        mem_free=12712722432 mem_total=12713115648
```

**Fact 1 — the Metal buffer-type alignment is 32, exactly the CPU's.** The plan expected the GPU to
declare a stricter rule and section 3.5 to have to carry a second alignment argument. It does not.
R5B already places every member at a `MAX_TENSOR_ALIGNMENT`-aligned (64 B) window offset, which is
strictly stronger than either backend asks for, so **R5C inherits R5B's alignment rule unchanged and
adds nothing**.

**Fact 2 — the device's maximum buffer length is 9,534,832,640 B, and the window is 4.7% of it.**
`ggml_backend_buft_get_max_size` reports 8.88 GiB. R5B's 447,086,592 B window is nowhere near it —
and neither is the whole 4.68 GB model, at 49%. **The window does not have to be split, and section
3.5's per-block-class windows stay a deferred *optimization* rather than becoming a correctness
requirement.** The plan had budgeted a design for splitting; the measurement removed it.

### 2.2 Probe 1 — the CPU oracle vector, re-established from scratch

R5B's probe artifacts were deleted, so the oracle vector was regenerated before anything was
compared against it. The R5B harness was re-run unchanged on the CPU device at the reconciliation
width:

```text
$ ALIGN_R5B_PADKV=256 ALIGN_R5C_BACKEND=cpu ./metalfwd MODEL.gguf cpu256.bin 750 912 2877 11 293 1648
LOGITS sha256=d2e48620ae3e31e2066a6172aa32c19c974d996d232ab91b118335e3d245bf74
       bit_sum=425868724161277 f32_sum=-232073.906250 argmax=671 val=17.850067
```

**The `sha256` is `r5b-model-prefill-forward.md` section 2.7's, to the character**, as are the
`bit_sum` and the f32 sequential sum the transcript prints. R5B established that this file is
byte-identical to `llama-debug --save-logits`, so the CPU arm's output at width 256 **is** the
instrument's vector and the Metal comparison below is a comparison against llama.cpp, not against a
sibling implementation. The oracle chain is re-established without re-running the instrument.

### 2.3 Probe 2 — the whole model on Metal

The same harness, the same window, the same thirty graphs, `ggml_backend_dev_by_type` changed from
`GGML_BACKEND_DEVICE_TYPE_CPU` to `..._GPU`:

```text
$ ALIGN_R5B_PADKV=256 ALIGN_R5C_BACKEND=metal ./metalfwd MODEL.gguf mtl256.bin 750 912 2877 11 293 1648
WINDOWFIT window=447086592 max_size=9534832640 fits=1
LOGITS sha256=b6e473e86ca903e27d1242d81cc7224ce2edfef043a425d17129ef878fc5f556
       bit_sum=427529168899916 f32_sum=-237902.906250 argmax=671 val=17.840048
```

The harness aborts with `COPIED` if any weight tensor's `ggml_get_data(t)` differs from its own
window offset. It did not: **all 339 placements per pass are external on Metal, exactly as on the
CPU.** R4.5's fact 1 holds at model scale — Metal takes the pointer and copies nothing.

Against the section 2.2 vector:

```text
elements      152064
max |D|       0.293651 at index 47118     metal = -2.096647   cpu = -1.802995
mean |D|      0.052888   median 0.046840   p99 0.165537   p999 0.208949
range         28.927321
over 0.5      0          over 1.0  0
argmax        671 both
top10         [671, 220, 470, 715, 2529, 256, 2303, 262, 257, 414]  identical, in order
```

**`argmax` and the whole top ten agree, and no logit moves by half a unit.** The worst element is
**2,937 ten-thousandths**, which is 1.02% of the logits' range. This is the measurement section 3.7's
tolerance is derived from, and it was taken before that tolerance was written.

### 2.4 Probe 3 — five runs, and Metal is not nondeterministic

The plan assumed Metal would be nondeterministic run to run and that section 3.7 would need a
stability allowance on top of the cross-device bound. **It does not.** Five consecutive full-model
runs:

```text
$ for i in a b c d e; do ... ./metalfwd MODEL.gguf mtl256_$i.bin 750 912 2877 11 293 1648; done
$ shasum -a 256 mtl256_*.bin
b6e473e86ca903e27d1242d81cc7224ce2edfef043a425d17129ef878fc5f556  mtl256_a.bin
b6e473e86ca903e27d1242d81cc7224ce2edfef043a425d17129ef878fc5f556  mtl256_b.bin
b6e473e86ca903e27d1242d81cc7224ce2edfef043a425d17129ef878fc5f556  mtl256_c.bin
b6e473e86ca903e27d1242d81cc7224ce2edfef043a425d17129ef878fc5f556  mtl256_d.bin
b6e473e86ca903e27d1242d81cc7224ce2edfef043a425d17129ef878fc5f556  mtl256_e.bin
```

**Byte-identical, five for five, over 152,064 f32.** The run-to-run component of the tolerance is
therefore exactly **zero**, and section 3.7 turns that into a *contract* rather than discarding it:
the GPU arm publishes `output.sha256` and the qualification asserts two consecutive runs agree. A
future ggml or driver change that introduces nondeterminism becomes a visible failure instead of
being absorbed into a bound that was sized for it.

The same held at the runtime width: two runs at `KV_WIDTH` 6 produced identical
`17c7950cf50830b407e053a8af492e0b53e4c9538a2ec411a16af579ac25303a`.

**One more fact the widths settle.** Comparing each arm against the section 2.2 vector:

| Arm | max `\|Δ\|` | worst index |
| --- | --- | --- |
| CPU at width 6 (R5B's runtime pass) | 0.2739 | 90771 |
| Metal at width 256 | **0.293651** | 47118 |
| Metal at width 6 | **0.293652** | 47118 |
| Metal at width 256 vs CPU at width 6 | 0.270674 | 64488 |

**The two error sources do not compound.** The KV-width difference and the Metal-kernel difference
are the same order and occur at *different* elements, so the Metal arm's worst case is the same
0.2937 at either width. Section 3.7 nevertheless fixes the acceptance comparison at the
**reconciliation width**, because only there is the reference byte-identical to the instrument and
the residual difference attributable to exactly one cause — which is `r5b-model-prefill-forward.md`
section 3.7's discipline, applied to a device change instead of a width change.

### 2.5 Probe 4 — the per-layer residual, and why it cannot be a gate

The plan intended to gate each layer's `l_out` against the CPU arm's with an absolute ceiling. The
measurement refutes that, and the refutation is the most useful thing in this section.

Every layer's `l_out` was dumped from both arms and compared elementwise:

```text
node        ne          max|D|     mean|D|        node        ne          max|D|     mean|D|
l_out-0    [3584,6]   0.038588    0.004284       l_out-14   [3584,6]  15.973389    0.036070
l_out-1    [3584,6]   0.103230    0.005536       l_out-20   [3584,6]  16.195557    0.050245
l_out-2    [3584,6]   0.101782    0.007004       l_out-25   [3584,6]  10.436768    0.109963
l_out-3    [3584,6]  17.773193    0.022455       l_out-26   [3584,6]   1.497559    0.136415
l_out-4    [3584,6]  18.584351    0.023581       l_out-27   [3584,1]   1.052490    0.163184
l_out-5    [3584,6]  18.205566    0.024619       result_norm[3584,1]   0.380096    0.042393
```

The maximum jumps by 175× between layer 2 and layer 3 while the **mean** moves by 3.2×. That is not
a defect appearing at layer 3, and the cause is a single element:

```text
l_out-3   max|D|= 17.773 at index 2570 (row 2570, col 0)  cpu= -1485.955  rel = 1.20e-2
l_out-4   max|D|= 18.584 at index 2570                    cpu= -1978.977  rel = 9.39e-3
l_out-14  max|D|= 15.973 at index 2570                    cpu= -3267.012  rel = 4.89e-3
l_out-26  max|D|=  1.498 at index 2570                    cpu= -2177.394  rel = 6.88e-4
```

**Every layer's worst absolute difference is the same channel, row 2570, and that channel carries a
value three orders of magnitude above the typical element.** This is Qwen2's massive-activation
channel; at layer 3 it holds −1,485.95 while nine of 21,504 elements exceed an absolute difference of
1.0 at all. Its *relative* error is 1.2% at layer 3 and **falls** monotonically to 0.07% by layer 26.

Three consequences, and section 3.7 takes all three:

1. **An absolute per-layer ceiling is meaningless.** It would have to be ≥ 19 to pass, which would
   admit any defect at all in the other 21,495 elements.
2. **A relative ceiling is no better.** Relative error over elements with `|ref| > 1` reaches 0.54 at
   layer 26 — on values near 1.0, where relative error is noise.
3. **Therefore the per-layer residual is recorded and never gated.** `schedule[]` publishes each
   layer's digest and its max absolute and relative difference so that a regression names *which*
   layer moved, and the acceptance contract is the logits alone. This is the same division R5B chose
   for `schedule[].l_out_sha256` — "recorded and not asserted as a checked-in golden" — reached here
   by measurement rather than by inheritance.

### 2.6 Probe 5 — alignment, the buffer limit, and a wrap that fails open

Three questions the plan raised, answered by one probe.

**Metal needs no 16 KB alignment.** The host page size is 16384. A 16384-aligned base was wrapped at
fifteen byte offsets:

```text
page size = 16384
  off      0 -> gpu buf=0xc60808480 base=0x55f400000 same=1
  off      1 -> gpu buf=0xc60808480 base=0x55f400001 same=1
  off      2 -> ... same=1        off      8 -> ... same=1
  off     32 -> ... same=1        off   4096 -> ... same=1
  off  16384 -> ... same=1
```

**Every offset down to one byte is accepted and the buffer's base is the pointer handed over.**
`r4-5-external-buffer.md` section 2.5's "Metal accepted an 8-byte-offset pointer where the CPU
aborted" is confirmed and generalized: Metal imposes no wrap alignment at all. The CPU's abort was
`ggml_backend_tensor_alloc`'s buffer-type alignment assertion, not a wrap requirement, and R5B
already satisfies it. **Metal is the more permissive backend, so R5C relaxes nothing and adds no
alignment rule.**

**An oversize wrap does not return null — it crashes.** This is the finding that adds a validation
step:

```text
$ ./overprobe                                   # wrap a 1 MiB allocation, claiming max_size bytes
CASE 1 MiB (valid)      len=1048576
   -> buf=0x97ac20480 base=0x97a818000 mine=0x97a818000 same=1 size=1048576
CASE max_size exactly   len=9534832640
ggml_metal_buffer_map: error: failed to allocate buffer, size =  9093.12 MiB
$ echo $?
139
```

**`ggml_backend_dev_buffer_from_host_ptr` on Metal logs a failure and then segfaults**; it does not
return `NULL`, so a null check cannot catch it. Section 3.9 therefore validates
`window_bytes <= ggml_backend_buft_get_max_size(buft)` **before the first wrap**, as
`R5C_DEVICE_BUFFER_LIMIT`, and section 3.10 records that this is a fail-closed guard over a
crash rather than over an error.

**The teardown fact, sharpened.** R4.5 recorded that an unfreed Metal host buffer aborts at exit.
Three orderings:

```text
buffer freed, then backend freed   -> exit 0
backend freed, then buffer freed   -> exit 0     (tolerated)
buffer never freed                 -> exit 134   (SIGABRT, during process exit)
```

**Freeing is what matters, not the order.** On the CPU a leaked buffer is a leak; **on Metal it is a
process abort**, which makes R5B's per-layer `lifetime.*_created == *_freed` assertion load-bearing
rather than merely tidy. Section 3.10 says so and section 4 keeps the assertion at every graph
boundary.

### 2.7 Probe 6 — the transfer that copies nothing and is not free

R4.5 recorded the no-copy hand-off as the good news and did not time it. It costs real time, and at
thirty wraps per prefill it is the dominant difference between the two arms.

Page-aligned host allocations, pre-faulted, wrapped and freed five times each:

```text
wrap    1048576 B  gpu=   0.035 ms   cpu=  0.0002 ms
wrap   16777216 B  gpu=   0.288 ms   cpu=  0.0004 ms
wrap  134217728 B  gpu=   2.435 ms   cpu=  0.0004 ms
wrap  447086592 B  gpu=  11.491 ms   cpu=  0.0002 ms      # R5B's window
wrap 1073741824 B  gpu=  29.605 ms   cpu=  0.0004 ms
```

**The cost is linear in the mapped length at roughly 26 µs/MB, and the CPU's is flat at 0.0002 ms.**
This is page-table and residency-set work over the range, not a byte copy — the bytes never move,
and `base == ptr` throughout. In the whole-model run it appears as thirty wraps of the 447 MB window:

```text
WRAP  total_ms=354.805 calls=30 per_call_ms=11.827 bytes_per_call=447086592   # Metal
WRAP  total_ms=  0.075 calls=30 per_call_ms= 0.003 bytes_per_call=447086592   # CPU
```

**This is microbenchmark A's "transfer", and the honest statement is that on M1's unified memory the
transfer moves zero bytes and still costs 354.8 ms per prefill.** Calling it a no-op because nothing
is copied would be the kind of claim this repository's benchmark rules exist to prevent.

**The cost is avoidable, and the measurement says by how much.** Wrapping the window **once** and
reusing the view across all thirty graphs — freeing each graph's tensor context as before, but not
the buffer:

```text
$ ALIGN_R5C_WRAPONCE=1 ... ./metalfwd ...
TOTAL wall_ms=2138.293 build_ms=7.721 compute_ms=511.094
WRAP  total_ms=75.610 calls=1 per_call_ms=75.610
$ cmp mtl_once.bin mtl256_a.bin        # (no output)
```

**One wrap costs 75.6 ms instead of 354.8, the logits are byte-identical, and 279 ms of wrap
disappears.**

**75.6 ms for one wrap is not the 11.6 ms the 26 µs/MB line predicts, and the two are deliberately
presented separately rather than reconciled.** They are not the same measurement: the scaling table
above wraps **pre-faulted** allocations five times each and reports the steady state, while this
variant's single wrap is the **first touch** of a 447 MB range — it pays the page-fault and
residency-set work for the whole range once, where the thirty-wrap loop pays it on wrap 1 and then
re-maps a range that is already resident (354.8 − 75.6 = 279.2 over the remaining 29 wraps is
9.6 ms each, below the 11.8 ms average that includes the first). The probe did not isolate
first-touch cost, so this is the reading the numbers support and not a decomposition it measured.
**The figure that generalizes is the per-wrap steady-state one**, and section 7.2's shipped arm
measures it at 12.4 ms over fifty-nine wraps, agreeing with this section's 11.8 ms. Section 5.4 defers it deliberately rather than shipping it: hoisting the wrap out of
the per-graph loop removes the per-layer buffer free that R5B's window-reuse invariant asserts, and
section 2.6 has just established that on Metal an unfreed buffer aborts the process. The optimization
is real, measured, and belongs in the capability that also re-establishes the invariant it weakens.

### 2.8 Probe 7 — the self-reference oracle survives the device change

R5B's oracle 1 builds each graph a second time with its weights allocated by
`ggml_backend_alloc_ctx_tensors` — genuinely ggml-owned, asserted not to alias the host pointer — and
requires every oracle node to be byte-identical. The plan assumed this oracle was CPU-specific and
that R5C would ship two tolerance oracles.

```text
$ ALIGN_R5B_REF=1 ALIGN_R5B_PADKV=256 ALIGN_R5C_BACKEND=metal ./metalfwd ... mtl_ref.bin ...
LOGITS sha256=b6e473e86ca903e27d1242d81cc7224ce2edfef043a425d17129ef878fc5f556
$ cmp mtl_ref.bin mtl256_a.bin        # (no output)
```

**Byte-identical.** The oracle compares two computations on the *same* device and is therefore a
statement about **bytes and pointers**, not about kernels: it is device-independent by construction,
and it is the only oracle that can catch a window reused before its previous tenant was freed.
**R5C keeps it bit-exact and unweakened**, which is why section 3.7 has one tolerance and not three.

Its cost on Metal is high and section 5.2 budgets for it: the reference arm's
`ggml_backend_tensor_set` of 4.37 GB into device buffers took the run from 2.5 s to **20.8 s** wall.

### 2.9 Probe 8 — paired timings

Five alternating warm runs of each arm at the reconciliation width, same session, same page-cache
state, so the pair is comparable even though this host is measurably colder than R5B's session
(`pread` 1.42 s here against R5B's 533 ms warm):

| Quantity | CPU | Metal |
| --- | --- | --- |
| compute, median | **500.7 ms** (465.3–537.4) | **523.3 ms** (518.4–531.6) |
| window wrap, total over 30 | **0.075 ms** | **354.8 ms** (334.3–362.7) |
| graph build, total | 2.1–3.1 ms | 318.4–348.8 ms |
| wall, median | **2,074.3 ms** (2,018.6–2,133.3) | **2,491.3 ms** (2,446.0–2,525.8) |
| `pread`, median | 1,423.8 ms | 1,466.0 ms |

Three warm pairs at the runtime width (`KV_WIDTH` 6): CPU compute median **466.8 ms**, Metal
**528.5 ms**, Metal wrap **364.7 ms**.

**Where the time goes, per graph, from one representative run at width 256:**

| Graph | CPU compute | Metal compute |
| --- | --- | --- |
| layers 0–26, median | 19.52 ms | **18.85 ms** |
| layer 27 (narrowed, `T` = 1) | **6.53 ms** | 10.31 ms |
| head — `MUL_MAT` against 447 MB of Q6_K | 26.57 ms | **12.84 ms** |

**The GPU wins exactly where the work is large and loses where it is small.** It is 2.07× faster on
the head, within noise on a full-width layer, and 1.58× slower on the narrowed last layer, whose
`T` = 1 leaves the device idle. Then the thirty window wraps erase the win. That decomposition is the
most useful thing microbenchmark A produces, and it is what a residency policy will need: the
transfer tax scales with the *window*, and the compute win scales with the *work*.

### 2.10 Probe 9 — what benchmark C needs, and what Align does not have

Microbenchmark C is async prefetch plus GPU compute: a task reads layer `L+1`'s bytes into the window
while the device computes layer `L`. Four programs, checked against the pinned compiler.

**Purity is not the blocker.** `docs/guide/10-closures-and-parallelism.md` requires `Pure` callables
for `par_map`, and `docs/language-spec.md` states the rule exactly — *"Effects restrict optimization
legality, while explicit `par_map` still requires Pure callables"* — naming `par_map` alone.
`task_group` accepts impure work, and it runs:

```align
task_group {
    a := spawn(fn { readsome(p) })      // fs.open_rw + f.pread inside a spawned task
    b := spawn(fn { readsome(p) })
    wait()?
    total = a.get() + b.get()
}
```

```text
$ alignc check tg.align   ->  ok: checked 4 function(s)
$ alignc run   tg.align   ->  128
```

`unsafe` and `extern "C"` inside a spawned task also check and run. **The candidate request this
document set out to file — "impure/I-O work inside `task_group`" — is not a gap. It already works.**

**The blocker is closure capture.** The prefetch task must write into the Align-owned window:

```align
mut w := buffer(4096)
task_group { a := spawn(fn { fill(p, w) }) ... }
```

```text
tg2.align:14:20: error: a lambda cannot capture the owned value 'w' yet
                        (capture supports copy values like int/float/bool/char)
tg2.align:14:33: error: the exclusive borrowed argument to 'fill' must be rooted in mutable storage
```

And a task cannot return the filled buffer either:

```text
tg3.align:1:12: error: Result ok payload cannot be `buffer` — an owned I/O handle/buffer is bound to
                       one local, not collected into an array/slice/box (bind it to a local)
```

A `Copy` `i64` captures and runs correctly, so an address-passing workaround through the existing
`align_ggml_window_copy` FFI symbol would compile. **It is deliberately not proposed.** `CLAUDE.md`
forbids building a compatibility layer around a language-owned gap, and it would put the window's
bounds outside Align's view — precisely what `r5b-model-prefill-forward.md` correction C20 removed
when it replaced a caller-computed `window_bytes` with the borrow's own `slice.len()`.

Section 5.5 files this as candidate **Request 41**, reframed from the plan's guess to what the
compiler actually refuses.

### 2.11 What the probes settle

1. The whole model computes on Metal from the same Align-owned window with **zero bytes copied**, 339
   external placements per pass, `argmax` 671, top ten identical in order, max `|Δ|` **0.293651**
   against the byte-identical llama.cpp vector, and **no element over 0.5**.
2. **Metal is bit-deterministic here**: five consecutive runs byte-identical. The tolerance needs no
   stability allowance, and determinism becomes a contract instead.
3. The per-layer residual's worst absolute difference is one massive-activation channel at row 2570
   carrying values up to 3,267. Per-layer comparison is **recorded, never gated**.
4. Metal's buffer-type alignment is **32**, identical to the CPU's, and its wrap accepts **any** byte
   offset. R5B's 64-byte rule is strictly stronger and is inherited unchanged.
5. The device's maximum buffer length is **9,534,832,640 B** and the window is 4.7% of it. No split
   is required. An oversize wrap **segfaults instead of returning null**, so the limit must be
   checked before the call.
6. An unfreed Metal host-pointer buffer **aborts the process at exit**; either free order is fine.
7. The no-copy transfer costs **11.8 ms per 447 MB window**, linearly in length, **354.8 ms** over
   thirty wraps — against the CPU's 0.075 ms. Wrapping once instead costs 75.6 ms for byte-identical
   output.
8. GPU compute is **523.3 ms** against the CPU's **500.7 ms**; the GPU is 2.07× faster on the head
   and 1.58× slower on the narrowed layer. End to end the GPU arm is **1.20× slower**.
9. The self-reference oracle is **byte-exact on Metal** and carries over unweakened.
10. `task_group` already accepts I/O and FFI. Benchmark C is blocked by **non-`Copy` closure
    capture**, not by purity.

---

## 3. Public-contract ledger

### 3.1 The arm, and why a separate arm rather than a `--backend` flag

R5C ships as **`ggml-spike --model-forward-gpu`**, taking `r5b-model-prefill-forward.md` section
3.3's operand positions and arity set unchanged.

**A trailing `--backend metal|cpu` operand was considered and rejected**, on four grounds:

1. **Arity.** R5B's rule is "exactly four, five, six, eight, or nine operands; **seven is
   `R5_ARITY`**", and the gap is load-bearing — `KV_WIDTH` travels with the transcript. A trailing
   optional flag makes every one of those counts ambiguous by one and turns a rule that is currently
   a closed set into a parity argument.
2. **Validation order.** A device operand in the last position would be validated *last*, while it
   determines which acceptance rule the *first* oracle applies. R5B validates arm selection at step 1
   "before path work"; the device belongs at the same step, not eight steps later.
3. **Blast radius.** `--model-forward`'s contract — including the sentence that its `IDENTICAL`
   verdict means byte-identity and "anything less is a regression, not a tolerance" — becomes
   conditional on an operand's value. Section 3.2 is the same argument for the document.
4. **Precedent.** The CLI already selects on the first operand, for R4.5, R5A, and R5B. A fourth arm
   is the shape this executable has.

The cost is accepted and stated: the two arms share their schedule, and section 3.10 keeps that
sharing in `src/model_forward.align` with a `DeviceKind` parameter rather than duplicating it. **What
differs is the CLI surface, the device, one validation step, one oracle, and the document — not the
computation.**

The rename to `align-runtime` remains deferred on `r5b-model-prefill-forward.md` section 5.4's stated
condition — the executable gaining a residency policy — which R5C does not do.

### 3.2 The document kind, and why a separate kind rather than a `backend` field

R5C emits **`R5_MODEL_FORWARD_GPU` at `schema_version: 1`**, a new kind. Extending
`R5_MODEL_FORWARD` with a `backend` field and a new verdict was considered and rejected.

**The decisive reason is that R5B's `IDENTICAL` rule must not become conditional.** R5B section 3.7
states that at the reconciliation width the verdict is byte-identity over all `n_vocab * 4` bytes and
that "anything less is a regression, not a tolerance". A `backend` field would make that sentence
true only for one field value, which is weakening it by construction — and R5B section 5.1 compares
every expected document **byte for byte**, so its goldens would move for a capability that does not
change its arithmetic.

Two supporting reasons. A consumer keying on `kind` plus `schema_version`, as R5B section 3.8
requires, then gets a **total** function: `R5_MODEL_FORWARD` means bit-exactness was the contract,
`R5_MODEL_FORWARD_GPU` means a tolerance was, and no consumer branches on a field to learn which
acceptance rule produced the verdict it is reading. And the two documents genuinely differ in more
than one field — the GPU document adds a `device` object, replaces `oracle_logits` with a tolerance
block, and publishes wrap timings that have no CPU meaning.

The GPU document **reuses R5B's field layout everywhere it means the same thing**, so tooling that
reads `pack`, `model`, `selection`, `schedule[]`, `window`, `graph`, `head`, `output`, `reference`,
`oracle`, `timings`, `lifetime`, and `abi` reads both.

### 3.3 CLI surface

```text
ggml-spike --model-forward-gpu PACK GEOM.json TOKENS
ggml-spike --model-forward-gpu PACK GEOM.json TOKENS DOC.json
ggml-spike --model-forward-gpu PACK GEOM.json TOKENS DOC.json REF.gguf
ggml-spike --model-forward-gpu PACK GEOM.json TOKENS DOC.json REF.gguf TRANSCRIPT.txt KV_WIDTH
ggml-spike --model-forward-gpu PACK GEOM.json TOKENS DOC.json REF.gguf TRANSCRIPT.txt KV_WIDTH LOGITS.bin
ggml-spike --model-forward-gpu PACK GEOM.json TOKENS -        REF.gguf -              KV_WIDTH LOGITS.bin
```

Exactly four, five, six, eight, or nine operands; **seven is `R5_ARITY`**. Every operand keeps
`r5b-model-prefill-forward.md` section 3.3's meaning, grammar, and bounds verbatim, including
`MAX_PATH_BYTES`, the `-` convention in the document **and** transcript positions
(`r5b-model-prefill-forward.md` section 6, correction C10), `TOKENS` as 1–6 comma-separated ids each
`< n_vocab`, `MAX_PREFILL_TOKENS = 6`, and `KV_WIDTH` in `[token_count, MAX_ATTENTION_WIDTH]` with
`MAX_ATTENTION_WIDTH = 4096` and no default.

The summary block is R5B's rows, in R5B's order, with `backend:` carrying the device name and four
rows appended:

```text
model forward gpu:
...                              # every R5B row, unchanged
device:            <name>        # MTL0
device max buffer: <integer>     # ggml_backend_buft_get_max_size
wrap ns:           <integer>     # the transfer, summed over every window wrap
wrap count:        <integer>     # 30 on a healthy run
logits oracle:     IDENTICAL | WITHIN | FAIL | -
```

`IDENTICAL` remains reachable and is **not** expected: section 2.3 measured a non-zero difference, so
a GPU run reporting `IDENTICAL` would mean the device produced the CPU's bytes exactly. The verdict
is retained rather than removed because removing it would make a surprising-but-correct result
unrepresentable.

### 3.4 Device selection and its validation

**The device is selected through the registry, exactly as R4.5 and R5B select the CPU**:
`ggml_backend_dev_by_type(GGML_BACKEND_DEVICE_TYPE_GPU)`, after `ggml_backend_load_all()` has
`dlopen`ed the backends from `libexec`. R5C names no Metal-specific entry point and includes no
`ggml-metal.h`; `r4-5-external-buffer.md` section 2.5 established that Metal exposes **no**
backend-specific host-pointer function and that the device-generic capability flag is the whole
surface.

Three properties are read and published before any work: `caps.buffer_from_host_ptr`, which must be
true (`R5C_NO_HOST_PTR`); `ggml_backend_buft_get_alignment`, validated exactly as R5B validates the
CPU's (`R5_ABI`); and `ggml_backend_buft_get_max_size`, which section 3.9 checks the window against.

**No device is `R5C_GPU_UNAVAILABLE`**, which is also what the stub shim returns, making every step
before device init reachable hosted.

### 3.5 The window on Metal

**Unchanged from `r5b-model-prefill-forward.md` section 3.5 in every respect**: one Align-owned
window, sized by the same sweep of the block table, **447,086,592 B** on this model, reused thirty
times, filled by `align_ggml_window_copy` through the same 1 MiB transient
(`r5b-model-prefill-forward.md` corrections C5 and C6), with every member placed at a
`MAX_TENSOR_ALIGNMENT`-aligned interior offset.

Section 2.1's fact 1 is why the alignment rule is inherited rather than extended, and section 2.6 is
why it is not relaxed even though Metal would accept a one-byte offset: **the arm's rule stays the
stricter of the two backends' so that a member placement is valid on either device**, which is what
makes a `--model-forward` and a `--model-forward-gpu` run over the same pack comparable.

**One new bound.** Before the first wrap:

```text
window_bytes <= ggml_backend_buft_get_max_size(device_buffer_type)    -> R5C_DEVICE_BUFFER_LIMIT
```

Section 2.6 is why this is a validation step rather than a null check: the call **segfaults** on
failure. On this device the check passes with 4.7% utilization, and it is a fail-closed guard over a
crash — the one class of guard this repository writes even when no input can reach it.

Section 5.4 records per-block-class windows as a **measured optimization**, not a requirement: at
section 2.7's 26 µs/MB, a 149,112,832 B window for the twenty-eight layers would cut each layer's
wrap from 11.8 ms to ~3.9 ms, about **220 ms** per prefill.

### 3.6 The graph — unchanged, and that is the contract

`src/layer_qwen2.align` gains **nothing**. The three node tables, `EMBED_NODE_COUNT` 1,
`LAYER_NODE_COUNT` 36, `HEAD_NODE_COUNT` 3, the `node_when` column, the `node_alt_*` columns
(`r5b-model-prefill-forward.md` correction C2), the mask image, the scalar derivations, and the
slot store are R5B's, walked on a different device.

Section 2.3 is the evidence that this is sound: the same tables produced the same `argmax`, the same
top ten, and a maximum divergence of 1.02% of the logit range. **Every op R5C issues is one ggml
already dispatches to Metal**, and no op was added, removed, or reordered for the device.

`graph.slot_high_water` remains 52 against `slot_capacity` 128, and `node_count_total` remains 874 at
the runtime width and 958 at the reconciliation width.

### 3.7 The oracles, and the tolerance derived before the qualification

**Oracle 1 — bit-exact self-reference. Carried over unweakened.** Section 2.8 measured it
byte-identical on Metal over the whole model. It compares two computations on the *same* device, so
it is a statement about bytes and pointers rather than kernels, and it remains the only check that
catches a window reused before its previous tenant was freed. Threshold: **byte-identical, every
oracle node of every graph**, exactly as R5B. `R5_SOURCE_DIVERGED` and `R5_REFERENCE_MISMATCH` are
unchanged.

**Oracle 2 — the transcript. Grammar and coverage bit-exact; elements not compared.** The
pre-schedule scan (`r5b-model-prefill-forward.md` correction C4) runs unchanged, and every one of its
*structural* rules is an error exactly as in R5B: the grammar (`R5_TRANSCRIPT`), the matched node set
and the element-count rule (`R5_ORACLE_MISSING`), and `kq-L`'s declared `ne0` against `KV_WIDTH`
(`R5_ORACLE_SHAPE`).

**Element comparison is disabled on the GPU arm**, and `oracle.verdict` is `"N/A_DEVICE"` with
`elements_compared: 0`. Section 2.5 is the reason and it is a measurement, not a convenience: the
instrument prints `%12.4f`, R5B's threshold is **one** unit of ten-thousandths, and the massive
activation channel differs by up to 18.58 — 185,844 units. A per-element bound wide enough to pass
would be 185,000× R5B's and would assert nothing. Publishing a number that cannot fail is worse than
publishing `N/A` with the reason, so the arm publishes the reason.

**Oracle 3 — the logits, against `d2e48620…`, with a bound fixed here.**

| `compared_pass` | Verdict | Threshold |
| --- | --- | --- |
| reconciliation (`KV_WIDTH > token_count`) | `WITHIN` | `\|Δ\| <= 6000` ten-thousandths **and** `argmax` equal **and** the top `min(10, n_vocab)` equal, in order (`r5b-model-prefill-forward.md` correction C19) |
| runtime (`KV_WIDTH == token_count`) | `WITHIN` | the same bound; section 2.4 measured the two widths within one ten-thousandth of each other |

**How the bound was derived, from section 2.3's measurement and before this qualification was
written:**

| Input | Value |
| --- | --- |
| measured max `\|Δ\|`, Metal vs `d2e48620…` | **2,937** ten-thousandths (0.293651) |
| mean / median / p99 / p999 | 529 / 468 / 1,655 / 2,089 |
| elements over 5,000 tt (0.5) | **0** of 152,064 |
| run-to-run component | **0** — five runs byte-identical (section 2.4) |
| logit range | 28.927 |
| **derivation rule** | twice the measured worst case, rounded up to the next multiple of 1,000 |
| **bound** | 2 × 2,937 = 5,874 → **6,000** ten-thousandths |

The bound is **2.04× the measured worst case** and **2.07% of the logits' range**, and it sits above
the entire measured distribution's support with a factor of two to spare — nothing reached 5,000.
`r5b-model-prefill-forward.md`'s comparable `WITHIN` bound is 5,000 against its own measured 2,738,
a 1.83× margin; the two numbers are deliberately **not** unified, because they characterize different
causes — a missing KV cache there, GPU kernel accumulation order here — and forcing them to share a
constant because they are numerically close would make a later change to one silently move the other.

**Three guards make the bound something other than slack**, and each is a contract of its own:

1. **`argmax` and the full top ten must agree, in order.** Section 2.3 measured both.
2. **Determinism is asserted, not assumed.** Section 2.4 measured five byte-identical runs, so
   `output.sha256` is stable, and section 5.2 runs the arm **twice** and requires the two digests to
   be equal. A regression that makes Metal nondeterministic fails here rather than hiding inside a
   0.6 bound.
3. **Oracle 1 stays bit-exact.** A defect that moved the arithmetic would have to survive
   byte-identity against a ggml-owned copy of the same weights on the same device, which is the check
   the tolerance does not have to do.

Both comparisons remain integer comparisons and **no float is rendered anywhere**
(`r4-alignpack-layer-major.md` section 2.3).

`LOGITS.bin` must be exactly `n_vocab * 4` bytes (`R5_LOGITS_SHAPE`) and readable
(`R5_LOGITS_UNREADABLE`). A breach of the bound sets `oracle_logits.verdict: "FAIL"` and is **not**
an error code, exactly as in R5B.

### 3.8 `R5_MODEL_FORWARD_GPU`, `schema_version: 1`

Canonical UTF-8 JSON in declaration order, in the R0/R1/R2A/R4/R4.5/R5A/R5B shape.
**Every block below not marked `# new` or `# changed` is `r5b-model-prefill-forward.md` section
3.8's, field for field**, so a consumer reads both documents with one reader.

```text
schema_version    1
kind              "R5_MODEL_FORWARD_GPU"
pack_path, geometry_path, reference_path, transcript_path, logits_path
status, error_code, error_detail, verdict

pack        ... unchanged
model       ... unchanged
selection   ... unchanged
schedule[]  ... unchanged, plus                                             # changed
            l_out_max_abs_diff_ten_thousandths, l_out_max_rel_diff_ppm,
            l_out_worst_index                    # recorded, never gated (section 2.5)
window      ... unchanged, plus wrap_count, wrap_ns                         # changed
graph       ... unchanged
head        ... unchanged
output      ... unchanged
reference   ... unchanged — bit-exact on Metal (section 2.8)
oracle      ... unchanged, with verdict "N/A_DEVICE" and elements_compared 0 (section 3.7)
device      kind, name, description, type_id, buffer_from_host_ptr (bool),  # new
            host_buffer (bool), buffer_alignment, buffer_max_size,
            memory_free, memory_total, window_fits (bool)
oracle_logits present (bool), verdict, compared_pass, byte_identical,       # changed
            max_abs_diff_ten_thousandths, tolerance_ten_thousandths,
            mean_abs_diff_ten_thousandths, p99_abs_diff_ten_thousandths,
            elements_over_half, argmax_primary, argmax_reference,
            top_k_agreement, elements_compared,
            reference_sha256, reference_bit_sum
timings     ... unchanged, plus wrap_ns                                     # changed
lifetime    ... unchanged, including graph_balance_failures (correction C16)
abi         ... unchanged
```

`window.wrap_count` is `30` and `window.wrap_ns` is the transfer — **the two fields microbenchmark A
exists to publish**, and the reason section 3.3 puts them in the summary block too. `device.*` is
read once, before the window is sized, so an error document produced at step 6 still names the device
that refused.

`schedule[].l_out_max_*` are populated only when a CPU reference document is supplied to the
qualification; hosted they are `-1`, which the golden asserts.

`schema_version` is `1` and nominal. Checksums are never floats: `sha256` is `crypto.sha256` over the
exact little-endian f32 bytes, `bit_sum` is the `i64` sum of the u32 bit patterns, and
`f32_sum_millionths` is R5B's sequential accumulation widened to `f64`
(`r5a-dense-layer-forward.md` correction C10). `nonfinite_count` is reported and is never a failure
condition.

### 3.9 Validation order and error codes

First applicable row wins. **R5B's thirty-four steps are inherited in order and unchanged**; R5C
inserts three and modifies two. Steps 1 and 2 return `Err` with no output; step 3 onward produce a
`status: "error"` document. **No ggml state is created before step 20.**

| Step | Change |
| --- | --- |
| 1 | arm selection now accepts `--model-forward-gpu`; arity set unchanged → `R5_ARITY` |
| 2–19 | **unchanged**, verbatim from R5B — every one reachable with the stub shim |
| 20 | `align_ggml_available()` → `R5_GGML_UNAVAILABLE`. **This is still where the stub stops** |
| **20a** | **new.** GPU device present → `R5C_GPU_UNAVAILABLE`, detail `device`, `verdict: "UNAVAILABLE"` |
| **20b** | **new.** `caps.buffer_from_host_ptr` is true → `R5C_NO_HOST_PTR`, detail the device name |
| 21 | `align_ggml_tensor_alignment()` and table drift, now read from the **device's** buffer type → `R5_ABI` |
| **21a** | **new.** `window_bytes <= ggml_backend_buft_get_max_size(buft)` → `R5C_DEVICE_BUFFER_LIMIT`, detail `window[<n>]/max[<n>]`. **Before the first wrap** (section 2.6) |
| 22–29 | **unchanged** |
| 30–31 | transcript arm: grammar, coverage, and `kq-L` `ne0` checks unchanged; **element comparison skipped**, `oracle.verdict: "N/A_DEVICE"` (section 3.7) |
| 32–33 | logits arm: section 3.7's bound replaces R5B's two-row table |
| 34 | teardown in section 3.10's order, then render, then write |

Note that step 21a is checked **after** the window sweep at step 16 and **before** step 23's device
init and step 24's first graph, which is the only ordering that can report a too-large window as a
document rather than as a signal.

**Error codes: R5B's thirty-two inherited unchanged, plus three new.** The new ones take an `R5C_`
prefix rather than `R5_` deliberately — they are conditions only the GPU arm can reach, and a shared
prefix would suggest `--model-forward` can raise them.

| Code | Meaning | Step | Detail |
| --- | --- | --- | --- |
| `R5C_GPU_UNAVAILABLE` | **new.** No device of type GPU in the registry, or the stub shim | 20a | `device` / `stub` |
| `R5C_NO_HOST_PTR` | **new.** The device does not advertise `buffer_from_host_ptr` | 20b | the device name |
| `R5C_DEVICE_BUFFER_LIMIT` | **new.** The computed window exceeds the device's maximum buffer length | 21a | `window[<n>]/max[<n>]` |

`R5C_GPU_UNAVAILABLE` is the whole owner test's baseline, exactly as `R5_GGML_UNAVAILABLE` is R5B's:
the stub shim has no Metal, so every hosted case reaches it and steps 1–19 stay fully reachable
without ggml, without a device, without a model, and without llama.cpp.

### 3.10 Ownership, allocation, lifetime, and teardown

| Module | Owns | Imports |
| --- | --- | --- |
| `src/layer_qwen2.align` | the three node tables — **unchanged by R5C** | `core.json`, `core.math` |
| `src/ggml_ffi.align` | **every** `extern "C"` and **every** `unsafe`, plus three new wrappers | none |
| `src/model_forward.align` | R5B's arm and schedule, now taking a `DeviceKind` | the two above |
| `src/gpu_forward.align` | **new.** device selection, device validation, the tolerance oracle, the GPU document | the three above |
| `src/ggml_spike.align` | arm selection and the CLIs | the three arms |

**Weights are Align-owned; the residual stream is Align-owned; the logits are Align-owned; per-graph
activations are ggml-owned.** Every clause of `r5b-model-prefill-forward.md` section 3.10 holds, with
three device-specific additions.

- **The window is still Align's, and Metal borrows it.** Section 2.3 measured 339 external placements
  per pass with `ggml_get_data(t) == base + offset` at every one, so `verdict: "EXTERNAL"` is the
  same measurement across the same 339 placements. **The device never owns a weight byte.**
- **The Metal buffer wrapper's lifetime is the graph's**, as on the CPU: created after the window
  fill, freed before the next block's read begins. Section 2.7's single-wrap variant is faster and
  **is not what ships** — see section 5.4.
- **An unfreed Metal host-pointer buffer aborts the process at exit.** Section 2.6 measured
  `exit 134`. On the CPU arm R5B's `lifetime.*_created == *_freed` assertion at every graph boundary
  is a leak check; **on this arm it is the thing standing between a missed free and a `SIGABRT` with
  no document**. `lifetime.graph_balance_failures` must be `0`, and section 4 keeps the assertion per
  graph rather than per run for that reason.

**Teardown order**, extending R5B's and asserted by the lifetime counters. Per graph: `gallocr` →
graph context → **device weight buffer** → weight context → reference buffer → reference context. At
the end of the run: input contexts → backend. Section 2.6 measured that freeing the buffer *after*
the backend also exits cleanly, so the order is not load-bearing — **but freeing at all is**, and the
design keeps R5B's order so that one teardown sequence serves both arms.

**Bounded memory** is R5B's table unchanged; the device adds no host allocation the arm controls.
Peak resident set is expected at R5B's 507,969,536 B for the shipped arm; section 2.8 measured the
self-reference arm at a substantially higher wall cost on Metal but not a higher window.

**`ggml_abort` is `abort()`**, and section 2.6 adds a second crash path that is *not* an abort: a
failed device wrap segfaults. Step 21a exists so that the one reachable route to it is closed.

### 3.11 Ledger dimensions

| Dimension | Answer |
| --- | --- |
| Public surface | `ggml-spike --model-forward-gpu`, section 3.3; `R5_MODEL_FORWARD_GPU` v1, section 3.8 |
| Inputs and defaults | R5B's four path operands, one token list, one width. **No defaults**, including no default device — the arm name is the device |
| Results, errors, precedence | Section 3.9, first applicable row wins, total across multi-invalid inputs |
| Ownership and allocation | Section 3.10; window, residual, logits, slot store Align-owned; the device borrows and never owns |
| Owner module | `src/gpu_forward.align` owns the arm; `src/model_forward.align` owns the schedule; `src/ggml_ffi.align` owns the boundary |
| Persisted identity | `kind` + `schema_version`, nominal. Deliberately a **new kind** — section 3.2 |
| Validation order | Section 3.9; R5B's thirty-four steps plus 20a, 20b, 21a; the device limit checked before the first wrap |
| Prerequisites | An alignpack v1 pack; an `R1_MODEL_IR` v2 document; for the qualification, ggml with a Metal backend, a GPU device, the model, and `d2e48620…` |
| Acceptance evidence | Section 5.1 owner, section 5.2 qualification, three oracles, the tolerance fixed in section 3.7 from section 2.3's measurement |
| Metrics | Section 5.3; **microbenchmark A only**, with a negative result recorded in section 1.5 |
| Text/wire boundary | UTF-8 JSON, R0's escaping rules, no float rendered anywhere |
| Inapplicable | Concurrency — the arm is single-threaded and section 2.10 records why benchmark C's is not expressible; network — none; schema migration — v1 is the first version; discrete VRAM — `N/A`, section 1.3 |

---

## 4. Closure matrix

Every cell names an implementation owner and the exact regression that covers it. `S` = reachable
with the stub shim (`make layer-forward-smoke`), `Q` = requires `make metal-forward-qualification`.

### 4.1 `src/ggml_ffi.align` and the two C files

| Cell | Owner | Regression |
| --- | --- | --- |
| Construction — `device_by_kind` | one `unsafe` block | `S` the stub returns "no GPU"; `Q` returns `MTL0` |
| Construction — `device_buft_max_size`, `device_props` | one `unsafe` block each | `S` the stub's fixed values; `Q` `9534832640` and `buffer_from_host_ptr` true |
| Success — status `0` | `r5_code_for` extended with the three new codes | `S` `gf-status-map`: every negative shim status maps to exactly one code, none unmapped |
| Failure — no GPU device | `device_by_kind` returns null | `S` `gf-no-gpu` → `R5C_GPU_UNAVAILABLE`, detail `stub` |
| Failure — device lacks host-ptr | `props.caps` false | `S` `ALIGN_GGML_FORCE_NO_HOST_PTR` → `R5C_NO_HOST_PTR` |
| Move in/out — no aggregate holds `raw` | named locals only | `S` the record-declaration scan over `src/` |
| Cleanup — per graph | `stage_teardown_graph`, total against null | `S` `gf-teardown-partial`: a failure at graph 14 still runs the full teardown and the counters balance |
| The two C files agree | the shared-contract marker block | `S` byte-identity assertion |
| No `malloc` | neither file allocates | `S` `grep -c malloc scripts/ggml_shim*.c` is `0` |
| Contraction off | `#pragma STDC FP_CONTRACT OFF` plus `-ffp-contract=off` | `S` `abi.fp_contract_off` asserted `true` on every document |

### 4.2 `src/model_forward.align` — the shared schedule

| Cell | Owner | Regression |
| --- | --- | --- |
| Formation — `DeviceKind` threaded, no stage reshaped | the stage signatures | `S` `arm-r5b-unchanged`: `--model-forward` still emits `R5_MODEL_FORWARD` and **every R5B golden is byte-unchanged** |
| Success — one schedule, two devices | `stage_read_block`, `carry_residual` | `S` the synthetic model's `schedule[]` identical between arms except the timing columns; `Q` 30 fills, 4,370,571,072 B on both |
| Success — window sizing is device-independent | `size_window` | `S` `window.bytes` equal across arms; `Q` `447086592` on both |
| Failure — R5B's codes still reachable from the GPU arm | `stage_*` | `S` section 4.5's inherited rows, run against both arms |
| Cleanup | section 3.10's order | `S` `lifetime.graph_balance_failures` 0 on both arms |

### 4.3 `src/gpu_forward.align` — the arm

| Cell | Owner | Regression |
| --- | --- | --- |
| Formation — arm selection | first operand, before path work | `S` `gf-arm-unknown-flag`; `gf-arity-seven` → `R5_ARITY` |
| Formation — device selection through the registry | `select_device` | `S` `gf-no-gpu`; `Q` `device.name == "MTL0"`, `type_id == 1` |
| Construction — device properties published | `read_device_props` | `S` the stub's golden block; `Q` `buffer_max_size == 9534832640`, `buffer_from_host_ptr` true, `window_fits` true |
| Construction — the device buffer limit, before the first wrap | `validate_device_window` | `S` `gf-device-limit` (a forced `max_size` of 1024) → `R5C_DEVICE_BUFFER_LIMIT`, detail `window[…]/max[1024]`; `Q` passes at 4.7% |
| Success — every placement external | the pointer-identity check R5B ships | `S` `verdict: "EXTERNAL"`; `Q` **339 placements, `pointer_identity_failures` 0** |
| Success — the transfer is measured | `window.wrap_count`, `wrap_ns` | `S` `wrap_count == 4` on the synthetic model; `Q` **30 wraps, 334–363 ms** |
| Failure — each new error code | `stage_*` | section 4.5 |
| Early exit — `-` document and `-` transcript | `run` | `S` `gf-doc-stdout-identical` |
| Return — exit mapping | R0's, verbatim | `S` `gf-exit-codes` |
| Cleanup — every device buffer freed | `stage_teardown_graph` | `S` `lifetime.graph_balance_failures` 0; `gf-force-buffer-leak` fails the per-graph assertion. **`Q` additionally proves the process exits 0**, which section 2.6 shows a leak would not |

### 4.4 The three oracles

| Cell | Owner | Regression |
| --- | --- | --- |
| Reference — bytes equal, per block | `compare_source` | `S` `gf-source-diverged` → `R5_SOURCE_DIVERGED`; `Q` all 339 members equal |
| Reference — nodes identical, per graph, **bit-exact on the device** | `stage_reference_graph` | `S` all nodes of all four synthetic graphs; `Q` **479 of 479 over 30 graphs** (section 2.8) |
| Transcript — grammar, coverage, element-count rule | `scan_transcript` | `S` `gf-transcript-garbage` → `R5_TRANSCRIPT`; `gf-transcript-missing-layer` → `R5_ORACLE_MISSING`; `Q` `layers_matched == 28` |
| Transcript — `kq-L` `ne0` against `KV_WIDTH` | step 30 | `S` `gf-transcript-kv-width` → `R5_ORACLE_SHAPE` |
| Transcript — elements deliberately not compared | step 31 | `S` and `Q` `oracle.verdict == "N/A_DEVICE"`, `elements_compared == 0`, asserted so a future silent re-enable is a diff |
| Logits — file shape | step 32 | `S` `gf-logits-short` → `R5_LOGITS_SHAPE`; `gf-logits-missing` → `R5_LOGITS_UNREADABLE` |
| Logits — the tolerance verdict | `compare_logits` | `S` `gf-logits-within`; `Q` **`WITHIN`, max 2,937 ten-thousandths, `argmax` 671 both, `top_k_agreement` 10, `elements_over_half` 0** |
| Logits — a real failure is not `WITHIN` | `compare_logits` | `S` `gf-logits-perturbed`: a reference blob shifted by 1.0 keeps the argmax and the whole top ten and is **`FAIL`**, so the bound alone cannot pass it |
| **Determinism is asserted** | `output.sha256` | `Q` `gf-determinism`: two consecutive runs, digests compared equal (section 2.4) |
| Per-layer recorded, never gated | `schedule[].l_out_max_*` | `S` fields present and `-1` hosted; `Q` populated, and **no case fails on them** — asserted by a case whose `l_out_max_abs_diff_ten_thousandths` exceeds 100,000 with `status: "ok"` |
| Tolerance not silently widened | `tolerance_ten_thousandths` | `S` and `Q` golden asserts `6000`; a change is a diff in two places |

### 4.5 Error-code-to-fixture map

R5B's thirty-two codes keep `r5b-model-prefill-forward.md` section 4.5's fixtures, re-pointed at the
GPU arm; the three new ones are:

| Code | Stub-reachable | Fixture |
| --- | --- | --- |
| `R5C_GPU_UNAVAILABLE` | yes | the default stub — the whole owner test's baseline |
| `R5C_NO_HOST_PTR` | yes | `ALIGN_GGML_FORCE_NO_HOST_PTR` |
| `R5C_DEVICE_BUFFER_LIMIT` | yes | `ALIGN_GGML_FORCE_MAX_BUFFER_SIZE=1024` |

**All three new codes are stub-reachable**, so the GPU arm's own failure surface is fully covered on
a host with no GPU. The three R5B codes that remain unreachable — `R5_WINDOW_BUDGET` (correction
C11), `R4_WINDOW_UNAVAILABLE`, and `R5_ABI` — are unchanged. The final matrix-to-diff pass maps every
cell above to its implementing function and its passing evidence, or to an explicit deferral in this
document, before review.

---

## 5. Fixtures, qualification, metrics, deferrals, risks, and candidate requests

### 5.1 Owner — `make layer-forward-smoke`, extended

Hosted, ggml-free, GPU-free, model-free, llama.cpp-free. **`layer-forward-smoke` is already a member
of `HOSTED_CHECK_TARGETS`, so R5C adds rows to an existing target and changes no aggregate
membership and no check topology**, and `metal-forward-qualification` joins no aggregate, exactly as
`model-forward-qualification` does not.

As in `r5b-model-prefill-forward.md` section 5.1, that is the whole of the claim and it is not an
exemption from the fresh-image scope: adding the `metal-forward-qualification` recipe and its
`.PHONY` entry edits the `Makefile`, which is an executable contract boundary, so
`scripts/verification_scope.py` is what selects the lane and **its verdict, not this paragraph, is
the evidence**.

The stub shim reports **no GPU device**, so every hosted case reaches `R5C_GPU_UNAVAILABLE` at step
20a and steps 1–19 stay fully covered. Three forced-failure environment variables —
`ALIGN_GGML_FORCE_NO_HOST_PTR`, `ALIGN_GGML_FORCE_MAX_BUFFER_SIZE`, and a stub GPU device that
otherwise behaves as R5B's engine — make the arm's *successful* path reachable hosted too, over
`r5b-model-prefill-forward.md` section 5.1's **synthetic two-layer, thirty-two-token-vocabulary
model** with its pure-Python second implementation. No new fixture generator is needed: the same
pack, geometry, transcript, and logits blob serve both arms. Correction C19 adds a fourth forced
build, `ALIGN_GGML_FORCE_INF_READBACK`, which is what makes a non-finite **computed** activation —
and therefore the arm's own non-finite logits — reachable on all three arms hosted.

Every fixture's expected document is a checked-in golden compared **byte for byte**, and R5C adds one
non-fixture assertion to R5B's five: **`arm-r5b-unchanged` asserts that every existing
`R5_MODEL_FORWARD` golden is byte-identical after the change**, which is the mechanical form of
sections 3.1 and 3.2's promise.

The smoke writes into a `mktemp -d` tree outside the work tree and removes it on every exit path,
with `r5a-dense-layer-forward.md` correction C22's shim-restoring trap.

**Budget.** `make layer-forward-smoke` measured 11.0 s when this plan was written; correction C11
records every measurement since, including the host drift that now puts it at the target's edge. The
acceptance target is **under 15 s**,
`r5b-model-prefill-forward.md` section 5.5's stated bound, and section 5.5 records the module split
that keeps it there.

### 5.2 Named qualification — `make metal-forward-qualification`, `scripts/run-metal-forward`

Opt-in, capable-only, in **neither** `HOSTED_CHECK_TARGETS` nor `CAPABLE_ONLY_CHECK_TARGETS`. It
prints one explicit `N/A` line naming the missing input and exits `0` when any of

```text
ALIGN_LLM_GGML_INCLUDE            ggml headers
ALIGN_LLM_GGML_LIB                ggml libraries
ALIGN_LLM_GGML_BACKEND_DIR        the only directory the backend plugins are dlopened from
ALIGN_LLM_GGUF_MODEL              the Qwen2 GGUF
ALIGN_LLM_LLAMA_DEBUG             path to llama-debug
ALIGN_LLM_METAL_FORWARD_TMPDIR    where the pack is written; defaults to TMPDIR
```

is unset, or **the declared backend directory holds no Metal plugin**, or the model or instrument is
absent, or free space under the scratch root is below the pack's size plus 1 GiB. **Hosted CI is
Linux, where no Metal plugin is built, so this target is `N/A` there** — which is the intended
behaviour and not a skip: the `N/A` line names the missing plugin. Once the directory does hold one,
the registry is scoped to it (correction C17) and a run that then finds no device of type GPU is a
**`FAIL`**, not an `N/A`.

Otherwise it builds the real shim, packs the model, emits the geometry, captures `llama-debug`'s
logits with `r5b-model-prefill-forward.md` section 2.2's **exact** contractual flag set, and runs the
arm twice:

```text
$ FLAGS="-p \"def add(a, b):\" -n 1 -t 4 -ngl 0 -fa off -ctk f32 -ctv f32 -nr -c 512"
$ $ALIGN_LLM_LLAMA_DEBUG -m $MODEL $FLAGS --save-logits --logits-output-dir $LG
$ ggml-spike --model-forward-gpu $PACK $GEOM 750,912,2877,11,293,1648 \
      $DOC1 $MODEL $TRANSCRIPT 256 $LG/llamacpp-qwen2.5-coder-7b-instruct-q4_k_m.bin
$ ggml-spike --model-forward-gpu $PACK $GEOM 750,912,2877,11,293,1648 \
      $DOC2 $MODEL $TRANSCRIPT 256 $LG/llamacpp-qwen2.5-coder-7b-instruct-q4_k_m.bin
```

It first asserts the reference file's `sha256` is
`d2e48620ae3e31e2066a6172aa32c19c974d996d232ab91b118335e3d245bf74` **before** running the arm, so an
instrument change is reported as an instrument change and not as a failing oracle. Then, against
section 2's recorded values:

| Assertion | Expected |
| --- | --- |
| `status`, `verdict` | `ok`, `EXTERNAL` |
| `device.name`, `type_id`, `buffer_from_host_ptr`, `window_fits` | `MTL0`, `1`, `true`, `true` |
| `device.buffer_max_size`, `buffer_alignment` | `9534832640`, `32` |
| `window.bytes`, `reuse_count`, `pointer_identity_failures`, `member_placements` | `447086592`, `30`, `0`, `339` |
| `window.wrap_count` | `30` |
| `graph.graph_count`, `node_count_total`, `reconciliation_node_count` | `30`, `874`, `958` |
| `output.element_count`, `argmax` | `152064`, `671` |
| `reference.verdict`, `graphs_compared`, `nodes_compared`, `nodes_identical` | `IDENTICAL`, `30`, `479`, `479` |
| `oracle.verdict`, `layers_matched`, `elements_compared` | `N/A_DEVICE`, `28`, `0` |
| `oracle_logits.verdict`, `max_abs_diff_ten_thousandths`, `tolerance_ten_thousandths` | `WITHIN`, `<= 6000` with **2,937** recorded, `6000` |
| `oracle_logits.argmax_primary` == `argmax_reference`, `top_k_agreement`, `elements_over_half` | `671`, `10`, `0` |
| **`DOC1.output.sha256` == `DOC2.output.sha256`** | equal — the determinism assertion (section 2.4) |
| `lifetime.graph_balance_failures`, `released_before_owner_scope_end` | `0`, `true` |
| **process exit code of both runs** | `0` — section 2.6 measured that a leaked device buffer gives `134` |
| `abi.tensor_alignment`, `fp_contract_off` | `32`, `true` |

Then the paired benchmark of section 5.3, then the ggml-only fixtures of section 4.5, then it removes
the pack, the instrument output, and the tree — on every exit path, including a signal.

**`output.sha256` is asserted equal between the two runs but is not a checked-in golden**, for
`r5b-model-prefill-forward.md` section 5.2's reason: `b6e473e8…` is a property of one ggml version on
one GPU family, and pinning it would fail on any Metal kernel change with a message that reads like
corruption. Determinism is the contract; the specific digest is a recording.

**Budget.** The shipped arm runs in ~2.5 s and the self-reference arm in ~20.8 s (section 2.8), so
the target is budgeted at **under 60 s** end to end including packing and the instrument.

### 5.3 Metrics — microbenchmark A

Paired, same host, same session, alternating runs, five samples at the reconciliation width and three
at the runtime width. **The pairing is the method**: this host's page cache made `pread` 1.42 s
against R5B's warm 533 ms, so only same-session pairs are comparable, and no cross-document timing
claim is made.

| Metric | Definition | CPU arm | GPU arm |
| --- | --- | --- | --- |
| microbenchmark **A**, transfer | window wraps per prefill | 30 wraps, **0.075 ms** | 30 wraps, **354.8 ms** (334.3–362.7) |
| — per wrap | 447,086,592 B, zero bytes copied | 0.003 ms | **11.8 ms** (11.1–12.1) |
| — scaling | measured 1 MiB → 1 GiB | flat 0.0002–0.0004 ms | **linear, ~26 µs/MB** |
| microbenchmark **A**, GPU compute | whole model, width 256 | **500.7 ms** (465.3–537.4) | **523.3 ms** (518.4–531.6) |
| — at the runtime width | whole model, width 6 | **466.8 ms** | **528.5 ms** |
| per-layer compute, layers 0–26 | median | 19.52 ms | **18.85 ms** |
| layer 27 compute | narrowed, `T` = 1 | **6.53 ms** | 10.31 ms |
| head compute | `MUL_MAT` against 447 MB Q6_K | 26.57 ms | **12.84 ms** |
| wall | median of five | **2,074.3 ms** | **2,491.3 ms** |
| **end-to-end ratio** | GPU ÷ CPU wall | — | **1.20× slower** |
| microbenchmark **B** | CPU compute | R5B's, unchanged | `N/A` |
| microbenchmark **C** | async prefetch + GPU compute | `N/A` | **`N/A` — blocked, section 5.5** |
| discrete VRAM transfer | DRAM → VRAM copy | `N/A` | **`N/A` — no such device here** |

These are secondary metrics and **R5C makes no claim on time to a passing patch** (section 1.5). Their
purpose is three numbers a residency policy will need:

1. **The transfer tax scales with the window, not the work.** 26 µs/MB, paid per wrap. A policy that
   wraps less, or wraps smaller windows, wins 220–280 ms per prefill before it improves a single
   kernel.
2. **The compute win scales with the work.** The GPU is 2.07× faster on the one graph that is large
   and slower on the one that is tiny. At `T` = 6 there is not enough work per layer to pay for the
   dispatch.
3. **Neither is the bottleneck.** `pread` is 1,423.8 ms of a 2,074.3 ms CPU prefill. **The device
   choice moves 377 ms of a run whose dominant cost is still reading the file**, which is
   `r5b-model-prefill-forward.md` section 5.3's conclusion confirmed from the other side.

### 5.4 Deferred surfaces

- **Microbenchmark C, async prefetch.** Blocked on section 5.5's Request 41, with the exact compiler
  refusal recorded in section 2.10. Not workaround-able within `CLAUDE.md`'s rules.
- **Wrapping the window once instead of thirty times.** Measured in section 2.7: **75.6 ms instead of
  354.8 ms, byte-identical output, 279 ms of wrap**. Deferred deliberately, because hoisting the wrap
  removes the per-graph buffer free that R5B's window-reuse invariant asserts, and section 2.6 shows
  that on Metal an unfreed buffer aborts the process. The capability that ships it must also
  re-establish the invariant it weakens — plausibly by asserting tensor-context balance per graph and
  buffer balance per run. **R6, with 279 ms as the recorded target.**
- **A window per block class.** `r5b-model-prefill-forward.md` section 5.4 deferred this as a
  *memory* question against a 507,969,536 B peak. Section 2.7 gives it a second, larger motive: a
  149,112,832 B layer window would cut each layer's wrap from 11.8 ms to ~3.9 ms, about **220 ms** per
  prefill. Still R6, now with two measured reasons instead of one.
- **Discrete VRAM.** `N/A` and unanswerable here, unchanged from `r4-5-external-buffer.md` section
  5.4. R5's DRAM → VRAM tier is a **transfer** design on such a device, not a compute-in-place one,
  and section 1.3 says so rather than generalizing from unified memory.
- **A per-layer numeric gate on the GPU arm.** Section 2.5 measured why no absolute or relative bound
  is meaningful over a residual stream with a massive-activation channel. If a later capability needs
  per-layer acceptance, the instrument is a **per-channel normalized** comparison, which is a design
  decision with its own evidence and not a threshold to be picked here.
- **The transcript oracle's element comparison on a GPU arm.** Same cause, same deferral; section 3.7
  publishes `N/A_DEVICE` rather than a bound that cannot fail.
- **The KV cache, decode, lifting `MAX_PREFILL_TOKENS`, a residency policy, geometry in the
  container, MoE, a second architecture, and the `align-runtime` rename.** All inherited unchanged
  from `r5b-model-prefill-forward.md` section 5.4.
- **A read-only pack open.** R5C is the **sixth** client for Request 21.

### 5.5 Candidate Align capability requests

**One new request, and it is not the one this document expected to file.** Section 2.10 set out to
record "impure/I-O work inside `task_group`" and **measured that it already works** — `spawn` accepts
`fs` I/O and `extern "C"` FFI, checks clean, and runs. The guide's purity requirement is `par_map`'s
alone, exactly as `docs/language-spec.md` states it. A request filed on the plan's guess would have
been wrong.

- **Request 41 — non-`Copy` capture in `spawn` closures.** `PROPOSED`. **Blocking: yes**, for
  microbenchmark C only.

  **Evidence, at pin `4b515f8d`:**

  ```text
  tg2.align:14:20: error: a lambda cannot capture the owned value 'w' yet
                          (capture supports copy values like int/float/bool/char)
  tg2.align:14:33: error: the exclusive borrowed argument to 'fill' must be rooted in mutable storage
  tg3.align:1:12:  error: Result ok payload cannot be `buffer` — an owned I/O handle/buffer is bound
                          to one local, not collected into an array/slice/box
  ```

  `docs/guide/10-closures-and-parallelism.md` documents value capture and the `Pure` rule for
  `par_map`; `docs/language-spec.md` (parallelism section) confirms `par_map` alone requires `Pure`,
  and states that task results are Copy values with "Owned results remain future work". So both
  halves of the prefetch shape are closed: the task cannot **capture** the window and cannot
  **return** a filled buffer.

  **Proposed surface**, Align-consistent and deliberately minimal: allow a `spawn` closure to capture
  an **exclusive `borrow mut`** of caller-owned storage that the enclosing `task_group` provably
  outlives. The lifetime argument is already the language's — *"Leaving a `task_group`, including by
  early return or error propagation, joins its tasks before captured frame-owned locals or enclosing-
  arena storage are released"* — and exclusivity is already what `borrow mut` proves. Disjointness
  between two spawned tasks is the open question and the natural bound is **one exclusive capture per
  spawn**, rejecting two spawns that capture the same root.

  **Acceptance criteria:** a `task_group` in which one spawned task fills a caller-owned `buffer` via
  `f.pread` while the main thread computes, checking and running at the pin; two spawns capturing the
  same root rejected at check time; and `align-llm` verification by a
  `--model-forward-gpu --prefetch` arm that overlaps layer `L+1`'s read with layer `L`'s compute and
  publishes microbenchmark C against section 5.3's 1,423.8 ms of `pread`.

  **Blocked gate or slice:** R5 microbenchmark C. **Independent work that may continue:** all of R5C
  — A is discharged without it. **Resume condition:** the capture rule ships and `.align-revision`
  advances past it.

R5C is additionally new client evidence for five existing requests, none of them newly blocking:

- **Request 37 — per-function check time superlinear in body length.** R5C's most direct
  consequence is again a **module boundary chosen before any code is written**:
  `src/model_forward.align` is already large, so section 3.10 puts the GPU arm in a new
  `src/gpu_forward.align`. The acceptance target is `check-per-unit src/gpu_forward.align` under
  **10 s** and `make layer-forward-smoke` under **15 s**; if either is exceeded the arm splits along
  the device/oracle boundary rather than absorbing the cost.
- **Request 34 — `Result` ok payloads beyond scalars.** Now also the mechanism behind Request 41's
  second half: a task cannot return a `buffer`.
- **Request 33 — aligned heap allocation.** Unchanged in kind; the window is still a `buffer(n)`
  over-reserved by `MAX_TENSOR_ALIGNMENT`, and section 2.6 shows the device would have accepted any
  alignment while the CPU would not.
- **Request 32 — FFI by-value structs and `bool` on AArch64.** Three more wrapped call sites;
  `device_props` returns its `bool` capabilities through `i32` for this reason.
- **Request 21 — a read-only open.** The sixth client.

If the implementation refutes this section — as R5A's and R5B's both did — the correction belongs in
a section 6 of this document, not in a quiet edit here.

### 5.6 Risks

| Risk | Mitigation | Residual |
| --- | --- | --- |
| **A failed device wrap segfaults instead of returning null** (section 2.6, `exit 139`) | Step 21a validates `window_bytes` against `ggml_backend_buft_get_max_size` before the first wrap, and `gf-device-limit` forces the check hosted | A wrap that fails for a reason *other* than length — device memory pressure from another process — still crashes with no document. The check closes the one input-reachable route, and the risk is named rather than claimed away |
| **An unfreed device buffer aborts the process at exit** (section 2.6, `exit 134`) | `lifetime.graph_balance_failures` asserted `0` per graph, and the qualification asserts **exit code 0**, which is the only check that can see a leak the counters missed | A leak freed before the next assertion point would pass, exactly as `r5b-model-prefill-forward.md` section 5.6 records for the CPU arm — but here it would then crash at exit, so the failure is loud rather than silent |
| **The tolerance is 6,000 ten-thousandths, which is large** | It is not the whole acceptance contract: `argmax`, the full top ten in order, `elements_over_half == 0`, two-run digest equality, and a bit-exact self-reference oracle all gate alongside it. `gf-logits-perturbed` proves a 1.0 shift fails while keeping the argmax | A defect that moves every logit by under 0.6, preserves the top ten, is bit-reproducible across runs, and survives byte-identity against a ggml-owned copy of the same weights is not constructible: the reference arm shares every node with the tolerant one |
| **Metal could become nondeterministic** in a later ggml or macOS release | Section 2.4 measured five byte-identical runs, and section 3.7 turns that into a two-run assertion rather than into slack | A change that makes the device nondeterministic fails `gf-determinism` loudly. That is a **correct** failure requiring a design decision — whether to widen the bound and drop the assertion — and not a bug to be patched by widening it quietly |
| **The per-layer digests could be mistaken for a gate** | Section 3.7 and section 3.8 mark them recorded-only, and section 4.4 asserts a case whose per-layer difference exceeds 100,000 ten-thousandths still reports `status: "ok"` | A reader who gates on them downstream gets a meaningless threshold. The document field names and section 2.5's measurement are the defence |
| **The GPU arm is slower and could be read as a failure** | Section 1.5 records the cost ceiling as negative **before** implementation, and section 5.3 publishes the decomposition that explains it | Someone quotes "Metal is slower" as a fact about Metal rather than about a six-token prefill of a 4.68 GB model on an M1. Section 5.3's per-graph table exists to make that misquote hard |
| **The qualification is `N/A` on hosted CI** and could rot unnoticed | The `N/A` line names the device as the missing input; the arm's own failure surface — all three new codes — is **fully stub-reachable** hosted, and `arm-r5b-unchanged` runs hosted too | Only the numeric agreement and the timings need a Metal host. That is the same shape as `model-forward-qualification` and is stated rather than implied |
| **Timings are page-cache dependent**, and this session's `pread` was 2.7× R5B's | Every figure in section 5.3 is a **paired, alternating, same-session** measurement, and no cross-document timing claim is made | Absolute wall figures are not comparable to `r5b-model-prefill-forward.md` section 7.6's. The ratio is what R5C claims, and pairing is what makes it claimable |
| **R5B's contract could drift** while R5C shares its schedule | `arm-r5b-unchanged` asserts every existing `R5_MODEL_FORWARD` golden is byte-identical, and sections 3.1 and 3.2 keep the arm, the kind, and the arity set separate | A change to the shared schedule still touches both arms by design. The golden assertion is what makes that visible in one line of the diff |

---

## 6. Corrections the implementation forced

Section 5.5's closing rule applied: every item below is a place where the design of sections 1 to 5
was refuted or under-specified by writing the code, and each records the measurement or the compiler
diagnostic that forced it rather than being edited quietly into the sections above.

### C1 — the wrappers are four, not three

Section 1.2 names three new one-call wrappers: `device_by_kind`, `device_buft_max_size`, and
`device_props`. Those three cover every **numeric** field of section 3.8's `device` object and none
of its two textual ones. `ggml_backend_dev_name` and `ggml_backend_dev_description` return a
`const char *`, and a `str` cannot be formed over foreign memory at this pin, so each name has to be
copied into an Align-owned byte range and decoded there — the shape `align_ggml_backend_name`
already has. A fourth symbol, `align_ggml_device_text(device, which, out, cap)`, carries both behind
one selector rather than adding two.

**Shipped:** four symbols in `src/ggml_ffi.align` and in both C files, and a `device_flag` helper
above `device_props` so a capability flag is read as `== 1` in one place. Anything that is not
exactly `1` — a zero, a negative shim status, an unknown field — is `false`, which keeps step 20b
fail-closed against an ABI drift instead of reading a status as a truth value.

### C2 — `SIZE_MAX` is not an `i64`

`ggml_backend_buft_get_max_size` reports `SIZE_MAX` — `18446744073709551615` — for the **CPU**
buffer type on this host, measured. Returned unclamped it is a negative `int64_t`, and step 21a's
`window_bytes <= max_size` would then refuse every window on the arm that has no limit at all. Both
C files clamp to `i64`'s maximum inside the shared contract region, so a device that declares no
limit reads as the largest limit rather than as a negative one. Metal's own `9534832640` needs no
clamp and is unaffected.

### C3 — the forced-failure inputs are build flavours, not environment variables

Section 5.1 calls `ALIGN_GGML_FORCE_NO_HOST_PTR` and `ALIGN_GGML_FORCE_MAX_BUFFER_SIZE`
"forced-failure environment variables". Every forced failure this repository ships is a
compile-time `-D` macro selected by a named `scripts/build-ggml-shim` flavour, for
`r4-5-external-buffer.md` section 4.6's reason: a shim whose behaviour changes with the environment
is a shim whose golden documents are not reproducible. R5C follows that discipline unchanged and
adds five flavours — `engine+gpu`, `engine+gpu+no-host-ptr`, `engine+gpu+max-buffer`,
`engine+gpu+compute` for the stub, and `max-buffer` and `no-host-ptr` for the real shim, so the
qualification reaches both new device conditions against the **real** Metal device as well.

### C4 — `schedule[].l_out_max_*` cannot be populated by this arm

Section 3.8 says the three per-layer difference fields are "populated only when a CPU reference
document is supplied to the qualification". **Section 3.3's operand grammar defines no operand that
could carry one**, and sections 3.1 and 3.2 hold that grammar fixed at R5B's arity set on purpose —
a tenth operand is exactly the change section 3.1 rejected. The fields therefore exist in the
document, are always `-1`, and the comparison they describe is made by `scripts/run-metal-forward`
between the two arms' own `schedule[]` digests and `l_out_f32_sum_millionths`, printed and never
gated, which is what section 2.5 concluded it must be in either place.

Measured on the real model: **all twenty-eight layers' `l_out` digests differ** between the two arms
and every one of them is a successful run, which is section 2.5's finding restated as a shipped
observation rather than a threshold.

### C5 — a `borrow mut` column set cannot cross a module boundary and come back

The plan's module split — `src/gpu_forward.align` calling `src/model_forward.align`'s `execute` —
does not compile as written, and the diagnostic is not about the device:

```text
src/gpu_forward.align:556:36: error: use of invalidated borrow 'schedule': its source 'tokens' was
                                    moved or reassigned (or its storage was reallocated)
src/gpu_forward.align:556:20: error: value snapshot was invalidated before the enclosing operation:
                                    owner 'tokens' was moved, reassigned, or reallocated by a later
                                    eager operand
```

`execute` reports its four column sets through `borrow mut` out-parameters. A caller **in another
module** cannot read them after the call: the checker merges the four owners into one region and
invalidates all of them, naming `tokens` as the source of `schedule`'s invalidation. The identical
sequence inside `src/model_forward.align` checks *and builds*, which is why R5B never met it.

Returning them inside a record instead is refused for a second, different reason —
`cannot return a view that borrows local storage` — and only for the four column sets: a `Bundle`
carrying `Outcome` alone builds. The columns are assembled from builders local to `stage_geometry`
and `schedule_model`, so the checker treats the caller's own local as a view over those. Assembling
the record field by field is refused by a third:
`field replacement of model_forward$Outcome is not supported yet (owned field replacement currently
supports only string and Option<string> leaves)`.

**Shipped:** `model_forward.render_parts` renders the four column sets where they are produced and
returns them as `string`s beside the `Outcome` — the one shape all three refusals allow. The GPU
document's three extra per-layer field names travel the other way, as a `schedule_suffix` string, so
the `R5_MODEL_FORWARD_GPU` field list stays in the module that owns that document and section 3.10's
ownership table holds. `--model-forward` keeps calling `execute` directly and its bytes are
unchanged.

**`alignc check` accepts all three forms that `alignc build` rejects.** Section 7 records that as
the Align-side finding; the application-side answer above consumes no hypothetical surface.

### C6 — step 20 keeps R5B's code on both arms

Section 4.5 gives `R5C_GPU_UNAVAILABLE` the detail `stub`, and section 5.1 says the default stub
reaches it at step 20a. It cannot: section 3.9 step 20 is `align_ggml_available()` and is declared
**unchanged**, so a host with no ggml at all stops there, before any device is selected. Renaming
that code for the GPU arm would also name the wrong cause — a code called `GPU_UNAVAILABLE` firing
on a host that has no ggml is a worse diagnostic than `R5_GGML_UNAVAILABLE`.

**Shipped:** step 20 is `R5_GGML_UNAVAILABLE` with detail `stub` on both arms, and step 20a is
`R5C_GPU_UNAVAILABLE` with detail `device`, reached by the `engine` stub build — which is available
and has no GPU device, which is exactly the condition the code names. All three new codes remain
fully stub-reachable and the owner's coverage of steps 1 to 19 is unchanged.

### C7 — the window is wrapped fifty-nine times, not thirty

Section 5.2 asserts `window.wrap_count == 30`, from section 2.7's `WRAP calls=30`. That probe
harness ran **one** pass. The shipped arm runs the runtime pass for every layer and the head **and**
the reconciliation pass for each of them whenever `KV_WIDTH > token_count`, which is the width the
qualification uses. The window is filled thirty times — `reuse_count` is 30, and section 3.5's
sizing is untouched — and handed to the device `1 + 2 * (n_layer + 1)` = **59** times.

The measured consequence is that microbenchmark A's transfer at the reconciliation width is
**732.3 ms over 59 wraps** at the median of three pairs, 12.4 ms per 447 MB wrap, rather than
section 2.7's 354.8 ms over 30. The per-wrap figure is the one that generalizes and it agrees with
section 2.7's independently measured 11.8 ms; section 5.3's totals are single-pass figures and
section 7.2 restates them for the shipped arm.

### C8 — the qualification needs the transcript instrument

Section 5.2's environment list omits `ALIGN_LLM_LLAMA_EVAL_CALLBACK` while its own assertion table
requires `oracle.layers_matched == 28`, which is only reachable with a transcript.
`scripts/run-metal-forward` declares it as a required input and prints an explicit `N/A` line naming
it when it is absent, exactly as the other five.

The same script also answers "is there a GPU device here" **before** packing four and a half
gigabytes, by running the arm over the synthetic two-layer fixture the owner already uses and
reading `error_code`. The registry answers the question rather than the host's name.

### C9 — `oracle.nodes_matched` is zero on a device arm

Section 3.7 disables the transcript oracle's element comparison, and the per-node match counter is
incremented inside that comparison. On the GPU arm `oracle.nodes_expected` is 479 and
`oracle.nodes_matched` is `0` while `layers_matched` is 28 and every structural rule has run and
passed in the pre-schedule scan. The field is left as it is rather than being made to mean something
else on one arm: `elements_compared: 0` and `verdict: "N/A_DEVICE"` already say that nothing was
compared, and a matched-node count synthesized from the scan would be a number that looks like the
CPU arm's and is not.

### C10 — the naming the plan settled on

Section 5.2 names the target `metal-forward-qualification` and the runner `scripts/run-metal-forward`
while section 1.2 and section 3 name everything else after the device-generic `gpu`. Both are
shipped as section 5.2 wrote them, and the Align module, the CLI arm, the document kind, the error
prefix, and the golden corpus keep the generic name: the *capability* is device-generic and the
*qualification* is the one part that genuinely requires Metal.

### C11 — the owner's budget, measured rather than asserted

Section 5.1 records `make layer-forward-smoke` at **11.0 s** and sets the acceptance target at
**under 15 s**; section 5.5 adds `check-per-unit src/gpu_forward.align` under **10 s**. Both were
measured, paired and alternating on the host of section 2.1, because a wall-clock target compared
against a number from a different session is not a measurement.

| Quantity | Result |
| --- | --- |
| `check` of `src/gpu_forward.align`'s own unit | **1.3–2.1 s** — the whole-graph check minus `src/model_forward.align`'s, paired. Well inside the 10 s target, which is what the new module bought (`docs/align-requests.md` Request 37) |
| `make layer-forward-smoke`, **unchanged runner**, this host | **12.98 s** median (12.54–14.93) |
| `make layer-forward-smoke`, with R5C's block | **15.70 s** median (14.50–16.12) |
| **R5C's own cost** | **+2.2 s, +17%** |

**The target is exceeded on this host and met against the baseline the target was set from.** The
plan's session ran the unchanged runner in 11.0 s and this one runs it in 13.0 s, so 2.0 s of the
overrun is the host and 2.2 s is this capability; 11.0 + 2.2 = 13.2 s is inside 15 s. Both numbers
are stated rather than one of them chosen.

Section 5.5's stated remedy — "the arm splits along the device/oracle boundary" — does **not**
apply, and saying so is the point of recording this: that remedy reduces *checker* cost, which is
already inside its target by a factor of five. The owner's cost is process launches, and it was
reduced where the reduction cost no coverage:

- the GPU arm's default-stub list is **five rows, not twenty-seven**. Steps 1 to 19 are the same
  `model_forward.execute` on both arms, and the `--model-forward` block already drives every one of
  those rules through it; one row per operand class proves the new arm reaches that path, which is
  the only thing those rows can add.
- `gf-gpu-type` was dropped as a duplicate of `gf-gpu-alignment` for section 4.2's "R5B's codes are
  still reachable from the GPU arm" cell, which seven other rows also cover.
- the determinism check reuses `gf-gpu-logits`'s own document as the first of its three runs.

What was **not** reduced: every closure cell of section 4 still has a case, all three `R5C_*` codes
are still stub-reachable, and `arm-r5b-unchanged` still runs hosted.

**Re-measured after the review repair**, which adds six cases across the two arms for correction
C12: three consecutive runs at **16.37 / 13.46 / 13.50 s**, median **13.50 s**, inside the 15 s
target. The first of the three rebuilt the shim and the executable and is the outlier.

**Re-measured again after the final-review repair**, which adds three cases and three shim builds
for correction C19. Paired and alternating in one session on this host, five runs each, the same
method as the table above:

| Quantity | Result |
| --- | --- |
| `make layer-forward-smoke` at `ca541bf` | **14.03 s** median (13.77–14.64) |
| the same, with C19's three cases | **15.08 s** median (14.71–17.50) |
| **C19's own cost** | **+1.05 s, +7%** — three shim rebuilds and three runs |

**The target is exceeded on this host by 0.08 s and met against the baseline the target was set
from**, which is the same split this correction already recorded and not a second excuse: the
plan's session ran the unchanged runner in 11.0 s and this one runs it in 14.0 s, so 3.0 s of the
overrun is the host and 1.05 s is C19; 11.0 + 1.05 = 12.05 s is inside 15 s. Both numbers are
stated rather than one of them chosen. The three cases are not tradeable for the 0.08 s: each is the
only reachable evidence that its module's oracle refuses a value that is not a number, and the
alternative to a forced build is no case at all.

### C12 — a logits element with no ten-thousandth, and the abort it caused

Section 3.7 defines both logits comparisons as integer comparisons in ten-thousandths and section
3.8 states that `nonfinite_count` "is reported and is never a failure condition". Neither sentence
says what the *comparison* does with an element that has no ten-thousandth, and the implementation's
answer was to wrap:

```text
difference := ((primary.f32_le(at * 4) as f64) * 10000.0).round() as i64
            - ((view.f32_le(at * 4) as f64) * 10000.0).round() as i64
```

`as i64` **saturates**, so a reference element of `-inf` — or any finite `|v|` above roughly
9.2e14 — becomes `i64`'s minimum or maximum. The arithmetic then has exactly one abort: when the
*primary* element at that index rounds to `0` (against a saturated minimum) or to `-1` (against a
saturated maximum), `primary - reference` wraps to `i64`'s minimum, `0 - difference` wraps that to
itself, and `histogram[bucket]` is indexed with it. Measured at `5663d8f`, on **both** arms, since
`compare_logits` is shared:

```text
$ ggml-spike --model-forward     PACK GEOM 1,25,5 - SOURCE - 3 model-logits-neg-inf.bin
$ ggml-spike --model-forward-gpu PACK GEOM 1,25,5 - SOURCE - 3 model-logits-neg-inf.bin
align: panic: index out of bounds: the len is 65537 but the index is -9223372036854775808
exit 134, 0 bytes of document
```

The other two failures need no such coincidence and were measured on the same build: a `+3.4e38`
reference published `max_abs_diff_ten_thousandths` **9,223,372,036,854,775,706** with a **negative**
`mean_abs_diff_ten_thousandths` of **−46** from the overflowed total, and a NaN reference — whose
`as i64` is `0`, not a saturation — published a difference of **5,193 ten-thousandths, inside this
arm's 6,000 bound**, held off `WITHIN` only by the top-ten guard. On a vector where the NaN did not
disturb the top ten, that is a **false pass**.

**Shipped**, and it is two rules rather than one because the two inputs are not the same kind of
thing:

1. **The reference is an input.** A reference blob carrying an infinity or a NaN is malformed, and
   it is refused before any difference is taken — new error code **`R5_LOGITS_NONFINITE`**, detail
   `elements[<n>]`, raised at step 32 beside `R5_LOGITS_SHAPE`'s length rule and reachable from
   **both** arms. R5B's code count is therefore **thirty-three**, not thirty-two. R5B took this
   half of the repair into its own head before it merged as PR #128 and R5C rebased onto it, as
   `r5b-model-prefill-forward.md` section 6, **correction C23** — the reference rule,
   `logit_ten_thousandths`, `LOGIT_SCALE_LIMIT_TEN_THOUSANDTHS`, `R5_LOGITS_NONFINITE`, and the
   `mf-logits-nonfinite` / `-nan` / `-huge` fixtures and goldens. That ledger owns the CPU arm's
   record and the code comments in `src/model_forward.align` cite it; what remains R5C's here is the
   device arm — the `gf-*` cases, `add_saturating`, and the histogram overflow bucket R5B has no
   running total or histogram to need.
2. **The arm's own logits are not refused for the same condition**, because section 3.8 promises
   they are not: `output.nonfinite_count` reports them. A non-finite primary — and any element of
   either vector whose magnitude exceeds `LOGIT_SCALE_LIMIT_TEN_THOUSANDTHS`, 10^15 — is instead
   converted through one range-checked helper that returns "unrepresentable", takes the scale limit
   as its magnitude, and lands in the histogram's overflow bucket. That magnitude is above every
   tolerance this repository declares, so an unrepresentable element is a **`FAIL`** and can never
   wrap into a pass. `total` accumulates saturatingly for the same reason.

A NaN is handled by the same helper and not by the conversion: `NaN as i64` is `0`, which would have
compared *within* any bound. The exponent test is `digest_region`'s, so one definition of
"non-finite" serves the digest and the oracle.

**Cases**, three fixtures each on both arms. `mf-logits-nonfinite` / `gf-logits-nonfinite` is the
aborting pair above, verbatim — the token list and the `-inf`'s element index are chosen so the
shipped fixture **is** the crashing input rather than a neighbour of it, swept out of the
generator's own second implementation, which agrees with the engine to zero ten-thousandths. It and
`mf-logits-nan` / `gf-logits-nan` now reach `R5_LOGITS_NONFINITE` with detail `elements[1]`, a
document, and no verdict. `mf-logits-huge` / `gf-logits-huge` — one `+3.4e38` and one `-3.4e38`,
both finite, so neither is an input error — is `status: "ok"` with `verdict: "FAIL"`,
`max_abs_diff_ten_thousandths` above the bound, `elements_over_half` 2, and a **non-negative** mean.
The negative element is the operand that made the subtraction wrap, which is why the fixture carries
both signs.

Two branches of this repair are **not** covered by those three fixtures, and both are named here
rather than left to be rediscovered:

- the **`primary`** side of the same rule — the arm's own logits carrying a non-finite element,
  which section 3.8 promises is reported and never refused. No operand can produce it, because the
  vector is computed. Correction C19's forced build now does, and `mf-force-inf-readback` and
  `gf-force-inf-readback` are its cases;
- `add_saturating`'s **saturating** branch. It needs a running total above
  `i64::MAX - 10^15`, which takes more than 9,223 elements at the scale limit; the synthetic model's
  `n_vocab` is 32 and the qualification's 152,064 elements are all in range, so no fixture in this
  repository reaches it. It is an **untested guard**, kept because the alternative on a real
  152,064-element vector of unrepresentable elements is a negative published mean — the exact defect
  C12 exists to close — and it is one comparison on a path that already costs a division.

### C13 — `IDENTICAL` at the runtime width belongs to the device arm alone

Section 3.3 keeps the `IDENTICAL` verdict reachable on `--model-forward-gpu` "because removing it
would make a surprising-but-correct result unrepresentable". The implementation reached it through
an early return that ran on **both** arms, so a byte-identical reference at the *runtime* width
would have made `--model-forward` publish `IDENTICAL` — a verdict
`r5b-model-prefill-forward.md` section 3.7's two-row table does not define at that width, where its
only successful verdict is `WITHIN`. That is precisely the conditional weakening of R5B's contract
that sections 3.1 and 3.2 exist to prevent, arrived at from the other direction.

**Shipped:** the early return is gated on `!logits_strict_reconciliation`, the same flag that
already separates the two arms' reconciliation rules, so `IDENTICAL` outside byte-identity at the
matched width is the device arm's verdict and nobody else's.

**Case:** byte-identity is not constructible hosted, for correction C9's reason in
`r5b-model-prefill-forward.md` — a pure-Python second implementation does not share the engine's
`expf`, `sinf`, and `cosf` — and the qualification's runtime-width reference is not byte-identical
either (2,739 ten-thousandths). `mf-engine-runtime-width` therefore asserts the near-miss it *can*
construct: `verdict: "WITHIN"` with `max_abs_diff_ten_thousandths` 0 and `byte_identical` **false**,
so a fixture that ever became byte-identical is a diff here rather than a silently changed verdict.

### C14 — `buffer_alignment` and `window_fits` are tri-state

Section 3.8 declares `buffer_alignment` an integer and `window_fits` a boolean, and section 3.9
reads the first at step 21 and computes the second at step 21a. An error document from step 20b —
`R5C_NO_HOST_PTR`, which returns before either — published `0` and `false`, which read as a device
declaring no alignment and a window that does not fit. Neither was measured.

**Shipped:** both are `-1` until the step that evaluates them runs, exactly as `device.type_id`
already is, and `window_fits` is therefore an **integer** `-1`/`0`/`1` in the document rather than a
boolean. `1` is the only value that means the check ran and passed.

**Cases:** `gf-no-gpu` (step 20a) and `gf-no-host-ptr` (step 20b) assert `-1` for both fields;
`gf-device-limit` asserts the evaluated `0`; every successful `gf-gpu-*` case and the qualification
assert `1`.

### C15 — the shim's wrap gate refused only a limit it could read

`align_ggml_buffer_from_host` is the fail-closed second gate over section 2.6's segfault, and its
length rule was `if (max_size > 0 && size > max_size)`. `align_ggml_device_buft_max_size` returns a
**negative shim status** for a null device or an ABI drift, and on a negative status that condition
is false — the gate fell through to the call it exists to prevent.

**Shipped:** `if (max_size <= 0 || size > max_size)` in both C files, which is the same fail-closed
reading correction C1 gives a capability flag that is not exactly `1`: a limit this file cannot read
is not a limit it will wrap past.

### C16 — the qualification asserts the contract and prints the host

Section 5.2's assertion table pins `device.name == "MTL0"` and
`device.buffer_max_size == 9534832640`, both of which are section 2.1's readings of one Apple M1,
and indexes `schedule[27]` by its literal position. A different Mac would fail this qualification
for a reason that is not a defect, and a model with a different layer count would fail with an
`IndexError`.

**Shipped:** the three properties R5C actually depends on stay hard — a device of type GPU
(`type_id == 1`), `buffer_from_host_ptr` true, and `window_fits == 1` — plus
`buffer_alignment == 32` and `buffer_max_size >= window.bytes`, which is the bound step 21a checks.
The device's name and its maximum buffer length are **printed** with the window's share of it, the
narrowed layer is the last schedule row rather than row 27, and the two instrument paths are
validated as regular executable files rather than by `[ -x ]`, which is true of every searchable
directory.

### C17 — `ALIGN_LLM_GGML_BACKEND_DIR` was declared and never used

Section 5.2 declares it "where the backend plugins are dlopened from" and the runner validated it
and then ignored it: `ggml_backend_load_all` searches the executable's directory, the working
directory, and the `GGML_BACKEND_DIR` compiled into libggml, none of which this variable reaches.
The qualification could therefore name one install and exercise another.

The first repair reached for ggml's **`GGML_BACKEND_PATH`** environment variable, which names one
backend library file, and that **does not scope the load** — measured directly on the 0.21.0 this
host links against, with a throwaway harness linked against the same library the shim links:

```text
$ ./probe                                    # ggml_backend_load_all(), no variable
load_backend: loaded MTL backend from /opt/homebrew/Cellar/ggml/0.21.0/libexec/libggml-metal.so
devices=3   BLAS type=3   MTL0 type=1   CPU type=0        gpu=MTL0

$ GGML_BACKEND_PATH=<bogus>/libggml-metal.so ./probe      # an empty file, named explicitly
load_backend: loaded MTL backend from /opt/homebrew/Cellar/ggml/0.21.0/libexec/libggml-metal.so
load_backend: failed to load <bogus>/libggml-metal.so: dlopen(...)
devices=3   BLAS type=3   MTL0 type=1   CPU type=0        gpu=MTL0

$ ./probe <bogus>                            # ggml_backend_load_all_from_path(<bogus>)
devices=0                                                 gpu=(none)

$ ./probe /opt/homebrew/opt/ggml/libexec     # ggml_backend_load_all_from_path(the named dir)
load_backend: loaded MTL backend from /opt/homebrew/opt/ggml/libexec/libggml-metal.so
devices=3   BLAS type=3   MTL0 type=1   CPU type=0        gpu=MTL0
```

`GGML_BACKEND_PATH` **adds** to the compiled-in search, which runs first: a bogus library named by
it fails to load and the run still gets `MTL0` from `GGML_BACKEND_DIR`. The entry point that scopes
is `ggml_backend_load_all_from_path`, exported by libggml 0.21.0 (`nm -gU libggml.dylib` shows
`_ggml_backend_load_all_from_path` beside `_ggml_backend_load_all`), which **replaces** the search
path with its argument.

**Shipped**, and the shim does change after all:

1. `align_ggml_registry_ready` reads `ALIGN_GGML_BACKEND_DIR` from the environment at **run** time
   and calls `ggml_backend_load_all_from_path` with it when it is set and non-empty, and
   `ggml_backend_load_all` otherwise. Reading it at run time is exactly correction C3's rule kept:
   no shim behaviour depends on the environment the library was **compiled** in. The variable's name
   is a `#define` in the shared fenced region, so both C files declare one contract and the stub —
   which has no registry — documents that it loads nothing.
2. `scripts/run-metal-forward` still resolves `libggml-metal.so`/`.dylib` inside the declared
   directory, but exports the **directory** as `ALIGN_GGML_BACKEND_DIR` rather than the file as
   `GGML_BACKEND_PATH`, and prints that it is loading from there and nowhere else.
3. Finding the plugin is what lets the device probe change verdict: a declared directory with no
   Metal plugin stays an `N/A` line naming it — the Linux CI path, where no Metal plugin is ever
   built — while a directory that holds one and a registry scoped to it that still reports no GPU
   device is now a **`FAIL`**, because the named install is then failing to produce the device it is
   named for rather than being absent.

No hosted case can assert this: `make layer-forward-smoke` runs the stub shim and loads no backend
at all. The evidence is the probe above plus the qualification's own device line, which names the
directory it loaded from; and the negative case was run — `ALIGN_LLM_GGML_BACKEND_DIR` pointed at a
scratch directory holding an empty `libggml-metal.so` reaches `R5C_GPU_UNAVAILABLE` and the runner
fails, where before this correction it silently qualified Homebrew's `MTL0`.

### C18 — the owner's trap restores the shim, as the qualification's does

`scripts/run-layer-forward-smoke` rebuilds `build/lib/libalign_ggml_shim` with
`ALIGN_LLM_GGML_FORCE=...` flavours in all three of its blocks and restored the ordinary stub only
on each block's success path. An unhandled exception, a failed assertion, or a signal inside a
forced-failure loop left a `-DALIGN_GGML_FORCE_*` library in shared state outside the work tree for
whatever ran next. **Shipped:** the runner's `EXIT`/`HUP`/`INT`/`TERM` trap restores the ordinary
shim before removing the work tree, guarded so an ordinary exit pays for no rebuild — which is
`r5a-dense-layer-forward.md` correction C22's rule applied to the owner as well as to
`scripts/run-metal-forward`.

### C19 — the transcript oracle saturated where the logits oracle no longer does

Correction C12 closed `((v as f64) * S).round() as i64` for the **logits** comparison and left the
same conversion standing in the **transcript** oracle, in both files that own one:

```text
src/model_forward.align   computed := ((window.f32_le(spot * 4) as f64) * 10000.0).round() as i64
src/layer_forward.align   computed := ((window.f32_le(spot * 4) as f64) * 10000.0).round() as i64
```

Here the operand that has no fixed-point value is the **computed activation**, not an input, so
C12's refusal rule does not apply and cannot: an arm that refused its own non-finite activation
would be refusing the measurement. The failure mode is the mirror image of C12's abort and worse
than it. A `+inf` or `-inf` activation saturates to `i64`'s maximum or minimum; against a transcript
value of `0` the subtraction gives `i64`'s minimum, `0 - difference` wraps that back to itself, and
`magnitude > o.oracle_max_abs` is **false** — the element is silently dropped and the oracle can
report `PASS` over a node that is not a number. A NaN does not even need the wrap: `NaN as i64` is
`0`, which compares *equal* to a printed `0.0000`. Neither aborts, so neither was visible; C12's
histogram index is what made the logits half loud.

The same class runs a second time three lines below, in the **sum** comparison: a node whose f32
accumulation is non-finite has no millionths value either, and it covers the elements the transcript
never printed — `llama-eval-callback` prints at most six positions per axis, so the element
comparison above can only ever see a corner of each node.

**Shipped**, four changes and no new tolerance:

1. `src/model_forward.align`'s transcript element comparison routes the computed activation through
   `logit_ten_thousandths` — C12's own range-checked conversion, whose non-finite test is
   `digest_region`'s exponent test — and range-checks the transcript's value beside it. An
   unrepresentable operand takes `LOGIT_SCALE_LIMIT_TEN_THOUSANDTHS` as its magnitude, which is
   fifteen orders above `TOLERANCE_TEN_THOUSANDTHS`, so it is an `ORACLE_FAIL` by construction.
2. `src/layer_forward.align` gains the same conversion under its own name, `oracle_ten_thousandths`,
   with its own `ORACLE_SCALE_LIMIT_TEN_THOUSANDTHS`. The two modules keep their constants separate
   exactly as they already keep `MAX_TENSOR_ALIGNMENT` and the two tolerances separate.
3. Both sum comparisons refuse before subtracting: `src/model_forward.align` counts non-finite
   elements with the same exponent test while it is already walking the node, and
   `src/layer_forward.align` reads `nodes.nonfinite[]`, the count its own document already
   publishes. Either count, or a `computed` beyond `SUM_SCALE_LIMIT_MILLIONTHS` (10^12 units, twelve
   orders above anything measured), publishes `max_sum_diff_millionths` as the sentinel and sets the
   breach.
4. No published value changes for a finite node: **every one of the 74, 58, and 27 golden documents
   already checked in regenerates byte-identically**, and the three cases below are the only added
   lines in the three files.

**Cases.** A non-finite *computed* activation needs a forced build for the same reason the `primary`
branch does, and one build produces both: `ALIGN_LLM_GGML_FORCE=engine+inf-readback` (and
`engine+gpu+inf-readback`) makes the first element of every readback `+inf` and leaves the tensor
data untouched, so the graph still computes what it computed. Because the arms carry the residual
through that same readback, the `+inf` propagates through the model exactly as a real one would, and
every logit of the two-layer model's 32-element vector is non-finite by the head.

| Case | Arm | Asserts |
| --- | --- | --- |
| `lf-force-inf-readback` | `--layer-forward` | `status: ok`, `oracle.verdict FAIL`, `max_abs_diff_ten_thousandths` **10^15**, `max_sum_diff_millionths` the sentinel |
| `mf-force-inf-readback` | `--model-forward` | the same three, **and** `oracle_logits.verdict FAIL` at 10^15 with `output.nonfinite_count` 32 — the `primary` branch C12 could not reach |
| `gf-force-inf-readback` | `--model-forward-gpu` | the tolerance verdict alone, because oracle 2's element half is `N/A_DEVICE` here: `FAIL` at 10^15, 32 elements over half a unit, a **non-negative** mean, `p99` at the histogram's overflow bucket |

The runtime width is deliberate on the two model arms: the logits comparison is then the *tolerance*
path rather than the byte-identity one, so the verdict is driven by the bound the device arm exists
to publish rather than by a `sha256`.

### Cell-to-case map

Every applicable closure cell of section 4, mapped to the implementing function and the exact case
that covers it. `S` runs in `make layer-forward-smoke`; `Q` runs in
`make metal-forward-qualification`.

| Section 4 cell | Implementation | Evidence |
| --- | --- | --- |
| 4.1 construction — `device_by_kind` | `align_ggml_device_by_kind`, both C files | `S` `gf-no-gpu` (null on the engine stub); `Q` the device probe prints `MTL0` |
| 4.1 construction — `device_buft_max_size`, `device_props`, `device_text` (C1) | three wrappers, both C files | `S` `gf-gpu-ok` asserts the stub's `32` / `4294967296`; `Q` asserts `9534832640`, `32`, `MTL0`, host-ptr true |
| 4.1 success — status map | `ggml_ffi.r5_code_for` | `S` `gf-status-map`: every `STATUS_*` but `OK` and the `ABI` fall-through has a branch, and the fall-through is asserted to exist |
| 4.1 failure — no GPU device | `execute` step 20a | `S` `gf-no-gpu` → `R5C_GPU_UNAVAILABLE`, detail `device` (C6) |
| 4.1 failure — device lacks host-ptr | `execute` step 20b, `device_flag` | `S` `gf-no-host-ptr`; `Q` forced `no-host-ptr` against the real device |
| 4.1 move in/out — no aggregate holds `raw` | named locals only | `S` the record-declaration scan over `src/`, unchanged |
| 4.1 cleanup — per graph | `teardown_graph` | `S` `gf-teardown-partial` (a forced compute failure) balances every counter |
| 4.1 the two C files agree | the fenced region | `S` byte-identity assertion, unchanged and extended by the R5C block |
| 4.1 no `malloc`, contraction off | neither file allocates | `S` the `malloc` grep and `abi.fp_contract_off` on every document |
| 4.2 formation — no stage reshaped | `DeviceSelection` threaded through `execute` | `S` `arm-r5b-unchanged`, and **every R5A and R5B golden regenerates byte-identically** |
| 4.2 success — one schedule, two devices | `stage_read_block`, `carry_residual` untouched | `S` both arms' `schedule[]` agree on the synthetic model; `Q` 30 fills and 339 placements on both |
| 4.2 success — window sizing device-independent | `stage_window` | `S` `window.bytes` equal across arms; `Q` `447086592` on both |
| 4.2 failure — R5B's codes reachable from the GPU arm | `stage_*` | `S` `gf-gpu-alignment`, `gf-source-diverged`, `gf-transcript-*`, `gf-logits-*` (`gf-gpu-type` was dropped as a duplicate — C11) |
| 4.2 cleanup | section 3.10's order | `S` and `Q` `lifetime.graph_balance_failures` 0 on both arms |
| 4.3 formation — arm selection | first operand, before path work | `S` `gf-arm-unknown-flag`, `gf-arity-7` → no document |
| 4.3 formation — device through the registry | `execute` step 20a | `S` `gf-no-gpu`; `Q` `device.name == "MTL0"`, `type_id == 1` |
| 4.3 construction — properties published | `execute`, `gpu_forward.render_device` | `S` the golden `device` block; `Q` `buffer_max_size 9534832640`, `window_fits` **`1`** (correction C14: it is the tri-state integer, and `1` is the only value that means the check ran and passed) |
| 4.3 construction — the limit, before the first wrap | `execute` step 21a | `S` `gf-device-limit`, asserting `wrap_count == 0` in the error document; `Q` forced `max-buffer` against the real device |
| 4.3 success — every placement external | R5B's pointer-identity check | `S` `verdict: "EXTERNAL"`; `Q` **339 placements, 0 failures** |
| 4.3 success — the transfer is measured | `run_graph`, `window.wrap_*` | `S` one wrap per graph run; `Q` **59 wraps, 775.5 ms** (C7) |
| 4.3 early exit — `-` document | `gpu_forward.run` | `S` `gf-doc-stdout-identical` |
| 4.3 return — exit mapping | R0's, verbatim | `S` every case asserts `status` against the exit code |
| 4.3 cleanup — every device buffer freed | `teardown_graph` | `S` `graph_balance_failures` 0 and created == freed; **`Q` both runs exit 0**, which section 2.6 shows a leak would not |
| 4.4 reference — bytes equal, per block | `compare_source` | `S` `gf-source-diverged`; `Q` all 339 members equal |
| 4.4 reference — nodes identical, bit-exact on the device | `stage_reference_graph` | `S` 37/37 on four synthetic graphs; `Q` **479 of 479 over 30 graphs** |
| 4.4 transcript — grammar, coverage, element count | `scan_transcript`, `prepare_transcript` | `S` `gf-transcript-garbage`, `gf-transcript-missing-layer` |
| 4.4 transcript — a computed element with no ten-thousandth (C19) | `logit_ten_thousandths` / `oracle_ten_thousandths` at the element comparison, the non-finite count at the sum comparison | `S` `mf-force-inf-readback` and `lf-force-inf-readback`: `FAIL` at 10^15 with the sentinel sum, where a saturating `as i64` reported `PASS` |
| 4.4 transcript — `kq-L` `ne0` | step 30 | `S` `gf-transcript-kv-width` → `R5_ORACLE_SHAPE` |
| 4.4 transcript — elements deliberately not compared | step 31 | `S` `gf-gpu-transcript` and `gf-transcript-perturbed` both `N/A_DEVICE`/0 with `status: ok`; `Q` the same |
| 4.4 logits — file shape | step 32 | `S` `gf-logits-short`, `gf-logits-missing`; and C12's reference-element rule, `S` `gf-logits-nonfinite`, `gf-logits-nan` → `R5_LOGITS_NONFINITE`, and their `mf-` twins on the CPU arm |
| 4.4 logits — the tolerance verdict | `compare_logits` | `S` `gf-gpu-logits`, `gf-gpu-runtime-width`; `Q` **`WITHIN`, max 2,936 tt, argmax 671 both, top-10, 0 over half** |
| 4.4 logits — a real failure is not `WITHIN` | `compare_logits` | `S` `gf-logits-perturbed`: a 1.0 shift keeps the argmax and the whole top ten and is `FAIL`; `S` `gf-logits-huge` and `mf-logits-huge`: an out-of-range reference element is `FAIL` and never a wrapped pass (C12) |
| 4.4 logits — the arm's **own** non-finite element (C12, C19) | `compare_logits`'s `primary` branch | `S` `gf-force-inf-readback` and `mf-force-inf-readback`: `FAIL` at 10^15 with `output.nonfinite_count` 32, `status: ok`, and a non-negative mean |
| 4.4 determinism is asserted | `output.sha256` | `S` three consecutive runs agree; `Q` **two runs, `b6e473e8…` both** |
| 4.4 per-layer recorded, never gated | `schedule[].l_out_max_*` | `S` all three fields `-1` on every row of every case; `Q` the same, and all 28 layers' digests differ with `status: ok` (C4) |
| 4.4 tolerance not silently widened | `logits_tolerance` | `S` and `Q` assert `6000`; `arm-r5b-unchanged` asserts R5B's is still `5000` |
| 4.5 `R5C_GPU_UNAVAILABLE` | step 20a | `S` `gf-no-gpu`, detail `device` (C6) |
| 4.5 `R5C_NO_HOST_PTR` | step 20b | `S` `gf-no-host-ptr`; `Q` forced |
| 4.5 `R5C_DEVICE_BUFFER_LIMIT` | step 21a | `S` `gf-device-limit`; `Q` forced |
| discrete VRAM | — | `N/A`, section 1.3: no such device on this host and no equivalent entry point |
| microbenchmark C | — | `N/A`, deferred behind section 5.5's Request 41 |

---

## 7. Measured result

Every figure below is from one paired session on the host of section 2.1, with the shipped arm and
its shipped operands — a reference GGUF, a transcript, `KV_WIDTH` 256, and the byte-identical
`d2e48620…` logits — rather than from the single-pass probe harness of section 2. It is therefore
**not** comparable to section 5.3's totals, and section 5.3 is left as the probe record it is.

### 7.1 Correctness

| Oracle | Result |
| --- | --- |
| Oracle 1, self-reference, **bit-exact on Metal** | `IDENTICAL`, **479 of 479 nodes byte-identical over 30 graphs** |
| Oracle 2, transcript | `N/A_DEVICE`, 28 of 28 layers matched by the pre-schedule scan, 0 elements compared |
| Oracle 3, logits vs `d2e48620…` | **`WITHIN`** — max `\|Δ\|` **2,936** of 6,000 ten-thousandths, mean 528, p99 1,656, **0 of 152,064 elements over half a unit**, `argmax` **671** on both arms, top ten `[671, 220, 470, 715, 2529, 256, 2303, 262, 257, 414]` identical in order |
| Determinism | two consecutive runs, `output.sha256` **`b6e473e86ca903e2…` both** — section 2.3's digest, reproduced by the shipped arm |
| Placement | **339 placements, 0 pointer-identity failures**, `verdict: "EXTERNAL"` |
| Lifetime | `graph_balance_failures` 0, every counter balanced, **both runs exit 0** |
| Device | `MTL0` (`Apple M1`), `type_id` 1, alignment **32**, `buffer_max_size` **9,534,832,640 B**, `buffer_from_host_ptr` true, `host_buffer` false, `window_fits` **1** (correction C14) |

The measured worst case is **2,936** ten-thousandths against section 2.3's 2,937 — one
ten-thousandth, which is the last-place rounding of a `f64` product — so the bound section 3.7 fixed
before the qualification existed is **2.04×** the shipped arm's measured worst case, exactly as
derived.

### 7.2 Microbenchmark A, on the shipped arm

**Three paired runs**, each one CPU arm then GPU arm, alternating, in the same invocation of
`make metal-forward-qualification` on the same warm page cache. The pairing is the method, and three
pairs rather than one is the finding: this host's wall-clock spread is larger than the difference
being measured, so a single pair would have supported either conclusion.

| Metric | Pair 1 | Pair 2 | Pair 3 | Median |
| --- | --- | --- | --- | --- |
| **transfer — total over 59 wraps** | 775.5 ms | 695.3 ms | 732.3 ms | **732.3 ms** |
| **transfer — per 447,086,592 B wrap, zero bytes copied** | 13.14 ms | 11.79 ms | 12.41 ms | **12.41 ms** |
| GPU compute, reconciliation width (`T` = 6, `KV` = 256) | 376.9 ms | 375.4 ms | 353.7 ms | **375.4 ms** |
| CPU compute, same | 475.8 ms | 486.1 ms | 549.7 ms | **486.1 ms** |
| GPU compute, runtime width (`KV` = 6) | 509.6 ms | 492.4 ms | 570.6 ms | **509.6 ms** |
| CPU compute, same | 433.7 ms | 481.9 ms | 539.0 ms | **481.9 ms** |
| layers 0–26 compute, median | 18.19 / 15.51 | 17.18 / 15.22 | 19.61 / 18.48 | **18.19 GPU / 15.51 CPU** |
| layer 27, narrowed, `T` = 1 | 14.22 / 5.38 | 10.36 / 4.39 | 13.96 / 6.51 | **13.96 GPU / 5.38 CPU** |
| head, `MUL_MAT` against 447 MB of Q6_K | 10.22 / 11.83 | 9.94 / 10.67 | 9.78 / 13.58 | **9.94 GPU / 11.83 CPU** |
| `pread` | 1,686.9 / 1,503.8 | 1,483.9 / 1,584.0 | 1,588.7 / 1,619.9 | **1,588.7 / 1,584.0** |
| wall | 6,474.2 / 4,946.9 | 5,899.8 / 5,951.0 | 6,338.9 / 6,064.1 | **6,338.9 / 5,951.0** |
| **end-to-end ratio** | 1.31× slower | 0.99× | 1.05× slower | **1.05× slower** |

**Three results, in decreasing order of how well they are resolved.**

1. **The transfer costs 12.4 ms per 447 MB wrap and copies nothing.** This is the number
   microbenchmark A exists to publish and it is the most stable one here: 11.8–13.1 ms across three
   pairs, agreeing with section 2.7's independently measured 11.8 ms. The shipped arm pays it
   **fifty-nine times** — 732 ms per prefill — because it runs both passes (correction C7). The CPU
   arm's is 0.003 ms per wrap (section 2.7); its document does not publish the field, and quoting a
   zero from a missing field would not be a measurement.
2. **The GPU is faster where the work is large and slower where it is small**, and this holds in all
   three pairs. GPU compute at the reconciliation width is **375 ms against the CPU's 486 ms —
   1.29× faster** — while at the runtime width, where attention is six wide, it is 510 ms against
   482 ms. Per graph: the head's `MUL_MAT` against 447 MB of Q6_K is **1.19× faster** on the device,
   a full-width layer is 1.17× slower, and the narrowed last layer, whose `T` = 1 leaves the device
   idle, is **2.6× slower**. That decomposition is what a residency policy needs: the transfer tax
   scales with the **window**, the compute win scales with the **work**.
3. **End to end the two arms are within noise of each other on this host**, at a median of 1.05×
   with a spread from 0.99× to 1.31×. **This is not resolved and is not claimed as a result.** The
   spread is `pread`'s: it varies by 140 ms between pairs and is 25–27% of either arm's wall, and
   the whole compute difference the device makes is smaller than that variation. Section 2.9's
   single-pass harness measured 1.20× on a colder cache; the shipped arm's honest statement is that
   **the device choice does not move end-to-end prefill time on this host by more than the file read
   varies between runs.**

Section 1.5's recorded expectation was **negative**, and the measured result is between parity and
1.3× slower, so this is not a ceiling-estimation miss. **R5C discharges microbenchmark A on unified
memory and publishes an unfavourable-to-neutral number, which is the benchmark working.** The
deferred optimizations of section 5.4 now have a larger target than section 2.7 recorded: wrapping
once instead of fifty-nine times would remove most of 732 ms, and a per-block-class window would cut
what remains roughly threefold.

### 7.3 Align limitations this capability met

All three are recorded here as client evidence. None is a blocker: the shipped arm works around each
inside Align, with no compatibility layer and no hypothetical surface consumed.

1. **`alignc check` is not a superset of `alignc build`.** Three separate programs in this
   capability checked clean and failed to build, all in the region checker. A per-module `check` is
   therefore not sufficient evidence that a module compiles, which matters because `make check` is
   the narrow owner this repository runs after a coherent batch.
2. **A `borrow mut` record out-parameter cannot be read by a caller in another module** (C5), and
   the two obvious ways around it — returning the owners inside a record, and moving them into an
   already-constructed one — are refused by two further rules. The shape that works is "render where
   the data is produced and return `string`s", which is what `render_parts` does.
3. **A `borrow mut` argument's own field cannot be passed as a `str` view to the same call**:
   `borrowed argument 1 to 'fail' aliases argument 3, whose mode may invalidate the same owner`. The
   fix is a `.clone()` at the one call site that names the device in its own error detail.

Item 3 is ordinary aliasing discipline and is not a language gap. Items 1 and 2 are language-owned
and belong in `docs/align-requests.md` as client evidence for the module-boundary and
`Result`/return-payload requests already registered there; this capability records them and does not
file a new blocking request, because microbenchmark A is discharged without one.
