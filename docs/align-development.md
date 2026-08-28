# Developing align-llm with Align

Align is developed in parallel with this project. There is no Align project manifest, package registry, general test runner, or configurable source search path yet. A program starts from one `.align` entry file, and imports resolve to files beneath that entry file's directory.

## Managed local toolchain

Ordinary align-llm development does not use an ambient sibling Align checkout. `.align-revision`
contains the exact compiler source commit. The wrapper materializes that commit outside Git at:

```text
${XDG_CACHE_HOME:-$HOME/.cache}/align-llm/align/dev-v1/<full-commit-sha>/
  target/release/alignc
  target/release/libalign_runtime.a
```

`scripts/alignc` selects a compiler in this order:

1. The authenticated `/tools/fresh-alignc` when the fresh profile requires it.
2. The executable named explicitly by `ALIGNC`.
3. The release, then debug compiler under an explicitly supplied `ALIGN_REPO`.
4. The managed release compiler for `.align-revision`.

There is no implicit `../align` or `PATH` fallback. `make check`, `run`, `build`, `fmt`, and their
recursive smoke targets therefore use the same pin after one file changes. The first command fetches
and release-builds the pin; later commands validate and reuse the checkout. Prepare it directly
with:

```sh
scripts/align-toolchain ensure compiler
```

`ALIGN_TOOLCHAIN_ROOT` changes the absolute cache base. `ALIGN_TOOLCHAIN_REPOSITORY` changes the
source remote, and `CARGO` changes the build command. This is trusted, mutable, single-user
development state: the first build intentionally uses the developer's ordinary Cargo/Rust
environment, it is not a reproducible artifact or hostile-process boundary, and changing those
inputs requires removing that revision directory before rebuilding. Generation `dev-v1` keeps the
checkout separate from earlier cache contracts. Active cross-repository development remains explicit:

```sh
make check ALIGNC=../align/target/release/alignc
make check ALIGN_REPO=../align
```

These overrides deliberately bypass the managed default. Use them only when testing Align work that
has not yet become the repository pin.

## What to read

Use the Align repository as the source of truth. When coordinating live Align changes, the sibling
checkout remains the convenient documentation and implementation workspace:

- Start with `../align/CLAUDE.md` for current implementation status and invariants.
- Read `../align/draft.md` for the authoritative language design.
- Read `../align/docs/guide/` for supported day-to-day syntax and APIs.
- Search `../align/examples/` and compiler tests for compiling examples.
- Check `../align/docs/open-questions.md` before depending on unsettled behavior.
- For HTTP work, read `../align/docs/impl/15-pkg-web-plan.md`, `../align/docs/impl/pkg-design/web.md`, and `../align/apps/web/pkg/`.

Do not copy the in-progress web package into this repository merely to make imports resolve. Until Align gains a package mechanism, either keep an application independent of it or coordinate an explicit vendoring decision with version and update rules.

## Supported development loop

```sh
make check
make fmt
make run
```

`check-per-unit` validates imported modules through their public interfaces. The formatter rewrites only meaningless syntax variation and should run before a commit. Use `emit-mir`, `emit-llvm`, `explain-opt`, and `size` directly through the wrapper when validating performance claims:

```sh
./scripts/alignc emit-mir src/main.align
./scripts/alignc explain-opt src/main.align --verbose
./scripts/alignc size src/main.align --profile tiny
```

Before publishing an executable branch, run the shared local preflight with the narrow owner
command. A Markdown additions/modifications branch omits the owner arguments only when `--plan`
classifies it as `docs`:

```sh
python3 scripts/pre-pr --owner-test provider-smoke -- make provider-smoke
python3 scripts/pre-pr
```

Markdown deletions and renames fail closed to executable preflight and therefore require an
applicable owner command; the classifier remains authoritative when path shape is ambiguous.

`scripts/pre-pr` computes the merge base with `origin/main`, classifies the exact diff, runs the
owner before its required aggregate, and records a local exact-HEAD stamp only after every selected
gate passes. With no `--align-repo`, the printed plan runs the owner first, then ensures and uses the
same managed full-history source as the wrapper. Use `--plan` to inspect every phase and predicted path without fetching, building,
running commands, or writing the stamp. An explicit `--align-repo` remains available for a named
exact checkout. Fresh-image ownership additionally runs the focused qualification and the installed
profile once each; the installed invocation removes ambient `DOCKER_HOST` and requires a reachable
Docker daemon. The disposable profile clones the selected source without hardlinks and never reads
another active checkout's worktree files.
The classifier and path inventory are shared with GitHub Actions, so local and hosted scope cannot
drift independently. See `docs/specs/development-preflight.md` for the exact commands and failure
behavior.

After a pull request merges, the `main` push jobs reuse its successful CI evidence only when the
merge commit has the exact tested head tree, the tested base as both first parent and parent merge
base, one matching merged pull request, and one matching successful `ci.yml` run containing both
required jobs. Direct pushes, squash/rebase or conflict-resolution merges, failed or stale runs,
and unavailable GitHub evidence run the normal classifier-selected gates. This removes the second
fresh-image execution after an exact merge without weakening direct-push coverage.

Run `make ci` for the complete capable-host gate. It uses the exact managed pinned Align release compiler,
then runs the bounded hosted functional graph, the sandboxed coding corpus, and canonical baseline
verification in a deterministic order. It is complete for that declared graph, not for every
focused qualification script in the repository. Run `make hosted-checks` only on hosts that cannot
provide the coding corpus's nested user namespace; it intentionally omits `eval-coding` and
`baseline-check`. A focused target is diagnostic evidence for that surface, not evidence that
either aggregate completed.

Resource-limit, race, security, fuzz, stress, platform, mutation, and benchmark qualification run
through their named owner commands when the owning boundary changes or an explicit audit requires
them. For example, coding-task resource-monitor qualification is:

```sh
python3 scripts/run-coding-task-resource-scan-smoke
```

It is intentionally not a transitive child of `make eval-coding`.

## Managing language dependencies

When the engine needs a feature that does not compile in the current Align checkout:

1. Confirm the feature is part of the settled language design.
2. Reduce the need to the smallest compiler or standard-library capability.
3. Register it in `docs/align-requests.md` with the lifecycle and blocking metadata required by
   `CLAUDE.md`.
4. If it is blocking, pause only the dependent consumer capability and record the resume condition
   in `HANDOFF.md`. Continue valid independent work without assuming the proposed surface.
5. Implement and test that capability in `../align` as a separate, reviewable change.
6. Update this repository only after the Align change is available at a named commit or release.
7. Batch merged prerequisites needed by the next consumer when practical. Update `.align-revision`
   once, materialize its managed release compiler, run the acceptance targets that own the changed
   consumer boundary and the request's named final integration owner, and record the real-client
   verification before closing each request. The pin change alone does not select `make ci` or a
   platform matrix.

This separation keeps engine work reproducible and prevents application code from becoming an accidental language specification.

## Provider development

The C1 provider surface lives in `src/model.align` and `src/provider.align`. `model.ProviderConfig`
holds the explicit provider kind, endpoint, model, API key, timeout, and optional llama.cpp
tokenizer endpoint. `provider.generate`, `provider.stream`, `provider.count_tokens`, and
`provider.model_info` dispatch only through the declared `ProviderKind` enum.

The OpenAI adapters send `/v1/chat/completions`; the llama.cpp adapter sends `/completion` and can
use `/tokenize` for exact counts. OpenAI-compatible token counts are deliberately marked as
estimated. Cloud OpenAI requires an `https://` endpoint and reads its bearer key from `std.env`.
Successful and failed calls are persisted through `result.GenerationRecord`, whose
`schema_version` is `2`, whose `error_code` preserves an HTTP status when available, and whose
shape is independent of the adapter.

Use `make provider-smoke` for the focused fixture. It starts a temporary HTTP server, exercises
local OpenAI-compatible and llama.cpp generate/stream calls, checks environment-backed Bearer
authentication, Cloud HTTP rejection, SSE failure handling, exact tokenizer counts, HTTP status
diagnostics, and the shared result records. Real Cloud OpenAI calls require HTTPS.

## Repository-index development

The current C2 slice is `src/repo_index.align`. It asks Git for the tracked file list with
`ls-files -z`, so repository boundaries and filenames containing newlines remain explicit. For
tracked files it records language classification, line count, readability, and test-path
candidates. `.align` files additionally contribute top-level module, type, function, and import
records, plus lexical references to imported qualified names and local calls. Each reference keeps
the source qualifier, member name, kind, resolution status, target path, target name, and line.
Tracked user-module public symbols and same-file functions resolve to targets; core/std references
are marked external, while private or missing targets remain unresolved. Because the index CLI
receives a repository root rather than one compiler entry file, user-module resolution uses the
importing file's directory as its conservative base. The result is a schema-version-3,
revision-bound JSON document written by:

```sh
./main --index <repo> <index.json> [timeout-ns]
```

Use `make index-smoke` for the focused fixture. It checks declaration/import/reference extraction,
user-module public resolution, local resolution, external and unresolved statuses, a
newline-containing tracked path, string/comment exclusion, test-candidate selection, revision
binding, and persisted failure metadata for a non-repository path.

### Related-test selection

The related-test selector uses the same Git `ls-files -z` tracked-file boundary as the index. It
accepts one changed path and writes a schema-version-1 selection document:

```sh
./main --select-tests <repo> <changed-path> <tests.json> [timeout-ns]
```

Tracked paths recognized as tests are ranked by a deterministic path heuristic. A basename/stem
match contributes 100 points, a shared directory contributes 20 points, and candidates with
neither signal remain at score 0. When at least one candidate has a positive score, the JSON includes
all positive-score candidates and omits score-0 generic candidates. When no positive candidate
exists, it includes every generic candidate as the deterministic fallback. Equal scores retain Git
listing order. The selector is intentionally path-based and does not yet use the resolved
symbol/reference graph, so symbol-specific ranking remains a later C2 slice.

The selector has two entries over one shared ranking core. The revision-bearing CLI entry
(`repo_index.select_tests`, used by `--select-tests`) runs `git rev-parse --verify HEAD` and then
`git ls-files -z`, because it publishes `revision`. The revision-free evaluation entry
(`repo_index.select_tests_for_evaluation`, used by `patch_eval.evaluate`) runs `git ls-files -z`
alone, because that is the only output it consumes. The two differ only for a repository with an
unborn HEAD: `rev-parse` exits 128 there, so the CLI still writes a failure document with
`error_code` 128 and an empty `revision`, while patch evaluation reports `ok` with the real
index-derived candidates — zero of them when the index is empty. A directory outside a work tree
fails on both entries, because `git ls-files -z` itself exits 128 there.

Use `make test-selection-smoke` for the fixture covering ranking order, reasons, revision binding,
generic fallback, the unborn-HEAD CLI failure, and persisted failure metadata; `make patch-eval-smoke`
owns the evaluation entry's unborn-HEAD and non-repository behavior.

## Patch-evaluator development

The first C3 slice is a read-only unified-diff evaluator. It does not apply the candidate or run a
build; those actions belong to C4. The CLI writes a schema-version-1 document:

```sh
./main --evaluate-patch <repo> <patch.diff> <evaluation.json> [timeout-ns]
```

The document records touched files and hunk-context symbols, additions/deletions, a simple
complexity delta (`if`, `match`, `loop`, `&&`, and `||` signals), public API-line changes, a
deterministic risk score, and the C2 recommended-test candidates for the first non-test file. The
risk score starts with changed lines, adds 20 for a public API change, 25 for a test/documentation/
metadata path flagged as unrelated, and five per positive complexity point. The `unrelated_diff`
flag is deliberately a conservative path heuristic until task-specific allowlists are connected.
The parser currently expects standard unified-diff file markers; patch application and richer
language-aware symbol resolution remain later slices. Use `make patch-eval-smoke` for shape,
symbol, risk, recommended-test, and failure-persistence coverage.

## Verification-loop development

The C4 slice is `src/verification_loop.align`. It turns the read-only C3 report into a bounded,
provider-independent verification loop. A task JSON document has this shape:

```json
{
  "schema_version": 2,
  "task_id": "task-name",
  "root": "/path/to/worktree",
  "candidate_patch": "/path/to/candidate.patch",
  "repair_patch": "/path/to/repair.patch",
  "memory_profile": "/path/to/repo.alignprof",
  "build": { "cmd": "...", "argv": ["..."], "expected_code": 0 },
  "targeted_test": { "cmd": "...", "argv": ["..."], "expected_code": 0 },
  "full_test": { "cmd": "...", "argv": ["..."], "expected_code": 0 },
  "timeout_ns": 10000000000,
  "max_iterations": 3
}
```

Set `repair_patch` to an empty string when the task should stop after the first failing stage.
`memory_profile` is optional. Set it to a repo-local `.alignprof` path to enable failure memory, or
omit it to preserve the C4 behavior without persistence. `targeted_test` is also optional: omit it
or set it to JSON `null` when the required `full_test` command already owns complete acceptance.
Use a command object only when the caller wants an earlier fast-fail diagnostic. Schema 1 is not a
compatibility input and is rejected with an `INVALID`, code 2 schema-2 result.

Run it with:

```sh
./main --verify-loop <task.json> <result.json>
```

The loop evaluates the candidate through C3, checks and applies it with `git apply`, then runs
build, an optional targeted-test, and the required full-test in order. With no targeted command the
order is candidate-apply, build, full-test on the first attempt and build, full-test on repaired
attempts. A failed stage is captured with its exit code, duration, summary, stdout, and stderr. The
repair prompt includes that diagnostic and the C3 evaluation document. If a repair patch is
configured and the iteration budget permits, it is checked and applied once, then the next
iteration verifies the repaired worktree. The compact result uses schema 2, emits only stages that
actually ran, uses `PASS`, `GAVE_UP`, `EXHAUSTED`, `REPAIR_FAILED`, or `INVALID` status labels, and
preserves all attempts for later provider or failure-memory work.

## Failure-memory development

The C5 slice is `src/failure_memory.align`. When `memory_profile` is configured, each completed
schema-2 verification appends one schema-1 memory event to the profile rather than rewriting a
mutable array. The event records the task and attempted patch, first failed stage/test, root-cause
summary, repair result, successful and unsuccessful strategies, recommended tests, risky symbols,
iteration counts, and risk score. The next run selects up to the three newest events for the same
task and adds them to every repair prompt. A missing or unreadable profile starts with empty
context, and a profile write/decode failure does not replace the already-written verification
result.

The fixed smoke proves persistence and reuse by running the same task twice:

```sh
make failure-memory-smoke
```

The checked-in smoke fixture uses a deterministic repair patch to prove the gate without a model
server:

```sh
make verify-loop-smoke
```

The repair patch is deliberately an input boundary, not a model implementation. A future provider
can consume `repair_prompt` and return an equivalent patch without changing verification, timeout,
or result handling.

## Persisted-result development

The C7-PERSISTED-RESULT consumer is `src/persisted_result.align`, specified by
`docs/specs/c7-persisted-result.md`. It decodes one declared verification input into an owned
record, lets the input document and every borrowed view expire, publishes one canonical result
artifact with a content-bound digest, and verifies that artifact with an independent recomputation.

An input document is one canonical `C7_VERIFICATION_INPUT` record:

```json
{
  "schema_version": 1,
  "artifact_kind": "C7_VERIFICATION_INPUT",
  "case_id": "upper-equal",
  "algorithm": "bounded-bucket-v1",
  "left": 4,
  "right": 5,
  "lower_bound": 0,
  "upper_bound": 9,
  "expected": 2,
  "note": "optional, at most 256 bytes"
}
```

The wire is canonical: declaration order, no leading or trailing whitespace, no final newline, and
an omitted `note` for `None`. A decoded record is re-encoded and compared byte-for-byte with the
file, so unknown fields, reordered keys, whitespace, and a `null` optional spelling are all
rejected. Both paths must be nonempty, NUL-free, and at most 4,096 bytes, and the two path strings
must not be byte-identical.

Only an exact-string overlap between the two paths is rejected. An aliased destination that
resolves to the same file under a different spelling — a symbolic link, a hard link, `./` or `..`
segments, or any other alternative path to the input — passes that check, and publication then
creates/truncates that file, destroying the input. Pass two distinct real paths.

Run the two commands with:

```sh
./main --persist-result <input.json> <result.json>
./main --verify-result <result.json>
```

Each prints the same seven-line summary block (`persisted-result:`, `status:`, `PASS` or `FAIL`,
`expected:`, the value, `observed:`, the value). `PASS` exits 0. A valid semantic `FAIL` is
persisted data: the artifact is written and reloaded and the summary is printed, and only then does
the CLI take its `Error.Invalid` exit. Malformed input, invalid artifact data, path validation, and
operating-system failures return an error with no summary block. Publication uses the whole-file
`std.fs.write_file` boundary, so a failed write may leave the caller-owned destination absent or
partial; nothing is removed or restored on that path.

The six bounded functional smokes remain individually invocable:

```sh
make c7-persisted-result-cli-smoke
make c7-persisted-result-lifetime-smoke
make c7-persisted-result-owned-move-smoke
make c7-persisted-result-wire-smoke
make c7-persisted-result-noncanonical-input-smoke
make c7-persisted-result-independent-destinations-smoke
```

Their fixture vectors live in `scripts/c7_persisted_result_fixtures.py`, an independent ordered
field table, escape grammar, and bucket reference.

`make persisted-result-smoke` is the bounded functional owner: it drives all six runners as one
target and prints its own wall-clock cost. That measured cost is the section 12 admission datum, and
at 3.6 s for the six runners it admitted the target to `HOSTED_CHECK_TARGETS`. The six member
targets themselves stay out of every aggregate, so the aggregate runs the set exactly once.

`make persisted-result-qualification` is the focused qualification and deliberately stays outside
every routine hosted and capable aggregate. It owns an independent Python reference (its own ordered
field tables, Request 7 escape grammar, and `bounded-bucket-v1` reimplementation, sharing nothing
with the smoke fixture module), the section 10.2 boundary table, the seeded generated differential
corpus at seed `20260803` (256 PASS and 32 FAIL cases), the malformed-input and artifact-mutation
corpora, and the temporary source mutation that rewrites the single `else if raw < upper_bound`
comparison to `<=` in a private copy of the tree, rebuilds it with the selected compiler, and
requires the differential corpus to detect it. It never mutates the working tree. Run it when the
algorithm, wire, digest, validation order, or verifier boundary changes, and before publishing such
a change:

```sh
make persisted-result-qualification
```

Both targets follow the section 9.4 process boundary: the Make recipe resolves the selected compiler
and the built product at the repository root and passes both as explicit arguments, so no child
rediscovers a compiler from a temporary tree, `PATH`, or a sibling checkout, and every child runs
with an explicit environment map, separate bounded stdout/stderr capture, and a fixed 60-second
timeout.

## GGUF-inspection development

The R0 consumer is `src/gguf.align`, specified by `docs/specs/r0-gguf-inspection.md`. It reads a
GGUF model file's header, metadata, and tensor table and publishes one canonical
`R0_GGUF_INSPECTION` document with `schema_version: 1`. It is strictly read-only on the model path:
no tensor payload is decoded, no dequantization happens, nothing is written, and no provider,
inference code, or `align-runtime` surface is imported. Only little-endian GGUF is decoded; the
container carries no endianness flag, so a big-endian file is a recorded limitation rather than a
detected rejection.

The CLI arm has the two forms every other document-producing arm has:

```sh
./main --inspect-gguf <model.gguf>
./main --inspect-gguf <model.gguf> <inspection.json>
```

The document bytes are byte-identical between the two. The one-operand form writes the document to
stdout followed by one newline and prints nothing else, so a machine consumer needs no temporary
file. The two-operand form writes the document to the named path and prints the stable summary block
(`gguf inspection:`, `status:`, `OK` or `ERROR`, then `architecture:`, `version:`, `tensors:`,
`metadata:`, `alignment:`, `data offset:`, and `bytes read:` with their values, plus `error:` and
its code on the error path). Both exit 0 on `status: "ok"` and return `Error.Invalid` on
`status: "error"`. Wrong arity returns `Error.Invalid` before any filesystem access.

`bytes_read` is the exact sum of the counts returned by every `pread` during one inspection, not an
estimate and not derived from the file size. It is what makes the "header and metadata only" claim
measurable: against a 4.68 GB reference model the expected value is roughly 5.35 MB.

The model path must currently be **writable by the invoking user**, because `fs.open_rw` is the only
random-access file constructor at the pinned Align revision. That gap is recorded as Request 21 in
`docs/align-requests.md` (`PROPOSED`, non-blocking); an `EACCES` surfaces as `Err(Error.Denied)`
with no document.

Use `make gguf-smoke` for the narrow durable owner. It needs no model, no network, and no reference
tool: `scripts/gguf_fixture.py` generates a complete synthetic container plus a negative corpus into
a `mktemp -d` tree at test time, and the runner asserts the document with an inline Python block.
Fixtures are build inputs and are never committed. The generator packs its own bytes from tables
transcribed from the specification and never imports or derives a value from `src/gguf.align`, which
is what makes the check differential rather than a mirror of the decoder.

The roadmap gate — that metadata and the tensor list agree with an existing tool — is discharged by
a focused, opt-in qualification that is deliberately in no aggregate and in no CI lane:

```sh
ALIGN_LLM_GGUF_REFERENCE=/path/to/llama-gguf \
ALIGN_LLM_GGUF_MODEL=/path/to/model.gguf \
  scripts/run-gguf-reference-parity
```

Both variables are required and neither has a default. If either the reference executable or the
model is unset or absent, the runner prints one exact line — `gguf reference parity: N/A
(ALIGN_LLM_GGUF_REFERENCE unset)` or the model equivalent — and exits 0. That skip never counts as a
pass and must be named as the `N/A` reason in the pull request. Parity covers exactly what
`llama-gguf FILE r n` prints: version, alignment, data offset, KV count, the ordered key names,
tensor count, and each tensor's name and offset. Value types, values, dimension counts, and
dimensions are outside reference parity and are owned by the synthetic corpus instead. The runner
also asserts the `bytes_read` bound and verifies that the model's size and modification time are
unchanged, which is the read-only proof.

## Model IR development

The R1 consumer is `src/frontend_qwen.align`, specified by `docs/specs/r1-qwen-model-ir.md` (merged,
align-llm PR #122). It consumes the new public, non-rendering `GgufTable` surface on `src/gguf.align`
(`read_table` and its typed accessors) rather than re-parsing the container or re-decoding the R0
document, and turns one real Qwen2-architecture GGUF file into the Model IR and Block IR that
`docs/specs/align-llm.md` section 5 places between the GGUF reader and the layout planner. It is
strictly read-only on the model path and decodes no tensor payload: every tensor byte size is
computed from the declared dimensions and the GGML block-geometry table, never from reading the data
section. The tokenizer and vocabulary are out of scope — R1 reads only the declared array length of
`tokenizer.ggml.tokens` and `tokenizer.ggml.merges`, never an element — so
`docs/align-requests.md` Request 22 stays non-blocking.

**The gpt-oss/MoE half is the merged R1B-GPTOSS-MOE-IR capability** (align-llm PR #123, head
`3bf5c9c`, merge `d8d4ef6`), specified by `docs/specs/r1b-gptoss-moe-ir.md`. `--model-ir` dispatches
on the container's own
`general.architecture` field, accepting `qwen2` (`src/frontend_qwen.align`) and `gpt-oss`
(`src/frontend_gpt_oss.align`, new); any other value, or a missing/non-UTF-8 architecture, is
rejected exactly as before. A neutral `src/model_ir.align` module owns the geometry pass, block
resolution, coverage, the size-sum oracle, and the document renderer for both frontends, so the
exchanged format has exactly one producer. `R1_MODEL_IR` becomes `schema_version: 2`, emitted by both
frontends: the block tensor record gains two additive fields, `claimed_absolute_offset` and
`claimed_nbytes`, naming the exact byte sub-range a block claims of a tensor. For qwen2 and every
non-expert member these equal `absolute_offset`/`nbytes` unchanged; a gpt-oss `ExpertBlock` claims
one `(layer, expert)` sub-range of a stacked expert tensor, giving one `RouterBlock` per layer and
one `ExpertBlock` per `(layer, expert)` pair. One new geometry row, MXFP4 (GGML type id 39, block
size 32, 17 bytes/block), joins the GGML block-geometry table in `src/gguf.align`; its provenance is
a named revision (`ggml.h` from the installed llama.cpp build 10566) plus a library oracle
(`ggml_blck_size`/`ggml_type_size` linked against `libggml-base` 0.21.0) that reproduces every
existing row, recorded as "library-oracle verified; real-model verification pending". One new error
code, `R1_BLOCK_CLAIM_MISMATCH`, guards the claim-tiling invariant — every tensor's block claims
either include one whole-tensor claim or exactly partition its byte range — and is defensive rather
than input-reachable once the row and stacked-tensor rules pass.

The CLI arm mirrors `--inspect-gguf`:

```sh
./main --model-ir MODEL.gguf
./main --model-ir MODEL.gguf OUT.json
```

The document bytes are byte-identical between the two forms. The one-operand form writes the
`R1_MODEL_IR` document (`schema_version: 2`) to stdout followed by one newline and prints nothing
else. The two-operand form writes the document to the named path and prints the stable summary block
(`qwen model ir:`, `status:`, then `arch:`, `layers:`, `embd:`, `heads:`, `heads kv:`, `head dim:`,
`ff:`, `vocab:`, `experts:`, `context:`, `blocks:`, `tensor bytes:`, and `size sum:`, plus `error:`
and `detail:` on the error path). Both exit 0 on `status: "ok"` and return `Error.Invalid` on
`status: "error"`. On `status: "error"` the document is still written with every value derived
before the failure, the same failure-persistence behavior R0 established.

Use `gmake model-ir-smoke` for the narrow durable owner. It needs no model, no network, and no
reference tool: `scripts/gguf_fixture.py`'s qwen2 and gpt-oss corpora each generate a complete
synthetic positive model plus a negative fixture per section 2.6 error code (of
`docs/specs/r1b-gptoss-moe-ir.md`) into a `mktemp -d` tree at test time, and the runner asserts the
document with an inline Python block, including recomputing every `claimed_absolute_offset`/
`claimed_nbytes` from the generator's own layout and independently checking claim tiling in Python.
It also asserts the `table-inspect-parity` agreement between `--inspect-gguf` and `--model-ir` over
the combined corpus, so the two walks over one decoder cannot silently drift.

The capability's own completeness proofs are the size-sum oracle,
`data_offset + Σ tensor_nbytes == file_size`, and — new for R1B — the claim-tiling oracle over each
tensor's block claims, both checked from inside the program on every input — real or synthetic — and
asserted by `gmake model-ir-smoke` on the synthetic corpus.

The roadmap gate — Model IR and Block IR can be produced — is discharged in part by those two oracles
and in part by a focused, opt-in qualification that compares the derived hyperparameters and quant
summary against `llama-cli -v`'s `print_info` block on a real model. It is deliberately in no
aggregate and in no CI lane, and the same runner dispatches on both architectures by reading
`model.arch` out of the document it just produced:

```sh
ALIGN_LLM_GGUF_MODEL=/path/to/model.gguf \
ALIGN_LLM_LLAMA_CLI=/path/to/llama-cli \
  scripts/run-model-ir-parity
```

Both variables are required and neither has a default. If the reference executable or the model is
missing, the runner prints exactly one of these four lines and exits 0:

```text
model ir parity: N/A (ALIGN_LLM_LLAMA_CLI unset)
model ir parity: N/A (ALIGN_LLM_LLAMA_CLI is not executable)
model ir parity: N/A (ALIGN_LLM_GGUF_MODEL unset)
model ir parity: N/A (ALIGN_LLM_GGUF_MODEL is absent)
```

They are checked in that order, so an unset variable is reported before an unusable one. That skip
never counts as a pass and the exact line must be named as the `N/A` reason in the pull request. A parse
failure against the reference's log output fails closed (a nonzero exit, never a skip and never a
silent pass). The runner also asserts the size-sum oracle against an independent `stat` of the file,
the `bytes_read` bound, and that the model's size and modification time are unchanged, which is the
read-only proof. The reference itself runs under a 300-second `timeout` (or `gtimeout`; skipped when
the host has neither) inside a subshell whose `ulimit -f 262144` caps every file it writes at 256 MiB
(bash counts 1024-byte blocks), so a reference build that fails to terminate is a bounded failure
rather than an unbounded log. The cap is deliberately far above the log itself (125 KB for the olmoe
model, 237 KB for the qwen one) because `ulimit -f` bounds *every* file the reference creates: on a
Metal host `llama-cli` writes a compiled shader pipeline cache of 12-35 MB per file, so an earlier
8 MiB cap killed the reference with SIGXFSZ mid-compile whenever that cache was cold, surfacing only
as "the reference reader exited 153". 256 MiB clears the cache and still bounds the 461 MB runaway
log the wrapper exists for. The timeout diagnostic is reported only when one of those wrappers was
actually used.

**The gpt-oss parity qualification is an explicit, named `N/A` today**, stated exactly, per
`docs/specs/r1b-gptoss-moe-ir.md` section 4.4:

```text
make model-ir-parity (gpt-oss): N/A — no gpt-oss GGUF on this host; ALIGN_LLM_GGUF_MODEL unset.
make model-ir-parity (qwen2):   PASS / N/A — unchanged R1 qualification.
```

`gpt-oss-20b-mxfp4.gguf` is 12.1 GB and is not downloaded by this capability; whether to fetch it, and
onto what storage, is a decision the user owns, not one the capability makes for them. Until that
model is present the gpt-oss half of the roadmap gate rests on the synthetic corpus, the size-sum and
claim-tiling oracles, and the MXFP4 library oracle above.

The model path inherits R0's writable-by-the-invoking-user precondition unchanged — `read_table`
uses the same `fs.open_rw` constructor for both frontends — so Request 21 in
`docs/align-requests.md` covers this capability too, still `PROPOSED` and non-blocking.

**The olmoe half is the R1C-OLMOE-MOE-IR capability, implemented** (branch
`agent/r1c-olmoe-moe-ir`, design ledger commit `83361a9`, implementation `45e4ced` with its review
repair on top; review is complete and publication is the remaining work), specified by
`docs/specs/r1c-olmoe-moe-ir.md`. `--model-ir` dispatch becomes a three-way chain at
`general.architecture`: `qwen2` (`src/frontend_qwen.align`), `gpt-oss`
(`src/frontend_gpt_oss.align`), and now `olmoe` (`src/frontend_olmoe.align`, new); everything else
still falls through to the qwen2 frontend, whose step-4 re-check produces `R1_UNSUPPORTED_ARCH`. No
change to `src/model_ir.align` or to `R1_MODEL_IR`'s `schema_version: 2` is required — olmoe reuses
the neutral geometry pass, block resolution, coverage, and size-sum oracle unchanged, and needs no
new GGML geometry row (the model uses only `F32`, `Q4_K`, and `Q6_K`, all already sized). The one
addition to the frozen `role_id` list in `src/alignpack.align` and its `scripts/alignpack_reader.py`
mirror is two roles the qwen2 and gpt-oss frontends never needed: `attn_q_norm` (27) and
`attn_k_norm` (28), the olmoe model's per-layer QK-norm tensors (`blk.N.attn_q_norm.weight` and
`blk.N.attn_k_norm.weight`, each `[n_embd]` F32). They are a hard precondition for R4.5's expert
matmul on this model: without them two of every seven attention block members would persist as
`DEFERRED_U32` in a pack rather than as an addressable role.

The parity row set gains a fourth architecture branch in `scripts/run-model-ir-parity`'s
`build_rows`. The olmoe extension over the shared row set is exactly `["n_expert_used"]` — unlike
gpt-oss it adds no `n_ff_exp` row, because the reference build prints one only for an architecture
that declares `expert_feed_forward_length`, and olmoe does not — and it adds no `n_swa` row, because
the olmoe Model IR has no `sliding_window` field to compare against the reference's architecture
default. Both omissions are asserted rather than silently dropped. `ALIGN_LLM_GGUF_MODEL` continues
to serve all three architectures; there is no third environment variable. Unlike the gpt-oss
qualification, olmoe's is runnable today against
`OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf` (3.92 GiB, already downloaded locally), and it **has been
run and passes**: 15 compared rows — `arch: olmoe`, `n_layer: 16`, `n_embd: 2048`,
`n_head`/`n_head_kv: 16`, `head_dim: 128` (from both `n_embd_head_k` and `n_embd_head_v`),
`n_ff: 1024`, `n_expert: 64`, `n_expert_used: 8`, `n_vocab: 50304`, `context_length: 4096`,
`rope.type: 2`, `freq_base 10000.0`, `rms_eps 1.0e-05` — plus a loader type census of `f32: 81`,
`q4_K: 97`, `q6_K: 17`, coverage of 195 of 195 tensors over 1,058 blocks, and a size-sum oracle
closing at `1,781,760 + 4,211,730,432 = 4,213,512,192`. `bytes_read` is 2,097,152, which is **two**
1 MiB windows rather than one, because `data_offset` (1,781,760) lies past the first window boundary.
This is the first `model-ir-parity` discharged against a real mixture-of-experts model; the qwen2
qualification passes unchanged over its 14 rows in the same runner.

## Expert trace development

R2A-EXPERT-TRACE-CAPTURE is merged into `main` as PR #124 (head `ab5f7d8`, merge `b8e1cb6`); its
authoritative plan is `docs/specs/r2a-expert-trace.md`. The instrument is llama.cpp's `llama-eval-callback` (recorded
build 10566), used as a measurement device rather than adopted as a runtime dependency. The CLI arm:

```sh
./main --expert-trace CALLBACK_LOG.txt
./main --expert-trace CALLBACK_LOG.txt OUT.json
```

consumes a `llama-eval-callback` transcript and produces an `R2_ACTIVATION_TRACE`
(`schema_version: 1`) document with per-(token, layer) expert ids and locality aggregates; a dense
(non-MoE) transcript yields `moe: false`. Both operands are validated lexically against
`MAX_PATH_BYTES` (4096) and rejected for a NUL byte before any file work, so an unusable destination
never costs a transcript scan.

**The transcript inherits the same writable-by-the-invoking-user precondition the model path has.**
`src/expert_trace.align` opens it with `fs.open_rw`, the only random-access constructor Align ships
at this pin, so a transcript captured into a root-owned or read-only artifact directory — a mode
`0444` file, for instance — cannot be opened at all and the arm exits nonzero with no document.
`docs/align-requests.md` Request 21 records this as a second class of read-only input, still
`PROPOSED` and non-blocking; `scripts/run-expert-trace-smoke`'s `read-only-transcript` case asserts
the current behavior and is expected to flip the day `fs.open_ro` ships.

The narrow durable owner is `gmake expert-trace-smoke`; adding it to the `Makefile` selects the
fresh-image preflight profile at publication. The named opt-in qualification is
`scripts/run-expert-trace-parity`, taking two environment variables:

```sh
ALIGN_LLM_GGUF_MODEL=/path/to/model.gguf \
ALIGN_LLM_LLAMA_EVAL_CALLBACK=/path/to/llama-eval-callback \
  scripts/run-expert-trace-parity
```

`ALIGN_LLM_GGUF_MODEL` names the model to run the callback instrument against; a dense model (e.g.
the existing Qwen2.5-Coder-7B) exercises the `moe: false` path, and a MoE model exercises
`moe: true`. Both halves are now discharged on this host: `OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf`
is the MoE subject. `ALIGN_LLM_LLAMA_EVAL_CALLBACK` names the callback instrument executable.

Neither variable has a default. A missing or unusable input prints exactly one of these lines and
exits 0 without claiming a pass, and the line must be named as the `N/A` reason in the pull request:

```text
expert trace parity: N/A (ALIGN_LLM_LLAMA_EVAL_CALLBACK unset)
expert trace parity: N/A (ALIGN_LLM_LLAMA_EVAL_CALLBACK is not executable)
expert trace parity: N/A (ALIGN_LLM_GGUF_MODEL unset)
expert trace parity: N/A (ALIGN_LLM_GGUF_MODEL is absent)
```

They are checked in that order, so an unset variable is reported before an unusable one. A run that
reaches the instrument also emits its own two-line verdict, one line per half, and exactly one of
the two is a `PASS`: a dense model prints `expert trace parity (dense): PASS` with
`expert trace parity (MoE): N/A - no MoE GGUF on this host; see section 4.5.`, and a MoE model
prints `expert trace parity (MoE): PASS` with `expert trace parity (dense): N/A - moe.present is
true`. A half whose branch never ran never claims a pass, so the pull-request record quotes lines
the runner printed rather than lines an author composed.

**The oracle is an independent Python re-parse, not a self-check.** The runner re-implements the
section 2.2 grammar in Python inside itself and parses the same transcript a second time, then
compares the node families, the operation set, the layer count, the graph count, every graph's token
count and phase, the line censuses, `moe.present`, and — for a MoE model — every selection field for
field, plus the locality reuse triple recomputed from its own selections with naive nested loops.
Any disagreement fails closed with a nonzero exit; a parse failure against the instrument's output
is a hard failure and never a skip. The runner also asserts the `bytes_read` bound and that the
model's size and modification time are unchanged, which is the read-only proof. The instrument runs
under a 600-second `timeout` so a run that fails to terminate is a bounded failure.

### The pinned R2c decode instrument

R2c's authoritative external-dependency contract is
`docs/specs/r2c-decode-instrument.md`. `.llama-revision` pins llama.cpp commit
`bb4caa7540188872173c44d161602d9271386413`, and
`patches/llama.cpp/r2c-decode-instrument.patch` is the reviewed two-file diff. It changes the
measurement example only: `ffn_moe_topk` axes print in full, and a positive `-n N` evaluates up to N
sampled non-EOG tokens as one-token decode graphs. No llama.cpp source or binary is committed.

The managed builder writes outside the work tree and binds its cache entry to both full source
identities:

```sh
scripts/llama-eval-callback-toolchain path instrument
scripts/llama-eval-callback-toolchain ensure instrument
scripts/llama-eval-callback-toolchain verify
scripts/llama-eval-callback-toolchain attest instrument
```

`path` is read-only and need not name an existing entry. `ensure` performs a one-commit fetch, exact
patch application, a fixed CPU CMake build with Metal and llama/ggml shared libraries disabled,
admission, and atomic publication. `verify` rejects source revision or staged/unstaged diff drift
from `HEAD`, untracked source, symlink boundaries, missing or non-executable output, and anything
whose version is not build 10566 / commit `bb4caa7`. `attest instrument` emits the source and patch
identities plus the platform-local instrument digest.

The cache root is `ALIGN_LLM_LLAMA_TOOLCHAIN_ROOT/r2c-v2` when explicitly set, otherwise
`$XDG_CACHE_HOME/align-llm/llama.cpp/r2c-v2` or `$HOME/.cache/align-llm/llama.cpp/r2c-v2`.
The resolved generation path must be outside the align-llm checkout; lexical containment and a
cache path that reaches the checkout through a symlink are both refused before any write.
`ALIGN_LLM_LLAMA_REPOSITORY` overrides the public upstream URL for an offline/local source, `CMAKE`
selects one CMake command, and `CMAKE_BUILD_PARALLEL_LEVEL` controls build scheduling. Unsafe,
relative, whitespace-containing, or semantically drifted inputs fail; no ambient llama.cpp checkout
or binary is selected.

The schema-1 parser now selects compact versus full axes from the actual ellipsis. Existing
build-10566 compact transcripts retain first/last-three indices and byte-identical documents; an
R2c router axis reports every slot/token and false truncation flags. The deterministic owners are:

```sh
scripts/run-r2c-instrument-smoke
make expert-trace-smoke
make residency-sim-smoke
```

The compiled focused qualification materializes the instrument, downloads upstream's SHA-pinned
15M dense test model into a temporary sibling, atomically publishes it only after hash validation,
and proves legacy one-prefill versus patched one-prefill-plus-two-decode behavior through
`main --expert-trace`:

```sh
scripts/run-r2c-instrument-qualification

ALIGN_LLM_GGUF_MODEL=/path/to/OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf \
  scripts/run-r2c-instrument-qualification
```

The first command must pass the dense half, proving omitted, zero, and negative `-n` each retain
one prefill graph while `-n 2` adds two decode graphs, and prints exact N/A for the optional MoE
half. The second additionally requires `moe.present: true`, at least one decode graph, no slot/token
truncation, every observed routing group to contain all `n_expert_used` slots, and at least one
retained router axis extent above six so the changed full-axis branch is actually exercised. Any
selected model/instrument failure is a hard failure, transcripts are bounded to 256 MiB and removed,
and no latency or locality claim is made.

### The R2 locality gate

`scripts/run-expert-locality-gate` is the R2 roadmap gate's measurement: it captures one prefill
transcript per prompt from a checked-in corpus, derives one `R2_ACTIVATION_TRACE` document from each
with `main --expert-trace`, deletes the transcript, and pools every document into one verdict. The
numbers it produced, and every caveat they carry, are recorded in `docs/specs/r2a-expert-trace.md`
section 8; that section is authoritative for the result and this one for how to run it.
The runner passes explicit `-n 0`, so positive-`-n` decode cannot enter this historical prefill
gate. It also requires the original compact first/last-three router-slot form: selecting the R2c
full-axis instrument is a controlled measurement failure, not a silent change from six to eight
observed slots. Use `run-r2c-instrument-qualification` for R2c instrument evidence and
`scripts/run-decode-locality-gate` — the next section — for the full-axis and decode measurement.

```sh
ALIGN_LLM_GGUF_MODEL=/path/to/moe-model.gguf \
ALIGN_LLM_LLAMA_EVAL_CALLBACK=/path/to/llama-eval-callback \
  scripts/run-expert-locality-gate
```

| Variable | Default | Meaning |
| --- | --- | --- |
| `ALIGN_LLM_GGUF_MODEL` | none | a **MoE** GGUF; a dense model makes the gate refuse, because a dense graph has no router to measure |
| `ALIGN_LLM_LLAMA_EVAL_CALLBACK` | none | the callback instrument executable |
| `ALIGN_LLM_LOCALITY_PROMPTS` | `eval/prompts/expert-locality-v1.txt` | the prompt corpus, one prompt per line |
| `ALIGN_LLM_LOCALITY_PROMPT_COUNT` | `40` | prompts to use, taken from the **top** of the corpus in file order |

Neither model variable has a default. A missing or unusable input prints exactly one of these lines,
in this order, and exits 0 without claiming a measurement:

```text
expert locality gate: N/A (ALIGN_LLM_LLAMA_EVAL_CALLBACK unset)
expert locality gate: N/A (ALIGN_LLM_LLAMA_EVAL_CALLBACK is not executable)
expert locality gate: N/A (ALIGN_LLM_GGUF_MODEL unset)
expert locality gate: N/A (ALIGN_LLM_GGUF_MODEL is absent)
```

**The gate is a measurement, not a pass/fail owner test.** It exits 0 on either verdict — `LOCALITY`
and `NO_LOCALITY` are both answers to the roadmap question — and exits nonzero only when the
instrument, the corpus, or the parser prevented a measurement from being taken. It prints a human
table and one machine-readable final line:

```text
expert-locality-gate verdict=... prompts=... layers=... layers_clearing=... pairs=... hits=...
  trials=... p0_per_mille=... p_hat_per_mille=... wilson_lo_per_mille=... wilson_hi_per_mille=...
  clusters=... deff_per_mille=... cluster_lo_per_mille=... cluster_hi_per_mille=...
  ratio_per_mille=... entropy_per_mille=... top8_mass_per_mille=... truncated_documents=...
  token_reduced_documents=... token_reduced_layers=...
```

**Two intervals are reported and the wider one decides.** The trials are clustered by prompt — one
prompt supplies every layer and token position it has — so the naive Wilson interval assumes an
independence the corpus does not have. The gate estimates the design effect with the prompt as the
cluster, widens Wilson by deflating the sample size to `N / deff`, and judges the interval half of
the verdict on the **cluster-robust** lower bound. The design effect is floored at 1, so clustering
can only widen. `truncated_documents` and `token_reduced_layers` report what the instrument dropped
before the gate saw it: a token-reduced layer contributes to no number in the result.

**The prompt corpus is checked in and its order is part of its identity.** Every prompt in
`eval/prompts/expert-locality-v1.txt` tokenizes to six tokens or fewer against the subject model,
verified with `llama-tokenize` before the file was frozen. That matters: the instrument prints at
most six entries per axis, so a longer prompt hides token positions and breaks adjacency in the
middle of the prefill. A new corpus must repeat that check. The runner prints the corpus name, md5,
byte count, and prompt count with every result.

**Transcripts are captured one at a time and deleted immediately**; only the documents are pooled.
A 40-prompt run against a 16-layer MoE model writes and removes roughly 44 MB of transcript and
takes about a minute with a warm page cache.

**The aggregation is a separate importable module**, `scripts/expert_locality_gate.py`, so that the
statistics have an owner test with no model and no network: `scripts/run-expert-trace-smoke`'s
`locality-gate-aggregator` case pools the synthetic corpus's memoryless-router documents and
requires `NO_LOCALITY`, then decides each half of the verdict rule on its own with routers it
specifies exactly: a case that clears the null but is immaterial, one that is material but whose
interval includes the null, one at exactly 2.0× the null, and one whose reuse is entirely
between-prompt and must be refused by the cluster-robust bound after the naive interval accepts it.
It also requires that a document whose `locality` disagrees with a recomputation from its own
`selections[]` is refused. Every number the module produces is an integer per mille; floating point
appears only inside the Wilson bound and the design effect, and every output is floored before any
comparison, so the verdict is a comparison of integers.

The gate joins no aggregate and no `Makefile` target: adding one would select the fresh-image
preflight profile for a runner that cannot execute in CI anyway.

### The R2D decode locality gate

`scripts/run-decode-locality-gate` is the decode half of the same roadmap question, and it is the
first measurement consumer of R2c's patched instrument. It captures one prompt-plus-decode
transcript per prompt from the same checked-in corpus, derives one `R2_ACTIVATION_TRACE` document
from each with `main --expert-trace`, reads one token fingerprint per observed position, deletes the
transcript, and publishes **three** verdicts under one rule. The numbers it produced are recorded in
`docs/specs/r2a-expert-trace.md` section 9; that section is authoritative for the result and this one
for how to run it.

It requires the **patched** instrument. `scripts/llama-eval-callback-toolchain ensure instrument`
prints the path to build.

```sh
ALIGN_LLM_GGUF_MODEL=/path/to/moe-model.gguf \
ALIGN_LLM_LLAMA_EVAL_CALLBACK="$(scripts/llama-eval-callback-toolchain ensure instrument)" \
  scripts/run-decode-locality-gate
```

| Variable | Default | Meaning |
| --- | --- | --- |
| `ALIGN_LLM_GGUF_MODEL` | none | a **MoE** GGUF; the subject model |
| `ALIGN_LLM_LLAMA_EVAL_CALLBACK` | none | the **patched** callback instrument; a compact-axis build is refused, not silently measured |
| `ALIGN_LLM_LOCALITY_PROMPTS` | `eval/prompts/expert-locality-v1.txt` | the prompt corpus, one prompt per line |
| `ALIGN_LLM_LOCALITY_PROMPT_COUNT` | `40` | prompts to use, taken from the **top** of the corpus in file order; 1 to 1000, and a value outside that range — `0` included — is an error rather than an empty measurement |
| `ALIGN_LLM_DECODE_STEPS` | `16` | generated tokens per prompt; 1 to 128, and a value outside that range is an error rather than a silent default |

A missing or unusable model/instrument prints exactly one of these lines, in this order, and exits 0
without claiming a measurement:

```text
decode locality gate: N/A (ALIGN_LLM_LLAMA_EVAL_CALLBACK unset)
decode locality gate: N/A (ALIGN_LLM_LLAMA_EVAL_CALLBACK is not executable)
decode locality gate: N/A (ALIGN_LLM_GGUF_MODEL unset)
decode locality gate: N/A (ALIGN_LLM_GGUF_MODEL is absent)
```

**Greedy decode is the contract.** The capture pins `-n N --temp 0 --seed 42` on top of the R2
flags (`-t 4 -fa off -ctk f32 -ctv f32 -nr -c 512`), so the generated continuation is the model's
argmax and is reproducible. The seed is recorded even though temperature zero makes it inert, so a
sampled arm can never be mistaken for this one. `-n N` is R2c's "at most N decode graphs": a prompt
that reaches an end-of-generation token contributes fewer.

**Three arms, one rule.** Adjacency here is over the *sequence*, not inside one graph, because every
decode graph holds exactly one token — which is why the merged prefill gate reports
`phase_split.decode` as `null` even on a multi-graph transcript. One chain per `(document, layer)`
is ordered by `(graph ordinal, token index)`, and two consecutive points are adjacent when they are
consecutive tokens of one graph or the last token of graph `g` and the first token of `g + 1`:

| Arm | Pairs | Note |
| --- | --- | --- |
| `prefill@8` | adjacent prompt tokens | **not** comparable to section 8's 286 per mille: that observed 6 printed slots of 8, this observes all 8 |
| `decode@8` | adjacent generated tokens | the measurement build 10566 could not take at all |
| `boundary` | last prompt token against first generated token | exactly one pair per prompt and layer, reported on its own |

Each arm is judged by the rule the prefill gate uses — the cluster-robust lower bound must exclude
`p0 = k/n`, and `p^` must be at least 1.5 × `p0` — and a pair touching a `single_token_first_graph`
graph reaches no arm and is counted as ambiguous. With every slot printed the compact gate's smaller
printed-subset null has no counterpart: there is one null, 125 per mille on this model.

**The repetition arm.** Greedy decode can enter a loop, and the experts of one token are trivially
the experts of the same token. The runner therefore reads a token fingerprint — the printed values
of the entry `embd = ... GET_ROWS(token_embd.weight, inp_tokens)` row, a deterministic function of
the token id — for every observed position, reports the measured repetition rate per phase and per
prompt, and republishes all three verdicts with every token-repeating pair excluded. No headline
verdict uses the fingerprint, and a block whose row count does not match the graph's `n_tokens`
disables the arm rather than excluding the wrong pairs. The arm is all-or-nothing across the corpus,
so the reason is recorded per prompt and reported by label — `token repetition N/A (1 of 40
prompt(s) could not be read: prompt 007: 7 entry embedding block(s) for 6 graph(s))` — rather than
lost behind one "could not be read".

**The caveats are bound to the run.** The runner prints the corpus's longest prompt as a header line
and substitutes it into the short-context caveat, because `ALIGN_LLM_LOCALITY_PROMPTS` can name a
corpus other than the checked-in one and a caveat that hard-codes the default is false the moment it
does.

It prints a human table and one machine-readable final line beginning `decode-locality-gate `, with
`PHASE_KEY=VALUE` fields for each of the three arms plus the repetition rate, the per-phase histogram
statistics, and the sensitivity verdicts.

**Transcripts are captured one at a time and deleted immediately.** A 40-prompt run at 16 steps
against this 16-layer MoE model writes and removes roughly 600 MB of transcript, one 15 MB file at a
time, and the file is capped at 256 MiB by `ulimit -f`.

**The aggregation is the same importable module**, `scripts/expert_locality_gate.py`. The historical
compact path and its refusal are untouched; the decode path is `require_full_router_axes`,
`entry_token_fingerprints`, and `aggregate_decode`, and its owner is
`scripts/run-expert-trace-smoke`'s `decode-locality-gate-aggregator` case, which needs no model, no
network, and no instrument. It builds full-axis multi-graph documents from a router it specifies
exactly and requires: a memoryless router to score `NO_LOCALITY` on all three arms; an effect
confined to one arm to appear in that arm and neither other; a boundary-only effect to move exactly
one pair per prompt and layer; a detectable-but-immaterial and a material-but-uncertain decode case
to be refused by the two halves separately; the materiality boundary to be pinned from **both**
sides, one per mille below it and one per mille above, and again on a second router shape whose
1.5 × null is an exact integer; a between-prompt effect to be refused by the cluster-robust bound
after the naive interval accepts it; and a corpus that loops for half its generated tokens to score
`LOCALITY` before exclusion and `NO_LOCALITY` after it. It reproduces correction 20's token-reduced
prefill layer at the real model's shape, so the 15/15/16 layer counts the real capture reports are
a fixture property rather than an accident, and it requires a hole in one layer's chain to break a
working-set run rather than be unioned across. It also requires that a compact R2A document, a
truncated token axis, and a `status: "error"` document are refused — the last on its own
`error_code`, because admission runs before any read of the router shape — that a parser `locality`
that disagrees with a recomputation from its own `selections[]` is refused, and that the fingerprint
reader identifies a repeated token without reading a non-entry tensor or the generated text that
follows the final `sum =` line.

Like the prefill gate, this one joins no aggregate and has no `Makefile` target: R2c's fetched
measurement dependency stays opt-in, and adding a target would select the fresh-image preflight
profile for a runner that cannot execute in CI anyway.

## Residency simulation development

R3-RESIDENCY-SIM's authoritative plan is `docs/specs/r3-residency-sim.md`, which owns the contract
ledger, the policy set, the exchanged document, the validation order, the closure matrix, the
correction ledger, and the probe record. It replays the demand stream implied by a set of
`R2_ACTIVATION_TRACE` documents against ten expert-residency cache policies at a nine-point budget
sweep, and answers the roadmap section R3 gate question — is any policy materially better than the
baseline on this hardware condition — with a measured verdict rather than an opinion. It needs no
model, no instrument, and no GPU: its inputs are two documents this repository already produces.

The CLI arm has the same two forms every other document verb has:

```sh
./main --simulate-residency TRACES.txt MODEL-IR.json BUDGET_BYTES
./main --simulate-residency TRACES.txt MODEL-IR.json BUDGET_BYTES RESIDENCY.json
```

`TRACES.txt` is a list of `R2_ACTIVATION_TRACE` document paths, one per line; `MODEL-IR.json` is an
`R1_MODEL_IR` document, from which only the `ExpertBlock` rows and their `byte_size` are read;
`BUDGET_BYTES` is the requested residency budget in bytes, parsed by the module's own decimal parser
rather than through a `json.decode` detour. The three-operand form prints the whole
`R3_RESIDENCY_SIM` (`schema_version: 1`) document and nothing else, and the four-operand form writes
it to `RESIDENCY.json` and prints the stable human summary block instead; both forms produce a
byte-identical document, which the owner asserts on every case. All four operands are validated
lexically against `MAX_PATH_BYTES` (4096) and rejected for a NUL byte before any file work, so an
unusable destination never costs a simulation. Every rate in the summary carries the router-slot
coverage it is conditional on: the instrument prints six of eight slots on the subject model, so no
number is a hit rate without the qualifier "over printed slots".

**The narrow durable owner is `gmake residency-sim-smoke`**, and it is a member of
`HOSTED_CHECK_TARGETS` alongside `gguf-smoke`, `model-ir-smoke`, and `expert-trace-smoke` — the same
justification admitted all four. It builds its own synthetic olmoe Model IRs and MoE transcripts,
needs no model, no network, no instrument, and no GPU, writes well under a megabyte into a temporary
tree, and runs in about a second. `scripts/check-gate-topology` pins the member list in two places
and `gmake gate-topology-check` fails if either drifts.

**The oracle is an independent Python re-implementation, not a self-check.** `scripts/residency_oracle.py`
implements sections 2.2 through 2.8 of the plan from the plan and never from `src/`, renders the
whole document itself, and the smoke compares every integer of every policy at every sweep budget in
both demand orders, with no tolerance. One case is additionally pinned by a checked-in golden,
`eval/fixtures/residency-sim/sim-basic.golden.json`, with its three host-dependent values normalized
(the two path operands and `inputs.bytes_read`, which grows with the scratch directory's name).
Regenerate the golden deliberately, never by hand:

```sh
ALIGN_LLM_RESIDENCY_SIM_UPDATE_GOLDEN=1 gmake residency-sim-smoke
```

That switch rewrites the file and prints `residency sim smoke: golden rewritten`; review the diff
before committing it, because the golden is a contract record and not a cache.

**The focused qualification is `gmake residency-sim-qualification`**, which runs
`scripts/run-residency-sim`. It is the run that discharges the roadmap section R3 gate on the real
corpus: it captures one prefill transcript per prompt with the flags and safeguards
`scripts/run-expert-locality-gate` established, derives one `R2_ACTIVATION_TRACE` per transcript with
`main --expert-trace`, deletes each transcript immediately, derives the `R1_MODEL_IR` once with
`main --model-ir`, and runs `main --simulate-residency` over the result.
The shared capture flags include explicit `-n 0`, and the wrapper reuses R2's historical
compact-axis admission before simulation. An R2c full-axis document is therefore refused rather
than changing the measured six-slot demand stream under the old R3 capability name.

```sh
ALIGN_LLM_GGUF_MODEL=/path/to/moe-model.gguf \
ALIGN_LLM_LLAMA_EVAL_CALLBACK=/path/to/llama-eval-callback \
  gmake residency-sim-qualification
```

| Variable | Default | Meaning |
| --- | --- | --- |
| `ALIGN_LLM_GGUF_MODEL` | none | a **MoE** GGUF; the subject model |
| `ALIGN_LLM_LLAMA_EVAL_CALLBACK` | none | the callback instrument executable |
| `ALIGN_LLM_LOCALITY_PROMPTS` | `eval/prompts/expert-locality-v1.txt` | the prompt corpus, one prompt per line |
| `ALIGN_LLM_LOCALITY_PROMPT_COUNT` | `40` | prompts to use, taken from the **top** of the corpus in file order |
| `ALIGN_LLM_RESIDENCY_BUDGET` | 25 per cent of the model's expert byte footprint | the `BUDGET_BYTES` operand |
| `ALIGN_LLM_RESIDENCY_SIM_UPDATE_GOLDEN` | unset | owner-only; `1` rewrites the checked-in golden instead of comparing against it |

**The opt-in is over exactly the two variables that name the subject.** Neither has a default,
because a qualification that silently passes when its subject is missing is worse than no
qualification. A missing or unusable subject prints exactly one of these lines, in this order, and
exits 0 without claiming a measurement; the line must be quoted as the `N/A` reason in the pull
request:

```text
residency sim qualification: N/A (ALIGN_LLM_LLAMA_EVAL_CALLBACK unset)
residency sim qualification: N/A (ALIGN_LLM_LLAMA_EVAL_CALLBACK is not executable)
residency sim qualification: N/A (ALIGN_LLM_GGUF_MODEL unset)
residency sim qualification: N/A (ALIGN_LLM_GGUF_MODEL is absent)
```

The other three variables are **overrides, not switches**: they have defaults, and a corpus this
script was pointed at and cannot read is a broken invocation that exits 1, never `N/A`.

**The qualification is a measurement, not a pass/fail owner test.** It exits 0 on all three
`verdict.result` values — `BEATS_BASELINE`, `NO_POLICY_BEATS_BASELINE`, and `NO_HEADROOM` are all
answers to the roadmap question — and exits nonzero only when the instrument, the corpus, or a
parser prevented a measurement from being taken. It prints human tables and one machine-readable
final line:

```text
residency-sim verdict=... budget=... baseline_bytes=... best=... best_bytes=... gain_per_mille=...
  headroom_per_mille=... jackknife_folds=... jackknife_min_per_mille=... jackknife_stable=...
  demands=... token_positions=... distinct_keys=... slot_coverage_per_mille=...
```

It deliberately joins no aggregate — not `HOSTED_CHECK_TARGETS`, not `CAPABLE_ONLY_CHECK_TARGETS`,
and not `ci` — because it needs a multi-gigabyte model and an external instrument that CI does not
have. Its elapsed time is printed as a diagnostic and is not a performance claim; the whole result
compares fetched bytes only.

**Two Align capability requests came out of implementing this module**, both recorded in
`docs/align-requests.md` with fresh sibling probes under the pinned compiler and neither blocking:
**Request 45** (priority high) is a compiler soundness defect — the region checker accepts a move of
a Move-typed field out of a `json.decode`d record through a two-hop field-access chain with no
diagnostic, and the built program corrupts the heap at run time when the decoded record's recursive
`Drop` frees the same string again; the shipped fix is one `.clone()`. **Request 46** is two related
array-shape gaps — a local `array<i64>` passed `borrow mut` into a call inside a `loop` invalidates
the caller's later reads of it, and an `array<i64>` field of a record cannot be element-assigned at
all — which together force every helper here to return owned columns and force one admission block
to be written twice rather than factored into a helper. Read both before restructuring
`src/residency_sim.align`.

### The R3 decode residency gate

`scripts/run-decode-residency-gate` asks the same R3 question of a stream that contains real
generated tokens. The recorded R3 result replayed prefill graphs in decode order and says so
(`docs/specs/r3-residency-sim.md` section 5.2); R2c's patched instrument removed the two limits that
forced it, and this runner is the residency consumer of the same capture
`scripts/run-decode-locality-gate` takes. Its numbers are recorded in
`docs/specs/r3-residency-sim.md` section 8; that section is authoritative for the result and this
one for how to run it. **`scripts/run-residency-sim` is unchanged and still refuses a full-axis
document**, so the historical section 7 measurement cannot be quietly rewritten under this runner's
capture.

It requires the **patched** instrument, exactly as the decode locality gate does.

```sh
ALIGN_LLM_GGUF_MODEL=/path/to/moe-model.gguf \
ALIGN_LLM_LLAMA_EVAL_CALLBACK="$(scripts/llama-eval-callback-toolchain ensure instrument)" \
  scripts/run-decode-residency-gate
```

| Variable | Default | Meaning |
| --- | --- | --- |
| `ALIGN_LLM_GGUF_MODEL` | none | a **MoE** GGUF; the subject model |
| `ALIGN_LLM_LLAMA_EVAL_CALLBACK` | none | the **patched** callback instrument; a compact-axis build is refused by `require_full_router_axes`, not silently measured |
| `ALIGN_LLM_LOCALITY_PROMPTS` | `eval/prompts/expert-locality-v1.txt` | the prompt corpus, one prompt per line |
| `ALIGN_LLM_LOCALITY_PROMPT_COUNT` | `40` | prompts to use, taken from the **top** of the corpus in file order; 1 to 1000, and a value outside that range — `0` included — is an error rather than an empty measurement |
| `ALIGN_LLM_DECODE_STEPS` | `16` | generated tokens per prompt; 1 to 128, and a value outside that range is an error rather than a silent default |
| `ALIGN_LLM_RESIDENCY_BUDGET` | 25 per cent of the model's expert byte footprint | the `BUDGET_BYTES` operand, the same point section 7 recorded; a positive decimal integer in 1..9,223,372,036,854,775 (the simulator's own `MAX_BYTE_TOTAL`), and anything else is an error rather than a diagnostic from the product an hour later |

A missing or unusable model/instrument prints exactly one of these lines, in this order, and exits 0
without claiming a measurement; the line must be quoted as the `N/A` reason in the pull request:

```text
decode residency gate: N/A (ALIGN_LLM_LLAMA_EVAL_CALLBACK unset)
decode residency gate: N/A (ALIGN_LLM_LLAMA_EVAL_CALLBACK is not executable)
decode residency gate: N/A (ALIGN_LLM_GGUF_MODEL unset)
decode residency gate: N/A (ALIGN_LLM_GGUF_MODEL is absent)
```

The other four variables are **overrides, not switches**: a corpus this script was pointed at and
cannot read is a broken invocation that exits 1, never `N/A`.

**Four arms, one budget, one rule.** The capture is `scripts/run-decode-locality-gate`'s, flag for
flag — `-n N --temp 0 --seed 42 -t 4 -fa off -ctk f32 -ctv f32 -nr -c 512` — so the two decode
measurements are taken over the same greedy continuations. The capture logic is **deliberately
duplicated** rather than factored into a shared helper: the two runners differ in their N/A
prefixes, their per-prompt side work (the locality gate also reads a token fingerprint), and their
post-capture admission, and a shared helper could not be adopted by `run-decode-locality-gate` —
a merged, measurement-bearing runner — without putting its recorded output and identity at risk.
The identity claim is therefore **enforced rather than asserted**: `capture-identity` in
`gmake residency-sim-smoke` extracts the instrument invocation, the corpus-identity block, and the
transcript size cap from both files and fails if they differ, and also fails if the extracted
invocation stops containing the flags, so the comparison cannot pass vacuously. A flag added to one
runner and not the other is a smoke failure, not a silent second measurement.

| Arm | Trace list | What it answers |
| --- | --- | --- |
| `mixed` | the documents as captured | a session of short requests, prompt and generation pooled — the regime section 7 was already reading |
| `decode_only` | the same documents with graph 0 projected away | generation alone, with no prompt tokens in the stream |
| `prefill_only` | the same documents with every decode graph projected away | the **coverage control**: prompt tokens alone, at the same full eight-slot axis |
| `decode_head4` | the same documents with graph 0 and every decode graph after the fourth projected away | the **stream-length control**: generation alone at the prefill-only arm's order of length |

The last two arms are what make the first two interpretable, and each removes one confound. R2c
changed *two* things at once against the stream section 7.4 recorded — the router axis went from six
printed slots to all eight, and real decode graphs appeared — so a verdict that moved could be
caused by either. The prefill-only arm holds corpus, budget, admission rule, and slot axis fixed and
removes only the decode graphs. If it agrees with the other arms, the movement is a **coverage**
effect and must not be attributed to decode; only a verdict the prefill-only arm does *not* share is
decode-specific. That control is also much shorter than the decode arms, though — 23,040 demands
against 81,920 — so a verdict that differs could still belong to the cache pressure the longer
stream carries rather than to the phase. The head-4 arm keeps the phase and truncates each
generation to its first `DECODE_HEAD_STEPS` steps, 20,480 demands over 160 positions, so a verdict
it shares with the decode-only arm is not a **length** effect either.

Each list is a **projection for the simulator**, not a second R2A document: exactly the two arrays
`main --simulate-residency` reads — `graphs` and `selections` — are filtered, and every other block
still describes the whole transcript. **The ordinals are kept.** Renumbering them would make the
first decode step a `single_token_first_graph`, which is `docs/specs/r2a-expert-trace.md` section
2.5.6's name for "the transcript cannot tell a one-token prompt from a decode step", and
`graph_phases` would stop being able to state what was replayed.

The projections live in `scripts/residency_projection.py`, **imported by both** this runner and
`scripts/run-residency-sim-smoke`, so the arms the hosted owner checks against the independent
oracle are the arms the real-model runner replays. `projection-binding` in that smoke pins the
import by name and fails if the runner grows a projection of its own. The runner also asserts the
partition — `mixed` demands equal `prefill_only` plus `decode_only`, demand for demand — that
`decode_head4` is a strict subset of `decode_only` carrying exactly four decode graphs per prompt,
and each arm's `graph_phases` census, which is the only field that states *which* phase was
replayed: a projection that filtered nothing, filtered everything, or renumbered an ordinal would
otherwise still produce a well-formed document with plausible byte totals.

**`one_token_working_set_*` is a first-position quantity, not an arm average.**
`src/residency_sim.align` scans the pooled stream until the first demand whose token ordinal is not
0, so the field reports the working set of whichever token position sorts first. In the mixed and
prefill-only arms that is a prompt token; in the two decode arms it is a generated one. Read it as
"a token of this phase demands this much", never as "this arm's tokens demand this much on average".

**Bounds are checked before the instrument runs.** `src/residency_sim.align`'s `MAX_DEMANDS` is
262,144, and the decode half of the capture is known in advance — every decode graph carries one
token, every router slot is printed, and a one-token graph has no token-reduced tail — so
`prompts x steps x n_layer x n_expert_used` is checked against the cap first and names the two knobs
to lower. The exact pooled total, prefill included, is re-checked after the capture, and the section
2.7 simulation-cost product is asserted against `MAX_SIMULATION_STEPS` for every arm before any
replay is launched.

**It is a measurement, not a pass/fail owner test.** It exits 0 on every `verdict.result` of every
arm and exits nonzero only when the instrument, the corpus, or a parser prevented a measurement. It
prints one human block per arm and one machine-readable line per arm:

```text
decode-residency-gate arm=mixed verdict=... budget=... baseline_bytes=... best=... best_bytes=...
  gain_per_mille=... headroom_per_mille=... jackknife_tested=... jackknife_folds=...
  jackknife_min_per_mille=... jackknife_stable=... demands=... token_positions=...
  distinct_keys=... slot_coverage_per_mille=... prefill_graphs=... decode_graphs=...
  single_first_graphs=... one_token_ws_keys=... one_token_ws_bytes=... prompts=... decode_steps=...
```

**`jackknife_tested` is the field that keeps two different zeros apart.** Section 2.8 resamples only
over candidates that clear the pooled effect floor, so when none does, the fold loop never runs and
`jackknife_min_per_mille` is the untested initial `0` rather than a fold that measured no gain.
`jackknife_folds` still reports how many folds the stream is *partitioned* into, which is a property
of the corpus and is true either way. Read `jackknife_min_per_mille` only under
`jackknife_tested=yes`. The sweep table carries no jackknife at all — section 2.8 resamples at the
requested budget only — and the human block says so above the rows.

**`best` is `best_policy`, and it is only a winner when `verdict` is `BEATS_BASELINE`.** On the two
non-winning results the field still names the lowest-byte candidate whenever one fetched fewer bytes
than the baseline, which is section 2.8's shape and not this runner's. The human block marks the row
accordingly and lists every candidate that cleared the pooled effect floor, so a reader can see
whether a win was lost to the jackknife rather than to the floor.

Like every other R2c consumer the gate joins no aggregate, no `Makefile` target, and no CI job.

## alignpack development

R4-ALIGNPACK-LAYER-MAJOR is merged into `main` as PR #125 (head `a7e72dc`, merge `991eab1`); its
authoritative plan is `docs/specs/r4-alignpack-layer-major.md`, which owns the container format,
the contract ledger, the closure matrix, the fixture design, the correction ledger, and the
cell-to-case map. Two CLI arms, three or four operands each:

```sh
./main --pack MODEL.gguf OUT.alignpack                   # document to stdout
./main --pack MODEL.gguf OUT.alignpack DOC.json          # document to DOC.json, summary to stdout
./main --pack-verify MODEL.gguf PACK.alignpack           # document to stdout
./main --pack-verify MODEL.gguf PACK.alignpack DOC.json  # document to DOC.json, summary to stdout
```

`--pack` writes an alignpack v1 container: the model's tensor bytes, unchanged and in the same
order, relaid so that every Model IR block — an attention block, an MLP block, one expert — is a
single contiguous range. **Both forms write the pack**; the optional third operand selects only
where the document goes, and there is no dry-run form. `--pack-verify` re-opens both files, compares
every claimed byte, reads every interior padding byte, and recomputes the sequential-read statistics
from the pack's own tables. Both emit `schema_version: 1` documents, `R4_ALIGNPACK` and
`R4_ALIGNPACK_VERIFY`.

There is no `--force`, no `--arch`, and no `--align` flag: an occupied destination is
`R4_DEST_EXISTS` rather than something a flag makes acceptable, the architecture is the container's
own `general.architecture` exactly as `--model-ir` decides it, and the alignments are properties of
the format recorded in its header. Neither arm reads any environment variable.

**The model inherits the writable-by-the-invoking-user precondition.** `src/alignpack.align` opens
it with `fs.open_rw`, the only random-access constructor Align ships at this pin, so a mode `0444`
model cannot be opened at all — `docs/align-requests.md` Request 21, still `PROPOSED` and
non-blocking, with R4 as its strongest client: this arm never writes the model and still needs
`O_RDWR`.

The narrow durable owner is `gmake alignpack-smoke`. It needs no model, no network, and no reference
tool — `scripts/gguf_fixture.py` writes the same synthetic qwen2 and gpt-oss corpora
`run-model-ir-smoke` drives — so it is in `HOSTED_CHECK_TARGETS`. It also runs
`scripts/alignpack_reader.py`, an independent Python reader written from the specification rather
than from `src/`, over every pack and against a 40-mutation corpus.

One case inside it is **opt-in**, because it attaches a disk image:

```sh
ALIGN_LLM_ALIGNPACK_ENOSPC=1 scripts/run-alignpack-smoke
```

closes `write-to-full-filesystem` by mounting an 8 MiB case-sensitive APFS volume with `hdiutil`
(no root required), filling it, and asserting that `--pack` reports `R4_WRITE_FAILED` and removes
the partial pack. Without the variable, or on a host with no `hdiutil`, it prints one exact `N/A`
line and the rest of the smoke is unaffected.

The named opt-in qualification is `scripts/run-alignpack-qualification`, taking two environment
variables read by the **runner** and never by `main`:

```sh
ALIGN_LLM_GGUF_MODEL=/path/to/model.gguf \
ALIGN_LLM_ALIGNPACK_TMPDIR=/path/to/scratch \
  scripts/run-alignpack-qualification
```

`ALIGN_LLM_GGUF_MODEL` names the model to pack and has no default. `ALIGN_LLM_ALIGNPACK_TMPDIR` is
optional and defaults to a `mktemp -d`; it is resolved with `pwd -P` and **refused if it resolves
inside the work tree**, because this is the only thing in the repository that writes a
multi-gigabyte file and it must never land in a checkout. The runner checks that
`model_size + 1 GiB` is free before writing anything, and removes the pack on every exit path —
success, failure, or signal — then asserts the removal and prints the reclaimed byte count.

A missing or unusable input prints exactly one of these lines, alone, and exits 0 without claiming a
pass; the line must be named as the `N/A` reason in the pull request:

```text
alignpack qualification: N/A (ALIGN_LLM_GGUF_MODEL unset)
alignpack qualification: N/A (ALIGN_LLM_GGUF_MODEL is absent)
alignpack qualification: N/A (ALIGN_LLM_ALIGNPACK_TMPDIR is not a directory)
alignpack qualification: N/A (ALIGN_LLM_ALIGNPACK_TMPDIR resolves inside the work tree)
alignpack qualification: N/A (the destination already exists: <pack>)
alignpack qualification: N/A (insufficient free space: <avail> < <required>)
```

They are checked in that order, so an unset variable is reported before an unusable one and an
occupied destination before a headroom failure — and the destination check runs **before** the
reclaim trap is installed, so a refusal never removes the file it declined to overwrite. A run that
reaches the model emits its own verdicts rather than the pull request authoring them:

```text
alignpack qualification (identity): PASS
alignpack qualification (sequential read): PASS  src 89 ranges / 11130544128 span / 2379786 ppm
                                                 pack 58 ranges / 4677120000 span / 1000000 ppm
alignpack qualification (MoE): N/A - the packed model has no ExpertBlock; see
docs/specs/moe-prereq-discharge.md section 5.5.
```

**The MoE verdict is a rule over the block set the run measured**, not a constant and not a second
environment variable: a model whose pack has `ExpertBlock`s is asserted against the eight conditions
of `docs/specs/moe-prereq-discharge.md` section 3.5 and prints `PASS` with the block count and both
sides' ranges, span, contiguity, and ppm; a model without them prints the `N/A` line above and
neither passes nor fails. On `OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf` it reports 1,024 `ExpertBlock`s
going 3,072 -> 1,024 ranges, 42,394,624 -> 1,000,000 ppm, and 0 -> 1,024 of 1,024 contiguous. **What
stays synthetic is the gpt-oss shape** — a six-member `ExpertBlock`, MXFP4 geometry, split expert
biases, and the fused `ffn_gate_up_exps` — asserted over `scripts/gguf_fixture.py`'s gpt-oss corpus
and still waiting on a real gpt-oss file.

**The peak resident set is not `metrics.peak_window_bytes`.** That field measures the I/O windows
only. Both arms also hold the plan columns and the rendered document, which are proportional to
block and member count: on a synthetic 16,514-block container the document is 26.8 MB and the arm's
peak is 419 MB (`--pack`) or 802 MB (`--pack-verify`) against a `peak_window_bytes` of 262,144. The
specification's section 2.9 records this; do not quote `peak_window_bytes` as a memory bound.

## External buffer spike development

R4.5-EXTERNAL-BUFFER-SPIKE is implemented on branch `agent/r4-5-external-buffer`; its authoritative
plan is `docs/specs/r4-5-external-buffer.md`, which owns the probe record, the contract ledger, the
closure matrix, the fixture design, the correction ledger, and the cell-to-case map. It answers one
question — can quantized weights living in a buffer Align owns be computed by the ggml backend? —
and it answers it as data, in an `R4_5_EXTERNAL_BUFFER`, `schema_version: 2` document. The bump
is MOE-PREREQ-DISCHARGE's (`docs/specs/moe-prereq-discharge.md` section 3.3): `tensor` carries
the member's `slice_index` / `slice_count` pair, and for one plane claimed out of a stacked
expert tensor `ne0`/`ne1` describe the **plane** rather than the tensor the `name` names.

It is **its own executable**, not an arm of `main`, and that is a contract rather than a
convenience: a `link(...)` clause is compile-time and unconditional and Align has no conditional
compilation, so a ggml dependency anywhere in `src/main.align`'s import graph would put `-lggml` on
every link of `main` on every host. `make build` is untouched, and `make check` never compiles these
three modules — `make ggml-spike-smoke` is what does. That target does depend on `make build`,
because its claim cases are taken from a synthetic olmoe container `main --pack` writes rather than
from a hand-forged one that could disagree with the writer about where a plane lives.

```sh
gmake ggml-spike                    # build ggml-spike (stub shim unless ALIGN_LLM_GGML_INCLUDE is set)
gmake ggml-spike-smoke              # the hosted owner; in HOSTED_CHECK_TARGETS
gmake ggml-spike-qualification      # the opt-in real-ggml, real-model qualification
```

Because `ggml-spike-smoke` is a hosted member, it also runs inside the fresh worker image, whose
tool set is curated in `image/fresh/Dockerfile` — 32 system binaries plus the toolchain forwarders,
with no `sort` and no `uname`. Anything the owner or `scripts/build-ggml-shim` shells out to must be
in that set, or be `python3`, or be a shell builtin; see ledger correction C22. The cheap way to
check a new dependency is to run the owner with `PATH` restricted to exactly that list.

Four operand shapes, three to five operands, where `BLOCK` is a block-table index and `MEMBER` is
the member's position **within that block**:

```sh
./ggml-spike PACK.alignpack BLOCK MEMBER                     # document to stdout
./ggml-spike PACK.alignpack BLOCK MEMBER DOC.json            # document to DOC.json, summary to stdout
./ggml-spike PACK.alignpack BLOCK MEMBER DOC.json REF.gguf   # + the bit-exact reference arm
./ggml-spike PACK.alignpack BLOCK MEMBER - REF.gguf          # reference arm, document to stdout
```

**Four environment variables, all read by the two runners and `scripts/build-ggml-shim`, none by any
executable.** There is no third state and no probing of `/opt/homebrew`, because a build input that
changes with the contents of a directory is not reproducible:

```sh
ALIGN_LLM_GGML_INCLUDE=/opt/homebrew/include \   # selects the REAL shim; unset selects the stub
ALIGN_LLM_GGML_LIB=/opt/homebrew/lib \           # where libggml / libggml-base are
ALIGN_LLM_GGUF_MODEL=/path/to/model.gguf \       # the model to pack and use as the reference
  gmake ggml-spike-qualification
```

`ALIGN_LLM_GGML_FORCE` is the fourth, `init | compute | reference`: it rebuilds the **real** shim
with one failure forced, which is the only way to reach `R4_5_GGML_INIT`, `R4_5_COMPUTE`, and
`R4_5_REFERENCE_MISMATCH`. The qualification sets it itself; `scripts/build-ggml-shim` refuses it
without the real shim, and `scripts/run-ggml-spike-smoke` unsets it along with the other two, because
that runner's contract is that it exercises the ggml-free build whatever a developer has exported.

**The stub is not a placeholder.** `scripts/ggml_shim_stub.c` includes no ggml header and names no
ggml symbol, but it answers the ABI probe, the type table, and the alignment pre-check from the same
checked-in data as the real shim — the fenced `R4.5 SHARED SHIM CONTRACT` region is byte-identical in
both files and the smoke asserts that on every run. So `gmake ggml-spike-smoke` runs the whole CLI,
the whole standalone pack reader, every index/shape/alignment check, and **eleven of the sixteen
error codes** for real — including both success forms and every detail of the claim rules, since
steps 7a and 7b sit inside the ggml-free prefix — on a host that has never heard of ggml, against a
synthetic corpus written by `scripts/ggml_spike_fixture.py` and a synthetic olmoe container packed
by `main --pack`. Every case is a checked-in golden document in
`scripts/ggml-spike-golden.jsonl`, compared byte for byte after the timings, the two `mktemp`
paths, and the four allocator-dependent `buffer` fields are rewritten in place:

```sh
ALIGN_LLM_GGML_SPIKE_GOLDEN_UPDATE=1 scripts/run-ggml-spike-smoke   # rewrite the golden
```

The qualification takes an optional `ALIGN_LLM_GGML_SPIKE_TMPDIR` (default `mktemp -d`, refused if it
resolves inside the work tree), an optional `ALIGN_LLM_GGML_SPIKE_SHA256`, and an optional
`ALIGN_LLM_GGML_SPIKE_EXPERT_SHA256`. Like
`run-alignpack-qualification` it writes a multi-gigabyte pack, checks `model_size + 1 GiB` of free
space first, removes the pack on every exit path, and prints the reclaimed byte count. A missing or
unusable input prints exactly one of these lines, alone, and exits 0 without claiming a pass; the
line must be named as the `N/A` reason in the pull request:

```text
ggml spike qualification: N/A (ALIGN_LLM_GGML_INCLUDE unset)
ggml spike qualification: N/A (ALIGN_LLM_GGML_INCLUDE holds no ggml.h)
ggml spike qualification: N/A (ALIGN_LLM_GGML_LIB unset)
ggml spike qualification: N/A (ALIGN_LLM_GGML_LIB is not a directory)
ggml spike qualification: N/A (ALIGN_LLM_GGUF_MODEL unset)
ggml spike qualification: N/A (ALIGN_LLM_GGUF_MODEL is absent)
ggml spike qualification: N/A (ALIGN_LLM_GGML_SPIKE_TMPDIR is not a directory)
ggml spike qualification: N/A (the temporary directory resolves inside the work tree)
ggml spike qualification: N/A (the destination already exists: <pack>)
ggml spike qualification: N/A (insufficient free space: <avail> < <required>)
```

A run that reaches the model **selects both arms out of the pack document it just wrote**, by
`role_id` and never from a path or a variable: the first `AttentionBlock`'s `attn_q` member, then
every member of the first `ExpertBlock` and member 0 of the last one, the latter being the only run
whose `slice_index` is not zero. It then prints two `N/A` lines it will never stop printing, because
each names a half of the gate this spike does **not** discharge — the GPU arm (measured working on
Metal, but it needs a tolerance oracle and a different alignment rule) and discrete VRAM
(unanswerable here). A dense model adds a third, for the expert block it does not have, and a model
with a single `ExpertBlock` one more, for the plane index it cannot vary. Quote them as they are
printed.

**Alignment is compensated, not assumed.** Align ships no aligned allocator, and this host answers
the same reservation with a 32-aligned base on one run and a 16-aligned one on the next
(`docs/align-requests.md` Request 33). The arm over-reserves both device-visible windows by 64 bytes,
lands block byte 0 and the output tensor on a boundary inside them, and re-measures the exact ranges
it hands across the boundary. `R4_5_ALIGNMENT` therefore reports one thing only — a container-chosen
interior offset that is not a multiple of the linked library's `tensor_alignment` — and
`buffer.weights_pad` / `buffer.output_pad` varying between runs of the same input is expected, not a
defect.

## Dense layer forward development

R5A-DENSE-LAYER-FORWARD is **implemented, owner-verified, and qualified against the real model**
on branch `agent/r5a-dense-layer-forward`; its authoritative plan is
`docs/specs/r5a-dense-layer-forward.md`, which owns the probe record, the contract ledger, the
closure matrix, and the fixtures, qualification, metrics, deferrals, risks, and candidate requests.
It answers the second of R5's three gate stages — a single Qwen2 dense layer, CPU only — computed by
ggml over weights, topology, and scalars that Align owns, checked against `llama-eval-callback`'s
own numbers for the same tokens, in an `R5_LAYER_FORWARD`, `schema_version: 1` document.

It ships as a **new arm of the existing `ggml-spike` executable**, `--layer-forward`, not as a new
`align-runtime` binary: the link boundary, the device/backend prologue, and the alignment pre-checks
are `r4-5-external-buffer.md`'s and stay singular, and `align-runtime` remains a name the roadmap's
loader-bearing product claims later, not a name this one-layer arm takes early.

```sh
gmake ggml-spike                    # unchanged; also builds the --layer-forward arm
gmake layer-forward-smoke           # the hosted owner; in HOSTED_CHECK_TARGETS
gmake layer-forward-qualification   # the opt-in real-ggml, real-model, real-instrument qualification
```

The R4.5 arms are unchanged. `--layer-forward` is selected by its exact first operand, five to eight
operands, `LAYER` a non-negative index and `TOKENS` one to six comma-separated token ids
(`MAX_PREFILL_TOKENS = 6`, an oracle limit — `llama-eval-callback` elides tensor rows past six —
not an arithmetic one):

```sh
./ggml-spike --layer-forward PACK LAYER GEOM.json TOKENS                              # to stdout
./ggml-spike --layer-forward PACK LAYER GEOM.json TOKENS DOC.json                     # to DOC.json
./ggml-spike --layer-forward PACK LAYER GEOM.json TOKENS DOC.json REF.gguf            # + self-reference oracle
./ggml-spike --layer-forward PACK LAYER GEOM.json TOKENS DOC.json REF.gguf TRANSCRIPT.txt   # + tolerance oracle
./ggml-spike --layer-forward PACK LAYER GEOM.json TOKENS -         REF.gguf TRANSCRIPT.txt   # document to stdout
```

`GEOM.json` is an **`R1_MODEL_IR` document at `schema_version: 2`** — what `main --model-ir` emits,
and what the qualification feeds straight into the arm; the alignpack carries no hyperparameters.
Only its `model` object is read, and `rms_eps` / `rope.freq_base` are taken only from the
`_bits` fields, which are lowercase eight-character IEEE-754 hex strings: a rendered float is never
trusted as the value. A `_bits` string that names a NaN, an infinity, or a negative — and, for
`freq_base`, a zero — is `R5_GEOMETRY` naming the field, because `ggml_rms_norm` asserts
`eps >= 0.0f` and `GGML_ASSERT` is `abort()` (plan section 6, correction C17).

**Env vars, all read by `scripts/run-layer-forward` and reused unchanged from R4.5 where named:**

```sh
ALIGN_LLM_GGML_INCLUDE=/opt/homebrew/include \       # selects the REAL shim; unset selects the stub
ALIGN_LLM_GGML_LIB=/opt/homebrew/lib \               # where libggml / libggml-base are
ALIGN_LLM_GGUF_MODEL=/path/to/model.gguf \           # the model to pack and use as the reference
ALIGN_LLM_LLAMA_EVAL_CALLBACK=/path/to/llama-eval-callback \   # new: the tolerance-oracle instrument
  gmake layer-forward-qualification
```

**The four instrument flags are contractual, not an invocation detail**, because three of the
instrument's defaults compute a graph R5A does not (flash attention, an f16 KV cache, and CPU weight
repacking):

```sh
-fa off -ctk f32 -ctv f32 -nr -c 512
```

The qualification captures the transcript with exactly these flags plus `-ngl 0`, and asserts
`nodes_matched == nodes_expected == 18` **and** `elements_compared == 1116` so a future build that
renames, reshapes, or truncates a node fails loudly (`R5_ORACLE_MISSING`/`R5_ORACLE_SHAPE`) rather
than silently comparing fewer elements: a matched node that carries fewer printed elements than its
own declared shape yields is `R5_ORACLE_MISSING` with detail `node[<id>]<got>/<expected>`.

The same rule now has a third code. `llama-eval-callback` prints a tensor's rows in full only while
`ne1 <= 6`, so above six prefill tokens both prefill arms compare a **clamped** six of the rows they
name. Since R6 lifted `MAX_PREFILL_TOKENS` to 8, `--layer-forward` and `--model-forward` refuse a
prefill of 7 or 8 tokens **when a transcript is supplied**, at their token stage and before any
container work, with `R5_ORACLE_TRUNCATED` and detail `tokens[<n>]`. The same token count without a
transcript is admitted; nothing about the arithmetic changed.

**The shim is built with `-ffp-contract=off`**, and both runners assert `abi.fp_contract_off` is
`true`. That is a correctness flag, not an optimisation preference: `a * b + c` contracts into one
fused multiply-add under Apple clang on `arm64` and does not under GCC 13 on `x86-64`, and the stub
engine's kernels are what `scripts/layer-forward-golden.jsonl` is generated from (plan section 6,
correction C15).

`layer-forward-qualification` is opt-in and capable-only, in **neither** `HOSTED_CHECK_TARGETS` nor
`CAPABLE_ONLY_CHECK_TARGETS` — the same footing as `alignpack-qualification` and
`ggml-spike-qualification`. It prints exactly one `N/A` line and exits 0 when a required input is
missing, the model or instrument is absent, or free space is under the pack's size plus 1 GiB; the
line must be quoted as the `N/A` reason in the pull request. These are the shipped lines, captured
from `scripts/run-layer-forward` itself with each input removed in turn:

```text
layer forward qualification: N/A ALIGN_LLM_GGML_INCLUDE is unset
layer forward qualification: N/A ALIGN_LLM_GGML_LIB is unset
layer forward qualification: N/A ALIGN_LLM_GGUF_MODEL is unset
layer forward qualification: N/A ALIGN_LLM_LLAMA_EVAL_CALLBACK is unset
layer forward qualification: N/A ALIGN_LLM_GGML_INCLUDE is not a directory
layer forward qualification: N/A ALIGN_LLM_GGML_LIB is not a directory
layer forward qualification: N/A ALIGN_LLM_GGUF_MODEL is not a file
layer forward qualification: N/A ALIGN_LLM_LLAMA_EVAL_CALLBACK is not executable
layer forward qualification: N/A the scratch root <path> does not exist
layer forward qualification: N/A free space under <path> is <n> KiB, below the <n> KiB the pack needs
```

The runner also restores the ordinary real shim from its `EXIT`/`HUP`/`INT`/`TERM` trap, so an early
exit inside the forced-failure loop cannot leave a `-DALIGN_GGML_FORCE_*` library in `build/lib` for
whatever runs next (plan section 6, correction C22).

**Adding `layer-forward-smoke` to `HOSTED_CHECK_TARGETS` changes aggregate membership**, so
`CLAUDE.md`'s verification rules select `make ci` for this capability's publication, independent of
whatever selects it for a `.align-revision` change. `layer-forward-qualification` joins no aggregate
and is named explicitly in the pull request instead, exactly as `ggml-spike-qualification` is.

## Model prefill forward development

R5B-MODEL-PREFILL-FORWARD is **implemented, owner-verified, qualified against the real model, and
merged** (PR #128, merge commit `870bf31` on `main`); its authoritative plan is
`docs/specs/r5b-model-prefill-forward.md`, which owns the probe record, the contract ledger, the
closure matrix, and the fixtures, qualification, metrics, deferrals, risks, and candidate-request
sections. It answers the third of R5's three gate stages — a smallest model, CPU only, dense,
prefill only — one prefill of at most six tokens through the whole twenty-eight-layer Qwen2 model,
computed by ggml over weights that live in **one reused Align-owned window**, carrying the residual
stream in **Align-owned buffers** between per-layer graphs, and checked against llama.cpp's own
final logits for the same tokens.

It ships as a **new arm of the existing `ggml-spike` executable**, `--model-forward`, for
`r5a-dense-layer-forward.md` section 3.1's reasons, unchanged: one link boundary, a discharged
prologue, and an `align-runtime` name the roadmap's loader-bearing product claims later. R5A's
promised rename to `align-runtime` "at the R5B boundary, where the loader arrives" is deferred
again: R5B owns a window, not a loader, and the rename now triggers when the executable gains a
residency policy.

```sh
gmake ggml-spike                    # unchanged; also builds the --model-forward arm
gmake layer-forward-smoke           # extended with model-forward rows; unchanged aggregate membership
gmake model-forward-qualification   # the opt-in real-ggml, real-model, real-instrument qualification
```

The R4.5 and R5A arms are unchanged. `--model-forward` is selected by its exact first operand,
takes no `LAYER` operand (R5B computes every layer, in order), and is exactly four, five, six,
eight, or nine operands — **seven is `R5_ARITY`**, because `KV_WIDTH` is not optional metadata
beside the transcript, it is what makes the comparison against that transcript meaningful, so it
travels with it:

```sh
./ggml-spike --model-forward PACK GEOM.json TOKENS                                          # to stdout
./ggml-spike --model-forward PACK GEOM.json TOKENS DOC.json                                 # to DOC.json
./ggml-spike --model-forward PACK GEOM.json TOKENS DOC.json REF.gguf                        # + self-reference oracle
./ggml-spike --model-forward PACK GEOM.json TOKENS DOC.json REF.gguf TRANSCRIPT.txt KV_WIDTH             # + transcript oracle
./ggml-spike --model-forward PACK GEOM.json TOKENS DOC.json REF.gguf TRANSCRIPT.txt KV_WIDTH LOGITS.bin  # + logits oracle
./ggml-spike --model-forward PACK GEOM.json TOKENS -        REF.gguf TRANSCRIPT.txt KV_WIDTH LOGITS.bin  # document to stdout
```

`GEOM.json` is the same **`R1_MODEL_IR` document at `schema_version: 2`** R5A reads, `MAX_PATH_BYTES`,
the `-` document convention, `TOKENS` (1 to 6 comma-separated ids, `MAX_PREFILL_TOKENS = 6`), and
arm selection are `r5a-dense-layer-forward.md` section 3.3's, verbatim. `KV_WIDTH` is new: the
attention width the reference instrument used, a non-negative decimal integer in
`[token_count, 4096]`. It is a fail-closed **operand**, never derived from the transcript — the file
being used as an oracle must not be allowed to silently change the computation it verifies — and the
transcript's own `kq-L` `ne0` is instead validated to equal it (`R5_KV_WIDTH` on the operand,
`R5_ORACLE_SHAPE` on a mismatch).

**Env vars, all read by `scripts/run-model-forward` and reused unchanged from R5A where named:**

```sh
ALIGN_LLM_GGML_INCLUDE=/opt/homebrew/include \       # selects the REAL shim; unset selects the stub
ALIGN_LLM_GGML_LIB=/opt/homebrew/lib \               # where libggml / libggml-base are
ALIGN_LLM_GGUF_MODEL=/path/to/model.gguf \           # the model to pack and use as the reference
ALIGN_LLM_LLAMA_EVAL_CALLBACK=/path/to/llama-eval-callback \   # the transcript-oracle instrument
ALIGN_LLM_LLAMA_DEBUG=/path/to/llama-debug \                   # new: the logits-oracle instrument
ALIGN_LLM_MODEL_FORWARD_TMPDIR=/path/to/scratch \    # where the pack is written; defaults to TMPDIR
  gmake model-forward-qualification
```

`ALIGN_LLM_LLAMA_DEBUG` is the only new environment input R5B adds. It must resolve to a
`llama-debug` build that supports `--save-logits --logits-output-dir`.

**The instrument flag set is contractual across both instruments, not an invocation detail**, and
R5B extends R5A's finding by one clause: the `-nr` (no-repack) flag matters on `llama-debug` too,
not only on `llama-eval-callback`. Without it, `llama-debug`'s logits differ from the pinned run by
0.30 of a logit even though the argmax survives — an oracle whose chosen token agrees while every
logit is wrong by 0.3 is an oracle that would pass a broken implementation:

```sh
-p "def add(a, b):" -n 1 -t 4 -ngl 0 -fa off -ctk f32 -ctv f32 -nr -c 512
```

The qualification runs both instruments with this exact flag set (plus `--save-logits
--logits-output-dir` for `llama-debug`), asserts they agree with each other **before** running the
arm — the f32 sequential sum of the logits file must equal the transcript's own printed
`result_output` sum, and `llama-debug`'s `-tokens.bin` must equal the six token ids — so an
instrument skew is reported as an instrument skew and not as a failing oracle.

**The shim is built with `-ffp-contract=off`**, inherited unchanged from R5A, and both runners
assert `abi.fp_contract_off` is `true`.

`model-forward-qualification` is opt-in and capable-only, in **neither** `HOSTED_CHECK_TARGETS` nor
`CAPABLE_ONLY_CHECK_TARGETS` — the same footing as `layer-forward-qualification`. It prints exactly
one `N/A` line and exits 0 when a required input is missing, the model or either instrument is
absent, or free space under the scratch root is under the pack's size plus 1 GiB. These are
`scripts/run-model-forward`'s own twelve lines, quoted from the shipped runner and final:

```text
model forward qualification: N/A ALIGN_LLM_GGML_INCLUDE is unset
model forward qualification: N/A ALIGN_LLM_GGML_LIB is unset
model forward qualification: N/A ALIGN_LLM_GGUF_MODEL is unset
model forward qualification: N/A ALIGN_LLM_LLAMA_EVAL_CALLBACK is unset
model forward qualification: N/A ALIGN_LLM_LLAMA_DEBUG is unset               # new
model forward qualification: N/A ALIGN_LLM_GGML_INCLUDE is not a directory
model forward qualification: N/A ALIGN_LLM_GGML_LIB is not a directory
model forward qualification: N/A ALIGN_LLM_GGUF_MODEL is not a file
model forward qualification: N/A ALIGN_LLM_LLAMA_EVAL_CALLBACK is not executable
model forward qualification: N/A ALIGN_LLM_LLAMA_DEBUG is not executable      # new
model forward qualification: N/A the scratch root <path> does not exist
model forward qualification: N/A free space under <path> is <n> KiB, below the <n> KiB the pack needs
```

**There is no thirteenth line, and the one that would have been is a failure.** `N/A` means "a
required input is absent from this host", which the runner establishes before it starts either
instrument. Once `llama-debug` has run, exited 0, and been asked for `--save-logits`, a missing
logits blob — or a blob with no companion `-tokens.bin`, which would silently skip the token-id
cross-check — is the instrument disagreeing with its own contract, so the runner prints a `FAIL`
line and exits non-zero:

```text
model forward qualification: FAIL llama-debug exited 0 and wrote no logits file under <dir>
model forward qualification: FAIL llama-debug wrote <blob> but no companion -tokens.bin, so the
token-id cross-check cannot run
```

**Peak RSS is reported, not asserted, and its capture is best-effort.** BSD `time -l` and GNU
`time -v` disagree on both the flag and the output label, and a host may have neither, so the arm
runs directly and the runner probes for a usable wrapper. Where none exists it prints
`model forward qualification: peak RSS not measured — no /usr/bin/time -l or -v on this host` and
every assertion still runs.

`R4_WINDOW_UNAVAILABLE` stays the one error code the closure matrix records as `N/A` for this arm
too (section 4.5): it is not input-reachable, as both R5A and Request 35 already record, because
`buffer(n)` is an advisory reservation that never fails.

**Adding rows to the existing `layer-forward-smoke` target changes no aggregate membership and no
check topology**: R5B extends an existing `HOSTED_CHECK_TARGETS` member rather than adding one, and
`model-forward-qualification` joins no aggregate and is named explicitly in the pull request
instead, exactly as `layer-forward-qualification` and `ggml-spike-qualification` are.

That is the whole claim. **It is not a claim that R5B avoids the fresh-image scope**, and an earlier
draft of this paragraph said so wrongly: adding the `model-forward-qualification` recipe and its
`.PHONY` entry edits the `Makefile`, an executable contract boundary, so
`scripts/verification_scope.py` — the shared classifier of record, whose verdict is the evidence —
returns `{"docs_only": false, "hosted": true, "fresh_focused": true, "fresh_installed": true,
"scope": "fresh-image"}` for the R5B diff. Run the classifier against the exact head rather than
reasoning from either paragraph.

## GPU prefill forward development

R5C-METAL-PREFILL-ARM is the **active** capability on branch `agent/r5c-metal-prefill`, rebased onto
the merged R5B at `main` `870bf31`; it is implemented, reviewed twice, repaired, qualified on a
Metal host, and publication is in progress. Its authoritative plan is
`docs/specs/r5c-metal-prefill.md`, which owns the probe record, the contract ledger, the closure
matrix, and the fixtures, qualification, metrics, deferrals, risks, and candidate-request sections.
It answers `docs/specs/roadmap.md` section R5's required microbenchmark A (transfer + GPU compute)
on unified memory: R5B's same thirty graphs, the same alignpack, and the same **Align-owned weight
window**, handed to the Metal device through `ggml_backend_dev_buffer_from_host_ptr` instead of to
the CPU backend, and checked against R5B's own byte-identical CPU logits vector with a tolerance
bound derived from measurement rather than argued for.

It ships as a **new arm of the existing `ggml-spike` executable, `--model-forward-gpu`**, for
`r5c-metal-prefill.md` section 3.1's reasons: a trailing `--backend metal|cpu` operand was
considered and rejected on arity, validation-order, blast-radius, and precedent grounds, so the
device is selected by which arm is invoked, not by an operand's value. The two arms share R5B's
schedule in `src/model_forward.align` through a new `DeviceKind` parameter; **no stage is
reshaped**.

```sh
gmake ggml-spike                    # unchanged; also builds the --model-forward-gpu arm
gmake layer-forward-smoke           # extended with the GPU arm's rows; unchanged aggregate membership
gmake metal-forward-qualification   # the opt-in real-ggml, real-model, real-GPU, real-instrument qualification
```

`--model-forward-gpu` takes `r5b-model-prefill-forward.md` section 3.3's operand positions and
arity set **unchanged**: exactly four, five, six, eight, or nine operands, seven is `R5_ARITY`, and
every operand keeps R5B's meaning, grammar, and bounds verbatim, including `MAX_PATH_BYTES`, the
`-` convention in the document and transcript positions, `TOKENS` as 1-6 comma-separated ids each
`< n_vocab`, `MAX_PREFILL_TOKENS = 6`, and `KV_WIDTH` in `[token_count, MAX_ATTENTION_WIDTH]` with
`MAX_ATTENTION_WIDTH = 4096` and no default:

```sh
./ggml-spike --model-forward-gpu PACK GEOM.json TOKENS
./ggml-spike --model-forward-gpu PACK GEOM.json TOKENS DOC.json
./ggml-spike --model-forward-gpu PACK GEOM.json TOKENS DOC.json REF.gguf
./ggml-spike --model-forward-gpu PACK GEOM.json TOKENS DOC.json REF.gguf TRANSCRIPT.txt KV_WIDTH
./ggml-spike --model-forward-gpu PACK GEOM.json TOKENS DOC.json REF.gguf TRANSCRIPT.txt KV_WIDTH LOGITS.bin
```

The document kind is a **new** one, `R5_MODEL_FORWARD_GPU` at `schema_version: 1`, deliberately not
a `backend` field on `R5_MODEL_FORWARD` (`r5c-metal-prefill.md` section 3.2): R5B's `IDENTICAL`
verdict must stay unconditional, and `arm-r5b-unchanged` (below) is the mechanical form of that
promise. The GPU document reuses R5B's field layout everywhere it means the same thing and adds a
`device` object, a tolerance-shaped `oracle_logits` block, and wrap timings that have no CPU
meaning (section 3.8).

**Env vars, all read by `scripts/run-metal-forward`, per `r5c-metal-prefill.md` section 5.2 and its
correction C8. All six are required — the runner prints one `N/A` line and exits 0 for any that is
missing:**

```sh
ALIGN_LLM_GGML_INCLUDE=/opt/homebrew/opt/ggml/include \
ALIGN_LLM_GGML_LIB=/opt/homebrew/opt/ggml/lib \
ALIGN_LLM_GGML_BACKEND_DIR=/opt/homebrew/opt/ggml/libexec \
ALIGN_LLM_GGUF_MODEL=/path/to/model.gguf \
ALIGN_LLM_LLAMA_DEBUG=/path/to/llama-debug \
ALIGN_LLM_LLAMA_EVAL_CALLBACK=/path/to/llama-eval-callback \
ALIGN_LLM_METAL_FORWARD_TMPDIR=/path/to/scratch \
  gmake metal-forward-qualification
```

`ALIGN_LLM_GGML_INCLUDE` selects the **real** shim; unset selects the stub. `ALIGN_LLM_GGML_LIB` is
where `libggml` and `libggml-base` are. `ALIGN_LLM_LLAMA_DEBUG` is the logits-oracle instrument and
`ALIGN_LLM_LLAMA_EVAL_CALLBACK` is the transcript one — section 5.2's list omitted the second while
its own assertion table asks for `oracle.layers_matched == 28`, which needs a transcript, and
correction C8 adds it. `ALIGN_LLM_METAL_FORWARD_TMPDIR` is where the pack is written, defaulting to
`TMPDIR`; it is R5B's `ALIGN_LLM_MODEL_FORWARD_TMPDIR` under this arm's own name, not a second,
independent variable.

`ALIGN_LLM_GGML_BACKEND_DIR` is the one genuinely new environment input: R5B never `dlopen`s a
device backend because the CPU backend is built in, while R5C's device is loaded through the
registry (section 3.4). It names the **directory holding `libggml-metal`** — a Homebrew ggml keeps
it in `libexec`, not in `lib` — and it is the **only** directory the run loads a backend from: the
runner exports it to the shim as `ALIGN_GGML_BACKEND_DIR`, and the shim then calls
`ggml_backend_load_all_from_path` instead of `ggml_backend_load_all`, which replaces ggml's search
path rather than adding to it. ggml's own `GGML_BACKEND_PATH` cannot do this — measured on 0.21.0,
it only *adds* one library file, and a bogus one named by it fails to load while the registry still
reports the `MTL0` from the compiled-in directory (correction C17). A directory holding no Metal
plugin is an `N/A` line naming it; a directory that holds one and still yields no GPU device is a
**FAIL**, because the named install is then failing to produce the device it is named for.

`metal-forward-qualification` is opt-in and capable-only, in **neither** `HOSTED_CHECK_TARGETS` nor
`CAPABLE_ONLY_CHECK_TARGETS` — the same footing as `model-forward-qualification`. It prints exactly
one `N/A` line and exits 0 when a required input is missing, **the declared backend directory holds
no Metal plugin**, the model or either instrument is absent, or free space under the scratch root is
below the pack's size plus 1 GiB (section 5.2). **Hosted CI is Linux, where no Metal plugin is
built, so this target is `N/A` there by the backend-directory check** — the intended behaviour, not
a skip. The device question is then answered by running the arm over the synthetic two-layer fixture
and reading its `error_code`, before four and a half gigabytes are packed (correction C8), so the
registry answers it rather than the host's name — and because that registry is scoped to the
declared directory, `R5C_GPU_UNAVAILABLE` there is a failure rather than an absence.

These are the shipped lines, captured from `scripts/run-metal-forward` itself with each input
removed or made wrong in turn:

```text
metal forward qualification: N/A ALIGN_LLM_GGML_INCLUDE is unset
metal forward qualification: N/A ALIGN_LLM_GGML_LIB is unset
metal forward qualification: N/A ALIGN_LLM_GGML_BACKEND_DIR is unset
metal forward qualification: N/A ALIGN_LLM_GGUF_MODEL is unset
metal forward qualification: N/A ALIGN_LLM_LLAMA_DEBUG is unset
metal forward qualification: N/A ALIGN_LLM_LLAMA_EVAL_CALLBACK is unset
metal forward qualification: N/A ALIGN_LLM_GGML_INCLUDE is not a directory
metal forward qualification: N/A ALIGN_LLM_GGML_LIB is not a directory
metal forward qualification: N/A ALIGN_LLM_GGML_BACKEND_DIR is not a directory
metal forward qualification: N/A ALIGN_LLM_GGML_BACKEND_DIR (<path>) holds no libggml-metal library
metal forward qualification: N/A ALIGN_LLM_GGUF_MODEL is not a file
metal forward qualification: N/A ALIGN_LLM_LLAMA_DEBUG is not executable
metal forward qualification: N/A ALIGN_LLM_LLAMA_EVAL_CALLBACK is not executable
metal forward qualification: N/A the scratch root <path> does not exist
metal forward qualification: N/A free space under <path> is <n> KiB, below the <n> KiB the pack needs
```

The device probe no longer has an `N/A` line of its own: once the declared directory holds a Metal
plugin and the registry is scoped to that directory, a missing GPU device is

```text
metal forward qualification: FAIL <dir> holds <dir>/libggml-metal.so and the registry scoped to it
still reports no device of type GPU
```

**No peak-RSS line is printed and none is asserted.** This runner has no RSS probe: bounded memory is
`r5b-model-prefill-forward.md` section 3.10's table, which R5C inherits unchanged because the device
adds no host allocation the arm controls (section 3.10). Report peak RSS as `N/A` rather than looking
for a number this target does not produce.

The runner restores the ordinary real shim from its `EXIT`/`HUP`/`INT`/`TERM` trap, so an early exit
inside its forced-failure loop cannot leave a `-DALIGN_GGML_FORCE_*` library in `build/lib` for
whatever runs next; `scripts/run-layer-forward-smoke` does the same, from correction C18.

**Hosted, the arm is exercised by shim build flavours, not by environment variables.** Every forced
failure this repository ships is a compile-time `-D` macro selected by a named
`scripts/build-ggml-shim` flavour (correction C3), because a shim whose behaviour changes with the
environment is a shim whose golden documents are not reproducible:

* the **default stub** has no ggml at all and stops the arm at step 20 with `R5_GGML_UNAVAILABLE`,
  detail `stub`, exactly as it stops `--model-forward` (correction C6);
* **`engine`** is available and has no GPU device, which is step 20a's `R5C_GPU_UNAVAILABLE`,
  detail `device`. Only this build reaches step 20a; the default stub stops one step earlier;
* **`engine+gpu`** gives it a stub GPU device and reaches the arm's whole successful path, its three
  oracles, and R5B's own codes through it;
* **`engine+gpu+no-host-ptr`**, **`engine+gpu+max-buffer`**, and **`engine+gpu+compute`** reach
  `R5C_NO_HOST_PTR`, `R5C_DEVICE_BUFFER_LIMIT`, and the per-graph teardown cell.

All three `R5C_*` codes are therefore stub-reachable on a host with no GPU (section 4.5), and steps
1-19 stay fully covered without ggml, without Metal, without a model, and without llama.cpp. The
qualification additionally forces `max-buffer` and `no-host-ptr` against the **real** Metal device.

**The shim is built with `-ffp-contract=off`**, inherited unchanged from R5A and R5B, and the runner
asserts `abi.fp_contract_off` is `true`.

**Adding rows to the existing `layer-forward-smoke` target changes no aggregate membership and no
check topology**, and `metal-forward-qualification` joins no aggregate. That is the whole claim and
it is **not** a claim that R5C avoids the fresh-image scope: adding the recipe and its `.PHONY`
entry edits the `Makefile`, an executable contract boundary, so `scripts/verification_scope.py` —
the shared classifier of record, whose verdict is the evidence — is what selects the lane. Run it
against the exact head rather than reasoning from this paragraph.

## MoE layer forward development

R5D-MOE-LAYER-FORWARD is merged as PR #139, merge commit `e312bd7`; it was the design of record on
branch `agent/r5d-moe-layer-forward`, ledger
commit `a85e1fc` after the rebase onto the merged R3 residency simulator at `main` `95c47e7`, with
implementation `7886cee` and review repair `a2e2748`, so every field below is
finalized. Its authoritative plan is `docs/specs/r5d-moe-layer-forward.md`, which owns
the probe record, the contract ledger, the closure matrix, and the fixtures, qualification, metrics,
deferrals, risks, and candidate-request sections. It answers R5's second gate stage for a **routed**
layer — one prefill of at most six tokens through OLMoE `blk.0`, computed by ggml over attention
weights and only the routed experts' planes held in Align-owned buffers, checked against
llama.cpp's own numbers for the same tokens — in an `R5_MOE_LAYER_FORWARD`, `schema_version: 1`
document.

It ships as a **fourth arm of the existing `ggml-spike` executable**, `--moe-layer-forward`, beside
R4.5's positional arm, `--layer-forward`, and `--model-forward`/`--model-forward-gpu`, for
`r5a-dense-layer-forward.md` section 3.1's reasons: the arm shares the pack reader, the FFI module,
the shim, the slot store, the alignment contract, the teardown order, and the summary-block shape
with three siblings. `src/layer_qwen2.align` is **not** extended for OLMoE; the topology lives in a
new module, `src/layer_olmoe.align`, because OLMoE's attention half (QK-norm, no QKV biases) and
Qwen2's (biases, no QK-norm) are a second architecture behind the same node-table shape.

```sh
gmake ggml-spike                        # unchanged; also builds the --moe-layer-forward arm
gmake layer-forward-smoke               # extended with a fourth block; unchanged aggregate membership
gmake moe-layer-forward-qualification   # the opt-in real-ggml, real-model, real-instrument qualification
```

The read schedule is in two phases because the set of expert planes the layer needs is a function of
the router's output, and the router's output is a function of half the layer: phase A reads the
embedding row, the attention members, and the router members into one Align-owned `dense_window`;
Align then decides which experts the tokens reached, entirely on bytes it owns (no strided view is
ever read back — `align_ggml_slot_get` is not stride-aware, and reading one back was the probe's own
bug, section 2.8 of the ledger); and phase B reads only the selected claims and computes the expert
half. `--moe-layer-forward` is selected by its exact first operand, has **no `LAYER` operand** (it
computes layer 0; section 5.4 of the ledger records the cost and what adding one would take), and is
exactly five, six, seven, or eight operands:

```sh
./ggml-spike --moe-layer-forward PACK GEOM.json TOKENS                              # to stdout
./ggml-spike --moe-layer-forward PACK GEOM.json TOKENS DOC.json                     # to DOC.json
./ggml-spike --moe-layer-forward PACK GEOM.json TOKENS DOC.json REF.gguf            # + self-reference and routing oracles
./ggml-spike --moe-layer-forward PACK GEOM.json TOKENS DOC.json REF.gguf TRANSCRIPT.txt   # + tolerance oracle
./ggml-spike --moe-layer-forward PACK GEOM.json TOKENS -        REF.gguf TRANSCRIPT.txt   # document to stdout
```

`GEOM.json` is the same **`R1_MODEL_IR` document at `schema_version: 2`** the other arms read, with
two fields this arm is the first consumer of: `n_expert_used` (the slot count of every MoE tensor)
and `n_ff_exp` (the expert planes' inner width). `MAX_PATH_BYTES`, the `-` document convention, and
`TOKENS` (1 to 6 comma-separated ids, `MAX_PREFILL_TOKENS = 6`) are `r5a-dense-layer-forward.md`
section 3.3's, verbatim; the prompt `"def add(a, b"` (not `"def add(a, b):"`) is used because
OLMoE's tokenizer produces seven ids for the latter, one over the cap.

**Env vars, read by `scripts/run-moe-layer-forward` and reused unchanged from `run-layer-forward`
where named:**

```sh
ALIGN_LLM_GGML_INCLUDE=/opt/homebrew/include \                # selects the REAL shim; unset selects the stub
ALIGN_LLM_GGML_LIB=/opt/homebrew/lib \                        # where libggml / libggml-base are
ALIGN_LLM_GGUF_MODEL=/path/to/olmoe.gguf \                    # the OLMoE model to pack and use as the reference
ALIGN_LLM_LLAMA_EVAL_CALLBACK=/path/to/llama-eval-callback \  # the tolerance- and routing-oracle instrument
ALIGN_LLM_MOE_LAYER_FORWARD_TMPDIR=/path/to/scratch \         # where the pack is written; defaults to TMPDIR
ALIGN_LLM_MOE_LAYER_FORWARD_EXCERPT_UPDATE=1 \                # refreshes the checked-in transcript excerpt
  gmake moe-layer-forward-qualification
```

`moe-layer-forward-qualification` is opt-in and capable-only, in **neither** `HOSTED_CHECK_TARGETS`
nor `CAPABLE_ONLY_CHECK_TARGETS` — the same footing as `layer-forward-qualification` and
`model-forward-qualification`. It reuses `run-layer-forward`'s `na()` detail strings verbatim (unset
or non-directory `ALIGN_LLM_GGML_INCLUDE`/`ALIGN_LLM_GGML_LIB`, non-file `ALIGN_LLM_GGUF_MODEL`,
non-executable `ALIGN_LLM_LLAMA_EVAL_CALLBACK`, an absent scratch root, insufficient free space) and
adds one line of its own, for a model whose `arch` is not `olmoe`:

```text
moe layer forward qualification: N/A ALIGN_LLM_GGUF_MODEL is not an olmoe model
```

The free-space guard is `run-layer-forward`'s own formula, `need_kib = model_bytes / 1024 +
1048576`; on `OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf` that is 5,163,334 KiB.

**The corpus is a new `--moe` mode of `scripts/layer_forward_fixture.py`**, not of
`gguf_fixture.py`: the latter synthesizes olmoe *geometry* only, while the former writes an alignpack
v1 container directly with real F32 members, at `n_expert 8` / `n_expert_used 3` matching
`gguf_fixture.py`'s `OLMOE_BASE`. At that `n_expert_used`, the router's slot axis is 3 — `<= 6` — so
the synthetic corpus is the only place the routing oracle's *full* print coverage is reachable; the
real model structurally truncates 12 of 48 selected expert ids (ledger section 2.2 fact 6).

**R5D adds no smoke target and changes no aggregate membership**; it does add one Makefile target,
the opt-in `moe-layer-forward-qualification`. A separate `moe-layer-forward-smoke` target would add a
`HOSTED_CHECK_TARGETS` member, which `docs/specs/check-gate-topology.md` and the `Makefile`'s own
comment record as a check-topology change selecting `make ci` for publication; R5D's fourth
`layer-forward-smoke` block keeps the topology fixed, so `make ci` is not selected.
`moe-layer-forward-qualification` joins no aggregate and is named explicitly in the pull request,
exactly as its three siblings are — but a `Makefile` edit is still an executable-contract boundary,
so `scripts/pre-pr` selects the **executable** row and the installed profile, not the documentation
lane (ledger section 6, correction C15).

The shim gains five new `extern` symbols (`argsort`, `mul_mat_id`, `view_2d`, a 3-D stacked-tensor
constructor, and a 2-D i32 constructor) and one widened one (`soft_max_ext` with `mask == -1` meaning
no mask); `src/ggml_ffi.align` remains the only file with an `extern` block or an `unsafe` block, and
the `BEGIN/END R4.5 SHARED SHIM CONTRACT` region stays byte-identical (ledger section 4.2). **The
shim is built with `-ffp-contract=off`**, inherited unchanged from R5A, and the runner asserts
`abi.fp_contract_off` is `true`.

## MoE whole-model prefill development

R5E-MOE-MODEL-PREFILL is the design of record on branch `agent/r5e-moe-model-prefill`, ledger commit
`5e3356d`, implementation `053de09`, review repair `e7f727f`, merged with the merged R5D at `main`
`e312bd7`. Its authoritative plan is `docs/specs/r5e-moe-model-prefill.md`, which owns the probe
record, the contract ledger, the closure matrix, and the fixtures, qualification, metrics,
deferrals, risks, and candidate-request sections. It completes R5's second gate stage: a **whole**
sixteen-layer OLMoE prefill of at most six tokens, per-layer routing, only the routed experts' planes
read into Align-owned buffers, the output head, and an `R5_MOE_MODEL_FORWARD`, `schema_version: 1`
document.

It ships as a **fifth arm of the existing `ggml-spike` executable**, `--moe-model-forward`, beside
R4.5's positional arm, `--layer-forward`, `--model-forward`/`--model-forward-gpu`, and
`--moe-layer-forward`, and it reuses `src/layer_olmoe.align` — R5D's topology module, extended with
layer-parameterized tables — rather than adding a second OLMoE description.

```sh
gmake ggml-spike                        # unchanged; also builds the --moe-model-forward arm
gmake layer-forward-smoke               # extended with a fifth block; unchanged aggregate membership
gmake moe-model-forward-qualification   # the opt-in real-ggml, real-model, two-instrument qualification
```

`--moe-model-forward` is selected by its exact first operand and takes exactly five, six, seven,
eight, or nine operands — there is no arity gap:

```sh
./ggml-spike --moe-model-forward PACK GEOM.json TOKENS KV_WIDTH
./ggml-spike --moe-model-forward PACK GEOM.json TOKENS KV_WIDTH DOC.json
./ggml-spike --moe-model-forward PACK GEOM.json TOKENS KV_WIDTH DOC.json REF.gguf
./ggml-spike --moe-model-forward PACK GEOM.json TOKENS KV_WIDTH DOC.json REF.gguf TRANSCRIPT.txt
./ggml-spike --moe-model-forward PACK GEOM.json TOKENS KV_WIDTH DOC.json REF.gguf TRANSCRIPT.txt LOGITS.bin
./ggml-spike --moe-model-forward PACK GEOM.json TOKENS KV_WIDTH DOC.json REF.gguf -              LOGITS.bin
```

**`KV_WIDTH` is mandatory and is operand five**, unlike R5B's optional trailing width, because on a
routed model the declared attention width changes which experts the router selects and therefore
which bytes the arm reads (ledger section 2.8). `-` is legal in exactly two positions: the document
position, where it is R0's write-to-stdout convention, and the transcript position, where it means
the transcript oracle does not run while the logits oracle still does. `-` anywhere else is
`R5E_PATH`.

**Env vars, read by `scripts/run-moe-model-forward`:**

```sh
ALIGN_LLM_GGML_INCLUDE=/opt/homebrew/include \                # selects the REAL shim; unset selects the stub
ALIGN_LLM_GGML_LIB=/opt/homebrew/lib \                        # where libggml / libggml-base are
ALIGN_LLM_GGUF_MODEL=/path/to/olmoe.gguf \                    # the OLMoE model to pack and use as the reference
ALIGN_LLM_LLAMA_EVAL_CALLBACK=/path/to/llama-eval-callback \  # the transcript and routing oracles
ALIGN_LLM_LLAMA_DEBUG=/path/to/llama-debug \                  # the byte-exact logits oracle
ALIGN_LLM_MOE_MODEL_FORWARD_TMPDIR=/path/to/scratch \         # where the pack is written; defaults to TMPDIR
ALIGN_LLM_MOE_MODEL_FORWARD_EXCERPT_UPDATE=1 \                # refreshes the checked-in transcript excerpt
  gmake moe-model-forward-qualification
```

`ALIGN_LLM_MOE_MODEL_FORWARD_TMPDIR` is deliberately **not** an N/A condition: it selects a location
and defaults to `TMPDIR`. The other five are, along with a model whose `arch` is not `olmoe` and a
scratch root with less than `model_bytes / 1024 + 1048576` KiB free — 5,163,334 KiB for
`OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf`.

**The qualification runs the arm twice**, once at the instrument's reconciliation width (256 on this
model at `-c 512`) with the transcript, and once at the runtime width (`KV_WIDTH == token_count`)
with `-` in the transcript position, so the arm rather than the runner produces the runtime-width
logits verdict. It asserts the tokenizer produced the six expected ids and that the two instruments
agree with each other **before** invoking the arm, so an instrument skew is reported as an instrument
skew rather than as a failing oracle.

**R5E adds no smoke target and changes no aggregate membership**; like R5D it adds one opt-in
Makefile target, `moe-model-forward-qualification`, and its owner is `layer-forward-smoke`'s fifth
block. A `Makefile` edit is still an executable-contract boundary, so `scripts/pre-pr` selects the
**executable** row and the installed profile rather than the documentation lane. The FFI boundary
does **not** change: R5E adds no `extern` symbol and neither C shim gains one.

## The `--decode-step` arm (R6-DECODE-KV-STEP1)

`docs/specs/r6-decode-kv-step1.md` is the authoritative ledger. R5B computes a whole prefill and
stops: `src/model_forward.align` opens three fresh `ggml_context`s per graph and frees them at the
end of that graph, so every K and V it produces dies with its graph and the model can answer "what
are the logits for this prompt" and not "what comes next". This arm adds the smallest thing that
changes that — an **Align-owned KV plane**, host bytes carrying every layer's post-RoPE K and its V
across the graph boundary, and one decode step at `n_past = T` that reads them.

The arm lives in a new module, `src/decode_step.align`, for `r5b-model-prefill-forward.md` section
5.5's reason (the checker's per-function cost is superlinear in body length and
`src/model_forward.align` is already 4,500 lines). It imports the container reader, the plan, the
member tables, the window discipline, the digests, and every renderer that means the same thing.

```sh
gmake ggml-spike                 # unchanged; also builds the --decode-step arm
gmake layer-forward-smoke        # extended with a fifth block; unchanged aggregate membership
gmake decode-step-qualification  # the opt-in real-ggml, real-model, real-instrument qualification
```

`--decode-step` is selected by its exact first operand and is five, six, seven, nine, or ten
operands. **Eight is `R6_ARITY`**, inherited verbatim from `--model-forward` and for the same
reason: `KV_WIDTH` travels with the transcript.

```sh
./ggml-spike --decode-step PACK GEOM.json TOKENS                                      # to stdout
./ggml-spike --decode-step PACK GEOM.json TOKENS DOC.json                             # to DOC.json
./ggml-spike --decode-step PACK GEOM.json TOKENS DOC.json REF.gguf                    # + the byte-plane self-reference
./ggml-spike --decode-step PACK GEOM.json TOKENS DOC.json REF.gguf TRANSCRIPT.txt KV_WIDTH
./ggml-spike --decode-step PACK GEOM.json TOKENS -        REF.gguf TRANSCRIPT.txt KV_WIDTH LOGITS.bin
```

`TOKENS` is the **prefill**; the decoded token is never an operand. The arm computes it as its own
prefill's `argmax`, because an operand would let a caller pass a token llama.cpp did not sample and
the transcript oracle would then compare two different sequences and still report `PASS`.
`KV_WIDTH` is fail-closed with **no default at any arity**: its range is `T + 1 .. 4096`, and below
nine operands it is simply not supplied and the run is refused at step 6 with `R6_KV_WIDTH` detail
`kv_width[-1]`. The lower bound is `T + 1` and not `T` because the step's own column has to fit.
`TRANSCRIPT` accepts `-` for "no transcript", exactly as `--model-forward`'s does.

**The transcript must hold two graphs.** `llama-eval-callback -n 1` emits a prefill graph and then a
decode graph, and every node name repeats across them; the arm skips the first, because comparing
its decode graph against llama.cpp's prefill graph would agree on the seven nodes that do not depend
on the KV cache and could still report `PASS`. `layer_forward.scan_transcript_after` is that
instruction and counts graphs by the `embd` header every graph begins with.

**The sampler is pinned and it is not optional.** Measured (ledger section 3.1): two runs with
default sampling produce byte-identical prefill graphs and **different** decode graphs, because a
different token is sampled. `scripts/run-decode-step` passes `--temp 0 -s 0` contractually.

**Env vars, read by `scripts/run-decode-step`:**

```sh
ALIGN_LLM_GGML_INCLUDE=/opt/homebrew/include \                # selects the REAL shim; unset selects the stub
ALIGN_LLM_GGML_LIB=/opt/homebrew/lib \                        # where libggml / libggml-base are
ALIGN_LLM_GGUF_MODEL=/path/to/qwen2.5-coder-7b.gguf \         # the dense Qwen2 model, also the byte reference
ALIGN_LLM_LLAMA_EVAL_CALLBACK=/path/to/llama-eval-callback \  # R2c-patched; oracle A's instrument
ALIGN_LLM_LLAMA_DEBUG=/path/to/llama-debug \                  # the prefill's byte-exact logits blob
ALIGN_LLM_DECODE_STEP_TMPDIR=/path/to/scratch \               # where the pack is written; defaults to TMPDIR
  gmake decode-step-qualification
```

`decode-step-qualification` is opt-in and capable-only, in **neither** `HOSTED_CHECK_TARGETS` nor
`CAPABLE_ONLY_CHECK_TARGETS` and in no aggregate — the same footing as its three siblings. It prints
one explicit `N/A` line naming the missing input and exits 0 rather than skipping silently.

**Instrument provenance is load-bearing.** Ledger section 3.1 measured the same llama.cpp commit
built two ways producing two different 608,256-byte logits blobs, so `llama-debug` must be the
pinned Homebrew build 10566 (`bb4caa754`) that `scripts/run-model-forward` already resolves, and
`llama-eval-callback` must be the R2c-patched instrument
`scripts/llama-eval-callback-toolchain ensure instrument` materializes.

**Three acceptance oracles. `r6-decode-kv-step1.md` section 2.11 states the rule; this is a
summary, not a second copy of it.** Oracle A compares every comparable node of llama.cpp's own
decode graph at one ten-thousandth — the instrument's `%12.4f` printing precision — over every layer
plus the head. Oracle B compares the K and V the decode graph **actually consumed**, read back after
compute, against the bytes the prefill wrote into the plane, byte for byte; it is the one that tests
what this capability adds, because a transposed axis, an off-by-one stride, or a K/V swap is
numerically plausible and survives A's four printed decimals. Oracle C compares the step's logits
against this arm's own single-shot `T+1` prefill and is **byte identity**. B and C must hold on every
prompt unconditionally; an A `FAIL` is admitted only inside the 0.5 characterization bound **and**
with C byte-identical on that prompt, which attributes it to llama.cpp's own kernel selection.

There is still no byte-exact **external** reference for the incremental step — `llama-debug
--save-logits` performs exactly one `llama_decode` and `-n` is inert for it. Ledger section 3.2
argued that a single-shot `T+1` prefill could not stand in for one either, and **section 5.1
measured that for this arm it does**: our decode step at `n_past = T`, our own `T+1` prefill, and
`llama-debug`'s blob on the extended prompt are the same 608,256 bytes. Section 3.2's divergence is
llama.cpp's own, between its two paths; read the two sections together and do not cite 3.2 alone.

**The hosted corpus is a second implementation.** `scripts/layer_forward_fixture.py --model` gained
a decode mode: a pure-Python decode step over the plane its own prefill produced, and a transcript
holding two graphs exactly as the instrument emits them. Both oracles are therefore reachable with
no ggml and no model, and the fifth `layer-forward-smoke` block asserts oracle A `PASS` at
`max_abs_diff` **0** and oracle B `IDENTICAL`.

**`MAX_PREFILL_TOKENS` moves from 6 to 8** (`src/layer_qwen2.align`). The cap's reason is unchanged
and still respected — `llama-eval-callback` prints every row only while `ne1 <= 6` — and it now
binds the prefill pass alone, because a decode graph's per-token tensors have `ne1 = 1`. The two
over-cap smoke fixtures move from seven tokens to nine; `src/layer_olmoe.align` keeps its own cap at
6, because OLMoE is a declared non-goal here.

**The lift is enforced, not just documented.** Above six tokens the instrument prints three leading
and three trailing rows and the scan clamps to six on both sides, so `--layer-forward` and
`--model-forward` **refuse** `T` of 7 or 8 **when a transcript is supplied**, with the new code
`R5_ORACLE_TRUNCATED` and detail `tokens[<n>]`, before any container or graph work. The same token
count without a transcript is admitted, which is what `--decode-step`'s own characterization pass
needs: it runs `--model-forward` at `T + 1` tokens with `-` in the transcript position. Four cases
carry the rule: `lf-/mf-tokens-seven-transcript` refused, `lf-/mf-tokens-eight-no-transcript`
admitted.

**R6 adds no smoke target and changes no aggregate membership**; it adds one Makefile target, the
opt-in `decode-step-qualification`, so `scripts/check-gate-topology`'s byte-literal `EXPECTED` does
not move and `make ci` is not selected by a topology change. A `Makefile` edit is still an
executable-contract boundary, so `scripts/pre-pr` selects the executable row and the installed
profile.

The shim gains **one** new `extern` symbol, `align_ggml_op_concat`, with its real body and its stub
kernel; `src/ggml_ffi.align` remains the only file with an `extern` block or an `unsafe` block, and
the `BEGIN/END R4.5 SHARED SHIM CONTRACT` region stays byte-identical.

## The aarch64 platform-profile gates

C7 evidence is target-bound, so each required non-x86 environment has its own reviewed profile.
Both gates are named focused qualifications: run them when a change reaches that target's C7 owner
boundary or for an explicit audit. A `.align-revision` change alone does not select either gate;
Align CI owns compiler portability, while align-llm owns only its changed consumer boundary.
Neither gate joins an aggregate.

On `aarch64-apple-darwin`, run the Section 10 profile gate of `docs/specs/check-gate-topology.md`.
`LIBRARY_PATH` is this target's Align build-gate linker input, and the gate fails closed — with the
exact expected value in its diagnostic — when it is absent or different:

```sh
LIBRARY_PATH="$(brew --prefix)/lib:$(brew --prefix openssl@3)/lib:$(brew --prefix zstd)/lib" \
  make darwin-profile-gate
```

It validates host identity (Darwin, native `arm64`, untranslated), a clean repository head, the
managed toolchain digests at the pin, the Homebrew `llvm`/`openssl@3`/`zstd` identities, and the
declared dylib digests; then it runs `check`, `build`, a direct `check-per-unit`,
`persisted-result-smoke`, and `persisted-result-qualification` as bounded children and prints one
canonical JSON identity block. Add `--json-only` when capturing that block. Its own toolchain
identity source is available separately:

```sh
python3 scripts/align-toolchain attest compiler
```

That reads the managed checkout only — it never fetches or builds; run `scripts/align-toolchain
ensure compiler` first if the pin is not materialized yet.

A passing gate run is evidence for the success path only, so the gate's failure paths have their own
focused owner. It imports the gate as a module and substitutes its named seams, so it runs anywhere —
no Homebrew, no managed toolchain, no Darwin host — and it covers construction, malformed toolchain
input, early exit, and cleanup, asserting that each leaves through the one canonical
`darwin profile gate: ERROR <phase> <detail>` prefix line with no partial block on stdout. Like
`scripts/test-align-toolchain` it has no Make target; run both directly when their owners change:

```sh
python3 scripts/test-check-darwin-profile
python3 scripts/test-align-toolchain
```

On `aarch64-unknown-linux-gnu`, the target-local gate is `make persisted-result-smoke` and
`make persisted-result-qualification` run natively against a compiler and runtime built at the exact
pin, after the Section 9 profile's native aarch64 owner has passed at the head being claimed.
Sections 11.1 to 11.3 of `docs/specs/c7-persisted-result.md` hold the profile table and both
discharge records.
