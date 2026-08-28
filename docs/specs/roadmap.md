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
    routed half of R5's second gate stage. Implemented and reviewed; in publication.** On branch
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
    model. Implemented and reviewed; in publication.** On branch `agent/r2d-decode-locality-gate`,
    started from `main` `89d8721` (R2c PR #140) and merged with `main` `e312bd7` (R5D PR #139)
    rather than rebased over it, so its recorded commits stay reachable.
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

**Items 25 and 26 are claimed and unmerged**, which is why this list steps from 24 to 27:
`agent/r3-decode-residency` holds **25** and `agent/r5e-moe-model-prefill` holds **26** (and Align
Requests 47/48). Both are reserved rather than skipped, and item 27's own number is re-checked at
reconciliation against whatever has merged by then.

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
    gate stays unmet and the next capability toward it is step 2 and the decode loop.

### Status (2026-08-28)

Track B is complete on the dense local model from R0 through R5C (item 17). Decision (a) is taken:
`OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf` (allenai, 4,213,512,192 B, sha256 `4ddc0e53159e…`, arch
`olmoe`, 16 layers, 64 experts top-8) is downloaded, and it unblocked items 18 through 24 above:
items 18 through 22 are merged, R2's gate is met, R4's and R4.5's per-expert halves are discharged,
R3's gate is met on the real corpus, and decision (c)'s pinned decode instrument is shipped. It also
unblocked item 23, R5D-MOE-LAYER-FORWARD, which is implemented, reviewed, and in publication with
one routed OLMoE layer computed over Align-owned expert claims and agreeing with llama.cpp node for
node, and item 24, R2D-DECODE-LOCALITY-GATE, which is implemented and reviewed and meets R2's
locality gate in the decode direction on the same 40-prompt corpus. Decision (b), `gpt-oss-20b-mxfp4.gguf` at 12.1 GB, is now recorded
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
gain 223‰、jackknife最小213‰）。hotness orderingとprefetch groupそのものは、この2つの実測結果を
resume条件として引き続きdeferされる。

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
review repair `a2e2748`。実装・review・実modelでのqualificationは完了し、publication中である。
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
prefix再利用とresidency policyが必要である。

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
