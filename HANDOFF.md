# Session handoff

Read `CLAUDE.md` first. This file records durable execution state; GitHub owns transient pull
request checks, reviews, and attestations.

## Current state

- Branch: `agent/fresh-compiler-topology-redesign-v4`, design head `7b848ea` (`docs: redesign fresh compiler pre-dispatch contract`); base main is `32bfeba55e358d249bab62623e9ea7d5f2cf7c63` (`Add C7 persisted-result design gate (#53)`).
- Active goal: re-scope the common fresh-compiler topology design around the remaining contract gaps, then obtain one clean comprehensive review before any merge or implementation. No dependent implementation or Align pin adoption may start until the design and implementation slices merge.
- Durable design state: Section 9 is the only normative fresh-compiler contract. The v4 slice separates the image-owned supervisor/bootstrap plane from the per-reviewed-head repository worker; the fixed image manifest authenticates image tools/runtime only, while a signed run capsule binds the checked-out head, object format, and worker digest. It defines the exact supervisor fd-4/5/6 boundary, sealed worker/manifest/run snapshots at fd-7/8/9, descriptor-relative source roots with a bounded active descriptor window, canonical source/cache/attestation wires, a worker-owned protected `/run/user/<uid>/align-llm-fresh/lock`, fail-closed orphan handling, executable `/tmp`, fixed resource/cardinality limits, complete Make option rejection, explicit root output-exception metadata, phase-5 Cargo configuration ownership, private Git views, read-only compiler/archive bundle, aggregate overlay, output closure, and exact status/cleanup grammar.
- Complete: the first comprehensive review findings were consolidated in `d5c0317`; the subsequent design audit reopened the closure matrix and the redesign in `7b848ea` moves supervisor dispatch directly to the image bootstrap, adds a no-follow bounded worker snapshot, closes the C/C++ compiler-suite helper/resource/header closure, and reconciles the caller option and compiler-bundle ledgers. Author-side vectors and static checks pass for the redesigned candidate. The conditional final review completed with three P1 and one P2 contract gaps; the candidate is not merge-ready. Not started: bootstrap/image installation, controller implementation, baseline refresh, hosted/capable acceptance, and any `.align-revision` change.

## Next steps

1. Reopen the closure matrix and re-scope Section 9 to preserve the authenticated `ALIGN_REPO` input, force the authoritative `Makefile`, retain the existing coding-task `/tmp` and `/dev/shm` quotas, and synchronize Request 6 with the fresh launcher/cache policy.
2. Batch the design corrections and run the author-side ledger, vector, Markdown, and diff checks. Do not start another local repair/review loop without a re-scoped design decision.
3. Obtain one clean comprehensive review for the re-scoped design; only then open and merge it, install/attest the fixed image supervisor and bootstrap, and create the separate repository implementation slice without changing `.align-revision`.
4. Refresh the identity-bound baseline after the implementation changes Make behavior, run the fresh topology matrix and capable `make ci`, then create the separate Request 6 adoption slice.

## Latest verification

- `git diff --check main...HEAD`: PASS.
- `python3 -c 'import json,re; from pathlib import Path; s=Path("docs/specs/check-gate-topology.md").read_text(); b=re.findall(r"^```json\n(.*?)\n```$", s, re.M|re.S); assert len(b)==11; [json.loads(x) for x in b]'`: PASS — 11 JSON blocks parse.
- `python3 -c 'from pathlib import Path; p=Path("docs/specs/check-gate-topology.md").read_text(); sec=p[p.index("## 9. Fresh compiler transition contract"):]; assert "fresh-bootstrap --mode ci" in sec; assert "is /usr/bin/make --no-print-directory ci" not in sec; assert "fresh_worker_max_bytes = 4194304" in sec; assert "target=/runtime/cc-suite" in sec; assert "four fixed handoff/bundle paths" in sec; assert "--no-print-directory` has the sole accepted option row" in sec; print("topology author consistency: PASS")'`: PASS — direct-bootstrap, worker snapshot, compiler-suite, caller-option, and bundle ledgers agree.
- `python3 -c 'import json,re; from pathlib import Path; s=Path("docs/specs/check-gate-topology.md").read_text(); b=re.findall(r"^```json\n(.*?)\n```$", s, re.M|re.S); assert len(b)==11; [json.loads(x) for x in b]'`: PASS — 11 JSON blocks parse; attestation predicate hashes `211475753df48fa9f8e6ae47b37c516be156ebebf6220433a0585cca723bd6d6` and `2b61df38636af38d36c13f9c6c38265fdd76bb0ad15db2ec0f5ca2f0c0d98e69`; cache/source/object-format vectors match their recorded hashes; fd, lock, bounds, noexec, Make-option, output-exception, and Cargo-phase markers are present.
- `git diff --check`: PASS.
- `awk '/^```/ { count++ } END { if (count % 2 != 0) exit 1 }' HANDOFF.md docs/align-requests.md docs/specs/c7-persisted-result.md docs/specs/check-gate-topology.md`: PASS — 176 fences.
- Source tests, `make check`, `make build`, `make ci`, hosted checks, and benchmarks are N/A because this remains a documentation/specification-only design slice with no executable contract change.

## Blockers and decisions

- `.align-revision` remains `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`; no adoption or compiler pin change is permitted yet.
- Section 9 claims only Ubuntu/Linux x86_64 with executable `/tmp`, delegated cgroup limits, and the named minimum toolchain. C7's required aarch64 Linux and aarch64 macOS environments need separate reviewed platform profiles and implementations.
- Request 7's exact Git 2.45.0 immutable OCI image/job remains a separate prerequisite; do not invent its digest.
- The dependent slice remains blocked until the re-scoped design is cleanly reviewed and merged, then the implementation passes its complete review/check gate. Preserve the run-capsule/image-manifest split, exact supervisor logical request and direct-bootstrap argv, environment scrub, fd 4/5/6 supervisor handoff with worker fd 4/7/8/9 snapshot map, no-follow `fresh_worker_max_bytes = 4194304` worker snapshot, worker-owned protected lock and fail-closed orphan policy, source identity and bounds, private Git views, fixed Cargo configuration, self-contained `/runtime/cc-suite` compiler closure, read-only `/tools/alignc`/archive bundle, and exact status grammar. The re-scope must also carry the authenticated `ALIGN_REPO` selection, pin aggregate Make execution to the authoritative `Makefile`, preserve the coding-task's per-task `/tmp` and `/dev/shm` quotas, and update Request 6's adoption commands to the fresh launcher and fixed cache policy.
- Do not consume `6b5dfaa`, `bb9ad1f`, or any unreviewed topology implementation as an implementation contract until this successor design and its dependent implementation merge. Preserve the no-host-fallback, staged interpreter/loader closure, overlay publication, private Git refs, and empty descriptor propagation decisions.
- The sibling Align checkout is the language source of truth. Do not code against hypothetical Align APIs or update the pin from this design branch.
- Intentional uncommitted files: none in this worktree. Main's separate uncommitted `HANDOFF.md` is intentional and must not be discarded.
