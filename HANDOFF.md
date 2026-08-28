# Session handoff

Read `CLAUDE.md` first. GitHub owns transient pull-request checks, reviews, and attestations; this
file records durable project state.

## Active: R5E-MOE-MODEL-PREFILL (2026-08-28)

Branch `agent/r5e-moe-model-prefill`, based on the merged MOE-PREREQ-DISCHARGE (PR #133,
`2cdb7bf` -> `35a0df6`). The branch carries **both** R5D and R5E: `3cb8d59` and `e584849` are
R5D-MOE-LAYER-FORWARD's ledger and implementation, `5e3356d` and `053de09` are R5E's, and
`docs/specs/r5d-moe-layer-forward.md` and `docs/specs/r5e-moe-model-prefill.md` are authoritative
for their own halves.

**What R5E ships.** `ggml-spike --moe-model-forward` computes a whole sixteen-layer OLMoE prefill of
at most six tokens: per-layer routing, only the routed experts' planes read into one Align-owned
claim window reserved at the arithmetic union bound and reused across layers, the narrowing inside
layer fifteen where the instrument does, and the output head. On the downloaded model the logits are
byte-identical to `llama-debug --save-logits`, all four oracles pass (227 of 227 self-reference
nodes, 227 transcript nodes over 21,372 elements, routing identity across all sixteen layers,
`IDENTICAL` logits), and a six-token prefill reads **333,644 ppm** of the model's expert bytes.
`layer-forward-smoke` gains a fifth block; no Makefile check target and no aggregate membership
change.

**Review and repair.** Two complementary reviewers covered `053de09` on explicitly disjoint risks:
reviewer A returned no blocker with 1 medium and 4 low findings; reviewer B returned changes
requested with 3 medium, 3 low, and 2 info findings. **All were accepted and repaired in one
consolidated commit** on this branch. The repair adds the two window-budget probe fixtures, an
honest coverage denominator (32 of 36 declared `R5*` codes plus 5 inherited), `oracle.sums_expected`
/ `sums_matched`, the reference arm's non-aliasing assertion, a run-level `(layer, expert)` key set
behind `residency.keys_distinct`, a non-UTF-8 path refusal, three qualification-runner fixes, one
sweep-script assertion, and corrections C17-C22 in section 6 of the R5E ledger. It also **files
Align Requests 46 and 47** (see below), retracting section 5.5's "no new request is expected".

**Next actions, in order.** (1) `python3 scripts/pre-pr` and publish; this capability adds no
`HOSTED_CHECK_TARGETS` member and changes no check topology, so it stays in the ordinary classifier
lane, not `make ci`. (2) Rerun `make moe-model-forward-qualification` on the host holding the model
if the pack was removed; it needs >= 6 GB free under the scratch root.

**Align capability requests filed here.** Requests **46** (a `Borrow` argument must be a stable
named local or field) and **47** (same-call aliasing between a `borrow mut` owner and its own `Copy`
scalar field), both `PROPOSED`, both non-blocking, both with a mitigation R5E ships and a probe
verified at the pinned `4b515f8d`. They are numbered 46 and 47, not 44 and 45, because
`agent/r3-residency-sim` already holds 44 and 45 unmerged; the register carries a renumbering note
and nothing outside it cites either number.

## Design and implementation in progress elsewhere

**R3-RESIDENCY-SIM**, branch `agent/r3-residency-sim`, design ledger `docs/specs/r3-residency-sim.md`
committed at `198850b`. One comprehensive review is **approved**, nits repaired at `967aadf`.
**Gate MET**: `BEATS_BASELINE` at a 25% cache fraction — `recent_reuse_w32` reaches 26.03 GB
against LRU's 33.53 GB, a gain of 223‰, jackknife minimum 213‰. It still needs a rebase onto the
merged MOE-PREREQ-DISCHARGE (PR #133) before publication; that is its only remaining step. It also
carries **Requests 44 and 45** (`docs/align-requests.md`), both non-blocking: Request 44 is a
compiler-soundness report (moving a field out of a decoded record double-frees at run time, R3's
mitigation is a `str`-view clone); Request 45 is `borrow mut` array locals inside loops plus no
element assignment through an array field (R3's mitigation returns owned columns and writes loop
bodies inline). **Requests 44 and 45 exist only on `agent/r3-residency-sim`**, which has not merged;
this branch's register runs 1-43 plus the new 46 and 47, with the numbering note recorded above and
in `docs/align-requests.md`.

## R4B (hotness layout): evaluated, not started

Roadmap item 19's router-histogram measurement (R2-LOCALITY-GATE, below) is near-uniform —
entropy 992 per mille, all 64 experts used — under which a prefetch policy was judged **harmful
rather than beneficial**, so R4's expert-hotness ordering and prefetch-group layout were not
implemented. Recorded as a deferral. **Resume condition**: a decode corpus, or a stratified corpus
that shows real skew in expert popularity.

## Remaining decisions

- **(b) TAKEN as infeasible.** `gpt-oss-20b-mxfp4.gguf` (12.1 GB) does not fit alongside the
  downloaded OLMoE model and its alignpack space on this host (~16 GiB free). R1B's real-model
  `model-ir-parity` qualification stays open pending a host with more free disk.
- **(c) Pending.** Build llama.cpp from source at `bb4caa754` and apply the R2c minimal instrument
  patch (decode-step graphs, untruncated `ffn_moe_topk`, router scores). Unblocks R6 (Persistent
  KV) and, through it, R7-R9, and extends the merged locality gate past prefill.
- **(d) Pending.** Align Request 41 (non-`Copy` capture in `spawn` closures). Unblocks R5's
  required microbenchmark C.

**Align capability requests.** Requests 1-20 CLOSED, Requests 21-43 and the new 46-47 PROPOSED and
non-blocking on this branch's register; none has merged since R0; `.align-revision` stays pinned to
`4b515f8d`. Requests 44 and 45 exist only on `agent/r3-residency-sim` (see above).

## Roadmap order (`docs/specs/roadmap.md`)

Item 20 MOE-PREREQ-DISCHARGE — merged, PR #133. Item 21 R3-RESIDENCY-SIM — gate met, publication
in progress. Item 22 R5D-MOE-LAYER-FORWARD and item 23 R5E-MOE-MODEL-PREFILL — both committed on
this branch, review repaired, publication next.

## Merged checkpoints

Track B, dense local model (R0 → R5C), plus the merged R2 locality gate, R1C olmoe frontend, and
MOE-PREREQ-DISCHARGE. Newest first:

- **MOE-PREREQ-DISCHARGE** (PR #133, `2cdb7bf` → `35a0df6`): the per-expert half of R4/R4.5,
  measured on the real OLMoE model — 1,024 `ExpertBlock`s at 1,000,000 ppm, and real expert
  claims bit-identical to the source GGUF. Ledger: `docs/specs/moe-prereq-discharge.md`.
- **R1C-OLMOE-MOE-IR** (PR #132, merge `e15e3d3`): `src/frontend_olmoe.align`, the first Model
  IR/Block IR derived from a real MoE model, `model-ir-parity` PASS. Ledger:
  `docs/specs/r1c-olmoe-moe-ir.md`.
- **R2-LOCALITY-GATE** (PR #131, merge `546b5cc`): met in the prefill direction — `p_hat` 286‰
  against a 125‰ null (2.29×), cluster-robust interval `[262, 311]`‰ over 40 prompts; router
  histogram near-uniform (entropy 992‰). Ledger: `docs/specs/r2a-expert-trace.md` section 8.
- **R5C-METAL-PREFILL-ARM** (PR #129, merge `39c69a2`): required microbenchmark A discharged on
  unified memory; zero-copy transfer, bit-deterministic, `argmax` 671 matches CPU. Ledger:
  `docs/specs/r5c-metal-prefill.md`.
- **R5B-MODEL-PREFILL-FORWARD** (PR #128, merge `870bf31`): a whole 28-layer Qwen2 CPU prefill,
  final logits byte-identical to `llama-debug --save-logits`. Ledger:
  `docs/specs/r5b-model-prefill-forward.md`.
- **R5A-DENSE-LAYER-FORWARD** (PR #127, merge `ccbd8ae`): one Qwen2 dense layer, bit-exact
  self-reference oracle. Ledger: `docs/specs/r5a-dense-layer-forward.md`.
- **R4.5-EXTERNAL-BUFFER-SPIKE** (PR #126, merge `fa567b1`): a ggml matmul over an Align-owned
  quantized DRAM buffer with no silent copy. Ledger: `docs/specs/r4-5-external-buffer.md`.
- **R4-ALIGNPACK-LAYER-MAJOR** (PR #125, merge `991eab1`): the alignpack v1 container and
  verifier. Ledger: `docs/specs/r4-alignpack-layer-major.md`.
- **R2A-EXPERT-TRACE-CAPTURE** (PR #124, merge `b8e1cb6`): `--expert-trace` CLI, `R2_ACTIVATION_TRACE`.
  Ledger: `docs/specs/r2a-expert-trace.md`.
- **R1B-GPTOSS-MOE-IR** (PR #123, merge `d8d4ef6`): gpt-oss MoE frontend, `R1_MODEL_IR
  schema_version: 2`; real-model `model-ir-parity` stays open (decision b). Ledger:
  `docs/specs/r1b-gptoss-moe-ir.md`.
- **R1-QWEN-MODEL-IR** (PR #122, merge `08492dc`): Qwen2 Model IR and Block IR, parity PASS.
  Ledger: `docs/specs/r1-qwen-model-ir.md`.
- **R0-GGUF-INSPECT** (PR #121, merge `6640dcf`): read-only `--inspect-gguf`, parity PASS. Ledger:
  `docs/specs/r0-gguf-inspection.md`.
- **C8-SPEED-FIRST closed** (PR #120, merge `92c0979`): nine consumer-complete capabilities, gate
  met. Ledger: `docs/specs/c8-speed-first.md`.

Earlier checkpoints, kept for continuity; full evidence in the named specs and git history:

- **REQUEST20-PIN** (PR #107, merge `eb61086`): adopted Align's macOS owned-JSON CI repair.
- **ADAPTER-ZOMBIE** (PR #106, merge `0a8b9cf`): repaired a zombie/thread-group-leader
  containment-scan defect across six scanners.
- **C7-P** (PR #105, merge `a4f8663`): `aarch64-apple-darwin` and `aarch64-unknown-linux-gnu`
  platform profiles for C7.
- **C7-PERSISTED-RESULT** (PR #104, merge `a52b9ac`): `persisted_result.align` bounded-bucket-v1
  CLI. Ledger: `docs/specs/c7-persisted-result.md`.
- **C6-MEASURED** (PR #103, merge `c9a510d`): C6e/C6g1/C6g2 provider proposal and measured
  acceptance gate. Ledger: `docs/specs/c6-prompt-context-optimizer.md`.

## Resume in another environment

Fetch `origin`, check out `main`, then check out `agent/r5e-moe-model-prefill` and read
`docs/specs/r5e-moe-model-prefill.md` (and `docs/specs/r5d-moe-layer-forward.md` for the layer
half) in full before touching `src/` or either qualification runner. Decisions (a) and (b) are taken; R2's gate, R1C's frontend, and MOE-PREREQ-DISCHARGE are
merged. For the rest: decision (c) → R6 and the decode half of R2's gate; decision (d) → R5's
deferred microbenchmark C; R4B's resume condition → a decode or skewed-expert corpus.

**DinD preflight note.** The installed profile requires true Docker-in-Docker on macOS. The
recipe lives in session memory, not in the repository; rebuild it from
`docs/development-preflight.md` if that file exists by the time work resumes, otherwise from the
`CLAUDE.md` rules (the repository wrapper, `scripts/pre-pr`, and the workflow classifier table)
rather than relying on a cached copy.
