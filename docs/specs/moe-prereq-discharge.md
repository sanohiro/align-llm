# MOE-PREREQ-DISCHARGE: the per-expert half of R4 and R4.5, measured on a real MoE model

Status: design of record for the MOE-PREREQ-DISCHARGE capability.
Owner document for the **MOE-PREREQ** cells of
[`r4-alignpack-layer-major.md`](r4-alignpack-layer-major.md) and
[`r4-5-external-buffer.md`](r4-5-external-buffer.md).
Align pin: `.align-revision` = `4b515f8d37de2e9a9ba06170c5842fd12dc1cba2`.
Predecessor: [`r1c-olmoe-moe-ir.md`](r1c-olmoe-moe-ir.md), whose olmoe frontend produces the
1,058-block Block IR this capability packs and computes over.

`r4-alignpack-layer-major.md` remains authoritative for the alignpack v1 container, the layout
rule, the sequential-read metric, and the frozen `role_id` list. `r4-5-external-buffer.md` remains
authoritative for the shim contract, the FFI boundary, the lifetime and abort-safety rules, the
alignment gate, and every `R4_5_*` code this document does not add. `r1c-olmoe-moe-ir.md` remains
authoritative for the olmoe Model IR, the block emission order, and the slice arithmetic.

This document triggers the `CLAUDE.md` proportional design gate on two counts: it extends a public
CLI's accepted input domain (`ggml-spike` gains a second admitted member shape, with one new error
code), and it changes a versioned exchanged document (`R4_5_EXTERNAL_BUFFER` gains two fields and
becomes `schema_version: 2`). It does **not** change the container format, the block layout, the
role list, or any ownership boundary. Section 3 is the single public-contract ledger, section 4 is
the closure matrix, and section 5 owns fixtures, qualification, metrics, deferrals, and risks.

**Every number in this document is measured on
`$HOME/models/OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf` (4,213,512,192 bytes) on this host.** There is
no assumption banner and no synthetic number is presented as a real one. Section 2 is the probe
record, and it is first on purpose: the central design decision of section 3 exists because a probe
refuted a sentence that ships today.

---

## 1. Purpose, scope, non-goals, and the gate

### 1.1 Goal

Close the per-expert half of two merged gates with real weights, and change the documents that say
it is open.

`r4-alignpack-layer-major.md` section 1.4 item 3 says the MoE case "is verified **synthetically
only**". `r4-5-external-buffer.md` section 1.4 says `one expert matmul succeeds` is "**deferred for
an expert block**". Both statements were true when they were written and both are false now: a real
MoE model is present, `r1c-olmoe-moe-ir.md` turns it into 1,058 blocks of which 1,024 are
`ExpertBlock`s, and this capability packs it, verifies it, computes over one expert's claim, and
replaces the two `N/A` verdicts with measured ones.

This is a **qualification-and-record capability**. New code is written only where an existing arm
cannot address an expert claim, and section 2.4 measures that exactly one such place exists.

### 1.2 In scope

1. `main --pack` and `main --pack-verify` over the real MoE model: byte identity, and the
   sequential-read improvement reported **for `ExpertBlock`s specifically** rather than only in the
   total.
2. One minimal extension to `src/ggml_spike.align`: admit a member whose `nbytes` is a **claimed
   sub-range** of a stacked tensor — one plane — as a 2-D `mul_mat` left operand, with one new error
   code for a self-inconsistent slice pair.
3. Two fields added to `R4_5_EXTERNAL_BUFFER`, which becomes `schema_version: 2`.
4. `scripts/run-alignpack-qualification` and `scripts/run-ggml-spike` made model-shape-driven rather
   than model-name-driven, so both discharge their MoE verdicts from the model the existing
   `ALIGN_LLM_GGUF_MODEL` already names.
5. A hosted smoke that reaches the whole new validation path under the **stub** shim, over the
   synthetic olmoe corpus `scripts/gguf_fixture.py` already generates.
6. The record: which sentences in `r4-alignpack-layer-major.md`, `r4-5-external-buffer.md`, and
   `docs/specs/roadmap.md` change, and which stay.

### 1.3 Non-goals

- **No hotness ordering and no prefetch group.** `r4-alignpack-layer-major.md` sections 5.1 and 5.2
  stay deferred, unchanged, with their format fields still reserved. Both are functions of an
  activation distribution, which is roadmap item 19's output and not this capability's. Section 5.5
  states this as a gate, not as an omission.
- **No GPU expert arm.** `r4-5-external-buffer.md` section 5.4's Metal and discrete-VRAM deferrals
  are untouched. This capability adds a CPU expert arm; a GPU one still needs a tolerance oracle and
  a different alignment rule, which is a different acceptance contract.
- **No change to the container format.** The member record already carries everything a claim needs
  (section 2.3). Nothing is added to the block table, the member table, the name stream, or the
  source-identity record, and `block_align` / `member_align` are unchanged.
- **No R2A row.** R2A's **MOE-PREREQ** cells need a transcript, not a pack, and roadmap item 19
  (`agent/r2-locality-gate`) owns them. What this capability owes item 19 is one measured finding,
  handed over in section 5.6, not a repair.
- **No gpt-oss claim.** Every gpt-oss row stays synthetic. Section 5.5 records precisely which
  **MOE-PREREQ** cells survive because they are gpt-oss-specific rather than MoE-generic.
- **No performance claim.** Every elapsed number here is a diagnostic. The sequential-read metric is
  a claim about **layout**, exactly as `r4-alignpack-layer-major.md` section 2.6 defines it.

### 1.4 Gate statement

Four clauses, each discharged, deferred, or refuted **individually**, with the probe that settles it
named. A single "the MoE case passed" verdict would hide that one of them is a refutation.

| Clause | Verdict | Evidence |
| --- | --- | --- |
| R4 identity, MoE weights | **Discharged.** `--pack-verify` reports `identical` over all 4,211,730,432 payload bytes of 3,219 claims, and `scripts/alignpack_reader.py` agrees independently | Section 2.2 |
| R4 sequential read, `ExpertBlock`s specifically | **Discharged.** 1,024 `ExpertBlock`s go from 3,072 ranges / 165,368,823,808 span / **42,394,624 ppm** to 1,024 ranges / 3,900,702,720 span / **1,000,000 ppm**, and from 0 of 1,024 contiguous to 1,024 of 1,024 | Section 2.3 |
| R4.5 `one expert matmul succeeds` | **Dischargeable, and the shipped claim about how is refuted.** The CLI addresses the block, but the arm rejects the member: `R4_5_SHAPE`, detail `n_dims[3]`. A C probe at the same shim boundary shows the computation is correct once step 7 admits the claim | Sections 2.4 and 2.5 |
| R4 hotness and prefetch groups | **NOT discharged, deliberately.** Unchanged from `r4-alignpack-layer-major.md` sections 5.1 and 5.2 | Section 5.5 |

The honest terminal state is: *the alignpack format's largest promise — one expert is one read — is
measured on real MoE weights at a 42.4x reduction in sequential-read amplification; ggml computes
bit-identically over one expert's plane held in Align memory; the arm needed one shape rule it did
not have; and two of R4's four named layout properties remain deferred with their format surface
still reserved.*

### 1.5 What this capability is not allowed to do

It is not allowed to report a MoE pass by packing a dense model, and it is not allowed to report a
dense pass by packing a MoE model. Both qualifications therefore derive their verdicts from the
**shape of the block set they measured**, not from a model path, a file name, or an environment
variable the caller sets. Section 3.5 is that rule written as a contract; section 2.6 is why it
matters, because the qualification that runs today prints an `N/A` about a missing gpt-oss file
directly underneath a table listing 1,024 real `ExpertBlock`s.

---

## 2. Probe record

Host: Apple M1, 8 cores, 16 GiB, APFS on `/dev/disk3s5`. Toolchain: the pinned managed release at
`.align-revision` `4b515f8d`. ggml: the Homebrew install at `/opt/homebrew`, `libggml` 0.21.0, with
backends `BLAS`, `MTL` (Apple M1, unified memory), and `CPU` (`apple_m1`) loaded as plugins.
Model: `OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf`, 4,213,512,192 bytes, GGUF v3, `data_offset`
1,781,760, 195 tensors, 16 layers, 64 experts, top-8 routing.

Free space measured with `os.statvfs` on the probe directory's filesystem: **14,236,098,560 bytes
before the probes, 19,632,476,160 bytes after the 4,212,193,280-byte pack was removed.** No probe
artifact survives.

### 2.1 What the probes had to settle

Three questions, in the order the answers depend on each other:

1. Does `--pack` lay a claim out contiguously **per expert**, as
   `r4-alignpack-layer-major.md` section 2.4.7 consequence 2 promises for six-member gpt-oss expert
   blocks, when the real block has three members drawn from three stacked tensors of two different
   quantizations?
2. Does the shipped `ggml-spike` address an `ExpertBlock` member, as
   `r4-5-external-buffer.md` section 5.4 asserts it already does?
3. If it does not, is the failure in the arm's validation or in the computation? A validation gap is
   a shape rule; a computation gap would be a redesign.

### 2.2 The pack and the verify, on the real MoE model

```text
./main --pack       $MODEL $T/olmoe.alignpack $T/alignpack.json
./main --pack-verify $MODEL $T/olmoe.alignpack $T/alignpack-verify.json
python3 scripts/alignpack_reader.py --source $MODEL --pack $T/olmoe.alignpack \
    --pack-document $T/alignpack.json --verify-document $T/alignpack-verify.json
```

| Value | Measured |
| --- | --- |
| Blocks / members | 1,058 / 3,219 — exactly `r1c-olmoe-moe-ir.md` section 2.5.3's prediction |
| Payload bytes | 4,211,730,432, equal to the source's `total_tensor_bytes` |
| Pack total bytes | 4,212,193,280 (462,848 of header, name stream, tables, and identity record) |
| Interior padding | **0** |
| Duplicated bytes | 0 (`output.weight` is present, so the tied-embedding path is not taken) |
| `--pack` elapsed | 6,316,007,084 ns; 3,253 `pread`s, 3,264 `pwrite`s, 4 MiB window, peak window 4,194,304 B |
| `--pack-verify` elapsed | 2,053,824,625 ns; 8,425,705,472 bytes read, 4,211,730,432 compared, 3,252 fast-path windows, 0 byte-scan windows |
| Same two arms, run again through `make alignpack-qualification` | 5,718,116,708 ns and 2,466,802,958 ns — the run-to-run spread section 5.2 records as a budget rather than a threshold |
| `--pack-verify` verdict | `identical`, `first_mismatch: null`, `header_region_match: true` |
| Source identity digest | `ce233b8aa20f77d6002ce9fd4f81adea8e5e2f2b4fc16b810bb67a01fe85fee4` over 1,781,760 bytes |
| Independent reader | agrees field for field, 1.85 s |

**Interior padding is zero across all 1,058 blocks, and that is a property of this model, not of the
format.** Every claim's `nbytes` on this model is a multiple of 4,096 — a Q4_K plane is
`(2048/256) * 144 * 1024 = 1,179,648` and a Q6_K plane is `(1024/256) * 210 * 2048 = 1,720,320`, and
both divide by 4,096 — so every block start lands on `block_align` without a pad and every member
start lands on `member_align` without one. The consequence is recorded in section 5.7 as a
**coverage** risk: this model does not exercise the padding path, so the padding assertions stay
owned by the synthetic corpus.

### 2.3 The `ExpertBlock` amplification, which is the number the gate wanted

`r4-alignpack-layer-major.md` section 2.6's metric, reported `by_kind` by both `--pack-verify` and
the independent reader, which agree exactly:

| Kind | Blocks | Source ranges | Source span | Source ppm | Source contiguous | Pack ranges | Pack span | Pack ppm |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `WeightBlock` | 2 | 2 | 142,469,120 | 1,000,000 | 2 | 2 | 142,469,120 | 1,000,000 |
| `AttentionBlock` | 16 | 16 | 160,038,912 | 1,000,000 | 16 | 16 | 160,038,912 | 1,000,000 |
| **`ExpertBlock`** | **1,024** | **3,072** | **165,368,823,808** | **42,394,624** | **0** | **1,024** | **3,900,702,720** | **1,000,000** |
| `RouterBlock` | 16 | 16 | 8,519,680 | 1,000,000 | 16 | 16 | 8,519,680 | 1,000,000 |
| **Total** | **1,058** | **3,106** | **165,679,851,520** | **39,337,715** | **34** | **1,058** | **4,211,730,432** | **1,000,000** |

**Every non-contiguous block in the source is an `ExpertBlock`, every `ExpertBlock` is exactly three
ranges, and every one of them becomes one range in the pack.** The whole model's amplification is
39.34x and the `ExpertBlock` kind's alone is **42.39x**; the other three kinds are already at
1,000,000 ppm because the source file is alphabetical within a layer
(`r1c-olmoe-moe-ir.md` section 2.5.6). Reporting only the total would therefore have understated the
one number the format exists for, which is exactly why section 2.6 of the R4 document made `by_kind`
part of the metric.

**R4's own prediction was close and slightly high, and the difference is instructive.**
`r4-alignpack-layer-major.md` section 2.2 finding 4 predicted "on the order of `n_expert` times its
payload". With `n_expert = 64` that would be 64x; the measurement is 42.4x. The gap is because an
expert's three claims lie inside one *layer's* expert region rather than across the whole file, and
because the three stacked tensors are not adjacent in the alphabetical run — `ffn_down_exps` sorts
before `ffn_gate_exps`, which sorts before `ffn_up_exps`, with `ffn_gate_inp` and `ffn_norm` between
the last two. The prediction's *shape* holds and its constant does not, and the honest form of the
claim is the measured one.

The single worst and best cases, from the pack document's per-block records:

```text
block 3     ExpertBlock layer 0  expert 0   pack_offset 69,488,640   pack_bytes 4,079,616
            source_range_count 3   source_span_bytes 187,310,080   source ppm 45,913,655
            pack_range_count   1   pack_span_bytes     4,079,616   pack   ppm  1,000,000
              blk.0.ffn_gate_exps.weight  source 264,894,464  nbytes 1,179,648  Q4_K [2048,1024,64] slice 0/64
              blk.0.ffn_up_exps.weight    source 340,924,416  nbytes 1,179,648  Q4_K [2048,1024,64] slice 0/64
              blk.0.ffn_down_exps.weight  source 154,793,984  nbytes 1,720,320  Q6_K [1024,2048,64] slice 0/64
```

One expert of layer 0 is **187,310,080 source bytes for 4,079,616 of payload, and 4,079,616 pack
bytes for the same payload** — the 45.9x that made `r1c-olmoe-moe-ir.md` section 2.5.6 write "loading
one expert of one layer costs three separated reads spanning 187 MB". It now costs one 4 MB read.

**The member record already carries the claim, so the container needs nothing.**
`r4-alignpack-layer-major.md` section 2.4.4 defines `source_offset` as `claimed_absolute_offset` and
`nbytes` as `claimed_nbytes`, with `slice_index` and `slice_count` beside them; `src/alignpack.align`
writes them from `r1b-gptoss-moe-ir.md` section 2.5.3's arithmetic, and the values check by hand:
expert 63's gate claim is at `264,894,464 + 63 * 1,179,648 = 339,212,288`, which is the recorded
`source_offset`. `src/alignpack_read.align` already decodes both fields into `PackMember`. Nothing in
the container, the writer, the verifier, or the standalone reader needs a line.

### 2.4 The refutation: the spike rejects an expert claim

`r4-5-external-buffer.md` section 5.4 says, of the expert-block deferral, that "when a real MoE GGUF
exists the qualification gains one line — **the CLI already addresses an `ExpertBlock` by its block
index with no new surface**". `scripts/run-ggml-spike` prints the same sentence as its `(expert
block): N/A` line. Measured, against the real pack:

```text
$ ggml-spike $T/olmoe.alignpack 3 0 $T/spike-expert.json $MODEL
status:  ERROR          verdict: UNAVAILABLE
block: 3   member: 0    name: blk.0.ffn_gate_exps.weight
ggml type: 12           dims: 2048x1024      member bytes: 1179648   block bytes: 4079616
error: R4_5_SHAPE       detail: n_dims[3]                            exit 2
```

The sentence is **half true and therefore misleading**: the CLI does address the block by index — the
selection resolved, the name and dims and byte counts are all correct — and then step 7 of
`r4-5-external-buffer.md` section 3.8 refuses the member, because it requires `n_dims == 2` and
`dim2 == 1` and a claim on a stacked tensor is `n_dims == 3` with `dim2 == n_expert`. No expert
matmul is reachable through the shipped arm on any real MoE pack.

The dense control on the **same MoE pack** succeeds, which localizes the failure to the shape rule
and not to the model, the pack, or the boundary:

```text
$ ggml-spike $T/olmoe.alignpack 1 1 $T/spike-dense.json $MODEL
status: OK   verdict: EXTERNAL   name: blk.0.attn_q.weight   dims: 2048x2048
member bytes: 2359296   block bytes: 10543104   data offset: 8192   buffer align: 0
output sha256: f7430e7beefe2d3322f3b115f2cd25683c49db31b96fa38f37d7a19c14f763a7
output bit sum: 17199420034216   reference: IDENTICAL   released: 7   exit 0
```

### 2.5 The C probe: the computation is correct, only the rule is missing

Before designing a shape rule, the question of section 2.1 item 3 had to be answered: is a claimed
plane actually a valid `mul_mat` left operand, and does a pointer into the middle of an
Align-owned block buffer still give pointer identity and a bit-identical result against the GGUF?

`moe_claim_probe.c` (out of tree, recorded in the pull request) calls **exactly the shim entry points
`src/ggml_spike.align` calls, in the same order** — `align_ggml_device_open`,
`align_ggml_backend_open`, `align_ggml_context_open`, `align_ggml_buffer_from_host`,
`align_ggml_new_tensor_2d`, `align_ggml_mul_mat`, `align_ggml_tensor_place`,
`align_ggml_alloc_remaining`, `align_ggml_tensor_set`, `align_ggml_tensor_data_offset`,
`align_ggml_compute`, `align_ggml_tensor_get` — so a pass is evidence about the Align arm and not
about a different boundary. It reads the **whole block** with one `pread` at `block.pack_offset`,
places a 2-D `[dim0, dim1]` tensor of `member.ggml_type` at `base + interior_offset`, builds the
identical `act[j] = ((j mod 17) - 8) / 8` activation of `r4-5-external-buffer.md` section 3.6 with
`ACTIVATION_COLUMNS = 4`, and compares bit-exactly against the same plane read from the GGUF at
`source_offset` into a ggml-allocated tensor.

| Case | Type | `[ne0, ne1]` | `nbytes` | Interior | `ggml_nbytes` == `nbytes` | Data offset | Differing elements | Output `sha256` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| L0 e0 `ffn_gate_exps` | Q4_K | 2048, 1024 | 1,179,648 | 0 | yes | 0 | **0** of 4,096 | `237ffed519b03a78ff1219aa0a89af8c2bf6876f1931bef4f9874145f6f5220f` |
| L0 e0 `ffn_up_exps` | Q4_K | 2048, 1024 | 1,179,648 | 1,179,648 | yes | 1,179,648 | **0** of 4,096 | `1a5ceeeaad4c03d43e2e73fafe1b73f2b74edb86970ec021b65018c2cda91c1a` |
| L0 e0 `ffn_down_exps` | Q6_K | 1024, 2048 | 1,720,320 | 2,359,296 | yes | 2,359,296 | **0** of 8,192 | `6436a1ff2caac9446fc784e7c6b74bda70ee14d2a9ca051905fbc9a7ef21f8ef` |
| L0 e63 `ffn_gate_exps` | Q4_K | 2048, 1024 | 1,179,648 | 0 | yes | 0 | **0** of 4,096 | `7ece476fb88aa549cb028ca59ddc956574824203395f35f58aa2339b07bce55b` |
| L2 e0 `ffn_gate_exps` | Q4_K | 2048, 1024 | 1,179,648 | 0 | yes | 0 | **0** of 4,096 | `2cc63d0a51ec4f189c153a711944d3052e11875929a78d6a12f5c3a92c8eeba4` |

`tensor_alignment` is 32 on every run, and the pack bytes at `interior` equal the GGUF bytes at
`source_offset` in all five cases before any compute runs.

Five findings, each load-bearing for section 3:

**Finding 1 — a claim's `[dim0, dim1]` *is* its plane, exactly.** `ggml_nbytes` of the 2-D tensor
built from the member's recorded `dim0` and `dim1` equals the member's recorded `nbytes` in every
case, in both axis orders and in both quantizations. The existing step-15 equality check of
`r4-5-external-buffer.md` section 3.8 — "the pack's recorded `nbytes` and `ggml_nbytes()` must
agree", which that document calls the check that the member table can size a member from the pack
alone — therefore becomes **stronger** for a claim, not weaker: it is now also the check that the
plane arithmetic of `r1b-gptoss-moe-ir.md` section 2.5.3 agrees with ggml's own type table. No new
assertion is needed for it.

**Finding 2 — the reference arm already reads the right bytes.** `M.source_offset` is
`claimed_absolute_offset`, so `pread(M.nbytes, M.source_offset)` on the GGUF is the plane and
nothing else. The oracle of `r4-5-external-buffer.md` section 3.6 needs no change, and expert 63's
case (`264,894,464 + 63 * 1,179,648`) is the evidence that the arithmetic holds at the far end of a
64-plane stack rather than only at plane 0.

**Finding 3 — a non-zero interior offset is exercised, and only by members 1 and 2.** The first
member of an `ExpertBlock` sits at the block's own `pack_offset`, so its interior offset is 0 and it
does **not** test interior addressing. `ffn_up_exps` at 1,179,648 and `ffn_down_exps` at 2,359,296 do.
Section 5.2 makes the qualification run all three members for this reason rather than picking one.

**Finding 4 — the mixed per-layer quantization is exercised for free.** `r1c-olmoe-moe-ir.md`
section 2.5.5 records that eight of sixteen layers carry `ffn_down_exps` as Q6_K and eight as Q4_K,
so two blocks of the same kind have different `byte_size`s. Layer 0 is a Q6_K layer and layer 2 is a
Q4_K one; both probe rows pass, so the arm's type handling is confirmed across the split without a
fixture that manufactures it.

**Finding 5 — nothing in the boundary needed changing.** No shim function was added, no alignment
rule moved, no lifetime rule moved. `align_ggml_tensor_place` accepted `base + 1,179,648` and
`base + 2,359,296`, both of which are 32-aligned because `member_align` is 64.

### 2.6 What the probes settle, and the one thing they do not

Settled: the container needs nothing (2.3); the computation is correct (2.5); the only gap is one
validation rule in one function (2.4). That makes this a qualification-and-record capability with a
minimal code change, and section 3 is written to keep it that way.

Not settled by a probe, and worth stating because it is the reason section 1.5 exists: the shipped
`scripts/run-alignpack-qualification` **passes** on this model and prints, immediately below a table
listing 1,024 real `ExpertBlock`s with a measured 42,394,624 ppm improvement:

```text
alignpack qualification (MoE): N/A - no gpt-oss GGUF on this host; see
docs/specs/r4-alignpack-layer-major.md section 4.5.
```

Nothing is wrong with the numbers; the verdict line is a constant. A qualification whose verdict does
not depend on what it measured is not a qualification, and section 3.5 replaces both such constants
with rules over the measured block set.

---

## 3. Public-contract ledger

### 3.1 `ggml-spike` — the CLI grammar is unchanged

```text
ggml-spike PACK.alignpack BLOCK MEMBER [DOC.json [REF.gguf]]
```

Three, four, or five operands; `BLOCK` is the Model IR block index; `MEMBER` is the member's position
within that block; `-` in the fourth position is "document to stdout". All unchanged from
`r4-5-external-buffer.md` section 3.3, including the absence of a `--backend` flag. An `ExpertBlock`
is selected exactly as any other block, which is the half of that document's section 5.4 sentence
that was true. For the real model, `r1c-olmoe-moe-ir.md` section 2.5.3's emission order makes the
first expert of layer `L`, member `m`, the pair `BLOCK = 3 + 66 * L`, `MEMBER = m`.

### 3.2 The one changed rule — step 7 of the validation order

`r4-5-external-buffer.md` section 3.8 step 7 currently reads: `n_dims == 2`, `dim0 >= 1`,
`dim1 >= 1`, `dim2 == 1`, `dim3 == 1`, `nbytes >= 1`, and the member's range inside its block.

It is replaced by **step 7a** (the slice pair) and **step 7b** (the shape), in that order.

**Step 7a — the slice pair is well formed.** `r4-alignpack-layer-major.md` section 2.4.4 defines
`slice_index` and `slice_count` as `-1`/`-1` for a whole-tensor claim and `plane index`/`sliced
axis extent` otherwise. Exactly two pairs are admitted:

```text
whole  slice_index == -1 and slice_count == -1
claim  slice_index >=  0 and slice_count >=  1 and slice_index < slice_count
```

Anything else — one of the two negative and the other not, `slice_count == 0`, or
`slice_index >= slice_count` — is **`R4_5_SLICE`**, with detail `pair`, `count[<n>]`, or
`index[<n>]` respectively.

**Step 7b — the shape, chosen by the pair.**

```text
both forms   dim0 >= 1, dim1 >= 1, dim0 <= MAX_DIMENSION, dim1 <= MAX_DIMENSION,
             nbytes >= 1, dim3 == 1,
             [pack_offset, pack_offset + nbytes) inside [block.pack_offset, +pack_bytes)
whole        n_dims == 2  and dim2 == 1
claim        n_dims == 3  and dim2 == slice_count
```

Failures are `R4_5_SHAPE` with the existing details `n_dims[<n>]`, `ne0[<n>]`, `ne1[<n>]`,
`nbytes[<n>]`, `ne0_bound[<n>]`, `ne1_bound[<n>]`, and one new detail `dim2[<n>]` for a claim whose
declared expert-axis extent is not its `slice_count`. `dim2_dim3` remains the detail for a
whole-tensor member with a non-unit `dim2` or `dim3`; a claim with a non-unit `dim3` reports
`dim3[<n>]`, because `n_dims == 3` makes `dim3` the one axis that must still be absent and naming
the pair would not say which.

**Everything downstream of step 7 is unchanged**, and section 2.5 is why: `A` is
`new_tensor_2d(ggml_type, dim0, dim1)` in both forms, the step-15 `ggml_nbytes == nbytes` equality
holds in both, the activation is `[dim0, 4]` in both, the output is `[dim1, 4]` in both,
`interior = member.pack_offset - block.pack_offset` is unchanged, the alignment gate at step 13 is
unchanged, and the reference arm reads `nbytes` at `source_offset` in both. `n_dims` is carried into
the document already; only the two slice fields are new.

**Why `R4_5_SLICE` is a new code and not another `R4_5_SHAPE` detail.** The two failures name
different faults. `R4_5_SHAPE` means *this member is not usable as a `mul_mat` left operand* — a
refusal by the arm about the arm's own domain. A self-inconsistent slice pair means *this container's
member record contradicts itself* — a defect the R4 writer cannot produce, that `--pack-verify` does
not check, and that no valid pack can contain. Reporting it as `R4_5_SHAPE` would tell an operator
the tensor is the wrong shape when the file is malformed, which is the class of mis-attribution that
`r4-5-external-buffer.md` section 3.6 already avoids by checking bytes before numbers and reporting
`R4_5_SOURCE_DIVERGED` rather than a numeric difference.

**Why it is not an `R4_PACK_*` code raised by the reader.** `src/alignpack_read.align` raises R4's
vocabulary verbatim, and `r4-5-external-buffer.md` section 3.5 fixes exactly what it validates:
magic, version, record widths, alignments, flags, length, region containment and disjointness,
`payload_offset` alignment. Adding a slice rule there would put a container rule in the standalone
reader that `--pack-verify` does not enforce, splitting the truth about what a valid v1 container is
across two owners. Making both enforce it is a change to R4's format validation, owned by R4 and
worth doing on its own evidence, not as a side effect of this capability. Section 5.5 records it as a
deferral with that reason.

### 3.3 `R4_5_EXTERNAL_BUFFER`, `schema_version: 2`

Two fields are added to the `tensor` object, and the version is bumped:

```text
tensor   ggml_type, n_dims, ne0, ne1, nbytes,
         slice_index, slice_count,                        # new
         blck_size, type_size, elements_per_row_ok (bool)
```

`slice_index` and `slice_count` are the member record's values verbatim: `-1` and `-1` for a
whole-tensor member, `[0, slice_count)` and `[1, ...]` for a claim. They are always present, in both
forms, because an absent field and a `-1` field are different statements and a consumer must not
have to distinguish them by key presence.

**The version is bumped rather than treated as additive, and the precedent is R1B.**
`r4-5-external-buffer.md` section 3.7 states that "a consumer keys on `kind` plus `schema_version`",
so a consumer at version 1 that receives a document describing a claim would read a `tensor` object
whose `ne0`/`ne1` no longer describe the whole tensor the `name` names — a difference in meaning, not
only in fields. `r1b-gptoss-moe-ir.md` took `R1_MODEL_IR` to `schema_version: 2` for the same kind of
change, and following that precedent is cheaper than explaining a new one.

The summary block gains exactly one line, after `dims:`:

```text
slice:             <index>/<count>      # or "-" for a whole-tensor member
```

Both output forms continue to emit byte-identical document bytes, and the `verdict` vocabulary
(`EXTERNAL` / `COPIED` / `UNAVAILABLE`) is unchanged.

### 3.4 Error codes, complete

| Code | Meaning | Step | Detail | Status |
| --- | --- | --- | --- | --- |
| `R4_5_SLICE` | the member record's `slice_index` / `slice_count` pair is self-inconsistent | 7a | `pair` / `count[<n>]` / `index[<n>]` | **new** |
| `R4_5_SHAPE` | the member is not a 2-D `mul_mat` left operand, or `ne0 % blck_size != 0` | 7b, 12 | adds `dim2[<n>]`, `dim3[<n>]`; keeps `n_dims[<n>]`, `ne0[<n>]`, `ne1[<n>]`, `nbytes[<n>]`, `ne0_bound[<n>]`, `ne1_bound[<n>]`, `dim2_dim3` | extended |
| every other `R4_5_*` and `R4_PACK_*` | unchanged | unchanged | unchanged | unchanged |

Exit mapping is R0's, reused verbatim and unchanged: `Ok(())` on `status: "ok"`,
`Err(Error.Invalid)` after an error document, `Err` with no document for arity, path, or OS failure.

### 3.5 The two qualifications become shape-driven

Neither script gains an environment variable. `ALIGN_LLM_GGUF_MODEL` already names the model, and
adding a second variable to say "this one is a MoE model" would let a caller assert a verdict the run
did not measure — exactly the defect section 1.5 refuses.

**`scripts/run-alignpack-qualification`.** Everything through the identity and sequential-read
verdicts is unchanged. The trailing constant

```text
alignpack qualification (MoE): N/A - no gpt-oss GGUF on this host; see ...
```

is replaced by a rule over `sequential_read.source.by_kind` and `sequential_read.pack.by_kind`:

- If neither side has an `ExpertBlock` entry, print
  `alignpack qualification (MoE): N/A - the packed model has no ExpertBlock; see section 5.5.`
  and neither pass nor fail.
- Otherwise assert, and print `PASS` with all six numbers:

  ```text
  source.contiguous_block_count == 0
  source.range_count            >  pack.range_count
  source.span_bytes             >  pack.span_bytes
  source.amplification_ppm      >  pack.amplification_ppm
  pack.contiguous_block_count   == pack.block_count
  pack.range_count              == pack.block_count
  pack.amplification_ppm        == 1000000
  pack.span_bytes               == pack.payload_bytes
  ```

  `source.contiguous_block_count == 0` is asserted rather than merely reported because a source in
  which some expert is already contiguous is a *different* model shape and the verdict should say so
  by failing rather than by silently averaging it away — the same strictness argument
  `r4-alignpack-layer-major.md` section 4.4 makes for the improvement verdict as a whole.

The verdict line, measured today, is:

```text
alignpack qualification (MoE): PASS  ExpertBlock 1024 blocks
    src  3072 ranges / 165368823808 span / 0 contiguous / 42394624 ppm
    pack 1024 ranges /   3900702720 span / 1024 contiguous / 1000000 ppm
```

**`scripts/run-ggml-spike`.** Two changes. First, the selection stops being the constant `1 1` and is
derived from the pack document the run just wrote:

```text
dense arm    the first AttentionBlock's member whose role is attn_q
expert arm   the first ExpertBlock's three members, in member order
```

Both are resolved by `role_id` — `attn_q` is 1, and the expert roles are 19 / 21 / 23 — and not by
name, because `r1c-olmoe-moe-ir.md` section 2.5.2 makes `role_id` the stable identity while a GGUF
name is a model's own spelling. A model with no `ExpertBlock` prints the `N/A` line of section 5.5
for the expert arm and runs the dense arm as it does today; a model with no `AttentionBlock` is a
`FAIL`, because every architecture this repository supports has one.

Second, the assertions split into invariants and a small keyed table. The invariants hold for every
model and every member and are the ones that carry the gate:

```text
status ok, verdict EXTERNAL
tensor.nbytes == the member record's nbytes, elements_per_row_ok true
buffer.interior_offset == member.pack_offset - block.pack_offset
buffer.tensor_data_offset == buffer.interior_offset, pointer_identity true
buffer.output_pointer_identity true
tensor.slice_index / slice_count == the member record's pair
reference.bytes_equal true, reference.verdict IDENTICAL, differing_elements 0
lifetime *_created == *_freed, released_before_owner_scope_end true
abi.tensor_alignment 32, q4k_blck_size 256, q4k_type_size 144, table_drift -1
```

The golden digests are keyed by the pack document's `source.header_region_sha256`, which
`r4-alignpack-layer-major.md` section 2.4.6 already computes and which identifies a model down to the
last tensor's placement. That is what lets one script hold golden values for more than one model
without keying on a path. `ALIGN_LLM_GGML_SPIKE_SHA256` remains an override for the dense arm and
gains `ALIGN_LLM_GGML_SPIKE_EXPERT_SHA256` for the expert arm's first member; an unknown model
identity prints one `N/A` line for the digest assertion only and still runs every invariant.

Measured entries for `ce233b8aa20f77d6002ce9fd4f81adea8e5e2f2b4fc16b810bb67a01fe85fee4`
(OLMoE-1B-7B-0125-Instruct-Q4_K_M):

| Arm | Block / member | Name | Dims | `nbytes` | Interior | `sha256` |
| --- | --- | --- | --- | --- | --- | --- |
| dense | 1 / 1 | `blk.0.attn_q.weight` | 2048x2048 | 2,359,296 | 8,192 | `f7430e7beefe2d3322f3b115f2cd25683c49db31b96fa38f37d7a19c14f763a7` |
| expert | 3 / 0 | `blk.0.ffn_gate_exps.weight` | 2048x1024 | 1,179,648 | 0 | `237ffed519b03a78ff1219aa0a89af8c2bf6876f1931bef4f9874145f6f5220f` |
| expert | 3 / 1 | `blk.0.ffn_up_exps.weight` | 2048x1024 | 1,179,648 | 1,179,648 | `1a5ceeeaad4c03d43e2e73fafe1b73f2b74edb86970ec021b65018c2cda91c1a` |
| expert | 3 / 2 | `blk.0.ffn_down_exps.weight` | 1024x2048 | 1,720,320 | 2,359,296 | `6436a1ff2caac9446fc784e7c6b74bda70ee14d2a9ca051905fbc9a7ef21f8ef` |

The existing narrow claim about digests is inherited verbatim: each is correct for this model, this
member, this activation, this ggml version, and this CPU backend, it is not portable, and its failure
message says the kernel or the model changed rather than reading as a corruption report.

The `(expert block)` `N/A` line is deleted. The `(GPU arm)` and `(discrete VRAM)` `N/A` lines are
**unchanged**, and section 5.5 is why.

### 3.6 Which sentences change, and which do not

This is the record half of the capability, stated as a diff of claims so a reviewer can check it
against the final tree.

**`docs/specs/r4-alignpack-layer-major.md`**

| Location | Change |
| --- | --- |
| §1.4 item 3 | Rewritten from **NOT discharged** to **discharged on olmoe**, with section 2.3's `by_kind` row. The clause "No gpt-oss GGUF exists on this host … so every real-model number in this document is the dense qwen2 case" narrows to: the gpt-oss six-member `ExpertBlock` and its MXFP4 geometry stay synthetic; the MoE case is real |
| §1.4 item 4 | **Unchanged.** Hotness and prefetch groups remain not discharged |
| §1.4 closing paragraph | "two of the four named layout properties are deferred" is unchanged; "verified over a real 4.68 GB model" gains the second model |
| §2.2 finding 4 | Gains the measurement and the correction of its own prediction: 42.4x measured against "on the order of `n_expert`" (64x) predicted, with section 2.3's reason |
| §3.2 row *Success — per-expert contiguity* | **MOE-PREREQ** removed; the case becomes `run-alignpack-qualification`'s ExpertBlock verdict beside the existing synthetic `expert-block-contiguous` |
| §4.4 verdict block | The third printed line changes from the constant `N/A` to section 3.5's `PASS` |
| §4.5 *The MoE prerequisite* | Retitled and narrowed to the **gpt-oss** prerequisite. Its disk argument is superseded by the roadmap's recorded finding that 12.1 GB is infeasible on this host; its sentence naming the small-MoE alternative is now satisfied |
| §4.6 | The primary-metric list gains the `by_kind` `ExpertBlock` row as a discharged measurement |
| §7.2 *Cells this host cannot reach* | The per-expert-contiguity row moves out; the gpt-oss-specific rows stay |

**`docs/specs/r4-5-external-buffer.md`**

| Location | Change |
| --- | --- |
| §1.4 row `one expert matmul succeeds` | From "Dischargeable for a dense block; **deferred for an expert block**. This host's model has no experts" to "**Discharged** for a dense block and for an expert claim on the CPU backend; deferred for the GPU arm", citing sections 2.4 and 2.5 here |
| §3.3 | Gains the `slice:` summary line |
| §3.7 | `schema_version` becomes 2; `tensor` gains `slice_index` and `slice_count` |
| §3.8 step 7 | Replaced by steps 7a and 7b of section 3.2 here; the code table gains `R4_5_SLICE` and the two new `R4_5_SHAPE` details |
| §4.3 / §4.6 | The `R4_5_SHAPE` fixture rows gain the claim cases; a new `R4_5_SLICE` row |
| §5.2 | The assertion table becomes the invariants plus the model-keyed digest table of section 3.5 here |
| §5.4 bullet *An expert block* | **The sentence "the CLI already addresses an `ExpertBlock` by its block index with no new surface" is refuted and removed.** Replaced by the measurement of section 2.4 and a pointer to step 7a/7b. The bullet itself is deleted from the deferral list |
| §5.4 bullets *Metal and the VRAM half*, *Discrete VRAM*, *The R5 loader*, *More than one node*, *A read-only pack open* | **Unchanged** |

**`docs/specs/roadmap.md`**

| Location | Change |
| --- | --- |
| Item 13 (R4) | "The per-expert half is closed synthetically and stays **MOE-PREREQ**" becomes the measured olmoe result; the residual **MOE-PREREQ** is named as gpt-oss-specific |
| Item 14 (R4.5), Japanese bullet `one expert matmul succeeds` | Rewritten: dense **and** expert claim discharged on CPU; the "CLIはExpertBlockをblock indexで既に指定でき、新surfaceは不要" clause is corrected, since one shape rule and one error code were required |
| A new item | MOE-PREREQ-DISCHARGE, with this document as the authoritative plan |

**`docs/specs/r2a-expert-trace.md`** — **no row changes.** Its **MOE-PREREQ** cells need a
transcript and are owned by roadmap item 19. Section 5.6 is the handover.

**`docs/specs/r1c-olmoe-moe-ir.md`** — no change. Its section 2.5.6 already predicted the
non-contiguity this capability measured, and section 2.3 above confirms rather than corrects it.

### 3.7 Ownership, allocation, and owner modules

| Surface | Owner | New allocation |
| --- | --- | --- |
| Steps 7a/7b, `R4_5_SLICE`, the two document fields, the `slice:` summary line | `src/ggml_spike.align` | none — both fields are already in `PackMember` |
| `PackMember.slice_index` / `.slice_count` decode | `src/alignpack_read.align` | **no change**; already decoded at offsets 80 and 84 |
| Container, layout, claim arithmetic, verifier | `src/alignpack.align`, `src/model_ir.align` | **no change** |
| ExpertBlock verdict | `scripts/run-alignpack-qualification` | none |
| Role-driven selection, keyed digests, expert arm | `scripts/run-ggml-spike` | none |
| Stub-reachable claim cases | `scripts/run-ggml-spike-smoke`, `scripts/gguf_fixture.py` | one synthetic olmoe pack per smoke run, in the runner's own temporary tree |

The lifetime and abort-safety contract of `r4-5-external-buffer.md` section 3.9 is unchanged in every
particular: one `pread` into one Align-owned `buffer`, ggml holding a borrowed pointer, teardown in
the recorded order before the owner's scope ends, and `lifetime.released_before_owner_scope_end`
still asserted.

### 3.8 Ledger dimensions

| Dimension | Value |
| --- | --- |
| Public surfaces changed | 1 CLI input domain (`ggml-spike` member shape), 1 exchanged document (`R4_5_EXTERNAL_BUFFER` 1 → 2) |
| Error codes added | 1 (`R4_5_SLICE`), 2 details added to an existing code |
| Persisted formats changed | **none** — alignpack v1 is untouched |
| Align modules changed | 1 (`src/ggml_spike.align`) |
| Scripts changed | 3 (`run-alignpack-qualification`, `run-ggml-spike`, `run-ggml-spike-smoke`) + fixture |
| Documents amended | 3 (`r4-alignpack-layer-major.md`, `r4-5-external-buffer.md`, `roadmap.md`) |
| Schema versions bumped | 1 |
| New modules | 0 |

---

## 4. Closure matrix

Cell names are cases inside `scripts/run-ggml-spike-smoke` unless another runner is named.
Every cell is reachable on a hosted runner under the **stub** shim except those marked **CAPABLE**,
which need a real ggml and the real model; each of those has a hosted companion over a fixture
document wherever the cell is a rule rather than a computation.

### 4.1 `src/ggml_spike.align` — step 7a, the slice pair

| Cell | Contract | Implementation | Regression |
| --- | --- | --- | --- |
| Construction | Both fields are read from the decoded `PackMember`; no second decode | reads `member.slice_index`, `member.slice_count` | `olmoe-expert-claim` asserts the document's pair equals the pack document's |
| Success — whole | `-1` / `-1` admits the whole-tensor form | step 7a | every existing dense case, unchanged |
| Success — claim | `0 <= index < count`, `count >= 1` admits the claim form | step 7a | `olmoe-expert-claim` (plane 0) and `olmoe-expert-claim-last` (plane `n_expert - 1`), both against the corpus's own `n_expert` rather than a constant |
| Failure — half pair | index set, count `-1` (and the mirror) → `R4_5_SLICE`, detail `pair` | step 7a | `expert-claim-slice-pair`, both directions |
| Failure — zero count | `index >= 0`, `count == 0` → `R4_5_SLICE`, detail `count[0]` | step 7a | `expert-claim-slice-count` |
| Failure — out of range | `index >= count` → `R4_5_SLICE`, detail `index[<n>]` | step 7a | `expert-claim-slice-range` |
| Malformed input | A mutated 96-byte member record, written by the fixture, not by `--pack` | n/a | all four failure cells use a hand-mutated record and assert `--pack` never produces one |
| Early exit | The error document is emitted and no ggml object is created | `fail` before step 8 | `expert-claim-slice-pair` asserts `lifetime.*_created == 0` and `verdict: UNAVAILABLE` |
| Cleanup | No file is written on the error path beyond the document | unchanged | inherited from the existing error corpus |

### 4.2 `src/ggml_spike.align` — step 7b, the shape

| Cell | Contract | Implementation | Regression |
| --- | --- | --- | --- |
| Success — claim shape | `n_dims == 3`, `dim2 == slice_count`, `dim3 == 1` | step 7b | `olmoe-expert-claim` |
| Success — whole shape | `n_dims == 2`, `dim2 == 1`, `dim3 == 1` | step 7b | existing dense cases |
| Failure — 3-D, not a claim | `n_dims == 3` with `slice_index == -1` → `R4_5_SHAPE`, `n_dims[3]` | step 7b | `whole-member-3d`; this is the case section 2.4 measured, kept as a failure for the whole form |
| Failure — expert axis mismatch | claim with `dim2 != slice_count` → `R4_5_SHAPE`, `dim2[<n>]` | step 7b | `expert-claim-dim2` |
| Failure — non-unit `dim3` | claim with `dim3 != 1` → `R4_5_SHAPE`, `dim3[<n>]` | step 7b | `expert-claim-dim3` |
| Failure — bounds | `dim0`/`dim1` zero or above `MAX_DIMENSION` | unchanged | existing cases, now exercised through both forms |
| Failure — range | member range outside its block | unchanged | existing `member-outside-block` |
| Cross-check | `ggml_nbytes(A) == member.nbytes` for a claim | step 15, unchanged | **CAPABLE** — `run-ggml-spike` expert arm, all three members. It is a computation over ggml's own type table and has no hosted companion |

### 4.3 `src/ggml_spike.align` — the document and the summary

| Cell | Contract | Implementation | Regression |
| --- | --- | --- | --- |
| Construction | `schema_version` is 2 in every emitted document, error documents included | renderer | every smoke case asserts it |
| Success | `tensor.slice_index` / `slice_count` present in both forms | renderer | `olmoe-expert-claim` (`0`/`64`), any dense case (`-1`/`-1`) |
| Success — summary | `slice: <index>/<count>` for a claim, `slice: -` for a whole-tensor member | summary renderer | `olmoe-expert-claim` and a dense case, exact-line assertions against the corpus's own values |
| Failure | The two fields are present in an error document produced after step 6 | renderer | `expert-claim-dim2` |
| Early exit | An error before step 6 emits `-1`/`-1`, not garbage | field defaults | `index-out-of-range` |
| Byte identity | The stdout and file forms are byte-identical | unchanged | existing `document-forms-identical` |

### 4.4 `scripts/run-alignpack-qualification`

| Cell | Contract | Implementation | Regression |
| --- | --- | --- | --- |
| Construction | The verdict reads `by_kind`, never a path or a variable | verdict block | `qualification-skip` unit, extended with a stub document holding an `ExpertBlock` |
| Success — MoE | The eight assertions of section 3.5, then `PASS` with six numbers | verdict block | **CAPABLE** real run; hosted, a fixture document |
| Success — dense | No `ExpertBlock` entry prints the shape `N/A` and neither passes nor fails | verdict block | hosted, a fixture document from the qwen corpus |
| Failure | A pack whose `ExpertBlock` rows do not improve exits non-zero | verdict block | hosted, a mutated fixture document |
| Malformed input | A `by_kind` array missing `contiguous_block_count` is a `FAIL`, not a silent pass | key access | hosted, a fixture document |
| Early exit | All six existing `N/A` lines are unchanged and still exit 0 | unchanged | existing `qualification-skip` |
| Cleanup | The pack is removed on every exit path and the reclaimed byte count printed | unchanged | existing trap assertions |

### 4.5 `scripts/run-ggml-spike`

| Cell | Contract | Implementation | Regression |
| --- | --- | --- | --- |
| Construction | Selection resolves by `role_id`, from the pack document | selection block | **CAPABLE**; hosted, a fixture document |
| Success — dense arm | The invariants plus the keyed digest | assertion block | **CAPABLE** real run |
| Success — expert arm | The invariants plus three keyed digests, over all three members | assertion block | **CAPABLE** real run |
| Failure — no `AttentionBlock` | `FAIL`, named | selection block | hosted, a fixture document |
| Early exit — no `ExpertBlock` | one `N/A` line for the expert arm, dense arm still runs | selection block | hosted, a fixture document |
| Early exit — unknown model identity | one `N/A` line for the digest assertion only; invariants still run | digest table | hosted, a fixture document |
| Cleanup | The pack, the documents, and every `forced-*.json` are removed; the reclaimed count printed | unchanged, extended with the expert arm's documents | existing trap assertions |

### 4.6 `scripts/gguf_fixture.py` and `scripts/run-ggml-spike-smoke`

| Cell | Contract | Implementation | Regression |
| --- | --- | --- | --- |
| Construction | The smoke packs the synthetic olmoe corpus with `main --pack` and verifies it before any spike run | new smoke stage | `olmoe-pack-verify` |
| Success | `ggml-spike PACK <first ExpertBlock> 0` under the stub reaches step 10 and reports `R4_5_GGML_UNAVAILABLE`, `verdict: UNAVAILABLE`, with the correct name, dims, `nbytes`, and slice pair | steps 1–9 are ggml-free | `olmoe-expert-claim` |
| Failure | The three `R4_5_SLICE` and three `R4_5_SHAPE` claim cells above | mutated member records | as named in 4.1 and 4.2 |
| Cross-implementation | `scripts/alignpack_reader.py` reports the same `slice_index` / `slice_count` for every member of the synthetic olmoe pack | existing reader | `olmoe-reader-agreement` |
| Cleanup | The synthetic pack and every document are removed on every exit path | existing smoke discipline | `olmoe-pack-verify` asserts removal |

**The stub reaching step 10 is what makes this matrix mostly hosted.** `r4-5-external-buffer.md`
section 3.8 records that step 10 is where the stub stops and that steps 1–9 are therefore fully
reachable without ggml. Steps 7a and 7b are inside that range, so the entire new validation surface —
every code, every detail, both success forms — is testable on a runner with no ggml at all. Only the
four **CAPABLE** cells, all of which are *computations* rather than validations, need the real
library and the real model.

---

## 5. Fixtures, qualification, metrics, deferrals, handover, and risks

### 5.1 The corpus

No new corpus. `scripts/gguf_fixture.py` already generates a synthetic olmoe container for
`r1c-olmoe-moe-ir.md` section 4.1, with generator-known plane offsets; the smoke packs it and uses
it. The three `R4_5_SLICE` and three `R4_5_SHAPE` claim fixtures are produced by rewriting bytes 80–95
of one 96-byte member record in a copy of that pack — the smallest mutation that produces each
defect, and one `--pack` can never write. Each mutation asserts, as part of its own case, that the
unmutated pack passes, so a fixture that stops reproducing its defect fails rather than silently
passing.

### 5.2 Qualification

`make alignpack-qualification` and `make ggml-spike-qualification` are unchanged as targets: opt-in,
never in an aggregate, never in CI, each printing exactly one `N/A` line and exiting 0 for a missing
input. Both now discharge a MoE verdict when the model they were given has experts.

The expert arm runs **all three members** of the selected `ExpertBlock` rather than one, for the
reason in section 2.5 finding 3: member 0's interior offset is 0 and does not exercise interior
addressing, member 1 is a Q4_K plane at a non-zero interior offset, and member 2 is a Q6_K plane with
the transposed axis order at a larger one. Three runs cost about three seconds.

Measured whole-run cost on this host, which is the budget the risk section is written against:

| Step | Elapsed |
| --- | --- |
| `make alignpack-qualification`, complete | 12.5 s |
| — `main --pack` | 6.15 s (arm 5.72 s) |
| — `main --pack-verify` | 2.64 s (arm 2.47 s) |
| — `scripts/alignpack_reader.py` | 1.85 s |
| — reclaim of 4,212,193,280 bytes | included above |
| one `ggml-spike` run, dense member, warm | ~1 s wall, `pread` 4.27 ms, compute 178 µs warm mean |

These are **budget estimates, not thresholds**. Neither qualification asserts an elapsed bound and
neither fails on timing.

### 5.3 Metrics

**Primary — correctness.** Three pass/fail measurements, none of them a speed metric: every claim's
bytes are identical in both containers (3,219 of 3,219, verified twice); every `ExpertBlock` of the
pack has `range_count == 1` and `span_bytes == pack_bytes`; and every expert-claim output is
bit-identical to the same plane computed from the GGUF (`differing_elements == 0`).

**Primary — the per-expert half of R4's second gate.** `range_count`, `span_bytes`,
`contiguous_block_count`, and `amplification_ppm` for the `ExpertBlock` kind on both sides, computed
by two independent implementations. Measured: 3,072 → 1,024 ranges, 165,368,823,808 → 3,900,702,720
span bytes, 0 → 1,024 of 1,024 contiguous, 42,394,624 → 1,000,000 ppm.

**Secondary — `pread` size per expert.** `block.pack_bytes` for an `ExpertBlock` is 4,079,616 bytes
(Q6_K layers) or 3,538,944 (Q4_K layers), against a 187,310,080-byte source span for the worst one. A
diagnostic, reported by the spike as `buffer.block_pack_bytes`.

**Secondary — peak resident bytes.** Unchanged: `COPY_WINDOW_BYTES` for the pack, and
`block.pack_bytes + output_bytes + activation_bytes` for the spike, which for an `ExpertBlock` is
about 4.1 MB against the 17 MB the dense qwen attention block needed. The MoE case is the *smaller*
resident set, which is worth recording because it is the opposite of the intuition that MoE is the
expensive case.

**No performance claim.** The 42.4x is a claim about **layout**, under
`r4-alignpack-layer-major.md` section 2.6's definitions, with that section's three honest limits
inherited verbatim: no timing is asserted, it is one model on one host, and the format *guarantees*
what the source file merely happened not to have. No baseline against time to a passing patch is
established and none is claimed.

### 5.4 Coverage this model does not provide

Recorded so a later reader does not mistake a pass for wider evidence than it is.

- **Interior padding.** Zero pads on this model (section 2.2). The padding assertions stay owned by
  the synthetic corpus, and no real-model evidence for them exists.
- **Duplicated bytes.** Zero on this model; `output.weight` is present, so the tied-embedding
  duplication path is untaken. Still synthetic-only.
- **`n_expert_used <= 6`.** Not reachable: this model routes top-8. The relevant open cell is R2A's,
  not this capability's, and section 5.6 names it.
- **Six-member expert blocks, MXFP4, split expert biases, a fused `ffn_gate_up_exps`.** All
  gpt-oss-specific, all still synthetic. Section 5.5.

### 5.5 Deferred surfaces, and the honest gate

- **Expert hotness ordering.** `r4-alignpack-layer-major.md` section 5.1, **unchanged and still
  deferred.** A hotness rank is a function of an activation distribution. This capability produces a
  contiguity result, not a distribution; the distribution is roadmap item 19's output, and even when
  it exists, section 5.1's two open questions — whether hotness is global or per-workload, and how a
  stale rank is detected — remain R3's. `flags` bit 0 and `hotness_rank` stay reserved at `0` and
  `0xFFFFFFFF`, and a reader that finds otherwise still fails `R4_PACK_RESERVED`. **Packing a real
  MoE model does not discharge this and this document does not claim it does.**
- **Prefetch groups.** `r4-alignpack-layer-major.md` section 5.2, **unchanged and still deferred**,
  for the same reason and with `flags` bit 1 and `prefetch_group` still reserved. The one grouping
  available without a trace — a layer's blocks are consecutive — is still a fact the offsets already
  state.
- **The GPU expert arm.** `r4-5-external-buffer.md` section 5.4's Metal bullet, **unchanged**. This
  capability's expert arm is CPU-only and its oracle is bit-exact; a Metal arm still needs a
  tolerance oracle and a different alignment rule. The `(GPU arm)` and `(discrete VRAM)` `N/A` lines
  of `scripts/run-ggml-spike` are not touched.
- **The gpt-oss prerequisite.** `r4-alignpack-layer-major.md` section 4.5 narrows rather than
  closing. `gpt-oss-20b-mxfp4.gguf` is 12.1 GB and the roadmap records it as infeasible on this host;
  every gpt-oss-shaped cell — a six-member `ExpertBlock`, MXFP4 geometry, split expert biases, the
  fused `ffn_gate_up_exps` — stays **MOE-PREREQ** and stays synthetic. What is now discharged is the
  *MoE-generic* claim, not the gpt-oss one.
- **A slice rule in the container's own validation.** Section 3.2 argues why `R4_5_SLICE` lives in
  the arm. Making a self-inconsistent slice pair a container defect — an `R4_PACK_*` code raised by
  both `src/alignpack_read.align` and `--pack-verify` — is a change to R4's format validation, worth
  doing on its own evidence and owned by R4. Deferred, with the reason recorded rather than the
  question dropped.
- **More than one node, the R5 loader, a read-only pack open.** `r4-5-external-buffer.md` section
  5.4, unchanged.

### 5.6 Handover to roadmap item 19 — one measured finding R2A does not know

R2A's **MOE-PREREQ** cells are not this capability's, but a capture taken while probing the model
produced a finding that blocks the design roadmap item 19 records, and withholding it until that
branch discovers it would be a waste. It is recorded here as evidence, not as a repair.

```text
$ llama-eval-callback -m $MODEL -p "Write a function" -n 1 -t 4 > transcript.txt
$ ./main --expert-trace transcript.txt trace.json
status: ERROR   graphs: 1   layers: 16   moe: YES   experts: 64   experts used: 8
error: R2_TOKEN_COUNT   detail: ffn_moe_topk-15
```

**llama.cpp prunes the final layer to the output tokens, so the last layer's `ffn_moe_topk`
legitimately carries fewer tokens than `embd`.** Measured on this transcript: `embd` is
`{2048, 3, 1, 1}` and `ffn_moe_topk-0` through `ffn_moe_topk-14` are `{8, 3, 1, 1}`, but
`ffn_moe_topk-15` is `{8, 1, 1, 1}` and so are `ffn_inp-15`, `ffn_moe_out-15`, and `l_out-15`, while
their layer-14 counterparts are all 3. R2A's per-graph invariant — `R2_TOKEN_COUNT` when "`embd` and
an `ffn_moe_topk` in one graph disagree" on `n_tokens` (section 2.6, and `src/expert_trace.align`
around line 1297) — treats a real graph shape as a defect. **Every capture with more than one token
fails**, and roadmap item 19's design is "N≈40 prompts of at most 6 tokens each".

A single-token capture parses clean, which localizes the fault to the invariant and not to the
grammar, the segmentation, or the model:

```text
$ llama-eval-callback -m $MODEL -p "x" -n 1 -t 4 > 1tok.txt
$ ./main --expert-trace 1tok.txt 1tok.json
status: OK   graphs: 1   layers: 16   moe: YES   experts: 64   experts used: 8   selections: 96
shape_class: "moe-ffn"   n_expert_source: "ffn_moe_probs"   slots_truncated: true
```

Two secondary observations for the same owner:

- `slots_truncated: true` on real data, with the observed slot ids exactly `{0, 1, 2, 5, 6, 7}` —
  precisely what R2A's finding 6 predicted for `n_expert_used = 8`. 96 selections is
  `16 layers × 6 slots`, not `16 × 8`. R2A section 5.2's `R2c` patch remains the fix.
- The value block's `sum = ` line covers **all eight** slots even though only six ids are printed:
  layer 0's printed ids sum to 160 while the block reports `sum = 219.000000`. That is an integrity
  cross-check on the six that were printed; it does not recover the two that were not, since one
  equation cannot determine two unknowns, and it should not be presented as a way around finding 6.
- R2A's *axis-0 full print* cell (`ne <= 6` on axis 0) stays open: this model routes top-8, so the
  branch is still unreached on real data.

### 5.7 Risks

| Risk | Size | Control |
| --- | --- | --- |
| **Disk.** Each qualification writes a 4,212,193,280-byte pack | The existing guard requires `model_size + 1 GiB` = 5,287,254,016 bytes; measured free was 13,692,309,504 | Unchanged: `pwd -P` resolution, refusal of a destination inside the work tree, refusal of an occupied destination before the trap, the free-space check, and reclaim on every exit path including signals. Measured: 4,212,193,280 bytes reclaimed, then asserted gone |
| **Two packs at once.** `alignpack-qualification` and `ggml-spike-qualification` each pack the same model, and both running concurrently need 8.4 GB | Would have fit today, will not on a smaller margin | Neither is in an aggregate and neither is in CI, so nothing schedules them together. Recorded here rather than guarded: adding a lock would be a permanent gate for a hazard with no recurring failure class |
| **Runtime.** The MoE model is packed twice across the two qualifications | 12.5 s + ~15 s | Both remain opt-in. No aggregate gains either |
| **Golden digest fragility.** Four exact `sha256` values, correct for this model, member, activation, ggml version, and CPU backend | A ggml kernel change moves them | Keyed by `header_region_sha256` so an unknown model degrades to an `N/A` for the digest only; the invariants, including the bit-exact GGUF reference, still run and still carry the gate. The failure message says the kernel or the model changed |
| **Measurement.** 42.4x is a layout number, not a throughput number | The headline risk of over-reading the result | Section 5.3 inherits section 2.6's three limits verbatim, and no elapsed number in this document is a threshold |
| **Coverage.** Zero padding and zero duplication on this model | Two format paths get no real-model evidence | Named in section 5.4; both stay owned by the synthetic corpus rather than being claimed as covered |
| **Schema bump.** `R4_5_EXTERNAL_BUFFER` 1 → 2 | Any consumer of the R4.5 document | There is exactly one consumer, `scripts/run-ggml-spike`, and it changes in the same commit. Recorded because the count being one is what makes the bump cheap, not because it is zero |
