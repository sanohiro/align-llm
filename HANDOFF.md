# Session handoff

Read `CLAUDE.md` first. Architecture and ordering live in `docs/specs/`.

## Active capability: ALIGN-PRODUCT-CUTOVER

The user requested completion of normal-product Python removal on 2026-09-13.
Implementation remains authorized; GPU campaigns remain deferred. This is one
consumer capability, not a series of helper/adoption PRs.

Branch: `agent/align-product-cutover`; integration base `9855afe` includes
`origin/main` at `39b4cdc`. The existing staged/unstaged/untracked product work was
preserved. The separate Antigravity capability described below must stay separate.

The normal evaluator now runs entirely through the native Align graph, including
provider generation, FILE edits, validation supervision, repair, scoring, verified
publication, acceptance and rollback. The Python source-chunk bootstrap is gone.
`eval_retirement` refuses the eight historical implementations by supported literal
launch descriptor, reserved path and frozen digest, including renamed copies,
before any task/result. Ordinary external Python tests and native-tool data operands
remain permitted. Decoded task records remain owned across dispatch.

`.align-revision` selects merged Align PRs #1033/#1034 at
`f502fe3da00ce0b39c4eeec40586b11688627fbd`. Managed release compiler/runtime
materialization and `scripts/align-toolchain verify` PASS. Exact Linux ARM64 source
build and the macOS managed compiler both build the product. Use the repository
wrapper normally; explicit Linux compiler selection is qualification only.

R84/R85/R87/R88 positive adoption owners pass on macOS/Linux. R86's valid
initializer order and direct-record negative pass, but the optional move-after-use
negative still compiles and produces an empty digest. The reduced witness and
remaining acceptance are recorded under R86 in `docs/align-requests.md` and
`eval/fixtures/product-cutover-option-after-move.align`. Keep R86 ALIGN_MERGED,
Blocking:no. Product construction binds the digest before moving its measurement;
the consuming optional-initializer sweep found no matching unsafe product pattern.
Do not start another provider pin cycle or claim R86 fully verified.

## Durable verification

- `scripts/run-product-cutover-adoption-smoke`: source/per-unit admission, command
  None/reuse and source expiry, owned JSON expiry/bounds, valid record ordering,
  array-root/embedded parity, regular/readonly/empty/dot/symlink readers and immediate
  FIFO/device/directory refusal PASS on macOS/Linux. The optional negative above
  is a separately recorded residual, not a passing rejection test.
- `python3 scripts/run-align-product-cutover --functional --binary "$CUTOVER_BINARY"`:
  PASS on Linux ARM64 with the real-linked product. Includes ordinary Git/invalid
  corpus, retirement, eight paired native rows, occupied publication, invalid inputs,
  sixteen attempted repair records, source/baseline failure prefixes, real HTTP
  generation workers and the new inclusive-range coding-v2 corpus.
- `python3 scripts/run-align-product-cutover --no-python --binary "$CUTOVER_BINARY"
  --models "$CUTOVER_MODELS" --libraries "$CUTOVER_LIBRARIES" --shim "$CUTOVER_SHIM"`:
  PASS. Relocated normal and repair evaluation, actual HTTP workers, all eight
  renamed retired implementations, Git/index/test-selection/patch/verification,
  failure memory, proposal/accept/rollback and real three-token local inference.
  Python and repository scripts are absent from normal product namespaces; full
  descendant exec traces are inspected. Independent oracles remain outside them.
  A separate namespace proves one explicitly declared Python target test.
- `scripts/run-eval-retirement-smoke`, `scripts/run-eval-invalid-smoke`, and
  `eval/runners/run-fixed.sh`: PASS on macOS/Linux. The later ordinary spawn/test
  error-preservation delta has its final retirement owner PASS on both platforms.
- `python3 scripts/check-python-boundary --strict`: PASS, 270 Python files,
  83 embedded hosts, 157 product modules, zero frozen product debts. Eight unchanged
  historical implementations are independent replay oracles; 16 frozen command
  manifests are replay-only. `python3 scripts/test-python-boundary`: 30 cases PASS.
- `python3 scripts/run-prompt-gate-validator-smoke FAMILY`: validator,
  product-version, source-bundle and source-revalidation PASS on Linux.
- Prior coherent native owners for source/tree/workspace/command/capture/supervision,
  task input/attempt, generation, schema/render/score/verifier and state passed at
  the earlier managed checkpoint. Current A2/A4 execute the composed graph with
  the new pin; this is not a claim that every focused owner is in an aggregate.

A final pure policy extraction moved identical target-language/test-path detection
from `repo_index`/`patch_eval` to `source_file_kind`; this keeps strict data-only and
process modules distinct without changing the checker. Its per-unit check PASS;
final product rebuild plus index/selection/patch golden owners are running. The
prior A4 result precedes only this pure extraction; final candidate evidence must
name the current product. `make fmt` and diff check have passed.

## Next actions

1. Finish the current macOS/Linux product rebuild and affected index/selection/patch
   owners; retain their useful logs. Run the existing runtime-provider owner for A6.
2. Finish `python3 scripts/run-align-product-cutover --containment` with the exact
   pin, native focused owners and the real installed profile. A suitable existing
   Linux Docker host now has a standard `/var/run/docker.sock`; no ambient
   `DOCKER_HOST` or Docker skip is needed. The earlier macOS socket failure was
   environmental and is not acceptance evidence. The profile clones committed
   `HEAD`, so first commit the coherent product candidate, keeping agy separate.
3. Map final ledger/matrix cells and request acceptance to the evidence, finish
   the concise status updates, then obtain one fresh independent high-effort
   comprehensive review. No comprehensive cutover review has run yet. Validate
   findings as a complete set and consolidate repairs; do not start repeated
   full-diff review loops. Publication, if performed, needs exact-head preflight.

Use `/opt/homebrew/bin/gmake` on macOS and the documented Homebrew linker paths.
The real ggml libraries and relocated shim are required for inference evidence;
the unavailable stub is not a substitute. Runtime model readers still require
private writable copies under R21; the relocation owner verifies unchanged bytes.
No new performance claim is made.

## Separate local Antigravity capability

Keep `.agents/`, `.codex/`, `scripts/review-agy`, `scripts/agy-review-result.jq`,
`scripts/test-agy-review`, `docs/agy-development.md`, `docs/specs/agy-development.md`,
and the unstaged agy additions in `CLAUDE.md` outside the product commit. The staged
`CLAUDE.md` blob contains only the product-language rule and belongs to cutover.
The agy capability's earlier live owner and 36 negative cases PASS; its separate
comprehensive review found two accepted defects, both repaired. Preserve this work.
