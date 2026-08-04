# Session handoff

Read `CLAUDE.md` first. This file records durable execution state; GitHub owns transient pull
request checks, reviews, and attestations.

## Current state

- Branch: `agent/fresh-compiler-topology-redesign-v4`, design head `d5c0317` (`docs: close fresh compiler topology review findings`); this handoff is the continuity commit immediately after that design head. Base main is `32bfeba55e358d249bab62623e9ea7d5f2cf7c63` (`Add C7 persisted-result design gate (#53)`).
- Active goal: finish the re-scoped common fresh-compiler topology design, pass its one conditional final review, merge it, implement the reviewed topology slice, and consume it for Request 6 adoption. No dependent implementation or Align pin adoption may start until the design and implementation slices merge.
- Durable design state: Section 9 is the only normative fresh-compiler contract. The v4 slice separates the image-owned supervisor/bootstrap plane from the per-reviewed-head repository worker; the fixed image manifest authenticates image tools/runtime only, while a signed run capsule binds the checked-out head, object format, and worker digest. It defines the exact supervisor fd-4/5/6 boundary, sealed worker/manifest/run snapshots at fd-7/8/9, descriptor-relative source roots with a bounded active descriptor window, canonical source/cache/attestation wires, a worker-owned protected `/run/user/<uid>/align-llm-fresh/lock`, fail-closed orphan handling, executable `/tmp`, fixed resource/cardinality limits, complete Make option rejection, explicit root output-exception metadata, phase-5 Cargo configuration ownership, private Git views, read-only compiler/archive bundle, aggregate overlay, output closure, and exact status/cleanup grammar.
- Complete: the first comprehensive review findings were consolidated in design head `d5c0317`; author-side vectors and static checks pass. In progress: the conditional final comprehensive review. Not started: bootstrap/image installation, controller implementation, baseline refresh, hosted/capable acceptance, and any `.align-revision` change.

## Next steps

1. Run the conditional final comprehensive review against design head `d5c0317`; the continuity handoff commit must not be treated as a design-scope change.
2. If clean, open and merge the design slice with its SHA-bound review evidence; install/attest the fixed image supervisor and bootstrap, then create the separate repository implementation slice without changing `.align-revision`.
3. Refresh the identity-bound baseline after the implementation changes Make behavior, run the fresh topology matrix and capable `make ci`, then create the separate Request 6 adoption slice.

## Latest verification

- `git diff --check main...d5c0317`: PASS.
- `python3 -c 'import json,re; from pathlib import Path; s=Path("docs/specs/check-gate-topology.md").read_text(); b=re.findall(r"^```json\n(.*?)\n```$", s, re.M|re.S); assert len(b)==11; [json.loads(x) for x in b]'`: PASS — 11 JSON blocks parse; attestation predicate hashes `211475753df48fa9f8e6ae47b37c516be156ebebf6220433a0585cca723bd6d6` and `2b61df38636af38d36c13f9c6c38265fdd76bb0ad15db2ec0f5ca2f0c0d98e69`; cache/source/object-format vectors match their recorded hashes; fd, lock, bounds, noexec, Make-option, output-exception, and Cargo-phase markers are present.
- `git diff --check`: PASS.
- `awk '/^```/ { count++ } END { if (count % 2 != 0) exit 1 }' HANDOFF.md docs/align-requests.md docs/specs/c7-persisted-result.md docs/specs/check-gate-topology.md`: PASS — 176 fences.
- Source tests, `make check`, `make build`, `make ci`, hosted checks, and benchmarks are N/A because this remains a documentation/specification-only design slice with no executable contract change.

## Blockers and decisions

- `.align-revision` remains `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`; no adoption or compiler pin change is permitted yet.
- Section 9 claims only Ubuntu/Linux x86_64 with executable `/tmp`, delegated cgroup limits, and the named minimum toolchain. C7's required aarch64 Linux and aarch64 macOS environments need separate reviewed platform profiles and implementations.
- Request 7's exact Git 2.45.0 immutable OCI image/job remains a separate prerequisite; do not invent its digest.
- The dependent slice remains blocked until the v4 design is merged, then the implementation passes its complete review/check gate. Preserve the run-capsule/image-manifest split, exact supervisor argv and environment scrub, fd 4/5/6 supervisor handoff with worker fd 4/7/8/9 snapshot map, worker-owned protected lock and fail-closed orphan policy, source identity and bounds, private Git views, fixed Cargo configuration, read-only bundle, and exact status grammar.
- Do not consume `6b5dfaa`, `bb9ad1f`, or any unreviewed topology implementation as an implementation contract until this successor design and its dependent implementation merge. Preserve the no-host-fallback, staged interpreter/loader closure, overlay publication, private Git refs, and empty descriptor propagation decisions.
- The sibling Align checkout is the language source of truth. Do not code against hypothetical Align APIs or update the pin from this design branch.
- Intentional uncommitted files: none in this worktree. Main's separate uncommitted `HANDOFF.md` is intentional and must not be discarded.
