# Session handoff

Read `CLAUDE.md` first. GitHub owns transient pull-request checks, reviews, and attestations; this
file records durable project state.

## No active capability (2026-08-28)

R5C-METAL-PREFILL-ARM merged as align-llm PR #129 (head `c025ee2`, merge `39c69a2` on `main`).
Track B progress R0 → R5C is now complete on the dense local model. **No roadmap item is startable
without a user decision or an Align-side change.** The decision list, consolidated (previously
tracked across the now-merged R5C section; this supersedes it):

1. **Small MoE GGUF, 1-4 GB.** Unblocks the R2 locality gate, R3's residency simulation, R4's
   per-expert half, and R4.5's expert matmul. A model chosen for size is unlikely to be `gpt-oss`
   architecture, so R3's real measurement also needs a new R1C frontend for whatever architecture it
   turns out to be — not just the download. Disk: the model plus roughly equal alignpack space,
   against ~26 GB free on this host.
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

**Resume in another environment.** Fetch `origin`, check out `main`, and read this section. Pick one
pending decision, then start the capability it unblocks: decision 1 → R2 (`docs/specs/roadmap.md`
section R2), R3 (section R3), R4's per-expert half (section R4), and R4.5's expert matmul (section
R4.5), plus a new R1C frontend if the chosen model is not `qwen2`/`gpt-oss`; decision 2 → R1B's
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
