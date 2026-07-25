# Session handoff

A living continuity note for resuming align-llm on another machine or in a fresh Claude Code or
Codex session. Read `CLAUDE.md` first, then this file, then the relevant specifications named below.
Conversation history and per-machine memory are not project state.

_Last updated: 2026-07-25. Active work is the uncommitted C1 provider slice on
`c1-provider-boundary`, based on `bb739d9`._

## Current position

The repository has completed C0 and is implementing C1:

- C0 now has both the evaluator smoke corpus and `coding-v1`, a real off-by-one repair task.
  The coding runner creates the exact pinned Git revision, proves the pre-repair failure, applies a
  separately supplied candidate, enforces allowed edits before and after validation, runs validation
  in a bubblewrap namespace with only its temporary checkout worktree writable and its `.git`
  metadata read-only, retains timeout diagnostics, kills its owned descendant process tree, and
  cleans its temporary checkout. It probes the required bubblewrap namespaces and fails closed when
  Linux child-subreaper support, bubblewrap, or the validation resource wrapper is unavailable;
  validation also has bounded address space, aggregate resident memory, CPU time, file size, process
  count, open files, bounded `/tmp` and `/dev/shm` tmpfs mounts, and writable-worktree
  size/file-count limits. Task-controlled IDs cannot influence temporary paths. Deleted-but-open
  files,
  adopted descendants, directory modes, and bounded resource scans are checked. Post-validation host
  Git checks cannot be configured by the candidate. Fixture and baseline Git subprocesses disable
  both system configuration and system attributes, global attributes are disabled with a fixed
  XDG configuration path, replacement objects are ignored, and NUL-delimited Git paths preserve
  whitespace and newlines. Post-repair validation mutations to even allowlisted files or the Git
  index are rejected by comparing the candidate state before and after validation. Fixture
  symlinks are preserved during materialization, and the immutable baseline oracle binds the
  source commit and artifact manifest as well as measured results.
- `eval/baselines/coding-v1-reference.json` is the first canonical machine-readable baseline. It was
  recorded twice from clean commit `f062daf` after rebuilding `main` with the verified pinned Align
  compiler. It binds the complete declared evaluation artifact set to both SHA-256 digests and the
  source commit, including the verifier itself, while enumerating source inputs explicitly so new
  unrelated modules do not invalidate C0. It records the requested and resolved Python runtime used
  for measurement and is checked against immutable oracle commit `42e6082`. This deterministic
  reference validates scoring and timing, not model quality.
- The refreshed baseline passed 2/2 attempts at 250,806,078 ns and 253,289,429 ns, with median time
  to a passing patch of 252,047,753 ns on the recorded WSL2/AMD Ryzen 9 5950X environment.
- A verify/repair control-loop spike exists in `src/repair.align`, backed by captured and
  timeout-bounded process execution in `src/verify.align`. C1 now adds the provider abstraction,
  three provider adapters, token-count metadata, and a common persisted result format.
- `src/main.align` exposes `--eval`, `--loop`, and `--selfcheck` demonstrations for these slices.
- `.align-revision`, `make ci`, `.github/workflows/ci.yml`, the pull request template, and
  `docs/review-checklist.md` now make the local check, pinned compiler, fixed evaluation, review, and
  merge expectations executable across environments.
- `CLAUDE.md` and `docs/align-requests.md` define the Align request lifecycle, mandatory blocking
  metadata, dependent-slice pause rule, independent-work rule, and real-client resume/closure gate.
- Requests 1 and 3 have real-client closure evidence; Request 2 is shipped at `ALIGN_MERGED`.
  Request 4 is a new proposed blocker only for real chunked SSE acceptance; non-streaming C1 work
  remains independent.
- Current C1 state: Align modules, three provider adapters, common JSON persistence, and the focused
  provider smoke are implemented. The branch still needs commit, PR, independent review, and merge.

The central metric remains time to a passing patch. Do not start align-runtime work before the
fixed evaluation and provider-independent coding-loop gates establish a measurable baseline.

## Completed bootstrap

PR #1, `Bootstrap the measured align-coder development cycle`, merged these intentionally
integrated bootstrap surfaces:

- `AGENTS.md` — Codex compatibility symlink to the canonical `CLAUDE.md`.
- `CLAUDE.md` — shared repository policy, English collaboration rules, mandatory
  PR-review-before-merge workflow, and handoff operation.
- `docs/align-requests.md` — Align responses and align-llm verification for the three shipped
  requests.
- `.align-revision`, `.github/`, `Makefile`, `scripts/`, and `docs/review-checklist.md` — pinned
  compiler, unified local/CI gate, pull request workflow, and shared review checks.
- `eval/tasks/`, `eval/expected/`, and `eval/runners/` — file-backed smoke corpus, deterministic
  score oracle, and runner.
- `src/main.align` — command entry points for the current demonstrations.
- `src/verify.align` — captured, timeout-bounded verification primitives.
- `src/eval.align` — declared JSON corpus loader and first deterministic C0 scorecard slice.
- `src/repair.align` — first provider-independent verify/repair loop skeleton.

The first executable evaluation, loop, CI, request lifecycle, and handoff rules were reviewed as one
bootstrap PR under the one-time exception in `CLAUDE.md`. That exception is now consumed: future
work returns to one roadmap gate or enabling slice per branch and PR. Review follow-ups resolved
diagnostic loss, loop bounds and exit coverage, task-identity checks, empty-corpus acceptance, the
effective compiler pin, request lifecycle evidence, and stale handoff state.

## Latest verification

Verified on 2026-07-25 with pinned Align commit
`db942d2f705546c7d6b8c0334a462548c6446f84`:

```text
make fmt
# PASS — all Align source formatted; the previous dash-incompatible `read -d` recipe was fixed

make ci (using a clean detached checkout of the pinned Align revision)
# PASS — pinned Align revision matches
# PASS — pinned Align compiler and runtime release build is current
# PASS — formatter output matches every Align source file
# PASS — 5 units checked per-unit: project, verify, eval, repair, main
# PASS — executable built as ./main
# PASS — smoke-v1: 2 tasks, 2 PASS, 0 failed; identity and summary oracles match
# PASS — an empty corpus is rejected
# PASS — coding-v1: pinned fixture repair 1/1 PASS; disallowed edits and validation side effects
# rejected, including index-flag-, stat-cache-hidden-, special-mode, and directory-mode mutations;
# ignored fixture inputs and validation side effects rejected; ambient Git and Python settings and
# corpus interpreter dispatch isolated; system and global Git configuration and attributes disabled;
# timeout
# and normal-completion process-tree cleanup,
# descendant reaping, and temporary checkout cleanup verified; missing child-subreaper, bubblewrap
# namespace, or resource wrapper support fails closed; validation cannot mutate the host filesystem or
# Git metadata; Git replacement objects are ignored; pre-validation byte/mode and untracked/ignored
# mutations are rejected; validation `/tmp` and `/dev/shm` tmpfs, process/file/address-space,
# aggregate RSS, deleted-open-FD,
# adopted-descendant, aggregate file-count, and writable-worktree quotas are enforced with bounded
# scans; NUL-delimited Git path handling and whitespace-path regression isolated; symlink fixture
# preservation and post-validation allowlisted-file mutation rejected; non-UTF-8
# diagnostics retained and bounded before buffering; non-passing baseline stdout and stderr
# diagnostics are persisted; concurrent baseline replacement-ref smoke runs are isolated
# PASS — canonical baseline metadata, source commit, artifact digests, immutable oracle, task identity, summaries,
# corpus task order and expected codes, and strictly typed numeric aggregates verified; malformed
# aggregates and verdicts rejected; measured Python runtime, pin checker provenance, and complete
# non-passing results retained
# PASS — loop spike: pass, give-up, stdout-driven repair/reverify, exhaustion, timeout, and
# zero-budget paths match their oracle

for file in eval/runners/run-fixed.sh scripts/check-* scripts/run-eval-invalid-smoke \
  scripts/run-loop-smoke scripts/run-baseline-invalid-smoke scripts/run-coding-task-*; do
  bash -n "$file"
done
# PASS

python3 -m json.tool <each task, manifest, expected summary, and canonical baseline>
# PASS

git diff --check
# PASS
```

## C1 verification

Verified on 2026-07-25 against the existing pinned Align compiler:

```text
make fmt                         PASS
make check                       PASS — 11 imported units, provider modules included
make build                       PASS — executable built as ./main
bash -n scripts/run-provider-smoke  PASS
./scripts/run-provider-smoke     PASS — 3 providers, generate/stream, auth, exact token count, common result format
git diff --check                 PASS
```

`make ci` has intentionally not been rerun for this feature slice; the focused provider gate is the
relevant verification, and CI repetition is not useful while the Align chunked-response capability
remains unshipped.

## Next steps

1. Review the current C1 diff against `docs/review-checklist.md`, commit it, push
   `c1-provider-boundary`, open the PR, and perform an independent adversarial review.
2. Apply any valid findings, rerun only the focused provider verification, then merge the PR with a
   merge commit. Do not repeat the full CI gate unless a concrete issue requires it.
3. After merge, start the next C1 slice. Keep Request 4 as the only blocker for real chunked SSE;
   continue non-streaming provider and result work independently.

## Constraints to preserve

- Use `make check`, `make run`, `make fmt`, and `make build`; do not invent an Align manifest or
  package workflow.
- `make ci` requires a clean sibling checkout at `.align-revision`, builds its release compiler,
  and forces all project gates to use that exact executable. Change the pin deliberately and rerun
  the full gate when adopting a newer Align compiler.
- Canonical baseline recording also rebuilds the pinned compiler and `main`; never measure an
  existing ignored binary. Task wrappers must declare all executable inputs in `artifact_paths`.
- PR #3 must use a merge commit rather than squash so the recorded source commit remains reachable.
- A captured process's stdout and stderr are region-bound views. Clone them before returning owned
  diagnostics, as `src/verify.align` does.
- A Move struct with owned `string` fields cannot currently be a `Result` Ok payload. The current
  `Captured` value therefore stores its run outcome as data and returns as a bare Move struct.
- Bind an owned `string` to an explicit `str` view before passing it through an indirect function
  value.
- Reusable command arguments cross loop iterations as `slice<str>` and are materialized for
  `std.process` per run.
- Provider SSE parsing currently depends on Content-Length framing because Align's shipped
  `std.http` client rejects chunked response bodies; do not add a raw-socket compatibility layer.
- Intentional uncommitted C1 files: `Makefile`, `README.md`, `HANDOFF.md`,
  `docs/align-development.md`, `docs/align-requests.md`, `scripts/run-provider-smoke`, and
  `src/model.align`, `src/provider.align`, `src/provider_http.align`, `src/provider_llama.align`,
  `src/provider_openai.align`, `src/result.align`, `src/main.align`.
- Source, comments, diagnostics, commits, pull requests, reviews, and releases are written in
  English.

## Read next

- `docs/specs/roadmap.md` — delivery order and gates.
- `docs/specs/align-llm.md` — architecture and system principles.
- `docs/align-requests.md` — shipped Align capability details and ownership limits.
- `docs/align-development.md` — local sibling-compiler workflow.
