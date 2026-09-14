# Antigravity development and review

Status: implementation plan of record. This is independent developer tooling, outside the
Align product execution graph. No Python dependency is added.

## Contract ledger

| Surface | Contract |
| --- | --- |
| Interactive development | `agy --add-dir "$PWD" --model gemini-3.8-flash-medium` from the repository root starts ordinary development. `AGENTS.md` remains a symlink to canonical `CLAUDE.md`. Read `HANDOFF.md`; use the pinned Make wrappers and existing owner/preflight rules. High effort remains available through `gemini-3.8-flash-high`. agy 1.2.1 remembers model selections in user settings; every entrypoint therefore supplies its model explicitly. The integration does not replace permission, plugin, or authentication settings. |
| Review command | `scripts/review-agy [--base REF] [--output DIRECTORY]`. Base defaults to `origin/main`. Review a clean, nonempty textual merge-base-to-HEAD diff in a new agy conversation, using exactly `gemini-3.8-flash-high` and the repository's `align-llm-reviewer` agent. No resume or fallback model is selected. This command does not run tests, publish reviews, or grant merge approval. |
| Inputs and prerequisites | Bash, Git, jq, and an authenticated agy with `--add-dir`, `--agent`, `--model`, `--output-format stream-json`, and `--print-timeout` support; native acceptance uses agy 1.2.1. The wrapper explicitly adds the physical repository root and its review directory as workspaces, plus the sibling `../align` when its `CLAUDE.md` exists. This is necessary even when agy's reported cwd names the repository. The selected agent lives in `.agents/agents/align-llm-reviewer/agent.md`; its permitted inspection tools are `view_file` and `grep_search`. |
| Validation order | Parse arguments; check dependencies and an integer `AGY_REVIEW_TIMEOUT_SECONDS` from 1 through 9999999 (default 1800); resolve the physical repository root and common Git directory; require a clean worktree; resolve HEAD/base tip/merge base; reject an empty diff or binary changes; require the native agent definition; validate the output location and require it absent; create evidence; invoke agy; check process, stderr, stream, identities, tool use, verdict, and unchanged source. Invalid admission never invokes the model. |
| Evidence ownership | Default directory: `<git-common-dir>/agy-reviews/<HEAD>-<base-tip>`. A caller-selected directory must have an existing parent and be outside the worktree, except beneath its Git common directory. Existing evidence is never overwritten. Directory creation excludes simultaneous cooperative callers for that output. Different output directories are independent explicit invocations; the repository's one-comprehensive-review rule still applies. Do not mutate the checkout during review. |
| Persisted format | `metadata` and `review.log` use version 1 `ALIGN_REVIEW_*` lines: FORMAT, HEAD, BASE_TIP, BASE (merge base), ENGINE (`agy`), MODEL, and SCOPE (`FULL`). `review.log` initially ends in `VERDICT=INCOMPLETE`. Preserve `diff.patch`, `prompt.txt`, raw `events.jsonl`, and `stderr.log` on success or failure. A completed log adds the conversation ID and the complete response, ending in exactly one `ALIGN_REVIEW_VERDICT=CLEAN` or `FINDINGS` line. The caller publishes the required review envelope separately. These local records are not preflight stamps or ancestry attestations. |
| Stream acceptance | Require one initial `init` and one final `result`, matching nonempty conversation IDs, expected model/agent/physical cwd, `SUCCESS`, a positive integer turn count, no denied actions, and a nonempty response. Only `view_file`/`grep_search` tool events are accepted; subagent events are refused. An agy stderr diagnostic is conservatively incomplete: agy 1.2.1 can return exit 0 and `SUCCESS` after a timeout or denied tool. Require exactly one terminal verdict marker in the response. No inference of CLEAN from exit 0, `SUCCESS`, empty findings prose, or missing output. |
| Result and failure | Exit 0 = complete CLEAN; 2 = complete FINDINGS; 1 = admission failure; 3 = failed invocation or incomplete/malformed evidence; 129/130/143 = hangup/interrupted/terminated invocation. A positive timeout bounds this invocation only; preserve incomplete evidence and continue only unfinished scope. On a signal, terminate and reap the CLI process group before returning. No failure publishes a completed verdict. |
| Isolation and limits | The native custom agent exposes inspection tools; the wrapper also rejects evidence of other tool use and source changes. This trusts agy and its installed integrations, and is not an OS security sandbox or protection against a hostile local process. The stream's `init.tools` is agy's global registry even for custom agents; it is not evidence of the selected agent's permitted tools. Source changes are checked cooperatively before and after, not atomically. Ignored files, external processes, model quality, and hosted provider cancellation are not certified by the local record. |
| Metrics and exclusions | No speed, cost, or review-quality claim. Performance floor and benchmark: N/A. Compiler ownership, ABI, product schemas, GPU qualification, and broad product aggregates: N/A; this changes developer orchestration only. |

## Closure and acceptance

The owner is `bash scripts/test-agy-review`. It is deliberately outside product aggregates.

| Path | Implementation | Regression |
| --- | --- | --- |
| Construction and clean/findings completion | `scripts/review-agy`, native agent | `clean`, `findings`, metadata/response assertions |
| Admission and existing evidence | wrapper admission | `dirty`, `empty`, `binary`, `existing-output`, `worktree-output`, `invalid-timeout`, `initial-status-error`, `initial-common-error`, `invalid-base` |
| Malformed, failed, partial, or misidentified output | `scripts/agy-review-result.jq`, wrapper | `malformed`, `provider-exit`, `error-status`, `empty-response`, `missing-verdict`, `duplicate-verdict`, `duplicate-result`, `wrong-model`, `wrong-agent`, `wrong-cwd`, `wrong-conversation`, `denied`, `timeout-warning`, `forbidden-tool`, `trailing-event` |
| Verdict outside code fences | result parser | `open-backtick-fence`, `open-tilde-fence`, `short-closing-fence`, `closed-fences` |
| Changed source and failure finalization | wrapper final check | `changed-source`, `final-status-error`, `final-head-error`; every failed run retains INCOMPLETE |
| Git layout and concurrency identity | common-directory/output admission | `linked-worktree`, `existing-output` |
| Cancellation and cleanup | wrapper signal trap and watchdog | `terminate`, `timeout-expiry`: process-group child is reaped and evidence stays INCOMPLETE |
| Actual provider and useful review | same wrapper and agent | `bash scripts/test-agy-review --live`: an isolated two-commit JavaScript currency-conversion regression must produce FINDINGS, with source unchanged and no denied actions |

Author consistency pass: the ledger owns CLI, evidence, timeout and admission behavior. The guide
and native agent reference it; no publication/classifier or product-language policy is changed.
