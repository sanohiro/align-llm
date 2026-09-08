# G1 Align readiness audit — 2026-09-08

This is one consolidated handoff for the remaining G1 compiler dependencies, requested before
further Align interruptions. It does not ship a compiler fix or claim GPU qualification.

The main Request 62 failure is a new G1 consumer of Request 49's existing foreign mutable-borrow
limitation. Requests 42 and 43 cover the adjacent checking-parity and independent-output failures.
Treat these as one investigation and delivery batch, with distinct regression rows, rather than
four consecutive requests to interrupt Align's normal development. Keep the historical numbers
and acceptance owners; do not claim that one inferred cause has already been proven for every row.

## Scope and evidence identity

- Align source: `3fbb74fe7c351e526c997bd4c70bd00cf1a424a0` (PR #982), managed release compiler
  and runtime, also the inspected sibling HEAD.
- Compiler SHA-256: `fa8455b1bc6f47de356845d38fa66d5ab884651f9c8909a66fe4ac20f5d15a88`.
- Application source: G1 checkpoint `1ee45be` and the complete source hashes in the companion
  bundle's `manifest.json`. The source snapshot includes nested resource Drop-hook modules.
- Host: native Apple Silicon macOS. No models, GPU hardware, network providers or credentials
  are needed to run the compiler probes. Native generation acceptance uses the existing GPU stub.
- 21 cases were each run through `check`, `check-per-unit` and ordinary `build`: 63 command results.
  Six admitted execution probes also ran successfully. Every case ran despite earlier failures.
- The audit covers production observation, all six numeric frame kinds, diagnostic pointer capture
  and readback, CPU/GPU generation imports, owned case results, JSON case inputs, mutable state,
  errors and lifetime negatives. It does not implement the final diagnostic traversal or qualifier.

The companion `g1-align-readiness-20260908.tar.gz` contains self-contained case directories, exact
application source snapshots, `run.py`, native fixture/stub sources, complete baseline logs and a
retirement-order proof. Audit-only generation variants are explicitly marked; production source
and `.align-revision` were not changed by this audit. Negative probes are never executed as ordinary
native programs.

## Consolidated findings

| Class | Evidence | Existing request and impact | Required repair property |
| --- | --- | --- | --- |
| A. Foreign non-retaining calls reject local payloads | Cases 02, 04, 19, 21 pass whole-program checking, fail per-unit checking and build. 04 uses the exact native codec; 19/21 use the actual Qwen/OLMoE generation module with observation hooks. | 49 / 62; **blocks G1 observed production and diagnostic output**. | Preserve precise non-retention across imported helpers; local scalar/routing payloads may be written synchronously through caller-owned stream state. |
| B. Foreign independent record outputs lose validity | Case 05 is the recorded 42/43 fixture. Whole-program accepts it; per-unit/build reject the later schedule read. Case 18's independent buffer/counter pair passes. | 42 / 43 / 49; same compiler investigation, distinct output regression. | Preserve separate output ownership and generations; replacing one output must not invalidate another independently filled output. Do not infer that all mutable-output shapes fail. |
| C. Byte-view mutation through a helper invalidates the complete owner | Case 06 rejects in all three modes; the identical inline mutation in 07 passes. | 62 precision subcase; **non-blocking for the current codec**, whose header helper borrows its complete stream. | A derived-view mutation must not retire the buffer owner or disjoint optional writer; real source replacement must still invalidate old views. |
| D. A copied scalar operand aliases its mutable owner | Case 11 rejects in every mode; explicitly snapshotting the scalar in 12 passes and runs. | 48; **non-blocking for G1's current explicit scalar snapshots**. | Preserve eager scalar-value semantics without admitting actual overlapping mutable borrows. Include in the batch assessment; do not mislabel it as another missing writer API. |
| E. Actual shorter-lived retained views can escape | Case 08 stores a local buffer view through a borrowed record and reads it after return. All modes accept it. Its MIR drops the local buffer before return. Imported twin 09 is accepted by whole-program checking but rejected by per-unit/build. | 62's required lifetime-negative acceptance, also relevant to 42's checking agreement; **safety defect**, not a desired widening. | Reject the actual escape consistently while admitting A. Exporting a permissive summary or merely suppressing the lifetime diagnostic is insufficient. |

A and B were already identified as related investigation work in Align's
`docs/impl/align-llm-request-audit-2026-09-07.md`. Recording 62 without connecting that history caused
avoidable fragmentation. E is newly evidenced by this batch's negative controls. The exact
compiler repair boundaries remain Align-owned; these are observed behavior classes, not a claim
that five unrelated implementation patches are necessary.

### Lifetime-negative proof for E

Case 08 is deliberately small:

```align
Holder { view: slice<u8> }
fn retain(borrow mut owner: Holder, borrow bytes: slice<u8>) { owner.view = bytes }
fn caller(borrow mut owner: Holder) {
  mut data := buffer(1)
  data.put_u8(65)
  bytes := data.bytes()
  retain(owner, bytes)
}
fn main() {
  mut backing := buffer(1)
  backing.put_u8(0)
  mut owner := Holder { view: backing.bytes() }
  caller(owner)
  print(owner.view.u8(0))
}
```

The emitted MIR calls `retain`, drops `data`, then returns from `caller`. Shipped runtime
`align_rt_buffer_bytes` returns a borrowing view; `align_rt_buffer_free` drops its allocation.
The diagnostic proof redirects only the emitted buffer-free symbol to a test shim that poisons
retired bytes with 221 and keeps their allocation alive. The caller prints **221**, with two
one-byte retirements logged, rather than the stored byte 65. This demonstrates a post-retirement
read without executing a real use-after-free. It does not alter the production compiler/runtime,
claim allocator-dependent output, or provide an application workaround. `prove-retention.py`
reconstructs the proof; Align should add its own normal rejection and ownership regression.

## Complete baseline

`A` means accepted (exit 0), `R` means rejected with compiler diagnostics (exit 1). Neither means
correct without the expected column. No final case timed out or failed because of missing tools.

| Case | Expected | check | per-unit | build | Native evidence / interpretation |
| --- | --- | --- | --- | --- | --- |
| 01 shipped stream | A | A | A | A | PASS; independent 160-byte golden and existing state/failure owner |
| 02 imported local payload | A | A | R | R | A; two writes through a caller-owned stream |
| 03 same-module payload control | A | A | A | A | PASS; exact `AA` output and retained counter |
| 04 actual codec, all six kinds | A | A | R | R | A; native golden validation is ready to run after acceptance |
| 05 independent record outputs | A | A | R | R | B; historical 42/43 reproduction |
| 06 derived-view helper | A | R | R | R | C |
| 07 inline-view control | A | A | A | A | Same mutation, no helper boundary |
| 08 actual local-view retention | R | A | A | A | E; MIR and controlled retirement proof |
| 09 imported retention twin | R | A | R | R | E; modes disagree on a real escape |
| 10 owner replacement | R | R | R | R | Correct existing negative |
| 11 same-call scalar snapshot | A | R | R | R | D |
| 12 explicit scalar control | A | A | A | A | PASS |
| 13 owned case-result return | A | A | A | A | PASS; borrowed inspection, bounded JSON and error return |
| 14 case-input decode | A | A | A | A | PASS; owned name, integer arrays, optional seed |
| 15 GPU payload readback | A | A | A | A | Existing `slot_get` boundary; no GPU execution in this probe |
| 16 diagnostic slot capture | A | A | A | A | Existing output-mark and slot-copy boundary; compile/link only |
| 17 real GPU generation import | A | A | A | A | Actual unobserved module graph; compile/link only |
| 18 buffer/counter peers | A | A | A | A | PASS; a passing mutable-output control |
| 19 real observed generation hooks | A | A | R | R | A; four Qwen/OLMoE production-logit call sites |
| 20 real CPU reference imports | A | A | A | A | Actual dense and routed generation modules; compile/link only |
| 21 observed GPU native owner | A | A | R | R | A; ready to run prefill/decode, framing and 65,576-byte reservation checks after acceptance |

The six executed cases are 01, 03, 12, 13, 14 and 18. No runtime success is claimed for blocked
cases. Case 21 includes the complete existing generation smoke plus active/inactive observed
Qwen/OLMoE runs and an independent frame reader. Its hooks are audit fixtures, not a published
runtime entrypoint. The final case's diagnostic reproduction and forced-token trajectories remain
application integration work even if every compiler probe passes.

## Already available, application work, and limits

- Existing FFI provides output marking, retained slot copying and bounded scalar/I32 readback.
  G1 must add per-layer/router capture, tensor order/shape checks, generation reproduction and a
  distinct teacher-forced traversal. That is application work; no proposed tensor or GPU API is
  needed by the inspected call shapes. Runtime correctness of the new traversal is not yet tested.
- Existing owned result/JSON/array forms cover the tested case I/O shape. Final profile-bound
  parsing, dispatch and exact output records remain application work. This probe is not a new
  public case schema and does not prove every future JSON shape.
- Process deadlines, source/build isolation, stream pairing, kit assembly and evidence publication
  already have Python owners. This audit reran `gmake gpu-case-traversal gpu-case-sequence
  gpu-qualification-cli gpu-kit-assembly`: **PASS**. The final connecting CLI remains unfinished.
- Request 21's read-only random-access file constructor is a known separate limitation:
  `runtime_pack_identity.observe_path` and generation use `fs.open_rw`. The current path needs
  writable AlignPack files. A read-only model-cache deployment would make that request blocking;
  this audit does not claim it is fixed or add that filesystem API to the borrowing repair batch.
- Request 38's positional buffer operations are not a prerequisite for the inspected GPU readback:
  existing FFI writes into caller-owned views. Arbitrary Move-handle arrays, stored builders,
  asynchronous writer retention and arbitrary exclusive partial-field calls are not required by
  the selected G1 construction. Do not expand this batch into those separate language proposals.
- Real Metal/CUDA execution, final calibration/profile data, diagnostic graph retention costs,
  forced-trajectory correctness and native-host failures remain to be measured. This audit cannot
  rule out bugs visible only in those implementations or on unavailable hardware.

## One delivery batch and one client adoption

1. Align investigates A–E together against this frozen consumer set. Use one capability with
   coherent internal commits where the repair shares analysis/interface ownership. If a repair
   truly has a distinct failure domain, name that boundary; request numbers alone do not require
   separate PRs. Keep any additional findings within this bounded set in the same batch record.
2. During implementation, run the affected case subset. Before the one stable-candidate review
   and delivery, run the complete bundle with the candidate compiler/runtime. A successful
   minimal receiver example is not delivery evidence for imported callers. Record explicit
   dispositions for C/D if they remain non-blocking; do not relabel their red rows as passing.
3. The bundle reports both desired positive acceptance and required negative rejection. Add
   producer-owned whole/per-unit, imported cache cold/hit/edit/revert, malformed-summary and
   native ownership regressions for the repaired analysis. This is focused evidence for this
   repeated failure class, not a new permanent full-workspace gate.
4. Batch the merged prerequisite commits into one align-llm pin adoption. Run the real
   `gpu-numeric-stream` and observed `gpu-generation-smoke` owners once on the coherent candidate,
   then continue diagnostic/case/CLI integration. Ordinary unobserved smoke success does not
   discharge observed acceptance. No versioned Align release is requested solely for this audit.
5. Historical application refactoring named by Requests 43/49 remains required for those requests'
   eventual client closure; it is not silently added to G1's unblock command. No request is closed
   by this report, by compiler syntax admission alone, or by a pin bump alone.

The bounded retrospective action is the frozen real-consumer handoff, including the negative
lifetime controls and existing-request links. There is no new rule to interrupt Align for each
symptom, no speculative language compatibility layer, and no promise that unimplemented hardware
paths have been exhausted by compilation.
