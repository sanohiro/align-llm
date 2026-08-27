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
  "schema_version": 1,
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
omit it to preserve the C4 behavior without persistence.

Run it with:

```sh
./main --verify-loop <task.json> <result.json>
```

The loop evaluates the candidate through C3, checks and applies it with `git apply`, then runs
build, targeted-test, and full-test in order. A failed stage is captured with its exit code,
duration, summary, stdout, and stderr. The repair prompt includes that diagnostic and the C3
evaluation document. If a repair patch is configured and the iteration budget permits, it is
checked and applied once, then the next iteration verifies the repaired worktree. The result uses
`PASS`, `GAVE_UP`, `EXHAUSTED`, `REPAIR_FAILED`, or `INVALID` status labels and preserves all
attempts for later provider or failure-memory work.

## Failure-memory development

The C5 slice is `src/failure_memory.align`. When `memory_profile` is configured, each completed
verification appends one JSON object to the profile rather than rewriting a mutable array. The
event records the task and attempted patch, first failed stage/test, root-cause summary, repair
result, successful and unsuccessful strategies, recommended tests, risky symbols, iteration
counts, and risk score. The next run selects up to the three newest events for the same task and
adds them to every repair prompt. A missing or unreadable profile starts with empty context, and a
profile write/decode failure does not replace the already-written verification result.

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
the host has neither) inside a subshell whose `ulimit -f 8192` caps its log at 8 MiB (bash counts
1024-byte blocks), so a reference build that fails to terminate is a bounded failure rather than an
unbounded log. The timeout diagnostic is reported only when one of those wrappers was actually used.

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
the existing Qwen2.5-Coder-7B) exercises the `moe: false` path, and a small MoE GGUF (1-4 GB, not
yet downloaded — a pending user decision) is required to exercise `moe: true` and close the R2
roadmap gate's locality question. `ALIGN_LLM_LLAMA_EVAL_CALLBACK` names the callback instrument
executable.

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
alignpack qualification (MoE): N/A - no gpt-oss GGUF on this host; see
docs/specs/r4-alignpack-layer-major.md section 4.5.
```

**The MoE half of the gate is closed only synthetically.** Per-expert contiguity — the case where
this format is worth the most, since one expert's six planes are six scattered ranges in a GGUF and
one range in a pack — is asserted over `scripts/gguf_fixture.py`'s gpt-oss corpus. It needs the same
small MoE GGUF the R2 locality gate is waiting for.

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
and it answers it as data, in an `R4_5_EXTERNAL_BUFFER`, `schema_version: 1` document.

It is **its own executable**, not an arm of `main`, and that is a contract rather than a
convenience: a `link(...)` clause is compile-time and unconditional and Align has no conditional
compilation, so a ggml dependency anywhere in `src/main.align`'s import graph would put `-lggml` on
every link of `main` on every host. `make build` is untouched, and `make check` never compiles these
three modules — `make ggml-spike-smoke` is what does.

```sh
gmake ggml-spike                    # build ggml-spike (stub shim unless ALIGN_LLM_GGML_INCLUDE is set)
gmake ggml-spike-smoke              # the hosted owner; in HOSTED_CHECK_TARGETS
gmake ggml-spike-qualification      # the opt-in real-ggml, real-model qualification
```

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
the whole standalone pack reader, every index/shape/alignment check, and **ten of the fifteen error
codes** for real, on a host that has never heard of ggml, against a synthetic corpus written by
`scripts/ggml_spike_fixture.py`. Every case is a checked-in golden document in
`scripts/ggml-spike-golden.jsonl`, compared byte for byte after the timings, the two `mktemp`
paths, and the four allocator-dependent `buffer` fields are rewritten in place:

```sh
ALIGN_LLM_GGML_SPIKE_GOLDEN_UPDATE=1 scripts/run-ggml-spike-smoke   # rewrite the golden
```

The qualification takes an optional `ALIGN_LLM_GGML_SPIKE_TMPDIR` (default `mktemp -d`, refused if it
resolves inside the work tree) and an optional `ALIGN_LLM_GGML_SPIKE_SHA256`. Like
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

A run that reaches the model prints three more `N/A` lines it will never stop printing, because each
names a half of the gate this spike does **not** discharge — an expert block (this host's only model
is dense), the GPU arm (measured working on Metal, but it needs a tolerance oracle and a different
alignment rule), and discrete VRAM (unanswerable here). Quote them as they are printed.

**Alignment is compensated, not assumed.** Align ships no aligned allocator, and this host answers
the same reservation with a 32-aligned base on one run and a 16-aligned one on the next
(`docs/align-requests.md` Request 33). The arm over-reserves both device-visible windows by 64 bytes,
lands block byte 0 and the output tensor on a boundary inside them, and re-measures the exact ranges
it hands across the boundary. `R4_5_ALIGNMENT` therefore reports one thing only — a container-chosen
interior offset that is not a multiple of the linked library's `tensor_alignment` — and
`buffer.weights_pad` / `buffer.output_pad` varying between runs of the same input is expected, not a
defect.

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
