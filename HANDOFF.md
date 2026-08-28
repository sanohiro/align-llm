# Session handoff

Read `CLAUDE.md` first. GitHub owns transient pull-request checks, reviews, and attestations; this
file records durable project state.

## Active: R1C-OLMOE-MOE-IR (2026-08-28)

Branch `agent/r1c-olmoe-moe-ir`, rebased onto `main` `546b5cc` (the merged R2-LOCALITY-GATE, PR
#131). Design ledger `docs/specs/r1c-olmoe-moe-ir.md` is authoritative. Implementation and review
are complete; publication is the only remaining step.

**The model.** `OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf` (path withheld from this file by
convention), 4,213,512,192 bytes, sha256
`4ddc0e53159ed512b8dd67914a66e27bc618f694672ba43a9a0454eabd9c684f`, architecture `olmoe`, 16
layers, `n_expert` 64, `n_expert_used` 8, types F32/Q4_K/Q6_K. The download was user-approved under
decision (a).

**What it delivers.** A new `src/frontend_olmoe.align` turns the real file into `R1_MODEL_IR` at the
unchanged `schema_version: 2` through a frontend table over the shared model IR: 195 tensors =
3 global + 16 layers x 12 per-layer patterns, a three-way architecture dispatch across three verbs,
and two roles appended to the frozen `role_id` list, `attn_q_norm` (27) and `attn_k_norm` (28),
guarded by a three-list mirror regression. Per-expert claims tile the stacked tensors, including
layers that mix Q4_K and Q6_K. The size-sum oracle closes at
`1,781,760 + 4,211,730,432 = 4,213,512,192` on the real file, and the Block IR reaches 1,058 blocks
/ 3,219 claims. `src/model_ir.align` and `src/gguf.align` are **byte-unchanged**, proven by 284
differential invocations rather than asserted. The ledger's section 3 closure matrix is discharged
(section 6.1 maps every cell to its shipped case, and section 6 records eleven corrections to the
plan).

**R1B corrections 16-18.** The real model contradicts rather than confirms two of R1B's `ASSUMED`
rows: the stacked gate/up/down axis order is reversed versus R1B's gpt-oss assumption, and R1B's
required split expert biases are falsified as a generic rule (the real file carries no bias tensor
of any kind). Both are recorded as corrections in `docs/specs/r1b-gptoss-moe-ir.md` section 7 and
are deliberately not repaired in the gpt-oss frontend, since no real gpt-oss file is present to
settle it (decision (b) is infeasible on this host).

**Committed on the branch.** Nothing is uncommitted. After the rebase onto `546b5cc` the branch is
`83361a9` (design ledger), `45e4ced` (implementation), `4c86336` (review repair), and the
reconciliation commit on top; the same three commits were `5a15fd7`, `eb868ba`, and `58e9ba9`
before the rebase, and the review record below names the pre-rebase head it read. No `Makefile`
change, so the classifier stays in hosted scope.

**Review envelope.** Two complementary reviewers covered the implementation head `eb868ba`
(`45e4ced` after the rebase) for explicitly disjoint risks. Reviewer A: approve, three nit findings
(the block-explosion guard always naming `olmoe.expert_count`; section 2.6's key-order sentence read across steps rather than within
one; `role_required` ignoring its parameter). Reviewer B: approve with changes, three medium and one
low (section 4.5 calling the real model's 2,097,152-byte `bytes_read` one window when it is two;
`docs/align-requests.md` Request 23 carrying no R1C evidence block and the ledger calling the
frontend a "third client"; `HANDOFF.md`, `docs/specs/roadmap.md` item 18 and its Japanese section R1,
and `docs/align-development.md` still describing R1C as unimplemented; the parity runner's `ulimit -f`
bounding the Metal shader cache). All seven findings were accepted, none rejected, and all are
repaired in one consolidated commit on top of it (`4c86336`). The repair is narrow — a diagnostic
detail key with its fixture, one enumerated function, one runner limit, and documentation — so it does not
trigger a second comprehensive review, and the reconciliation commit onto the merged locality gate
is documentation-only.

**Verification.** Durable owner evidence at the repaired head, all four PASS on this macOS host with
the recorded Homebrew `LIBRARY_PATH` (`docs/align-development.md`):

```text
gmake check              ok: checked 30 unit(s) per-unit
gmake model-ir-smoke     PASS — 49 qwen, 31 gpt-oss, 29 olmoe, 62 R0 fixtures re-run
gmake alignpack-smoke    PASS — 27 positive fixtures, 128 negative sources, 20,280 assertions
gmake model-ir-parity    PASS (olmoe) — 15 compared rows, type census f32 81 / q4_K 97 / q6_K 17,
                         coverage 195 of 195 over 1,058 blocks, bytes_read 2,097,152
                         PASS (qwen2) — 14 compared rows, coverage 339 of 339 over 58 blocks
```

Both parity runs point `ALIGN_LLM_LLAMA_CLI` at the Homebrew `llama-cli`, the recorded reference
build `0.2.0 (build 10566, commit bb4caa754)`. The runner's `ulimit -f` is now 262,144 blocks
(256 MiB) rather than 8,192: it bounds every file the reference writes, and on a Metal host that
includes `llama-cli`'s 12-35 MB shader pipeline cache, which killed the reference with SIGXFSZ on any
cold-cache run under the old 8 MiB cap (ledger section 6 item 9). `gmake build`,
`gmake expert-trace-smoke`, `gmake gate-topology-check`, and `gmake format-check` also PASS after
the rebase; `gmake fmt` leaves no diff and `git diff --check` is clean.

**Observation, not a claim.** The real model produces 1,024 non-contiguous `ExpertBlock`s. That is
recorded as an input to R3's residency simulation, not as a performance result; this capability
makes no timing claim.

**Next actions, in order.** (1) `python3 scripts/pre-pr --owner-test olmoe-model-ir -- gmake
model-ir-smoke alignpack-smoke`, then publish and merge. (2) Rebase the two design-stage branches
below onto the merged result and implement them in roadmap order. (3) R2b's corpus-wide
stratification, which the merged locality gate's corpus and aggregator are the input to.

## Design in progress

Two local branches stack on this capability's implementation commit; neither is pushed:

- `agent/moe-prereq-discharge` — the MoE prerequisite discharge ledger **and its implementation**.
  It discharges the per-expert half of R4 and R4.5 on the real olmoe model: the container's 1,024
  `ExpertBlock`s go 42,394,624 → 1,000,000 ppm, and the spike computes real expert claims — all
  three members of the first `ExpertBlock` and member 0 of the last, the latter a `slice_index
  63/64` plane — every one `EXTERNAL` and bit-identical to the same plane read from the GGUF. The
  claim form required `schema_version: 2`, step 7a/7b, and the new `R4_5_SLICE` code; R4's
  hotness/prefetch groups and R4.5's GPU expert arm stay deferred. **Review:** one comprehensive
  reviewer of the whole diff at the pre-rebase implementation head `ee041a7` — verdict *approve*,
  8 findings (4 minor, 2 low, 2 nit), **all 8 accepted**, none rejected, all repaired in the single
  follow-up commit on that branch.
- `agent/r3-residency-sim` at `198850b` — the R3 residency simulator ledger, design only.

Both must be rebased onto the merged R1C before publication or further implementation.

## Pending decisions (2026-08-28)

**Decision (a) taken 2026-08-28.** `OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf` (allenai;
4,213,512,192 B; sha256 `4ddc0e53159ed512b8dd67914a66e27bc618f694672ba43a9a0454eabd9c684f`; arch
`olmoe`; 16 layers, 64 experts, top-8 routing; types F32/Q4_K/Q6_K) is downloaded to the local
models directory (path withheld from this file by convention). Disk free is now ~16 GiB on this
host. **Decision (b) is now infeasible on this host**: `gpt-oss-20b-mxfp4.gguf` at 12.1 GB no
longer fits alongside the downloaded model and its alignpack space; R1B's real-model
`model-ir-parity` qualification stays open pending a host with more free disk. Decisions (c) and
(d) below are unchanged and still pending.

1. **Small MoE GGUF, 1-4 GB. — TAKEN.** `OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf` (3.9 GiB) is on
   this host. It unblocked the R2 locality gate, which is measured, met, and merged (PR #131), and
   R1C's `olmoe` frontend, which is in publication above. R3's residency simulation and R4's
   per-expert half and R4.5's expert matmul follow from the merged R1C rather than from another
   download.
2. **`gpt-oss-20b-mxfp4.gguf`, 12.1 GB.** Unblocks R1B's real-model `model-ir-parity` qualification
   and every `ASSUMED` row of `docs/specs/r1b-gptoss-moe-ir.md` section 2.5 — including the two
   rows R1C has now contradicted from the olmoe side. **Infeasible on this host** after decision 1
   (disk free ~16 GiB); it stays open pending a host with more free disk.
3. **Build llama.cpp from source at `bb4caa754`** and apply the R2c minimal instrument patch (decode-
   step graphs, untruncated `ffn_moe_topk`). Neither `llama-eval-callback` nor
   `llama-debug --save-logits` can observe a KV cache beyond a handful of positions, so this unblocks
   R6 (Persistent KV) and, through it, R7-R9. It is also what would extend the merged locality gate
   past prefill. Cost: a clone plus a cmake build, a new from-source external dependency, and a
   qualification reproducible only on hosts that repeat the build.
4. **Align Request 41** (non-`Copy` capture in `spawn` closures), Align-side. Unblocks R5's required
   microbenchmark C.

**Align capability requests.** Requests 1-20 CLOSED, Requests 21-43 PROPOSED and non-blocking; none
has merged since R0; `.align-revision` stays pinned to `4b515f8d`. Top clients by reference count in
`docs/align-requests.md` (grep-verified against the register): Request 34 (`Result` payloads beyond
scalars, 9 mentions), Requests 21 and 23 (read-only open; huge-struct-copy lint, 7 each — Request 23
gained R1C's evidence block, making `src/frontend_olmoe.align` its fifth client and the third
architecture frontend to trip it), and Requests 33 and 32 (aligned allocation; FFI by-value structs,
6 each); Requests 32, 33, and 37 are also R5's own named clients.

**R2-LOCALITY-GATE merged checkpoint (PR #131, head `fff5806`, merge `546b5cc`).** The R2 gate is
**met in the prefill direction**. `scripts/run-expert-locality-gate` over
`eval/prompts/expert-locality-v1.txt` (40 prompts, all ≤ 6 tokens, md5
`d7fff23f5a1d4f6237e6f848f3318d8b`), one invocation per prompt, 51.8 s:

```text
verdict=LOCALITY prompts=40 layers=15 layers_clearing=15 pairs=2280 hits=3924 trials=13680
p0_per_mille=125 p_hat_per_mille=286 wilson_lo_per_mille=279 wilson_hi_per_mille=294 clusters=40
deff_per_mille=10460 cluster_lo_per_mille=262 cluster_hi_per_mille=311 ratio_per_mille=2288
entropy_per_mille=992 top8_mass_per_mille=180 truncated_documents=0 token_reduced_documents=40
token_reduced_layers=15
```

Adjacent-token expert reuse is 286 per mille against a 125 per mille null (`k/n` = 8/64), 2.29× the
null against a 1.5× materiality threshold, with all 15 contributing layers clearing the null on
their own stratum. The verdict is judged on the cluster-robust interval `[262, 311]` (design effect
10.460 over 40 prompt clusters), not the naive Wilson `[279, 294]`. The router histogram is nearly
uniform (entropy 992 per mille, all 64 experts used), so the effect is conditional structure rather
than popularity. Working sets grow sublinearly: 10.278 experts over two consecutive tokens where
independence predicts 11.437, 16.495 over four where it predicts 20.830. **Prefill only** — build
10566 evaluates one graph per invocation, `phase_split.decode` is `null`, and nothing there licenses
a decode or cache-policy claim. R2's contingency to shrink repo-expert-profile investment does
**not** fire; R3 has a measured demand signal. The same capability discharged R2A's `MOE-PREREQ`
cells (`expert trace parity (MoE): PASS` over 934 callback blocks) and added correction 20: build
10566 applies the output-token `GET_ROWS` reduction before the last layer's feed-forward, so a
*token-reduced* highest-index layer is parsed and validated but contributes no `selections[]` row
and is listed in the additive `moe.token_reduced_layers` field (`schema_version` stays 1). Full
numbers and every caveat: `docs/specs/r2a-expert-trace.md` section 8.

**R5C merged checkpoint.** Metal microbenchmark A, unified memory: self-reference `IDENTICAL` 479 of
479 nodes over 30 graphs; logits `WITHIN`, max `|Δ|` 2,936 of 6,000 ten-thousandths against R5B's
byte-identical CPU vector, `argmax` 671, top ten identical in order; bit-deterministic across paired
runs (`b6e473e8…` on both passes); transfer 59 wraps at ~12.4 ms each (732 ms total, both passes);
end-to-end wall ratio 0.99×/1.05×/1.31× across three paired runs, recorded **unresolved** rather than
claimed — the spread is `pread`'s. Correction C21 found and repaired a real cross-architecture NaN
sign-bit/payload difference (arm64's default NaN vs. x86-64 SSE's QNaN) surfacing only in the forced
non-finite-readback goldens, masked in golden normalization alone. Full ledger:
`docs/specs/r5c-metal-prefill.md`.

**Resume in another environment.** Fetch `origin`, check out `main`, then check out
`agent/r1c-olmoe-moe-ir` and read `docs/specs/r1c-olmoe-moe-ir.md` in full before touching `src/`.
Decision 1 is taken, R2's gate is measured and merged, and the work it still gates (R3, R4's
per-expert half, R4.5's expert matmul) waits on the merged R1C frontend rather than on another
decision. For the rest: decision 2 -> R1B's `model-ir-parity` qualification (section R1);
decision 3 -> R6 (section R6), R7-R9, and the decode half of R2's gate; decision 4 -> R5's deferred
microbenchmark C (section R5).

**DinD preflight note.** The installed profile requires true Docker-in-Docker on macOS. The recipe
lives in this session's memory, not in the repository, and the scripts that ran it lived only in a
scratchpad and were never committed. Rebuild them from `docs/development-preflight.md` if that file
exists by the time work resumes; otherwise rebuild from the CLAUDE.md rules (the repository wrapper,
`scripts/pre-pr`, and the workflow classifier table) rather than relying on a cached copy.

## Merged checkpoints

Track B, dense local model (R0 → R5C), plus the merged R2 locality gate. The R2 and R5C
checkpoints are above; the rest, newest first:

- **R5B-MODEL-PREFILL-FORWARD** (PR #128, head `3470646`, merge `870bf31`): a whole 28-layer Qwen2
  CPU prefill computed over one Align-owned alignpack window, final logits byte-identical to
  `llama-debug --save-logits`. Ledger: `docs/specs/r5b-model-prefill-forward.md`.
- **R5A-DENSE-LAYER-FORWARD** (PR #127, head `0397228`, merge `ccbd8ae`): one Qwen2 dense layer
  computed by ggml over Align-owned weight windows, bit-exact self-reference oracle. Ledger:
  `docs/specs/r5a-dense-layer-forward.md`.
- **R4.5-EXTERNAL-BUFFER-SPIKE** (PR #126, head `d46fce6`, merge `fa567b1`): a ggml matmul over an
  Align-owned quantized DRAM buffer with no silent copy; dense-block gate achieved, expert-block half
  was `MOE-PREREQ`, now unblocked by decision (a) above. Ledger: `docs/specs/r4-5-external-buffer.md`.
- **R4-ALIGNPACK-LAYER-MAJOR** (PR #125, head `a7e72dc`, merge `991eab1`): the alignpack v1
  container, its layer-major layout, and its verifier. Ledger: `docs/specs/r4-alignpack-layer-major.md`.
- **R2A-EXPERT-TRACE-CAPTURE** (PR #124, head `ab5f7d8`, merge `b8e1cb6`): `--expert-trace` CLI
  producing an `R2_ACTIVATION_TRACE` document from a `llama-eval-callback` transcript. Ledger:
  `docs/specs/r2a-expert-trace.md`.
- **R1B-GPTOSS-MOE-IR** (PR #123, head `3bf5c9c`, merge `d8d4ef6`): gpt-oss MoE frontend and
  per-expert Block IR, `R1_MODEL_IR schema_version: 2`; the gpt-oss `model-ir-parity` qualification
  stays open — decision (b) above records it infeasible on this host. Ledger:
  `docs/specs/r1b-gptoss-moe-ir.md`.
- **R1-QWEN-MODEL-IR** (PR #122, head `85a3a97`, merge `08492dc`): Qwen2 Model IR and Block IR,
  `--model-ir`, parity `PASS` against the local Qwen2.5-Coder-7B model. Ledger:
  `docs/specs/r1-qwen-model-ir.md`.
- **R0-GGUF-INSPECT** (PR #121, head `dcd8801`, merge `6640dcf`): read-only `--inspect-gguf`
  inspection, parity `PASS`. Ledger: `docs/specs/r0-gguf-inspection.md`.
- **C8-SPEED-FIRST closed** (final capability PR #120, head `fd78482`, merge `92c0979`): nine
  consumer-complete capabilities, gate met; the ppm-floor rule is the one promoted retrospective
  lesson. Ledger: `docs/specs/c8-speed-first.md`.

Earlier checkpoints, kept for continuity; full evidence lives in the named specs and in git history
at the cited commits:

- **REQUEST20-PIN** (PR #107, head `e1351f8`, merge `eb61086`): adopted Align's macOS owned-JSON CI
  repair; `ALIGN_LLM_VERIFIED` at the selected pin.
- **ADAPTER-ZOMBIE** (PR #106, head `ba02f25`, merge `0a8b9cf`): repaired a zombie/thread-group-leader
  containment-scan defect across six process-containment scanners.
- **C7-P** (PR #105, head `c86ce1e`, merge `a4f8663`): `aarch64-apple-darwin` and
  `aarch64-unknown-linux-gnu` platform profiles for C7 evidence, both discharged.
- **C7-PERSISTED-RESULT** (PR #104, head `e14ba33`, merge `a52b9ac`): `persisted_result.align`
  bounded-bucket-v1 CLI (`persist_file`/`verify_file`) and the Request 9 owned-record adoption
  checkpoint. Ledger: `docs/specs/c7-persisted-result.md`.
- **C6-MEASURED** (PR #103, head `d7f1ff6`, merge `c9a510d`): C6e/C6g1/C6g2 provider proposal and
  measured acceptance gate, `make prompt-gate-check` PASS. Ledger:
  `docs/specs/c6-prompt-context-optimizer.md`.
