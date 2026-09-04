# align 開発ロードマップ v2.0

## 1. 開発戦略

一人開発であるため、align-runtimeとalign-coderを同時に全面開発しない。

最初にalign-coderで最終価値を検証し、既存モデルを使ってコード生成・検証ループを成立させる。

align-runtimeは、重要な技術spikeと小さな実装を並行して進め、後からbackendとして統合する。

```text
優先順位:

1. コーディングタスクの評価基盤
2. repo解析と検証ループ
3. prompt/contextの局所改善
4. local runtimeへの置き換え
5. 巨大モデル最適化
```

## 2. Capability delivery model

Roadmap gates define acceptance, not pull request count. Deliver work as consumer-complete
capabilities. Ledger rows, closure-matrix cells, helper layers, and historical slice labels remain
useful for implementation and test ownership, but they are internal checkpoints unless they have an
independent consumer or a distinct operational failure domain. Do not reduce the product contract
to make a larger capability fit; combine the pieces needed to exercise it end to end.

The current forward delivery order is:

1. **FRESH-IMAGE — installable minimum-platform profile.** Image provisioning, keys, supervisor
   installation, cgroup delegation, and platform attestation are a separate operational failure
   domain and the trust root for capable worker evidence. FRESH-WORKER development may progress in
   parallel, but its capable acceptance and merge require this installed and attested profile.
2. **FRESH-WORKER — usable fresh-compiler repository worker.** Treat the merged Section 9 design,
   attestation wire, manifest wire, source-manifest wire, and source-identity work as foundations of
   one capability, not as a precedent for more helper-only pull requests. Combine private-root
   admission, source/cache materialization, compiler bundle, process ownership, cleanup, Make
   integration, and the core end-to-end functional smoke. Do not merge it with synthetic or direct
   host evidence while FRESH-IMAGE is unavailable.
3. **C6-LIFECYCLE — usable offline prompt lifecycle.** Complete the artifact, renderer, scorer,
   verifier, activation, persistence, and CLI path required to load, inspect, accept, and roll
   back a deterministic candidate. Existing C6a/C6b/C6c/C6d labels are acceptance and ownership
   cells inside this capability.
4. **C6-EVALUATION — deterministic end-to-end comparison.** Combine the trusted workspace/source
   boundary, paired evaluator, fixed adapter, result/evidence publication, and functional corpus so
   the lifecycle is exercised by a real contained task.
5. **C6-MEASURED — provider proposal and measured gate.** Add the bounded provider proposal, real
   consumer, checked-in measurement evidence, acceptance, and rollback proof. Performance and
   provider-quality checks run here because this capability makes those claims.
6. **C7-PERSISTED-RESULT — owned-result verification consumer.** After its platform and Align
   prerequisites are adopted, deliver records, codec, algorithm, CLI, persistence, and core
   functional verification as one vertical capability. Keep generated differential, mutation,
   fuzz, stress, and benchmark work in focused qualification commands unless a later core contract
   specifically requires it.
7. **C7-P — aarch64 platform profiles.** Deliver the two reviewed non-x86 C7 acceptance
   environments required by section 11 of `docs/specs/c7-persisted-result.md`: discharge the
   Section 9 reuse condition for `aarch64-unknown-linux-gnu`, and add the separate minimal
   `aarch64-apple-darwin` profile (Section 10 of `docs/specs/check-gate-topology.md`) whose trust
   content is digest attestation rather than kernel mediation. Both gates are named focused
   qualifications; neither joins an aggregate. It is listed after the consumer because the consumer
   defines the exact targets a profile must gate, and because the profiles gate *evidence*, not
   implementation.
8. **C8 — speed-first optimization. Reopened for one bounded tenth capability.** Nine
   consumer-complete capabilities each preserved
   their correctness contract, named one changed path, and closed a paired fixed-task benchmark
   before claiming an improvement. The section C8 gate is met and `docs/specs/c8-speed-first.md` is
   authoritative for every baseline and measurement. Its retrospective promoted one reusable rule —
   the ppm-floor rule with a 2,000 ppm shipping floor — into section 1 of that document and one
   clause into the `CLAUDE.md` performance-claim row. `C8-OPTIONAL-TARGETED-STAGE` is the one
   explicitly prioritized re-entry: its fresh current-parent targeted process is 14,311,285 ns of a
   43,886,999 ns parent median (326,093 ppm), and its Align prerequisite shipped in PR #892. Its authoritative
   contract and stop conditions are in `docs/specs/c8-optional-targeted-stage.md`. Its stable
   candidate passes the schema/owner matrix and improves the 101-pair fixed-task median from
   60,515,456 ns to 40,475,113 ns (331,160 ppm, 33.12%); review is complete and PR #134 is in final
   base-integration/publication. Track B resumes after this bounded capability merges. Every other deferred surface retains the normal floor or
   genuine-request re-entry rule.
9. **R0-GGUF-INSPECT — read-only GGUF header, metadata, and tensor-table inspection. Gate met,
   closed.** The first Track B capability. It delivers one consumer-complete path: a caller names a
   `.gguf` path and receives one canonical `R0_GGUF_INSPECTION` document describing what the file
   declares about itself. It triggered the proportional design gate on a public CLI surface and a
   versioned exchanged document, so `docs/specs/r0-gguf-inspection.md` is the authoritative plan and
   owns the contract ledger, closure matrix, and fixture design. It makes no performance claim, so
   the C8 performance row does not apply to it. Merged as PR #121 (head `dcd8801`, merge
   `6640dcf`); the `scripts/run-gguf-reference-parity` qualification ran once against a real
   Qwen2.5-Coder-7B Q4_K_M model and passed: 29 metadata KV pairs, 339 tensors, `data_offset`
   5,953,536, `bytes_read` 6,291,456.
10. **R1-QWEN-MODEL-IR — Qwen2 Model IR and Block IR. Gate met, closed.** Turned one real
    Qwen2-architecture GGUF file into the Model IR and Block IR that `docs/specs/align-llm.md`
    section 5 places between the GGUF reader and the layout planner. `docs/specs/r1-qwen-model-ir.md`
    is the authoritative plan and owns the contract ledger, closure matrix, and fixture design.
    Merged as PR #122 (head `85a3a97`, merge `08492dc`); the `scripts/run-model-ir-parity`
    qualification ran once against a real Qwen2.5-Coder-7B Q4_K_M model and passed: 339 tensors over
    58 blocks, size-sum oracle `data_offset` 5,953,536 + `total_tensor_bytes` 4,677,120,000 =
    `computed_end` 4,683,073,536, matching `file_size`.
11. **R1B-GPTOSS-MOE-IR — gpt-oss MoE frontend and per-expert Block IR. Gate met, closed.** Merged
    as align-llm PR #123 (head `3bf5c9c`, merge `d8d4ef6`) onto `main` at `08492dc`. It discharged
    the MoE half of the R1 roadmap gate: a new architecture-neutral `src/model_ir.align` builder, a
    new `src/frontend_gpt_oss.align`, per-expert `ExpertBlock`/`RouterBlock` block kinds, and
    `R1_MODEL_IR` at `schema_version: 2`. `docs/specs/r1b-gptoss-moe-ir.md` is the authoritative plan
    and owns the contract ledger, closure matrix, and fixture design. **One qualification stays an
    open standing item**: the gpt-oss `model-ir-parity` qualification and real-model inspection
    against ledger section 2.5 remain the documented explicit `N/A` pending the user decision to
    download `gpt-oss-20b-mxfp4.gguf` (12.1 GB); the qwen half of the gate is real-model verified.
12. **R2A-EXPERT-TRACE-CAPTURE — expert-trace capture from a callback transcript. Merged as
    PR #124** (head `ab5f7d8`, merge `b8e1cb6`), from branch `agent/r2a-expert-trace`.
    `docs/specs/r2a-expert-trace.md` is the authoritative plan for R2a: `main --expert-trace
    CALLBACK_LOG [OUT.json]` consumes a `llama-eval-callback` transcript (recorded instrument
    build 10566) into an `R2_ACTIVATION_TRACE`, `schema_version: 1` document with per-(token,
    layer) expert ids and locality aggregates; a dense transcript yields `moe: false`. **The gate
    is met for parser correctness** on the dense case — `scripts/run-expert-trace-parity` PASS,
    `expert-trace-smoke` a hosted member — while **the R2 roadmap gate stays open** pending a real
    MoE transcript, a separate pending user decision (a small 1-4 GB MoE GGUF).
13. **R4-ALIGNPACK-LAYER-MAJOR — the alignpack v1 container, its layer-major writer, and its
    verifier. Merged as PR #125, merge commit `991eab1` on `main`.** Was on branch
    `agent/r4-alignpack-layer-major`.
    [`r4-alignpack-layer-major.md`](r4-alignpack-layer-major.md) is the authoritative plan and owns
    the contract ledger, closure matrix, fixture design, correction ledger, and cell-to-case map.
    `main --pack MODEL OUT.alignpack [DOC.json]` writes a layer-major container whose every block is
    one contiguous range, and `main --pack-verify MODEL PACK [DOC.json]` re-reads both files and
    compares every claimed byte; both emit `schema_version: 1` documents
    (`R4_ALIGNPACK`, `R4_ALIGNPACK_VERIFY`). It consumes R1's Block IR through
    `model_ir.resolve_claims` and `model_ir.derive_status` and imports no frontend. **It closes
    the R4 gate on the qwen half with real weights**: one qualification run over
    Qwen2.5-Coder-7B Q4_K_M reported byte identity and 89 → 58 ranges, 11,130,544,128 → 4,677,120,000
    span bytes, 2,379,786 → 1,000,000 ppm, and 27 → 58 of 58 contiguous blocks. **The per-expert
    half is discharged on a real MoE model by item 20**: over
    `OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf` the 1,024 `ExpertBlock`s go 3,072 → 1,024 ranges,
    165,368,823,808 → 3,900,702,720 span bytes, 42,394,624 → 1,000,000 ppm, and 0 → 1,024 of 1,024
    contiguous blocks. The residual **MOE-PREREQ** is gpt-oss-specific — a six-member `ExpertBlock`,
    MXFP4 geometry, split expert biases, and the fused `ffn_gate_up_exps` stay synthetic — and it
    waits on the 12.1 GB file the Status section records as infeasible on this host.
14. **R4.5-EXTERNAL-BUFFER-SPIKE — computing a ggml matmul over an Align-owned quantized buffer.
    Merged as PR #126, merge commit `fa567b1` on `main`.** Was on branch
    `agent/r4-5-external-buffer`.
    [`r4-5-external-buffer.md`](r4-5-external-buffer.md) is the authoritative plan and owns the probe
    record, the contract ledger, the closure matrix, the fixture design, the correction ledger, and
    the cell-to-case map. `ggml-spike PACK BLOCK MEMBER [DOC.json [REF.gguf]]` is a **separate**
    executable — `make build` links no ggml on any host — that reads one alignpack block into one
    Align-owned buffer, hands ggml a pointer *into* it, computes one `mul_mat` on a real backend, and
    emits an `R4_5_EXTERNAL_BUFFER`, `schema_version: 1` document saying, as data, whether ggml
    computed over our bytes or over a copy. It answers R4.5's gate for the DRAM half and for unified
    memory; section R4.5 below records clause by clause what that discharges and what it defers.
    Implemented, reviewed, repaired, and merged; R4's PR #125 merged first and PR #126 landed on top
    of it. **Its `one expert matmul succeeds` clause is discharged for a real expert claim by
    item 20**, which took `schema_version` to 2 and added one shape rule and one error code —
    the claim form was not, as this item's Japanese bullet had it, already addressable with no new
    surface. The GPU expert arm stays deferred.
15. **R5A-DENSE-LAYER-FORWARD — one Qwen2 dense layer computed from an Align-owned alignpack.
    Merged as PR #127, merge commit `ccbd8ae` on `main`.** Was on branch
    `agent/r5a-dense-layer-forward`, rebased onto the merged R4.5 at `main` `fa567b1`.
    [`r5a-dense-layer-forward.md`](r5a-dense-layer-forward.md) is the authoritative plan and owns the
    probe record, the contract ledger, the closure matrix, and the fixtures, qualification, metrics,
    deferrals, risks, and candidate-request sections. `ggml-spike --layer-forward` is a new arm of
    R4.5's executable — not a third link boundary — that reads the embedding rows and the two layer
    blocks a Qwen2 dense layer needs into Align-owned aligned windows, builds the layer's
    thirty-two-node graph from an Align-owned node table, computes it on a real backend, and emits an
    `R5_LAYER_FORWARD`, `schema_version: 1` document carrying per-node checksums and two independent
    oracle verdicts (a bit-exact self-reference arm and a tolerance comparison against a checked-in
    `llama-eval-callback` transcript). **Implemented, owner-verified, and qualified against the real
    model:** all eighteen oracle nodes agree with the transcript at `max |Δ| == 0` ten-thousandths
    over 1,116 sampled elements, the self-reference arm is 20 of 20 tensors byte-identical, and
    microbenchmark B measures **13.4 ms typical** for one dense layer (12.97-15.05 ms over four
    qualification runs; the design-stage probe harness measured 15.5 ms). Reviewed, repaired,
    preflighted, and merged; R5B (item 16) is stacked on it and rebased onto its merged result.
16. **R5B-MODEL-PREFILL-FORWARD — a whole Qwen2 prefill computed from an Align-owned alignpack.
    Merged as PR #128, merge commit `870bf31` on `main`.** Was on branch
    `agent/r5b-model-prefill-forward` at `3470646`, rebased onto the merged R5A at `main` `ccbd8ae`.
    [`r5b-model-prefill-forward.md`](r5b-model-prefill-forward.md) is the authoritative plan and owns
    the probe record, the contract ledger, the closure matrix, and the fixtures, qualification,
    metrics, deferrals, risks, and candidate-request sections. `ggml-spike --model-forward` is a new
    arm of the same executable, streaming all twenty-eight `AttentionBlock`/`MlpBlock` pairs through
    one reused Align-owned window sized from the largest block in the pack, carrying the residual
    stream in an Align-owned buffer between per-layer graphs, narrowing to the last token inside
    layer 27 after the attention output projection, and emitting an `R5_MODEL_FORWARD`,
    `schema_version: 1` document with three independent oracle verdicts. **Implemented,
    owner-verified, and qualified against the real model:** the self-reference oracle is 479 of 479
    nodes byte-identical over 30 graphs, the transcript oracle is `PASS` over 28 of 28 layers and
    30,078 elements at max `|Δ|` 0 ten-thousandths, the 152,064 final logits are byte-identical to
    `llama-debug --save-logits` at the instrument's declared attention width (KV width 256,
    sha256 `d2e48620…`), and at the runtime's own six-token width the verdict is `WITHIN` at max
    `|Δ|` 2,739 ten-thousandths with argmax 671 and the whole top ten unchanged — the difference
    traces to the declared no-KV-cache non-goal. Microbenchmark B is discharged at whole-model
    scale: the design-stage probe measured 349.6 ms compute and 533 ms `pread` for 4,370,571,072 B
    at 1.07-1.12 s wall, and the shipped arm measures 484-620 ms compute and 515-648 ms `pread` at
    1,141-1,275 ms wall on one reused 447,086,592 B window, warm. Implementation complete and
    committed; two complementary reviews and one final review are done and repaired in the
    consolidated repair commit `b5b2db8` and the final-review commit `5ab2ad0`; preflighted and
    merged. R5C (item 17) is stacked on it and rebased onto its merged result.
17. **R5C-METAL-PREFILL-ARM — the same Align-owned window, handed to Metal. Merged as PR #129, merge
    commit `39c69a2` on `main`.** Was on branch `agent/r5c-metal-prefill` at the final-review
    repair `9ac28bb`, on the review repair `31cd1d5` and the implementation `e3d94d9`, rebased onto
    the merged R5B at `main` `870bf31`.
    [`r5c-metal-prefill.md`](r5c-metal-prefill.md) is the authoritative plan and owns the probe
    record, the contract ledger, the closure matrix, and the fixtures, qualification, metrics,
    deferrals, risks, and candidate-request sections. `ggml-spike --model-forward-gpu` is a new arm
    of the same executable, taking R5B's schedule and operand grammar unchanged and handing the
    same Align-owned weight window to the Metal device through
    `ggml_backend_dev_buffer_from_host_ptr` instead of to the CPU backend, emitting a new
    `R5_MODEL_FORWARD_GPU`, `schema_version: 1` document. **Implementation, both review repairs, and
    the qualification on a Metal host are complete** (ledger section 7); the branch was rebased onto
    the merged R5B, preflighted, and merged. Required microbenchmark A (section R5 below) is
    discharged on unified memory: Metal is bit-deterministic (two consecutive shipped-arm runs and
    five probe runs byte-identical), the whole-model logits reach max `|Δ|` 2,936 of 6,000
    ten-thousandths against R5B's byte-identical CPU vector with `argmax` 671, the whole top ten
    identical in order, and zero of 152,064 elements over half a unit, and the self-reference oracle
    is byte-exact at 479 of 479 nodes over 30 graphs. The transfer copies **zero bytes** and costs
    **12.4 ms per 447,086,592 B wrap, 732 ms over the shipped arm's 59 wraps**; GPU compute at the
    reconciliation width is **375 ms against the CPU's 486 ms**. End to end the three paired runs
    are 1.31×, 0.99×, and 1.05× (median **1.05×**) and that spread is `pread`'s, so the ratio is
    **recorded as unresolved rather than claimed** — the cost ceiling was recorded as negative
    before implementation, so this is not a ceiling-estimation miss. Required microbenchmark C
    (async prefetch + GPU compute) cannot be written at this pin and is deferred with Request 41
    named (`docs/align-requests.md`).
18. **R1C-OLMOE-MOE-IR — an olmoe frontend and the first Model IR/Block IR derived from a real MoE
    model. Merged as PR #132, merge commit `e15e3d3` on `main`.** Was on branch
    `agent/r1c-olmoe-moe-ir` at head `3580a62`; design ledger `83361a9`, implementation `45e4ced`,
    review repair `4c86336`, reconciliation `3580a62`.
    [`r1c-olmoe-moe-ir.md`](r1c-olmoe-moe-ir.md) is the authoritative plan and owns the contract
    ledger and closure matrix. It turns the real, locally present
    `OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf` (195 tensors = 3 global + 16 layers × 12 per-layer
    patterns; 64 experts, top-8 routing) into `R1_MODEL_IR` at the unchanged `schema_version: 2`
    through a new `src/frontend_olmoe.align` and a three-way architecture dispatch, and appends two
    roles to the frozen `role_id` list (`attn_q_norm` 27, `attn_k_norm` 28). The size-sum oracle
    closes at `1,781,760 + 4,211,730,432 = 4,213,512,192` and the Block IR reaches 1,058 blocks /
    3,219 claims, measured on the real file. `src/model_ir.align` needs **no change**, confirming
    R1B section 5.5's design intent for a second MoE architecture. The real model also **contradicts
    rather than confirms** two of R1B's `ASSUMED` rows: the stacked gate/up/down axis order is
    reversed versus R1B's gpt-oss assumption, and R1B's required split expert biases are falsified
    as a generic rule (the real file carries no bias tensor at all). Both are recorded as
    corrections to `docs/specs/r1b-gptoss-moe-ir.md` section 7 by this capability's implementation,
    not repaired in the gpt-oss frontend itself, since no real gpt-oss file is present to settle it.
    Implementation is complete and all four owner checks PASS on the host that holds the model:
    `make check` (30 units), `make model-ir-smoke` (49 qwen, 31 gpt-oss, 29 olmoe, 62 R0 fixtures
    re-run), `make alignpack-smoke` (27 positive fixtures, 128 negative sources, 20,280 assertions),
    and `make model-ir-parity` against **both** real models — olmoe PASS over 15 compared rows plus
    the type census (`f32` 81, `q4_K` 97, `q6_K` 17), and qwen2 PASS over 14. The olmoe parity run
    is the qualification R1B could only record as `N/A`, so this is the first `model-ir-parity`
    discharged against a real MoE model. Section 6 of the ledger records eleven corrections to the
    plan, including that the parity runner's `ulimit -f` had to rise to 256 MiB because it bounds
    `llama-cli`'s Metal shader pipeline cache and not only its log.
19. **R2-LOCALITY-GATE — the R2 locality gate, measured on a real MoE model. Merged as PR #131,
    merge commit `546b5cc` on `main`.** Was on branch `agent/r2-locality-gate` at the review repair
    `fff5806`; no design gate triggered. Discharged R2A's `MOE-PREREQ` deferral by running
    `--expert-trace` against `OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf` and added a multi-prompt
    locality measurement script: 40 prompts of at most 6 tokens each, a null hypothesis
    `p0 = 125` per mille, and a confidence interval judged against a 1.5× effect-size floor over
    the null. **The gate is met in the prefill direction**: verdict `LOCALITY`, observed
    `p^ = 286` per mille against the null's 125 (2.29×), 95% cluster-robust interval
    `[262, 311]` per mille over 40 prompt clusters (design effect 10.460), and all 15 measurable
    layers clearing the null on their own. The router histogram is near uniform (entropy 992 per
    mille, all 64 experts used), so the effect is conditional structure between tokens rather than
    popularity bias. The measurement is prefill-only at this instrument pin, and the real model's
    top-8 routing reached R2A's `slots_truncated: true` branch for the first time on real data
    (observed truncated slots 3 of 8 at each end). The R2 section below records the verdict, its
    limits, and the R2b/R2c work that remains.

20. **MOE-PREREQ-DISCHARGE — the per-expert half of R4 and R4.5, measured on a real MoE model.
    Merged as PR #133 at `35a0df6`.** The branch was rebased onto the merged R1C at `main`
    `e15e3d3`; design ledger `4656d88`, implementation `eed850e`, review
    repair `4bf25b8`, developer-guide refresh `0dd4ea8`. [`moe-prereq-discharge.md`](moe-prereq-discharge.md) is the authoritative plan
    and owns the probe record, the contract ledger, the closure matrix, the correction ledger, and
    the cell-to-case map. It discharges the two prerequisites items 13 and 14 left open, on
    `OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf` rather than on the synthetic corpus, by turning two
    constant verdicts into rules over the block set each run measured: the alignpack qualification
    reports the container's 1,024 `ExpertBlock`s going 3,072 → 1,024 ranges, 42,394,624 → 1,000,000
    ppm, and 0 → 1,024 of 1,024 contiguous; the ggml spike selects both arms by `role_id` out of the
    pack document it just wrote and computes real expert claims — all three members of the first
    `ExpertBlock` and member 0 of the last (block 1,056, plane 63 of 64) — every one `EXTERNAL` and
    bit-identical to the same plane read from the original GGUF. **The shipped R4.5 arm refused a
    real expert claim** with `R4_5_SHAPE`, detail `n_dims[3]`, so admitting the claim form took
    `R4_5_EXTERNAL_BUFFER` to `schema_version: 2`, split step 7 into 7a (the slice pair) and 7b (the
    shape by form), and added the `R4_5_SLICE` code; R4.5's claim that the CLI already addressed an
    `ExpertBlock` with no new surface is refuted and removed. R4's expert hotness ordering and
    prefetch groups, and R4.5's GPU expert arm and discrete-VRAM half, stay deferred and unchanged.
    The layout numbers are a claim about this container on this named model, not a platform or
    throughput claim. Review, publication, and merge are complete; see `HANDOFF.md`.

21. **R3-RESIDENCY-SIM — the R3 cache-simulator gate, measured on the real MoE activation corpus.
    Merged in PR #135.** The merged capability is based on the
    merged MoE prerequisites and C8's optional targeted stage at `main` `4f01553`. [`r3-residency-sim.md`](r3-residency-sim.md) is the
    authoritative plan and owns the contract ledger, the closure matrix, the correction ledger, the
    probe record, and the cell-to-case map; the design gate triggered on three counts (a new public
    CLI verb `--simulate-residency`, a new exchanged format `R3_RESIDENCY_SIM` `schema_version: 1`,
    and a coordinated invariant across three modules plus the `Makefile`). It replays a demand stream
    derived from real `R2_ACTIVATION_TRACE` documents against ten residency policies over four
    families — `lru`, `lfu`, three fixed-window `recent_reuse`, two `topk_prefetch` degrees, and the
    `null` / `compulsory` / `belady` references — at a nine-point budget sweep, with a
    leave-one-document-out jackknife over the corpus and a headroom measure against the miss-optimal
    offline reference. **The R3 gate is met**: at the requested 975,175,680 B budget (250 per mille
    of the 3,900,702,720 B expert footprint), `recent_reuse_w32` fetches 26,033,848,320 B against the
    `lru` baseline's 33,532,231,680 B — 223 per mille fewer, against a 50-per-mille materiality
    floor — with a 40-fold jackknife minimum gain of 213 per mille and 574 per mille of headroom
    still left to the offline optimum, verdict `BEATS_BASELINE`. Across the sweep the verdict is
    `BEATS_BASELINE` at 1/3/6/12/25 per cent, `NO_POLICY_BEATS_BASELINE` at 0 and 50 per cent, and
    `NO_HEADROOM` at 100 per cent. Roadmap section R3's remaining three policies — score-based,
    impact-driven prefetch, and CPU fallback — are deferred with named prerequisites rather than
    simulated against invented constants (router scores need an R2A `schema_version: 2` weight
    column; a miss penalty needs R4.5's and R5's measured transfer costs; CPU fallback needs R5's
    microbenchmark). The result is a policy claim about this named model and this corpus, not a
    platform or throughput claim, and it carries the caveats the section R3 entry below records.
    Review, publication, and merge are complete; a follow-up by a parallel session, PR #138 at
    `1b11245`, moved the qualification wrapper's Model IR and budget validation ahead of the
    instrument runs. See `HANDOFF.md`.
23. **R5D-MOE-LAYER-FORWARD — one OLMoE MoE layer computed from Align-owned expert claims, the
    routed half of R5's second gate stage. Merged** as PR #139 (`main` `e312bd7`). On branch
    `agent/r5d-moe-layer-forward`, rebased onto the merged R3 residency simulator at `main`
    `95c47e7` and then merged with `main` `1b11245` (PR #138's follow-up) rather than rebased over
    it, so the recorded baseline-chain commits stay reachable; design ledger `a85e1fc`,
    implementation `7886cee`, review repair `a2e2748`.
    [`r5d-moe-layer-forward.md`](r5d-moe-layer-forward.md) is the authoritative plan and owns the
    probe record, the contract ledger, the closure matrix, the correction ledger, and the
    cell-to-case map; the design gate triggered on the new `--moe-layer-forward` CLI arm, its
    `R5D_*` result codes, and a coordinated invariant across `src/layer_olmoe.align`,
    `src/moe_layer_forward.align`, `src/ggml_ffi.align`, and both C shims. The ledger's probe record
    fixes the OLMoE MoE layer's real topology as data — the
    QK-norm is an RMS norm over `n_embd` taken before the head reshape, the router's 64-way softmax
    is never renormalized, the top-k node is `ARGSORT` plus `VIEW` rather than `ggml_top_k`, and a
    compacted, remapped expert stack computed with `mul_mat_id` is bit-identical (28 of 28 dumped
    nodes) to llama.cpp's own whole-tensor shape and needs no restacking copy. Against a checked-in
    `llama-eval-callback` transcript the tolerance oracle reaches max `|Δ|` 5.0e-5 (the instrument's
    own print-rounding bound) over 2,376 sampled elements, and the routing-identity oracle matches
    the transcript's selected expert ids exactly. **The shipped arm measured on the real model**
    (ledger section 7.1): the routed layer reads **101,990,400 of 261,095,424** expert bytes,
    390,625 ppm, 75 of 192 planes over 25 block reads; the self-reference oracle is 46 of 46
    byte-identical; the routing-identity oracle is `MATCH` at the exact printed ids and their sum
    1,471; the transcript oracle is `PASS`, 26 of 26 nodes, 2,376 elements, max `|Δ|` 0
    ten-thousandths. Required microbenchmark B is discharged at **5.64 ms** for one routed layer,
    six tokens, warm (phase A 1.452 ms, phase B 4.185 ms; the probe's 9.4 ms timed a cold graph per
    arm). The residency win this capability exists to measure is smaller than the plan assumed and is
    stated as such: at six prefill tokens R5D reads 39.1% of the layer's expert bytes (12.5% at one
    token, 73.4% at eighteen), so claim-level expert residency is recorded as a **decode-time**
    property rather than a prefill win. The result is a correctness and layout claim about this named
    model, not a throughput claim. No new Align capability request was needed; four existing requests
    (37, 42, 45, 46) gain R5D as a non-blocking client. See `HANDOFF.md`.
22. **R2C-DECODE-INSTRUMENT — a pinned, source-built decode-graph measurement dependency. Merged
    as PR #140, merge commit `89d8721` on `main`, by a parallel session.** [`r2c-decode-instrument.md`](r2c-decode-instrument.md)
    is the authoritative ledger and closure matrix. It pins llama.cpp commit
    `bb4caa7540188872173c44d161602d9271386413` and one two-file patch, builds the patched
    `llama-eval-callback` into an identity-addressed cache outside Git, and extends the existing
    schema-1 parser to accept either the upstream three-plus-three router axes or exact full axes.
    Positive `-n` values now emit bounded one-token decode graphs while omitted/nonpositive `-n`
    retains one prefill graph; only `ffn_moe_topk` prints every slot and token. Existing R2/R3
    measurement wrappers now pass explicit `-n 0` and reject full-axis documents, preserving their
    historical prefill-only, compact six-slot semantics. The deterministic owner, dense
    qualification, and real OLMoE qualification pass;
    the latter records three graphs including decode, 48 full-width groups, 384 selections, and a
    router extent of eight above the old six-value threshold. The first comprehensive review found
    four valid cache/recipe/qualification defects, all consolidated and owner-tested. Final repair
    review found three further valid compatibility/safety/parser defects; their consolidated repair,
    affected owner verification, and real OLMoE requalification pass. Its first measurement
    consumer is item 24; R6 may consume the same instrument as its decode-graph source.

24. **R2D-DECODE-LOCALITY-GATE — the decode half of the R2 locality gate, measured on the real
    model. Merged** as PR #141 (`main` `c21b9e4`). It was developed on branch
    `agent/r2d-decode-locality-gate`, started from `main` `89d8721` (R2c PR #140) and merged with
    `main` `e312bd7` (R5D PR #139) rather than rebased over it, so its recorded commits stay
    reachable.
    [`r2a-expert-trace.md`](r2a-expert-trace.md) section 9 is the authoritative record; no
    design gate is triggered, because it adds no CLI verb, no exchanged document, and no coordinated
    invariant. `scripts/run-decode-locality-gate` captures one prompt-plus-decode transcript per
    prompt with item 22's patched instrument at `-n 16 --temp 0 --seed 42`, derives one
    `R2_ACTIVATION_TRACE` per transcript, deletes the transcript, and pools the documents into three
    verdicts under one rule: `prefill@8` over all eight router slots, `decode@8` between consecutive
    decode graphs, and the prompt-to-generation `boundary` pair reported separately. On the same
    40-prompt corpus all three are `LOCALITY` — 371, **447**, and 364 per mille against a 125 per
    mille null, with cluster-robust intervals [338, 405], [426, 468], and [325, 405] over 40 prompt
    clusters — and every layer clears the null on its own stratum. Greedy decode's token-repetition
    rate is measured at 51 per mille and excluding those pairs leaves every verdict unchanged. The
    historical compact-axis path and section 8's recorded 286 per mille are untouched. The
    aggregator's owner case is hosted in `expert-trace-smoke`, needs no model or instrument, and
    kills all fourteen mutations of the shipped rule. One comprehensive review over two independent
    reviewers found thirteen findings — one blocker, one major, eleven minor — all accepted and
    repaired in one consolidated commit; the real-model run was repeated at the repair head and
    reproduced every recorded number.
25. **R3-DECODE-RESIDENCY — the decode half of the R3 cache-simulator gate, measured on the real
    model. Implemented and reviewed; repair complete.** On branch `agent/r3-decode-residency`,
    started from item 24's `d48bde0` and merged with `main` `c21b9e4` (item 24's PR #141) rather
    than rebased over it, so its recorded commits stay reachable.
    [`r3-residency-sim.md`](r3-residency-sim.md) section 8 is the
    authoritative record; no design gate is triggered, because it adds no CLI verb, no exchanged
    document, no Align source change, and no coordinated invariant.
    `scripts/run-decode-residency-gate` takes item 24's capture flag for flag — 40 prompts at
    `-n 16 --temp 0 --seed 42` — admits it with the same `require_full_router_axes`, and replays it
    through `main --simulate-residency` in **four** arms at section 7.4's own 25-per-cent budget:
    the **mixed** list as captured (104,960 demands, 832 token positions), a **decode-only** list
    with graph 0 projected away and the ordinals kept (81,920 demands, 640 positions), a
    **prefill-only** coverage control with the decode graphs projected away instead (23,040 demands,
    192 positions), and a **head-4** stream-length control keeping only decode ordinals 1–4 (20,480
    demands, 160 positions). **The gate is met in the decode direction and its answer is narrower**:
    `recent_reuse` beats `lru` by 59 to 238 per mille at 1.5/3.1/6.2/12.5 per cent on the mixed and
    decode-only arms and by 70 to 200 at 3.1/6.2/12.5 on the head-4 arm, but at 25 and 50 per cent
    **no candidate beats the baseline at all** on any of the three — all report
    `NO_POLICY_BEATS_BASELINE`, `recent_reuse_w2` is byte-identical to `lru`, and `lfu` changes sign
    from a 221-per-mille saving to a 152/190/88-per-mille loss. **The two control arms are what make
    that attributable.** R2c changed slot coverage (750 → 1,000 per mille) and phase at the same
    time; the prefill-only arm changes only coverage and is **`BEATS_BASELINE` at the same
    25-per-cent budget**, `lfu` 194 per mille with a stable jackknife (minimum fold 186),
    `recent_reuse_w32` still clearing the floor at 191. So section 7.4's 223-per-mille win
    **survives full axes**. Phase also changed the stream's length, and the head-4 arm removes that
    too: at 20,480 demands — eleven per cent *fewer* than the winning prefill-only arm, so less
    cross-prompt pressure, not more — it still reaches `NO_POLICY_BEATS_BASELINE` with a gain of 0.
    **Two arms of comparable length give opposite verdicts, and only the phase differs**, so what
    removes the win is the presence of decode demands: not coverage, not the working-set tightening
    an earlier draft blamed (the winning control sits at 2.14 working sets, the identical multiple
    the losing mixed arm's own prefill positions sit at — the seven per cent separates that from a
    decode position's 2.00), and not stream length. *Why* frequency loses is **not** settled: it is
    consistent with decode's more uniform expert distribution (item 24's entropy 996 against
    prefill's 992), but `r2a-expert-trace.md` section 9.4 measures that effect as **small** — a
    4-per-mille entropy gap of which estimator bias accounts for up to 0.24, and about 3 per cent of
    the window-deficit — so it is one candidate explanation and not a demonstrated mechanism. What
    the arms cannot separate is decode's routing statistics from a decode position's wider
    per-position working set (sixteen layers against fifteen), and section 8.4 says so. 476, 473,
    and 453 per mille of headroom to the offline optimum remain **uncaptured by every online
    candidate** on the three decode arms, which is the strongest evidence yet for the score-based
    and impact-driven policies ledger section 5.1 defers with named prerequisites.
    `scripts/run-residency-sim` still refuses a full-axis document, so the two corpora can never be
    pooled. Six hosted cases and two binding checks join `residency-sim-smoke` — four full-axis arms
    against the independent oracle, the renumbered decode-only list that makes their
    `single_token_first_graph: 0` an assertion rather than a vacuous label, both admission refusals,
    the runner's binding to the shared `scripts/residency_projection.py`, and an enforced
    capture-flag identity with item 24's runner — and a mutation that ignores decode graphs is
    killed by the new cases and by nothing else in the file, as are both mutations of the head-4
    predicate. No `Makefile` change and no aggregate membership change. See `HANDOFF.md`.

26. **R5E-MOE-MODEL-PREFILL — a whole sixteen-layer OLMoE prefill computed from Align-owned expert
    claims, completing R5's **third** gate stage. Implemented and reviewed; in publication.** On branch
    `agent/r5e-moe-model-prefill`, merged with the merged R5D at `main` `e312bd7` and then again with the merged R2D at
    `main` `c21b9e4` and the merged R3-DECODE-RESIDENCY at `main` `76246f3`, rather than rebased
    over any of them, so the recorded baseline-chain commits stay reachable; design ledger `5e3356d`,
    implementation `053de09`, review repair `e7f727f`.
    [`r5e-moe-model-prefill.md`](r5e-moe-model-prefill.md) is the authoritative plan and owns the
    probe record, the contract ledger, the closure matrix, the correction ledger, and the
    cell-to-case map; the design gate triggered on the new `--moe-model-forward` CLI arm, its
    `R5E_*` result codes, and a coordinated invariant across `src/layer_olmoe.align`,
    `src/moe_model_forward.align`, and the two window budgets. The arm streams all sixteen routed
    layers and the output head with per-layer routing, reads only the selected experts' planes into
    **one** Align-owned claim window reserved at the arithmetic union bound and reused across layers,
    narrows inside layer fifteen where the instrument does, and emits the per-layer union curve.
    **Measured on the real model**: the final logits are **byte-identical** to
    `llama-debug --save-logits` (sha256 `a56195da…`, `IDENTICAL`); the self-reference oracle is
    **227 of 227** nodes byte-identical; the transcript oracle is `PASS` over **227 nodes and 21,372
    elements**; the routing-identity oracle is `MATCH` at **546 of 546** compared selections across
    all sixteen layers. A six-token prefill reads **1,301,446,656 of 3,900,702,720** expert bytes —
    **333,644 ppm**, 33.36% — so two thirds of this model's expert weights are never touched by a
    prefill; peak resident weight bytes are 280,342,528, **6.66%** of the 4,212,193,280-byte
    container. Microbenchmark B is discharged as a **shape, not a single number**: the probe's warm C
    harness measured **121.3 ms** of compute against **~227 ms** of claim `pread`, and the shipped
    arm's qualification runs measured **252.8 / 109.9 / 147.3 ms** of compute against **612.0 /
    519.9 / 560.8 ms** — the claim read is **1.9×–4.7× compute** in every run, so a six-token routed
    prefill of this model on this CPU is **I/O bound even with the file in page cache**, which is
    what a residency policy has to beat. Every timing here is a single run or a small median and
    carries the variance ledger correction **C16** records; the exact-integer residency half carries
    none. Any residency **policy** and any cache-hit claim stay deferred:
    within one prefill there are 343 demands and 343 distinct keys, so no cache can hit. Two new
    Align capability requests, **47** (a `Borrow` argument must be a stable named local or field) and
    **48** (same-call aliasing between a `borrow mut` owner and its own `Copy` scalar field), are
    filed `PROPOSED` and non-blocking. See `HANDOFF.md`.

27. **R6-DECODE-KV-STEP1 — one decode step over an Align-owned KV plane. Implemented; the hosted
    owner and the real-model qualification are recorded in
    [`r6-decode-kv-step1.md`](r6-decode-kv-step1.md). It does **not** meet R6's own roadmap gate
    below — TTFT on repeated coding tasks over a shared prefix — and makes no TTFT claim.** R5B computes a whole prefill and every K and
    V dies with its graph — `src/model_forward.align` opens three fresh `ggml_context`s per graph
    and frees them at the end of that graph — so the model can answer "what are the logits for this
    prompt" and not "what comes next". This capability adds the smallest thing that changes that: an
    Align-owned KV plane carrying all twenty-eight layers' post-RoPE K and V across the graph
    boundary, a decode graph at `n_past = T` with positions `[n_past]` and a `{KV_WIDTH, 1}` mask,
    one new ggml op wrapper (`ggml_concat`) with its shim body and its stub kernel, a split of token
    ids from positions — one buffer until now — and a lift of `MAX_PREFILL_TOKENS` from 6 to 8. The
    boundary is deliberately narrow: dense Qwen2.5-Coder-7B Q4_K_M, CPU, **one** step, the plane in
    memory, no tiering, no invalidation, no Metal, no OLMoE, and no TTFT claim. It is the first
    consumer of item 22's decode instrument, exactly as
    [`r2c-decode-instrument.md`](r2c-decode-instrument.md) section 1 anticipated. Its own gate is
    correctness on **three** acceptance oracles, whose exact rule is `r6-decode-kv-step1.md` section
    2.11 and is stated nowhere else: A, every comparable node of llama.cpp's own **decode** graph at
    the instrument's printing precision of one ten-thousandth over twenty-eight layers plus the head,
    four prompts x three runs; B, the KV plane's round trip through the graph boundary,
    **byte-identical** across all twenty-eight layers' K and V; and C, the step's logits against this
    arm's own single-shot `T+1` prefill, **byte-identical** on every prompt. An oracle A `FAIL` is
    admissible only inside the 0.5 characterization bound **and** with C byte-identical, which
    attributes it to llama.cpp's own kernel selection rather than to this arm. The design records, as
    measured findings, that `llama-debug --save-logits` has no step-1 blob at all — `-n` is inert for
    it and the R2c patch does not touch it — and that the decode graph is not reproducible unless the
    sampler is pinned to `--temp 0 -s 0`. It also records that llama.cpp's own single-shot `T+1`
    prefill and its own incremental step differ by up to 0.17 in activations and 0.054 at the logits
    through batch-size-dependent kernel selection — and that **this arm's two paths do not**, which
    is the measurement that promoted oracle C from characterization to acceptance. The plane is
    29,360,128 B at KV width 256. The hosted owner is `layer-forward-smoke`, extended with a fifth
    block whose corpus is a **second implementation** of the decode step in Python and a transcript
    holding two graphs; `gmake decode-step-qualification` is the opt-in real-model run and joins no
    aggregate. `docs/specs/r6-decode-kv-step1.md` is the authoritative ledger. **What it leaves
    open:** the R6 gate below asks that TTFT improve on repeated coding tasks sharing a prefix. One
    step, in memory, with no session reuse, no tiering, and no invalidation does not answer it; the
    gate stays unmet and the next capability toward it is step 2 and the decode loop, which is
    item 28.

28. **R6-STEP-N — an N-step greedy decode loop over the Align-owned KV plane, gated on the token
    ids llama.cpp produces at `--temp 0 -s 0`.** Design and results in
    [`r6-step-n.md`](r6-step-n.md). Item 27 computes **one** decode step and stops, so the model can
    answer "what is the next token" and not "what are the next `N` tokens" — which is the question
    every consumer of a coding model actually asks. This capability ships the smallest change that
    makes the second answerable: `--decode-step` gains a `STEPS` operand and its document goes to
    schema 2 with a per-step `steps[]` array and a `decode.token_ids` chain; the plane is grown **in
    place** one column per step — the buffer was `KV_WIDTH` columns wide from the start, so nothing
    is reallocated — and every written column is byte-verified inside the step that wrote it, which
    closes a gap item 27 shipped. The loop needs **no new ggml op, FFI symbol, node row, or slot**:
    R6's decode row table is already parameterised by `n_past`, and `src/ggml_ffi.align`,
    `scripts/ggml_shim.c`, and `src/ggml_spike.align` are byte-unchanged. `MAX_PREFILL_TOKENS` moves
    8 -> 32 so the self-reference oracle can run at `T + N` tokens; `R5_ORACLE_TRUNCATED` is
    byte-unchanged and still refuses a prefill above six tokens *with* a transcript. Acceptance is
    correctness, stated once in `r6-step-n.md` section 3.5: **gate G**, the `N` decoded ids equal
    llama.cpp's — `d_1` byte-exact through item 27's `llama-debug` blob, and `d_1 .. d_N` through
    transcript graph `k+1`'s `embd = GET_ROWS(token_embd.weight, [d_k])`, over a vocabulary whose
    printed-fingerprint collision count was **measured** before the gate was claimed (149,710
    distinct fingerprints over 152,064 rows, one collision class, and that class is exactly the
    2,355 all-zero unused vocabulary rows, none of which any step decoded); **oracle B**,
    the plane round trip `IDENTICAL` at every step over `T + k` columns including the one that step
    wrote; **oracle C'**, the step-`k` logits byte-identical to this arm's own single-shot `T+k`
    prefill at `k in {1, ceil(N/2), N}`; and **oracle A'**, structurally complete at every step and
    numerically admitted at step 1 under item 27's own rule. A' is demoted to characterization at
    steps 2..N for a measured reason: llama.cpp's decode graph takes a different `MUL_MAT`
    accumulation path from its own multi-column prefill, and gating on a quantity whose growth is a
    property of the reference implementation would fail the run for something this arm cannot fix.
    Four prompts x three runs at `N = 16`, `KV_WIDTH` 256, dense Qwen2.5-Coder-7B Q4_K_M, CPU. Owner
    `gmake layer-forward-smoke`, whose fifth block gains a **three-step** pure-Python reference loop
    and a four-graph transcript; focused `gmake decode-step-qualification`. **No TTFT or throughput
    claim** — but the run measures the loop's `O(N x model bytes)` pack-read cost at
    `N in {1, 4, 16}`, which is the first concrete evidence for the resident-weight work R3/R5
    design. **What it leaves open:** the R6 gate below still asks that TTFT improve on repeated
    coding tasks sharing a prefix. `N` steps in memory, with no session reuse, no tiering, no
    invalidation, and weights re-read once per step, does not answer it; the gate stays unmet and
    the next capability toward it is resident weights.

29. **R6-KV-PERSIST — the KV plane persisted to disk and reloaded in a fresh process.** Design and
    results in [`r6-kv-persist.md`](r6-kv-persist.md). Items 27 and 28 build a correct KV plane and
    throw it away when the process exits, so every invocation on the same prompt recomputes the
    prefill. This capability ships the first of the five mechanisms the R6 gate lists — **session
    KV** — and nothing else: `--decode-step` gains `KV_SAVE` and `KV_LOAD` operands, and a new
    `akvp` v1 container holds the prefill plane, the prompt's token ids, the prefill's last-position
    logit vector, and an identity record binding all three to the exact pack, geometry, width, and
    plane layout that produced them. **Every mismatch is a refusal, never a silent re-prefill**:
    nineteen `R6_KV_*` codes plus item 27's own `R6_KV_WIDTH`, in a stated validation order,
    cheapest first, so a wrong file costs 192 bytes and one `fstat` rather than 29 MB. Acceptance is
    that the two paths are the same run — a separate process loading a saved plane decodes the same
    `N` ids and publishes a byte-identical document outside a named exclusion list, with item 28's
    gate G, oracle B, and oracle C′ carried forward and asserted on both processes, and with the
    writer's determinism proved by triple-write digest equality — including under a perturbed
    environment — rather than by a checked-in hex golden. The container's model identity is the
    **pack's** header-region digest and not the GGUF's, because `REFERENCE` is optional and a load
    run may not have the model at all. Owner `gmake layer-forward-smoke`, whose fifth block gains a
    save/load round trip, a 51-case refusal matrix over 13 independent reject kinds, and
    `scripts/kv_plane_reader.py` — a complete second implementation of the format, written from the
    specification and driven as a subprocess — plus a **third** implementation in
    `scripts/layer_forward_fixture.py`, whose container the arm loads and decodes. Focused `gmake
    decode-step-qualification`. **No TTFT claim.** The run reports `timings.first_token_ns` and the
    invocation wall clock for prefill-then-decode against load-then-decode as a labelled
    diagnostic. **What it leaves open:** the R6 gate asks that TTFT improve on repeated coding tasks
    *sharing a prefix*. There is no prefix-sharing corpus, no key, no lookup, and no invalidation;
    loading removes one prefill pass and keeps every per-step weight sweep, which item 28 measured
    at 4.37 GB per step. The gate stays unmet and the next capability toward it is prefix-keyed
    lookup on top of resident weights.

30. **R6-RESIDENT-WEIGHTS — the weight set held resident across decode steps.** Design and results
    in [`r6-resident-weights.md`](r6-resident-weights.md). Item 28 measured the term that dominates
    a decode loop: **one 4.37 GB pass over the pack per decode step**, 83 % of a sixteen-step run's
    elapsed time, re-reading weights the previous step already read. This capability removes that
    term. `--decode-step` gains a fourteenth operand, `RESIDENT` (`-` or `weights`); in resident
    mode the whole weight set — every layer, the head, and the **full** `token_embd.weight` table —
    is held in one Align-owned arena of 4,677,533,696 B on the reference model, filled once in 4,669
    one-mebibyte `pread`s, wrapped once as one `ggml_backend_buffer`, and read by every graph
    through `ggml_backend_tensor_alloc` at arena offsets. **A decode step then reads zero pack bytes
    and copies 2,016 host bytes.** No new shim symbol and no new Align surface: the zero-copy
    placement path has been the primary weight path since item 14 (R4.5). The primary metric is
    `weights.step_pack_bytes`, a counter and not a clock: **69,928,975,872 → 0** at `N = 16`.
    Measured on the reference host in one session, three runs per point with the two legs
    **interleaved**, baseline re-taken back to back: elapsed 17.112 s → 10.049 s, **412,763 ppm** of
    the fixed task against a 150,000 ppm floor this capability's own document defines, because no
    document owned Track B decode performance before it — **MET** at 2.75× the floor, and 70 % of
    the 586,000 ppm ceiling recorded in advance, which the runner reports as a shortfall with its
    cause (the one-time fill) rather than as a ceiling-estimation miss:
    `docs/specs/c8-speed-first.md` section 1 reserves that label for a result **far** below its
    ceiling, and its own worked precedent is 41 % of one. The whole qualification was taken four
    times, at 412,763 / 449,779 / 507,887 / 511,125 ppm; the first is the interleaved run and the
    conservative reading, and it landed 37,016 ppm below the lowest blocked run and 98,362 below the
    highest — a range comparable to their own 61,346 ppm spread, so with one interleaved run the
    magnitude is not separated from noise. What the re-measurement establishes is that the
    review-found order confound is removed, and that the direction argued from thermal drift was not
    confirmed. The byte metric was identical in every run and
    the clock is the secondary metric for exactly that reason. Residency is **slower** at
    `N = 1`, a coin toss at `N = 4` where the runs disagree about the sign, and decisive from 16 up
    — stated rather than hidden, and the practical reason the operand is opt-in. Correctness is free: the resident and streamed
    documents are byte-identical outside the `weights` object, the two pack counters, and the
    per-graph ggml buffer pair the run-scope hoist moves, so every decoded id, gate G, oracle A′,
    oracle B, and the logits oracle are re-run on the resident leg rather than inferred. The
    hoisted wrap is the ownership boundary item 17 refused once; the invariant it weakens is
    re-established at run scope in its own counter pair rather than loosened. CPU only; the Metal
    arm keeps the per-graph wrap item 17's abort requires. **Opt-in, because a host that cannot hold
    the arena aborts rather than refuses** (Request 35), so `scripts/run-decode-step` preflights
    physical memory and prints one `N/A` line below 12 GiB. Peak footprint rises from 504 MB to
    4.74 GB, which is the point of the capability and is published as `weights.resident_bytes`.
    Owner `gmake layer-forward-smoke`, whose fifth block gains nine cases including oracle R at one
    and three steps and a forced build in which a resident run fails with its arena live; focused `gmake decode-step-qualification`. **The R6 gate is still unmet:** this
    removes the per-step weight sweep item 29 left in place, and prefix-keyed lookup on top of it is
    the next capability toward the TTFT gate.

<!-- Items 34 and 35 are reserved: each was on a branch or in draft when the item beside it was
     written, so the numbers are claimed and the entries land with those branches. The gap is
     deliberate and must not be re-used. Item 31 landed with C4-REPAIR-MEASURED and item 32 with
     R6-OLMOE-DECODE, which are the two entries below. -->

31. **C4-REPAIR-MEASURED — one bounded model repair attempt in the provider-backed measurement
    path.** The first Track A capability since the C6-MEASURED wave, and the one that asks whether
    C4's roadmap gate can be closed with a model instead of a scripted patch. Design and results in
    [`c4-repair-measured.md`](c4-repair-measured.md), which owns the contract ledger, closure
    matrix, repair-prompt contract, cost ceiling, gate statement, and the implementation record.
    The design gate triggered on the `PROMPT_TASK_ROW` schema-2 per-attempt identity, a new frozen
    corpus scope, and a coordinated invariant across `scripts/prompt-evaluate.py`,
    `src/prompt_score.align`, and the corpus assets. After a first-attempt validation `FAIL`, the
    evaluator renders a repair prompt from the run's **own** redacted validation diagnostics, calls
    `prompt generate` a second time, and validates again; `generation_to_passing_patch_ns` then
    includes the repair, as C6 section 5.2 has always contracted and never exercised. The repair
    prompt carries the failing attempt's status labels, diagnostic summary, stdout, and stderr but
    **not its edit set**: the model's output lives only inside the adapter and is dropped when it
    returns, so a diagnostics-driven second attempt is what an evaluator-owned loop can deliver
    without breaking the freeze. That narrowing, and the two ways to lift it, are recorded in the
    plan. **The adapter and the validation runner are byte-identical**: both are frozen `FILE_SET`
    members of `canonical-v1`, so the loop is evaluator-owned and the corpus is a new freeze,
    `eval/prompt/canonical-v1r/` over the same three tasks with `maximum_repair_loops: 1` so the
    manifest itself is the cap. The 24 shared file-set members carry identical digests in both
    manifests. The gate: on 3 tasks x 2 variants x 2 paired samples at temperature 0 and
    `PAIRED_FIXED`, at least one (task, variant) pair fails at attempt 1 and passes at attempt 2 in
    **both** samples.

    **The gate is `NOT_MET`, and that is the published result.** The run made all 22 provider calls
    the ceiling allowed — 12 initial plus 10 repair — in 824.2 s (13 min 44 s) against a recorded
    60-minute ceiling. Every one of the ten repair prompts assembled from the run's own persisted
    diagnostics, re-derived byte-exactly against its own output, and fitted the budget at 8,123 to
    16,129 bytes of 65,536, so no section was ever dropped. **None of the ten recovered:**
    `repair_recovery_count` and `repair_recovery_paired_count` are both 0. The mechanism is
    delivered — measured, bounded, contained, re-derivable — and **C4's gate remains unmet by a
    model.** In the one failure mode where the model emitted an applicable patch at all
    (`record-codec-round-trip`, all four rows), attempt 2's patch had the same 1,008 bytes and the
    same observable `TEST` failure as attempt 1; only `patch_size_bytes` is persisted, so that is an
    inference and not a verified identity, and a patch digest is now a named deferral. In the other
    mode (`layer-precedence-frozen-module`, all four rows) attempt 1 already produced an empty
    patch, so more diagnostics were not the missing input. That splits the case for carrying the
    failing edit set into the repair prompt: it addresses the first mode and not the second.
    **No speed claim is made** — the 22 calls span 7.98 s to 64.67 s, an 8.1x ratio, and a first
    run of the same corpus at the same seeds spanned 8.13 s to 73.82 s at 9.1x while reproducing
    every correctness value exactly; the version-2 totals are a superset of the version-1 ones
    anyway. Named focused qualification
    `make c4-repair-gate`; it joins no aggregate. Multi-repair, corpus expansion, failure-memory
    feedback, a persisted patch digest, and converging the Align `verification_loop`/`repair`
    modules with this loop are deferred with resume conditions.

32. **R6-OLMOE-DECODE — `N` greedy decode steps on a routed model, and the per-step expert demand
    they make.** Design and results in [`r6-olmoe-decode.md`](r6-olmoe-decode.md). Item 26 computes
    one OLMoE prefill and measures that 33.36 % of the model's expert bytes are touched by it; item
    30 makes a dense decode loop read zero weight bytes per step. Neither can say what a *routed*
    decode step demands, and [`r3-residency-sim.md`](r3-residency-sim.md) section 8 — whose
    four-word finding is **the intervention is decode** — could only simulate it over llama.cpp's
    trace. This capability ships a **seventh arm**, `--moe-decode-step`, with `--decode-step`'s
    operand shape position for position and its own document kind `R6_MOE_DECODE_STEP` at schema 1:
    `N` greedy steps on OLMoE-1B-7B-0125-Instruct Q4_K_M over an Align-owned KV plane, each step
    resolving that step's top-8 claims in **all sixteen** layers and computing only those experts,
    weights **streamed**. Weights are streamed **because residency would destroy the measurement** —
    item 30 makes `step_pack_bytes` zero by construction — so the two are mutually exclusive in one
    invocation and demand measurement comes first. The design's probe record settles three things
    before implementation, from two full-axis transcripts the item-22 instrument had already
    produced: a decode graph does **not** narrow, so all sixteen layers route and the routing oracle
    compares 8 of 8 slots on 16 of 16 layers where item 26 compared 546 of 728; the per-step demand
    is therefore exactly `3,900,702,720 / 8 = 487,587,840` bytes, **125,000 ppm**, prompt- and
    step-independent, and the same number `r3-residency-sim.md` section 8.1 publishes as the decode
    arms' one-token working set; and the open quantity is the **union**, which over four steps on
    one prompt grows 128 → 274 keys of 1,024 while **79.9 %** of those 274 *distinct* decode keys
    were already read by the prefill. The plane is OLMoE's geometry in item 27's unchanged layout,
    67,108,864 B at width 256 — **2.29×** the dense arm's on a model with a fifth of the parameters,
    because sixteen KV heads beat twenty-eight layers. What it needed that did not exist: an
    `OP_CONCAT` and a `WHEN_DECODE` condition in `src/layer_olmoe.align`, and a **thirty-seven-row**
    decode phase-A table — `WHEN_WIDE` cannot be reused, because `ggml_pad` writes its source at
    index 0 and a decode step's new column belongs at `n_past`. `MAX_PREFILL_TOKENS` moves
    **6 → 32** so the self-reference oracle can run at `T + k` tokens, and the guard that keeps the
    cap's original reason is **new**: `--moe-layer-forward` and `--moe-model-forward` did not ship
    `R5_ORACLE_TRUNCATED` because at a cap of 6 the condition was unreachable, and both now refuse a
    prefill above six tokens *with* a transcript exactly as the dense arms do. **No new ggml op, FFI
    symbol, or shim body**, and `src/decode_step.align` is byte-unchanged; the dense arm's
    `R6_ARCH_UNSUPPORTED` refusal keeps its meaning and gains a documented answer. Acceptance is
    stated once in `r6-olmoe-decode.md` section 4.6: **gate G**, the `N` ids equal llama.cpp's over
    a vocabulary whose fingerprint collision classes are measured before the gate is claimed;
    **oracle R**, routing identity `MATCH` at every step over 128`N` of 128`N` ids; **oracle B**, the
    plane round trip `IDENTICAL` at every step including the column that step wrote; **oracle C′** at
    `k ∈ {1, ⌈N/2⌉, N}`; and **oracle T**, structurally complete at every step and numerically
    admitted at step 1 only. **Measured**, four prompts x sixteen steps in 3 min 18 s: gate G over
    64 ids, oracle R **`MATCH` at 8,192 of 8,192**, oracle B `IDENTICAL`, oracle T `PASS` with
    `max_abs_diff` **0**, `expert_bytes` and `expert_pread_bytes` **both exactly 487,587,840 on all
    64 steps** — a read amplification of **zero**, so the arm read exactly what it claimed. The
    union over sixteen steps reaches 585, 698, 614 and 607 keys of 1,024, and the mean marginal cost
    is 57.9, 92.3, 95.4 and 83.1 MB against the 487.6 MB a streamed step reads: **a 5.1x to 8.4x
    gap**, which corrects the 9.2x a four-step probe suggested and is the honest size of the case for
    a decode-side residency policy. "Four fifths of every decode demand is already in the prefill's
    union" is likewise a short-window artifact: over sixteen steps it is 52.0 % to 75.2 %. Oracle C′
    demoted to **characterization** by its own measurement — `mul_mat_id` is not stack-shape
    invariant, 1 of 12 checkpoints byte-identical and 12 of 12 argmax-equal — exactly as the design
    wrote both branches in advance. Owner `gmake layer-forward-smoke`, whose **seventh** block gains a
    routed decode loop over the synthetic two-layer MoE model and runs the whole seven-block runner in
    80 s; focused `gmake moe-decode-step-qualification`. **No TTFT or throughput claim and no cost ceiling** — the
    claim is a byte demand and the byte counters are exact, published twice, arithmetically and from
    the pack reader's own `pread` accounting, with a bounded relation between them. **What it leaves
    open:** the R6 gate still asks that TTFT improve on repeated coding tasks *sharing a prefix*. A
    routed decode loop that streams its weights and shares no prefix does not answer it; the gate
    stays unmet, and the next capability toward it is resident dense weights with streamed experts,
    whose input is this capability's per-step demand stream.
33. **R6-PREFIX-SUFFIX-PREFILL — a saved prefix plane continued with a different suffix.** Design
    and results in [`r6-prefix-suffix-prefill.md`](r6-prefix-suffix-prefill.md). Item 29 made a
    prefill plane outlive its process; it could only be reloaded for the prompt it was saved for,
    because the arm had no graph that computes more than one column at `n_past > 0`. This capability
    ships that graph. `--decode-step` gains a fifteenth operand, `SUFFIX` (a token id list or `-`),
    legal only with `KV_LOAD`: the arm loads a container holding `T_prefix` columns for exactly the
    tokens in `TOKENS`, runs **one suffix pass** — a decode-shaped graph set over the `S` suffix
    tokens at absolute positions `T_prefix .. T_prefix+S-1`, causally masked over prefix-plus-suffix,
    writing the suffix's K and V into the plane at columns `T_prefix ..` — and then continues the
    existing `N`-step loop from `n_past = T_prefix + S`. Nothing is re-saved and the `akvp` format is
    **byte-unchanged**, which is a consequence of keeping `TOKENS` meaning "the container's tokens":
    every `R6_KV_*` identity check holds character for character, and `ds-suffix-tokens-mismatch`
    proves it by having an **unmodified** L12 refuse a container written for the whole list when a
    run supplies that list as a prefix. No new ggml op, shim symbol, node row, slot, or Align
    surface: the decode node table becomes parameterised by its token count — **six** literals, one
    more than the design predicted — and `mf_write_mask_offset` and `capture_plane` are called for
    the first time with **both** of their existing parameters non-trivial. The oracle is that a
    suffix run and a single-shot prefill of `TOKENS ++ SUFFIX` are **the same run**: byte-identical
    documents outside a fixed exclusion list, byte-identical logits against `--model-forward` at the
    whole prompt, byte-identical logits against `llama-debug --save-logits`, and identical decoded
    ids, with the plane round trip verified over `T_prefix + S` columns before the first decode step.
    Measured on the real model at every split, and hosted on three splits of a two-layer synthetic
    model — where the design's load-bearing risk, that ggml's `MUL_MAT` selection might be
    column-count-sensitive at `S >= 2` **and** `n_past > 0`, was discharged on the first
    implementation checkpoint and never reappeared. Document schema **5** with a `suffix` object in
    every document; `output` and `oracle_logits` describe the suffix pass's own logits on a completed
    suffix run, with the container's vector still published in `kv`. Exact prefixes only: RoPE
    positions are absolute, so prefix sharing is inherently **left-anchored**, and prefix truncation
    is deferred. Owner `gmake layer-forward-smoke`, whose fifth block gains 22 cases and 21 golden
    rows — three oracle-S splits, twelve refusals, and two forced builds that publish a partial pass,
    plus a four-token comparand kept out of the cross-platform golden because its `l_out` digest
    differs between arm64 and x86_64 in the last bit (section 11.3 deviation 7); focused
    `gmake decode-step-qualification`, which splits each of the four prompts at up to two points and
    needs **no new `llama-debug` run and no new instrument run**, because the split is on ids the
    instrument already printed. **The R6 gate is still unmet:** this ships the *execution* half of
    mechanism 2 (repo stable prefix KV) and none of its *lookup* half — there is still no prefix key,
    no store, no corpus, and no prefix-sharing consumer — so TTFT is reported as a labelled
    diagnostic on three legs and no claim is made. One surface shipped **narrower than the mechanism
    allows**: `T_prefix >= 2` was required, raising `R6_SUFFIX` with detail `prefix[<n>]`, because a
    one-token prefill computed the embedding of token 0 whatever the operand said. **Item 36 removed
    that defect and this branch lifted the bound**, so a one-token prefix is accepted and
    `ds-suffix-prefix-one` is a passing oracle-S run rather than a refusal.

    **Follow-up, discharged: `MF-SINGLE-TOKEN-LOGITS`, item 36 below.** A pre-existing defect this
    capability found in an arm it does not touch: `fill_members` and `compare_source` gathered an
    embedding row by id only where `pieces > 1`, so **any prompt of exactly one token computed the
    logits of token 0**, silently and with `status: ok`. Section 11.2 of
    [`r6-prefix-suffix-prefill.md`](r6-prefix-suffix-prefill.md) filed it and item 36 measured its
    blast radius, correcting three of that record's claims: four arms, but **not the four named**
    (`--layer-forward` and `--moe-layer-forward` gather unconditionally and were never affected,
    while `--model-forward-gpu` is), **nine** construction sites and not eighteen (ten once item 32
    landed), and the resident
    path is **not** immune — `stage_embed_row` staged the right row while `compare_source` still
    expected row 0, so a one-token non-zero resident run with a reference reported
    `R5_SOURCE_DIVERGED` over a correct result. It was filed outside item 33 because it would have
    put an R5B correctness change inside a review scoped to a suffix graph.

35. **R6-MOE-RESIDENT-DENSE — the dense third of a routed decode step, held resident, with the
    expert measurement unmoved.** Design and results in
    [`r6-moe-resident-dense.md`](r6-moe-resident-dense.md). Item 30 made a *dense* model's decode
    step read zero weight bytes and item 32 measured what a *routed* decode step reads:
    **740,666,496 B**, of which 487,587,840 is the top-8 routing decision in all sixteen layers and
    **253,078,656 is dense weight the previous step already read** — the same bytes on every step of
    every prompt, because the dense half of a routed model does not depend on the routing. This
    capability removes that third. It takes item 32's **reserved fourteenth operand**, `RESIDENT` at
    `args[13]` with the value `dense` (arity 14, with `-` required in the two reserved KV positions
    and `R6M_KV_UNSUPPORTED` otherwise, so a reserved position stays reserved), holds the pack's
    **147 dense members** — the 57,950,208 B `token_embd.weight` table, sixteen layers of attention,
    norms and router at `8 x 9,994,240 + 8 x 11,075,584 = 168,558,592`, and the 84,520,960 B head —
    in **one 311,066,624 B region under one run-scope ggml wrap across all 578 graphs**, replacing
    306 per-graph dense-window wraps with one, and leaves the 3,900,702,720 B of expert planes
    streaming through the claim window untouched. **The measurement survives, which is the whole
    point:** `steps[].residency.expert_bytes` and `expert_pread_bytes` stay **487,587,840 on every
    step in both legs** with 0 ppm read amplification, and that is an acceptance clause rather than
    an expectation. `R6_MOE_DECODE_STEP` goes to **schema 2** with a `weights` object item 32 had
    deliberately left absent; the primary metric is the new **`weights.step_dense_pack_bytes`**,
    exactly **0** in `dense` mode against **4,049,258,496** streamed at `N = 16`, while
    `weights.step_pack_bytes` keeps `r6-resident-weights.md`'s exact meaning so one name does not
    mean two things across two decode arms. **`docs/specs/r6-resident-weights.md` section 3.4
    remains the owner of Track B decode performance**; this capability records its ceiling against it
    and adopts its **150,000 ppm floor unchanged**: baseline 3.63 s at `N = 16` on the fixed prompt,
    **cost ceiling 276,000 ppm** committed in the commit *before* the implementation commit — the
    process correction item 30 said it owed its successor — predicted 2.63 s, measured with the two
    legs **interleaved**, three repeats, **worst-of-N**, and a pre-committed `INDETERMINATE` rule for
    the case where this arm's 3.63 s baseline is noisier than the ceiling is wide.
    **What it measured.** The byte claim holds exactly and is host-independent: at all twelve
    points — four prompts x `N` in {1, 4, 16} — `weights.step_dense_pack_bytes` is **0** in `dense`
    mode against `253,078,656 x N` streamed, `weights.step_expert_pack_bytes` is `487,587,840 x N`
    in **both** legs, `weights.resident_bytes` is **311,066,624** (equal to an independent walk of
    the pack document's 147 dense member records), `weights.wrap_count` is **306 -> 1**, and
    **oracle D is `MATCH` on all four prompts**. The elapsed leg is **`BELOW FLOOR`** and is recorded
    as such. It was measured twice. The **measurement of record** is the quiet-host run (section
    12.4), taken with no `llama-server`, no container and a completely clear process table at
    8.47 GB free, which **reproduced the committed baseline** — streamed `[3.458, 3.551, 3.928]` s
    against 3.63 s, a median 21,693 ppm away — and removed **138,402 ppm** at the fixed task
    worst-of-3, **92 % of the 150,000 ppm floor and 50 % of the 276,000 ppm ceiling**. The median and
    best-of-3 readings are 86,825 and 84,187 ppm, so no reading clears the floor; the other three
    prompts at `N = 16` give 138,128, **156,687** and 147,670 ppm, so one prompt does clear it and it
    is not the fixed task, which section 3.7 chose before any number existed. `INDETERMINATE` does
    not apply (streamed spread 129,116 ppm) and the `miss` label does not either (the result is above
    half the ceiling, so the ceiling estimate was sound and the seam is simply thin, as section 3.7's
    1.84× margin predicted). **No elapsed claim is made**; per section 4.6 clause 12, stated in
    advance, clauses 1 to 11 carry the capability. A first run on a contended host (section 12.5) is
    kept as evidence with its 857,000 ppm baseline drift stated: its byte results are identical to
    the quiet run's in **every** field, which is what a counter is supposed to do. `gmake moe-decode-step-qualification` itself refuses on this host at
    its **instrument cross-check**, reproducing item 32's deviation 4 to the digit, which is item
    32's condition and not this capability's.
    **There is no crossover:** unlike item 30, whose 4.68 GB fill loses at `N = 1`, this fill costs
    only the 57,943,296 B of embedding table the prefill did not already read, so `N = 1` and
    `N = 4` are small wins — below the floor, published as diagnostics, and not claimed. Peak
    footprint grows 347,451,392 -> 573,997,056 B, a factor of 1.65 against item 30's 9.4, **so no
    physical-memory preflight ships and Align Request 50 gains no client**. `src/decode_step.align`,
    `src/model_forward.align`, `src/layer_olmoe.align`, `src/ggml_spike.align`, and both shims are
    **byte-unchanged**; the one new function is `moe_model_forward.plan_resident_dense`, a twin of
    `model_forward.plan_resident` that Align's missing generics force (Request 49's newest and
    sharpest-shaped client, and roughly 65 lines rather than 40 because three of the arithmetic
    helpers it needs are private). Correctness is **free**: oracle D compares the two legs' whole
    normalized documents outside the `weights` object and an enumerated ten-name exclusion, and
    gate G, oracle R, oracle B, oracle T and oracle C' are all re-run on the resident leg. Owner
    `gmake layer-forward-smoke`, whose seventh block gains eleven golden rows, a staging-boundary
    case with no golden row, two no-document arity cases and a forced build in which a `dense` run
    fails with its region live;
    focused `gmake moe-decode-step-qualification`. **What it leaves open:** the R6 gate still asks
    that TTFT improve on repeated coding tasks *sharing a prefix*, and a decode loop that shares no
    prefix does not answer it; the next capability toward it is partial **expert** residency, whose
    input is item 32's union curve and this capability's freed footprint.

36. **MF-SINGLE-TOKEN-LOGITS — the one-token prefill reads the prompt's embedding row.** Design,
    blast radius, and results in
    [`mf-single-token-logits.md`](mf-single-token-logits.md). A bug fix, filed by
    R6-PREFIX-SUFFIX-PREFILL section 11.2 and numbered 36 because **31, 32, 34 and 35 are reserved
    by capabilities that were on branches or in draft at the time of writing** and this one merged
    out of order; the numbering is a name, not a delivery order. `fill_members` and `compare_source` gathered a
    member's rows by token id only where `pieces > 1` — the piece count used as a **proxy** for
    "this member is the per-token embedding row set". `build_embed_members` sets `pieces = tokens`,
    so a one-token prefill took the whole-member branch and read **row 0 of the embedding table**
    instead of the prompt's row: wrong logits with `status: ok`. Four public arms were affected —
    `--model-forward`, `--model-forward-gpu`, `--moe-model-forward`, and `--decode-step`'s prefill —
    across ten `GraphMembers` construction sites in four modules — nine when the fix was written
    and a tenth with item 32's `moe_decode_step`; `--layer-forward` and
    `--moe-layer-forward` were not, because they gather unconditionally. The resident path was not
    immune either: `stage_embed_row` staged the right row while `compare_source` still expected
    row 0, so a one-token non-zero resident run **with** a reference reported `R5_SOURCE_DIVERGED`
    over a correct result. The fix is a `gathered: bool` on both `GraphMembers` records and the
    predicate `m.gathered && at == 0`, which is true exactly where `pieces > 1` was, so `T >= 2` is
    byte-identical and **the gather fix changes no existing golden row in any of the six corpora**.
    Its regression is therefore **six new rows** rather than a changed one — a one-token control at
    id 0 and a one-token non-zero id on each affected arm, plus the streamed/resident equality pair
    whose `R5_SOURCE_DIVERGED` false alarm disappears. *(The item 33 lift this branch also carries
    adds one more row and removes `ds-suffix-prefix-one`'s, so the branch as a whole adds seven
    golden rows, removes one, and changes none. That row leaves because a passing two-token run is
    host-dependent in its decode step — measured on hosted CI — and is asserted from
    `BOUNDARY_CASES` without a pinned digest, as item 33's own four-token comparand is.)* The
    real-model half is
    `--model-forward` at one non-zero token byte-identical to `llama-debug --save-logits` on the
    same one-token prompt, with the tokenization checked rather than assumed. Owner
    `gmake layer-forward-smoke`; focused `gmake model-forward-qualification` and
    `gmake moe-model-forward-qualification`. No Align gap and no design gate: no CLI operand,
    persisted format, or ownership boundary moves. **It also widens item 33's accepted surface**:
    that capability's `T_prefix >= 2` bound existed only because of this defect, so this branch
    lifts it — the `R6_SUFFIX prefix[<n>]` refusal is gone, `ds-suffix-prefix-one` becomes a passing
    oracle-S run at `T_prefix = 1`, and `r6-prefix-suffix-prefill.md` sections 3.7, 5.6 and 11 record
    the lift.

34. **C4-REPAIR-EDITSET — the failing edit set in the repair prompt, through a second
    corpus-member adapter.** The direct consequence of item 31's measured negative. C4-REPAIR-
    MEASURED ran ten repair attempts and recovered nothing, and its evidence names the reason:
    on all six repair attempts where attempt 1 had produced a validated edit set, attempt 2
    returned a patch of exactly the same byte count. The model was never shown what it wrote.
    Design in [`c4-repair-editset.md`](c4-repair-editset.md), which owns the contract ledger,
    the import-by-path contract, the closure matrix, the repair-prompt contract version 2, the
    cost ceiling, the gate statement, and the implementation record. The design gate triggered on
    the `TASK_MEASUREMENT` schema-2 exchanged format, a new frozen corpus scope with a **second
    adapter** as a member, and a coordinated invariant across the new adapter,
    `scripts/prompt-evaluate.py`, `src/prompt_score.align`, and the corpus assets.
    `scripts/prompt-repair-adapter.py` **loads the frozen `scripts/prompt-measurement-adapter.py`
    by path** and calls its functions, so the reviewed containment, sealing, redaction, and
    process-ownership code has exactly one copy and the second file carries only the sequencing
    that differs — which is what makes item 31's section 5.7 option B affordable now that its
    tie-breaker has been answered. Only `measurement()` and `assemble()` are near-copies, and
    their divergence from the frozen originals is asserted against a checked-in golden. Three
    digest pins hold the base file byte-identical: a constant in the new adapter, the file-set
    manifest, and the per-invocation artifact snapshot. `TASK_MEASUREMENT` moves to
    `schema_version: 2` with the attempt's realized edit set, its total size, a **digest of the
    complete patch body**, and the base adapter's runtime identity; version 1 stays decodable
    forever, and `PROMPT_TASK_ROW` does **not** move, because the row gains no field. The repair
    prompt gains an `EDITSET` section rendered in the response's own whole-file format, bounded
    whole-block, and dropped **last** — after STDOUT, STDERR, and SUMMARY — so an over-budget row
    degrades into the diagnostics-only prompt that already measured zero recoveries only as a last
    resort, and `repair_editset_attempt_count` keeps a dropped row out of every edit-set
    denominator. New freeze `eval/prompt/canonical-v1e/` + `eval/tasks/prompt-v1e/`, 30 file-set
    members; the 24 shared with both earlier corpora carry identical digests in all three
    manifests. **The addressable arm is six of ten repair attempts.** The other four are
    `layer-precedence-frozen-module`, where the model emits well-formed blocks naming allowlisted
    files and fills them with the files' **existing** content, so every hunk is empty and no patch
    is synthesized — a no-op answer rather than a format failure, and the design's original
    "no parsable block" reading is corrected against the evidence in section 1.2. That mode is a
    prompt and edit-policy capability and is named as the fallback. Found by probe and closed here: a second adapter that
    reused the frozen `environment_probe()` would persist the **imported** file's digest while
    running its own code, and the existing check would accept it; the same probe found that no
    producer or runtime-identity check existed on an *attempt-level* measurement's probe at all.
    The gate is item 31's predicate unchanged: `repair_recovery_paired_count >= 1`. **A measured
    negative is a published result**, and here it is directional — it would answer item 31's
    tie-breaker in the negative and move the next capability from the adapter to the prompt.
    No speed claim: the item 31 run measured an 8.1x spread over 22 calls at temperature 0, and the
    repair prompt is a strict textual extension of the attempt-1 prompt, so prompt-cache reuse is
    an uncontrolled confound. Recorded run-cost ceiling 60 minutes, expected 12-30, at most 22
    provider calls. Named focused qualification `make c4-editset-gate`; it joins no aggregate, and
    neither does the new owner test `make prompt-repair-adapter-smoke`.

    **The gate is `NOT_MET`, and that is the published result.** The run made all 22 provider calls
    the ceiling allowed — 12 initial plus 10 repair — in 839.492 s (13 min 59 s) against a recorded
    60-minute ceiling. `repair_recovery_count` and `repair_recovery_paired_count` are both 0.
    `repair_editset_attempt_count` came out at **exactly 6**, the value fixed before the run, so
    the addressable arm was realized in full: every repair prompt that could carry `EDITSET` did,
    and the drop ladder never fired at 8,348 to 16,904 assembled bytes of 65,536. **The question
    item 31 could not answer is answered.** On all four rows where both attempts produced a patch,
    `attempts[1].measurement.patch_sha256` equals `attempts[0]`'s exactly — the same bytes, not
    merely the same byte count — so item 31's inference is now a verified identity. The persisted
    edit set says more: on the two `record-codec-round-trip` CANDIDATE rows the model re-emitted a
    byte-identical edit set, while on the two PARENT rows it dropped the file it had reproduced
    unchanged and kept the other byte-identical, producing the same patch anyway. On the two
    `duration-half-away-from-zero` PARENT rows it changed mode and got worse: shown its own
    rejected answer it returned the pinned files **unchanged**, so every hunk is empty and no patch
    is synthesized — a wrong patch replaced by a no-op. **Item 31's section 5.7 tie-breaker is
    therefore answered in the negative:** on this model and this corpus the missing edit set was
    not the binding constraint, and the next capability is the prompt, the template, and the edit
    policy rather than more adapter work. Its first sub-problem is this capability's own recorded
    gap — `edit_set` is `None` on every `PATCH` row (design section 11.3 deviation 14) — so the
    answers the dominant mode produces are exactly the ones no artifact shows. Evidence in
    `eval/prompt/c4-editset-gate/`; the per-row table and the analysis are in design section 11.4.

37. **R6-PREFIX-KEY — a content-addressed store for prefix planes.** Design and results in
    [`r6-prefix-key-corpus.md`](r6-prefix-key-corpus.md). `--decode-step` gains a sixteenth operand,
    `STORE`, a directory that is mutually exclusive with `KV_SAVE` and `KV_LOAD`. The arm **derives**
    the key `r6-kv-persist.md` section 2.8 recorded in advance — `(source_header_region_sha256,
    geometry_sha256, token_stream_sha256, kv_width, plane_layout_version)`, plus `pack_total_bytes`,
    `token_count`, `element_type`, `format_version`, and a `key_version` — as a SHA-256 over a
    152-byte preimage, and addresses `<STORE>/<key-hex>.akvp`. **A hit loads; a miss prefills, saves,
    and continues**, and the two produce byte-identical documents outside the store's own three
    moving fields and item 29's own exclusion set — oracle K, the capability's acceptance rule, which
    holds on the hosted fixture on three pairs (plain, `+SUFFIX`, and resident). **A miss
    is only a missing file**: a container that exists and fails any identity check is that check's
    refusal and never a silent re-prefill, which keeps item 29's invalidation rule character for
    character; three hosted rows place a broken container at a key path and assert exactly that. The
    `akvp` v1 format is **byte-unchanged** and the hosted owner asserts, by SHA-256, that a `STORE`
    container is byte-identical to a `KV_SAVE` one — including for a miss that has a suffix, which is
    what pins *when* a miss saves. Schema **6** adds a `store` object
    published in every document including error documents; **no path is published**, so the key — a
    digest, not a clock or a machine path — is golden-stable, and the whole 139-row decode-step
    golden moves only in the document's own `schema_version` plus that object, verified mechanically
    — the container header's separate `document_schema_version` field stays **3**, as
    `r6-prefix-suffix-prefill.md` section 2.9 requires. One byte
    layout has three implementations (the arm, `scripts/kv_plane_reader.py` checking that a container
    is at its own name, and the smoke recomputing it from the document's own published digests) and
    oracle D asserts all three agree, with five determinism rows changing one preimage field each.
    **No new refusal code is minted**: step 2d adds two `R6_KV_ARGS` details and a miss whose create
    fails is `R6_KV_UNWRITABLE store[create]` — one code for three causes the pin cannot separate,
    which is Request 53's client evidence. Owner `gmake layer-forward-smoke`; focused
    `gmake decode-step-qualification`, two extra invocations per prompt, **run on the reference host
    and PASS**: four prompts, a keyed miss and a keyed hit each, oracle K / oracle S / gate G1 /
    oracle B all IDENTICAL on both legs, four distinct keys addressing four 29,970,432 B containers
    each byte-identical to `KV_SAVE`'s, and the leg costing 48.71 s of a 15 min 38 s
    target. **No TTFT or throughput
    claim and no cost ceiling** — `CLAUDE.md`'s performance row is not selected; the runner's TTFT
    figures stay a labelled diagnostic. Stacked on item 36, whose lift of the `T_prefix >= 2` refusal
    a store that *writes* containers requires. One new Align request, **53** (`std.fs` directory
    operations), `PROPOSED` and non-blocking. **What it leaves open:** the R6 gate asks that TTFT
    improve on repeated coding tasks sharing a prefix. This discharges two of item 33 section 1.4's
    four reasons — there is now a key and a store — and leaves the corpus and the consumer.
    `MAX_PREFILL_TOKENS` is still **32**, so the largest legal prefix is 32 tokens and no real prompt
    reaches it; the compositional shared prefix of `eval/prompt/canonical-v1` measures **369 tokens** against
    suffixes of 697, 828, and 1,050 (section 1.2). Item 38 lifts the cap, pins the corpus, and takes
    the gate measurement.

38. **R6-PREFIX-TTFT — the prefill cap lifted, the corpus pinned, and the R6 gate measured.**
    **Implemented; the corrected replacement measurement at `de4cb6e` passes both the roadmap
    improvement gate and the shipping floor. The earlier result measured at `eb832bf` remains
    withdrawn because the record-codec prompt was escape-rewritten during corpus generation.** Its
    charter is section 11 of
    [`r6-prefix-key-corpus.md`](r6-prefix-key-corpus.md), written **before** item 37 was implemented
    so the split is a schedule rather than a hope, and it needs its own design gate and its own
    ledger before implementation. The ledger and closure matrix are
    [`r6-prefix-ttft.md`](r6-prefix-ttft.md). The required first-action probe is complete: at 1,200
    tokens, three resident runs measured mean first-token **129.31 s**, prefill compute **123.41 s**
    (**95.44%**), and a 38,606 ppm range. The precondition therefore passes. Before the 168 MiB
    container-read subtraction, the corrected measured ceiling is **290,920 ppm** at the mean prefix share and
    **248,183 ppm** at the worst, above the unchanged 150,000 ppm floor. Implementation lifts
    `MAX_PREFILL_TOKENS` from 32 to 2048 — a constant read as
    code by seven `.align` modules and four scripts and **bound into a persisted header field**, so
    the lift is a one-way compatibility step — pins `eval/kv/prefix-corpus-v1` from the qualification's
    own instrument, and measures TTFT on the paired single-shot and keyed-hit legs. Its first
    implementation step is a **baseline probe, not code**: the ceiling is
    `(T / (T + S)) x (prefill compute / single-shot TTFT)`, whose first factor is already measured at
    **0.30482 mean and 0.26004 worst**, so the gate is reachable only if this arm's resident prefill
    runs at or below roughly 200 tokens per second on the reference host — a falsifiable precondition
    written before any number exists. The floor (150,000 ppm, adopted from `r6-resident-weights.md`
    section 3.4), the two cache protocols, and the pre-committed MET / NOT_MET / INDETERMINATE rule
    are all fixed in section 11 in advance.

    The corrected frozen corpus is a 369-id shared prefix plus three suffixes of 697, 1,050, and 828
    ids. The replacement five-repeat warm and complete-file-eviction measurement completed all 30
    pairs and 66 fresh processes. W's leave-one-suffix-out range is 291,511..321,192 ppm; C's is
    306,038..336,707 ppm. W is worse, and its 291,511 ppm minimum exceeds the 150,000 ppm floor, so
    both the improvement gate and shipping verdict are **MET**. The audited evidence identity,
    withdrawn-run isolation, and review finding are recorded in
    [`r6-prefix-ttft.md`](r6-prefix-ttft.md) section 8.

> Items 35 and 36 are claimed on sibling branches (`agent/r6-moe-resident-dense`,
> `agent/mf-single-token-logits`); 37 and 38 are reserved for Track B's `R6-PREFIX-KEY-CORPUS`,
> which its own charter note allows to split into `R6-PREFIX-KEY` and `R6-PREFIX-TTFT`. Item 39 is
> numbered on that assumption and corrected at reconciliation if it changes. The numbering is a
> name, not a delivery order — item 36's own precedent.

39. **C4-REPAIR-TEMPLATE — the prompt template and the declared edit policy.** The capability
    item 34 named as its own successor, and the one that corrects the record item 34 wrote.
    **Read the evidence again and it says something else.** Every `failure_kind: PATCH` row in
    both gate runs carries `diagnostic_summary: "the response reproduced the pinned files
    unchanged"` — `synthesized_patch`'s refusal, which fires only *after* `parse_file_blocks`
    returned terminated blocks and `validated_edit_set` accepted every path. The string "the
    response declares no file block" appears in **zero** rows. The model never failed to produce
    a parsable `FILE:` block; it produced correct blocks whose bodies were byte-identical to the
    pinned source. Ten of twenty-two ran attempts in each run were refused by the edit policy —
    eight for reproducing the files unchanged, two for naming a path outside the editable set —
    and that is the largest failure class in either run. Design in
    [`c4-repair-template.md`](c4-repair-template.md), which owns the contract ledger, the
    import-chain contract, the closure matrix, the prompt contract version 3, the cost ceiling,
    and the gate statement. The design gate triggered on the version-3 repair-prompt exchanged
    format, on `TASK_MEASUREMENT` schema 3 and the declared `edit_policy` persisted format, on a
    new frozen scope with a **third adapter** and **three new task prompts** as members, and on a
    coordinated invariant across the new adapter, `scripts/prompt-evaluate.py`,
    `scripts/prompt-gate-validator.py`, `src/prompt_score.align`, and the corpus assets. **The
    rule the model actually broke is stated in no prompt in the repository**: nothing anywhere
    says that a block identical to the file's current content is refused. Version 3 says it, in
    the task prompt and in the repair template, next to a worked example and the editable-path
    allowlist — both of which the task prompt already carried and the model violated anyway, so
    the statement is repeated rather than introduced. **The `FILE:` grammar does not change**: it
    has never failed in 44 calls. `MAXIMUM_FILE_BLOCKS` (32), `MAXIMUM_EDIT_BYTES` (262,144), and
    `synthesized_patch`'s unstated unchanged-file refusal become a declared `EDIT_POLICY` record
    on the task manifest, validated as equal to the constants the pinned adapters enforce and
    refused as `INVALID_INPUT`/`EDIT_SET` otherwise; it cannot live in the task definition,
    because the frozen validation runner refuses any extra key there. `TASK_MEASUREMENT` moves to
    `schema_version: 3` with a ten-code `edit_refusal`, the completion's bounded identity, a
    **conditional** bounded completion excerpt persisted only where no structured substitute
    exists, and a widened `edit_set` rule so the reproduced-unchanged refusal keeps the blocks it
    already built and then threw away. Versions 1 and 2 stay decodable forever and
    `PROMPT_TASK_ROW` does **not** move. `scripts/prompt-template-adapter.py` loads
    `scripts/prompt-repair-adapter.py` by path, which loads the frozen base adapter by path, so
    containment still has exactly one copy and each hop's divergence is a checked-in golden.
    Measured freeze `eval/prompt/canonical-v1t/` + `eval/tasks/prompt-v1t/`, 31 members, 22 carried
    from `canonical-v1e` at identical digests and 21 of those identical in all four manifests. It
    is sealed after measurement: its check command is read-only and write invocations fail. Review
    repair is isolated in the distinct, unqualified `canonical-v1u` + `prompt-v1u` successor; its
    24-call topology is rejected before provider access against the unchanged 22-call ceiling.
    **Attempt 1 changes too**, identically for both variants, because six of the ten refusals are
    attempt-1 refusals and time to a passing patch is the primary metric; the cost, stated before
    the run, is that this run measures the version-3 contract end to end rather than the repair
    template alone. The gate is item 31's predicate unchanged,
    `repair_recovery_paired_count >= 1`, with a pre-committed secondary `edit_refusal_count < 10`.
    **The prompt-size hypothesis is refuted before the run**: the largest repair prompt in either
    run is 16,904 bytes of a 65,536-byte budget, no section was ever dropped, and the refused rows
    carry the smallest prompts. A `NOT_MET` gate has two readings and both are fixed in advance:
    refusals fall and nothing recovers, which points at corpus difficulty; or refusals do not
    fall, which points at the model and the decoding strategy and at nothing in the prompt. No
    speed claim. Recorded run-cost ceiling 60 minutes, expected 12-30, at most 22 provider calls.
    Named focused qualification `make c4-template-gate`; it joins no aggregate, and neither does
    `make prompt-template-adapter-smoke`.

    **The named qualification failed its call ceiling; the observed predicate value is 1 and the
    capability is unchanged.** The clean committed-head run made 24 calls in 700.452 s, exceeding
    the pre-committed maximum of 22 calls even though it stayed inside the separate 60-minute wall
    ceiling. Its immutable gate record incorrectly hard-codes `addressable_ran_attempts: 22`; the
    correction is recorded in the owning spec and evidence README. `repair_recovery_paired_count`
    is 1, but its only
    pair is `duration-half-away-from-zero` CANDIDATE: a pair that passed first-shot at 758 bytes in
    both prior runs now fails attempt 1 at 724 bytes and recovers to the same 758-byte patch at
    attempt 2. Version 3 introduced the failure it then repaired. `candidate_pass_count` stays 2,
    `completion_gain_count` stays 2, and no new task passes. The pre-committed secondary is also
    unmet: `edit_refusal_count` stays 10 against `< 10`. `PATH_NOT_EDITABLE` does move 2 -> 0, but
    those attempts become `UNCHANGED_FILES`, whose persisted breakdown is now 10. Section 1.6
    reading (b) applies: on `layer-precedence-frozen-module` the model re-sends the same pinned file
    despite the rule appearing three times, so neither adapter nor prompt is binding; the remaining
    axes are model and decoding strategy and require a different experimental design. The shipped
    value is the declared policy, machine-checkable refusal vocabulary and aggregate, retained edit
    blocks, and whole-answer identity — not a recovery or speed claim. Evidence and the per-pair
    analysis are in the design's section 11.4.

40. **DEV-OUTPUT-SUMMARY — preserve full verification evidence while making successful local,
    CI, and toolchain output concise. Planned immediately after item 38 publishes, before R7 unless
    a product blocker becomes eligible.** Repeated successful Align builds currently send hundreds
    of identical compiler-warning lines through every owner and qualification: in item 38's session,
    the first yielded `layer-forward-smoke` payload alone was 912 lines / approximately 45,720
    transport tokens, and the qualification's ordinary build phase was 564 lines / approximately
    30,038 transport tokens before any measurement progress. Item 38's first publication preflight
    then retained **2,490 lines / 441,553 bytes** before a five-line actionable failure tail. A
    second host-native attempt retained **4,374 lines / 815,682 bytes** before its late
    Linux-profile diagnostic. The corrected Linux preflight then retained **4,632 lines / 840,851
    bytes** before the installed aggregate reduced its actual baseline mismatch to the generic
    `ERROR CHILD aggregate`; the diagnostic retry captured 16,562 stderr bytes but its bounded
    8,192-byte tail was dominated by repeated Git graft hints before the useful final failure line.
    This is a recurring class across local owners, `scripts/pre-pr`, hosted CI,
    managed-toolchain builds, and capable qualifications, not a one-off test incident.

    The capability will start with a checked-in design and exact byte/line baselines before code,
    because it changes a developer process boundary and makes a measurable output-volume claim. Its
    consumer-complete boundary is one shared capture/summarization path actually used by a local
    owner and the corresponding CI/preflight execution: on success it prints phase, result, elapsed
    time, warning counts by normalized class, full-log digest, and retained artifact path; on failure
    it preserves the original exit/signal/pipe status, prints the failing phase plus a bounded useful
    tail, and retains the complete log. Long-running progress coordinates remain visible at least
    once per minute. Mutants must prove that the wrapper cannot turn a failure into success, lose the
    first actionable diagnostic, truncate the retained log, or reorder aggregate phases. The design
    records a maintenance ceiling and an acceptance floor in exact bytes and lines; tokenizer-specific
    token counts remain a secondary observation. It will not suppress warnings without summarizing
    them, replace installed-profile evidence, or add another aggregate merely to test itself.

    **Merged as PR #158.** [`dev-output-summary.md`](dev-output-summary.md) fixes the shared command,
    raw-log identity and lifetime, signal/status rules, warning normalization, bounded diagnostic
    format, direct-owner/preflight/CI adopters, exact three-sample baseline, output ceilings, and
    closure matrix. Repaired head `24a6686` emits 7 lines / 872 bytes against the 922-line /
    185,927-byte baseline while retaining all 921 child lines / 185,893 bytes; both gates are
    **MET**. The final workflow repair is `af5d766`, and merge commit `5e124c2` carries all required
    hosted, x86_64, and aarch64 evidence.

41. **R7-TOKENIZER — Qwen2 text/token conversion from the model's own GGUF vocabulary.** R7's
    gate cannot be reached from R6's token-id-only runtime: the existing `ModelProvider` accepts
    text and returns text, while every shipped runtime arm accepts ids and publishes ids. The first
    independently useful boundary is therefore a Qwen2 tokenizer that materializes
    `tokenizer.ggml.tokens` and `tokenizer.ggml.merges`, encodes UTF-8 plus explicitly selected
    special tokens to ids, and decodes ids back to exact UTF-8 without an external tokenizer at
    runtime. It targets the same Qwen2.5-Coder-7B Q4_K_M model as the dense runtime and takes pinned
    llama.cpp tokenization as the parity oracle; it does not yet expose a provider, render a chat
    conversation, load weights, run inference, sample logits, or claim speed.

    The proportional design gate fires on public GGUF/tokenizer/CLI surfaces, large owned string
    arrays, malformed-model and special-token precedence, and the invariant spanning GGUF,
    tokenizer, CLI, fixtures, and parity. A design-only publication checkpoint is exceptional but
    necessary here because external coordination had to consume it first: at the design checkpoint,
    Align Request 22 rejected ordinary borrow indexing of Move array elements at both the pinned
    revision and Align `main`. That request blocked source implementation until `ALIGN_MERGED`.
    The authoritative ledger and closure matrix are [`r7-tokenizer.md`](r7-tokenizer.md).

    **Merged as PR #161 (`de44bf0`) on 2026-09-01.** Align PR #920 shipped Request 22 as
    `27770420555d19b98eced133369c168e9c6d4a2f`; the pin now selects that revision and all three
    registered stream-plus-column workarounds have migrated to indexed Move-field arrays. The
    hosted tokenizer owns GGUF array materialization, Qwen2 splitting and BPE, explicit special
    modes, canonical token JSON, raw decode output, malformed-model precedence, and CLI isolation.
    `make gguf-smoke model-ir-smoke layer-forward-smoke tokenizer-smoke` passes, and the exact
    299-case real-model `tokenizer-parity` qualification passes against pinned llama-tokenize build
    10566 with 50,893 input bytes and 69,485 compared ids. Exact-head Linux preflight and all
    hosted, x86_64, and aarch64 required checks passed; Request 22 is closed.

42. **R7-PROMPT — provider text to exact Qwen2.5-Coder prompt token ids.** The existing
    `GenerationRequest` carries `system` and `user`, while the runtime begins at ids. R7-TOKENIZER
    can encode arbitrary text but deliberately does not interpret `tokenizer.chat_template`, so a
    caller still cannot construct the model's actual conversation. This capability validates the
    exact model-carried supported template, renders one system turn plus one user turn with the
    assistant generation prefix, and encodes the complete prompt through one retained GGUF
    snapshot. Its public `prepare_prompt_model` result and `--prepare-prompt` CLI stop at ids; tools,
    history, inference, sampling, EOG termination, provider dispatch, streaming, and decoded text
    remain deferred. The authoritative ledger and closure matrix are
    [`r7-prompt.md`](r7-prompt.md).

    **Merged as PR #163 (`88b77ed`) on 2026-09-01.** The public prompt preparation API and CLI
    validate the model-carried supported template, retain one GGUF snapshot across template and
    tokenizer reads, and match pinned llama.cpp build 10566 on eight real-model cases (1,538 prompt
    bytes and 303 token ids). The repaired candidate closes all three comprehensive-review findings,
    exact-head Linux preflight and every required hosted platform check passed, and the valid coding
    baseline chain remains reachable from merged `main`.

43. **R7-RUNTIME-PROVIDER — in-process text generation through the resident dense runtime.
    Merged as PR #164 (`29b5475`) on 2026-09-02.**
    Connect R7-PROMPT's exact prompt ids to the existing resident Qwen2 decode loop, stop before an
    EOG token or at the requested completion bound, detokenize the generated non-EOG ids, and expose
    the result through an explicit `AlignRuntime` `ModelProvider` arm. The provider binds the retained
    GGUF snapshot to both the alignpack source identity and the exact model-derived geometry before
    inference; it does not trust three independently named artifacts. Streaming, non-greedy sampling,
    seeds, runtime timeouts, prefix-cache reuse, GPU execution, and MoE execution remain deferred.
    A named real-model qualification runs the same fixed `python-inclusive-range` request through
    local OpenAI-compatible llama.cpp and align-runtime, persists both existing schema-2 generation
    records, and requires both completions to pass the existing coding-task validator. The
    authoritative public-contract ledger, closure matrix, validation order, and pre-implementation
    qualification ceiling are [`r7-runtime-provider.md`](r7-runtime-provider.md).

    The candidate now carries prompt/EOG preparation, exact geometry and source-identity binding,
    stop-aware resident generation, detokenization, provider dispatch, the public CLI, a hosted
    synthetic owner, and the opt-in fixed-task gate. On the 16 GiB Apple reference host the real
    gate passed in 62.7 seconds: pinned llama.cpp and `AlignRuntime` both produced the same
    validator-passing patch (SHA-256 prefix `5d6b107e706a`) within the precommitted 20-minute
    maintenance ceiling. Comprehensive review found and repaired three fixed-gate contract defects.
    Publication preflight then exposed a clean-Linux build dependency on an ambient ggml shim; the
    candidate now owns a temporary static hosted stub and an explicit real-shim build path. The
    resulting final comprehensive review found two valid inference-boundary defects: artifact
    identity did not survive path reopen into the exact objects consumed by inference, and provider
    generation could publish an argmax from a non-finite logit plane. The re-scoped repair retains
    and rechecks source identity on the exact inference pack handle, compares the exact reopened
    geometry image, and rejects any non-finite prefill or decode step before token publication.
    Review of the redesigned boundary found two narrow contract-enforcement defects: the geometry
    reopen itself was not capped before comparison, and prerequisite identity work was outside the
    declared complete-gate timer. The consolidated repair applies the same 16 MiB cap to the exact
    reopen, owns a cap-plus-one sparse-replacement regression that requires the bounded-read error
    rather than a later identity mismatch, and starts timing before every configured prerequisite
    probe. The repaired complete gate passes in 75.2 seconds and both provider legs
    again produce the validator-passing `5d6b107e706a` patch. Exact-head publication preflight then
    found one remaining clean-link consumer: the standalone prompt seed-attestation harness imports
    the exhaustive provider dispatcher and therefore the runtime FFI, but did not use the hosted
    static-shim wrapper. It now routes its direct compiler run through that wrapper. The next
    Linux/aarch64 publication run found that the original 1 TiB sparse regression was rejected by
    the installed worker's 512 MiB file-size ceiling before it reached generation; the fixture is
    now 16 MiB plus one byte and asserts the exact capped-read refusal. A fresh exact-head
    installed run then reached a second clean-link consumer in the capable-only prompt evaluation
    adoption. The evaluator and all three opt-in C4 measurement gates now route their derived main
    builds through the same static-shim wrapper as every other hosted main consumer. The resulting
    exact-head Linux/aarch64 publication run passed every phase at `d5d9ec4`, but PR #164's hosted
    x86_64 pinned-compiler job exposed a GNU ld ordering defect: pinned Align emits automatic
    `-lm` before the user `libalign_ggml_shim.a`, whose one object contains deterministic engine
    functions that reference libm even when the ordinary unavailable path is selected. `ggml_ffi`
    now explicitly records `m` after `align_ggml_shim` with the shipped empty `link("m")` form;
    Align Request 54 owns the compiler-order root cause. A system-linker Linux/aarch64 clean build
    and the complete 49-assertion runtime-provider owner pass after the repair; exact-head
    publication and required checks must be rerun. The final Linux/aarch64
    coding-baseline chain is source `0278e6e`
    -> oracle `2ccb385` -> finalization `94fee50`; it binds the new wrapper, shim builder, and static
    stub source and passes the complete `make baseline-check`. Exact-head publication preflight and
    all three required checks passed at `cf76641`; the merge commit preserves the full baseline
    chain.

44. **REQUIRED-CI-UNDER-15 — remove duplicate complete-graph execution from every PR. Merged in
    PR #165.**
    PR #164 measured the pinned hosted check at 12m19s, native x86_64 installed evidence at 43m22s,
    and native aarch64 installed evidence at 46m57s. The aarch64 profile spent 37m14s rerunning the
    complete common capable graph after the hosted job already owned common functional behavior;
    the installed image's architecture, trust, lifecycle, compiler-self-test, adoption, and cleanup
    boundary took about 7m09s. Required checks now use 15 minutes of complete GitHub job wall time
    as the configured timeout and approximate operating target, not as a universal correctness
    constant. The installed matrix keeps both native platform profiles and
    every image-specific refusal, but the complete aggregate becomes an explicit owner-triggered
    audit instead of routine PR evidence. Fresh-image publication preflight uses the same approximate
    operating target: after ordered owner/toolchain/focused prerequisites, it runs only the
    installed owner and leaves the unchanged common graph to required hosted CI. The authoritative contract,
    coverage allocation, and closure matrix are in
    [`check-gate-topology.md`](check-gate-topology.md) section 1.1 and the section 2 ledger. This
    changes no product behavior or evaluator result. PR #171 (`dc38b76`) completed the 2026-09-03
    repair after PR #170's hosted graph exceeded the 15-minute whole-job boundary twice. Section
    1.2 removes only the redundant uncached `check-per-unit` invocation from routine
    hosted/capable aggregates. `make check`, the shared `build` failure boundary, every functional
    owner, and the configured timeout remain unchanged. The repaired required hosted job passed in
    9m28s, down 5m24s from the exact-cache incident, and both installed profiles passed below 13
    minutes.

45. **R8-SCORE-BASED-CACHE — selected router weights through one score-based residency policy.
    Merged as PR #166 (`c1338f1`) on 2026-09-02.**
    [`r8-score-cache.md`](r8-score-cache.md) is the authoritative implementation contract.
    The capability upgrades `R2_ACTIVATION_TRACE` and `R3_RESIDENCY_SIM` to schema 2, extends the
    managed measurement instrument so `ffn_moe_topk` and `ffn_moe_weights` expose identical full
    axes, and adds one predetermined `router_weight_lfu` candidate to the simulator and its
    independent oracle. It is the smallest producer-complete consumer of R3's named router-weight
    prerequisite: every selected expert carries its exact printed four-decimal gating weight and
    the policy evicts the lowest cumulative routing mass with LRU/key tie breaks. The Align pin to
    `b6f95a261e1434d705d7de006484ffa66b1542f0` is an internal checkpoint on the same branch. This
    capability evaluates a cache policy in bytes; it does not yet implement a runtime cache or make
    the latency claim required to close R8.

    The first real decode-corpus replay at the merged head completed in 190.0 seconds and rejected
    `router_weight_lfu` as the runtime candidate at the requested 25-per-cent budget: it fetched
    181, 224, and 110 per mille more bytes than LRU on the mixed, decode-only, and head-4 arms.
    That measurement still pooled forty prompts through one continuing cache, while the current
    runtime owns one invocation at a time. Item 46 closes that lifetime mismatch before any runtime
    cache allocation.

46. **R8-RESET-CACHE-DECISION — evaluate cache policy at the runtime's per-request lifetime.
    Merged as PR #167 (`d3b04b0`) on 2026-09-02.**
    [`r8-reset-cache-decision.md`](r8-reset-cache-decision.md) is the authoritative
    implementation contract. Add an explicit reset-per-trace simulator verb and schema-3 result,
    with both replay orders, the independent oracle, and the existing real decode runner using one
    unchanged capture for continuing and reset results. This is a byte-level investment decision,
    not a runtime cache or latency claim. A partial expert cache is eligible only if the reset
    decode-only evidence materially beats streaming and survives leave-one-trace-out folds.

    The 40-prompt, 16-step real run completed in 213.47 seconds total (199.0 seconds for the sole
    capture). At the 25-per-cent budget, reset decode-only null streaming fetched 312,056,217,600
    bytes and LRU fetched 144,557,211,648: a 536-per-mille reduction, with a conservative
    524-per-mille lower bound after any one trace is removed. Weighted LFU fetched
    143,222,243,328 bytes, only 9 per mille below LRU, so rule 3 does not justify its extra state.
    The next partial-cache capability is eligible with LRU at 975,175,680 bytes.

47. **R8-PARTIAL-LRU-CACHE — execute the selected bounded expert cache in the real OLMoE decode
    consumer. Merged as PR #168 (`4d9f9c8`) on 2026-09-02.**
    [`r8-partial-lru-cache.md`](r8-partial-lru-cache.md) is the authoritative implementation
    contract. Extend the existing `dense` residency boundary with an invocation-local
    `dense+lru:BUDGET_BYTES` mode, share its deterministic LRU state from prefill through all decode
    steps, and publish physical read/hit/eviction evidence without changing the claim window or
    graph. The selected real budget is 975,175,680 bytes. The precommitted shipping floor is 50,000
    ppm fewer decode expert pack bytes than the paired `dense` leg on one fixed 16-step task, with
    exact semantic equality; elapsed time is diagnostic only. The focused real qualification is
    bounded at approximately 15 minutes and does not repeat the 40-prompt capture or broad OLMoE
    matrix. The merged capability removes 625,585 ppm (7,801,405,440 to 2,920,955,904 bytes) on
    that task, with 1,279 hits, 1,112 misses, 873 evictions, and exact semantic equality in 9.75
    seconds of paired model execution. This capability does not claim provider-level time to a
    passing patch.

48. **R8-OLMOE-TEXT — OLMoE text/token and prompt preparation. Merged as PR #169
    (`c987838`) on 2026-09-03.**
    [`r8-olmoe-text.md`](r8-olmoe-text.md) is the authoritative implementation contract. Extend
    the existing tokenizer and prompt consumers to the reference model's exact `gpt2`/`olmo`
    profile and 508-byte chat template, while preserving Qwen behavior and identity byte-for-byte.
    This is the smallest independently useful prerequisite for an OLMoE provider: it produces the
    exact token ids already accepted by the MoE decoder, but does not yet add provider dispatch,
    generation, EOG policy, cache configuration, or a performance claim. The Align `8cefc803` pin
    adoption is an internal checkpoint in this consumer branch. Acceptance is one focused
    synthetic owner, Qwen regression ownership, and focused real parity against pinned llama.cpp;
    unrelated aggregates, installed profiles, benchmarks, and the OLMoE runtime matrix are not
    selected by this boundary. The candidate's synthetic owner passes in about one second, and its
    real 13-case/two-mode tokenizer plus six-prompt parity passes in 23.6 seconds with 332 compared
    ids. Existing Qwen tokenizer and prompt owners pass, and the real Qwen tokenizer identity is
    unchanged.

49. **R8-OLMOE-PROVIDER — expose cache-backed OLMoE generation through `ModelProvider`. Merged as
    PR #170 (`0eaed91`) on 2026-09-03.**
    [`r8-olmoe-provider.md`](r8-olmoe-provider.md) is the authoritative implementation contract.
    Dispatch the existing in-process runtime provider by exact model architecture, carry an explicit
    invocation-local expert-cache budget, and extend the shipped MoE decoder with the same
    pre-graph EOG and maximum-token semantics already used by dense generation. Preserve the Qwen
    provider path and require OLMoE callers to opt into a positive cache budget. Acceptance is a
    focused synthetic provider owner plus one bounded real-model generation qualification; this
    correctness capability makes no provider-level latency or time-to-passing-patch claim and does
    not select `make ci`, platform profiles, stress, or the 40-prompt runtime matrix. The merged
    candidate passes 61 synthetic assertions and one fixed real-model generation against pinned
    llama.cpp with prompt count 47, emitted ids `[1992,4993]`, and decoded bytes `To fix`.

50. **R8-OLMOE-CODING-DECISION — measure provider-level time to a passing patch. Decision recorded:
    `NOT_ELIGIBLE`.**
    [`r8-olmoe-coding-decision.md`](r8-olmoe-coding-decision.md) is the authoritative measurement
    contract and closure matrix. Run the shipped local llama.cpp and partial-LRU `AlignRuntime`
    OLMoE provider arms over the existing fixed `python-inclusive-range` task in four balanced
    paired samples. Each sample measures from provider-helper launch through the unchanged coding
    validator. R8's performance gate is met only if every leg reaches a passing deterministic patch,
    the candidate is faster in every pair, and its median is at least 50,000 ppm below the baseline
    median. A negative decision is valid evidence and selects the next investment; malformed,
    incomplete, nondeterministic, or over-ceiling evidence fails. The complete real decision has an
    approximately 15-minute diagnostic ceiling and is run once, without `make ci`, platform
    profiles, the 40-prompt corpus, cache-policy replay, stress, or unrelated benchmarks. The one
    complete bound run finished in 142.183 seconds. Both arms deterministically emitted the same patch,
    but that patch failed the unchanged validator in every sample, so both pass counts are 0/4 and
    primary timing medians remain null. The next investment belongs to model/prompt patch
    correctness rather than provider-level runtime optimization.

51. **R8-OLMOE-SAMPLED-CODING — decide whether a bounded sampled portfolio reaches a passing
    patch. Decision recorded: `MET`.**
    [`r8-olmoe-sampled-coding.md`](r8-olmoe-sampled-coding.md) is the authoritative measurement
    contract and closure matrix. Item 50's greedy OLMoE completion chose
    `range(start, stop, -1)` and repeated it after direct validator feedback. This capability keeps
    the model, prompt, task, strict extractor, and validator fixed, but uses the existing local
    provider's seeded sampling surface at temperature 0.3 over ordered seeds 1 through 8, stopping
    at the first passing patch. `MET` selects seeded sampling as the next `AlignRuntime` consumer;
    `NOT_MET` redirects to another model. The one run is bounded at approximately 10 minutes and
    makes no quality-rate, generality, latency, or R8 shipping claim. The one complete portfolio
    finished in 34.483 seconds and stopped at seed 5: two candidates were invalid patches, two
    reproduced the greedy wrong patch, and candidate 5 matched the existing known-good patch and
    passed in 13.176 seconds from portfolio start. Seeded sampling is therefore the next eligible
    `AlignRuntime` consumer capability; R8's performance gate remains open.

52. **R8-OLMOE-RUNTIME-SAMPLING — execute fixed seeded sampling in the real OLMoE provider
    consumer. Merged as PR #174 (`728a186`) on 2026-09-04.**
    [`r8-olmoe-runtime-sampling.md`](r8-olmoe-runtime-sampling.md) is the authoritative public
    contract and closure matrix. Add the fixed policy selected by item 51 to the existing
    in-process OLMoE generation path: stable top-k 40, top-p 0.95, min-p 0.05, temperature 0.3,
    and one explicit Align Xoshiro256++ draw per emitted token. Preserve greedy OLMoE, dense Qwen,
    diagnostic decode documents, cache ownership, and EOG semantics. Acceptance is the focused
    pure and synthetic provider owner plus one repeated real-model reproducibility qualification;
    token parity with llama.cpp and performance are not claims. The succeeding capability measures
    the fixed passing-patch portfolio through this shipped path.

53. **R8-OLMOE-SAMPLED-RUNTIME-DECISION — compare provider-level time to a passing patch through
    the fixed sampled portfolio. Decision recorded: `NOT_MET`.**
    [`r8-olmoe-sampled-runtime-decision.md`](r8-olmoe-sampled-runtime-decision.md) is the
    authoritative measurement contract and closure matrix. Run four balanced pairs of the same
    ordered seeds 1 through 8 at temperature 0.3, stopping each local llama.cpp or in-process
    `AlignRuntime` leg at its first validator-passing patch. The gate requires four passes per arm,
    runtime faster in every pair, and at least 50,000 ppm lower median time to passing patch. The
    pre-implementation attempt-count opportunity ceiling is 800,000 ppm because item 51's baseline
    stopped at candidate five and a portfolio can stop no earlier than candidate one; differing
    provider costs remain inside the measurement. The one complete decision is bounded at
    approximately 25 minutes and may validly record `MET`, `NOT_MET`, or `NOT_ELIGIBLE`.

    Both arms passed 4/4 portfolios and selected seed 5 with the same known-good patch. Local times
    were 12.813, 13.068, 12.607, and 12.118 seconds (median 12.710); runtime times were 149.977,
    179.570, 198.440, and 202.138 seconds (median 189.005). Runtime was slower in every pair and
    gain was -13,871,021 ppm, about 14.87 times the local median. Both arms needed five candidates,
    so the 800,000-ppm attempt-count opportunity did not materialize and is recorded as a
    ceiling-estimation miss. The R8 gate remains open. The next investment must distinguish
    repeated provider construction from co-resident memory pressure before changing runtime
    lifetime or cache behavior.

54. **R8-OLMOE-RUNTIME-PHASE-DIAGNOSIS — separate request-local setup from co-resident model
    pressure. Decision recorded: `MIXED_OR_UNRESOLVED`.**
    [`r8-olmoe-runtime-phase-diagnosis.md`](r8-olmoe-runtime-phase-diagnosis.md) is the
    authoritative measurement contract and closure matrix. Run fixed seed 5 with two-token and
    full-completion bounds in four balanced pairs, both without a matching llama.cpp model process
    and with one owned pinned server resident but idle. A qualification-only helper records the
    production-order preparation clocks plus the runtime's existing phase and lifetime counters.
    Compare the paired full-request co-resident penalty with conservative repeated-setup lower and
    upper bounds under a 50,000-ppm attribution deadband. The result selects isolated-baseline work
    only when pressure clears the upper bound, bounded persistent-lifetime design only when the
    measured lower bound clears pressure, and otherwise one narrower phase instrument. It does not
    itself change provider lifetime, cache behavior, or the open R8 performance gate.

    The repaired 360.313-second diagnosis reproduced the fixed output in all sixteen requests and
    balanced every native lifetime counter. Solo short/full medians were 4.941/30.617 seconds and
    co-resident medians were 6.412/32.242 seconds. All four paired full penalties were positive;
    their 2.025-second median was 66,127 ppm of solo full time. The measured setup lower bound was
    0.132 seconds or 4,320 ppm, while the conservative full-request upper bound was 30.617 seconds.
    The penalty lies between them, so neither directional rule clears its bound. Every co-resident
    helper began above the 2-GiB RSS floor and ended below it, confirming pressure without proving
    it dominates unassigned reconstruction. R8 remains open.

55. **R8-OLMOE-FIRST-TOKEN-PHASE-DIAGNOSIS — tighten the unresolved reconstructive-work
    interval. Decision recorded: `CO_RESIDENT_PRESSURE_EXCEEDS_CONSTRUCTION`.**
    [`r8-olmoe-first-token-phase-diagnosis.md`](r8-olmoe-first-token-phase-diagnosis.md) is the
    authoritative measurement contract and closure matrix. Run the fixed full sampled request in
    four balanced solo/co-resident pairs and partition construction, prefill, first decode,
    remaining decode, claim I/O, and compute. Replace item 54's full-request setup upper bound with
    provider preparation plus completed pre-prefill engine construction under the same 50,000-ppm
    attribution deadband. The new upper bound must be below 30.617 seconds before another
    isolated-baseline, bounded lifetime, or phase-specific diagnosis is selected. The capability
    introduces no persistent state and makes no R8 performance-win claim.

    After symmetric two-token candidate conditioning, the 363.859-second diagnosis reproduced the
    fixed output in all eight timed requests and balanced every native lifetime. The new setup
    interval was 0.068–0.272 seconds, while all four co-resident penalties were positive and their
    3.052-second median was 102,268 ppm of the 29.843-second solo median. Prefill and remaining
    decode contributed 1.011 and 1.854 seconds of paired median wall movement; their claim-I/O
    components contributed 0.958 and 1.555 seconds, while compute movement was small. Pressure
    therefore clears the construction upper bound and selects an isolated provider-level decision.

56. **R8-OLMOE-ISOLATED-SAMPLED-RUNTIME-DECISION — remeasure time to a passing patch without
    co-resident model pressure. Decision recorded: `NOT_MET`.**
    [`r8-olmoe-isolated-sampled-runtime-decision.md`](r8-olmoe-isolated-sampled-runtime-decision.md)
    is the authoritative measurement contract and closure matrix. Repeat item 53's exact sampled
    coding portfolio and
    50,000-ppm gate in four balanced local/runtime pairs, but give each local leg its own pinned
    llama.cpp server lifetime and prove that server terminated and was reaped before any runtime
    leg. The runtime leg must begin and end without a matching model process. This decision changes
    no provider lifetime or cache behavior and may record `MET`, `NOT_MET`, or `NOT_ELIGIBLE`.

    The 724.144-second run proved every local server lifetime and all eight runtime absence
    boundaries. Both arms passed all four portfolios at candidate 5 with the same patch. Local
    median time to a passing patch was 13.197 seconds and isolated runtime median was 149.273
    seconds, a -10,310,731-ppm gain with runtime slower in every pair. Isolation recovered 39.732
    seconds, or 21.0% of item 53's old co-resident-runtime median, but did not approach the
    50,000-ppm gate. R8 remains open.

57. **R8-OLMOE-REMAINING-DECODE-OVERHEAD-DIAGNOSIS — assign the isolated decode tail before
    choosing graph, transfer, or orchestration work. Decision recorded:
    `MEASURED_BUCKET_ELIGIBLE / KV_PLANE_TRANSFER`.**
    [`r8-olmoe-remaining-decode-overhead-diagnosis.md`](r8-olmoe-remaining-decode-overhead-diagnosis.md)
    is the authoritative measurement contract and closure matrix. Reuse the fixed isolated seed-5
    full request and split remaining decode exactly into pre-pass, decode-pass, and post-pass. Within
    pass, project the existing pack/resident staging, claim I/O, compute, routing, and KV-plane
    upload/readback clocks and retain every other graph/context, generic-transfer, digest, and
    allocation cost in an explicit residual rather than mislabelling it. Four conditioned repeats
    compare each bucket's removable-work ceiling with the precommitted 1,466,649,650-nanosecond
    floor. A dominant residual selects only a narrower diagnosis; this capability changes no
    provider lifetime, cache policy, or generation behavior.

    The 154.183-second run reproduced the fixed output and balanced native lifetimes in all four
    full requests, with zero matching llama.cpp processes at all twelve required boundaries.
    Remaining decode had a 25.267-second median. `KV_PLANE_TRANSFER` was the largest bucket at
    11.555 seconds (457,325 ppm), ahead of pass residual at 4.762 seconds, compute at 4.756 seconds,
    and claim I/O at 4.015 seconds. CPU K/V staging supplied 11.548 seconds of the winning bucket;
    plane readback supplied only 0.008 seconds. The winner clears the 1.467-second floor and selects
    item 58; it does not itself establish a performance win.

58. **R8-OLMOE-KV-PLANE-STAGING-TRANSFER — reduce the measured scalar K/V staging boundary.
    Decision recorded: `MET`.**
    [`r8-olmoe-kv-plane-staging-transfer.md`](r8-olmoe-kv-plane-staging-transfer.md) is
    the authoritative implementation ledger and closure matrix. Preserve the current plane,
    graph-input, token/output, cache, and native-lifetime semantics while replacing the per-scalar
    host staging loops with one validated, allocation-free call at the existing shared C shim.
    Item 57's four fixed full helper walls and 30,450,856,583-ns median are the immutable baseline;
    the exact conditioned four-repeat qualification must preserve output and lifetimes and clear
    the precommitted 50,000-ppm gate, a candidate median no greater than 28,928,313,753 ns.

    One combined caller-owned staging range and one validate-before-write shared-shim call preserve
    the canonical plane and exact K/V graph-input layouts. The post-review 105.628-second
    qualification bound baseline and candidate to the same Apple M1 host and reproduced the fixed
    output and balanced lifetimes in all four repetitions. Full helper wall fell from the immutable
    30.451-second baseline to an 18.429-second median, a 394,794-ppm gain; staging upload fell from
    11.548 seconds to 2.045 seconds. The intervention ships.

59. **R8-OLMOE-DECODE-PASS-RESIDUAL-DIAGNOSIS — partition the post-staging decode-pass residual.
    Decision recorded: `OTHER_PASS_NEEDS_DIAGNOSIS / OTHER_PASS_RESIDUAL`.** Item 58's post-review
    four exact sample records leave `PASS_RESIDUAL` as the largest
    remaining bucket at a 4,172,949,292-ns median, ahead of compute at 4,104,846,715 ns and claim
    I/O at 3,609,378,007 ns. Define a narrower diagnosis of graph/context construction,
    graph build/allocation/teardown, generic tensor transfer/digest, and other unassigned pass work
    before authorizing another implementation seam. Preserve item 58's fixed workload, output,
    isolation, cache, and lifetime boundaries.

    Review corrected claim-buffer construction attribution and made result publication follow
    cleanup and the cleanup-inclusive ceiling check. The replacement fixed-host four-repeat run
    reproduced every output, lifetime, and isolation boundary. Its decode-pass residual median was
    4.144 seconds. `OTHER_PASS_RESIDUAL` dominated at 2.877 seconds (694,324 ppm), while generic
    transfer/digest was 0.868 seconds, graph teardown 0.273 seconds, graph build/allocation 0.093
    seconds, and context/buffer setup 0.025 seconds. Every direct bucket missed the 0.921-second
    materiality floor. No implementation seam is authorized; item 60 is selected.

60. **R8-OLMOE-DECODE-PASS-OTHER-DIAGNOSIS — partition the remaining unassigned pass work.
    Decision recorded: `MEASURED_BUCKET_ELIGIBLE / PLANE_ROUNDTRIP_COMPARE`.**
    [`r8-olmoe-decode-pass-other-diagnosis.md`](r8-olmoe-decode-pass-other-diagnosis.md)
    is the authoritative ledger and closure matrix. Preserve item 59's exact request and evidence boundaries while
    separating plane round-trip comparison outside the existing readback clock, graph-member/spec
    construction, per-layer/step accounting, and an explicit remainder. A direct measured winner
    must clear item 59's precommitted materiality floor before it can authorize implementation.

    The clean-head four-repeat diagnosis reproduced the fixed output, balanced every native
    lifetime, and passed all twelve isolation boundaries. Plane round-trip comparison dominated at
    a 2.972-second median and 991,445 ppm of the 2.998-second measured total, clearing the inherited
    0.921-second floor by 2.051 seconds. Graph-member/spec construction, layer/pass accounting, and
    the explicit remainder measured only 0.007, 0.001, and 0.017 seconds. Item 61 is selected; this
    diagnosis does not itself establish a performance win.

61. **R8-OLMOE-PLANE-ROUNDTRIP-BOUNDARY — reduce the measured K/V verification boundary.
    Active; first two interventions measured `NOT_MET`.** [`r8-olmoe-plane-roundtrip-boundary.md`](r8-olmoe-plane-roundtrip-boundary.md) is the
    authoritative implementation ledger and closure matrix. Item 60 measured the complete
    `verify_plane` call, including concat
    shape reads, two `slot_get` operations, scalar K/V comparison, and result accounting; it did not
    attribute cost among them. Preserve the exact canonical-plane and graph-consumed layouts,
    first-mismatch tensor/column, output, isolation, cache, and native lifetimes while reducing that
    complete boundary. Item 60's four full-helper samples and 18,746,386,770-ns median are the
    immutable fixed-host baseline. Precommit a 50,000-ppm floor of 937,319,339 ns in the
    implementation ledger; the conditioned candidate must have a median no greater than
    17,809,067,431 ns before the intervention can ship. Replacing only scalar comparison reduced
    the boundary median to 1,878,132,280 ns but produced only a 23,162-ppm full-helper gain, so it
    cannot ship alone. The second intervention removed the remaining two host-to-host
    `slot_get` copies by comparing host-visible concat tensors in place under an explicit native
    buffer-visibility check, but its 19,122,598,458-ns median was also `NOT_MET`. Disassembly names
    the remaining V scalar loop. The final bounded intervention uses exact 4-by-4 AArch64 transpose
    tiles for success and reruns the original traversal on mismatch; it retains the original
    baseline and gate, with a scalar non-AArch64 fallback.

### Status (2026-08-28)

Track B is complete on the dense local model from R0 through R5C (item 17). Decision (a) is taken:
`OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf` (allenai, 4,213,512,192 B, sha256 `4ddc0e53159e…`, arch
`olmoe`, 16 layers, 64 experts top-8) is downloaded, and it unblocked items 18 through 26 above:
items 18 through 25 are merged, R2's gate is met **in both the prefill and the decode direction**,
R4's and R4.5's per-expert halves are discharged, R3's gate is met on the real corpus **in both
directions**, and decision (c)'s pinned decode instrument is shipped. It also unblocked item 23,
R5D-MOE-LAYER-FORWARD, merged as PR #139, with one routed OLMoE layer computed over Align-owned
expert claims and agreeing with llama.cpp node for node, item 24, R2D-DECODE-LOCALITY-GATE, merged
as PR #141, which meets R2's locality gate in the decode direction on the same 40-prompt corpus,
item 25, R3-DECODE-RESIDENCY, merged as PR #142, which meets R3's gate in the decode direction —
narrowly, with the win confined to budgets at or below 12.5 per cent of the expert footprint and no
candidate beating `lru` at 25 or 50 per cent — and item 26, R5E-MOE-MODEL-PREFILL, merged as
PR #143: a whole sixteen-layer routed prefill over one reused Align-owned claim window, logits
byte-identical to `llama-debug`, and 33.36% of the model's expert bytes read at six tokens. Item 25
discharges R4B's decode-corpus resume condition negatively and orders R6's KV tiering ahead of a
runtime expert-residency policy, and **item 27, R6-DECODE-KV-STEP1, is the first capability on that
order**: one decode step at `n_past = T` over an Align-owned KV plane on the dense model, byte-exact
against llama.cpp's own single-shot `T+1` prefill. It is a correctness capability and does not meet
R6's own gate below.
**R5's gate is therefore complete on the real MoE model for all three stages of the routed path** —
単一block (R4.5 and MOE-PREREQ-DISCHARGE), 単一layer (R5D), and 最小モデル (R5E).
Decision (b), `gpt-oss-20b-mxfp4.gguf` at 12.1 GB, is now recorded
**infeasible on the host where that decision was recorded** (disk free ~16 GiB after decision (a)); it still unblocks R1B's
real-model `model-ir-parity` qualification whenever a host with enough free space is available. (c)
a source build of llama.cpp at `bb4caa754` plus the R2c minimal instrument patch is **taken** and
merged as item 22, unblocking R6 and, through it, R7-R9, and already consumed by item 24 to meet
R2's gate in the decode direction; (d) Align Request 41 (non-`Copy` capture in `spawn` closures) unblocks R5's
required microbenchmark C. See `HANDOFF.md`, "Active capabilities", for the full decision list and
disk-space accounting.

**I0 is substantively covered and is not scheduled as its own capability.** I0 asks that align-coder
prove its value on an existing model, and the merged C6-MEASURED wave (align-llm PR #103, `c9a510d`)
already did so end to end: `src/provider_llama.align` drives a real local provider, and the frozen
`eval/prompt/canonical-v1/` scope names `LOCAL_OPENAI` at
`http://127.0.0.1:18080/v1/chat/completions` with model `qwen2.5-coder-7b-instruct-q4_k_m` and a
recorded `provider_service_revision`. The measured run reported `IMPROVED` with
`gate_eligible: true`, zero serious regressions, and completion gain 2, against a parent-vs-parent
null replicate that flipped no cell. That evidence carries no paired timing, so I0's claim is the
completion-gain path only; the remaining I0 work is absorbed by later Track B integration rather
than by a separate align-coder capability.

**ALIGN-ADOPTION is an internal prerequisite checkpoint, not a standalone capability.** Within the
next consumer branch, batch its merged Align requests into one compiler-pin update, run every named
focused real-client acceptance target, and then run one final fresh `make ci`. Preserve each
request's lifecycle evidence without opening a pin-only pull request. C8-OPTIONAL-TARGETED-STAGE
adopts Request 44's merged Align prerequisite at `3a34febe`; that adoption and its real-client
verification remain part of the consumer capability rather than a pin-only pull request.

Only design the next eligible capability in implementation detail; later ledger entries may retain
their accepted contracts but must not generate speculative implementation pull requests. The
roughly eight-hour checkpoint and 24-hour substantial-progress expectations in `CLAUDE.md` are
diagnostics for workflow problems, not split thresholds or delivery quotas.

---

# Track A: align-coder

## C0: 固定評価セット

最初に、改善を測定できる環境を作る。

### 成果物

```text
eval/
  tasks/
  expected/
  runners/
  baselines/
```

### タスク例

```text
- 小さなbug fix
- 型エラー修正
- test failure修正
- 小規模feature
- refactor
- 性能改善
- 境界条件修正
```

### 比較対象

```text
- cloud coding model
- existing local model
- same model without align-coder
```

### Gate

同じタスクを繰り返し再現・採点できること。

---

## C1: Provider-independent Coding Loop

モデルbackendを抽象化する。

```text
ModelProvider:
  generate()
  stream()
  count_tokens()
  model_info()
```

初期対応。

```text
- cloud API
- llama.cpp互換server
- OpenAI互換local server
```

### Gate

同じcoding taskを複数providerで実行し、結果を共通形式で保存できること。

---

## C2: Repo Index MVP

最初から高度な独自静的解析器を作らない。

既存ツールを使って次を構築する。

```text
- files
- symbols
- imports
- definitions
- references
- related tests
```

### 初期対象言語

align自身で最も必要な1言語、または対象repoで最も頻度が高い1言語に絞る。

### Gate

変更対象symbolから、関連ファイルとテスト候補を取得できること。

---

## C3: Patch Evaluator

git diffを解析する。

```text
align-coder evaluate <patch>
```

出力。

```text
- touched files
- touched symbols
- risk score
- unrelated diff
- public API change
- complexity delta
- recommended tests
```

### Gate

固定評価タスクに対して、人間が危険と判断する差分を一定割合で検出できること。

---

## C4: Verification Loop

```text
generate
  ↓
evaluate
  ↓
build / test
  ↓
failure summary
  ↓
repair
```

### 初期機能

```text
- build command
- targeted test
- full test
- timeout
- structured error extraction
- repair prompt generation
```

### Gate

少なくとも一部の固定タスクで、初回失敗から自動修正してtest passまで到達すること。

### First measured consumer: C4-REPAIR-MEASURED

C4's gate was met in mechanism by `make verify-loop-smoke`, whose repair patch is a checked-in
deterministic input rather than a model. Item 31 above ran it with a real provider on the C6
measurement path, and `docs/specs/c4-repair-measured.md` section 10.3 is the authoritative record
of what came back. **The loop is delivered and C4's gate is still not met by a model.** Ten repair
attempts were rendered from the run's own diagnostics, measured, bounded, and contained; none
recovered, so `repair_recovery_paired_count` is 0 and the qualification's verdict is `NOT_MET`.
That is a measured negative, published as a result. It is provider-independent — no provider module
changes — and it does not modify `src/repair.align` or `src/verification_loop.align`; converging
the two loops is a named deferral in that document.

### Second measured consumer: C4-REPAIR-EDITSET

Item 34 above carried the failing attempt's own edit set into the repair prompt, through a second
reviewed corpus-member adapter, and ran the gate again on the same predicate.
`docs/specs/c4-repair-editset.md` section 11.4 is the authoritative record. **C4's gate is still
not met by a model.** Six of the six addressable repair prompts carried `EDITSET`, none recovered,
and `repair_recovery_paired_count` is 0 again. What the run settled is which capability comes next:
`patch_sha256` shows attempt 2 re-sending attempt 1's **exact bytes**, and the persisted edit set
shows the model reproducing pinned files unchanged rather than misunderstanding the diagnostics. So
the missing edit set was not the binding constraint. The next capability toward a model-met C4 gate
is a **prompt, template, and edit-policy** capability for the unchanged-file reproduction mode —
starting with that document's section 11.3 deviation 14, which records that `edit_set` is discarded
on exactly the rows where it would matter most.

---

## C5: Failure Memory

失敗と修正結果をrepo profileへ保存する。

```text
repo.alignprof:
  failed_attempts
  root_causes
  successful_repairs
  test_relationships
  risky_symbols
```

### Gate

過去と類似する失敗で、関連情報を次の修正promptへ再利用できること。

---

## C6: Prompt and Context Optimizer

LLMにprompt/context改善候補を提案させる。

ただし固定評価セットによるA/B評価を必須とする。

```text
align-coder prompt experiment
align-coder prompt evaluate
align-coder prompt accept
align-coder prompt rollback
```

### Gate

採用したprompt patchが、固定タスク全体で改善し、重大な回帰を起こさないこと。

---

## C7: Algorithm Verification

アルゴリズムや性能変更向け機能を追加する。

```text
- property-based testing
- fuzzing
- differential test
- invariant checks
- benchmark comparison
```

### First planned consumer slice: C7-PersistedResult

The first planned C7 consumer is the `C7-PersistedResult` slice: retain a declared verification
result after its input document and borrowed views have expired, then verify the persisted value
through the algorithm-testing gate. This is a named roadmap slice, not an implementation contract;
its own design must define the persisted artifact schema, validation boundary, and adoption test
before implementation starts. Align Request 9 is now `ALIGN_MERGED` at named commit
`2bb93a93a2f30da1daabd5b65d83863dab617560`, and the consumer design explicitly names the accepted
owned record shapes. Its managed pin and C7 adoption target remain a blocking prerequisite for the
consumer; C6 work remains independent.

### Platform profiles: C7-P

C7 evidence is target-bound, so each required non-x86 acceptance environment has its own reviewed
platform profile before it may provide that evidence: `aarch64-unknown-linux-gnu` reuses the
Section 9 fresh-compiler topology under that section's own stated condition, and
`aarch64-apple-darwin` has the separate minimal profile in Section 10 of
`docs/specs/check-gate-topology.md`, gated by `make darwin-profile-gate`. Both are named focused
qualifications run at a pin bump, a C7 owner-boundary change, or an explicit audit.

### Gate

意図的に入れた境界条件バグ、性能劣化、挙動差を検出できること。

---

## C8: Speed-first Optimization

評価対象を、モデル速度からタスク完了速度へ移す。

```text
- context縮小
- stable context reuse
- targeted tests（最初のcapabilityはtracked-file rankingを121走査から1走査へ変更）
- parallel checks
- small-model routing
- cached static analysis
```

性能主張と固定passing-patch benchmarkのrecordは
[`c8-speed-first.md`](c8-speed-first.md)をsource of truthとする。最初のcapabilityは公開selection
documentと検証順序を変えず、4種類のscore bucketを一度のtracked-file走査で構築する。次の
capabilityは同じ公開fieldを保ったまま、各testのbasename/directory signalをscore用とreason用に
二重計算せず一度だけ求める。第3capabilityは、全test candidateで不変なchanged pathのstemと
directoryをtracked-file loopの前に一度だけ求める。第4capabilityは正の関連候補がある場合に
score 0のgeneric候補をcontextから省き、正の候補がない場合だけgeneric全件をfallbackにする。
第5capabilityはその契約を保ちつつ、generic pathをGit listing内のoffsetとして一時保持し、fallback
が必要と確定した場合だけJSONへserializeする。第6capabilityは、関連候補がある通常経路ではその
offset保持も省き、正の候補がない場合だけ既に所有しているGit listingを再走査してgeneric fallbackを
構築する。第7capabilityは、候補・修正patchの事前checkと適用をGitの原子的な1 invocationにまとめ、
成功時の重複processとcheck専用stage recordを省く。第8capabilityは、各layerで完成したowned JSON
bufferを唯一のresult ownerへ移し、return直前の同一buffer再allocationを省く。第9capabilityは、
test selectionをrevision付きCLI entryとrevision不要なevaluation entryに分け、評価経路が消費しない
`git rev-parse --verify HEAD`のspawnを省いて`git ls-files -z`のみを実行する。CLI documentはbyte
単位で不変で、非repositoryは`git ls-files`が失敗するため引き続きfailするが、commitのないunborn
HEAD repositoryは評価経路で`ok`（candidate 0件、あるいはindexが持つ候補）を返すようになる。

### Gate

baselineと比べて、固定タスクの中央値でtime to passing patchが短縮すること。

**9個のcapabilityで当初gateを達成し、1個のbounded capabilityだけ再開した。** 9個すべてが固定タスクのpaired benchmarkで
中央値の短縮を測定しており、最後の第9capabilityは10,793 ppm（1.08%）の短縮を記録した。個々の
baseline・測定値・host・binary digestは
[`c8-speed-first.md`](c8-speed-first.md)のsection 3〜11がsource of truthである。同じretrospective
で**ppm-floor rule**（cost ceilingを実装前にledgerへ記録し、shipping floorである2,000 ppmを
下回るseamは実装せずdeferred surfacesに記録する）をsection 1へ昇格させた。残るdeferred surface
は、floorを超えるcost ceilingを持つか、genuineなAlign capability requestになった場合にのみ
新しいcapabilityとして再開する。`C8-OPTIONAL-TARGETED-STAGE`はtargeted processが
43,886,999 ns中14,311,285 ns（326,093 ppm）であり、必要なAlign修正もPR #892でshipしたため、
2026-08-28に明示的に再開した唯一の例外である。権威あるcontractと停止条件は
[`c8-optional-targeted-stage.md`](c8-optional-targeted-stage.md)にある。stable candidateはschema/owner
matrixをpassし、101-pairの固定タスク中央値を60,515,456 nsから40,475,113 nsへ短縮した
（331,160 ppm、33.12%）。reviewは完了し、PR #134のbase integrationとpublicationが残る。このbounded capabilityの
merge後にTrack Bへ戻る。R0のgateは達成済みでcloseした。R1（Qwen2 Model IR）のgateも
達成済みでcloseし、R1B（gpt-oss/MoEフロントエンド）もPR #123としてmergeされ、R1のgateはgpt-oss側を
含めてcloseした（gpt-oss実モデルによるqualificationのみ、ユーザー判断待ちのopen項目として残る）。
現在はR2 locality gate、R1C OLMoE frontend、MoE prerequisite discharge（PR #133）までmerge済みであり、
このbounded C8 capabilityの次はR3 residency simulationを実装する。

---

# Track B: align-runtime

## R0: GGUF Inspection

```text
main --inspect-gguf MODEL.gguf
```

### 実装

```text
- GGUF header
- metadata
- tensor table
- offset
- dtype / quant type
- architecture判定
```

little-endian decode APIはすでにAlign標準ライブラリが提供している。pin
`4b515f8d`時点で`bytes`（`slice<u8>`）は`u8`/`i8`と`u16 i16 u32 i32 u64 i64 f32 f64`の
`_le`/`_be`形、計18個のscalar decoderを持つ（例: `bv.u32_le(off)`）。range外読み出しは
`slice[i]`と同じくabortするfail-closedなので、bounds checkはR0側の正しさの責務である。
したがってR0は新しいAlign surfaceを提案せず、compatibility layerも作らない。

R0のauthoritative planは[`r0-gguf-inspection.md`](r0-gguf-inspection.md)である。公開CLI
（`main --inspect-gguf`）と versioned exchanged document（`R0_GGUF_INSPECTION`,
`schema_version: 1`）を追加するため、`CLAUDE.md`のproportional design gateが発動する。契約・
validation順序・error code・closure matrix・fixture設計はすべてその文書が持つ。

実装中に見つかったAlignのgapは2件で、`docs/align-requests.md` Request 21
（read-only random-access file open）とRequest 22（Move要素配列のborrow indexing）として記録した。
Request 21: pin時点の唯一のrandom-access constructorは`fs.open_rw`で、書き込まないmodel fileに
`O_RDWR`を要求する。Request 22: `array<string>`やMove fieldを持つrecordの配列は`check_index`が
indexingを拒否するため、`src/gguf.align`はtensorの`absolute_offset`をNUL区切りのprefix streamと
並行する`array<i64>`として持つ。いずれもnon-blockingであり、R0は現行surfaceのまま進む。

### Gate

対象GGUFのmetadataとtensor一覧が既存toolと一致すること。この gateは
`scripts/run-gguf-reference-parity`（opt-in focused qualification、llama.cppの`llama-gguf`と比較）
が担い、model不要の`make gguf-smoke`が日常のownerとなる。

**達成済み。** 実モデル（Qwen2.5-Coder-7B Q4_K_M）に対する`scripts/run-gguf-reference-parity`は
PASSし、metadata KVペア29件、tensor 339件、`data_offset` 5,953,536、`bytes_read` 6,291,456を記録した。

---

## R1: Qwen / gpt-oss Frontend

```text
frontends/
  qwen/
  gpt_oss/
```

R1のauthoritative planは[`r1-qwen-model-ir.md`](r1-qwen-model-ir.md)である。Alignの1ファイル1
モジュールという慣習に沿い、上記`frontends/qwen/`が指すQwen2 frontendは`src/frontend_qwen.align`
としてflatな`src/`配下に実装する。tokenizer/vocabulary（`tokenizer.ggml.tokens`のようなMove要素
配列のindexingを要する、Request 22）はこのcapabilityから意図的に除外し、Request 22を
non-blockingのまま保つ。gpt-oss/MoE frontend（`ExpertBlock`/`RouterBlock`）は別capability
R1B-GPTOSS-MOE-IRとしてPR #123でmergeされた（[`r1b-gptoss-moe-ir.md`](r1b-gptoss-moe-ir.md)）。その
MoE frontendは`R1_MODEL_IR`を`schema_version: 2`へ引き上げ、block tensor recordへ
`claimed_absolute_offset`/`claimed_nbytes`の2フィールドを追加してper-expertのbyte claimを
表現する（同文書section 2.4）。`schema_version: 2`は既に出荷済みである。

### Gate

Model IRとBlock IRを生成できること。

**達成済み。** 実モデル（Qwen2.5-Coder-7B Q4_K_M）に対する
`scripts/run-model-ir-parity`はPASSし、`n_layer` 28、`n_embd` 3584、`n_head` 28、
`n_head_kv` 4、`head_dim` 128、`n_ff` 18944、`n_vocab` 152064、`n_expert` 0を記録した。
size-sum oracleは`data_offset` 5,953,536 + `total_tensor_bytes` 4,677,120,000 =
`computed_end` 4,683,073,536で`file_size`と一致し、339 tensorすべてが58 blockへ割り当てられた。
gpt-oss/MoEの半分（`n_expert > 0`、per-expert `ExpertBlock`）はR1B-GPTOSS-MOE-IR（PR #123）で
実装・mergeされ、合成corpusおよびsize-sum/claim-tiling oracle、MXFP4 library oracleで検証済み。
gpt-oss実モデルに対する`model-ir-parity` qualificationのみ、`gpt-oss-20b-mxfp4.gguf`（12.1 GB）の
ダウンロードに関するユーザー判断待ちのopen項目として残る（決定(b)は本hostでは容量不足のため
**infeasible**として記録済み、`HANDOFF.md`参照）。

**R1C-OLMOE-MOE-IR**（[`r1c-olmoe-moe-ir.md`](r1c-olmoe-moe-ir.md)、PR #132、merge
`e15e3d3`、design ledger commit `83361a9`）は第三のR1 capabilityであり、実MoEモデル
`OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf`に対する`src/frontend_olmoe.align`と三方向architecture
dispatchは`45e4ced`で**実装完了**、review指摘の修正commitがその上に載っている（forward order
item 18）。owner checkは4本ともPASS：`make check`（30 unit）、`make model-ir-smoke`（qwen 49、
gpt-oss 31、olmoe 29、R0 62 fixtureの再実行）、`make alignpack-smoke`（positive 27、negative source
128、assertion 20,280）、および実モデル2本に対する`make model-ir-parity`（olmoe 15行＋type census
`f32` 81 / `q4_K` 97 / `q6_K` 17、qwen2 14行）。olmoeのparityはR1Bが`N/A`としか記録できなかった
qualificationであり、実MoEモデルに対する初のPASSである。review・publication・mergeは完了している。
この実測は、R1Bのsection 2.5が`ASSUMED`としていた2行を**確認ではなく反証**した：stacked gate/up/down axis orderはR1Bの想定と逆であり、R1Bがrequiredとしていたsplit
expert bias群は実MoEファイルに一切bias tensorが存在しないことで汎用規則としては反証された。
どちらも実gpt-ossファイルがない以上gpt-oss frontend自体は変更せず、R1B section 7への訂正として
記録される（`r1c-olmoe-moe-ir.md` section 2.9, 5.3）。

---

## R2: Expert Trace

既存runtimeを測定器として利用する。測定器は`llama-eval-callback`（build 10566）である。

```text
R2a:
  callbackでrouter tensorを観測

R2b:
  callbackでtrace取得

R2c:
  不足時のみ最小patch
```

R2aのauthoritative planは[`r2a-expert-trace.md`](r2a-expert-trace.md)である。Merged:
`main --expert-trace CALLBACK_LOG [OUT.json]`が
`llama-eval-callback`のtranscriptを`R2_ACTIVATION_TRACE`（`schema_version: 1`）document
へ変換し、token・layerごとのexpert idとlocality aggregateを記録する。dense（非MoE）transcript
は`moe: false`を返す。

R2cのauthoritative planは[`r2c-decode-instrument.md`](r2c-decode-instrument.md)である。Exact
llama.cpp pinと最小の2-file patch、out-of-tree managed builder、full-axis schema-1 parser
adoptionを一つのconsumer-complete capabilityとして実装する。

### 測定

```text
- token間expert reuse
- language別偏り
- task別偏り
- repo別偏り
- prefill/decode差
```

### Gate

条件付き局所性が存在するか、数値で判断できること。

局所性が弱ければ、repo expert profileへの投資を縮小する。

**このgateはprefill方向で満たされた（2026-08-28、R2-LOCALITY-GATE）。** 小さなMoE GGUFの取得
判断は決定済みで、`OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf`（olmoe、16層、`n_expert` 64、
`n_expert_used` 8）を実測に使用した。測定器は`scripts/run-expert-locality-gate`、prompt corpusは
`eval/prompts/expert-locality-v1.txt`（40 prompt、全て6 token以下、md5
`d7fff23f5a1d4f6237e6f848f3318d8b`）。1 promptにつき1 invocation、合計51.8秒。

```text
verdict=LOCALITY  prompts=40  layers=15  layers_clearing=15  pairs=2280
null p0 = 125 per mille (k/n = 8/64)
observed p^ = 286 per mille (3924 / 13680)
95% Wilson = [279, 294] per mille (independent-trial assumption)
95% cluster-robust = [262, 311] per mille (40 prompt clusters, design effect 10.460) <- 判定に使用
p^ / p0 = 2.29x  (LOCALITY threshold: 1.5x)
histogram entropy = 992 per mille of uniform, top-8 mass = 180 per mille (uniform: 125)
working set w=2: 10.278 experts vs null 11.437 / w=4: 16.495 vs null 20.830
```

数値の意味と限界は[`r2a-expert-trace.md`](r2a-expert-trace.md) section 8にある。要点のみ:
routerのhistogramはほぼ一様（entropy 992 per mille、64 expertすべて使用）なので、2.29倍はpopularity
偏りではなくtoken間の条件付き構造による。15層すべてが単独でnullを超える（最小207、最大326 per mille）。
trialは1 prompt内で相関するため（1 promptが全層・全token位置を供給する）、design effect 10.460で
広げたcluster-robust区間[262, 311]を判定に使う。naiveなWilson区間[279, 294]ではない。

したがって「局所性が弱ければrepo expert profileへの投資を縮小する」は**発動しない**。R3の
residency simulationは実測されたdemand signalを前提にしてよい。

ただし**この測定結果はprefillのみ**である。当時の未patch build 10566は1 invocationにつき1 graphしか評価しないため
decodeの測定は存在せず（`phase_split.decode` は `null`）、decode時reuseやcache policyについては
何も主張しない。また1 promptあたり6 token位置まで、reuseは印字された3+3スロットのみの観測である。
このうち厳密に言えるのは**t側**の制限だけで、これはhitのみを取り除くのでp^を**低く**偏らせる。
t+1側の制限は分子と分母を同時に動かすため方向は確定できず、真のtop-8 reuseが286 per milleより
上か下かはここでは主張しない。最終層はinstrumentがoutput-token reductionを先に適用するため寄与しない
（section 6 correction 20）。R2cの測定器（item 22、merge済み）はこの過去の数値を書き換えない。

**decode方向も満たされた（2026-08-28、R2D-DECODE-LOCALITY-GATE）。** R2cのpatched instrumentを
使い、同じcorpusの40 promptを`-n 16 --temp 0 --seed 42`（greedy）で捕捉した。40 prefill graphと
640 decode graph、832 token位置（所要は診断値でありhost負荷に依存する: repair後の再実行で252.9秒、
その前は189.8秒。記録した数値はすべて両者で一致する）。router slotは8/8すべて印字されるため、印字subset用の
小さいnullは存在せず、nullは125 per milleただ一つである。隣接の定義はgraph内ではなく**系列**
上であり（decode graphは1 tokenなので、graph内定義ではdecode pairが1件も存在しない）、3本の
arm を同一ruleで判定する。測定器は`scripts/run-decode-locality-gate`、集計は
`scripts/expert_locality_gate.py`の`aggregate_decode`である。

```text
p0 = 125 per mille (k/n = 8/64), 40 prompt clusters, LOCALITY threshold 1.5x

prefill@8  (prompt内の隣接token)          verdict=LOCALITY  p^=371  Wilson [364,378]
                                          cluster-robust [338,405] (deff 23.274)  2.97x  15/15層
decode@8   (生成tokenの隣接)              verdict=LOCALITY  p^=447  Wilson [443,450]
                                          cluster-robust [426,468] (deff 35.375)  3.58x  16/16層
boundary   (prompt末尾 -> 最初の生成token) verdict=LOCALITY  p^=364  Wilson [350,378]
                                          cluster-robust [325,405] (deff 8.794)   2.91x  15/15層

histogram entropy: prefill 992 / decode 996 per mille of uniform, top-8 mass 179 / 163
working set (decode) w=2: 12.420 vs null 15.000 / w=4: 19.105 vs 26.484 / w=8: 28.328 vs 42.009
```

数値の意味と限界は[`r2a-expert-trace.md`](r2a-expert-trace.md) section 9にある。要点のみ:
**decodeのreuseはprefillより高く**（447 対 371、cluster-robust区間は重ならない）、decode側の
histogramはprefill側より一様なので（entropy 996 対 992）popularity偏りではない。8 token連続の
decodeで触れるexpertは28.33（独立仮定なら42.01）で、window拡大に伴い不足幅が広がる。greedy decode
のloop（同一tokenの連続）は測定済みで**51 per mille**にとどまり、該当pairを除外しても
decode@8は429 per mille・cluster-robust [408,451]・LOCALITYのまま変わらない。

限界: greedy（`--temp 0`）固定、`-c 512`、prompt 6 token以下、生成16 tokenの範囲のみ。
prefill@8の371 per milleは8 slot分母の別測定であり、section 8の286 per mille（印字6 slot）を
**書き換えるものではない**。1 model・1 corpus・1 hostである。R2bのcorpus横断層別
（language別/task別/repo別偏り）がR2で唯一未達のまま残る。

---

## R3: Cache Simulator

```text
align-sim
```

比較policy。

```text
- LRU
- LFU
- recent reuse
- score-based
- top-k prefetch
- impact-driven prefetch
- CPU fallback
```

### Gate

対象ハードウェア条件で、baselineより有効なpolicyを特定できること。

このgateはR3-RESIDENCY-SIM（roadmap item 21、[`r3-residency-sim.md`](r3-residency-sim.md)）が所有
する。実装・contract ledger・closure matrix・fixture設計・correction ledger・probe recordはすべて
同ledgerにある。実MoE model `OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf`と実corpus
`eval/prompts/expert-locality-v1.txt`（40 prompt、md5 `d7fff23f5a1d4f6237e6f848f3318d8b`）から
`R2_ACTIVATION_TRACE`を40件導出し、938 distinct key / 17,280 demandのstreamを10 policyで
replayした結果、**gateは達成**である: 要求budget 975,175,680 B（expert footprint
3,900,702,720 Bの250‰）で`recent_reuse_w32`が26,033,848,320 Bをfetchし、baselineの`lru`の
33,532,231,680 Bに対して223‰少ない（materiality floorは50‰）。40-fold
leave-one-document-out jackknifeの最小gainは213‰でstable、offline optimumまでのheadroomは574‰、
verdictは`BEATS_BASELINE`。9点sweepでは1/3/6/12/25 %が`BEATS_BASELINE`、0 %と50 %が
`NO_POLICY_BEATS_BASELINE`、100 %が`NO_HEADROOM`である。上のpolicy一覧のうち実装したのは
LRU・LFU・recent reuse・top-k prefetchの4系統で、score-based・impact-driven prefetch・CPU
fallbackはledger section 5.1のとおりprerequisite付きでdeferしている（router scoreはR2Aの
`schema_version: 2` weight column、miss penaltyはR4.5/R5の実測transfer cost、CPU fallbackはR5の
microbenchmarkが前提）。

**この結果が主張する範囲**（ledger section 4.5末尾および5.2-5.3）: prefill graphのみをdecode順で
replayしたものであり、decodeを観測したものではない。instrumentが印字するrouter slotは8中6、
prompt長は最大6 tokenで192 token positionしかなく、cache pressureの大半はprompt間のreuseに
由来する。比較指標はfetch byte数のみで、時間・帯域・throughputの主張は一切含まない。したがって
読み方は「短いrequestが多数並ぶsessionにおいて、frequency-awareなresidencyはrecencyに勝つ」で
あり、「1回の生成の内部でexpert reuseが高い」ではない。後者にはR2cのdecode traceが必要である。

**decode方向も満たされた（2026-08-28、R3-DECODE-RESIDENCY、roadmap item 25）。ただし答えは
上記より狭い。** R2cのpatched instrumentで捕捉した同じ40 prompt・`-n 16 --temp 0 --seed 42`の
decode corpus（R2Dと同一のcapture、admissionも同一の`require_full_router_axes`）を
`main --simulate-residency`で4 armに replayした。arm (i) **mixed**は捕捉したままのlist
（40 prefill + 640 decode graph、832 token位置、104,960 demand）、arm (ii) **decode-only**は
graph 0 をprojectionで落とし ordinalはそのまま残したlist（640 decode graph、640 token位置、
81,920 demand）、arm (iii) **prefill-only**は逆にdecode graphだけを落とした**coverage control**
（40 prefill graph、192 token位置、23,040 demand）、arm (iv) **head-4**はdecode ordinal 1–4だけを
残した**stream長のcontrol**（160 decode graph、160 token位置、20,480 demand）である。

第3・第4のarmが必要な理由は、それぞれ別の交絡を除くためである。まずR2cが**2つの変数を同時に
動かした**: router slotの印字が6/8から8/8になり（slot coverage 750‰ → 1000‰）、同時に実decode
graphが現れた。mixedとdecode-onlyはsection 7.4のstreamに対して両方が変わっているため、結果が
動いてもどちらが原因か決められない。prefill-only armはcorpus・budget・admission・8 slot軸を
固定し、decode graphだけを除く。したがってこのarmが他と同じverdictを出せばそれはcoverageの
効果であり、出さなければcoverageの効果ではない。次にそのcontrol arm自身がdecode armより
**短い**（23,040 対 81,920 demand）ため、verdictの差がphaseではなくstream長に由来する可能性が
残る。head-4 armはphaseを保ったまま各生成を先頭4 stepに切り詰め、20,480 demandにする。
このarmがdecode-onlyと同じverdictを出せば、それはstream長の効果ではない。

```text
budget 975175680 B (250‰), token_major

arm          baseline lru        best_policy  gain   headroom  jackknife      result
mixed        176,661,381,120 B   -            0‰     476‰      未実施         NO_POLICY_BEATS_BASELINE
decode-only  134,615,285,760 B   -            0‰     473‰      未実施         NO_POLICY_BEATS_BASELINE
prefill-only  44,349,947,904 B   lfu          194‰   552‰      最小186‰ 安定  BEATS_BASELINE
head-4        33,722,744,832 B   -            0‰     453‰      未実施         NO_POLICY_BEATS_BASELINE

sweep（mixed と decode-only は全pointでverdict一致。以下 mixed / decode-only / prefill-only / head-4）
   7‰   NO_POLICY_BEATS_BASELINE（4 arm共通）
  15‰   BEATS_BASELINE   recent_reuse_w32 59‰ / 59‰、prefill-onlyは lfu 61‰、head-4のみ NO_POLICY（41‰）
  31‰   BEATS_BASELINE   recent_reuse_w32 137‰ / 134‰ / 106‰ / 97‰
  62‰   BEATS_BASELINE   recent_reuse_w32 238‰、recent_reuse_w8 232‰、recent_reuse_w32 226‰、recent_reuse_w8 200‰
 125‰   BEATS_BASELINE   recent_reuse_w32 59‰、recent_reuse_w8 70‰、lfu 78‰、recent_reuse_w8 70‰
 250‰   NO_POLICY（mixed/decode-only/head-4、headroom 476‰ / 473‰ / 453‰）／ BEATS_BASELINE（prefill-only、lfu 194‰）
 500‰   NO_POLICY_BEATS_BASELINE（4 arm共通、headroom 593‰ / 583‰ / 496‰ / 512‰）
1000‰   NO_HEADROOM
```

数値の意味と限界は[`r3-residency-sim.md`](r3-residency-sim.md) section 8にある。要点のみ:
**baselineより有効なpolicyは依然として特定できる**（expert footprintの1.5–12.5 %では
`recent_reuse`が59–238‰勝つ）が、**section 7.4が記録した25 %の動作点では、decodeを含む3 armの
どのcandidateもlruに勝たない**。`recent_reuse_w2`はlruとbyte単位で完全に一致し、`lfu`は221‰の
節約から152‰・190‰・88‰の悪化へ符号が反転した。

**その原因はcoverageでもstream長でもなくdecodeである。** control armであるprefill-onlyは同じ
25 %のbudgetで`lfu`が194‰勝ち、jackknifeも安定（最小186‰）で`BEATS_BASELINE`となる。
`recent_reuse_w32`も191‰でfloorを越える。つまりsection 7.4の223‰という結果は**8/8 slotでも
生き残る**（223‰ → 194‰）のであって、6 slot subsampleの産物ではなかった。さらにhead-4 armは
prefill-only armより**11 %短い**20,480 demandでありながら`NO_POLICY_BEATS_BASELINE`（gain 0）
のままである。同じcorpus・同じbudget・同程度の長さの2 armが**逆のverdict**を出し、両者の違いは
tokenがpromptか生成かだけである。初期の草稿はworking setの拡大（341 MB → 455–488 MB、budgetが
2.86倍から2.0–2.14倍へ）を原因としていたが、これは**実測により棄却された**: 勝つprefill-only arm
の2.14倍は、負けるmixed armのprefill位置とまったく同じ値である（7 %の差はdecode位置の2.00倍との
差であって、arm間の差ではない）。

decodeで何が変わるかはbyte tableが示す。`lru`はdecodeでむしろ**強くなり**（hit 569‰・568‰ 対
prefillの492‰）、`lfu`は**弱くなる**（487‰・530‰ 対 592‰）。**なぜfrequencyが効かなくなるのかは
本測定では確定しない。** decodeのexpert分布がprefillより一様であること（entropy 996 対 992、
top-8 mass 163 対 179、64 expert全使用、`docs/specs/r2a-expert-trace.md` section 9.2）と整合する
が、同document section 9.4はその効果量を**小さい**と測っている（entropy差4‰、うち推定量のbiasが
最大0.24‰、相対mass分散は約3 %）。したがってこれは**候補となる説明の1つ**であって、実証された
機構ではない。

**分離できていない点を明示する**: coverageとstream長は上記の2つのcontrol armで除かれた。残るのは
「decodeのrouting統計」と「decode位置あたりのworking setの広さ」の区別である。decode位置は16層
（128 key・487,587,840 B）をdemandし、prompt位置は15層（120 key・454,950,912 B）である。この2つ
を分離するarmは本capabilityでは作らない。

一方でofflineに対するheadroomはdecodeを含む3 armで25 %に476‰・473‰・453‰、50 %に593‰・583‰・
512‰残り、**online candidateはその一切を回収していない**。これはledger section 5.1が
prerequisite付きでdeferしているscore-based / impact-driven prefetchに投資する根拠であって、
recency/frequencyの変種を増やす根拠ではない。`topk_prefetch`は4 armのいずれでも改善しない
（mixedでk=1がlru比+4 %、k=8で+65 %のbyte、prefill-onlyでも-10‰・-343‰、head-4でも-36‰・
-567‰）。
section 7.4の223‰という記録は**書き換えられない**: `scripts/run-residency-sim`はfull-axis document
を引き続き拒否するため、2つのstreamがpoolされることはない。

限界: greedy（`--temp 0`）固定、`-c 512`、prompt 6 token以下、生成16 tokenの範囲のみ。
`pooling`は4 armとも`continuing`であり、decode-only armもhead-4 armも40件の生成を1つのcacheに
poolしている（「多数の短いrequestからなるsession」であって「1回の長い生成」ではない）。head-4 arm
は**長さのcontrol**であって「4 token生成して止まるworkload」の測定ではない。
prefill graphの最終層はinstrumentのoutput-token reductionで縮約されるため、layer 15はdecodeで
初めてdemandされる（prefill-only armのdemand layerは15、他の3 armは16）。
`one_token_working_set_*`はpooled streamの**先頭token位置1つ**の値であり、armごとの平均ではない
（mixedとprefill-onlyはprompt tokenの120 key / 454,950,912 B、decode-onlyとhead-4はgenerated
tokenの128 key / 487,587,840 B）。sweep表の各行にjackknifeは無い（section 2.8はrequested budgetでのみ
resamplingする）。時間・帯域・throughputの主張は一切含まない。

---

## R4: alignpack v1

```text
align-pack model.gguf
```

基本layout。

```text
layer-major
  + layer-local block grouping
  + expert hotness
  + prefetch group
```

### Gate

元GGUFとのtensor内容一致と、連続read量の改善を確認できること。

このgateはR4-ALIGNPACK-LAYER-MAJORが所有し、PR #125（head `a7e72dc`、merge `991eab1`）で
merge済みである。実装・contract ledger・closure
matrix・fixture設計・correction ledgerはすべて
[`r4-alignpack-layer-major.md`](r4-alignpack-layer-major.md)にある。qwen側は実weightで達成済み
（89 → 58 range、2,379,786 → 1,000,000 ppm、27 → 58/58 contiguous、byte identity）。per-expert側も
MOE-PREREQ-DISCHARGE（roadmap item 20、[`moe-prereq-discharge.md`](moe-prereq-discharge.md)）が
実MoE model `OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf`で達成した（1,024 ExpertBlockが
3,072 → 1,024 range、165,368,823,808 → 3,900,702,720 span、42,394,624 → 1,000,000 ppm、
0 → 1,024/1,024 contiguous）。残る**MOE-PREREQ**はgpt-oss固有（6 member ExpertBlock、MXFP4、
split expert bias、fused `ffn_gate_up_exps`）のみである。

**expert hotness orderingとprefetch groupは引き続きdeferされている。** R4B（hotness layout）を
評価した結果、R2-LOCALITY-GATEが測定したrouter histogramはほぼuniform（entropy 992 per mille、
64 expert全使用）であり、この分布下ではprefetchはむしろ有害と判定され、実装は開始しなかった。
resume条件は、decode corpusまたはskewを示すstratified corpusが得られることである
（roadmap item 19、`docs/specs/r2a-expert-trace.md`）。R3-RESIDENCY-SIM（roadmap item 21）は
R4がpackした1,024個のnon-contiguous `ExpertBlock`を入力としてcache policyを比較し、gateは
`BEATS_BASELINE`で達成済み（25% cache fractionで`recent_reuse_w32` 26.03 GB対LRU 33.53 GB、
gain 223‰、jackknife最小213‰）。

**R4Bのresume条件のうち「decode corpus」の側は2026-08-28に解消され、結論はdefer継続である。**
R2C-DECODE-INSTRUMENT（item 22）がdecode corpusを取得可能にし、R2D-DECODE-LOCALITY-GATE
（item 24）とR3-DECODE-RESIDENCY（item 25）がそれを実測した。得られた答えは2つとも
hotness layoutを支持しない: decode側のhistogramはprefill側より**さらに一様**で
（entropy 996対992 per mille、top-8 mass 163対179、64 expert全使用、
`docs/specs/r2a-expert-trace.md` section 9.2）、hotness orderingが前提とするskewは存在しない。
そしてdecodeを含むstream上のresidency simulationでは、25 %および50 % budgetで**どのcandidateも
LRUに勝たず**、`topk_prefetch`は4 armのいずれでも改善しない（mixedでk=1が+4 %・k=8が+65 %のbyte、
prefill-only armでも-10‰・-343‰、長さを揃えたhead-4 armでも-36‰・-567‰）
（`docs/specs/r3-residency-sim.md` section 8.2・8.3）。
したがってresume条件は**充足されたうえで否定的に解消**された: expert hotness orderingと
prefetch groupは、「decode corpus待ち」ではなく「decode corpusで測ったが正当化されなかった」として
引き続きdeferする。

**この否定はprefetch group全体に及ぶが、frequency信号そのものに及ぶわけではない。** item 25の
control armは、同じ25 % budget・同程度の長さのprefill-onlyのstreamでは`lfu`が194‰勝つことを
示している
（`docs/specs/r3-residency-sim.md` section 8.2）。つまりprefillのrouting分布には依然として
frequencyが利用できる偏りがあり、上の否定は**decodeを含む動作点**についての否定である。
それでもR4Bのhotness orderingは再開しない: hotness orderingは**静的なpack順**であって
動的なcache policyではなく、静的順を正当化するのはcorpus横断のskewである。item 24が測った
decode histogramにそのskewは無く、prefill側のskewはR4が既にlayer-major layoutで扱っている。
残るresume経路は引き続きR2bのstratified corpus（language別/task別/repo別）がskewを示すことである。

---

## R4.5: External Buffer Spike

alignが所有するDRAM/VRAM buffer上の量子化weightを、ggml backendで計算できるか確認する。

### Gate

```text
- align owns buffer lifetime
- no silent copy
- quantized layout preserved
- one expert matmul succeeds
```

失敗時はruntime設計を見直す。

このgateはR4.5-EXTERNAL-BUFFER-SPIKEが所有する。実装・contract ledger・closure
matrix・fixture設計・correction ledgerはすべて
[`r4-5-external-buffer.md`](r4-5-external-buffer.md)にある。同ledger section 1.4がgate 4節を1節ずつ
判定しており、現状は次のとおり:

- `align owns buffer lifetime` — **達成**。bytesはAlignの`buffer` localが所有し、ggml objectは
  所有scope終了前にすべて明示的に解放される（実測 buffers 4/4、contexts 2/2、backends 1/1、
  `released_before_owner_scope_end true`、`exit`でのabortなし）。
- `no silent copy` — **達成（DRAM実weight）**。`ggml_get_data(A)`がAlign buffer内のmember interior
  offsetと厳密に一致（`14336 == 14336`、`verdict: EXTERNAL`）。
- `quantized layout preserved` — **達成**。実Q4_K tensorの出力が元GGUFをggml所有memoryに読んだ
  reference armとbit一致（`differing_elements 0` / 14,336 f32）。
- `one expert matmul succeeds` — **dense blockとexpert claimの両方でCPU backend上達成**。
  MOE-PREREQ-DISCHARGE（roadmap item 20）が実MoE model
  `OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf`のExpertBlock claimを計算し、元GGUFの同一planeと
  bit一致した（`verdict: EXTERNAL`、`differing_elements 0`）。shipped armは当初この claimを
  `R4_5_SHAPE`（detail `n_dims[3]`）で拒否しており、`schema_version: 2`・step 7a/7bの shape rule・
  `R4_5_SLICE` codeの追加が必要だった。GPU armは引き続きdeferである。

**未達として明示的にdeferしているもの**（ledger section 5.4）: GPU/Metal arm（unified memoryでは
no-copyで動作することを実測済みだが、CPU出力とbit一致しないためtolerance oracleと別のalignment
ruleが必要＝別のacceptance contract）、discrete VRAM（`ggml-cuda.h`に`buffer_from_host_ptr`相当が
存在せず、この環境では原理的に回答不能）、およびR5のloader（residency・eviction・prefetch）。

---

## R5: Minimal Runtime

```text
- alignpack loading
- DRAM → VRAM
- cache slot
- CPU fallback
- ggml computation
```

### 必須microbenchmark

```text
A: transfer + GPU compute
B: CPU compute
C: async prefetch + GPU compute
```

### Gate

単一block、単一layer、最小モデルの順に正しい出力を得ること。

このgateは3段階を個別に判定する。単一block（単一Q4_K memberのDRAM実weight matmul）は
R4.5-EXTERNAL-BUFFER-SPIKEが達成済み（上記R4.5節参照）。単一layer（CPU、dense）は
R5A-DENSE-LAYER-FORWARDが対象とし、実装・owner検証・実modelでのqualificationにより達成済み——
`docs/specs/r5a-dense-layer-forward.md`が権威あるledgerで、transcript（tolerance）oracleは
18ノード全一致（sampled 1,116要素、max`|Δ|` 0 ten-thousandths。design段階のprobeは5.0e-5で、
instrumentの印字精度上限）、bit-exact
self-reference oracleは20/20 tensor byte一致、microbenchmark Bは**13.4 ms前後**（1 dense layer、
6 token、warm。実装済みarmの4 run計測で12.97-15.05 ms。design段階のprobe harnessは15.5 ms中央値）。最小モデル（stage 3、prefill専用・KV cacheなし、dense CPUで全28層＋`output_norm`＋`output`）は
R5B-MODEL-PREFILL-FORWARDが対象とし、実装・owner検証・実modelでのqualificationにより達成済み——
`docs/specs/r5b-model-prefill-forward.md`が権威あるledgerで、instrumentの宣言attention幅（KV width
256）ではfinal logits 152,064要素が`llama-debug --save-logits`とbyte-identical（sha256
`d2e48620…`）、28層＋headの全oracleノード30,078要素が`llama-eval-callback`の印字精度で
ten-thousandths 0一致、bit-exact self-reference oracleは30 graphで479/479 node byte一致。
runtime自身のattention幅（prefillの6 token）ではmax`|Δ|` **2,739 ten-thousandths**（0.2739）、
argmax 671、top-10完全一致——差はKV cache非搭載という宣言済みnon-goalの帰結と測定済み。必須
microbenchmarkのうちBはR5Bが**whole-model scale**で達成（six-token prefill。design段階のprobeは
wall 1.07-1.12 s、compute 349.6 ms、pread 533 ms/4,370,571,072 B。実装済みarmは
wall 1,141-1,275 ms、compute 484-620 ms、pread 515-648 ms、447,086,592 Bのwindow 1つ、warm）。
必須microbenchmarkのうちAはR5C-METAL-PREFILL-ARM（`docs/specs/r5c-metal-prefill.md`）が
unified memory上で達成した。align-llm PR #129としてmergeされ、実装・両review repair・Metal host上の
qualificationはすべて完了している（ledger section 7）。R5Bと同一のAlign-owned window
（447,086,592 B）をMetal deviceへ
`ggml_backend_dev_buffer_from_host_ptr`経由で渡し、339配置すべてがexternalかつzero-byte copyだが、
この「transfer」はwrap（`ggml_backend_dev_buffer_from_host_ptr`の呼び出し自体）として測定され、
実装されたarmは1 wrapあたり**12.4 ms**、runtime passとreconciliation passの両方を走らせるため
59 wrapで**732 ms**を要する（correction C7。section 2.7のsingle-pass probeは30 wrapで354.8 ms、
CPU比0.075 ms）。byte-identicalなCPU logits vector（`d2e48620…`）に対しmax`|Δ|`
**2,936 ten-thousandths**、argmax 671、top-10完全一致、152,064要素中0.5超はゼロで、
6,000 ten-thousandthsのtoleranceに収まる（測定値の2倍を切り上げ）。reconciliation幅のcompute
自体はGPU **375 ms**対CPU **486 ms**だが、end-to-endのwall比は3組のpairで1.31倍／0.99倍／
1.05倍（中央値**1.05倍**）と散らばり、その散らばりは`pread`由来であるため
**未確定として記録し、結果としては主張しない**——実装前に記録したcost ceilingが負の値だったため、
GPUが速くならないという結果はceiling-estimation missではなく、microbenchmark Aの正直な結果
として許容される。Cは`spawn`
closureが所有値（`buffer`）をcaptureできず、captureしたタスクが値を返すこともできないため
この pinでは書けず、Request 41としてAlign capability requestに記録した上でdeferされる
（`docs/align-requests.md`、`r5c-metal-prefill.md` section 2.10・5.5）。discrete VRAMは
この環境では原理的に回答不能というR4.5・R5A・R5Bの結論を引き継ぐ（`r4-5-external-buffer.md`
section 5.4、`r5a-dense-layer-forward.md` section 5.4、`r5b-model-prefill-forward.md`
section 5.4、`r5c-metal-prefill.md` section 1.3）。

**単一layerのrouted版（MoE stage 2）はR5D-MOE-LAYER-FORWARD（roadmap item 23、
`docs/specs/r5d-moe-layer-forward.md`）が対象とする。** branch `agent/r5d-moe-layer-forward`、
merged R3の上へrebase済み（`main` `95c47e7`）、design ledger `a85e1fc`、実装 `7886cee`、
review repair `a2e2748`。PR #139（merge commit `e312bd7`）としてmerge済みである。
probeはplanの前提を複数覆した——QK-normは`head_dim`単位
ではなく`n_embd`全体へのRMS normであり、routerのtop-8はrenormalizeされず、top-k nodeは
`ggml_top_k`ではなく`ARGSORT`＋`VIEW`である。compactしid remapしたexpert stackは`mul_mat_id`で
llama.cppのwhole-tensor形状とbit一致（28/28 node dump一致）し、restacking copyは不要と判明した。
transcript oracleはmax`|Δ|` 5.0e-5（instrumentの印字精度上限）、routing-identity oracleは
selected expert idが完全一致。**実装済みarmの実model計測**（ledger section 7.1）では
routed layerがexpert byteの**101,990,400 / 261,095,424**（390,625 ppm、75/192 plane、25 block read）
を読み、self-reference oracleは46/46 node byte一致、routing-identity oracleは`MATCH`（printed id
完全一致、sum 1,471）、transcript oracleは`PASS`（26/26 node、2,376要素、max`|Δ|` 0
ten-thousandths）。microbenchmark Bは**5.64 ms**（1 routed layer、6 token、warm；
phase A 1.452 ms、phase B 4.185 ms。design段階のprobeの9.4 msはarmごとにcold graphを計測したもの）
で達成。**このcapabilityが測定するresidency winは
planが想定したより小さい**——6 tokenのprefillでlayerのexpert byteの39.1%を読む
（1 tokenでは12.5%、18 tokenでは73.4%）ため、claim単位のexpert residencyは
**decode-time property**として記録され、prefillの勝ちとしては主張されない。

**whole modelのrouted版（MoE stage 3）はR5E-MOE-MODEL-PREFILL（roadmap item 26、
`docs/specs/r5e-moe-model-prefill.md`）が対象とする。** branch `agent/r5e-moe-model-prefill`、
merged R5D（`main` `e312bd7`）とmergeし、design ledger `5e3356d`、実装 `053de09`、
review repair `e7f727f`。実装・review・実modelでのqualificationは完了し、publication中である。
armは16 layerすべてをper-layer routingで流し、選択されたexpertのplaneのみを
**単一の**Align所有claim window（arithmetic union boundで確保し、layer間で再利用）へ読み込み、
layer 15内部でinstrumentと同じ位置でnarrowingし、output headまで計算する。**実model計測**では
最終logitsが`llama-debug --save-logits`と**byte一致**（sha256 `a56195da…`、`IDENTICAL`）、
self-reference oracleは**227/227** node byte一致、transcript oracleは**227 node・21,372要素**で
`PASS`、routing-identity oracleは全16 layerで**546/546** `MATCH`。6 tokenのprefillは
expert byteの**1,301,446,656 / 3,900,702,720＝333,644 ppm（33.36%）**しか読まない——すなわち
この modelのexpert weightの2/3はprefillで一度も触れられない。peak resident weight byteは
280,342,528（4,212,193,280 B containerの**6.66%**）。microbenchmark Bは**単一の数値ではなく形状**
として達成される——probeのwarm C harnessはcompute **121.3 ms**対claim `pread` **~227 ms**、
shipped armのqualificationは**252.8 / 109.9 / 147.3 ms**対**612.0 / 519.9 / 560.8 ms**であり、
いずれのrunでもclaim readはcomputeの**1.9〜4.7倍**である。すなわち
**page cacheに載っていてもI/O boundである**ことが、residency policyが超えるべき数値である。
ここでのtimingはすべて単一runまたは小さなmedianであり、ledger correction **C16**が記録する
分散を伴う（exact integerのresidency側にはその risk はない）。**residency policyとcache hitの主張は引き続きdeferされる**
——1回のprefill内では343 demandに対しdistinct keyも343であり、cacheは原理的にhitしないため、
policyの測定にはmulti-prefill sessionかdecodeが必要である。

---

## R6: Persistent KV

```text
- session KV
- repo stable prefix KV
- DRAM tier
- NVMe tier
- invalidation
```

### Gate

同一prefixを使う反復coding taskでTTFTが改善すること。

**未達。** item 27（R6-DECODE-KV-STEP1）は`n_past = T`の1 decode stepとAlign所有のKV planeを
正しさの観点で実装したものであり、session KV・prefix KV・DRAM/NVMe tier・invalidationのいずれも
持たず、TTFTの主張もしない。このgateを満たすには少なくともstep 2とdecode loop、そのうえで
prefix再利用とresidency policyが必要である。item 29（R6-KV-PERSIST）はKV planeをディスクに
永続化し別プロセスで再読み込みする——5項目のうちsession KVのみ——が、prefix共有・DRAM/NVMe tier・
invalidationは持たず、TTFTの主張もしない。item 37（R6-PREFIX-KEY）はprefix planeの
content-addressed storeを実装し、keyとstoreという欠けていた4つのうち2つを埋めた——しかしcorpusと
consumerは依然として存在せず、TTFTの主張もしない。`MAX_PREFILL_TOKENS`が32のままであるため実際の
promptは1つも入らない（`eval/prompt/canonical-v1`の再利用可能な共有prefixは369 token）。cap引き上げ・corpus
固定・gate測定はitem 38（R6-PREFIX-TTFT）が担う。

**順序についての実測由来の結論（2026-08-28、R3-DECODE-RESIDENCY、roadmap item 25）。**
R6はexpert residencyのruntime実装より**先**に着手してよい。実際の運用に最も近いmixed arm
（prompt + 生成をpoolした1本のstream）では、25 %および50 %のcache fractionで`lru`を上回る
candidate policyが存在せず、`recent_reuse`が勝つのは1.5–12.5 %の狭いbudget帯に限られる
（`docs/specs/r3-residency-sim.md` section 8.3）。つまり「`recent_reuse`をruntimeへ持ち込めば
広い動作点で効く」という前提は**decodeを含むstreamでは成立しない**ため、それをKV tieringに
優先させる根拠はない。

この結論は2つのcontrol armによって**強められている**。prefill-only armは同じ25 % budgetで`lfu`が
194‰勝ち（`BEATS_BASELINE`、jackknife最小186‰）、長さを揃えたhead-4 armは20,480 demand（prefill-
onlyより11 %短い）でも`NO_POLICY_BEATS_BASELINE`のままである。したがって25 %でcandidateが
勝てないのはslot coverageの変化でもworking setの拡大でもstream長でもなく、**streamにdecode
demandが含まれること**に帰属する。runtimeが実際に扱うのはまさにそのstreamであり、prefillだけのstreamではない。
残る476‰のheadroomを取りにいくにはscore-based / impact-driven policyが必要で、
その入力（R2Aの`schema_version: 2` weight column、R4.5/R5の実測transfer cost）はまだ存在しない
（ledger section 5.1）。したがってTrack Bの次順はKV tieringであり、expert residency policyの
runtime実装はその前提が揃ってから再評価する。

---

## R7: Codex / align-coder Integration

```text
align-coder
  ↓ ModelProvider
align-runtime
```

### Gate

既存providerからalign-runtimeへ差し替えても、同じ固定coding taskを実行できること。

---

## R8: Hybrid Expert Execution

```text
- score-based cache
- CPU/GPU decision
- impact-driven prefetch
- router lookahead
```

### Gate

llama.cpp等のlocal baselineに対して、対象ハードウェア上でtime to passing patchまたはdecode latencyが改善すること。

---

## R9: Speculative Execution

small coding modelをdraftとして利用する。

### 評価

```text
- acceptance rate
- task type
- language
- repo
- actual speedup
```

速くならない組み合わせは無効化する。

---

## R10: Large-model Pressure Test

初期目標ではない。

候補。

```text
- Qwen大型Coder MoE
- DeepSeek系巨大MoE
```

目的。

```text
- NVMe → DRAM → VRAM
- expert streaming
- physical layout
- persistent KV
- extreme memory pressure
```

### Gate

「起動できる」ではなく、coding taskで意味のある速度が得られること。

---

# Integration Track

## I0: Existing Model + align-coder

align-coderの価値を既存modelで証明する。

## I1: Local Model + align-coder

クラウド依存を減らし、local baselineを作る。

## I2: align-runtime + align-coder

KV、profile、cacheを共有する。

## I3: Self-optimizing Local Coding Loop

```text
generate
verify
repair
measure
update profile
propose prompt patch
evaluate
accept or rollback
```

この状態がalignの最初の完成形となる。

---

# 優先して作らないもの

```text
- 3つ以上のモデルfrontendを同時開発
- 多数言語の静的解析
- 独自IDE
- 汎用chat
- multimodal
- 全自動prompt変更
- 独自GPU kernel
- 1Tモデルを動かすだけのデモ
- Codex CLI全体の再実装
```

---

# 開発判断の停止条件

次の場合は設計を縮小・変更する。

```text
- repo別expert profileがlanguage/task profileを上回らない
- alignpackの物理配置が実測で改善しない
- CPU/GPU hybridが既存runtimeを上回らない
- prompt自己改善が固定評価セットで回帰を起こす
- 巨大モデルが遅すぎてcoding loopに使えない
- 対応モデル追加が本質的検証を遅らせる
```

---

# 最初の実装順

```text
1. 固定coding評価タスクを作る
2. ModelProvider abstractionを作る
3. Patch Evaluatorを作る
4. build/test/repair loopを作る
5. Repo Indexを追加する
6. Failure Memoryを追加する
7. Prompt OptimizerのA/B評価を作る
8. 並行してalign-inspectを実装する
9. expert traceとcache simulatorを実行する
10. align-runtimeをproviderとして統合する
```

この順番なら、align-runtimeが完成する前から、align-coderの価値と局所最適化の仮説を検証できる。
