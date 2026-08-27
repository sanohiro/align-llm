# Session handoff

Read `CLAUDE.md` first. GitHub owns transient pull-request checks, reviews, and attestations; this
file records durable project state.

## Active: R2-LOCALITY-GATE (2026-08-28)

Branch `agent/r2-locality-gate`, based on `main` `d5280ab`. **Decision 1 below has been taken**, and
this capability is the first thing it unblocked.

**The model.** `~/models/OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf`, 4,213,512,192 bytes, sha256
`4ddc0e53159ed512b8dd67914a66e27bc618f694672ba43a9a0454eabd9c684f`. Architecture `olmoe`, 16 layers,
`n_expert` 64, `n_expert_used` 8. It is **not** `qwen2` and **not** `gpt-oss`, so R3's real
measurement needs an R1C frontend for `olmoe` exactly as decision 1 predicted; that work is
**active in parallel** on branch `agent/r1c-olmoe-moe-ir` and is not part of this capability.

**The R2 gate is met, in the prefill direction.** `scripts/run-expert-locality-gate` over
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
null against a 1.5× materiality threshold, and all 15 contributing layers clear the null on their
own stratum. The trials are clustered by prompt, so the verdict is judged on the cluster-robust
interval `[262, 311]` (design effect 10.460 over 40 prompt clusters), not on the naive Wilson
`[279, 294]`. The router histogram is nearly uniform (entropy 992 per mille of uniform, all 64
experts used), so the effect is conditional structure rather than popularity.
Working sets grow sublinearly: 10.278 experts over two consecutive tokens where independence
predicts 11.437, 16.495 over four where it predicts 20.830. **Prefill only** — build 10566 evaluates
one graph per invocation, `phase_split.decode` is `null`, and nothing here licenses a decode or
cache-policy claim. Full numbers and every caveat: `docs/specs/r2a-expert-trace.md` section 8.
R2's "局所性が弱ければ投資を縮小する" contingency does **not** fire; R3 has a measured demand signal.

**R2A's MOE-PREREQ cells are discharged.** `scripts/run-expert-trace-parity` prints
`expert trace parity (MoE): PASS` on the real model, cross-checked field for field against its own
independent Python parse of all 934 callback blocks. That run also found one real contract error:
build 10566 applies the output-token `GET_ROWS` reduction **before the last layer's feed-forward**,
so `ffn_moe_topk-15` carries a shorter token axis than `embd` and the parser refused every real MoE
transcript with `R2_TOKEN_COUNT`. Repaired as correction 20 — such a block is *token-reduced*, is
parsed and validated but contributes no `selections[]` row, and its layer is listed in the new
additive `moe.token_reduced_layers` field (`schema_version` stays 1). The exemption is bounded to
the reduction the instrument performs: at most one layer per graph, and it must be the graph's
highest layer index; an interior short axis stays `R2_TOKEN_COUNT`.

**Committed on the branch.** Nothing in this capability is uncommitted: commit `19d91d1` carries
`src/expert_trace.align`, `scripts/eval_callback_fixture.py`, `scripts/run-expert-trace-smoke`,
`scripts/run-expert-trace-parity`, the new `scripts/run-expert-locality-gate`,
`scripts/expert_locality_gate.py`, `eval/prompts/expert-locality-v1.txt`, and the four documents
updated with the result; the review repair below is the second commit. No `Makefile` change: the
gate joins no aggregate, so the classifier stays in hosted scope.

**Review.** One comprehensive reviewer at `19d91d1` returned 1 major and 5 minor findings, all
accepted and all repaired in the follow-up commit: (1) the `locality-gate-aggregator` unit was
vacuous against the verdict rule — its two corpora failed or passed both halves at once, and six
mutations of the rule survived it; (2) the gate never read `moe.token_reduced_layers` or
`truncated_documents`; (3) the token-reduced exemption was broader than the instrument that
motivates it, silently accepting an interior reduced layer; (4) the Wilson interval ignored
(prompt, layer) clustering; (5) the truncation bias-direction claim was only half rigorous; (6) this
file's "everything uncommitted" paragraph was false. The repair adds five hand-built aggregator
cases that decide each half of the rule separately (all six mutants now fail), pools and prints both
omission fields, restricts the exemption to the graph's highest layer index with a new
`token-reduced-middle` refusal fixture, reports a cluster-robust interval and judges the verdict on
its lower bound, and states only the `t`-side half of the bias claim.

**Verification.** `gmake expert-trace-smoke` PASS (98 fixtures, up from 95; three added for
correction 20; the `locality-gate-aggregator` case owns the statistics with no model). `gmake check`
PASS. `gmake fmt` no diff. `git diff --check` clean. `scripts/run-expert-trace-parity` MoE half
PASS. `scripts/run-expert-locality-gate` MEASURED / LOCALITY, rerun after the repair.

**Next actions, in order.** (1) `python3 scripts/pre-pr` and publish. (2) R2b — the corpus-wide
stratification section R2 still names (language別 / task別 / repo別偏り), which this corpus and this
aggregator are the input to. (3) R3's residency simulation, once R1C lands an `olmoe` frontend.
R2c's decode measurement stays blocked on decision 3.

## Pending decisions (2026-08-28)

R5C-METAL-PREFILL-ARM merged as align-llm PR #129 (head `c025ee2`, merge `39c69a2` on `main`).
Track B progress R0 → R5C is now complete on the dense local model. **No roadmap item is startable
without a user decision or an Align-side change.** The decision list, consolidated (previously
tracked across the now-merged R5C section; this supersedes it):

1. **Small MoE GGUF, 1-4 GB. — TAKEN.** `OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf` (3.9 GiB) is on
   this host; see the active section above. The R2 locality gate is measured and met. Still open
   behind it: R3's residency simulation and R4's per-expert half and R4.5's expert matmul, which
   need an R1C `olmoe` frontend (active in parallel on `agent/r1c-olmoe-moe-ir`) rather than another
   download.
2. **`gpt-oss-20b-mxfp4.gguf`, 12.1 GB.** Unblocks R1B's real-model `model-ir-parity` qualification
   and every `ASSUMED` row of `docs/specs/r1b-gptoss-moe-ir.md` section 2.5. Disk: roughly 24 GB with
   its pack against ~26 GB free — tight enough that it should not be decided alongside decision 1
   without rechecking free space first.
3. **Build llama.cpp from source at `bb4caa754`** and apply the R2c minimal instrument patch (decode-
   step graphs, untruncated `ffn_moe_topk`). Neither `llama-eval-callback` nor
   `llama-debug --save-logits` can observe a KV cache beyond a handful of positions, so this unblocks
   R6 (Persistent KV) and, through it, R7-R9. Cost: a clone plus a cmake build, a new from-source
   external dependency, and a qualification reproducible only on hosts that repeat the build.
4. **Align Request 41** (non-`Copy` capture in `spawn` closures), Align-side. Unblocks R5's required
   microbenchmark C.

**Align capability requests.** Requests 1-20 CLOSED, Requests 21-43 PROPOSED and non-blocking; none
has merged since R0; `.align-revision` stays pinned to `4b515f8d`. Top clients by reference count in
`docs/align-requests.md` (grep-verified against the register): Request 34 (`Result` payloads beyond
scalars, 9 mentions), Request 21 (read-only open, 7), Requests 33 and 32 (aligned allocation; FFI
by-value structs, 6 each) and Request 23 (huge-struct-copy lint, 5); Requests 32, 33, and 37 are also
R5's own named clients.

**R5C merged checkpoint.** Metal microbenchmark A, unified memory: self-reference `IDENTICAL` 479 of
479 nodes over 30 graphs; logits `WITHIN`, max `|Δ|` 2,936 of 6,000 ten-thousandths against R5B's
byte-identical CPU vector, `argmax` 671, top ten identical in order; bit-deterministic across paired
runs (`b6e473e8…` on both passes); transfer 59 wraps at ~12.4 ms each (732 ms total, both passes);
end-to-end wall ratio 0.99×/1.05×/1.31× across three paired runs, recorded **unresolved** rather than
claimed — the spread is `pread`'s. Correction C21 found and repaired a real cross-architecture NaN
sign-bit/payload difference (arm64's default NaN vs. x86-64 SSE's QNaN) surfacing only in the forced
non-finite-readback goldens, masked in golden normalization alone. Full ledger:
`docs/specs/r5c-metal-prefill.md`.

**Resume in another environment.** Fetch `origin`, check out `main`, and read this section. Decision
1 is taken and R2 is measured; the work it still gates (R3, R4's per-expert half, R4.5's expert
matmul) waits on R1C's `olmoe` frontend, not on another decision. For the rest: decision 2 → R1B's
`model-ir-parity` qualification (section R1); decision 3 → R6 (section R6) and, through it, R7-R9;
decision 4 → R5's deferred microbenchmark C (section R5). With no decision made, no roadmap item is
startable; do not invent a workaround for any of the four.

**DinD preflight note.** The installed profile requires true Docker-in-Docker on macOS. The recipe
lives in this session's memory, not in the repository, and the scripts that ran it lived only in a
scratchpad and were never committed. Rebuild them from `docs/development-preflight.md` if that file
exists by the time work resumes; otherwise rebuild from the CLAUDE.md rules (the repository wrapper,
`scripts/pre-pr`, and the workflow classifier table) rather than relying on a cached copy.

## Merged checkpoints

Track B, dense local model (R0 → R5C). R5C's checkpoint is above; the rest, newest first:

- **R5B-MODEL-PREFILL-FORWARD** (PR #128, head `3470646`, merge `870bf31`): a whole 28-layer Qwen2
  CPU prefill computed over one Align-owned alignpack window, final logits byte-identical to
  `llama-debug --save-logits`. Ledger: `docs/specs/r5b-model-prefill-forward.md`.
- **R5A-DENSE-LAYER-FORWARD** (PR #127, head `0397228`, merge `ccbd8ae`): one Qwen2 dense layer
  computed by ggml over Align-owned weight windows, bit-exact self-reference oracle. Ledger:
  `docs/specs/r5a-dense-layer-forward.md`.
- **R4.5-EXTERNAL-BUFFER-SPIKE** (PR #126, head `d46fce6`, merge `fa567b1`): a ggml matmul over an
  Align-owned quantized DRAM buffer with no silent copy; dense-block gate achieved, expert-block half
  deferred on the small-MoE-GGUF decision above. Ledger: `docs/specs/r4-5-external-buffer.md`.
- **R4-ALIGNPACK-LAYER-MAJOR** (PR #125, head `a7e72dc`, merge `991eab1`): the alignpack v1
  container, its layer-major layout, and its verifier. Ledger: `docs/specs/r4-alignpack-layer-major.md`.
- **R2A-EXPERT-TRACE-CAPTURE** (PR #124, head `ab5f7d8`, merge `b8e1cb6`): `--expert-trace` CLI
  producing an `R2_ACTIVATION_TRACE` document from a `llama-eval-callback` transcript. Ledger:
  `docs/specs/r2a-expert-trace.md`.
- **R1B-GPTOSS-MOE-IR** (PR #123, head `3bf5c9c`, merge `d8d4ef6`): gpt-oss MoE frontend and
  per-expert Block IR, `R1_MODEL_IR schema_version: 2`; the gpt-oss `model-ir-parity` qualification
  stays open pending the model download (decision 2 above). Ledger: `docs/specs/r1b-gptoss-moe-ir.md`.
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
