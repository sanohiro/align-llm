# Session handoff

Read `CLAUDE.md` first. GitHub owns transient pull-request checks, reviews, and attestations; this
file records durable project state.

## Active capability: R5A-DENSE-LAYER-FORWARD — one Qwen2 dense layer computed from an Align-owned alignpack (2026-08-27)

- Branch `agent/r5a-dense-layer-forward`, ledger commit `01e8df4` ("docs: add R5A dense layer
  forward design ledger"), continuing from R4.5-EXTERNAL-BUFFER-SPIKE (branch
  `agent/r4-5-external-buffer` at `ecce870`, awaiting publication above). The authoritative design
  ledger is `docs/specs/r5a-dense-layer-forward.md`.
- **Status: implementation complete in the working tree.** R5A is stage 2 of `docs/specs/roadmap.md`
  section R5's three-stage gate — a single dense layer, CPU only — computed by ggml over Qwen2
  weights that live in Align-owned buffers, checked against `llama-eval-callback`'s own numbers for
  the same six tokens. Design is complete with probe evidence (below), the arm
  (`src/layer_qwen2.align`, `src/layer_forward.align`, the shim wrappers) is implemented and
  committed to the working tree, and both owner and named-qualification verification have passed.
  Next action is review.
- **Owner verification, latest run.** `check` (29 units), `build`, `ggml-spike` (both the default
  stub and the real linked library), `ggml-spike-smoke`, `layer-forward-smoke` (run three times,
  identical results each time: eight shim builds plus the 48-case golden corpus, 24 of 26 error
  codes reached and both oracles exercised, matching section 7.6's own count), `alignpack-smoke`,
  `gate-topology-check`, `format-check`, and `fmt` idempotent on a second run — all pass.
- **Named qualification, against `qwen2.5-coder-7b-instruct-q4_k_m.gguf`, layer 0, tokens
  `750,912,2877,11,293,1648`** (`docs/specs/r5a-dense-layer-forward.md` section 7.7):
  - self-reference oracle: **IDENTICAL**, 20 of 20 dumped node tensors byte-identical;
  - transcript oracle: **PASS**, 18 of 18 nodes, 1,116 sampled elements, `max |Δ| == 0`
    ten-thousandths;
  - `l_out` sha256 `f601bf855d32ffa8faca2f50d98b2344df44e6b8aeb9b1e46b0d74b58685bdc6`;
  - compute **12.970 ms** (warm mean of 5), pread **55.2 ms**;
  - weight window **149,139,456 B**, activation **2,453,376 B**, 32 graph nodes;
  - lifetime counters balanced (buffers 3/3, contexts 5/5, backends 1/1, gallocrs 2/2, released
    true); the qualification's own temporary alignpack is deleted on exit (`scripts/run-layer-forward`
    writes it under a work directory removed by an `EXIT`/`HUP`/`INT`/`TERM` trap).
- **Probe evidence (ledger section 2), gathered before section 3's contract was written.**
  - Transcript (tolerance) oracle: 18 oracle nodes, 1,116 sampled elements, worst `max|Δ|` **5.0e-5**
    against `llama-eval-callback`, which is the instrument's own `%12.4f` print-rounding bound —
    every sampled element agrees to the last digit printed.
  - Re-accumulating in sequential f32 order (matching the instrument's own accumulation) makes
    `norm-0`, `Qcur-0/ROPE`, and `kq-0` **bit-identical** to the transcript's printed sums; worst
    residual 1.5e-6 relative (`ffn_gate-0`).
  - Bit-exact self-reference oracle: the same graph, Align-owned weights vs. ggml-allocated weights,
    **20 of 20** dumped node tensors byte-identical (the 18 oracle nodes plus `kq-0` and
    `kq_soft_max-0`); two consecutive external-arm runs also byte-identical (deterministic on this
    host at this thread count).
  - Compute (microbenchmark B): **15.5 ms** median (15.3-16.6 ms range) for one dense layer, six
    tokens, 32 graph nodes, warm.
  - The embedding member must be row-gathered, not read whole: whole-member window
    455,688,192 B / 87.0 ms read vs. row-gathered window **149,139,456 B** / 19.5-20.9 ms read, for a
    byte-identical answer.
  - The oracle instrument's default graph is not the one R5A computes; the qualification's flags are
    contractual: `-fa off -ctk f32 -ctv f32 -nr -c 512` (disables flash attention/f16 KV cache/CPU
    weight repacking, keeps everything on CPU). The transcript's first node is `embd`, not the
    plan's assumed `inp_embd`; the attention output-projection node has no stable name across builds
    (`node_31` under `-fa off`, `node_26` under flash attention) and is matched by its source weight
    name (`blk.L.attn_output.weight`) instead.
  - FFI surface verified at the pin: `f32` crosses by value in both directions (a nine-argument
    mixed-scalar probe) and an unsuffixed float literal coerces at an `f32` parameter with no cast —
    the design nonetheless passes every scalar as an `i32` bit pattern for GGUF bit-fidelity, not
    because `f32` doesn't work. `bool` is still refused, so `ggml_gallocr_reserve` and
    `ggml_gallocr_alloc_graph` needed shim wrappers, now shipped. `raw` cannot be a `layout(C)` struct field
    (already known) **or an array element** (new), which is why the 32-node graph's `ggml_tensor *`
    handles live in an Align-owned node-slot store addressed by `i64` index rather than in any Align
    aggregate.
- **Align capability requests.** Design believed **no new request** was needed — ledger section 5.5
  verifies every gap the design's probes hit was already recorded in `docs/align-requests.md` — and
  implementation confirmed that, but also hit two further gaps of its own (ledger section 6,
  corrections C8 and C9), now **Requests 36 and 37, both PROPOSED**. Design-time work added new
  client evidence to Request 34 (`raw` refused as an array element too, the reason the node-slot
  store exists; now citable at `src/layer_qwen2.align:13-16,24-38`) and Request 32 (two more
  `bool`-typed ggml entry points needing wrappers, now shipped at `src/ggml_ffi.align:744-754` and
  `scripts/ggml_shim.c:1069-1090`, plus the positive `f32` measurement above), with no-text-change
  client evidence to Requests 21 and 35, and a shipped citation strengthening Request 33 (the
  per-member alignment compensation now paid thirteen times per run). Request 36: an owned
  `array<i64>` struct field cannot be replaced in place and a nested struct field cannot be moved out
  of its parent, so `src/layer_forward.align`'s document columns live in eight single-assignment
  records instead of the one `Outcome` the design wrote down. Request 37: per-function check time is
  superlinear in body length and a `match` on a `Result` inside a loop costs roughly 45x the same
  loop with `?`, so the arm is split into fourteen functions purely to keep `make check` fast. Both
  are non-blocking. See `docs/align-requests.md` for the full text.
- **Next actions, in order.**
  1. Two independent reviews (source; specification/register/handoff/runners), consolidated repair,
     rerun of affected owner verification.
  2. At publication, run **`make ci`**, not only the narrower classifier path — adding
     `layer-forward-smoke` to `HOSTED_CHECK_TARGETS` changes aggregate membership, which is one of
     `CLAUDE.md`'s explicit triggers for the full integration graph.
  3. Exact-head preflight (`python3 scripts/pre-pr`), including the DinD-capable installed profile
     check; do not substitute a Docker skip or an ambient `DOCKER_HOST` endpoint.
  4. Publish the English pull request against `main`, once R4 (PR #125) and R4.5 (PR TBD-PR) are
     both ahead of it in the merge chain or this branch is rebased onto their merged result.
- **Two pending user decisions, carried forward verbatim.**
  1. Carried forward from R1B: whether to download `gpt-oss-20b-mxfp4.gguf` (12.1 GB) to run the
     gpt-oss `model-ir-parity` qualification; until decided that qualification stays the documented
     `N/A`.
  2. Carried forward from R2A: whether to download a small MoE GGUF (1-4 GB) so
     `scripts/run-expert-trace-parity` can exercise the `moe: true` path against a real MoE
     transcript; until decided the R2 roadmap gate stays open on dense-only smoke evidence, R4's own
     MoE case stays synthetic-only, and R3 stays blocked (below). Note: a small MoE GGUF chosen for
     size will most likely not be gpt-oss architecture, so R3's real measurement would also need a
     new R1C frontend for whatever architecture that model uses, not just the download itself.
- **R3 (Cache Simulator) is blocked on pending decision 2 above.** R3's gate
  ("対象ハードウェア条件で、baselineより有効なpolicyを特定できること", `docs/specs/roadmap.md` section
  R3) needs a real MoE activation trace and a cache-policy comparison against it; R2A's design ledger
  already records that no such trace exists on this host. Resume condition: the small-MoE-GGUF
  decision is made, the model's architecture is identified, an R1C frontend is built if that
  architecture is not already `qwen2`/`gpt-oss`, and R2A's `moe: true` path is exercised against a
  real transcript from it. Independent work that may continue: R4's publication, R4.5's publication
  once R4 merges, R5A's implementation (its stage-2 dense CPU gate needs no MoE trace), and the next
  eligible roadmap capability.

## Awaiting publication: R4.5-EXTERNAL-BUFFER-SPIKE — computing a ggml matmul over an Align-owned quantized buffer (2026-08-27)

- Branch `agent/r4-5-external-buffer`, **rebased onto the merged R4-ALIGNPACK-LAYER-MAJOR work**:
  it now sits directly on `main` at `991eab1` (the PR #125 merge of R4 head `a7e72dc`). The
  authoritative design ledger is `docs/specs/r4-5-external-buffer.md`, committed at `7bd7d0d`
  ("docs: add R4.5 external buffer spike design ledger").
- **Status: implemented, verified, reviewed twice, both review repairs committed, and rebased onto
  the merged R4; awaiting publication.** The branch is five commits on `991eab1`: the design ledger
  `7bd7d0d`, the implementation `de86c58` ("feat: compute a ggml matmul over an Align-owned
  alignpack block"), the consolidated repair for both reviewers' findings `bf7f10b` ("fix: close
  external buffer spike review findings"), the final-review repair `049a5cc` ("docs: close external
  buffer spike final review findings"), and the reconciliation commit that records this rebase.
  Nothing is intentionally uncommitted. The rebase carried one content conflict, resolved keeping
  both sides: this file's R4 status bullet, where `main`'s final R4 content (the re-recorded
  baseline chain and the two review repairs) supersedes the branch's older "publication in
  progress" text, while R4.5's own section is kept intact.
- **What is on the branch.** `src/alignpack_read.align`, `src/ggml_ffi.align`, `src/ggml_spike.align`,
  `scripts/ggml_shim.c`, `scripts/ggml_shim_stub.c`, `scripts/build-ggml-shim`,
  `scripts/ggml_spike_fixture.py`, `scripts/run-ggml-spike-smoke`, `scripts/run-ggml-spike`, and
  `scripts/ggml-spike-golden.jsonl`; `Makefile`, `scripts/check-gate-topology`, and `.gitignore` are
  wired for the `ggml-spike` / `ggml-spike-smoke` / `ggml-spike-qualification` targets.
  `docs/specs/r4-5-external-buffer.md` section 6 records twenty-two implementation-forced
  corrections (C1-C23) against the design — C1-C13 from the implementation, C14-C21 from the review,
  and C22-C23 from preflight; section 7 is the delivered-surface record.
- **Probe evidence (ledger section 2), gathered before the design was written.**
  - Pointer identity: `ggml_get_data(A)` equals the Align `weights` buffer's base plus the member's
    own interior offset, exactly `14336` bytes (`pack_offset - block.pack_offset`), and the output
    tensor is likewise Align-owned — no silent copy on either side (probe 2b).
  - Bit-identity vs. GGUF: a real Q4_K tensor (`blk.0.attn_q.weight`, Qwen2.5-Coder-7B Q4_K_M,
    3584x3584, 7,225,344 bytes) computed from pack bytes is bit-identical to the same tensor read
    from the original GGUF into ggml-owned memory — `differing_elements = 0` of 14,336 output f32.
  - Compute cost: 0.41-0.55 ms per `mul_mat` call (mean of five, after one mandatory warm-up call
    that absorbs ~4.6 ms of thread-pool spin-up); external vs. internal (Align-owned vs.
    ggml-owned weights) showed no measurable penalty, 0.427 ms vs. 0.423 ms.
  - GPU half: Metal accepted the same host pointer with no copy (`base == ptr`, this host's unified
    memory) and computed successfully, but its output was not bit-identical to the CPU's — max
    absolute difference 0.029 across all 14,336 elements. A GPU arm therefore needs a
    tolerance-based oracle rather than the bit-exact one this design ships, so section 5.4 defers
    it to R5 instead of shipping two acceptance rules under one name.
- **Owner verification (`docs/specs/r4-5-external-buffer.md` section 7.2), all passing.**
  `gmake check` — `ok: checked 29 unit(s) per-unit`; `gmake build` — links no ggml on the link line;
  `gmake ggml-spike` builds both against the stub (`ALIGN_LLM_GGML_INCLUDE` unset) and against the
  real ggml headers/libs; `gmake ggml-spike-smoke` — 7 no-document cases, **33** documented cases,
  reader parity, shared shim contract, and lifetime all PASS, consecutive runs identical;
  `gmake alignpack-smoke`, `gmake gguf-smoke`, `gmake model-ir-smoke`, `gmake expert-trace-smoke` —
  unchanged PASS; `gmake gate-topology-check` — PASS; `gmake format-check` / `gmake fmt` — clean,
  `fmt` a no-op on the three new modules; `git diff --check` — clean.
- **Qualification (`gmake ggml-spike-qualification`, section 7.3), run twice before the review repair
  and three times after it, end to end on the real model** (`qwen2.5-coder-7b-instruct-q4_k_m.gguf`, block 1
  / member 1, `blk.0.attn_q.weight`, Q4_K, 3584x3584): `verdict EXTERNAL`;
  `buffer.interior_offset == buffer.tensor_data_offset == 14336` (the no-silent-copy clause,
  discharged) on every run — after the repair the offset is measured from block byte 0, so the value
  is unchanged by the compensation; `output.sha256` reproduced
  `2ccc7dc778108df3b626128895347f203795a2d82b502805806fb8472457e044` on every run (bit-identical to
  the section 2.3 probe digest); `reference.verdict IDENTICAL`, `differing_elements 0` of 14,336 on
  every run; `compute.backend_name CPU`; post-repair compute 435,075 ns over Align-owned memory vs.
  584,292 ns over ggml-owned memory on the final run, pre-repair 550,308 vs. 560,792 ns (no penalty
  for external memory — the roadmap's actual question); pread 6,829,084 ns for 17,020,928 B
  post-repair against 5,080,833 ns before, the difference being the one copy into the
  alignment-compensated window;
  `base_alignment 0 / weights_pad 64 / output_base_alignment 0 / output_pad 0`; lifetime counts
  balanced (buffers 4/4, contexts 2/2, backends 1/1, `released_before_owner_scope_end true`), no abort
  at `exit`; forced failures `init -> R4_5_GGML_INIT`, `compute -> R4_5_COMPUTE`,
  `reference -> R4_5_REFERENCE_MISMATCH`; the temporary pack (4,677,222,400 bytes) was removed and
  reclaimed on every run, with no file left behind.
- **Requests 32-35 in `docs/align-requests.md`, all PROPOSED and non-blocking.** Request 32, FFI v1
  by-value struct ABI (AAPCS64 and SysV MEMORY class) and `bool` FFI type: `ggml_init`'s 24-byte-by-
  value struct and `ggml_tallocr_new`'s by-value return are unreachable from Align by any route
  (by-value rejected at codegen; by-pointer impossible because `layout(C)` cannot hold a `raw`
  field), forcing the C shim `scripts/ggml_shim.c`. Request 33, aligned heap allocation:
  `ggml_backend_cpu_buffer_from_ptr` aborts on a misaligned pointer, but neither `buffer(n)` nor
  `raw.alloc(n)` guarantees any alignment; its evidence is now strengthened with correction C9's
  measurement that the same 192-byte `buffer` came back 32-aligned on one run and 16-aligned on the
  next, and with correction C14's, that a rule consulting that base refused a legitimate member at
  interior offset 0 on 20 of 20 runs. The shipped arm compensates on **both** device-visible windows
  by over-reserving `MAX_TENSOR_ALIGNMENT = 64` bytes and handing ggml an aligned interior range;
  the price, and the request's concrete cost, is that over-reservation plus one copy of each block
  into its aligned window. Request 34 (new),
  `Result` ok payloads beyond scalars (`raw`, `buffer`, records): a `Result` ok payload must be a
  scalar at this pin — verified directly against the pinned compiler — so `src/ggml_ffi.align`'s
  constructors return a bare `raw` with a null sentinel and `src/ggml_spike.align`'s reference reader
  threads bytes out through a `borrow mut buffer` parameter instead of an owned return; a plain
  struct cannot hold a `raw` field either, closing off the record workaround. Request 35 (new),
  observable `buffer` capacity and allocation failure: `buffer(n)` is an advisory reservation that
  never fails and has no `.cap()` accessor, so `R4_WINDOW_UNAVAILABLE` (R0) and R4.5's
  window-adjacent codes are untestable guards for an observable consequence rather than the
  reservation itself — R0, R4, and R4.5 each reached the same conclusion independently. The header
  status line in `docs/align-requests.md` now reads "21–35 are PROPOSED".
- **Review envelope.** Two complementary independent reviewers covered explicitly disjoint risks of
  the candidate at `6b19163`, which the rebase onto `991eab1` replayed as `de86c58`: **A** the Align
  source, **B** the specification, register, handoff,
  runners, and `Makefile`. A requested changes with 2 major, 2 minor, and 2 nit findings; B requested
  changes with 1 high, 3 medium, and 6 low. **Every finding was accepted** and all were repaired as
  one consolidated commit on top of `6b19163`, replayed as `bf7f10b`; the contract changes are ledger section 6.1 rows
  C14-C21, each with its case in section 6.2. A's and B's highest findings were the **same root
  cause**: the alignment gate `(base_alignment + interior_offset) % tensor_alignment` consulted the
  Align allocator's base, so a legal member at interior offset 0 was refused `R4_5_ALIGNMENT` on 20
  of 20 runs on this host while `weights_pad` compensated nothing, and two goldens
  (`spike-block-zero`, `spike-misaligned-member`) were recordings of an allocator accident. The arm
  now over-reserves the weights window too and reads the block in **behind** `weights_pad` through a
  new `alignpack_read.read_append`, so block byte 0 lands on a boundary and the gate is the
  container's own property, `interior_offset % tensor_alignment != 0`. The other substantive repairs:
  a short, empty, or wrong reference file reported `R4_WINDOW_UNAVAILABLE` instead of
  `R4_5_SOURCE_UNREADABLE` (`read_reference` now bounds the range against `f.len()` before the
  `pread`, with three new fixtures); `output.element_count` was non-zero on an `UNAVAILABLE`
  document; `tensor.blck_size` published the `-3` status sentinel as a size; `STATUS_BOUNDS` mapped
  to `R4_5_GGML_INIT` rather than `R4_5_SHAPE`; section 6.2 cited `make check` for five cells over
  modules `make check` never compiles; `docs/align-development.md` had no R4.5 section and
  `docs/specs/roadmap.md` no R4.5 forward-order item or gate-clause pointer. A final review of the
  repair delta at `ddc9bc6` (replayed as `bf7f10b`) returned **approve** with 3 low/nit findings, all documentation: the
  section 6 correction table listed rows C1-C9, C14-C21, C10-C13 instead of running C1-C21
  monotonically; a `docs/align-requests.md` blockquote line ran 136 characters against the
  surrounding ~100-column width; and `scripts/run-ggml-spike-smoke` and `docs/align-requests.md`
  both described `weights_pad` as alternating between 16 and 48, which is not reproducible
  (measured `{16, 32}` under the stub and `{32, 48, 64}` under the real shim) rather than varying
  run to run within `[1, 64]`. All three are repaired in `049a5cc`. The rebase onto `991eab1` is a
  replay of the same trees: `git diff` between each pre-rebase commit and its replacement is empty
  except for this file, so no reviewed R4.5 risk changed across it, and
  `docs/specs/r4-5-external-buffer.md` keeps the pre-rebase hashes as the identities its
  measurements were actually taken at.
- **Preflight, first attempt, and the repair it forced.** `python3 scripts/pre-pr --owner-test
  ggml-spike -- make ggml-spike-smoke gate-topology-check` at `77acbb1` passed the `ggml-spike`
  owner (7.5 s), `hosted-checks` (381.6 s), and `fresh-focused` (21.0 s), and failed
  `fresh-installed` in the worker aggregate after 1,194 s. The worker's output is suppressed unless
  `ALIGN_LLM_AGGREGATE_DIAGNOSTIC=1`; re-running only that phase with it showed
  `./scripts/run-ggml-spike-smoke: line 55: sort: command not found` and
  `make[1]: *** [Makefile:179: ggml-spike-smoke] Error 127`. The fresh worker image ships a curated
  tool set (`image/fresh/Dockerfile`) with neither `sort` nor `uname`, and R4.5 is the first
  capability whose hosted member used them. Repaired as ledger correction C22: the two static scans
  sort through a `python3` helper, and `scripts/build-ggml-shim` selects its suffix and
  install-name/soname flag from bash's `OSTYPE`. Verified by running the owner with `PATH`
  restricted to exactly that tool set — PASS — and unchanged on macOS.
  The rerun at `7a2be4e` then failed the same phase again, at 1,306 s instead of 1,194 s and this
  time with **no** captured child output even under the diagnostic, because every check inside the
  aggregate had passed: the fresh worker lists the `/workspace` overlay's upper directory after the
  aggregate exits and fails unless the only entry is `main`, and the owner had left `build/lib/` and
  a `ggml-spike` binary there. Repaired as ledger correction C23: the owner builds the shim and the
  executable into its own `mktemp -d` tree (`scripts/build-ggml-shim` gained
  `ALIGN_LLM_GGML_SHIM_DIR`; `make ggml-spike` still writes `build/lib` and `./ggml-spike` for
  developers). Verified with `git status --porcelain --ignored` before and after a run — the work
  tree is unchanged — and with the restricted-`PATH` owner run, still PASS.
- **Baseline chain**: `45cdc55` -> `8b3b161` -> `eece7a1` (source -> oracle -> finalization),
  identity-bound and re-recorded on Linux (aarch64, kernel 6.11.11-linuxkit, Python 3.12.3) after
  the rebase onto the merged R4. **Exactly one** of the twenty recorded artifacts changed against
  the R4 chain — `Makefile`, which carries the `ggml-spike` / `ggml-spike-smoke` /
  `ggml-spike-qualification` targets. `src/main.align`, the other artifact R4 moved, is **unchanged**
  by R4.5, and the twenty paths are identical with every other hash unchanged.
  `make baseline-check` on Linux: PASS, ending `baseline chain: PASS`.
- **Next actions, in order.**
  1. Exact-head preflight —
     `python3 scripts/pre-pr --owner-test ggml-spike -- make ggml-spike-smoke gate-topology-check`.
     Do not replace the required installed profile with a Docker skip or an ambient `DOCKER_HOST`
     endpoint.
  2. Publish the English pull request against `main` at `991eab1` or later, recording the
     qualification numbers above, the baseline chain, the review envelope, and the finding
     dispositions.
- **Two pending user decisions, carried forward verbatim.**
  1. Carried forward from R1B: whether to download `gpt-oss-20b-mxfp4.gguf` (12.1 GB) to run the
     gpt-oss `model-ir-parity` qualification; until decided that qualification stays the documented
     `N/A`.
  2. Carried forward from R2A: whether to download a small MoE GGUF (1-4 GB) so
     `scripts/run-expert-trace-parity` can exercise the `moe: true` path against a real MoE
     transcript; until decided the R2 roadmap gate stays open on dense-only smoke evidence, R4's own
     MoE case stays synthetic-only (design ledger section 1.4, item 3), and R3 stays blocked (below).
     Note: a small MoE GGUF chosen for size will most likely not be gpt-oss architecture, so R3's
     real measurement would also need a new R1C frontend for whatever architecture that model uses,
     not just the download itself.
- **R3 (Cache Simulator) is blocked on pending decision 2 above.** R3's gate
  ("対象ハードウェア条件で、baselineより有効なpolicyを特定できること", `docs/specs/roadmap.md` section
  R3) needs a real MoE activation trace and a cache-policy comparison against it; R2A's design ledger
  already records that no such trace exists on this host. Resume condition: the small-MoE-GGUF
  decision is made, the model's architecture is identified, an R1C frontend is built if that
  architecture is not already `qwen2`/`gpt-oss`, and R2A's `moe: true` path is exercised against a
  real transcript from it. Independent work that may continue: R4.5's publication (its DRAM half
  needs no MoE trace) and the next eligible roadmap capability.


## Merged checkpoint: R4-ALIGNPACK-LAYER-MAJOR — alignpack v1 container, layer-major layout, and verifier (2026-08-27)

- **Status: merged.** R4-ALIGNPACK-LAYER-MAJOR merged as align-llm PR #125, head `a7e72dc`, merge
  commit `991eab1` on `main`. Required checks passed before merge; GitHub owns that transient
  check and review metadata.
- Branch was `agent/r4-alignpack-layer-major`, rebased onto the merged R2A-EXPERT-TRACE-CAPTURE
  work and therefore based on `main` at `b8e1cb6` (the PR #124 merge of R2A head `ab5f7d8`), which
  itself continued the merged R1B-GPTOSS-MOE-IR chain (PR #123, head `3bf5c9c`, merge `d8d4ef6`)
  onto `main` at `08492dc`. The authoritative design ledger is
  `docs/specs/r4-alignpack-layer-major.md`, committed at `d678485`. The branch was eight commits on
  `b8e1cb6`: the design ledger `d678485`, the implementation `4bc2b86` ("feat: pack GGUF models
  into layer-major alignpack containers"), the consolidated repair for both reviewers' findings
  `ab7d4a6`, the reconciliation commit `cb116f4`, the final-review repair `de5e12d`, the baseline
  chain `47ba089` and `cfd15e8` with its record `a4d9be6`, and the preflight repair `a7e72dc`
  ("fix: compile the lowered-limit entry point once", which compiles the lowered-limit entry point
  a single time instead of once per negative source).
- **What it delivers.** `main --pack MODEL.gguf OUT.alignpack [DOC.json]` and
  `main --pack-verify MODEL.gguf PACK.alignpack [DOC.json]`: a byte-exact streaming rewrite of one
  GGUF file into the alignpack v1 container (magic, versioned 128-byte header, name stream, 64-byte
  block records, 96-byte member records, 128-byte source-identity record, and a layer-major payload
  copied verbatim in Model IR block order), plus a verifier that re-reads **both** containers and
  compares every claimed byte rather than trusting the writer's bookkeeping. Two `schema_version: 1`
  documents, `R4_ALIGNPACK` and `R4_ALIGNPACK_VERIFY`. `src/alignpack.align` imports no frontend: the
  architecture dispatch stays in `src/main.align` and the packer receives a `BlockPlan`. Out of scope
  for v1 (ledger section 1.3): expert hotness ordering, prefetch groups, metadata rewrite, tokenizer,
  in-place update or append, compression, mmap, and any runtime/loader/durability claim.
- **Gate result, from one real-model qualification run** (`ALIGN_LLM_GGUF_MODEL` =
  Qwen2.5-Coder-7B Q4_K_M, 4,683,073,536 bytes). Both dischargeable halves are met on the dense case:
  - identity **PASS** — `verdict: identical`, no first mismatch, header-region digest matches;
  - sequential read **PASS** — src **89 ranges / 11,130,544,128 span / 2,379,786 ppm** to pack
    **58 ranges / 4,677,120,000 span / 1,000,000 ppm exactly**, contiguous blocks **27/58 → 58/58**;
    per kind, src `WeightBlock` 2,039,993 ppm, `AttentionBlock` 10,922,100 ppm, `MlpBlock`
    1,291,478 ppm, all three 1,000,000 ppm in the pack;
  - pack 4,677,222,400 bytes; layout payload 4,677,120,000, interior padding 57,344, duplicated 0;
    `--pack` 6.74 s wall (6.72 s in-arm), 1,387 `pread`s, 1,420 `pwrite`s; `--pack-verify` 3.12 s
    wall (3.05 s in-arm), 9,360,295,936 bytes read, 4,677,120,000 compared; peak window 5,953,536;
  - the pack was **removed on exit** and 4,677,222,400 bytes reported reclaimed; the model's size and
    mtime were unchanged.
  - MoE half: **N/A** — no gpt-oss GGUF on this host, closed synthetically only (ledger section 4.5).
- **Verification, all at the unchanged pin `4b515f8d` on this working tree.**
  - `gmake check`: **29 units, PASS**. `gmake build`: PASS.
  - `gmake alignpack-smoke`: **20 positive fixtures, 106 negative sources, 14,996 assertions, PASS**.
  - `ALIGN_LLM_ALIGNPACK_ENOSPC=1 scripts/run-alignpack-smoke`: 15,007 assertions, PASS, including
    `write-to-full-filesystem PASS (Code@13312)` and
    `qualification-skip insufficient-free-space PASS`.
  - `gmake model-ir-smoke`: PASS (49 qwen, 31 gpt-oss, 62 R0 fixtures), **and** a direct before/after
    comparison of all **142** fixture `R1_MODEL_IR` documents across the `derive_status` extraction:
    **byte-identical, 0 differing**.
  - `gmake gguf-smoke`: PASS (62 fixtures). `gmake expert-trace-smoke`: PASS (95 fixtures).
  - `gmake gate-topology-check`: PASS. `gmake format-check`: PASS. `gmake fmt`: no diff.
    `git diff --check`: clean.
  - Resident-set measurement on a synthetic 16,514-block / 99,139-member gpt-oss container:
    `--pack` 456,015,872 → **419,037,184** bytes and `--pack-verify` 839,532,544 → **802,340,864**
    after the packing arms stopped rendering an `R1_MODEL_IR` document they discarded.
- **Review envelope.** Two complementary independent reviewers covered explicitly disjoint risks of
  the candidate at `ded98cb`, which the rebase onto `b8e1cb6` replayed as `4bc2b86`: **A** the Align
  source, **B** the specification, register, handoff, and runners. A approved with 3 low-to-medium
  findings, 2 low, 2 informational, and 1 observation; B requested changes with 4 medium and 5 low.
  **The two commits are not the same tree.** `git diff ded98cb 4bc2b86` touches 10 files —
  `HANDOFF.md`, `docs/align-development.md`, `docs/align-requests.md`, `docs/specs/r2a-expert-trace.md`,
  `eval/baselines/coding-v1-reference.json`, `eval/expected/coding-v1-reference-oracle.json`,
  `eval/expected/coding-v1-reference.sha256`, `scripts/run-expert-trace-parity`,
  `scripts/run-expert-trace-smoke`, and `src/main.align` — and every one of those deltas is R2A-owned
  upstream content that arrived with `b8e1cb6`, not R4 content. No file R4 introduces and no R4 risk
  either reviewer examined changed across the rebase. **Every finding was accepted** and all were
  repaired as one consolidated repair on top of `ded98cb`. The substantive ones are recorded as ledger section
  6.8: `--pack-verify` accepted a pack extended with trailing payload bytes whose `total_bytes` and
  `payload_bytes` had been raised to match (step 17 now cross-checks the header's whole region
  geometry against the planner, `R4_PACK_HEADER` naming the field); the section 2.9 allocation claim
  was false for a large model (peak is the rendered document, not the copy windows, and
  `peak_window_bytes` is not the resident set); both packing arms rendered and discarded an
  `R1_MODEL_IR` document (`model_ir.derive_status` now runs the ordered checks and renders nothing);
  the qualification refused an occupied destination **after** installing the reclaim trap, so it
  deleted the artifact it declined to overwrite — found by the new `qualification-skip` unit on its
  first run; and ledger section 7.2's claim that a loopback image needs root on darwin was simply
  wrong, so `write-to-full-filesystem` now ships opt-in behind `ALIGN_LLM_ALIGNPACK_ENOSPC=1`.
- **Final review of the repair: one fresh comprehensive review at `cb116f4` returned approve**, with
  3 low findings and 1 informational one. All four were accepted and repaired in the following
  commit ("docs: close alignpack final review findings"); none changed a shipped behaviour of
  `--pack` or `--pack-verify`, so no further full review was required. Recorded as ledger section
  6.9: the qualification's `reclaim` removed `alignpack.json` and `alignpack-verify.json`
  unconditionally while the refusal covered only the pack, so a caller's document in the temporary
  directory was deleted (the refusal now covers all three paths, and `reclaim` therefore removes
  only paths the run could have created); that refusal used `-e`, which follows a link, so a
  **dangling** symlink at the destination was invisible to it while `--pack` followed it and wrote
  the container at the link's target and `reclaim` then unlinked the symlink and reported bytes
  reclaimed with the payload still on disk (the test is now `-e` **or** `-L`); section 2.8 did not
  state `--pack`'s symlink behaviour at all (it now does, in both directions, with Request 30 named
  as the fix and a `dest-symlink` smoke case pinning current behaviour); and section 4.4 did not say
  that an already-contiguous container reports `(sequential read): FAIL` because no third "no
  improvement available" outcome exists at v1 (documented, with the reason the third outcome is
  deferred rather than added).
- **Align capability requests.** R4 added Requests 29 (incremental `sha256` init/update/final), 30
  (`fs.create_rw_exclusive`), and 31 (file durability via `fsync`/`fdatasync`) to
  `docs/align-requests.md`. All three are PROPOSED and non-blocking: 29 because R4 ships the bounded
  header-region digest and reserves the whole-payload `payload_sha256` field; 30 because R4 ships the
  documented check-then-create race (`R4_DEST_EXISTS`: `fs.exists` then `fs.create_rw`); 31 because
  R4 makes no durability claim (a pack is a reproducible derivative of a source file that still
  exists). Requests 21 and 23 gained new R4 client evidence without a status change — 21 a third
  input class (sizing a read-only model still needs `O_RDWR` because Align ships no `fs.size`/`stat`,
  alongside R0's model and R2A's transcript), 23 a fourth client, `PackPlan`, now with its verbatim
  warnings quoted and reproducible: `src/alignpack.align:1261:50`, `:1317:56`, and `:1331:57`, the
  three `borrow p: PackPlan` encoders, plus eleven more `borrow` sites in the same module. The header
  status line in `docs/align-requests.md` reads "21–31 are PROPOSED".
- **Baseline chain**: `de5e12d` -> `47ba089` -> `cfd15e8` (source -> oracle -> finalization),
  identity-bound and re-recorded on Linux (aarch64, kernel 6.11.11-linuxkit, Python 3.12.3) after
  the final review repair. Exactly two of the twenty recorded artifacts changed against the R2A
  chain — `Makefile` and `src/main.align`, which carry the `alignpack-smoke` owner target and the
  `--pack` / `--pack-verify` arms — and the twenty paths are otherwise identical, every other hash
  unchanged. `make baseline-check` on Linux: PASS, ending `baseline chain: PASS`.


## Merged checkpoint: R2A-EXPERT-TRACE-CAPTURE — expert-trace capture (2026-08-27)

- **Status: merged.** R2A-EXPERT-TRACE-CAPTURE merged as align-llm PR #124, head `ab5f7d8`, merge
  commit `b8e1cb6` on `main`. Required checks passed before merge; GitHub owns that transient
  check and review metadata.
- Branch was `agent/r2a-expert-trace`, based on the merged R1B-GPTOSS-MOE-IR chain (PR #123, head
  `3bf5c9c`, merge `d8d4ef6`, onto `main` at `08492dc`). The authoritative design ledger is
  `docs/specs/r2a-expert-trace.md`, committed at `b4dfb60`; the implementation is committed at
  `140e868`, the consolidated review repair at `e99bceb`, and the final portability and
  writable-copy repairs at `aff1beb` and `ab5f7d8`.
- **What it delivers.** The R2a slice of the R2 roadmap item: `main --expert-trace CALLBACK_LOG
  [OUT.json]` consumes a `llama-eval-callback` transcript and produces an `R2_ACTIVATION_TRACE`
  (`schema_version: 1`) document recording, per (token, layer), the selected expert ids and locality
  aggregates. A dense (non-MoE) transcript yields `moe: false` rather than an error, so the arm is
  exercisable before a real MoE transcript exists.
- **Align capability requests.** R2A added Requests 25 (`std.process` streaming/redirecting child
  stdout), 26 (`str`-to-integer parsing in the standard library), 27 (string sorting), and 28 (a
  readable append-only accumulator) to `docs/align-requests.md`. All four are PROPOSED and
  non-blocking:
  - **25** does not block because R2A consumes a transcript *file* and never invokes
    `llama-eval-callback` itself (the shell redirection already in `scripts/run-expert-trace-parity`
    stands in).
  - **26** does not block because `parse_uint` at `src/expert_trace.align:328` is a viable
    workaround. Its evidence is *not* "four hand-rolled parsers": `src/main.align:71`,
    `src/failure_memory.align:176`, and `src/c6f1_request11_adoption.align:6` are each a two-line
    `json.decode` detour, and only `src/expert_trace.align:328` is a real parser — which is the
    stronger argument, because those three route a plain decimal integer through a JSON decoder and
    R2A cannot even do that (`     12.0000` is not a JSON integer and an expert id must not travel
    through a float).
  - **27** does not block because `sort_spans` sorts an index array by hand and `src/model_ir.align`
    packs a 42-bit name hash (`name_hash`/`packed_entry`/`name_index`, lines 261-301). The request is
    string *sorting*, not string ordering: `str` satisfies `Ord` and backs `<`/`<=`/`>`/`>=` and
    `sort_by_key`'s `str`-key comparator at this pin, so `span_less`/`span_same` now use the shipped
    `<` and the module's false "Align ships no string ordering" comment is gone. Three sort paths
    were compiled and rejected in the module's own shape: `.sort()` ("needs a numeric element type,
    got str"), `array_builder<str>` ("requires a Copy scalar, `string`, or a closed heap record"),
    and `index.sort_by_key(fn i { span_text(...) })` ("a lambda cannot capture the owned value
    'family_start' yet"; "field access is only supported on a local binding" for a `borrow`
    parameter's column). `crates/align_sema/src/lib.rs:50616` is the `elem.is_numeric()` gate and
    `:50601-50603` the "first cut … a `sort(cmp)` overload is a follow-up" comment.
  - **28** does not block because the module accumulates interned name and operation text into a
    `buffer` (readable through `.bytes()` while growing) plus pre-sized `array<i64>` span columns.
    `builder` and `array_builder` are write-only until `build()`: `'.len()' is not defined on
    array_builder<i64>`, `cannot index array_builder<i64>`, `'.len()' is not defined on builder`,
    `'.bytes()' is not a method on builder`.

  Requests 21 and 23 gained new R2A client evidence without a status change — 21 a second class of
  read-only input (a transcript in a root-owned or read-only artifact directory; the `0444`
  `read-only-transcript` smoke case exits 3 with no document), 23 the single `borrow`-parameter lint
  line `src/expert_trace.align:1622`. Request 22 gained **none**: R2A holds no `array<string>` and
  avoids that shape entirely. Requests 22 and 24 remain inherited, unconsumed, and unchanged.
- **Owner and qualification.** `make expert-trace-smoke` is the new narrow Makefile owner; adding it
  changes the `Makefile`, so preflight selects the fresh-image installed profile.
  `scripts/run-expert-trace-parity` is the named opt-in qualification. The R2 roadmap gate stays open
  until a real MoE transcript exists — a small MoE GGUF (1-4 GB) is a separate pending user decision
  that would close it — with a dense-Qwen parity run (`moe: false` path) recorded below as smoke-level
  evidence ahead of that decision.
- **Implementation is complete and reviewed.** `--expert-trace` is implemented
  (`src/expert_trace.align`, `src/main.align`), `docs/specs/r2a-expert-trace.md` is updated, and every
  owner below passes at the unchanged pin `4b515f8d`:
  - `gmake check`: 28 units, PASS. `gmake build`: PASS.
  - `gmake expert-trace-smoke`: 95 fixtures plus a real transcript excerpt, PASS.
  - `gmake gguf-smoke`: PASS. `gmake model-ir-smoke`: PASS.
  - `gmake gate-topology-check`: PASS. `gmake format-check`: PASS. `gmake fmt`: no diff.
  - `make expert-trace-smoke gate-topology-check` on **Linux** (aarch64, Python 3.12.3): PASS. The
    first Linux run of the new owner failed in `destination-path-guard`, which probed a 4097-byte
    destination with `Path.exists()`: `stat` answers `ENAMETOOLONG`, which Python 3.12 re-raises and
    3.13 swallows, so the case passed on this macOS host and aborted in the container. The guard now
    reads the working directory instead of probing the impossible name. The first *installed*
    profile run then failed inside the fresh trusted worker with `expert trace smoke: FAIL
    real-transcript: exit 3` (named by `ALIGN_LLM_AGGREGATE_DIAGNOSTIC=1`): that worker mounts the
    checkout read-only and `fs.open_rw` demands `O_RDWR`, so the owner now scans a writable copy of
    the checked-in excerpt. This is fresh Request 21 client evidence and is recorded there.
  - `git diff --check` and `git diff --check d8d4ef6..HEAD`: clean. The checked-in excerpt's
    truncation markers end in a significant space, so `eval/fixtures/expert-trace/*.txt -whitespace`
    is now in `.gitattributes` (the `corpus-file-set.manifest` precedent) rather than the markers
    being stripped.
  - Dense-Qwen parity (`moe: false` path, `scripts/run-expert-trace-parity`): **PASS** — 1 graph, 958
    nodes, 28 layers, `moe: false`, 16,633 lines, `bytes_read` 1,101,339.
  - MoE parity: **N/A** (no small MoE GGUF downloaded yet; see the pending user decision below). The
    runner now *emits* both verdict lines rather than leaving them for an author to compose, and
    exactly one of them is a `PASS`: the dense half prints `N/A - moe.present is true` on a MoE run,
    because its dense-only assertions never execute there.
- **Review envelope.** Two complementary independent reviewers covered explicitly disjoint risks of
  the candidate at `140e868`: **A** the Align source, **B** the specification, register, handoff, and
  fixtures. A returned 1 blocker class, 1 major, 2 minor, and 1 low; B returned 3 major, 5 moderate,
  and 5 minor. **Every finding was accepted** and all repaired as one consolidated repair on top of
  `140e868`. The two substantive ones were real and both are recorded as ledger corrections 15 and
  16: five `str` slices at length-relative offsets aborted the process (exit 134, no document) on any
  transcript carrying a multi-byte UTF-8 scalar at the offset — the whole class is now audited and
  every `str[a..b]` uses an ASCII-matched offset — and the locality adjacency test compared packed
  keys alone, so a token index at the top of its field carried into the layer field and manufactured
  a cross-layer pair (measured: `adjacent_pair_count` 9 where the definition gives 8). A final
  review of the repair delta at `e99bceb` returned **changes requested**: 3 medium and 3 low, every
  one accepted and repaired in the commit that follows it. The medium class was
  documentation accuracy against the shipped source — every `src/*.align:NNN` citation in the diff
  was stale by the eleven lines the repair added, Request 27 mis-stated the `sort_by_key` blocker as
  a missing `str` key when the real blocker is owned-value lambda capture plus `borrow`-parameter
  field access, and Request 21 called `fs.open_rw` the *only* random-access constructor. The low
  class was three assertions that could not fail: an unconditional dense parity verdict, a `-1`
  printed for an underived layer count, and a `destination-path-guard` that accepted any nonzero
  exit. Every `src/*.align` citation in the whole diff has since been re-resolved against `HEAD`,
  the Request 23 lint block is a paste of this HEAD's `gmake check` output, and the Request 27 probe
  block is a paste of a probe re-run at this HEAD. That review also swept **207,807 UTF-8 mutations**
  of the real build-10566 excerpt through the arm with **0 aborts**, which is the durable evidence
  that the multi-byte slicing class repaired at `e99bceb` is closed. The repair is narrow and bound
  to the recorded findings, so it does not trigger another full review.
- **Baseline chain**: `a2eefdf` -> `8cffdd4` -> `dd0b150` (source -> oracle -> finalization),
  identity-bound and re-recorded on Linux (aarch64, kernel 6.11.11-linuxkit, Python 3.12.3) after
  the final review repair. Exactly three of the twenty recorded artifacts changed against the R1B
  chain — `Makefile` and `src/main.align` (the `--expert-trace` owner and arm) and `.gitattributes`
  (the `eval/fixtures/expert-trace/*.txt -whitespace` rule) — and the twenty paths are otherwise
  identical, every other hash unchanged. `make baseline-check` on Linux: PASS, ending `baseline
  chain: PASS`.
- **Next actions, in order.**
  1. None for R2A itself: PR #124 merged. The R4 branch below is rebased onto that merge and is
     the active capability.
- **Two pending user decisions, tracked and not to be lost.**
  1. Carried forward from R1B: whether to download `gpt-oss-20b-mxfp4.gguf` (12.1 GB) to run the
     gpt-oss `model-ir-parity` qualification; until decided that qualification stays the documented
     `N/A`.
  2. New for R2A: whether to download a small MoE GGUF (1-4 GB) so
     `scripts/run-expert-trace-parity` can exercise the `moe: true` path against a real MoE
     transcript; until decided the R2 roadmap gate stays open on dense-only smoke evidence.

## Merged checkpoint: R1B-GPTOSS-MOE-IR — gpt-oss MoE frontend and per-expert Block IR (2026-08-27)

- R1B-GPTOSS-MOE-IR merged as align-llm PR #123 (head `3bf5c9c`, merge `d8d4ef6`) onto `main` at
  `08492dc`, continuing the merged R1-QWEN-MODEL-IR chain (PR #122, `85a3a97` -> `08492dc`). Branch
  was `agent/r1b-gptoss-moe-ir`; the design ledger is `docs/specs/r1b-gptoss-moe-ir.md`, committed at
  `2cd2cb4`. Sections 6 and 7 of the ledger are applied and closed — section 7 carries fifteen
  implementation corrections and section 7.1 maps every section 3 closure cell to its shipped case.
- **What it delivered.** The MoE half of the R1 roadmap gate: a new architecture-neutral
  `src/model_ir.align` builder (`BlockPlan` -> `ModelIr` -> document, imported by both frontends), a
  new `src/frontend_gpt_oss.align` owning gpt-oss hyperparameters and block-plan construction, and
  `src/frontend_qwen.align` reduced to qwen2 knowledge alone. `--model-ir` dispatches on the
  container's own `general.architecture` field (`qwen2` or `gpt-oss`; no new flag, no new CLI verb).
  `R1_MODEL_IR` is `schema_version: 2`, emitted by both frontends: two additive fields on the block
  tensor record, `claimed_absolute_offset` and `claimed_nbytes`, carry **per-expert** `ExpertBlock`
  byte sub-ranges (chosen over layer granularity because every named R2/R3 consumer needs the
  individual expert, section 2.4.1). One new geometry row, MXFP4 (GGML type id 39, block size 32, 17
  bytes/block), is transcribed from `ggml.h` in the named revision and verified against
  `libggml-base` of llama.cpp build 10566 by a library oracle (`ggml_blck_size`/`ggml_type_size`),
  recorded "library-oracle verified; real-model verification pending". One new error code,
  `R1_BLOCK_CLAIM_MISMATCH`, is a defensive, provably input-unreachable claim-tiling guard.
- **Owner results at the merged head (unchanged pin `4b515f8d`).** `gmake check`: 27 units, PASS.
  `gmake build`: PASS. `gmake gguf-smoke`: 62 fixtures, byte-identical to R0's, PASS.
  `gmake model-ir-smoke`: 49 qwen + 31 gpt-oss + 62 R0 fixtures re-run, PASS. `gmake
  gate-topology-check`: PASS (the `Makefile` is untouched). `gmake format-check`: PASS. `gmake fmt`:
  no diff. `git diff --check`: clean.
- **Qualifications.** The qwen `model-ir-parity` qualification was re-run against the local
  Qwen2.5-Coder-7B Q4_K_M model and the local `llama-cli`: **PASS**, size-sum oracle `computed_end`
  4,683,073,536 equal to `file_size`. **The gpt-oss half is a standing open qualification, not
  discharged by the merge**: it stays the documented explicit `N/A` (plan section 4.4) pending the
  user decision to download `gpt-oss-20b-mxfp4.gguf` (12.1 GB, see below); until then no row of
  ledger section 2.5 is settled by real-model inspection — every ASSUMED row still stands on its
  assumption banner — and the gpt-oss half of the R1 roadmap gate rests on the synthetic corpus, the
  size-sum and claim-tiling oracles, and the MXFP4 library oracle alone.
- **Review envelope.** Two complementary independent reviewers covered explicitly disjoint risks of
  the candidate at `53f064f`: **A** the Align source and **B** the specification, register, and
  handoff. A returned **approve** with 2 low findings; B returned **approve** with 1 major, 2
  moderate, and 5 minor. **Every finding was accepted** and all eight were repaired as one
  consolidated repair, `3bf5c9c`. The two substantive ones were real: the `role_required` comment
  justified the optional router bias with a regex (`ffn_gate(_exps)?.bias`) that does not match
  `ffn_gate_inp.bias` at all, and the fused variant required an `ffn_gate_up_exps.bias` that no
  installed artifact names — role 21 is now optional like role 13, with
  `gptoss-variant-fused-nobias` as its positive fixture and the asymmetry recorded in ledger section
  2.5.4 and section 7, item 15.
- **Open item carried forward, not to be lost.** `gpt-oss-20b-mxfp4.gguf` (12.1 GB) remains
  undownloaded. The gpt-oss `model-ir-parity` qualification and real-model inspection against ledger
  section 2.5 stay open until the user decides whether to fetch it; see the pending decisions in the
  active R2A capability below.

## Merged checkpoint: R1-QWEN-MODEL-IR — Qwen2 Model IR and Block IR (2026-08-27)

- R1-QWEN-MODEL-IR merged as align-llm PR #122 (head `85a3a97`, merge `08492dc`) onto `main` at
  `6640dcf`. Branch was `agent/r1-qwen-model-ir`; the design ledger is
  `docs/specs/r1-qwen-model-ir.md`, committed at `631b2ce`.
- **What it delivered.** One consumer-complete path: a caller names a `.gguf` file and receives one
  canonical `R1_MODEL_IR` document (`schema_version: 1`) carrying the Model IR (architecture-level
  hyperparameters) and the Block IR (placeable, evictable `WeightBlock`/`AttentionBlock`/`MlpBlock`
  units with tensor names, absolute offsets, and byte sizes) that `docs/specs/align-llm.md` section 5
  places between the GGUF reader and the layout planner. `./main --model-ir MODEL` writes the
  document to stdout; `./main --model-ir MODEL OUT.json` writes it to a file and prints the stable
  summary block, byte-identical to the one-operand form. `src/gguf.align` gained the public
  `GgufTable` producer surface (`read_table` plus ten accessors and two geometry functions);
  `src/frontend_qwen.align` was the new Qwen2 owner module. Deliberately out of scope: tokenizer or
  vocabulary materialization (Request 22 stays non-blocking), a MoE/gpt-oss frontend (a nonzero
  expert count was rejected), tensor payload decode or dequantization, layout plan, `.alignpack`, and
  execution/runtime.
- **Owner results (unchanged pin `4b515f8d`, after the review repair).** `gmake check`: 25 units,
  PASS. `gmake build`: PASS. `gmake gguf-smoke`: 62 fixtures, PASS. `gmake model-ir-smoke`: 49 qwen
  fixtures + 62 R0 fixtures re-run, PASS. `gate-topology-check` and `format-check`: PASS. `git diff
  --check`: clean. Preflight ran the installed profile via Docker-in-Docker on macOS (the `Makefile`
  changed, matching `FRESH_IMAGE_PATTERNS`).
- **Parity qualification run once** (`scripts/run-model-ir-parity`) against the local
  Qwen2.5-Coder-7B Q4_K_M model with the local `llama-cli` (build 10566, `bb4caa754`): **PASS**.
  Compared rows: `n_layer` 28, `n_embd` 3584, `n_head` 28, `n_head_kv` 4, `head_dim`
  (`n_embd_head_k`/`_v`) 128, `n_ff` 18944, `n_vocab` 152064, `n_expert` 0, `rope type` 2,
  `freq_base` 1.0e6, `rms_eps` 1.0e-06. Size-sum oracle: `data_offset` 5,953,536 +
  `total_tensor_bytes` 4,677,120,000 = `computed_end` 4,683,073,536, matching `file_size`
  4,683,073,536. Coverage 339 of 339 tensors over 58 blocks. This discharged the dense half of the
  roadmap gate; `docs/specs/roadmap.md` section R1 records these numbers as achieved.
- **Baseline chain**: `51b5d86` -> `a207933` -> `bc42527` (source -> oracle -> finalization),
  identity-bound and re-recorded on Linux after the final review repair. `gmake baseline-check` on
  Linux: PASS.
- **Review envelope.** Two complementary independent reviewers covered explicitly disjoint risks of
  the candidate at `87a64b4` (Align source vs. specification/fixtures/runners/governance); 17
  findings (2 major, 2 minor, 3 nit, 3 medium, 5 low, 2 nit), **all accepted**, repaired at `d05cb2b`
  as one consolidated repair. The two majors were real: GGML's block invariant is per row, so the
  original `qwen2-full` fixture described a tensor GGML cannot store; and duplicate detection,
  block-member lookup, and the coverage sweep were quadratic (26.75 s / 87.25 s on 100k/200k-tensor
  files), fixed by a sorted tensor-name index (0.09 s / 0.18 s). One final comprehensive review of the
  repair delta at `d05cb2b` returned **approve** with 5 low findings, all accepted and repaired in
  the following commit. No further review was required: the repair changed no behavior of the product
  executable.
- **Align requests 23 and 24 opened during this capability**, `PROPOSED`, non-blocking, alongside
  inherited Requests 21 and 22; all four carry forward into R1B above. Request 23: the pinned
  compiler's huge-struct-copy lint fires on every `borrow t: GgufTable` accessor even though no call
  copies the 552-byte struct. Request 24: `array_builder<T>` is admitted as a `borrow mut` parameter
  type but the plain text `builder` is rejected, so `gguf.inspect` and `gguf.read_table` duplicate one
  decode-and-accumulate walk.

## Merged checkpoint: R0-GGUF-INSPECT — read-only GGUF inspection (2026-08-26)

- R0-GGUF-INSPECT merged as align-llm PR #121 (head `dcd8801`, merge `6640dcf`) onto `main` at
  `92c0979`. Branch was `agent/r0-gguf-inspect`; the design ledger is
  `docs/specs/r0-gguf-inspection.md`, committed at `12453d7`.
- **What it delivered.** One consumer-complete path: a caller names a `.gguf` file and receives one
  canonical `R0_GGUF_INSPECTION` document (`schema_version: 1`) describing the header, every
  metadata key/value with its declared GGUF type, the complete tensor table, the architecture, the
  alignment, the absolute data offset, and `bytes_read`. `./main --inspect-gguf MODEL` writes the
  document to stdout; `./main --inspect-gguf MODEL OUT.json` writes it to a file and prints the
  stable summary block. The document bytes are byte-identical between the two forms. Strictly
  read-only and runtime-independent: no tensor payload decode, no dequantization, no mmap, no
  tokenizer materialization, no multi-shard resolution, no big-endian GGUF, and no import of any
  provider or `align-runtime` surface. R0 made **no performance claim**.
- **Baseline chain**: `3af0902` -> `813358f` -> `dcd8801` (source -> oracle -> finalization),
  identity-bound and appended after the review repair. `python3 scripts/check-baseline-chain` passes
  at the branch head.
- **Owner results (unchanged pin `4b515f8d`, after the review repair).** `gmake check`: 24 units.
  `gmake build`: PASS. `gmake gguf-smoke`: 62 fixtures, PASS. `python3 scripts/check-gate-topology`:
  PASS. Preflight ran the installed profile via Docker-in-Docker on macOS.
- **Parity qualification run once** (`scripts/run-gguf-reference-parity`) against a local
  Qwen2.5-Coder-7B Q4_K_M model: PASS. `bytes_read` 6,291,456 of a 4,683,073,536-byte file
  (0.1343%), `data_offset` 5,953,536, 29 metadata KV pairs, 339 tensors — this discharged the roadmap
  gate. `docs/specs/roadmap.md` section R0 records these numbers as achieved.
- **Align requests 21 and 22 are `PROPOSED` and non-blocking**, and both are inherited unchanged by
  the active R1-QWEN-MODEL-IR capability above; see `docs/align-requests.md` for the current
  next-consumer framing. Request 21: both random-access `file` constructors at pin `4b515f8d`
  (`fs.create_rw` and `fs.open_rw`) demand `O_RDWR`, so inspecting a model requires write access to a
  file that is never written. Request 22:
  `array<string>` and arrays of a record with a Move field cannot be indexed (`check_index` rejects
  it); `src/gguf.align` carries tensor `absolute_offset` values as a NUL-separated prefix stream plus
  a parallel `array<i64>` instead.
- **Review envelope.** Two complementary independent reviewers covered explicitly disjoint risks of
  the candidate at `ebaaf99`: **A** the Align source (`src/gguf.align`, `src/main.align`) and **B**
  the specification, fixtures, runners, and governance documents. A returned 1 blocker, 2 minor, and
  4 nit; B returned 2 medium, 5 low, and 3 nit. **Every finding was accepted** and all fourteen were
  repaired in one consolidated repair, with plan, code, tests, and documentation moving together. The
  blocker was real and reproduced before the fix: `data_offset + offsets[i]` wrapped in two's
  complement, so a tensor offset of `0x7FFFFFFFFFFFFFE0` gave `status: "ok"`, exit `0`, and a
  negative `absolute_offset`; both sites are now non-wrapping and two new fixtures pin them. The
  other code corrections are a completing `refill` for short reads, a distinct
  `GGUF_WINDOW_UNAVAILABLE` for a zero-capacity window, control-byte escaping in the summary block,
  and `architecture_present` on `GgufInspection`. Sections 6 items 15–24 and the new section 6.2
  cell-to-case mapping of `docs/specs/r0-gguf-inspection.md` carry every contract correction; the
  repair changed no document field and no `schema_version`.

## C8 is closed (2026-08-26)

C8 delivered nine consumer-complete capabilities and its gate is met. The ninth,
`C8-SELECTION-SINGLE-GIT-QUERY`, merged as PR #120 on `main` at `92c0979`: `patch_eval.evaluate`
now reaches a revision-free `select_tests_for_evaluation` that runs `git ls-files -z` alone, while
the revision-bearing `--select-tests` CLI document stays byte-identical. Its 101-pair
`compare-atomic` measured a 10,793 ppm (1.08%) reduction, but on an aarch64 Docker Desktop
linux/arm64 VM host rather than the WSL2 x86_64 host of the earlier series, so that number is
comparable only with its own baseline and is a path-specific claim, not a platform claim. Every
per-capability baseline, binary digest, host, and ledger row is in `docs/specs/c8-speed-first.md`
sections 2 through 11 and is not repeated here. The bounded retrospective promoted exactly one
reusable rule: the **ppm-floor rule** in section 1 of that document — a performance capability
records its cost ceiling in the ledger before implementation, a seam below the 2,000 ppm shipping
floor is deferred rather than implemented, and a measured result far below its recorded ceiling is
reported as a ceiling-estimation miss. `CLAUDE.md`'s performance-claim row carries the one
corresponding clause. A deferred C8 surface reopens only with a recorded ceiling above the floor or
as a genuine Align capability request.

Two maintenance items remain deliberately deferred rather than active work: preserve the
`eval/runners/run-coding-task.py` zombie-counting behavior until a capability already rebinds and
re-measures the frozen coding corpus or revisits its validation-process budget; replace
`c6f2-request14-adoption`'s publication-race polling with a deterministic seam only when that owner
boundary is next changed.

## Resume in another environment

1. Fetch `origin`, check out `agent/r4-5-external-buffer`, and read `CLAUDE.md`, then
   `docs/specs/r4-5-external-buffer.md` in full (committed at `7bd7d0d`, corrections applied) — it
   is the plan of record — and `docs/specs/r4-alignpack-layer-major.md` for the alignpack container
   surface it consumes. R4-ALIGNPACK-LAYER-MAJOR merged as PR #125 (`a7e72dc` -> `991eab1`); this
   branch is rebased onto that merge.
2. Materialize the pinned toolchain with `scripts/align-toolchain ensure compiler`; on macOS use
   `gmake` and the recorded `LLVM_CONFIG`/`LIBRARY_PATH` environment. Confirm `.align-revision`
   still selects `4b515f8d37de2e9a9ba06170c5842fd12dc1cba2`; R4.5 requires no pin change.
3. Resume at the first unfinished next action in the R4.5-EXTERNAL-BUFFER-SPIKE capability above:
   the implementation (`de86c58`), both reviews, and both repairs (`bf7f10b`, `049a5cc`) are done
   and every owner passes, and the baseline chain is re-recorded (`45cdc55` -> `8b3b161` ->
   `eece7a1`), so what remains is exact-head preflight and publication.
4. Do not open another Align request unless implementation exposes a further genuine shipped-language,
   compiler/runtime, or standard-library gap under the register rules. Requests 21-35 are
   `PROPOSED` and non-blocking.
5. Two user decisions are pending and must not be silently dropped: whether to download
   `gpt-oss-20b-mxfp4.gguf` (12.1 GB) for the carried-forward gpt-oss `model-ir-parity`
   qualification, and whether to download a small MoE GGUF (1-4 GB) so
   `scripts/run-expert-trace-parity` can exercise a real `moe: true` transcript and close the R2
   roadmap gate. Absent either decision, the corresponding qualification/gate stays the documented
   `N/A`/open.
6. After merge, refresh `main` and take the next eligible roadmap item. C8 is closed; do not start a
   tenth C8 capability without a recorded cost ceiling above the 2,000 ppm floor.

## Merged checkpoint: REQUEST20-PIN — adopt Align's macOS owned-JSON CI repair (2026-08-25)

- Work is on `agent/request20-align-pin-final`, based on align-llm `main` at `0a8b9cf`. Align Request 20
  shipped in Align PR #887 as `fa3f03f15f0b1d876683343233f440bce6ea27c5`; PR #888 then closed
  its upstream handoff. A later docs-only CI merge, PR #889, moved Align `main` to
  `f57b986bc9326ba8d75dad5dbe4c6531c0f872b6`; `.align-revision` now selects that exact latest
  commit. The compiler/runtime source payload is unchanged, but the managed binary and every
  pin-bound record still require evidence against the new identity.
- The upstream response is verified, not inferred from the PR summary: the required `macos-15`
  Apple Silicon job ran `align_driver --test m5_owned_json` and all 10 rows passed. The same PR
  repairs the storage-generation regression that made `JsonOwnedDecode` retain its input and arena
  facts even though the shipped owner is free-standing.
- The managed release compiler/runtime materializes at the selected latest pin on native macOS arm64 with
  `LLVM_CONFIG=/opt/homebrew/opt/llvm@22/bin/llvm-config`. The first original client fixture passes:
  `gmake --no-print-directory c7-owned-record-source-expiry-adoption` reports 3 parsed fixtures,
  12 example rows, and 45 adoption rows.
- The Darwin profile passed at clean latest-pin head `863ab0d333209fbd90bec0dd4e4148ef56f167f7`:
  `check` 4,677 ms, `build` 5,960 ms, direct `check-per-unit` 4,568 ms,
  `persisted-result-smoke` 3,534 ms, and `persisted-result-qualification` 11,138 ms. The attested
  compiler digest is `ea90318886ebcc9ed9e29b11ea3065c9d91160fea61b0be285d3196ffa1d084e`;
  runtime digest is
  `0c26b938060e747d63886f5f98c07953b69b52d2b572a538373642b96cb75211`.
- The first supervised aggregate correctly rejected the canonical baseline's old Align pin. A
  replacement chain was then mistakenly measured on macOS, where the corpus-fixed
  `/usr/bin/python3` is 3.9 and cannot parse the runner's `float | None` annotation. The recorder
  deliberately persisted two complete FAIL samples, and the negative smoke exposed their null
  aggregate timing. That non-passing chain (`026e3b1` -> `7d24042` -> `1a8b026`) is preserved as
  failed evidence and must not be published as canonical proof.
- The latest accepted replacement was recorded as non-root on native Linux aarch64 in the privileged
  `c6g2-measure:latest` helper with CPython 3.12 and bubblewrap. Both deterministic-reference
  samples passed (133,219,500–141,093,417 ns; median 137,156,458 ns). The strict chain is source
  `3714b371e09ca2937981d9098a167c43084bc0f3`, oracle
  `7080b61f9a4b5b6542b77524f0f6c7b42786b801`, and finalization
  `863ab0d333209fbd90bec0dd4e4148ef56f167f7`; `check-baseline-chain` and `verify-baseline.py` pass.
  The preceding `dc321412` Linux chain remains a valid intermediate pin checkpoint, not canonical.
- The final supervised fresh-image profile passes at `863ab0d`. Phases: image build 33,852 ms,
  attestation 3,354 ms, lifecycle 2,426 ms, self-test 14,769 ms, trust mutations 12,336 ms,
  runtime replacements 21,554 ms, boundary profile 274,947 ms, worker aggregate 424,471 ms, and
  cleanup 1,272 ms. Request 20 is `ALIGN_LLM_VERIFIED` at the selected latest pin.
- The first comprehensive review of `2caae5f` found one valid P2: the request register still called
  the earlier `2f33ac5` revision current. The register now names the selected pin and labels Request
  19's filing-time measurement historical. Because Align advanced during review, the accepted
  `dc321412` evidence above is now an intermediate checkpoint rather than publication evidence.
- The final comprehensive review of `c2cb859` found two valid P2 classes: Request 20 still promised
  its owner on every pull request even though the selected PR #889 workflow deliberately exempts
  trusted docs-only `main` diffs, and Requests 16–18 lacked their already-merged align-llm
  publication links. The repair narrows the CI contract to platform-required pull requests with the
  exact fail-closed exception and records PR #98/#99 merge evidence; no executable or baseline-owned
  path moves.
- Pending at this checkpoint: inspect the narrow review-repair commits, run exact-head preflight,
  and publish. `CLOSED` waits for the resulting align-llm merge.

## Merged checkpoint: ADAPTER-ZOMBIE — descendant-scan containment repair (2026-08-25)

- C7-P merged as align-llm PR #105 (`a4f8663`). The active capability is ADAPTER-ZOMBIE on branch
  `agent/adapter-zombie-descendants`, which closes follow-up item 2 below — the latent
  containment-scan defect deferred from PR #103's CI repair `d7f1ff6`.
- **The defect.** Every `/proc` descendant scan counted any entry whose `PPid:` matched a root,
  including entries in `State: Z`. A zombie has already terminated and only holds a process-table
  slot until someone waits for it, so it cannot escape containment. Under `PR_SET_CHILD_SUBREAPER`
  an adopted orphan that has already exited becomes a permanent zombie child of the scanning
  process, so the scan reported a containment failure for a process that no longer runs. Git 2.47
  detaches auto-maintenance before deciding whether any task is due, which is how PR #103 hit it as
  `generation child left a descendant`. `d7f1ff6` treated that one trigger from the harness side;
  this repairs the class in the scan itself.
- **All six candidates named in the PR #103 diagnosis carry the pattern and all six are repaired**
  (`cf9bd75`): `scripts/prompt-measurement-adapter.py`, `scripts/prompt-evaluate.py`,
  `scripts/prompt-fixed-adapter.py`, `scripts/prompt-gate-validator.py`,
  `scripts/prompt-snapshot-helper.py`, and `scripts/prompt-source-verifier.py`. The
  private-group check is a separate contract and is untouched — a zombie still holds its process
  group open — so each end-to-end regression's orphan leads its own session.
- **The exact-head review found that repair too wide, and `563e3ae` narrows it (finding F1).** A
  zombie is not always a terminated process: when a thread-group leader exits while another thread
  in its group keeps running, the leader stays in `State: Z` and cannot be released, yet the worker
  thread continues to execute. Omitting every `State: Z` entry hid that live descendant. Liveness
  is a property of the thread group, not of its leader, so all six scans now omit an entry only at
  `State: Z` **and** `Threads: 1`, read from the `/proc/PID/status` text already in hand — no second
  filesystem read. The visited-set traversal is unchanged, so a live entry parented to an omitted
  one is still reported. The two parse failures are deliberately asymmetric and both the code and
  the specification now say so: a vanished entry or an absent/malformed `PPid:` line is dropped by
  the shared `OSError`/`IndexError` path and **fails open** for that one entry, consciously accepted
  for parse robustness because without a parent link it cannot be placed in the tree at all; an
  absent or malformed `State:`/`Threads:` line **fails closed** and reports the entry.
- **The regression is the reviewer's own reproduction, and it is a negative control.** Every owner
  with `descendant_scan_rows` carries it — `prompt-evaluate-smoke`, `test-prompt-fixed-adapter`,
  `test-prompt-snapshot-helper`, `test-prompt-source-verifier`, and `prompt-gate-validator-smoke`'s
  `validator` family — and `e41d9ba` added the same three rows to the measurement adapter's inline
  equivalents (73 rows become 74). The fixture forks a child that starts a worker thread and then
  leaves its own leader thread through `pthread_exit`, which the kernel takes as a plain thread exit
  rather than a group exit; the child settles at `State: Z` with `Threads: 2`. Two alternatives were
  measured first: a raw `SYS_exit` through `ctypes` works but needs a per-architecture syscall
  table, and a compiled-at-test-time C helper needs a toolchain in every image. `pthread_exit` needs
  neither and was verified on `x86_64` and `aarch64` glibc CPython, so it is the portable
  construction.
- **A seventh occurrence exists and is deliberately not repaired here, and the deferral now lives in
  the plan.** `eval/runners/run-coding-task.py` has the same scan, but its consumers are
  `kill_owned_processes`/`kill_adopted_descendants` (signalling a terminated entry is a no-op) and
  `validation_process_usage`, which counts processes against `MAX_VALIDATION_PROCESSES = 256`.
  That is a resource-budget contract, not a containment verdict, so it is a distinct failure
  domain; and the file is a frozen `FILE_SET` corpus member, so touching it forces another chain
  rebind and another provider-backed re-measurement. Review finding F2 required this to be a plan
  decision rather than a handoff note, so §1.2 of `docs/specs/c6-prompt-context-optimizer.md` now
  records it with its owner (the coding runner) and its resume condition. Also tracked as follow-up
  item 2 below.
- **Where the rule is written.** The prose is §1.2 "Runtime ownership and bounded persistence" of
  `docs/specs/c6-prompt-context-optimizer.md`; the descendant-ownership ledger rows are §10.1g and
  §10.1c. `cf9bd75`'s commit message cited "section 11.3" for that ledger row, which is the
  C6-MEASURED public-contract ledger instead; the documents now carry the correct citations.
- **Review envelope.** One comprehensive review at head `8e86a22` returned **request-changes** with
  five findings. Dispositions, all accepted: **F1** (blocking, code — the `State: Z` skip hides a
  live zombie leader) closed in code by `563e3ae` and extended to the sixth owner by `7df41ac`;
  **F2** (spec-section citations, the closure-row owners, and the seventh-occurrence deferral
  belonging in the plan) closed by `563e3ae` and this handoff; **F3** (the movement sentence
  overstated "digest plus wall time") closed by naming the exact moved fields above; **F4** (the
  `IndexError` fail-open behaviour was undocumented) and **F5** (the row docstrings called a direct
  fork child an adopted orphan) closed by `563e3ae`. No finding was rejected. The repair changed
  behaviour in the six shipped scans, so it carried the full rebind and re-measurement chain rather
  than being treated as a narrow documentation fix.
- **Consequence, discharged a second time: the frozen digest chain was rebound again (`762b1d0`).**
  The review repair moved the same three script bytes, so the identical rebind set moved again and
  nothing else. The rebind tool was replayed unchanged against a worktree of the pre-repair commit
  `8e86a22`, where it reproduces the committed chain exactly and reports nothing moved; only then
  was it allowed to write. `EVALUATOR_SOURCE_SHA256` moved with the repair in `563e3ae`, as before.
- **Consequence, discharged: the frozen digest chain was rebound (`bf844f8`).** Three repaired
  scripts are corpus members and declared task artifacts — both adapters and the snapshot helper —
  so each task's `measurement_adapter_runtime`, `snapshot_helper_runtime`, three
  `artifacts[].expected_sha256` entries, and `content_sha256` moved, then
  `corpus-file-set.manifest` (six digest columns), `corpus.json`, `scope.json`, and the
  `prompt-activation-baseline-v1.json` envelope. The rebind uses only the shipped canonical binder
  and the shipped snapshot helper's `canonical_mode`/`digest_file`/`file_expectation_sha256`, and
  asserts that no other field, no membership, no mode, and no path byte moved. This extends
  `1d27b5f`; the snapshot helper is new to this rebind set.
- **Consequence, discharged: `src/prompt_evaluate.align` `EVALUATOR_SOURCE_SHA256`.**
  `scripts/prompt-evaluate.py` is bound by exact digest and executed from those bytes, so the
  repair left `./main prompt evaluate` failing before it could construct any result — exactly the
  `99a6ba7` failure mode, and `prompt-evaluate-smoke` reproduced it. The digest moves in the same
  commit as the repair so that commit is self-consistent.
- **Consequence, discharged: the gate evidence was re-measured**, because the rebind moves every
  digest the checked-in `eval/prompt/gate/` bundle embeds. Result and transcript below.
- **No new Align request.** The whole defect and its repair live in the Python contained-execution
  helpers; nothing here needs a language, compiler/runtime, or standard-library surface Align does
  not ship. `docs/align-requests.md` is unchanged.

## Merged checkpoint: C7-P — aarch64 platform profiles (2026-08-25)

- C7-PERSISTED-RESULT merged as align-llm PR #104 (`a52b9ac`). C7-P was implemented on
  branch `agent/c7p-aarch64-profiles` and merged as align-llm PR #105 (`a4f8663`), the two reviewed
  non-x86 platform profiles that section 11
  of `docs/specs/c7-persisted-result.md` requires before either aarch64 target may provide C7
  evidence. Both are discharged and merged.
- **Settled and implemented: the `aarch64-apple-darwin` profile.** Section 10 of
  `docs/specs/check-gate-topology.md` is the contract. It is deliberately minimal — a process
  boundary plus digest attestation — and explicitly claims no kernel-mediated containment, **no
  `sandbox-exec`**, no fresh compiler, no aggregate membership, and no other target. Trust content
  is the attested identity: managed compiler/runtime digests at the pin, `.align-revision`,
  repository head and cleanliness, Homebrew `llvm`/`openssl@3`/`zstd` identities, the resolved dylib
  digests behind `LIBRARY_PATH`, and host identity including a non-translated `arm64` check.
  `scripts/check-darwin-profile` (behind the `.PHONY` `make darwin-profile-gate`) validates those in
  a fixed order, runs `check`, `build`, a direct `check-per-unit`, `persisted-result-smoke`, and
  `persisted-result-qualification` as bounded children, and emits the identity block itself;
  `scripts/align-toolchain attest compiler` is the toolchain-identity source and reuses `verify()`.
- **Discharged: the `aarch64-unknown-linux-gnu` reuse condition.** Section 9.1's condition ("only
  after this profile's native aarch64 owner passes at the exact C7 head") is met by the
  `Installed Ubuntu 24.04 fresh-image profile (aarch64)` check concluding `success` at the exact C7
  head `e14ba33` (run `32814437108`, job `97699828694`), and the target-local C7 gate then passed
  natively on aarch64 Linux at this branch's head. `docs/specs/c7-persisted-result.md` sections 11.2
  and 11.3 hold both records, including the two emitted attestation blocks.
- **Cadence, deliberately.** Both gates are named focused qualifications — run at a C7 target-local
  owner-boundary change or an explicit audit, not for a pin change alone and not per pull request.
  Neither joins
  `hosted-checks`, `capable-checks`, or `ci`, so `scripts/check-gate-topology`'s `EXPECTED` bytes and
  the topology oracle are untouched and `make gate-topology-check` passes unchanged.
- **The `Makefile` change re-finalized the identity-bound baseline chain.** Adding
  `darwin-profile-gate` changed a recorded baseline artifact. The replacement chain is source
  `9fd3ab64433e526d3af5c647ab933e8bfc365103`, oracle
  `3605b27ccbe1089f5ed2cb06294806a85d247cf1`, and finalization
  `f72e71f077e43d2943f9b9572c4367b9091888c4`; it was appended, never amended, and
  `python3 scripts/check-baseline-chain` reports `baseline chain: PASS` at the branch head on both
  the host and inside the container.
- **New Align request.** `docs/align-requests.md` Request 20 (`PROPOSED`, medium, non-blocking):
  Align CI's `macos-15` matrix leg executes no test binary — the bounded PR test gate is guarded by
  `if: matrix.lint`, and `scripts/test-pr.sh` does not select `m5_owned_json` even there, so
  Request 9's own boundary regressions run only in the ubuntu-only nightly full suite. Request 9's
  contract is target-local, so this asks upstream to run that focused target on the macOS leg.
- **Environment fact for the local preflight on this host, not repository state.** `/usr/bin/make`
  is GNU Make 3.81 and cannot parse this `Makefile` (`Makefile:220: *** multiple target patterns`),
  while the repository requires GNU Make 4.3 or newer. `scripts/pre-pr`'s executable plan invokes a
  bare `make`, so run it with a directory containing a `make` symlink to `gmake` ahead of
  `/usr/bin` on `PATH`. The profile gate itself is unaffected: it resolves `gmake` before `make` and
  rejects anything that does not report GNU Make.
- **Reviewed and repaired.** One fresh comprehensive adversarial review of head `9119549` returned
  request-changes with nine findings (F1-F9); all nine were accepted. The consolidated repair is
  `3e9b27e` — three uncaught-exception paths in `scripts/check-darwin-profile` (empty `--version`
  output, attestation shape drift, a non-ASCII `.align-revision`), the `gmake --version` fall-through
  and the `ALIGN_LLM_FRESH_COMPILER=0` selector, the new failure-path owner
  `scripts/test-check-darwin-profile`, and the specification repairs — followed by the gate
  re-emission commit. `scripts/test-check-darwin-profile` has no Make target, per the
  `scripts/test-align-toolchain` precedent, so the `Makefile` and the identity-bound canonical
  baseline chain are untouched by the repair.
- Published and merged as PR #105 (`a4f8663`) with the sections 11.2/11.3 citations and the
  verification table below.

## Merged checkpoint: C7-PERSISTED-RESULT (2026-08-25)

- C6-MEASURED merged as align-llm PR #103 (`c9a510d`). C7-PERSISTED-RESULT was implemented on
  branch `agent/c7-persisted-result` and merged as align-llm PR #104 (`a52b9ac`), per
  `docs/specs/c7-persisted-result.md`. All three implementation slices are landed — `cb3459b`
  (Request 9 adoption checkpoint), `1d066ff` (product consumer), `1e5797b` (qualification plus lane
  admission) — the lane topology is final for that wave and its identity-bound baseline chain was
  re-finalized on top of it. C7-P then changed the `Makefile` again and re-finalized the chain a
  second time; the current chain is recorded in the active capability above.
- **Landed: the mandatory Request 9 adoption checkpoint.**
  `src/c7_owned_record_source_expiry_adoption.align`,
  `scripts/run-c7-owned-record-source-expiry-adoption`, and the `.PHONY` Make target
  `c7-owned-record-source-expiry-adoption` implement the section 6.1 fixture
  `c7-owned-record-source-expiry-adoption` against the real shipped surface at the unchanged pin
  `2f33ac5c33a898a7894af58322852632ce6ffe42`. It covers section 6.1 source expiry for every
  retained direct field, the three optional-note states, the section 6.3 Move-carrier transfer set,
  the Request 9 normative owned-path golden byte pair, bounded canonical encode at exact fit and
  both rejection rows, and direct `array<string>` cleanup through replacement, move-out, and a
  mid-array recoverable failure. `docs/examples/c7-persisted-result-syntax.align` and
  `docs/examples/c7-persisted-result-lifetime.align` are the section 12.1 checked-in fixtures; the
  runner owns their pinned `alignc fmt` parser-only check together with the normative
  `docs/examples/request9-owned-json-syntax.align`.
- **Landed: the product consumer.** `src/persisted_result.align` implements the section 4 records,
  the section 5 `bounded-bucket-v1` algorithm and the six ordered verifier recomputations, the
  section 6 ownership/lifetime boundary, the section 7 whole-file publication limitation, the
  section 8.1/8.2 precedence tables, and the section 3.1 `persist_file`/`verify_file`/
  `VerificationSummary` surface. `src/main.align` adds the two exact selectors, the section 3.3
  seven-line summary, and the valid-semantic-`FAIL` nonzero exit after publication. Six focused
  `.PHONY` smoke targets (`c7-persisted-result-{cli,lifetime,owned-move,wire,noncanonical-input,
  independent-destinations}-smoke`) and `scripts/c7_persisted_result_fixtures.py` are the bounded
  functional evidence; they join no aggregate, so `gate-topology-check` stays green. The section
  4.4 golden vectors reproduce byte-for-byte end to end: `input_sha256` `6de733d4...`,
  `content_sha256` `a0160d36...`, and the external `result_sha256` `8fb29a72...`.
- **Landed: the qualification slice and the bounded functional owner.**
  `scripts/run-persisted-result-qualification` owns its own independent reference (ordered field
  tables, Request 7 escape grammar, `bounded-bucket-v1`; it imports neither the Align module nor
  `scripts/c7_persisted_result_fixtures.py`), the section 10.2 boundary table, the seed-`20260803`
  corpus of 256 PASS + 32 FAIL differential cases, 38 malformed inputs against both a fresh and an
  existing sentinel destination, 29 artifact mutations including digest-consistent semantic
  mutations, and the temporary `else if raw < upper_bound` -> `<=` source mutation built in a
  private copy of the tree. `scripts/run-persisted-result-smoke` drives the six member runners as
  one bounded functional owner and prints its own cost. Both follow the section 9.4 boundary: the
  Make recipe resolves the compiler and product at the repository root and passes them explicitly.
- **Aggregate admission decision: `persisted-result-smoke` is now a hosted member.** Its measured
  cost is 3.6 s for all six runners at the pinned compiler, so section 12's "small stable
  integration regression" test is satisfied. `Makefile`, `scripts/check-gate-topology` (oracle plus
  self-test literals), and `docs/specs/check-gate-topology.md` (prose plus oracle block) changed
  together, and `docs/specs/c7-persisted-result.md` section 12 records the decision.
  `persisted-result-qualification` (8.7 s plus one whole-program compile) stays outside every
  aggregate by design.
- **The qualification found and repaired one real contract deviation.** Sections 8.1/8.2 row 3 and
  the section 8.3 matrix require `Err(Invalid)` for a malformed document, but the shipped
  `core.json` decoder returns its own `Error.Code(_)`, which `decode_input`/`decode_result`
  propagated unchanged — the CLI exited 1 (`NotFound`-class) instead of 2 (`Invalid`) for every
  malformed input and artifact. Both helpers now apply the section 6.3 typed `map_err`; section 8.1
  states the rule explicitly. A genuinely absent file still maps to the row-2 filesystem error
  (exit 1). Negative control: a temporary rebuild with the mapping reverted fails the qualification
  at `malformed input empty-file: exit 1 != 2`.
- **One measured section 9.4 correction.** The 64 KiB per-stream capture bound is unreachable for
  the mutation build: the pinned compiler writes 105,234 bytes of whole-program advisory warnings to
  stderr, and the exact build vector admits no suppressing option. Section 9.4 now keeps 64 KiB for
  product children and sets 1 MiB for a compiler child, with the same overflow -> terminate,
  kill-if-needed, wait, close -> gate failure behavior.
- **Landed: the wrap-up.** The identity-bound canonical baseline chain is re-finalized against the
  final `Makefile`, and the supervised capable gate is green at the repaired head `36c8568`
  (`fresh worker qualification: PASS (installed profile only)`). That run is the capability's final
  `make ci` evidence and it advanced `docs/align-requests.md` Request 9 to `ALIGN_LLM_VERIFIED`.
  What remains is one fresh comprehensive review and the English pull request with the section 12
  evidence.
- **The first supervised run of the admitted lane member found one real defect (`36c8568`).**
  Admitting `persisted-result-smoke` to `HOSTED_CHECK_TARGETS` put it in the capable aggregate for
  the first time, and that aggregate failed with `fresh compiler: ERROR CHILD aggregate` while the
  check graph itself exited 0. `ALIGN_LLM_AGGREGATE_DIAGNOSTIC=1` reported
  `DIAGNOSTIC worker stderr captured=38 shown=38` and no aggregate-child output at all, which is
  what located the fault: the `make` child succeeded and the worker's *post*-aggregate overlay check
  rejected the run, because it admits exactly one workspace-overlay entry, `main`.
  `scripts/run-persisted-result-smoke` built its member-runner environment as an explicit map and
  applied section 9.4's product-child rule to the member runners themselves, dropping every
  sandbox-owned value the aggregate exports — including `PYTHONDONTWRITEBYTECODE=1`. Each member
  runner does `import c7_persisted_result_fixtures`, so CPython wrote `scripts/__pycache__/` into
  the workspace overlay and the gate failed on the second entry. The owner now forwards `HOME`,
  `TMPDIR`, `PYTHONHOME`, `PYTHONNOUSERSITE`, and `PYTHONDONTWRITEBYTECODE` when the caller supplies
  them, and section 9.4 records the rule. This is the same root-cause class as `3768ad8`: a child
  launcher rebuilding the environment from fixed literals instead of the aggregate's own values.
  Class audit: `run-persisted-result-qualification` launches only the product and the compiler — no
  `bash`/`python3` child, no import, no workspace write — and stays outside every aggregate, so it
  has no instance of the defect and is unchanged.
- **The section 4.4 golden vectors reproduce exactly.** The decoded C7 input re-encodes
  byte-for-byte to the section 4.4 `input bytes` line, and the Request 9 `OwnedTask` pair
  reproduces its canonical output including `u64::MAX`, embedded NUL, and multibyte text. The
  section 4.4 `input_sha256`, `content_sha256`, and external `result_sha256` values were
  independently recomputed from the document's own literal bytes and match. No Align gap was found;
  no new `docs/align-requests.md` entry is required by this checkpoint.
- **Resolved: the identity-bound canonical baseline chain is re-finalized.** Admitting
  `persisted-result-smoke` to `HOSTED_CHECK_TARGETS` changed `Makefile`, which
  `docs/specs/check-gate-topology.md` records as a baseline artifact, so the previous chain went red
  with `working-tree Makefile differs from the baseline source commit`. The replacement chain is
  source `1e5797b3b451c79a48bd28f78edbd47b8540f9ec`, oracle
  `32e1442a5470f6c25862e290b6c2495ee8c2df0b`, and finalization
  `2fe903625816bd4738293e94497f88d43c42b5d9`; it was appended, never amended, and
  `python3 scripts/check-baseline-chain` reports `baseline chain: PASS` at the final head.
  `make gate-topology-check` is green at the admitted lane state.
- **Platform-profile verdict, now superseded by C7-P.** Section 11 and section 12.1 make
  `aarch64-unknown-linux-gnu` and `aarch64-apple-darwin` *required* C7 acceptance environments, and
  during that wave neither had a reviewed profile, so every run on this macOS host was development
  evidence only. C7-P delivered both profiles and recorded their discharge in sections 11.2 and
  11.3, so a host reproducing the recorded identities now produces C7 acceptance evidence rather
  than development evidence. The x86_64 Section 9 profile still substitutes for neither target.

## Merged checkpoint: C6-MEASURED (2026-08-25)

- C6-MEASURED (C6e/C6g1/C6g2) was implemented on branch `agent/c6-measured` and merged as
  align-llm PR #103 (`c9a510d`). One comprehensive adversarial review returned request-changes at
  `535be1087622dfd05481503d5f5d933555c06953`; every finding was accepted and repaired, and the
  consolidated repair is `baf8c24` (validator bindings, adapter deadline and redaction order),
  `3ca42d8` (claim narrowing and lane/post-freeze records), `1d27b5f` (frozen-chain rebind),
  `99a6ba7` (Align evaluator wrapper digest), `c737adc` (a second credential-code expectation),
  `e935790` (regenerated gate evidence), and `e14c472` (measurement record). The measured gate is
  real and green at the repaired head: `make prompt-gate-check` with all five explicit `C6_GATE_*`
  values exits 0 (`prompt gate validator: PASS`) against the regenerated `eval/prompt/gate/` bundle.
- **Resolved: the supervised fresh-worker `make ci` passes.** At head
  `3768ad8af68bb50ee3129ff392f6ba86ac89e071`,
  `python3 scripts/run-fresh-worker-qualification --installed-profile-only --require-docker
  --align-repo <path-to-sibling-align-checkout>` exits 0 with `fresh worker qualification: PASS
  (installed profile only)`. The blocker had two independent causes, both C6-MEASURED lane
  additions that the supervised aggregate had never exercised — its last green run predates them —
  so both were pre-existing wave gaps rather than review-repair regressions.
- **Cause 1, removed: resource pressure from `prompt-verifier-smoke`.** A high-fidelity
  reproduction of the exact aggregate environment ran `make capable-checks` to `exit=0` in 890 s
  with a clean workspace-upper (only `./main`), of which roughly 780 s was that one smoke. The
  pinned compiler needs about 720 s and a 1,525,732 KiB peak resident set to code-generate
  `src/prompt_verifier_smoke.align`, against 0.494 s for `alignc check` of the same unit. The
  member was demoted to a named focused qualification (see the lane entry below), and the aggregate
  cost came back inside its historical band.
- **Cause 2, removed: `prompt-measurement-adapter-smoke` could not find `git`.** Its patch row
  builds a pinned checkout and runs `git apply` over the adapter's synthesized bytes, and it
  launched that fixture with a hard-coded child `PATH=/usr/bin:/bin` plus a bare `git` argv. Python
  resolves a bare program name against the *child* environment's PATH, and the fresh aggregate puts
  only its staged tool root on PATH, so the row died with
  `prompt measurement adapter: FAIL: [Errno 2] No such file or directory: 'git'` and took
  `capable-checks` down with `make[1]: *** [Makefile:129: prompt-measurement-adapter-smoke] Error 1`.
  `3768ad8` resolves that fixture PATH from `ALIGN_LLM_TOOL_ROOT`, exactly as
  `scripts/check-baseline-chain` already does, with the previous fixed host directories as the
  default. The whole class was audited across the aggregate's goal list: every other bare-name child
  launch in the lane either inherits the aggregate environment or already derives its PATH from the
  tool root, and the remaining hard-coded `/usr/bin:/bin` occurrences launch absolute paths the
  aggregate provides.
- **The aggregate diagnostic seam is now reachable end to end (`e4c7e45`).** One optional entry,
  `ALIGN_LLM_AGGREGATE_DIAGNOSTIC=1`, is forwarded — never synthesized — across every launch
  boundary that previously rebuilt the environment from fixed literals: `fresh-supervise.c` beside
  its five-variable allowlist, `fresh-bootstrap.c` beside its five fixed entries,
  `fresh_image_control.py`'s bootstrap and worker environments, and the worker's
  `EXPECTED_ENVIRONMENT` admission via `environment_admitted()`. On failure the worker emits the
  bounded tail of the aggregate child's streams and the controller emits the bounded tail of the
  worker's stderr, both before the canonical `fresh compiler: ERROR <category> <phase>` line and
  both capped at 8,192 bytes. With the entry absent every environment, stream, status, and byte of
  output is exactly what it was before. This is what named cause 2: the diagnostic run printed the
  failing target and its error verbatim. `run-fresh-image-control-smoke` and
  `run-fresh-worker-unit-smoke` pin both halves, and
  `docs/specs/check-gate-topology.md` records the contract. Use it by exporting the variable before
  the qualification; it costs one extra qualification run and nothing else.
  `run-fresh-worker-qualification` forwards it only to the installed-profile owner
  (`run-fresh-image-profile-smoke`), the one phase that reaches the worker aggregate; the focused
  owners keep their unchanged qualified environments.
- Slice E landed the final integration wiring. The section 11.3 owner targets are now
  `HOSTED_CHECK_TARGETS` members — `prompt-seed-attestation-smoke`, `prompt-experiment-smoke`,
  `prompt-generate-smoke`, `prompt-measurement-adapter-smoke`, `prompt-credential-lifetime-smoke`,
  the nine `prompt-gate-*-smoke` fixtures, and `c6e-request2-adoption` — and
  `scripts/check-gate-topology`'s literal `EXPECTED` lane bytes were refreshed in the same commit
  `6f937fb4bb4a596afd0540b5b37415d65d5dbb3c`, per the section 11.1 precedent.
- `prompt-gate-check` is the C6-MEASURED gate target. It takes the five explicit `C6_GATE_*`
  command-line values, fails closed before the validator starts when any is missing or empty, and
  maps them to `--source-bundle-root`, `--python-executable-path`, `--git-executable-path`,
  `--generation-child-path`, and `--generation-child-sha256`. The declared interpreter is also the
  launcher, so the target never reaches the validator through an ambient Python or Git.
- **Closed: the gate is a named capable qualification.** `prompt-gate-check` stays out of
  `CAPABLE_ONLY_CHECK_TARGETS`. Section 9 and section 11.3 of
  `docs/specs/c6-prompt-context-optimizer.md` previously required the gate to run as
  `make ci C6_GATE_...=...`, but the settled FRESH-WORKER caller contract in
  `docs/specs/check-gate-topology.md` admits exactly `make --no-print-directory ci` **with no
  variable assignments**, and the worker runs the `capable-checks` graph inside bwrap under a
  cleared, fixed environment, so the five explicit values cannot cross that boundary. Both sections
  now name `make prompt-gate-check` with the five explicit `C6_GATE_*` values as the measured
  gate's named capable qualification — a focused qualification the supervised aggregate does not
  reach — leaving the FRESH-WORKER contract and the `make ci` goals unchanged.
- The Makefile change invalidated the identity-bound canonical baseline chain, which requires the
  working-tree `Makefile` to equal its source commit's blob. The chain was already red at
  `19c5d5c` because earlier C6-MEASURED commits changed the Makefile without re-finalizing. The
  replacement chain is source `6f937fb4bb4a596afd0540b5b37415d65d5dbb3c`, oracle
  `182fa3c9a537884f59cf9257d91c884d3732d1ca`, and finalization
  `7273f65bfc1a2604daf37b2bd7748a46d2bd59f2`; it was appended, not rewritten. Adding
  `prompt-render-parity-smoke` to the lane changed the `Makefile` again, so the next chain was
  source `ba47abdb01776d10f041c0d3e3f36edc67034993`, oracle
  `656a5bf9609762b899c4e841de7529bfde2ec5c2`, and finalization
  `8ddea8a03b817404e68a23e8ce1f39534b7abd13`; it was appended the same way. Removing
  `prompt-verifier-smoke` from the lane changed the `Makefile` once more, so the **current** chain
  is source `ebcc8d5c384c9a6c30619637018c7c9d07270192`, oracle
  `f5158d5741bc912dbc0324f5138eb7e8c216a6dd`, and finalization
  `55282a8` — appended, never amended — recorded on native Linux `aarch64` in the privileged
  `c6g2-measure:latest` container with `bubblewrap` installed, non-root, `umask 022`,
  `PYTHONDONTWRITEBYTECODE=1`, on a clean clone of the source commit. Both deterministic-reference
  samples pass: 134,471,000-140,342,375 ns, median 137,406,687 ns.
  `scripts/check-baseline-chain` passes on it.
- **`prompt-verifier-smoke` is no longer a hosted-lane member.** It stays a `.PHONY` public target
  and the direct C6c2 owner with unchanged coverage, and is now a **named focused qualification**
  owned by the section 10 verifier boundary in `src/prompt_score.align`: run
  `make prompt-verifier-smoke` when that boundary changes and before publishing such a change. It
  is not reached by `hosted-checks`, `capable-checks`, or `ci`. The same change refreshed the
  `Makefile` list, `scripts/check-gate-topology`'s `EXPECTED` bytes and `exact_environment()`
  self-test copy, the `docs/specs/check-gate-topology.md` `hosted=` oracle and prose, section 11.3
  of `docs/specs/c6-prompt-context-optimizer.md`, and the baseline chain. The compiler-side gap is
  recorded as `docs/align-requests.md` Request 19 (`PROPOSED`, non-blocking); the member rejoins the
  lane when it closes.
- **Closed: `prompt-render-parity-smoke` is no longer an orphan.** It is now a
  `HOSTED_CHECK_TARGETS` member beside `prompt-model-smoke`, section 11.3 names it as the
  renderer-parity owner, and the same change refreshed the `EXPECTED` lane bytes, the
  `exact_environment()` self-test copy, and the baseline chain.
- `c6f2-request14-adoption` is timing-flaky on a fast, quiet host. Its publication-race fixtures poll
  for a staged temporary file inside a five-second window; when the fixture binary completes before
  the poll observes staging, the run reports "publication race did not reach evidence staging" or
  "result-only cleanup fixture did not reach staging". It passed on retry in the final capable gate
  and it is a pre-existing C6-EVALUATION owner, not a Slice E regression, but the fixture needs a
  deterministic seam rather than a poll.
- The frozen `eval/prompt/canonical-v1/` scope now names a real provider: `LOCAL_OPENAI` on
  `http://127.0.0.1:18080/v1/chat/completions`, model `qwen2.5-coder-7b-instruct-q4_k_m`,
  `api_key_env: null`. `provider_service_revision` carries llama.cpp `b10610` /
  `a14dba686aaafba3a2d6b5eb8820b0df5c5d2d92`, the `llama-server` digest, and the model digest.
- Measured result (`c6g2-measure`): `IMPROVED`, `gate_eligible: true`, zero serious regressions,
  completion gain 2. `duration-half-away-from-zero` moves 0/2 -> 2/2 under a model-proposed
  candidate that enables the context sections; the other two tasks fail in both variants.
  `paired_pass_count` is 0 for every task and for the corpus, so the evidence carries **no** paired
  timing and therefore no time-to-passing-patch comparison; acceptance is the section 8
  completion-gain path alone. Section 11.3's "What the measured claim is and is not" states the
  narrowed claim.
- Reproducible baseline: the parent-vs-parent null replicate `c6g2-replicate`, same frozen corpus,
  same command and provider environment, distinct variant identifiers over a byte-identical rendered
  prompt. Result `NO_IMPROVEMENT`, `gate_eligible: false`, every task 0/2 in both variants, corpus
  `completion_gain_count: 0` — it flipped no cell. Reproducing command, inside the privileged
  `c6g2-measure:latest` container at project root `/work/align-llm`:

  ```text
  ./main prompt evaluate run/evaluate-request-replicate.json run/result-replicate.json
  ```

  The request is built by the replicate driver, which copies the parent effective variant into the
  candidate slot under `c6g2-replicate/variant` and `c6g2-replicate/candidate` and otherwise reuses
  the measure request verbatim. At the review-repaired measuring commit
  `c737adcf905cb4662472bc86e8345bbcd9bc1346` the replicate result digest (SHA-256 of the exact
  `run/result-replicate.json` bytes) is
  `b1d68148c5bfc3e86c2a022620d10dc95a79b3f685da8a5ceca4d1341898420d`, its evidence sidecar is
  `c2854e7546e9b31b03f99337ee935f07e99efe7dbbe7aea8aa72c28bc0b69f03`, and wall time is 444.1 s. The
  superseded pre-repair replicate at `6da28d88327797649bbf229f14be9be1e6dd2d96` was
  `e111201e8096ac5a64fb7c5522c0dae2c3b70f81645c4cffe8a5afb85c790eca` with sidecar
  `0aafe8d62e9622c02b5d3baaaa94faf07084daa1bcd14e234235f5c8225a07c5` and wall time 520.2 s, and
  reported the same null result. The replicate artifacts are diagnostics, not repository state, and
  are not checked in.
- The gate run found and repaired five shipped defects no fixture reaches: three canonical
  `Option::None`-omission mismatches (experiment-result decode, aggregate optional set, and the
  activation-lineage identity the gate validator compared against the envelope instead of the
  nested activation), a stale `c6-prompt-state` fixture that left `prompt-state-smoke` red on the
  hosted lane at `52aefeb` and `19c6bed`, an overlapping automatic snapshot path set, and a 2 MiB
  sealed-input cap that could never admit the derived generation child. Repairing the measurement
  adapter rebound the frozen digest chain; only digest bindings moved.
- Next actions, in order: (1) publish the C6-MEASURED pull request with the narrowed measured
  claim, the per-cell matrix, the validator transcript, the named-qualification status of
  `prompt-gate-check`, and the green supervised fresh-worker qualification recorded above — the
  earlier `capable-checks` aggregate blocker is resolved, so `make ci` evidence is available;
  (2) after merge, start `C7-PersistedResult` (`docs/specs/roadmap.md` §C7), the owned-result
  verification consumer that adopts Request 9's owned-JSON surface from the current pin.
- The measurement environment is a privileged `linux/arm64` container (`c6g2-measure:latest`) with
  `bubblewrap` installed at run time; the image does not ship it and the validation runner requires
  it. Docker's default seccomp/AppArmor blocks the runner's user namespaces, so the container needs
  `--privileged`. Both are environment facts, not repository state.
- C6-EVALUATION merged as align-llm PR #100
  (`282062bf00416f5e0df678b8bd885709084b4e16`); its final capable integration gate passed at head
  `049172f5be57002c2426f012fe23038f570f5069` in pull-request CI run 32490981785, including both
  installed native profiles; main push run 32493880784 reused that exact evidence on the merge
  commit. `.align-revision` remains pinned to Align
  merge `19c3db144c462bf7d6784f88d64cc124229b7ec2` at that time; C6-MEASURED then bumped it to
  Align merge `2f33ac5c33a898a7894af58322852632ce6ffe42` in commit `f344ea9`, which is the pin every
  Slice E result below was produced against.
- Align-llm PR #94 merged as `ba56ebed5ac1c82ebc5925e6257e7bd5dba8a9b9`, with the C6a1/C6a2
  graph-and-codec capability pinned to Align merge `a440970ac81118ed2169f600b2b3c06fcb9cde7`.
- The register records Requests 2, 7, 8, and 10–18 as `ALIGN_LLM_VERIFIED`; the merged C6-EVALUATION
  gate advanced Requests 11 and 14, and C6-MEASURED Slice E advanced Request 2 once
  `c6e-request2-adoption` and the wave's final capable gate both passed. Request 9 advanced to
  `ALIGN_LLM_VERIFIED` in the merged C7-PERSISTED-RESULT wave at the unchanged pin. C6-MEASURED
  added Request 19, a compiler code-generation performance gap, and C7-P added Request 20, the
  missing macOS leg for Request 9's own `m5_owned_json` boundary regressions in Align CI; those two
  are the register's only `PROPOSED` entries and neither blocks. Every other open Align request has
  a merged Align-side surface, and none is `ACCEPTED` or `IMPLEMENTING`.
- The merged C6-EVALUATION capability drives the deterministic two-task corpus through source/workspace verification,
  alternating parent/candidate execution, fixed contained adapters, before/after snapshots, strict
  prefix verification, and immutable result/evidence publication. Invalid pre-execution inputs are
  result-only; operational failures retain the exact valid trace prefix and paired evidence. Its
  review reopened exact interpreter identity, descendant ownership, FILE_SET physical traversal,
  nested deadline hierarchy, pre-allocation result binding, validation precedence, and capable-gate
  execution as one runtime-containment axis. The final ownership review additionally reopened exact
  per-invocation workspace admission, cleanup-before-pair construction, immediate publication-owner
  retirement, and bounded FILE_SET decimal decoding on that same axis. The merged implementation binds
  and descriptor-launches the exact CPython/helper/Git bytes, gives nested owners cleanup/report
  margins, streams canonical result binding, proves private process-group absence, admits only the
  current invocation's four workspace names, constructs terminal evidence after owned cleanup,
  retains FILE_SET roots/manifests/final files, and executes the complete evaluator adoption owner
  inside capable-only `make ci`. The later exact-head review reopened the inner retained-input and
  admission-bounds axis: the fixed adapter now executes sealed admitted runner bytes and passes
  sealed task/patch descriptors, artifact schemas are complete before side effects, reviewed TREE
  enumeration is bounded while it occurs, and publication uses a fixed-size content-bound sibling.
  The replacement review then reopened semantic consumption; prompt limits, complete persistent
  drift, snapshot declaration caps, unavailable-source non-gate execution, and containment-first
  measurement validation now follow the already-settled contract.
- Align-llm PR #96 merged as `df8b872d1ed766b5bbca643729bb2dfdb08bde3`. C6d now builds on that
  decoded verifier: `prompt accept` verifies result/evidence before constructing an immutable
  activation, `prompt rollback` validates immutable lineage, and both commands use retained-root
  reads plus exclusive result creation. Evaluator/provider execution remains in the named later
  waves.
- The managed exact-pin compiler materializes successfully. PR #94's owner wave, hosted checks,
  fresh-focused qualification, and both installed native profiles passed at head
  `954258e24d93300dcdb78f8280de8868cf1ced56`; main push CI run `32111007638` reused that exact
  evidence on merge commit `ba56ebed5ac1c82ebc5925e6257e7bd5dba8a9b9`.
- Align PR #812 merged the bounded `std.http` response implementation as
  `5aa5b23ace02109ad5ef9c36ba6d2acaba9ae7ad`. PR #90 pins that exact merge, adopts the shipped
  bounded/chunked provider surface, and closes Requests 4 and 5.
- The managed release compiler/runtime for the new pin materialized under `dev-v1` as a native
  Mach-O `arm64` compiler with `CARGO_BUILD_JOBS=1`. It passes
  `./scripts/alignc check-per-unit src/main.align`: all 15 units pass with the three existing
  lossy-conversion/large-copy warnings.
- The FRESH-IMAGE-REQUEST6 installed adoption profile is merged and passes its complete native
  Linux `aarch64` and `x86_64` profiles. Request 6 is now `CLOSED`.
- Align PR #801 shipped Request 8 as `029e27465d79e24cd36d374aae41dca0ec7e6979`, and Align PR #804
  shipped Request 10 as `3ec710656c7ce7412da14a5c929529cb3e89caa3`. Align PR #800 shipped
  Request 4 as `f04672bce6f8689c9b219d0a20e770571e2d638b`, PR #808 shipped Request 11 as
  `82da9f580cc005fbb78f67af6847c7b4ce6626c4`, and PR #807 shipped Request 12 as
  `c37d79a180612c345551e259091b0b5acf2cb9cd`. Requests 4 and 5 are `CLOSED`; Requests 8, 10, 11,
  and 12 are `ALIGN_LLM_VERIFIED`; Request 11 advanced when the merged C6-EVALUATION gate passed
  in PR #100.
- FRESH-IMAGE, FRESH-WORKER, and FRESH-IMAGE-REQUEST6-BOUNDARY are merged. The migrated profile
  preserves current authenticated cgroup cleanup, phase tracking, multistage image construction,
  and the `25b1201b...` pin while adding the ordinary adoption dispatcher, namespace helper,
  compiler handoff, installed-profile bindings, fixtures, and owner tests.
- The installed profile supports one native-platform capability for Linux `x86_64` and `aarch64`.
  The immutable Ubuntu OCI index, native Rust/Debian/ELF/loader tuple, manifest
  admission, runtime roots, controller, worker, Docker owner, and CI matrix now reject
  architecture mismatch; emulation is explicitly non-acceptance evidence.
- PR #84's final reviewed head is `031917b5518170f905793af65b9cb347b837d178`; its consolidated
  repair commit is `d50373fc14afe2994176bc26fdaa55ad5e9c64b2`.
- The native ARM installed profile now passes image attestation, lifecycle, self-test, trust
  mutations, runtime replacements, the valid ordinary Request 6 consumer, the complete boundary
  rejection matrix, the worker aggregate, and cleanup.
- Baseline commits `db2c88d24574` and `cceaf15fdf0c` intentionally remain historical failed
  measurement evidence: the first ARM helper lacked `/usr/bin/bwrap`, so both recorded tasks were
  non-passing and remain unacceptable as baseline evidence.
- The failed chain and its first passing replacement were superseded after a later full-profile run
  exposed a separate resource bug: after roughly 8.5 GB of authenticated runtime copying, Cargo
  inherited all eight Docker CPUs and `rustc align_sema` was killed with `SIGKILL` in the 8 GB VM.
  Source `cbcde22600e7` introduced `CARGO_BUILD_JOBS=1` in both fresh compiler build paths; the
  current policy retains that bound only on native `aarch64`, while native `x86_64` omits the
  override and uses Cargo's default parallelism. Native ARM
  oracle `12cce0199762` records two passing samples, and finalization `be0131f85c3c` owns the matching
  canonical baseline and digest. `scripts/check-baseline-chain` passes on that exact chain.

## Contract and decisions to preserve

- `align-llm` is a continuing real-client testbed for Align. During every capability, record any
  genuine Align language, compiler/runtime, or standard-library requirement in
  `docs/align-requests.md`, even when non-blocking or temporarily avoidable in the application; do
  not let an application workaround hide a language-owned gap.
- `.align-revision` is the only implicit compiler selector. Ordinary commands use the managed exact
  pin; `ALIGNC` and `ALIGN_REPO` remain explicit overrides.
- ALIGN-ADOPTION remains an ordered checkpoint inside a consuming capability, not a pin-only pull
  request. The merged bounded provider-response consumer applies the cap, switches real provider
  fixtures to chunked framing, and owns the combined Requests 4/5 acceptance gate.
- C6-LIFECYCLE has completed the Request 7/8/10/12/13/15 adoption wave in PR #94, Requests 16/17
  through the real decoded verifier, and Request 18 through the C6d retained-root lifecycle owner.
  The public verifier keeps its settled borrowed signature and no compatibility API was added.
  Requests 11 and 14 are adopted by the contained evaluator and pair-publication owners. Requests
  4–6 are closed with real-client and native installed-profile evidence.
- Preserve the exact fresh-image trust, descriptor, namespace, cgroup, source-identity, and cleanup
  boundaries in `docs/specs/check-gate-topology.md`. Reclassify and update its closure matrix if the
  migrated diff changes those contracts.
- Future resource tuning may replace the temporary architecture-specific Cargo job policy with an authenticated
  `--cargo-build-jobs auto|N` profile input. The candidate automatic policy is the smaller of
  `max(1, effective CPU affinity count - 1)` and a conservative budget derived from the cgroup hard
  memory limit, with physical memory only as an unlimited-cgroup fallback. An explicit value would
  remain bounded by effective CPUs and the qualified memory budget, and the resolved value would be
  recorded in execution and baseline evidence. This is a deferred design note, not an implemented
  or accepted contract. The canonical native ARM profile remains fixed at `CARGO_BUILD_JOBS=1`
  until multi-job memory measurements justify a change; native x86_64 currently uses Cargo's
  default parallelism as qualified by the 128 GiB owner.

## Latest durable verification

- **ADAPTER-ZOMBIE review-repaired C6g2 gate, green (native Linux `aarch64`, 2026-08-25).** This is
  the current evidence and supersedes the `b336017` block below. Measured at the rebind head
  `762b1d0f068a10774ff976b1889ddacf483321a5`; the evidence is committed as `6537482`. Same
  environment as both earlier runs: the privileged `c6g2-measure:latest` container with `--init`,
  `bubblewrap` installed at run time, a non-root uid, `umask 022`, `PYTHONDONTWRITEBYTECODE=1`, the
  model copied onto the container filesystem, and `LOCAL_OPENAI` on a co-located `llama-server` at
  `http://127.0.0.1:18080/v1/chat/completions`, model `qwen2.5-coder-7b-instruct-q4_k_m`. The served
  build and weights match the frozen `provider_service_revision` exactly: llama.cpp `b10610` /
  `a14dba686aaafba3a2d6b5eb8820b0df5c5d2d92`, `llama-server`
  `e3905073c4322ff33c7b365c9ea10aadbc776fe3eab372869694555d8f5693a8`, model
  `509287f78cb4d4cf6b3843734733b914b2c158e43e22a7f4bf5e963800894d3c`. The server ran
  `--parallel 1 -c 16384` on 8 threads over the 8 logical CPUs the environment probe records, and
  every prompt reported `truncated = 0`. Generation child built in run:
  `6650e4486ec8b205604e6348cd9dd81f7370b478a7ed1cf7607ce7aa94ff2aba`.
  - **Measure (`c6g2-measure`), 595.0 s: `IMPROVED`, `gate_eligible: true`,
    `serious_regression_reasons: []`, corpus `completion_gain_count: 2`.**
    `duration-half-away-from-zero` 0/2 parent to 2/2 candidate; `layer-precedence-frozen-module`
    and `record-codec-round-trip` fail in both variants. `paired_pass_count` is 0 for every task
    and for the corpus, so this evidence still carries **no paired timing and no
    time-to-passing-patch comparison**; acceptance is the section 8 completion-gain path alone.
    Result `content_sha256`
    `0d8668053654d3f7fef3bcd5b2966dcaaf966315432ec4e9245b4ecb25346267`, evidence sidecar
    `bc7ed85a647a0098fb4812c69adbeb0e87132fc9704d8746bc880db9efd862aa`. Accept then rollback
    reproduce as `ACCEPTED` (`00b3cf42…`) and `ROLLED_BACK` (`cf881026…`). All three source
    reachabilities are `VERIFIED`.
  - **Reproducible baseline, the parent-vs-parent null replicate (`c6g2-replicate`), 493.0 s:**
    `NO_IMPROVEMENT`, `gate_eligible: false`, every task 0/2 in both variants, corpus
    `completion_gain_count: 0` — it flipped no cell. Result digest (SHA-256 of the exact
    `run/result-replicate.json` bytes)
    `dcd4e994f1a44c59a4e0ac96644d8adce0023b86f8e870dd2f7794f08cacd359`, evidence sidecar
    `0b77c94b70d9eae285a24aaca718401d9211c8a6ed2dc03c2c606b8a73867c03`. Same reproducing command as
    below. The replicate artifacts are diagnostics, not repository state, and are not checked in.
  - **The comparison with the superseded evidence is tighter than the previous one: no measurement
    field moved at all.** Movement is confined to digests and runtime identities, to
    `artifact_digests[].byte_count` for the three rebound scripts, and to wall-clock `*_ns` timings
    with the test-duration text they print into `diagnostic_stderr`. Every verdict-bearing cell is
    identical — `status`, `gate_eligible`, `serious_regression_reasons`, every `task_aggregates`
    entry, the whole `corpus_aggregate`, and every row's `measurement.status`. The candidate variant
    is provably the same one: its `content_sha256` `78611fbc…` is byte-identical to the variant both
    earlier measurements consumed. Only the experiment artifact's own frozen-chain references — the
    parent-activation digest and its embedded scope — were rebound with the corpus, giving artifact
    digest `435a34b9…` in place of `01b04b76…`.
  - **Three reproduction preconditions, recorded because rebuilding the lost drivers hit all
    three.** The measurement drivers are diagnostics and were never checked in, so they were
    reconstructed from the embedded copies in the checked-in evidence. (1) `observe_git` requires an
    empty `git status --porcelain=v1 -z --untracked-files=all` in **both** the align-llm and the
    Align repository. The run's own `run/` outputs are untracked and `run/` is not in `.gitignore`,
    so the working clone needs `run/` in `.git/info/exclude` (local, uncommitted). (2) The Align
    checkout must be owned by the running uid, because a root-owned checkout trips git's
    dubious-ownership guard. Either of those degrades the affected reachability to `UNVERIFIED`,
    which silently drops `gate_eligible` to false while still reporting `IMPROVED` with identical
    aggregates — the first attempt produced exactly that and was discarded. (3) The evaluate
    request's `verifier_source_policy_path` must name the **same** `PROMPT_SOURCE_VERIFIER_POLICY`
    document the gate bundle carries, `policy_id: prompt-v1-gate-source-policy-v1`; a
    differently-named policy over identical helper bytes produces a different digest and the
    validator rejects the evidence with `evaluation environment source_verifier_policy_sha256
    disagrees with the gate locator`. That policy id was recovered by solving the previous
    locator's recorded digest against the known helper, interpreter, and Git digests. Only the run
    that satisfies all three is checked in.
- **Superseded: ADAPTER-ZOMBIE re-measured C6g2 gate (native Linux `aarch64`, 2026-08-25).** Kept
  as history; the block above is the current evidence. Measured at
  the rebind head `bf844f821a45464e67ed30eafe025c31dfb2c4e5`; the evidence was committed as
  `b336017`. Environment identical to the superseded run: the privileged `c6g2-measure:latest`
  container with `--init`, `bubblewrap` installed at run time, a non-root uid, `umask 022`,
  `PYTHONDONTWRITEBYTECODE=1`, the model copied onto the container filesystem, and `LOCAL_OPENAI`
  on a co-located `llama-server` at `http://127.0.0.1:18080/v1/chat/completions`, model
  `qwen2.5-coder-7b-instruct-q4_k_m`. Generation child built in run:
  `903f38004ac3c935b0ca41c70f94f77b274bdb84adebe3873a1aec70be59bf72`.
  - **Measure (`c6g2-measure`), 685.2 s: `IMPROVED`, `gate_eligible: true`,
    `serious_regression_reasons: []`, corpus `completion_gain_count: 2`.**
    `duration-half-away-from-zero` 0/2 parent to 2/2 candidate; `layer-precedence-frozen-module`
    and `record-codec-round-trip` fail in both variants. `paired_pass_count` is 0 for every task
    and for the corpus, so this evidence still carries **no paired timing and no
    time-to-passing-patch comparison**; acceptance is the section 8 completion-gain path alone.
    Result digest `1b2164dc8acebf25ae815e87d9aa9b3b9fb25be99917b57658b6462fb1a281cc`, evidence
    sidecar `7c2d48b571377f20918dc2a8d0ce6d68372c2ca440a10bd997009b3f2e8a9f80`. Accept then
    rollback reproduce as `ACCEPTED` and `ROLLED_BACK`.
  - **Reproducible baseline, the parent-vs-parent null replicate (`c6g2-replicate`), 637.6 s:**
    `NO_IMPROVEMENT`, `gate_eligible: false`, every task 0/2 in both variants, corpus
    `completion_gain_count: 0` — it flipped no cell. Result digest
    `56a4f367b054db8471500bb61921e169270b36bc5e7d54ed608eb7272d05c87a`. Reproducing command, in
    the same container at project root `/work/align-llm`:

    ```text
    ./main prompt evaluate run/evaluate-request-replicate.json run/result-replicate.json
    ```

    The replicate artifacts are diagnostics, not repository state, and are not checked in.
  - **The comparison with the superseded evidence is cell for cell identical.** Same verdicts, same
    per-task pass counts, same `completion_gain_count: 2`, same empty serious-regression array,
    same all-zero `paired_pass_count`, and the same null replicate verdict. The candidate variant
    is provably the same one: its `content_sha256` `78611fbc…` is byte-identical to the variant the
    superseded measurement consumed, taken from the checked-in evaluation. Only the experiment
    artifact's own frozen-chain references — the parent-activation digest and its embedded scope —
    were rebound with the corpus, giving artifact digest `01b04b76…` in place of `4dfe5fe7…`.
    **Correction (review finding F3): "everything that moved is a digest plus wall time" was
    wrong.** Besides digests, runtime identities, `align_llm_commit` and timings, two measurement
    fields moved on the `record-codec-round-trip` **parent** row, sample 1 (`rows[8]`, not a
    candidate row): `patch_size_bytes` went 1036 to 1008, and `diagnostic_summary`'s applied-edit
    list went from `src/encode.py` to `src/decode.py, src/encode.py`. Every snapshot's
    `artifact_digests[].byte_count` also moved for the three rebound scripts, since their bytes are
    what the rebind was for. Both variants fail `record-codec-round-trip`, so no verdict-bearing
    cell moved: the verdict-bearing cells were and remain identical.
- **ADAPTER-ZOMBIE review-repair owner verification (2026-08-25).** At the evidence head `6537482`,
  with the working tree carrying only this documentation change. Linux rows ran in the privileged
  `c6g2-measure:latest` image with `bubblewrap` installed at run time, non-root with `umask 022` and
  `PYTHONDONTWRITEBYTECODE=1`; the repaired scans are Linux-only, so all three helper owners fail on
  Darwin for that reason at the base commit too.
  - Repaired-file owners, all **PASS**: `test-prompt-fixed-adapter`, `test-prompt-snapshot-helper`,
    `test-prompt-source-verifier`, `run-prompt-measurement-adapter-smoke` (**74** rows, up from 73),
    `run-prompt-evaluate-smoke`, and all nine `prompt-gate-*` families.
  - Regression neighbours, all **PASS**: `prompt-experiment-smoke`, `prompt-seed-attestation-smoke`,
    `prompt-generate-smoke`, `prompt-credential-lifetime-smoke`, `prompt-render-parity-smoke`
    (58 vectors byte-equal), `prompt-state-smoke`.
  - Host (macOS, managed pinned toolchain), all **PASS**: `gmake check` (23 units per-unit),
    `gmake format-check`, `gmake gate-topology-check` (`check gate topology: PASS`; no lane member
    changed), `gmake provider-smoke`, `gmake persisted-result-smoke`, `git diff --check`, and
    `python3 scripts/check-baseline-chain` (`baseline chain: PASS` — the `Makefile` is untouched, so
    the identity-bound chain stands).
  - **The new row is a negative control in all six files.** With the `Threads:` discriminator
    removed in one scan at a time — `return state == "Z"` in place of
    `return state == "Z" and tasks == 1` — each owner fails with `a zombie leader with a live worker
    thread was not reported as a live descendant` (the measurement adapter reports the same message
    under its `zombie-leader-descendant` label). The evaluator's control also rebinds
    `EVALUATOR_SOURCE_SHA256` for the mutated bytes, so it fails on the row and not on the digest
    gate. In every control the terminated-zombie row and the live-descendant row still pass, so the
    control isolates the discriminator and not the containment guarantee.
- **ADAPTER-ZOMBIE review-repaired gate qualification, green, at head
  `65374827f4fc901ead4e777b680ce8692d5805e8`.** Same container, clean clone (`dirty=0`), bundle
  built from a clean align-llm mirror at that head plus a clean Align checkout at
  `2f33ac5c33a898a7894af58322852632ce6ffe42` (`dirty=0`). The generation child rebuilt in run
  reproduced the locator's frozen digest
  `6650e4486ec8b205604e6348cd9dd81f7370b478a7ed1cf7607ce7aa94ff2aba` exactly. Both forms pass:

  ```text
  /usr/bin/python3.12 scripts/prompt-gate-validator.py \
    --source-bundle-root /tmp/bundle \
    --python-executable-path /usr/bin/python3.12 \
    --git-executable-path /usr/bin/git \
    --generation-child-path /tmp/bundle/align-llm/main \
    --generation-child-sha256 6650e4486ec8b205604e6348cd9dd81f7370b478a7ed1cf7607ce7aa94ff2aba
  -> prompt gate validator: PASS (exit 0)

  make prompt-gate-check C6_GATE_SOURCE_BUNDLE_ROOT=/tmp/bundle \
    C6_GATE_PYTHON_EXECUTABLE_PATH=/usr/bin/python3.12 \
    C6_GATE_GIT_EXECUTABLE_PATH=/usr/bin/git \
    C6_GATE_GENERATION_CHILD_PATH=/tmp/bundle/align-llm/main \
    C6_GATE_GENERATION_CHILD_SHA256=6650e448...94ff2aba
  -> prompt gate validator: PASS (exit 0)
  ```

  The bundle holds `align-llm/`, `align/`, `scripts/prompt-source-verifier.py` at mode 0644, and the
  `prompt-v1-gate-source-policy-v1` policy document — the same one the evaluate request consumed.
- **Publication preflight, both fresh legs, and the supervised installed profile run at the exact
  publication head and are recorded in the pull request**, not here: a `pre-pr` stamp belongs to an
  unchanged `HEAD`, so it cannot be committed into the head it certifies. This branch changes
  `src/*` and `eval/*`, so the wave classifies `fresh-image` and both compensating legs are re-run
  rather than argued from a head delta.
- **Superseded: ADAPTER-ZOMBIE gate qualification, green, at head
  `b3360171e965568af59aabaec14f89c6b5b60602`.** Same container, clean clone, bundle built from a
  clean align-llm mirror at that head (`dirty=0`) plus a clean Align checkout at
  `2f33ac5c33a898a7894af58322852632ce6ffe42` (`dirty=0`). The generation child rebuilt in run
  reproduced the locator's frozen digest exactly. Both forms pass:

  ```text
  /usr/bin/python3.12 scripts/prompt-gate-validator.py \
    --source-bundle-root /work/bundle \
    --python-executable-path /usr/bin/python3.12 \
    --git-executable-path /usr/bin/git \
    --generation-child-path /work/align-llm/main \
    --generation-child-sha256 903f38004ac3c935b0ca41c70f94f77b274bdb84adebe3873a1aec70be59bf72
  -> prompt gate validator: PASS (exit 0)

  make prompt-gate-check C6_GATE_SOURCE_BUNDLE_ROOT=/work/bundle \
    C6_GATE_PYTHON_EXECUTABLE_PATH=/usr/bin/python3.12 \
    C6_GATE_GIT_EXECUTABLE_PATH=/usr/bin/git \
    C6_GATE_GENERATION_CHILD_PATH=/work/align-llm/main \
    C6_GATE_GENERATION_CHILD_SHA256=903f3800...be59bf72
  -> prompt gate validator: PASS (exit 0)
  ```

  The same qualification was re-run unchanged at the documentation head
  `fd44514212c9989c5c60db1432822fb216f96018` and again after it, each time rebuilding the
  generation child in run to the same digest and each time reporting `prompt gate validator: PASS`.
  Every commit after `b336017` is Markdown only, so no input the validator, the preflight, or
  either fresh leg consumes has moved.

- **ADAPTER-ZOMBIE owner verification (2026-08-25).** Linux rows ran in a privileged
  `python:3.12-bookworm`-derived container with `bubblewrap`, and the Align-dependent rows in the
  `c6g2-measure:latest` image at the pinned compiler; the repaired scans are Linux-only, and all
  three helper owners already fail on Darwin for that reason at the base commit.
  - Repaired-file owners, all **PASS**: `test-prompt-fixed-adapter`,
    `test-prompt-snapshot-helper`, `test-prompt-source-verifier`,
    `run-prompt-measurement-adapter-smoke` (73 rows), `run-prompt-evaluate-smoke`, and all nine
    `prompt-gate-*` families.
  - Regression neighbours, all **PASS**: `prompt-experiment-smoke`,
    `prompt-seed-attestation-smoke`, `prompt-generate-smoke`,
    `prompt-credential-lifetime-smoke`, `prompt-render-parity-smoke`, `prompt-state-smoke`.
  - Host (macOS, managed pinned toolchain), all **PASS**: `gmake check` (23 units per-unit),
    `gmake format-check`, `gmake gate-topology-check` (`check gate topology: PASS`; no lane member
    changed), `gmake provider-smoke`, `gmake persisted-result-smoke`, `git diff --check`, and
    `python3 scripts/check-baseline-chain` (`baseline chain: PASS` — the `Makefile` is untouched,
    so the identity-bound chain stands).
  - **Every regression has a recorded negative control.** With the repair reverted in that one
    file, each owner fails on its new row: the four `owned_descendant_ids` unit rows report `an
    adopted zombie was counted as a live descendant`; `test-prompt-fixed-adapter`'s contained
    runner reports `an adopted zombie descendant was reported as a containment failure`;
    `prompt-measurement-adapter-smoke`'s generation-child row reproduces the exact PR #103
    diagnostic `generation child left a descendant` with `failure_kind: CONTAINMENT`; and
    `prompt-evaluate-smoke` reports `an adopted zombie was treated as an escaped descendant:
    PROCESS`. In every negative control the live-descendant row still passes, so the controls
    isolate the zombie classification and not the containment guarantee.
- **ADAPTER-ZOMBIE publication preflight and supervised gate, at the final head
  `fd44514212c9989c5c60db1432822fb216f96018` (2026-08-25).** `python3 scripts/pre-pr --owner-test
  descendant-scan -- <the repaired-file owners in a privileged Linux container>` classified the
  wave `fresh-image`, because `eval/*` changed. Phases: `descendant-scan` 18,359 ms **PASS**,
  `managed-align-ensure` 276 ms **PASS**, `pinned-align-build` 100 ms **PASS**, `hosted-checks`
  49,531 ms **PASS**. Its `fresh-focused` leg **cannot run on Darwin**:
  `scripts/run-fresh-source-identity-smoke` reads `/proc/self/fd`, and the identical failure
  reproduces on a clean clone of the base commit `a4f8663`, so it is a pre-existing host
  limitation rather than a wave regression — the same `N/A` reason C7-P recorded. Both fresh legs
  were therefore run where they belong.
  - **Focused leg, native Linux `aarch64`** in the privileged `c6g2-measure:latest` container with
    `--init`, `bubblewrap`, `clang`, and `unzip`, non-root with `umask 022` and
    `PYTHONDONTWRITEBYTECODE=1`, on a clean clone of the exact head:
    `python3 scripts/run-fresh-worker-qualification` **PASS**, exit 0 (focused; installed profile
    deferred).
  - **Installed profile, host Docker:** `python3 scripts/run-fresh-worker-qualification
    --installed-profile-only --require-docker`: **PASS**, `fresh image profile smoke: PASS` then
    `fresh worker qualification: PASS (installed profile only)`. Phases: `docker-daemon` 618 ms,
    `image-build` 22,731 ms, `image-attestation` 3,544 ms, `profile-lifecycle` 2,397 ms,
    `profile-self-test` 15,437 ms, `trust-mutations` 12,301 ms, `runtime-replacements` 21,955 ms,
    `boundary-profile` 302,596 ms, **`worker-aggregate` pass after 365,588 ms**, `cleanup`
    1,313 ms; whole installed profile 749,127 ms. Run with the default environment and no
    diagnostic opt-in. **That is this capability's `make ci` evidence.**
- **C7-P Darwin platform-profile gate, green, re-emitted at the review-repaired head
  `3e9b27e9af04d4eae616dffb812c8db926d938d8` (macOS `aarch64-apple-darwin`, 2026-08-25).** The
  repair changed the gate's own owner, which section 10.4 names as a re-run trigger, so the
  section 11.3 record is the block from this run, not the superseded `41b2f43` one.
  `LIBRARY_PATH="$(brew --prefix)/lib:$(brew --prefix openssl@3)/lib:$(brew --prefix zstd)/lib"
  make darwin-profile-gate`: **PASS**. Five acceptance commands, all exit 0 — `gmake check`
  1,266 ms, `gmake build` 276 ms, direct `alignc check-per-unit src/main.align` 1,166 ms,
  `gmake persisted-result-smoke` 3,534 ms, `gmake persisted-result-qualification` 9,325 ms. Attested
  identity: managed compiler `82e6bea0933332291012f5de43a2a65c02e8dda7dfe990602de3cce3e30c0908`,
  runtime archive `0c26b938060e747d63886f5f98c07953b69b52d2b572a538373642b96cb75211`, pin
  `2f33ac5c33a898a7894af58322852632ce6ffe42`, Homebrew `llvm 22.1.8`, `openssl@3 3.6.3`,
  `zstd 1.5.7_1`, macOS 26.5.2 (`25F84`), Darwin 25.5.0 `arm64`, `proc_translated 0`, GNU Make
  4.4.1. The complete emitted block is section 11.3 of `docs/specs/c7-persisted-result.md`.
- **C7-P publication preflight and fresh-profile evidence (2026-08-25).** At head
  `4d8aa33f3dff5553043ade5ef8eb87712d5a451c`, `python3 scripts/pre-pr --owner-test
  darwin-profile-gate -- python3 scripts/check-darwin-profile` classified the wave `fresh-image`
  (the `Makefile` and `eval/*` artifacts changed) and passed `darwin-profile-gate` (15,388 ms),
  `managed-align-ensure`, `pinned-align-build`, and `hosted-checks` (50,594 ms). Its `fresh-focused`
  leg **cannot run on Darwin**: `scripts/run-fresh-source-identity-smoke` reads `/proc/self/fd`, and
  the identical failure reproduces at the base commit `a52b9ac` in a clean worktree, so it is a
  pre-existing host limitation rather than a wave regression. Both fresh legs were therefore run
  where they belong. **Installed profile, host Docker:** `python3
  scripts/run-fresh-worker-qualification --installed-profile-only --require-docker --align-repo
  <managed-pin-source>`: **PASS**, `fresh image profile smoke: PASS` then `fresh worker
  qualification: PASS (installed profile only)`. Phases: `docker-daemon` 552 ms, `image-build`
  23,200 ms, `image-attestation` 3,680 ms, `profile-lifecycle` 2,405 ms, `profile-self-test`
  14,771 ms, `trust-mutations` 12,064 ms, `runtime-replacements` 21,692 ms, `boundary-profile`
  246,632 ms, **`worker-aggregate` pass after 363,821 ms**, `cleanup` 1,292 ms. That is this wave's
  `make ci` evidence. **Focused qualification, native Linux `aarch64`** in the privileged
  `c6g2-measure:latest` container with `--init`, `bubblewrap`, `clang`, and `unzip`, non-root with
  `umask 022` and `PYTHONDONTWRITEBYTECODE=1`, on a clean clone of the same head: `python3
  scripts/run-fresh-worker-qualification` **PASS** (focused; installed profile deferred; 23 focused
  rows including `check-gate-topology --self-test`), `python3 scripts/test-development-preflight`
  PASS, and `python3 scripts/test-align-toolchain` PASS. Both the preflight and the installed
  profile were then re-run at `cab6755b55b6fb6d94317d3fbfa518cb0ed12061` with
  the same results — preflight phases `darwin-profile-gate` 15,143 ms, `hosted-checks` 50,434 ms,
  the same Darwin-only `fresh-focused` failure; installed profile **PASS** with `boundary-profile`
  255,854 ms and **`worker-aggregate` pass after 379,459 ms**.
- **Why the two Linux legs are not re-run for the review repair, stated as a head delta.** Both
  compensating legs are owned by the fresh-image classifier in `scripts/verification_scope.py`. The
  complete delta from `4d8aa33` (focused fresh-worker qualification, native Linux `aarch64`) and
  from `cab6755` (installed profile, host Docker) to the publication head is `HANDOFF.md`,
  `docs/align-development.md`, `docs/specs/c7-persisted-result.md`,
  `docs/specs/check-gate-topology.md`, `scripts/check-darwin-profile`, and the added
  `scripts/test-check-darwin-profile`. `owns_fresh_image()` returns false for every one of them —
  neither the Darwin gate nor its owner test is a `FRESH_IMAGE_PATTERNS` entry — so no input either
  leg consumes has moved and both green runs stand. The publication preflight still classifies the
  wave `fresh-image`, because the `Makefile` and `eval/*` changed earlier in the branch; its
  per-phase table and the Darwin `fresh-focused` `N/A` reason are recorded in the pull request.
- **C7-P target-local aarch64 Linux gate, green, at head
  `09294dec94924e0363f0443cc671751dd8174186` (2026-08-25).** Native Linux
  `aarch64` in the privileged `c6g2-measure:latest` container with `--init`, non-root with
  `umask 022` and `PYTHONDONTWRITEBYTECODE=1`, on a clean clone of the committed head, with the
  image's native pinned build presented through the managed toolchain layout (compiler
  `7507770f2d5c36e94730fee3290446d7751d1ea83ecac00801086261ecfcf100`, runtime
  `8718943f29a9a3f9ba12b38c18eeeb3e70db9bbfdb034e78bf03c49a222a755d`). `check-gate-topology
  --self-test` PASS (5,685 ms), `make gate-topology-check` PASS, `make check` 23 units per-unit,
  `make build`, direct `check-per-unit`, `make persisted-result-smoke` **PASS** (747 ms),
  `make persisted-result-qualification` **PASS** (7,179 ms; same corpus counts as the host, with the
  runner's own `target aarch64-linux` observation), and `python3 scripts/check-baseline-chain`
  `baseline chain: PASS`. Section 11.2 holds the full record.
- **C7-P host publication checks at the repaired head `3e9b27e` (macOS, managed pinned toolchain,
  2026-08-25).** `gmake check` (23 units per-unit), `gmake gate-topology-check` (`check gate
  topology: PASS`, the `EXPECTED` lane bytes unchanged because `darwin-profile-gate` joins no
  aggregate), `gmake format-check`, `git diff --check`, `python3 scripts/test-align-toolchain`
  (managed checkout plus the attestation cases), `python3 scripts/test-check-darwin-profile` (the
  new failure-path owner: construction, malformed input, early exit, and cleanup PASS), and
  `python3 scripts/check-baseline-chain` (`baseline chain: PASS`): all PASS. Negative controls for
  the new owner: reverting each of the four repairs it covers makes it fail with the exact escaped
  exception type.
- **C7-P baseline chain re-finalization (2026-08-25).** Recorded on native Linux `aarch64` in the
  privileged `c6g2-measure:latest` container with `--init` and `bubblewrap` installed at run time,
  as a non-root uid with `umask 022` and `PYTHONDONTWRITEBYTECODE=1`, on a clean `git clone` of the
  source commit. `check-gate-topology --self-test` and `make gate-topology-check` ran first, both
  PASS. `record-baseline.py` then recorded both deterministic-reference samples as passing:
  134,035,875-140,845,834 ns, median 137,440,854 ns, at the unchanged pin. The replacement chain is
  source `9fd3ab64433e526d3af5c647ab933e8bfc365103`, oracle
  `3605b27ccbe1089f5ed2cb06294806a85d247cf1`, and finalization
  `f72e71f077e43d2943f9b9572c4367b9091888c4` — appended, never amended. The oracle projection
  produced in the container and the copy committed on the host are byte-identical (SHA-256
  `4335765eec6d715349d9239faadf448c449eeb2756c4c01302b14fb19ebdc417`).
- **C7-PERSISTED-RESULT baseline chain re-finalization (2026-08-25).** Recorded on native Linux
  `aarch64` inside the privileged `c6g2-measure:latest` container run with `--init`, `bubblewrap`
  installed at run time, as a non-root `runner` uid with `umask 022` and
  `PYTHONDONTWRITEBYTECODE=1`, with `chown -R runner:runner /opt/align`, on a clean `git clone` of
  the committed source head. In that container `python3 scripts/check-gate-topology --self-test`
  (**PASS**) and `make gate-topology-check` (**PASS**) ran first, proving the admitted lane bytes and
  the `exact_environment()` self-test copy moved together in `1e5797b`. `record-baseline.py` then
  recorded both deterministic-reference samples as passing: 130,939,292-139,880,709 ns, median
  135,410,000 ns, at Align pin `2f33ac5c33a898a7894af58322852632ce6ffe42`. The replacement chain is
  source `1e5797b3b451c79a48bd28f78edbd47b8540f9ec`, oracle
  `32e1442a5470f6c25862e290b6c2495ee8c2df0b`, and finalization
  `2fe903625816bd4738293e94497f88d43c42b5d9` — appended, never amended — and
  `python3 scripts/check-baseline-chain` reports `baseline chain: PASS`. The oracle projection
  produced in the container and the copy committed on the host are byte-identical
  (SHA-256 `4ecff07744fe4fc37c1052304fbe2a9593a0672c23232133b0c52e22678d4191`).
- **C7-PERSISTED-RESULT supervised capable gate, green, at head
  `36c8568897802afe6744edf6177dbb089d887b5a` (2026-08-25).** `python3
  scripts/run-fresh-worker-qualification --installed-profile-only --require-docker`: **PASS**,
  exit 0, `fresh image profile smoke: PASS` then `fresh worker qualification: PASS (installed
  profile only)`. Phases: `docker-daemon` 913 ms, `image-build` 16,526 ms, `image-attestation`
  3,342 ms, `profile-lifecycle` 2,594 ms, `profile-self-test` 14,713 ms, `trust-mutations`
  12,892 ms, `runtime-replacements` 27,036 ms, `boundary-profile` 412,666 ms,
  **`worker-aggregate` pass after 365,567 ms**, `cleanup` 1,380 ms; whole installed profile
  858,251 ms. Run with the default environment and no diagnostic opt-in. This is the first green
  supervised run that includes `persisted-result-smoke`, and it is the capability's final `make ci`
  evidence; the only later commit on the branch is the documentation update, which changes no
  executable input. Per section 11/12.1 it is not C7 platform acceptance evidence: this host is
  `aarch64` with no reviewed C7-P profile.
- **Environment facts learned while getting that run green; none is repository state.** (1) A failed
  installed-profile run leaves `/sys/fs/cgroup/align-llm-fresh/<uid>` behind in the Docker VM, and
  the next run then fails `profile-lifecycle` in about 0.5 s with
  `FileExistsError: '/sys/fs/cgroup/align-llm-fresh/12345'`; remove that directory from a
  `--privileged --cgroupns=host` container before retrying. (2) `boundary-profile` builds the
  pinned Align compiler twice from source and failed twice with the generic
  `json-scan adoption: ERROR toolchain` while the Docker VM had roughly 17 GiB free, then passed at
  412 s with roughly 31 GiB free; treat that message as a capacity signal first. (3) Do not prune
  the BuildKit cache to make room: two consecutive runs then hit the 1,800 s `image-build` budget
  downloading LLVM 22 from `apt.llvm.org`. Warming the cache once with a direct
  `docker build -f image/fresh/Dockerfile` (which fails only at the late build-key layer) restored
  a 16-28 s cached `image-build`.
- **Container environment fact: the topology self-test needs a reaping PID 1.** In the same image
  started **without** `--init`, `python3 scripts/check-gate-topology --self-test` fails
  reproducibly (three of three attempts) with
  `hanging child cleanup failed: ... lifecycle_errors=('process-group-remains',)`, because `sleep
  infinity` as PID 1 never reaps the orphan the case kills, and the zombie keeps its process group
  alive. With `--init` the same command passes. This is an environment fact, not repository state,
  and it is the same unreaped-descendant class as the `d7f1ff6` adapter fix.
- **C7-PERSISTED-RESULT publication host checks at head `36c8568` (macOS `aarch64-apple-darwin`,
  managed pinned toolchain `2f33ac5c33a898a7894af58322852632ce6ffe42`, 2026-08-25).** `gmake check`
  (23 units per-unit), `gmake gate-topology-check` (`check gate topology: PASS`), `gmake
  format-check`, `git diff --check`, `python3 scripts/check-baseline-chain` (`baseline chain:
  PASS`), `gmake persisted-result-smoke` (**PASS**, 3.1 s for six runners), `gmake
  persisted-result-qualification` (**PASS**, same corpus counts as below, 9.2 s), and `gmake
  c7-owned-record-source-expiry-adoption` (**PASS**, 3 parsed fixtures, 12 example rows, 45 adoption
  rows): all PASS. Section 11 names `LIBRARY_PATH` as this host's Align build-gate linker input, so
  every C7 target here runs with
  `LIBRARY_PATH=$(brew --prefix openssl@3)/lib:$(brew --prefix zstd)/lib` exported; without it the
  bounded functional owner fails closed before its first child. The only later commit is the
  documentation update, which is Markdown-only.
- **C7-PERSISTED-RESULT qualification slice, host (macOS `aarch64-apple-darwin`, managed pinned
  toolchain `2f33ac5c33a898a7894af58322852632ce6ffe42`, 2026-08-25).** `gmake check` (23 units
  per-unit), `gmake format-check`, `gmake gate-topology-check` (`check gate topology: PASS` at the
  admitted lane), `git diff --check`, `gmake persisted-result-smoke` (**PASS**, 3.5-3.6 s for six
  runners), `gmake persisted-result-qualification` (**PASS**: 11 boundary, 256 generated PASS, 32
  generated FAIL, 38 malformed inputs, 29 result mutations, 10 golden rows, 0 unexpected
  divergences, source mutation detected with 5 divergent and 38 agreeing cases, 749 bounded
  children, 8.7 s), and the regression set `gmake c7-owned-record-source-expiry-adoption` plus all
  six `c7-persisted-result-*-smoke` targets: PASS. `python3 scripts/check-baseline-chain` was red by
  design at that checkpoint (`working-tree Makefile differs from the baseline source commit`) and is
  green again after the wrap-up re-finalization recorded below.
  `python3 scripts/check-gate-topology --self-test` fails on this host in
  its `reader-start cleanup` process-lifecycle case with `sigkill-PermissionError`; the same failure
  reproduces at the unmodified `HEAD` copy, so it is a pre-existing macOS-host limitation, not a
  lane-admission regression. Per section 11/12.1 this host has no reviewed C7-P profile, so these
  runs are development evidence, not C7 acceptance evidence.
- **C6-MEASURED supervised gate, green, at head `3768ad8af68bb50ee3129ff392f6ba86ac89e071`
  (2026-08-25).** `python3 scripts/run-fresh-worker-qualification --installed-profile-only
  --require-docker --align-repo <path-to-sibling-align-checkout>`: **PASS**, exit 0,
  `fresh image profile smoke: PASS` then `fresh worker qualification: PASS (installed profile
  only)`. Phases: `docker-daemon` 675 ms, `image-build` 21,883 ms, `image-attestation` 3,822 ms,
  `profile-lifecycle` 3,188 ms, `profile-self-test` 14,331 ms, `trust-mutations` 13,151 ms,
  `runtime-replacements` 22,893 ms, `boundary-profile` 270,909 ms, **`worker-aggregate` pass after
  354,739 ms**, `cleanup` 1,883 ms; whole installed profile 708,521 ms. The
  aggregate is legitimately above the 172-192 s historical band because that band predates the
  C6-MEASURED lane members, which this run is the first supervised run to complete. Run with the
  default environment and no diagnostic opt-in.
- The immediately preceding diagnostic run, same command with `ALIGN_LLM_AGGREGATE_DIAGNOSTIC=1`
  exported, at head `e4c7e45`: FAIL at `worker-aggregate` after 178,853 ms, and it named the cause
  verbatim — `prompt measurement adapter: FAIL: [Errno 2] No such file or directory: 'git'`,
  `make[1]: *** [Makefile:129: prompt-measurement-adapter-smoke] Error 1`,
  `make: *** [/workspace/Makefile:234: capable-checks] Error 2`. The controller forwarded 8,192 of
  11,037 captured worker stderr bytes and the worker forwarded all 2,669 aggregate-child stderr
  bytes.
- Host (macOS, managed pinned toolchain) at `3768ad8`: `gmake check` (22 units per-unit),
  `gmake gate-topology-check` (`check gate topology: PASS`), `gmake format-check`,
  `git diff --check`, and `python3 scripts/check-baseline-chain` (`baseline chain: PASS`): PASS.
  The `Makefile` is unchanged by this work, so the baseline chain needed no re-finalization.
- Debian bookworm `aarch64` container, privileged, with `clang` and `unzip` installed and
  `PYTHONDONTWRITEBYTECODE=1`, at `e4c7e45`: `python3 scripts/run-fresh-worker-qualification`
  (all ten focused owners including `run-fresh-image-control-smoke` 4,745 ms with the new
  controller-diagnostic case, `run-fresh-worker-unit-smoke` 5,206 ms with the new worker-admission
  case, and `check-gate-topology --self-test`) and `python3 scripts/test-development-preflight`:
  PASS. That focused run also builds both changed native launchers twice and compares them.
- `python3 scripts/run-prompt-measurement-adapter-smoke` at `3768ad8`: PASS on the host (48 rows,
  unchanged documented Linux-only SKIP) and PASS in the container with a tool root that contains
  only `git` and is the whole child PATH (`ALIGN_LLM_TOOL_ROOT=/toolsim`, 64 rows) — the fresh
  aggregate's shape, reproduced outside it.
- C6-MEASURED aggregate-cost repair at head `55282a8` (2026-08-25). Host (macOS, managed pinned
  toolchain): `gmake check` (22 units per-unit), `gmake gate-topology-check`, `gmake format-check`,
  `gmake prompt-seed-attestation-smoke` (now 0 bytes on stderr), `git diff --check`, and
  `python3 scripts/check-baseline-chain` (`baseline chain: PASS`): PASS. A direct probe also proves
  `scripts/check-gate-topology`'s `exact_environment()` self-test copy still reproduces `EXPECTED`
  byte-for-byte after the lane change.
- Native Linux `aarch64` inside the privileged `c6g2-measure:latest` container, non-root with
  `umask 022` and `PYTHONDONTWRITEBYTECODE=1`, on a clean clone of `ebcc8d5`:
  `make gate-topology-check`, `python3 scripts/run-fresh-worker-unit-smoke` (includes the new
  aggregate-diagnostic seam case), and `python3 scripts/test-development-preflight`: PASS.
  `make prompt-verifier-smoke` also PASS as a direct invocation, in 719 s with a 1,525,732 KiB peak
  resident set — the measurement behind its demotion.
- `python3 scripts/run-fresh-worker-qualification --installed-profile-only --require-docker
  --align-repo <path-to-sibling-align-checkout>` at head `55282a8`: **FAIL**. Phases:
  `docker-daemon` 540 ms, `image-build` 20,497 ms, `image-attestation` 3,684 ms,
  `profile-lifecycle` 2,657 ms, `profile-self-test` 14,642 ms, `trust-mutations` 12,299 ms,
  `runtime-replacements` 21,970 ms, `boundary-profile` 266,754 ms, **`worker-aggregate` fail after
  191,760 ms**, `cleanup` 1,751 ms; whole installed profile 537,636 ms. Only output:
  `fresh compiler: ERROR CHILD aggregate`. See the two causes in the active checkpoint.
- `python3 scripts/check-gate-topology --self-test` fails in the `c6g2-measure:latest` container
  with `hanging child cleanup failed: ... lifecycle_errors=('process-group-remains',)`. It
  reproduces identically at the pre-change head `cffdda66c6307d3b6abdbee4c27f3fbd14750690`, so it is
  a pre-existing property of that container, not a regression. The image's own fresh profile runs
  the self-test successfully.
- C6-MEASURED review repair at head `e14c472b11abcbb2368a93d1fd4c97d3554f11e4` (2026-08-25).
  Host (macOS, managed pinned toolchain): `gmake check` (22 units per-unit), `gmake format-check`,
  `gmake gate-topology-check`, `gmake prompt-render-parity-smoke` (58 vectors byte-equal),
  `gmake prompt-generate-smoke`, `gmake prompt-experiment-smoke`,
  `gmake prompt-seed-attestation-smoke`, `gmake prompt-credential-lifetime-smoke`,
  `python3 scripts/run-prompt-measurement-adapter-smoke` (48 rows; the Linux launch rows SKIP),
  the six host-capable `prompt-gate-*-smoke` families, `python3 scripts/check-baseline-chain`, and
  `git diff --check`: PASS. `prompt-evaluate-smoke`, `prompt-fixed-adapter-smoke`,
  `prompt-source-verifier-smoke`, and `prompt-snapshot-helper-smoke` are Linux-only owners and fail
  on macOS for platform reasons alone (`child-subreaper containment is unavailable`); they are run
  in the container below.
- Native Linux `aarch64` inside the privileged `c6g2-measure:latest` container, non-root with
  `umask 022` and `PYTHONDONTWRITEBYTECODE=1`, on a clean clone of
  `e14c472b11abcbb2368a93d1fd4c97d3554f11e4`: all 24 owner targets PASS — `check`, `format-check`,
  `gate-topology-check`, `prompt-render-parity-smoke`, `prompt-experiment-smoke`,
  `prompt-generate-smoke`, `prompt-measurement-adapter-smoke`, `prompt-credential-lifetime-smoke`,
  `prompt-seed-attestation-smoke`, `prompt-evaluate-smoke`, `prompt-fixed-adapter-smoke`,
  `prompt-source-verifier-smoke`, `prompt-snapshot-helper-smoke`, `prompt-state-smoke`,
  `provider-smoke`, and all nine `prompt-gate-*-smoke` families. `eval-coding` and
  `c6-evaluation-adoption` also PASS. The gate then passed:

  ```text
  make prompt-gate-check \
    C6_GATE_SOURCE_BUNDLE_ROOT=/work/bundle \
    C6_GATE_PYTHON_EXECUTABLE_PATH=/usr/bin/python3.12 \
    C6_GATE_GIT_EXECUTABLE_PATH=/usr/bin/git \
    C6_GATE_GENERATION_CHILD_PATH=/work/align-llm/main \
    C6_GATE_GENERATION_CHILD_SHA256=c2f5be632c8c3c09fa2d47102a844dd78a85aeebe7fc637296381e85b50c7bb9
  ```

  `prompt gate validator: PASS`. The generation child was built in-run by `make build` and its
  SHA-256 reproduces the locator's frozen
  `c2f5be632c8c3c09fa2d47102a844dd78a85aeebe7fc637296381e85b50c7bb9` exactly. The verifier reported
  `align_llm_observed_head` equal to the derived CI head, `align_reachability: VERIFIED`, and
  `corpus_reachability: VERIFIED`. The same command was re-run at
  `07320e47f243e2a8abc7277f785e2d3a76a7a8d3` — which differs from the branch tip only by this
  handoff entry — and exits 0 there with the same generation-child digest, so the transcript holds
  over the documentation commits as well as over the evidence head.
- Container environment fact discovered by the regeneration: the source verifier runs Git with
  `GIT_CONFIG_NOSYSTEM=1` and `GIT_CONFIG_GLOBAL=/dev/null`, so a `safe.directory` exception cannot
  apply. The pinned Align checkout at `/opt/align/<revision>` must therefore be owned by the
  non-root runner, or every Git observation of it fails with dubious ownership and
  `align_reachability` is `UNVERIFIED`. `chown -R runner:runner /opt/align` is environment
  preparation, not repository state.
- The regenerated measurement was produced at `c737adcf905cb4662472bc86e8345bbcd9bc1346`: measure
  819.2 s, replicate 444.1 s, experiment 145.8 s. The re-run experiment used the identical
  opportunity artifact and at `temperature_micros: 0` reproduced the same candidate variant
  `78611fbc8f6f3f895a0ed715ef01800d5335cb5cba61ee2bd43aedc03166dc63`.
- Publication closures at head `8ddea8a03b817404e68a23e8ce1f39534b7abd13` (2026-08-25). Host
  (macOS, managed pinned toolchain): `gmake gate-topology-check`, `gmake check` (22 units
  per-unit), `gmake prompt-render-parity-smoke` (58 vectors byte-equal), `gmake format-check`,
  `git diff --check`, and `python3 scripts/check-baseline-chain`: PASS. Native Linux `aarch64`
  inside the privileged `c6g2-measure:latest` container, non-root with `umask 022` and
  `PYTHONDONTWRITEBYTECODE=1`, on a clean clone of source commit
  `ba47abdb01776d10f041c0d3e3f36edc67034993`: `python3 scripts/check-gate-topology --self-test`,
  `make gate-topology-check`, and `make prompt-render-parity-smoke`: PASS, then
  `eval/runners/record-baseline.py` recorded both deterministic-reference samples as `PASS`
  (121,396,125-128,282,751 ns, median 124,839,438 ns). The self-test is the proof that the
  `EXPECTED` bytes and the `exact_environment()` copy moved together.
- C6-MEASURED Slice E final capable gate at head `7273f65bfc1a2604daf37b2bd7748a46d2bd59f2`
  (2026-08-25): PASS. The complete capable check graph — every `HOSTED_CHECK_TARGETS` member in lane
  order, then `eval-coding`, `baseline-check`, and `c6-evaluation-adoption`, serially at `-j1`, the
  same list and order `capable-checks` runs — completed in 59 s, and `baseline chain: PASS`. The
  wired gate then passed:

  ```text
  make prompt-gate-check \
    C6_GATE_SOURCE_BUNDLE_ROOT=/work/bundle \
    C6_GATE_PYTHON_EXECUTABLE_PATH=/usr/bin/python3.12 \
    C6_GATE_GIT_EXECUTABLE_PATH=/usr/bin/git \
    C6_GATE_GENERATION_CHILD_PATH=/work/align-llm/main \
    C6_GATE_GENERATION_CHILD_SHA256=93e590658253507dc1518275743fd4e30a7f6c234a9a1e3ac4cf096e29474603
  ```

  `prompt gate validator: PASS`. The generation child was built in-run by `make build` and its
  SHA-256 was computed then; it reproduces the locator's frozen
  `93e590658253507dc1518275743fd4e30a7f6c234a9a1e3ac4cf096e29474603` exactly. The source bundle is a
  clean clone of the tested head plus a clean Align checkout at `.align-revision`; the verifier
  reported `align_llm_observed_head` equal to the derived CI head, `align_reachability: VERIFIED`,
  and `corpus_reachability: VERIFIED`.
- Slice E capable host: the privileged `linux/arm64` `c6g2-measure:latest` container with
  `bubblewrap` installed at run time, running as a non-root user with `umask 022` and
  `PYTHONDONTWRITEBYTECODE=1`. All three matter and are environment facts, not repository state.
  Root ignores directory mode bits, so the `c6f2` permission fixtures cannot fail as designed;
  Ubuntu's default `umask 002` produces `0664` checkouts, which the `FILE_SET` corpus manifest
  correctly rejects with `file-set entry type or mode disagrees`; and stray `__pycache__` output
  makes the CI checkout unclean, which the gate validator correctly rejects. This is not a
  `make ci` substitute: the supervised fresh-worker path builds a fresh compiler and runs the graph
  in its own sandbox, and remains publication CI evidence.
- Host checks at the same head: `gmake gate-topology-check`, `gmake format-check`, `gmake check`
  (22 units per-unit), `python3 scripts/check-baseline-chain`, and `git diff --check`: PASS.
  `gmake prompt-gate-check` with no `C6_GATE_*` values fails closed with
  `prompt gate: ERROR explicit C6_GATE_* input`.
- `python3 scripts/check-gate-topology --self-test` is Linux-only; it fails on macOS in the
  reader-start cleanup case with `sigkill-PermissionError`. Run it on a capable profile.

- `make provider-smoke` at the exact pin `19c3db144c462bf7d6784f88d64cc124229b7ec2` on native
  Linux `x86_64` (WSL2, 2026-08-24): PASS, including adapters, chunked SSE, framing failures, the
  bounded-response matrix with the `Error.Code(-1)` limit sentinel, HTTP 413, status diagnostics,
  exact prompt count, and the common result format. This re-verifies the adopted Request 5
  transport at the current pin for the C6-MEASURED ledger. `make check` at the same pin: PASS,
  20 units per-unit.

- Pre-merge C6-EVALUATION owners `gmake --no-print-directory c6-evaluation-adoption`,
  `gmake --no-print-directory c6-prompt-artifact-adoption`, `gmake --no-print-directory check`, and
  `gmake --no-print-directory format-check`: PASS at Align
  `19c3db144c462bf7d6784f88d64cc124229b7ec2` after the reopened
  deadline/allocation/precedence/gate repair and the final ownership-boundary repair. Source
  `163af7baa210`, oracle `549db0052fc2`, and finalization `d8d45c806658` form the ownership-repaired
  passing identity-bound baseline chain. The exact-head review of that chain found the remaining
  cross-process result-boundary class: nested-session descendants, unbounded adapter diagnostics,
  operational runner failures scored as tests, pre-creation child-output ownership, deterministic
  prepared-output cleanup, missing output-parent preflight, invalid-ID result suppression,
  malformed unavailable-source envelopes, behavioral publication gaps, and stale continuity. The
  reopened §10.1g redesign is complete. Source `1b9b98785743`, oracle `a8f4a2990cd3`, and
  finalization `72e931685fa3` form its passing replacement identity-bound baseline chain. Its
  exact-head review found the remaining reviewed-source execution-boundary class: unbound outer
  evaluator bytes, task code before or unrelated to source observation, task-repository Git config,
  late TREE/task bounds, incomplete child-result validation, missing cross-invocation drift,
  incomplete environment-policy validation, and partial result-only publication. The reopened
  §10.1h redesign is complete. Source `c24e82462a64`, oracle `d023c2f9c6d5`, and finalization
  `75cfc9c79b38` form its passing replacement identity-bound baseline chain. The redesigned
  exact-head review found the retained-source/complete-score class: an outer pathname reopen,
  corpus files not proven as commit or FILE_SET members, task-cwd helper resolution, fixture-only
  scoring, incomplete automatic snapshots and child observations, raw-only FILE expectations, and
  generic mismatch errors. The reopened §10.1i redesign is complete. Source `6e52ff04a698`, oracle
  `1e07ffe13553`, and finalization `365249123ec6` form its passing replacement identity-bound
  baseline chain. Its exact-head review at `0c2f24bd7889` found incomplete artifact schemas before
  side effects, runner/task/patch pathname reopen after adapter admission, unbounded reviewed TREE
  enumeration, and overlong publication temporary components. The reopened §10.1j redesign is
  complete. Source `00f7c7964e04`, oracle `2d15069c7d6f`, and finalization `ef174295ce5a` form its
  passing replacement identity-bound baseline chain. Its replacement exact-head review at
  `8fd2dfa5884f` found missing prompt-size enforcement, partial cross-invocation input comparison,
  late static-expectation bounds, unavailable-source aborts, and reversed containment/cleanup
  precedence. Because that revised review found new P1s, §10.1k reopened the semantic axis and
  closed the complete measurement state machine plus the same-class retained patch-size and
  snapshot-result bounds. Source `06e5e28b2892`, oracle `b8f6e0ece59b`, and finalization
  `d40cab8bdbf4` form its passing replacement identity-bound baseline chain. Subsequent gate
  integration made the request fixtures portable, bound fresh tools and the authenticated Git view,
  and preserved the aggregate's output-only overlay contract. Exact-head preflight and the final
  capable gate passed at head `049172f5be57` (CI run 32490981785) before the PR #100 merge; the one
  full-diff review is the §10.1k finding ledger. Focused evidence covers Request 11 exact-cap,
  over-cap, timeout, post-EOF, concurrent, and descendant cleanup; Request 14 collision, competing
  creator, special-file, reverse-cleanup, and exact owned-orphan recovery; source identity and local
  Git isolation; workspace/snapshot mismatch and drift; adapter failure prefixes; result-only
  invalid inputs; content-bound interpreter/helper/Git launch; evaluator/helper/adapter descendant
  cleanup; exact Git-blob and FILE_SET task-source membership; retained evaluator/helper execution;
  automatic identity-input drift; canonical FILE mode/content identity; exact snapshot observation
  closure and mismatch families; every complete score status and gate path; raw-byte FILE_SET
  traversal and physical-alias rejection; schema-v1 byte goldens; complete artifact-schema
  rejection before child launch; exact and cap-plus-one TREE entry/byte enumeration; retained inner
  runner/task/patch replacement races; 255-byte publication basenames; parent/candidate prompt-byte
  limits; complete automatic-input drift; present-mismatched and absent-unverified sources; all
  measurement states and containment-first failure precedence; and lifecycle consumption of the
  evaluator-produced pair.
- C6d owner: `make c6d-request18-adoption` and the final capable `make ci`: PASS at Align
  `19c3db144c462bf7d6784f88d64cc124229b7ec2`. The focused owner covers request and artifact bounds,
  retained-root symlink/special-file rejection, deterministic error precedence, exclusive output
  preservation and creator races, verifier-first acceptance, immutable rollback, and CLI behavior.
- C6c2 and borrowed-projection owners: `make c6-borrowed-option-adoption`,
  `make c6-borrowed-array-adoption`, and `make prompt-verifier-smoke`: PASS at Align
  `cdf333dc0707edbc4984dc8b1cb6b52edf7b48d0`. The verifier owner covers eligible and ineligible
  completion, all incomplete trace states, compact overflow, status/aggregate/reason/gate tampering,
  evidence order/duplication/digest tampering, and caller-owned record reuse.
- C6b-memory candidate owner evidence: `make prompt-model-smoke`, `make failure-memory-smoke`,
  `make check`, `make format-check`, and `git diff --check`: PASS against the exact pinned
  compiler; the owner covers chronological bounded selection, source/schema invalidation, policy
  caps, UTF-8 rendering, and SHA-256 preservation.
- Align Request 13 implementation PR #854 merged as
  `340a3304724fefb56c2b1aa642e6b2b2c169e6d7`; its required
  `cargo build --release --workspace` passed. Align-llm PR #94 then passed the exact C6a1/C6a2
  adoption target and final C6-LIFECYCLE `make ci` at `954258e24d93300dcdb78f8280de8868cf1ced56`,
  and merged as `ba56ebed5ac1c82ebc5925e6257e7bd5dba8a9b9`.
- Align `cargo build --release --workspace` at #786 final source: PASS.
- Align focused owner
  `scripts/cargo.sh test -p align_driver --test m5 owned_string_clone_duplicates_locals_and_fields -- --exact`:
  PASS.
- Align #786 preflight: PASS (owner, lint ratchet, 16-binary bounded gate, Clippy); all required
  hosted checks passed before merge.
- Align Request 8 design PR #799: comprehensive review found five valid closure gaps and the
  consolidated repair added checked-HIR rows, reconciled builder transfer and nominal identity,
  added the same-shape nominal twin, completed the Move-source matrix, and parameterized cleanup
  over stack-local and boxed headers. Exact-head docs preflight, native Linux ARM64, Linux x86_64,
  macOS Apple Silicon, PostgreSQL integration, pre-PR attestation, and post-open review all passed;
  merged as `60622c60a4fc21b8586e1f6a907c32c025aa1658`.
- `scripts/align-toolchain ensure compiler` for `5aa5b23a...`: PASS with native ARM and one Cargo
  build job; managed compiler path is under `~/.cache/align-llm/align/dev-v1/5aa5b23a...`.
- `./scripts/alignc check-per-unit src/main.align`: PASS, 15 units. The direct bounded HTTP adoption
  fixture and provider smoke pass locally against the exact pin: exact/cap-plus-one fixed and
  many-tiny-chunk bodies, bodyless/interim framing, exact/cap-plus-one trailers, connection reuse
  and teardown, chunked OpenAI/llama SSE, malformed/truncated framing, limit code `-1`, and HTTP 413.
- align-llm PR #90 merged as `bb86e9f8a1b9e2ab07500152b81e173a13400a06`. Exact-head preflight
  at `0987a2271034881fd1ac27101aa695e94c7729e5` passed the `fresh-image` lane, including the native
  Linux `aarch64` installed profile in 533,103 ms and worker aggregate in 179,830 ms. GitHub's
  pinned checks passed in 2m06s, native `x86_64` in 17m16s, and native `aarch64` in 18m16s.
- `python3 scripts/run-fresh-worker-qualification --installed-profile-only --require-docker --align-repo <path-to-sibling-align-checkout>`:
  PASS at `0f9e08eee427` on native Linux `aarch64`.
  The installed profile, Request 6 boundary, fresh compiler, worker aggregate, canonical baseline,
  complete `make ci`, resource owners, and cleanup pass; the worker aggregate took 172,039 ms and
  the complete installed profile took 514,222 ms.
- Latest pinned compiler Request 6 matrix: four owned-row fixtures reject with the exact Copy-row
  diagnostic; `copy-row.align`, `decode-owned.align`, and `decode-owned-option.align` run with the
  exact expected output.
- `python3 scripts/run-fresh-focused-adoption-smoke`: PASS in Linux; `./scripts/check-format`, Python
  syntax parsing, the FRESH-WORKER qualification inventory, and the migrated ordinary cgroup cleanup
  unit cases: PASS.
- Native Linux `aarch64` focused evidence on Docker Desktop: `run-fresh-image-control-smoke`,
  `run-fresh-worker-unit-smoke`, and the complete `run-fresh-worker-qualification` all PASS. The
  ARM run exposed a same-size post-copy mutation whose filesystem timestamps did not change; the
  worker now re-digests the retained source after materialization and the existing regression passes.
- The bounded-adoption publication preflight re-exercised the focused owners on a native Linux
  `aarch64` capable helper. A faster tmpfs ordering exposed that the two post-enumeration source
  mutation fixtures accepted only `OSError` as evidence even though the worker's retained-snapshot
  rejection is the documented `ValueError("materialization source changed")`. Both fixtures now
  require their mutation seam and accept either `OSError` or that exact `ValueError`, matching the
  existing same-size post-write row without allowing unrelated validation failures. The same run
  exposed a timing-dependent quota-disappearance fixture; its stat seam now injects exact `ENOENT`
  results and proves one strict and one live mutation. The tmpfs owner then exposed that scanning a
  retained readable directory descriptor can retain an exhausted or pre-population stream offset;
  every private-root quota pass now reopens the admitted directory through its retained descriptor,
  so newly staged entries and repeated scans are visible. Native ARM `run-fresh-worker-unit-smoke`
  passes with the consolidated repair on tmpfs.
- Native Linux `aarch64` installed profile through `boundary-profile`: PASS. This run exposed and
  repaired the focused-row prefix slicing and bare-Git fixture setup bugs; the focused adoption
  owner passes after both repairs. Warm signed-image builds reuse the architecture/toolchain layers,
  reducing the observed image-build phase from 1,065,794 ms to roughly 20-31 seconds.
- Native ARM diagnostics reproduced ordinary `align-build-only` as Cargo exit 101 and captured the
  exact failing child: `rustc align_sema` exited on `SIGKILL` after the authenticated runtime copy.
  The same pinned compiler builds natively in about 40 seconds when the runtime is bound without
  the preceding copy pressure; compiler/archive type, mode, size, and Cargo hard-link identity are
  valid. Fixed single-job Cargo contract and fresh-worker unit owners: PASS. The repaired native
  ARM ordinary adoption completed with canonical PASS in 225,474 ms, followed by cleanup PASS.
- Native ARM baseline source `cbcde22600e7`, oracle `12cce0199762`, and finalization
  `be0131f85c3c`: PASS. Both deterministic-reference samples pass under native `aarch64` bubblewrap;
  time to passing patch is 135,683,334-174,716,542 ns with median 155,199,938 ns. The canonical
  digest and baseline chain pass.
- `python3 scripts/run-fresh-image-profile-smoke --require-docker --align-repo
  <clean-pinned-Align-checkout>` at `be0131f85c3c`: PASS on native Linux `aarch64`. Boundary profile
  passed in 282,213 ms, worker aggregate in 190,201 ms, and cleanup in 3,345 ms.
- Comprehensive `codex review --base origin/main` reviewed `dae654a` against base tip and merge base
  `350ea497fbf1`. It found three valid ordinary-lifecycle defects: success could be emitted before
  outer cleanup, cgroup cleanup could replace an active build/fixture phase, and equal nested
  deadlines let an outer owner preempt inner cleanup. `b82d3b97ec83` repairs all three; the newly
  visible cleanup failure additionally exposed and repaired fixed bind-FD collision with retained
  Git/tool descriptors. The repair stayed within the reviewed ordinary lifecycle and timeout
  contract, and its focused delta was inspected without triggering another comprehensive review.
- `python3 scripts/run-fresh-image-profile-smoke --require-docker --align-repo
  <clean-pinned-Align-checkout>` at `b82d3b97ec83`: PASS on native Linux `aarch64` after the review
  repair. Image build passed in 23,143 ms, boundary profile in 257,071 ms, worker aggregate in
  174,881 ms, and cleanup in 3,983 ms. Success is now emitted only after the worker-owned root,
  source views, tools, bind placeholders, and cgroup are cleaned.
- Architecture-specific Cargo job owners at `6438dd4a6181`: PASS. Native `aarch64` selects
  `CARGO_BUILD_JOBS=1`; native `x86_64` omits the variable. The full native Linux `aarch64` image
  profile passes with the fixed ARM policy: boundary profile in 288,027 ms, worker aggregate in
  186,162 ms, and cleanup in 2,846 ms. The later required native `x86_64` 128 GiB CI owner passed
  at the final PR #84 head.
- Comprehensive `codex review --base origin/main` reviewed `fff8370c017a` against base tip and
  merge base `350ea497fbf1`. It found seven valid ordinary-isolation defects: staged input mounts
  and tool directories remained reachable or writable; the child could run before parent-verified
  cgroup admission; session-breaking descendants could escape teardown; a phase-channel failure
  could lose the active row phase; source mutation during staging was classified as `toolchain`;
  platform rejection was classified as `unobserved`; and setup failures were classified as
  `build`. Repair `d50373fc14af` closes all seven findings. It seals staged inputs and the namespace
  root, adds a parent-controlled cgroup start gate, kills all subreaper-owned children, preserves
  the active phase on channel loss, and corrects the three failure mappings. The repair implements
  the already reviewed lifecycle contract without expanding capability scope, so its focused delta
  was inspected without triggering another comprehensive review.
- Native Linux `aarch64` owners at `d50373fc14af`: `run-fresh-focused-adoption-smoke` and
  `run-fresh-worker-unit-smoke` PASS in the pinned capable image; Python syntax parsing,
  `check-format`, `check-baseline-chain`, and `git diff --check` PASS. The complete
  `run-fresh-image-profile-smoke --require-docker` passes against a clean checkout of pinned Align
  `25b1201b...`: image build in 29,701 ms, image attestation in 3,597 ms, profile lifecycle in
  3,173 ms, profile self-test in 14,771 ms, trust mutations in 13,740 ms, runtime replacements in
  22,496 ms, boundary profile in 275,309 ms, worker aggregate in 185,239 ms, and cleanup in
  3,410 ms.
- Exact-head publication preflight at `031917b5518170f905793af65b9cb347b837d178`: PASS. The
  installed boundary profile passed in 274,781 ms, worker aggregate in 179,603 ms, and cleanup in
  3,855 ms. Required native Linux `aarch64` and `x86_64` GitHub jobs passed before PR #84 merged.
- The first ARM baseline recorder invocation completed but produced two FAIL samples solely because
  its helper did not install `/usr/bin/bwrap`; schema inspection rejected it as canonical evidence.
- `python3 scripts/test-development-preflight`: PASS in the native Linux `aarch64` capable helper;
  `docker build --check -f image/fresh/Dockerfile .`: PASS with no warnings.
- Local `/usr/bin/make` is GNU Make 3.81, below the supported Make 4.3 floor, and cannot parse the
  repository's target-specific `override export` assignments. Use a capable profile for Make gates;
  do not weaken the Makefile for this host.
- Docker Desktop is native Linux `aarch64`. Do not run or cite an `amd64`-emulated container as
  installed-profile evidence; the native ARM owners are the local acceptance route.
