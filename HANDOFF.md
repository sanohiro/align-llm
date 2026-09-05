# Session handoff

Read `CLAUDE.md` first. GitHub owns transient pull-request checks, reviews, and attestations; this
file records durable project state.

## Active: R8-OLMOE-K-PREPARATION-BOUNDARY (2026-09-05)

Branch `agent/r8-olmoe-k-preparation-boundary`, based on merged main `e221df3` (PR #195).
Align remains pinned to `8cefc803d5c7f883a8db5b67250ed4ed069b43a4`; no new Align capability is
required. Item 74's authoritative ledger and closure matrix are
`docs/specs/r8-olmoe-k-preparation-boundary.md`.

The candidate replaces only K concatenation and padding (rows 17/18) with two explicit CPU custom
nodes using bulk byte copies and one callback task. Full width, shapes, marked concat and all V
operations stay exact. The gate compares four contemporary normal-control/candidate pairs, requires
all four positive, median saving at least max(871,174,011 ns, 5% of control), and the existing
16,552,306,197-ns historical candidate ceiling. The complete owner has an eight-minute ceiling.

**Next actions.** Implement the two explicit operations and focused real/stub owner; implement the
isolated two-build paired qualifier; run owner checks and clean-head qualification; retain production
only for `MET`; review, repair, preflight, publish and merge; continue to the selected successor.

**Blocker.** None. Design is fixed; implementation and qualification remain pending.

**Latest durable verification.** Item 73's focused owners, real diagnosis, comprehensive review
(findings none), exact-head preflight and all three required CI jobs passed. Item 74 has the author
ledger-to-prose consistency pass; executable owners remain pending.

**Intentional uncommitted files.** None after the design checkpoint; local models/evidence and
build products remain outside Git.

## Merged checkpoint: R8-OLMOE-ATTENTION-CORE-DIAGNOSIS (PR #195, 2026-09-05)

PR #195 merged as `e221df3`, preserving the tested tree `8fa087bc4f22839480845dfccd29475a1ecab1c4`.
The clean-head four-repeat run completed in 91.512 seconds. QK preparation won at 1,000,260,743 ns
median / 435,353 ppm of the 2,297,584,394-ns core parent, above the unchanged 871,174,011-ns floor:
`MEASURED_CORE_SEAM_ELIGIBLE / QK_PREPARATION`. Every fixed output/cache/isolation/lifetime and
accounting boundary passed. Comprehensive review approved with no findings; exact-head preflight
and all three required checks passed. Item 74 owns the selected copy boundary and requires a
contemporary control because historical timing alone can credit ambient variation.

## Merged checkpoint: R8-OLMOE-ATTENTION-OPERATION-DIAGNOSIS (PR #194, 2026-09-05)

PR #194 merged as `e1f3aee`. The repaired slot-membership diagnosis measured projection, attention
core and output/residual medians of 332,900,623 ns, 2,525,763,020 ns and 111,561,949 ns. Core won
at 846,606 ppm and cleared the immutable floor: `ATTENTION_CORE_SUBDIAGNOSIS_REQUIRED`. All exact
output/cache/isolation/lifetime/accounting boundaries passed. Review found and repaired positional
misattribution; the required final comprehensive review was clean. Exact-head preflight and all
three required checks passed. Item 73 owns the narrower successor.

## Merged checkpoint: R8-OLMOE-PHASE-A-OPERATION-DIAGNOSIS (PR #193, 2026-09-05)

PR #193 merged as `ce74938`. Its clean-head run selected `ATTENTION_AND_RESIDUAL` at a
2,627,247,387-ns median and 980,342 ppm of split phase A; router measured only 52,680,203 ns.
Every output, cache, isolation, lifetime, and operation-accounting boundary passed. Comprehensive
review found no substantive defects; exact-head preflight and all three required CI jobs passed.
Item 72 owns the selected narrower attention diagnosis.

## Merged checkpoint: R8-OLMOE-POST-OPTIMIZATION-REMAINING-DECODE-DIAGNOSIS (PR #192, 2026-09-05)

PR #192 merged as `11d98f7`. Its clean-head run measured a 22,326,600,666-ns current full-helper
median and 16,318,058,461-ns remaining-decode median. `ROUTING_PHASE_A` won the exact 23-leaf
partition at 4,620,020,794 ns, above the fixed 871,174,011-ns floor. Every output, cache,
isolation, lifetime, and accounting boundary passed. Comprehensive review found and repaired only
a stale handoff action; exact-head preflight and all three required CI jobs passed. Item 71 owns
the selected phase-A operation diagnosis.

## Merged checkpoint: R8-OLMOE-POST-OPTIMIZATION-SAMPLED-RUNTIME-DECISION (PR #191, 2026-09-05)

PR #191 merged as `cc2b080`. The clean-head run completed in 506.52 seconds and recorded
`NOT_MET`: local median time to a passing patch was 13,992,706,375 ns and runtime median was
91,415,902,187 ns, with runtime slower in all four pairs and a -5,533,111-ppm gain. Both arms passed
all four portfolios at candidate 5 with the same patch, and every server lifetime, isolation,
identity, and cleanup boundary passed. Review found and repaired insufficient delegated cleanup
grace plus stale handoff state. Exact-head preflight and all three required CI jobs passed. Item 70
owns the selected current-clock diagnosis.

## Merged checkpoint: R8-OLMOE-EXACT-SAFE-DECODE-BOUNDARIES (PR #190, 2026-09-05)

PR #190 merged as `917565deae247f4d75841ad98ca9c5553cd29568`. Its clean-head four-repeat
qualification measured a 17,423,480,208-ns median against item 62's 19,266,559,229-ns baseline,
a 95,662-ppm gain, and recorded `MET`. Exact output, cache accounting, fetched bytes, native
lifetimes, and isolation all passed. Comprehensive review found only one stale handoff action;
repair `1f8439b`, exact-head preflight, and all three required CI jobs passed. Item 69 owns the
provider-level primary-metric remeasurement after this shipped improvement.

## Merged checkpoint: R8-OLMOE-COMBINED-DECODE-BOUNDARIES (PR #189, 2026-09-05)

PR #189 merged as `3b890c3`. Evaluated candidate `1407d3a` changed exact cache accounting on its
first full request, so no latency aggregate was formed and all production changes were removed.
Review found and repaired missing evaluated-head ancestry enforcement. Exact-head preflight and all
three required CI jobs passed; post-merge ancestry and the focused owner self-test also passed.

## Merged checkpoint: R8-OLMOE-CACHE-TO-CLAIM-COPY-BOUNDARY (PR #188, 2026-09-05)

PR #188 merged as `7ef2124`. Evaluated implementation `3bb7135` removed every cache-to-claim copy
but produced a 19,056,394,208-ns median, only 10,908 ppm faster than item 62, so the result was
`NOT_MET` and all production changes were removed. Comprehensive review found one stale handoff
action; repair `2e12911`, exact-head preflight, and all three required CI jobs passed. Item 67 above
owns the combined successor.

## Merged checkpoint: R8-OLMOE-FILE-PREAD-BOUNDARY (PR #187, 2026-09-05)

PR #187 merged as `8107627`. Evaluated implementation `b82ff83` removed claim-file `pread` but
slowed the immutable fixed request by 155,680 ppm: walls
`[24070862584,24437186500,20461090500,20031240292]` ns and 22,265,976,542-ns median. Mapped page
faults moved into source consumption and raised block-to-claim copying to a 2,206,615,794-ns median,
so the result was `NOT_MET` and all production changes were removed. Comprehensive review found
and repaired publication-mode replay, one matrix error code, and stale handoff state. Exact-head
preflight and all three required CI jobs passed; item 66 above owns the next selected bucket.

## Merged checkpoint: R8-OLMOE-CLAIM-IO-DIAGNOSIS (PR #186, 2026-09-05)

PR #186 merged as `3c1a0a8`. The clean-head four-repeat diagnosis selected `FILE_PREAD` at a
1,945,780,694-ns median and 517,958 ppm of its claim-I/O parent. Comprehensive review found and
repaired inherited-result validation, exception normalization, and stale handoff state. Exact-head
preflight and all three required CI jobs passed; item 65 above owns the selected implementation.

## Merged checkpoint: R8-OLMOE-ROUTING-PHASE-A-BOUNDARY (PR #185, 2026-09-05)

PR #185 merged as `154133acebe686018d3a4478c50f8ca5d7f83e86`. The candidate's pre-review
qualification provisionally met the gate, but comprehensive review found that the runner pinned
only its immediate imported owner, not nine transitive Python qualification owners. The repaired
clean-head qualification produced walls `[16668116584,17859126833,19039104500,19435260625]` ns,
median 18,449,115,666 ns, and a 42,428-ppm gain, so the final decision was `NOT_MET`. The candidate
production changes were removed. Exact-head preflight and all three required CI jobs passed; item
64 above owns the next diagnosis.

## Merged checkpoint: R8-OLMOE-DECODE-COMPUTE-DIAGNOSIS (PR #184, 2026-09-05)

PR #184 merged as `4b69eaa5e7b99e4206b7a4c90e3257e19c8dca07`. The clean-head diagnosis
selected `ROUTING_PHASE_A` at a 2.939-second median and 697,193 ppm of total decode compute. Review
found and repaired a ledger field-name mismatch and stale handoff state. Exact-head preflight and
all three required CI jobs passed; item 63 above owns the selected implementation boundary.

## Merged checkpoint: R8-OLMOE-PLANE-ROUNDTRIP-BOUNDARY (PR #183, 2026-09-05)

PR #183 merged as `9ebcd49e835cd2819e47a4c3b73ec51cfb8b261d`. It was based on pulled merged `main`
`8e7be2a77f69d7afb0da34507e90e84f89301871` (item 60 PR #182). The sibling Align checkout and
`.align-revision` remain at merged Align `8cefc803d5c7f883a8db5b67250ed4ed069b43a4`; no new Align
surface is currently required.

Item 61's authoritative ledger and closure matrix are
`docs/specs/r8-olmoe-plane-roundtrip-boundary.md`. Item 60 measured the complete `verify_plane`
call—shape reads, two `slot_get` operations, scalar K/V comparison, and result accounting—at a
2,972,324,939-ns median, without attributing cost among those operations.

Intervention A retained the shape reads and both `slot_get` calls and replaced scalar K/V comparison
with one validated shared-shim call per tensor. Its clean-head run reduced the boundary median from
2,972,324,939 ns to 1,878,132,280 ns but improved the full helper by only 23,162 ppm, so it is
`NOT_MET` and cannot ship alone. Intervention B removed the remaining two host-to-host copies by
comparing each concat slot in place only after the real shim proves its backend buffer is host
visible; the unchanged capture readback preserves the routed-offset and forced-inf regressions.
Its clean-head full-helper median was 19,122,598,458 ns / -20,069 ppm, also `NOT_MET`. Disassembly
shows that V still executes approximately 30 million scalar four-byte comparisons. Intervention C
added an AArch64 4-by-4 exact-success transpose scan and reran the original scalar traversal on any
difference, preserving exact K/V traversal and first-mismatch tensor/column semantics. The
immutable baseline is item 60's full-helper samples
`[17704139042,18412456541,19080317000,19520549709]` and 18,746,386,770-ns median. The precommitted
50,000-ppm floor is 937,319,339 ns and candidate ceiling is 17,809,067,431 ns. Only the complete
fixed-request gate can establish the performance claim.

Intervention A is committed at `9b940fd94acaeea839725f79f7092882e722b057`. Intervention B was
qualified `NOT_MET` at `c7f5eadf9229422190b056fa507bf3be8ce91994`. Intervention C was initially
qualified `MET` at `1e121c41c58f39c584bdc43c864aeccae6b16c04`. The item 61 runner independently
pins item 60's evidence, the full evaluated source chain, fixed host, helper schema, output,
lifetimes, isolation, gate arithmetic, and cleanup-before-publication.

The pre-review four-repeat full-helper samples were
`[16554919250,17140798625,16882099208,17146960833]`, median 17,011,448,916 ns, for a
1,734,937,854-ns / 92,547-ppm gain against item 60. The plane-boundary median fell to 779,712,734
ns. All four runs reproduced the fixed 86-token output/hash, exact native lifetime balances, twelve
clean isolation boundaries, fixed cache state, and cleanup in 100.934 seconds.

The comprehensive Codex CLI review covered head
`fd9835ffa691e8b5d6d06e777ada6d20cf3327a7` against base tip and merge base
`8e7be2a77f69d7afb0da34507e90e84f89301871`, using gpt-5.6-sol at high effort over the full diff.
It found one accepted P2: the AArch64 fast path cast arbitrary byte ranges to `uint32_t *`, adding
an undeclared four-byte alignment precondition and undefined behavior. The consolidated repair
loads through byte-aligned NEON vectors before reinterpreting register bits and adds a direct
unaligned-consumed/nonaligned-plane-base tile regression. Consolidated repair `549179f` preserves
the ABI and does not change the capability boundary, so another comprehensive review is not
required.

The repair-owned clean-head qualification at `4e1f53d208191d274c4ef9733059afd290bb9c4f`
produced full-helper samples `[16670214417,19040051292,19655093584,18174675459]`, median
18,607,363,375 ns, for only a 139,023,395-ns / 7,416-ppm gain. It was 798,295,944 ns above the
precommitted ceiling, so the final decision is `NOT_MET` even though the plane boundary remained at
an 838,509,258-ns median. Every fixed output/hash, lifetime, isolation, cache, host, and cleanup
check passed in 108.080 seconds. Per the ledger, all three production interventions and their
owner-test additions are removed before publication; item 60's behavior remains shipped.

The final comprehensive Codex CLI review covered head
`fd6208900f91fe224332e719f475733cae7f669d` against base tip and merge base
`8e7be2a77f69d7afb0da34507e90e84f89301871`, using gpt-5.6-sol at high effort over the complete
post-removal diff. It found one accepted P2: the retained runner pinned the ggml libraries but not
the three headers compiled into its shim. The consolidated repair records exact name/size/hash rows
for `ggml.h`, `ggml-alloc.h`, and `ggml-backend.h`, validates them before build and after
measurement, adds them to the exact candidate schema, and owns a mutation self-test.

**Publication result.** Exact-head preflight and all three required checks passed; PR #183 merged
with the complete measurement history preserved.

**Blocker.** None.

**Latest durable verification.** Before the final decision, `make layer-forward-smoke` passed after
review repair in 66.455 seconds with the unaligned tile regression, explicit UBSan unaligned V-tile
execution passed, emitted IR used alignment 1, `make runtime-provider-smoke` passed its self-test and
61 CLI assertions, and the full item 57→61 self-test chain, `make fmt`, and `git diff --check`
passed. The repaired real qualification recorded the `NOT_MET` result above. Final production files
compare byte-for-byte with `origin/main`; `make fmt`, item 60's self-test, item 61's complete inherited
self-test, and `git diff --check` pass after removal. The final diff is limited to the authoritative
decision/specification, roadmap/handoff state, immutable item 60 evidence, and item 61 qualification
owner. After final-review repair, deterministic header identity, mutation, missing-header, exact
candidate-schema, Python compilation, focused inherited self-test, `make fmt`, and
`git diff --check` all pass.

**Intentional uncommitted files.** None.
Machine-local model/evidence and generated build products remain outside Git.

## Merged checkpoint: R8-OLMOE-DECODE-PASS-OTHER-DIAGNOSIS (PR #182, 2026-09-04)

PR #182 merged as `8e7be2a77f69d7afb0da34507e90e84f89301871`. The clean-head diagnosis
selected `PLANE_ROUNDTRIP_COMPARE` at a 2.972-second median and 991,445 ppm of its 2.998-second
parent. Comprehensive review found that the clock covered the complete `verify_plane` boundary,
not scalar loops alone; the repair broadened item 61 accordingly without changing measurement
behavior. Exact-head preflight and all three required CI jobs passed.

## Merged checkpoint: R8-OLMOE-DECODE-PASS-RESIDUAL-DIAGNOSIS (PR #181, 2026-09-04)

PR #181 merged as `a502f94a22302e4896509204d3423b6e21090ade`. The repaired fixed-host run
completed in 105.743 seconds and selected `OTHER_PASS_RESIDUAL` at a 2.877-second median and
694,324 ppm of the 4.144-second decode-pass residual. Every direct bucket missed the 0.921-second
floor, so no optimization was authorized and item 60 was selected. Comprehensive review found and
repaired claim-buffer timing attribution and pre-cleanup result publication; exact-head preflight
and all three required CI jobs passed.

## Merged checkpoint: R8-OLMOE-KV-PLANE-STAGING-TRANSFER (PR #180, 2026-09-04)

PR #180 merged as `ef113f8c049a93334cabd42d17dde6d51f31e1be`. One combined caller-owned
staging range and one bounded shared-shim call preserve the canonical plane and graph-input layouts.
The post-review fixed-host run completed in 105.628 seconds and recorded `MET`: full-helper median
fell from 30.451 seconds to 18.429 seconds (394,794 ppm), and upload median fell from 11.548 seconds
to 2.045 seconds. Exact output, native lifetimes, and all isolation gates passed. Review found and
repaired one evidence-identity class covering baseline-host binding and nested result validation.

## Merged checkpoint: R8-OLMOE-ISOLATED-SAMPLED-RUNTIME-DECISION (PR #178, 2026-09-04)

PR #178 merged as `6d05d1fbbf79644806edecded24755ae701a6d0a`. The comprehensive review's
two accepted reproducibility/schema findings were consolidated by independently pinning every
imported workload value and rejecting boolean server-instance counts. Exact-head preflight and all
three required CI jobs passed; the active item 57 above owns the selected remaining-decode
diagnosis.

Item 53's provider-level sampled decision kept one llama.cpp model resident across all four pairs
and measured runtime at a 189.005-second median versus local at 12.710 seconds. Item 55 then bounded
repeated pre-prefill construction at 0.272 seconds and measured a 3.052-second co-resident penalty
for one full request, selecting isolation before any persistent lifetime change.

Item 56's authoritative ledger, closure matrix, and recorded decision are
`docs/specs/r8-olmoe-isolated-sampled-runtime-decision.md`. It repeats the exact item-53 workload,
four balanced pairs, metric, and 50,000-ppm gate. Each local leg owns one fresh server and excludes
startup/teardown from its unchanged portfolio metric; the server must be alive during the local
portfolio, then terminated and reaped. Every runtime leg begins and ends with zero matching model
processes. Product provider, sampling, cache, and lifetime behavior remain unchanged.

The complete run at head `ee3ca3d691a91bac06f2e41e4b8fa4fc05f3e00f` finished in 724.144 seconds
and recorded `NOT_MET`. Both arms passed all four pairs at candidate 5 with the same patch. Local
median time to a passing patch was 13.197 seconds; runtime median was 149.273 seconds, for a
-10,310,731-ppm gain with runtime slower in every pair. All four server lifetimes and every
before/after absence check passed. Isolation recovered 39.732 seconds, 21.0% of item 53's runtime
median, but left runtime 11.31 times slower than local. R8 remains open; item 57 is selected to
partition remaining-decode graph/context lifecycle, transfer/readback, claim, compute, and
routing/sampling/accounting overhead before any implementation seam is authorized.

## Merged checkpoint: R8-OLMOE-FIRST-TOKEN-PHASE-DIAGNOSIS (PR #177, 2026-09-04)

PR #177 merged as `6da234fb6ef3c96d10aec3b07c2cf1b5bd9ab640`. The conditioned diagnosis
narrowed repeated setup to 0.068–0.272 seconds and measured a positive 3.052-second co-resident
penalty median. Claim I/O dominated its prefill and remaining-decode movement, so the decision was
`CO_RESIDENT_PRESSURE_EXCEEDS_CONSTRUCTION`. The comprehensive review's two reproducibility
findings were consolidated by pinning inherited identities and item 53's exact token chain. The
exact-head preflight and all three required CI jobs passed. The active item 56 above owns the
selected isolated provider-level decision.

## Merged checkpoint: R8-OLMOE-RUNTIME-PHASE-DIAGNOSIS (PR #176, 2026-09-04)

PR #176 merged as `fdf358ef269f7a016d6925d531a0947bfaeaba22`. The repaired 360.313-second
diagnosis reproduced the fixed output in all sixteen requests and balanced every native lifetime.
Solo short/full medians were 4.941/30.617 seconds, co-resident medians were 6.412/32.242 seconds,
and the positive paired full-request penalty median was 2.025 seconds. It lay between the measured
0.132-second setup lower bound and conservative 30.617-second full-request upper bound, so the
decision was `MIXED_OR_UNRESOLVED`. Exact-head preflight and all required CI passed after the
comprehensive review and its accepted attribution, N/A-label, warmup-metadata, and handoff repairs.
The active item 55 above owns the selected narrower instrument.

## Merged checkpoint: R8-OLMOE-SAMPLED-RUNTIME-DECISION (PR #175, 2026-09-04)

PR #175 merged as `f2c83c96ed31aac322ecfbd30efaff75d7917ef9`. The capability ran the fixed
sampled coding portfolio through the resident llama.cpp baseline and invocation-local AlignRuntime
provider in four balanced pairs and recorded `NOT_MET`.

This capability runs the fixed seeds 1 through 8 sampled coding portfolio through both the pinned
resident llama.cpp baseline and shipped partial-LRU `AlignRuntime` provider in four balanced pairs.
Its authoritative measurement ledger, 50,000-ppm floor, pre-implementation 800,000-ppm
attempt-count opportunity ceiling, approximately-25-minute execution ceiling, schema, validation
order, and closure matrix are `docs/specs/r8-olmoe-sampled-runtime-decision.md`.

**Latest durable verification.** The focused self-test passes. The one complete real decision ran
on clean head `d8a3da0` in 801.574 seconds and recorded `NOT_MET`: both arms passed 4/4 at seed 5
with the same known-good patch, but local median time to passing patch was 12.710 seconds and runtime
median was 189.005 seconds, a -13,871,021-ppm gain with runtime slower in every pair. Both required
five candidates, so the 800,000-ppm attempt-count opportunity was not realized. Runtime provider
intervals rose from 27.928 to 40.243 seconds; a 16-GiB host showed about 4.29 GiB swap used after the
run, but that non-precommitted observation does not distinguish repeated provider construction from
co-resident memory pressure. The comprehensive Codex CLI review covered head
`cf58d064fd84522833fd59721e2d9f33ef5bde1f` against base tip and merge base
`728a186fbd7d21d43c3f1d8993adf124444652bc`, using gpt-5.6-sol at high effort over the full diff.
Its three accepted P2 findings require isolating Git routing, canonicalizing configured paths, and
declaring the validator-image selector while retaining the immutable resolved identity. Consolidated
repair `770b0aa` resolves all three without changing the absolute inputs or immutable image identity
used by the recorded decision; Python compilation, the focused self-test, and `git diff --check`
pass after repair.

Consolidated review repair `770b0aa` resolved all three accepted reproducibility findings. Exact-head
preflight passed at `1ca3b95`, all required PR checks passed, and merge-head push CI reused that
evidence successfully. The active item 54 above owns the selected diagnosis.

## Merged checkpoint: R8-OLMOE-RUNTIME-SAMPLING (PR #174, 2026-09-04)

PR #174 merged as `728a186fbd7d21d43c3f1d8993adf124444652bc`. The shipped OLMoE provider now accepts the exact
temperature-0.3 seeded policy selected by item 51, using stable top-k 40, top-p 0.95, min-p 0.05,
fixed-point categorical weights, and one explicit Xoshiro256++ draw per emitted token. Greedy OLMoE,
dense Qwen, diagnostic argmax evidence, cache ownership, and EOG semantics remain unchanged.

The fixed real qualification repeated seed 5 twice with exact two-token output `To fix` in 17.05
seconds. The comprehensive review's three accepted qualification defects were consolidated in
`a4ebdad`; no valid finding remained. Exact-head preflight passed, required PR CI passed at head
`e2d405b`, and the merge-head push reused that evidence successfully. The next consumer is the
active sampled provider-level performance decision above.

## Merged checkpoint: R8-OLMOE-SAMPLED-CODING (PR #173, 2026-09-04)

PR #173 merged as `753e7c4acb6284dc495f92a243da081434073b97`. Its fixed eight-seed local-provider
portfolio recorded `MET` at candidate 5, seed 5, with passing patch digest `5d6b107e706a` and 13.176
seconds from portfolio start through validation. The result is feasibility evidence and not a speed
claim. The comprehensive review found one valid validator-environment isolation defect; repair
commit `a2537f1` removed ambient native routing overrides from the control and every candidate. The
exact-head preflight and all required GitHub checks passed before merge.

## Merged checkpoint: R8-OLMOE-PROVIDER (PR #170, 2026-09-03)

Branch `agent/r8-olmoe-provider` merged as PR #170 at
`0eaed918f34b1dbb8a70ef0aaa352cbaec7513e7` after integrating the required-CI repair at
`dc38b7639d86aaea786965487f1b09c806fbc20a`.

The merged capability exposes OLMoE greedy generation through the existing in-process provider,
using an explicit invocation-local partial-LRU cache budget and stop-aware MoE generation. Its
public-contract ledger and closure matrix are `docs/specs/r8-olmoe-provider.md`. Qwen and the
diagnostic MoE CLI remain unchanged, and this correctness capability makes no performance claim.

The implementation candidate is complete. `gmake fmt` passed; `gmake runtime-provider-smoke`
passed 61 assertions; `gmake layer-forward-smoke` passed the unchanged diagnostic/cache boundary;
and the repaired fixed real-model qualification matched pinned llama.cpp prompt count 47, actual
generated token ids `[1992,4993]`, and bytes `To fix` in 22.62 seconds. The qualification runner self-test,
Python compilation, and `git diff --check` also passed. No broad aggregate, platform, stress, or
benchmark suite was selected.

The comprehensive Codex CLI review covered head
`59e5111e619c25f11bec7c6428f771d91c32d5e6` against base tip and merge base
`c987838130077d5b6119ee20b717774c1c913fbe`, using gpt-5.6-sol at high effort over the full diff.
It found two accepted P2 qualification defects: the real gate re-tokenized decoded text instead of
observing the generated id chain, and SIGTERM could bypass `llama-server` cleanup. The consolidated
repair adds a qualification-only exact generation seam consumer and signal-aware cleanup with a
forced escalation self-test. It does not change provider behavior or expand scope, so another
comprehensive review is not required.

The base integration changed only hosted-check allocation, documentation, and the identity-bound
baseline chain, so it did not materially change the reviewed provider risks. Exact-head preflight
passed with the 61-assertion owner in 7.3 seconds and the shortened local hosted graph in 2m55s.
Required GitHub checks passed: hosted in 11m47s despite a compiler-cache miss, and the unaffected
installed classifiers in 8 and 12 seconds. The final tested synthetic integration tree was
`67bea32a1748afe6f7f20dc32515d90518164b8c`.

**Blocker.** None.

**Intentional uncommitted files.** None. Local configuration remains outside the change.

## Merged checkpoint: REQUIRED-CI latency repair (PR #171, 2026-09-03)

Branch `agent/ci-remove-redundant-check`, based on pulled `main`
`c987838130077d5b6119ee20b717774c1c913fbe`, merged as PR #171 at
`dc38b7639d86aaea786965487f1b09c806fbc20a`. The repair followed two PR #170 hosted failures at
the 15-minute whole-job boundary: the exact-cache attempt completed its aggregate in 14m52s before
finalization cancellation, and the single cache-miss retry was cancelled 12m45s into that aggregate.

The repair removes only the redundant standalone `check` goal from `HOSTED_CHECK_TARGETS`.
`make check` remains unchanged for local checkpoints; the aggregate's shared `build` prerequisite
uses Align's same bottom-up per-unit package frontend and continues through lowering, code
generation, and linking before every functional owner. Author-host measurements at the unchanged
provider candidate were 177.42s for uncached `make check`, 10.74s for `format-check`, and 0.87s for
an immediately warm `make build`. The authoritative contract and closure matrix are
`docs/specs/check-gate-topology.md` sections 1.2 and 2.

The identity-bound baseline chain is source `d62e7a1e34fe390596131b16e1777d66ad6cdb48`
-> oracle `92cf3bdbb024606aec74a9d3e4eebb2547af1827` -> finalization
`dcb893d93612d5afb13cdd7b43e04bf0c9d17e7a`. Its two fixed-task samples passed on Linux/aarch64,
kernel 6.11.11-linuxkit, Python 3.12.3, with the exact pinned Align compiler. In the same Linux
boundary, `make baseline-check` ended `baseline chain: PASS` and
`python3 scripts/check-gate-topology --self-test` passed. The normal exact topology owner also
passes. The macOS self-test's existing reader-start fault injection records a post-exit
`sigkill-PermissionError`; unmodified `origin/main` reproduces it, so Linux owns publication
evidence for that platform-sensitive lifecycle case.

The comprehensive Codex CLI review covered head
`dcb893d93612d5afb13cdd7b43e04bf0c9d17e7a` against base tip and merge base
`c987838130077d5b6119ee20b717774c1c913fbe`, using gpt-5.6-sol at high effort over the full diff.
It found one accepted P2: a historical closure row still claimed both `check` and `build` remained
in both aggregate graphs. The documentation-only repair states the actual allocation: standalone
`make check`, aggregate `build`, and compiler-owned checker parity. It changes no implementation,
baseline artifact, or verification behavior, so it does not trigger another comprehensive review.

On the final synthetic integration tree `5b8895873f026ba3657ade7c2381b7cb4ca9c819`, the required
hosted job passed in 9m28s, down 5m24s from the exact-cache incident. Installed aarch64 and x86_64
passed in 12m54s and 11m47s respectively. The provider branch is now consuming this merged repair.

**Blocker.** None; the provider publication gate is resumed.

**Intentional uncommitted files.** None. Local configuration remains outside the change.

## Merged checkpoint: R8-OLMOE-TEXT (2026-09-03)

Branch `agent/r8-olmoe-text` merged as PR #169 at
`c987838130077d5b6119ee20b717774c1c913fbe`. The sibling Align checkout was fast-forwarded from the prior pin
`b6f95a261e1434d705d7de006484ffa66b1542f0` to merged `origin/main`
`8cefc803d5c7f883a8db5b67250ed4ed069b43a4` (Align PR #933, `pkg.kv` v1). Commit `5c9ac3c`
advances `.align-revision` and records compatibility evidence as an internal checkpoint in this
consumer branch; it will not be published as a pin-only pull request.

The capability extends existing tokenize, detokenize, and prompt preparation to the exact
`gpt2`/`olmo` profile and 508-byte chat template carried by the local OLMoE reference model. Its
authoritative public-contract ledger and closure matrix are
`docs/specs/r8-olmoe-text.md`. It deliberately stops before provider dispatch, MoE generation, EOG
policy, cache configuration, and any latency claim.

Implementation now adds profile-specific identity, the exact OLMo scanner, the valid-UTF-8 byte
alphabet boundary, model-carried BOS rendering, and independent synthetic and real parity owners.

**Latest durable verification.** The managed release compiler/runtime materialized in 1m03s with
the host's explicit LLVM 22 path. `scripts/align-toolchain verify` returned the exact new identity,
and `make check` passed all 40 units per-unit in about 1m58s. The repaired focused synthetic owner
passes in about one second over 8 lexical cases in both modes, 6 prompt cases, 7 malformed models,
and 3 byte-boundary models. Real parity against the exact OLMoE model and pinned llama.cpp
build 10566 passes in 23.6 seconds: 13 lexical cases in both modes, 6 prompts, 805 bytes, and 332
compared ids. Existing Qwen tokenizer and prompt owners pass after the profile repair in about four
seconds; the real Qwen identity remains `b56e4ff2...9fe2`. No aggregate, installed/native profile,
benchmark,
runtime matrix, or inference ran. The one real Qwen non-regression qualification also passed all
299 cases and 69,485 compared ids in 4m16s; it will not be repeated absent a relevant repair.

The comprehensive Codex CLI review covered head
`897d8b91e9dde33394b9f7ba37451d77bc5ab63c` against base tip and merge base
`4d9f9c823dc6596f87c7bb6db1b16e55d9653637`, using gpt-5.6-sol at high effort over the full diff.
It found three accepted P2 defects: omitted byte positions also admitted present non-normal entries,
crossed profiles could reach OLMo-only BOS validation before profile rejection, and the focused
owner could execute a stale ignored `main`. The consolidated repair requires a normal token for
every present byte spelling, selects and validates the tokenizer profile before OLMo-only metadata,
adds the missing malformed-profile regressions, and makes the publication owner rebuild `main`
from the exact source through the repository wrapper before testing it.
The repair does not expand the public behavior or capability scope, so another comprehensive review
is not required.

PR #169 merged as `c987838130077d5b6119ee20b717774c1c913fbe`; `main` was pulled and no additional
align-llm or sibling Align update was present at that checkpoint. Its provider-level successor is
the current active capability.

**Blocker.** None.

**Intentional uncommitted files.** None. Local configuration remains outside the change.

## Merged checkpoint: R8-PARTIAL-LRU-CACHE (PR #168, 2026-09-02)

Branch `agent/r8-partial-lru-cache`, based on pulled merged `main`
`d3b04b08d44bafa1afa28438e2229333e14810ec` (R8-RESET-CACHE-DECISION PR #167). PR #168 passed its
required hosted check in 12m48s; both unaffected installed profiles classified and exited in 8s
and 10s. It merged as `4d9f9c823dc6596f87c7bb6db1b16e55d9653637`, and `main` was pulled with no
additional align-llm update.

The capability implements the measured 975,175,680-byte LRU policy in the existing real
`--moe-decode-step` consumer. Its authoritative contract, public CLI/schema ledger, closure matrix,
byte shipping floor, memory bound, and approximately-15-minute focused qualification ceiling are
in `docs/specs/r8-partial-lru-cache.md`. It combines dense residency with an invocation-local expert
cache, preserves the claim-window/graph boundary, and makes no elapsed or provider-level
time-to-passing-patch claim.

Design checkpoint `5d5617c`, implementation checkpoint `158c469`, and review repair `46ccede` add
the schema-3
`dense+lru:BUDGET_BYTES` mode, deterministic invocation-local LRU staging, aggregate and per-step
cache evidence, and synthetic grammar/budget/hit/miss/eviction/semantic coverage. The real pack's
expert keys vary by layer, so the implementation uses the maximum 4,079,616-byte key as its fixed
slot stride: the selected budget owns 239 slots and 975,028,224 bytes, never the erroneous
pre-implementation 256 uniform slots.

The comprehensive Codex CLI review covered head
`158c469f4e30bcec007852447d5cc0a17611e320` against base tip and merge base
`d3b04b08d44bafa1afa28438e2229333e14810ec`, using gpt-5.6-sol at high effort over the full diff.
It found two accepted P2 public-reporting defects: amplification estimated logical cache-miss bytes
from an average key size even though layer key sizes vary, and canonical representable budgets over
18 digits were misclassified as malformed. Consolidated repair
`46ccede55b2fe16fa1b867c5ce2e30510aa875f2` uses the exact accumulated logical miss bytes and a
canonical overflow-safe parser that distinguishes malformed text from every over-budget integer.
The repair delta also corrects the obsolete expert-read comment and binds the classifications and
amplification formula into the owner. No finding remains open and the repair does not change cache
selection, lifetime, or transport behavior, so another comprehensive review is not required.

**Latest durable verification.** The repaired `make layer-forward-smoke` owner passes in 83.577
seconds, including i64-limit, beyond-i64, trailing-nondigit, and exact amplification regressions.
The focused real paired qualification reused the existing reference AlignPack and passed in 9.75
seconds of
model execution: dense read 7,801,405,440 decode expert-pack bytes, cache read 2,920,955,904, a
625,585-ppm reduction. It recorded 1,279 hits, 1,112 misses, and 873 evictions with exact normalized
semantics. Internal elapsed 4.407 seconds dense and 4.435 seconds cache is diagnostic only. No broad
aggregate, installed profile, stress, benchmark, or unrelated platform suite ran.

Exact-head hosted publication preflight passed in about 6m30s. GitHub's required hosted check
passed in 12m48s; the two unaffected installed jobs performed only classification and evidence
binding. No broad `make ci`, installed profile execution, stress, benchmark, or unrelated platform
suite ran.

## Merged checkpoint: R8-RESET-CACHE-DECISION (PR #167, 2026-09-02)

Branch `agent/r8-reset-cache-decision`, based on merged `main`
`c1338f1cf95d99255bcbb62c2b60d39522394411` (R8-SCORE-BASED-CACHE PR #166). PR #166 passed its
required hosted check in about twelve minutes, merged, and `main` was pulled with no additional
remote update.

Design checkpoint `ba641e5`, implementation checkpoint `465b0bf`, and measurement record
`83420a0` add the explicit
`--simulate-residency-reset` verb, schema-3 reset documents, exact independent-oracle coverage, and
continuing plus reset versions of all four real-runner projections from one capture. The existing
schema-2 command and golden remain byte-identical.

The real 40-prompt, 16-step run completed in 213.47 seconds total (199.0-second sole capture). On
reset `decode_only` at the 975,175,680-byte budget, null streaming fetched 312,056,217,600 bytes and
LRU fetched 144,557,211,648, a 536-per-mille reduction. The conservative all-40-fold lower bound is
524 per mille. `router_weight_lfu` improved on LRU by only 9 per mille, below rule 3's floor, so the
next runtime capability is eligible with the simpler LRU policy, not weighted LFU.

The comprehensive Codex CLI review covered head
`83420a081dded8c9ae28884f0ddc21b4dc65ceec` against base tip and merge base
`c1338f1cf95d99255bcbb62c2b60d39522394411`, using gpt-5.6-sol at high effort over the full diff.
It found two accepted P2 reporting and selection defects: the real runner could promote a non-LRU
policy that had not passed rule 3 when LRU failed the streaming gate, and its refactored human
report omitted the settled budget sweep. Consolidated repair
`f514feec3388cd31e5cbda85617b559c119e3fcb` defers when neither a qualified rule-3 winner nor LRU
clears the investment rule, restores every sweep row for every pooling/arm pair, and binds both
properties into the narrow owner. No finding remains open and the repair does not change the
simulator or measured result.

**Latest durable verification.** `make residency-sim-smoke` passes in 5.3 seconds over both pooling
lifetimes, both orders, every policy/budget, both output forms, and the full error corpus against the
independent oracle. The real runner passes all eight arm/lifetime results with the model unchanged
in 213.47 seconds. No aggregate, installed profile, benchmark, or platform suite has completed.

The first publication plan incorrectly selected the fresh-image scope solely because this branch
had edited the existing `Makefile` owner comment without changing its target or command. A native
Linux/aarch64 attempt proved the owner and focused qualification, then was stopped after roughly 17
minutes while a cold inner image was still downloading LLVM. Removing that non-contract comment
restores the intended hosted scope; the failed cold-image attempt is not candidate evidence and is
not repeated.

**Next actions.** (1) Run exact-head publication preflight. (2) Publish and merge after required
checks. (3) Pull `main` and begin the measured 975,175,680-byte partial LRU cache capability.

**Blocker.** None.

**Intentional uncommitted files.** None. Local configuration remains outside the change.

## Merged checkpoint: REQUIRED-CI-UNDER-15 (PR #165, 2026-09-02)

Branch `agent/ci-under-15`, based on merged `main` `29b54757c837fdfc610e413acd297d253644e292`
(R7-RUNTIME-PROVIDER PR #164). The user-set operating target is roughly 15 minutes for each
required CI check and the complete fresh-image publication preflight, with only work that
distinguishes a required risk. The number is diagnostic rather than an absolute correctness limit.

PR #164 is the pre-implementation baseline: hosted 12m19s, native x86_64 installed 43m22s, and
native aarch64 installed 46m57s. The aarch64 installed-profile log attributes 2,233.685 seconds to
the duplicate `worker-aggregate` and 428.396 seconds to the image-specific profile before it. The
complete common graph is already owned by the hosted job; it is not a benchmark. The authoritative
cost ceiling, public qualification CLI contract, coverage allocation, and closure matrix are in
`docs/specs/check-gate-topology.md` section 1.1 and the section 2 ledger. Roadmap item 44 owns the
consumer-complete change.

Design checkpoint `514f356` and implementation checkpoint `5e1ba3c` make
`--complete-aggregate` explicit, remove it from routine preflight and hosted CI, set both required
job definitions to 15 minutes, and preserve the native worker-unit ELF closure plus real
compiler-generated fixture execution. All ten focused owners and the complete Linux/aarch64
development-preflight owner pass. Routine installed evidence still covers image admission,
attestation, lifecycle, compiler self-test, trust and runtime-replacement refusals, ordinary
adoption, the worker-native build/bundle namespace, and cleanup; only aggregate-owned common
product behavior is deferred to explicit audit.

The exact native Linux/aarch64 installed owner at repair head
`64ca4c7f8e4f314a050ffda51144fb65efb88c35` passes without `--complete-aggregate` in
**576.532 seconds**: Docker daemon 0.077s, image build 21.960s, attestation 2.640s, profile lifecycle
1.786s, compiler self-test 14.482s, trust mutations 12.184s, runtime replacements 21.680s,
adoption boundary 313.091s, worker build 186.037s, and cleanup 2.059s. No worker aggregate runs.
This is a 78.3% reduction from PR #164's 2,662.367-second owner and leaves 323.468 seconds beneath
the current 900-second timeout.

The comprehensive Codex CLI review covered head
`162ef17653684f037e4b224aed5c73fc3af3c3ea` against base tip and merge base
`29b54757c837fdfc610e413acd297d253644e292` at high effort. It found two accepted documentation and
coverage-allocation defects, repaired in `cfab7340ec8d66078e6c26f12a8604b161bbfd80`.
The required final review covered head `7ca7f95959fe742984257df8e446e63d34c15de9` against the same
base and merge base at high effort. It found two accepted issues: routine installed evidence had
lost the worker-native build boundary, and the outer private Docker configuration did not reach
the inner Docker CLI calls. Consolidated repair `64ca4c7f8e4f314a050ffda51144fb65efb88c35`
restores worker mode `build`, reserves mode `ci` for explicit aggregate audit, and forwards the
private client configuration only to Docker commands. Targeted owners and the exact installed
measurement above pass.

Publication preflight's previously serial hosted plus installed tail would itself exceed the
rough 15-minute operating target despite both phases being meaningful. Checkpoint
`446f0b144e08764bcabf55391603112d97c0388b` therefore runs short owner/toolchain/focused
prerequisites first, then launches independent hosted and installed owners as one fail-fast parallel
group. Synchronized success and failure/cancellation regressions pass in 0.6s; the complete
Linux/aarch64 development-preflight owner passes in 10.0s and `format-check` in 11.9s. This expands
the public local-preflight execution contract after the prior final review.

The fresh comprehensive review covered head
`c2c04fc8513c2a832b5b1c106f57a10825df912b` against base tip and merge base
`29b54757c837fdfc610e413acd297d253644e292`, using Codex gpt-5.6-sol at high effort over the full
diff. It found two P1 cancellation leaks, both accepted: peer-failure escalation killed only the
output wrapper while a TERM-resistant managed command group survived, and a top-level termination
could exit the coordinator before it forwarded signals to either wrapper. Consolidated redesign
repair `38acbb0c155ad02f4a287e8046aded5abdf677d2` gives the output wrapper a two-second
signal-to-KILL escalation for its owned command group and makes the coordinator forward and
preserve HUP/INT/QUIT/TERM after reaping every started wrapper. The resistant-child owner passes in
6.6s, combined peer/top-level coordination owner in 0.8s, and `format-check` in 12.2s. No finding
remains open from that review.

The first exact-head parallel preflight stopped at 8m40s when hosted checks could not create the
Align cache below an outer root-owned `HOME`; this was an invocation defect, not a candidate
failure. Fail-fast cancellation correctly stopped the installed peer at worker-build, but the
incident exposed invocation-owned image and volumes left after the installed Python owner received
TERM. Those exact resources were identified and removed. Re-scoped repair
`d0eec6a1f60c5bcd1d82ac0a5c7373ddb7ced9ac` gives the installed image owner catchable-signal
unwinding through its existing finalizer and gives that cleanup five seconds before the output
wrapper escalates the whole command group to KILL. A synthetic image-build cancellation proves all
five volumes and the image reach removal; output-summary and profile cancellation owners pass in
10.1s, the cleanup-specific owner in 0.7s, and `format-check` in 13.4s. This adds installed resource
cleanup behavior beyond the reviewed head.

The redesigned-candidate review covered head
`9f3eb7728363196346445bb21bd35016dd4cb6cf` against base tip and merge base
`29b54757c837fdfc610e413acd297d253644e292`, using Codex gpt-5.6-sol at high effort over the full
diff. It found two accepted finalization defects: a signal arriving after image cleanup began could
skip the remaining Docker removals, and peer cancellation could terminate the qualification owner
before its private Docker configuration directory unwound. Narrow repair
`60fb1fa6027167655f4367c6871b31b59a72b873` defers a first signal received during finalization
until every registered removal has run and gives the outer qualification owner the same
catchable-signal unwinding boundary. The focused
qualification and both cleanup-interruption regressions pass in 0.464s; `format-check` passes in
6.3s. The repair delta was inspected for unrelated behavior and no review finding remains open.

Exact-head preflight at `eaa4f174c40d98cd2f44efe5b3f55758c5f61486` passed the 15.015-second
development owner, 0.393-second managed toolchain verification, 21.624-second focused owner, and
678.270-second installed owner. The installed owner again ran no aggregate. The publication command
then reached its 900-second ceiling because the local hosted graph was still running
`layer-forward-smoke` after 863.302 seconds. That graph is already required once in GitHub hosted CI
and does not distinguish a fresh-image risk locally. The candidate is therefore re-scoped again:
fresh-image preflight leaves the common graph to the required hosted check and runs only its local
owner, toolchain verification, focused qualification, and installed owner. The unused parallel
coordinator and its regressions are removed, deleting 362 lines of script and test machinery. This
changes the reviewed execution approach and requires one final comprehensive review after the
re-scope is committed.

The final comprehensive review covered head
`af35e22da8c9f158b09143e8c0217e552e7da8c0` against base tip and merge base
`29b54757c837fdfc610e413acd297d253644e292`, using Codex gpt-5.6-sol at high effort over the full
diff. It found one accepted P1 cleanup defect: PID-targeted cancellation could terminate the outer
qualification or an active Docker client without relaying the signal and reaping that child, so the
installed finalizer was guaranteed only for process-group cancellation. It also identified this
handoff's stale pre-commit next action. Narrow repair
`6878ae75657e4c5ffd76ceb4aa97ad9a292b74cb` adds one shared synchronous signal owner, relays and
reaps the active child before unwinding, permits the remaining cleanup commands to run, and owns
both qualification-parent and image-parent PID-targeted regressions. The focused classifier and
signal owners pass in 0.647s, the complete Linux development-preflight owner passes, and
`format-check` passes. The repair delta was inspected; no review finding remains open.

Exact-head Linux/aarch64 publication preflight at
`39863d05ed62437b05007a0834ac81225fca2e83` passes: development owner 14.849s, managed ensure
0.320s, pin verification 0.072s, fresh-focused 21.456s, and installed owner 586.795s. No common
aggregate ran locally. The user then clarified that 15 minutes is an approximate diagnostic target,
not an absolute number. The authoritative wording now retains the current 15-minute workflow
timeouts while allowing a narrowly longer distinct owner when measurement justifies its value; it
does not allow a timeout increase to substitute for removing duplicate or unowned work.

The post-clarification comprehensive review covered head
`a8aecdbd752abed04c5e7b7ffea06301988c85f4` against base tip and merge base
`29b54757c837fdfc610e413acd297d253644e292`, using Codex gpt-5.6-sol at high effort over the full
diff. It found two accepted ownership defects. First, the PID-targeted signal helper signaled and
escalated only the direct process, so a descendant retaining captured pipes could block cleanup.
Second, the focused inventory overstated real generated-output ELF validation: its native unit owner
feeds `/bin/true` through the production parser, while strict validation of the real published
`main` occurs only inside the aggregate. Repair `15edbd411291017d3a34f93e8a6ba6ff12c1188b`
starts each helper child in a new session, relays and escalates to that process group, and adds a
resistant pipe-owning descendant regression. It also separates focused native parser coverage from
the explicit aggregate's new `fresh-v2-published-elf-smoke` inventory row. The targeted signal and
qualification owners, output-summary suite, qualification inventory, and `format-check` pass. The
repair delta changes no product or aggregate execution behavior; no review finding remains open.

PR #165 merged as `edc5c132225f567c7810f8809819d18b3d4ec45d`. Its exact final head
`2f0a8ac6decd900d44496d90696c029e70a4d258` passed the required hosted check in 12m26s, the
x86_64 installed profile in 12m28s, and the aarch64 installed profile in 13m37s. Each remained
inside the configured 15-minute timeout and approximate operating target without duplicate common
aggregate execution.

**Blocker.** None.

**Intentional uncommitted files.** None; local configuration remains outside the change.

## Merged checkpoint: R7-RUNTIME-PROVIDER (2026-09-02)

Branch `agent/r7-runtime-provider`, based on merged `main`
`88b77ed112d36cb29b948f7212442b3a4f02afcd` (R7-PROMPT PR #163 plus the concurrent R7-TOKENIZER
evidence update). The next consumer-complete R7 boundary is an explicit in-process provider that
turns the existing `GenerationRequest` into completion text through the resident dense runtime.

The proportional design gate is active because this changes the public provider enum/configuration,
adds snapshot and artifact-identity ownership seams, changes the resident decode loop's internal
termination behavior, and coordinates seven modules plus CLI and evaluation. The authoritative
ledger, exact validation order, EOG/max-token semantics, closure matrix, fixed coding-task gate, and
pre-implementation 20-minute qualification ceiling are `docs/specs/r7-runtime-provider.md`.

Design checkpoint `fe3665d44148f4d840d098b394e17a48938e7c4f` and implementation candidate
`8a17034b7c77d1659d32db4e4567d1b20eab7bf5` are complete. The provider retains one GGUF snapshot
while deriving exact model geometry, checking the alignpack source record, and preparing prompt/EOG
ids. Generation is greedy, CPU, resident, at most 128
tokens, non-streaming, unseeded, and without an internal timeout. It returns no
partial text on failure and excludes the terminal EOG id from detokenization. The fixed gate runs
the existing `python-inclusive-range` request through both local OpenAI-compatible llama.cpp and
align-runtime, persists unchanged schema-2 generation records, and requires both patches to pass
the existing task validator.

**Latest durable verification.** `make tokenizer-smoke provider-smoke runtime-provider-smoke
gate-topology-check layer-forward-smoke` passes, including the gate runner self-test, 49-assertion
synthetic provider/CLI matrix, six generation-EOG cases, and the complete shared decode regression.
The re-scoped final-review repair passes `runtime-provider-smoke`, the complete shared
`layer-forward-smoke` in 64.117 seconds, and `alignpack-smoke` with 27 positive fixtures, 128
negative sources, and 20,312 assertions. After the redesigned-candidate repair, the real
`runtime-provider-gate` passes in 75.2 seconds with its full prerequisite checks included in the
measurement; both provider legs again produce the passing patch with SHA-256 prefix
`5d6b107e706a`.
The real `runtime-provider-gate` passed after initial review repair in 60.3 seconds with the pinned
4,683,073,536-byte Qwen model and llama.cpp build 10566: both provider legs produced a passing patch
with SHA-256 prefix `5d6b107e706a`. The gate's earlier 64-token probe established truncation, so the
settled request limit is 128. The comprehensive review of `8a17034b` against base and merge base
`88b77ed` found three valid gate-contract defects: raw completion trailers were admitted,
configured invalid prerequisites could be hidden by an earlier N/A, and an untimed baseline probe
consumed a third task validation. Consolidated initial repair rejects non-exact fixed-task envelopes,
validates every configured prerequisite before N/A, removes the task execution from the topology
probe, and permanently owns these cases in the hosted self-test. Publication owners and aggregate
preflight have not completed yet.

**Publication incident.** Host-native preflight passed the named owner in 75.9 seconds and all
hosted checks in 296.2 seconds, then correctly stopped when the explicitly Linux-only fresh-focused
owner reached `/proc/self/fd` on macOS. The required uid-501 aarch64 DinD rerun then exposed a real
candidate defect: `main` now imports the runtime FFI, but `make build` still assumed an ambient
`libalign_ggml_shim`. A clean Linux owner therefore failed to link. The repair makes `make build`
and `make run` self-sufficient: the default embeds a temporary static unavailable-engine stub and
leaves only `main`, while explicit ggml include/lib inputs retain the real shared-shim path. This
changes the build boundary and authoritative design after the original review, so it triggers one
final comprehensive review after the current-head coding baseline is re-recorded. Clean default and
real-shared builds pass on macOS; the aarch64 Linux clean build plus tokenizer, layer-forward
(128.954 seconds), provider, 48-assertion runtime provider, and topology owners all pass.
The final coding-baseline chain is source `0278e6e4d57d6796872473f73c86e482c7343845` -> oracle
`2ccb3854e03b040740e9d9b9cb62dddafd61fdf0` -> finalization
`94fee5013d4e7af30ed35c02d096599deacd059d`. Its two Linux/aarch64 samples pass in 143.366 and
150.679 ms (147.023 ms median), bind the wrapper, shim builder, and static stub source, and pass the
complete Linux `make baseline-check` including malformed, failure, immutable-oracle, and ancestry
owners.

**Final review and re-scope.** The comprehensive review of stable head
`00e67dab9dcfeb952b96ec393ab6a6f1ebcfcba6` against base tip and merge base
`88b77ed112d36cb29b948f7212442b3a4f02afcd` was performed by Codex gpt-5.6-sol at high effort over
the full diff. Its verdict contained two findings, both accepted: `[P1]` pack and geometry identity
did not survive reopening into the exact objects consumed by inference, so atomic replacement could
retarget validated work; `[P2]` provider generation could render an arbitrary argmax after a
non-finite prefill or decode-step logit plane. The boundary is re-scoped rather than patched around:
the first pack pass returns a retained `SourceIdentity`, the exact inference handle revalidates that
identity, the reopened geometry image must byte-equal the already-derived image before that same
image is parsed, and generation rejects non-finite prefill or step output before publishing token
ids. The existing diagnostic API retains its counter-reporting behavior. This materially changes
the public artifact-identity seam and therefore requires focused owner evidence plus one fresh
comprehensive review of the redesigned candidate before publication.

**Redesigned-candidate review.** `codex review --base origin/main` reviewed head
`de18ced87c248738ba1b47215a882490ecb1ac29` against base tip and merge base
`88b77ed112d36cb29b948f7212442b3a4f02afcd`, using Codex gpt-5.6-sol at high effort over the full
diff. It found two P2 contract-enforcement defects, both accepted: the inference-time geometry
reopen used unbounded `fs.read_file` before its exact comparison, and the complete-gate timer began
after validation-image, full-model-digest, server-version, and scratch checks. The narrow
consolidated repair gives the reopen the same 16 MiB cap as the first pass, owns a cap-plus-one
sparse-file regression that requires the bounded-read error rather than the old path's later
identity mismatch, and starts timing immediately after all configured prerequisites are present.
`runtime-provider-smoke` passes with both repairs. Neither finding changes the public strategy or
baseline-bound artifacts, and no finding remains open.

**Baseline-chain correction.** Clean-build repair `4fc0f26` produced two passing aarch64 Linux
samples, but the first oracle commit mistakenly retained the pending record's `recorded_at` and
empty `canonical_oracle_commit` fields. The corrected projection then followed an already-created
finalization commit, so `check-baseline-chain` properly rejected that non-direct topology. Commits
`9096787` through `a4ee218` are retained as failed evidence. A later valid chain (`4db07fd` ->
`94620c8` -> `52b00eb`) exposed a separate closure omission before review: the recorded task bound
the changed `Makefile` but not its new transitive build wrapper, shim builder, and static stub
source. The task artifact set now names all three executable inputs. The final direct chain named
above supersedes both earlier sequences and is the authoritative shipping evidence.

**Latest publication incident.** Exact-head Linux/aarch64 preflight at `0e7ff4e` passed the named
runtime provider owner in 290.777 seconds and managed Align ensure/verify, then failed hosted checks
at `prompt-seed-attestation-smoke`: that standalone harness imports the exhaustive `provider`
dispatcher and now reaches the runtime FFI, but invoked `alignc run` without the hosted static-shim
wrapper. The complete direct-compile harness audit found no other standalone hosted `provider`
import outside wrapper-owned `main`. The repair routes this one compiler run through
`scripts/run-main-with-shim`; it changes no baseline-bound artifact or public runtime behavior.
The corrected rerun passed the owner in 264.651 seconds, managed Align ensure/verify, hosted checks
in 580.463 seconds, and fresh-focused in 29.872 seconds. Its installed profile first exposed an
outer DinD cgroup-namespace setup error; after the outer wrapper also used the host cgroup namespace,
the profile reached `runtime-provider-smoke` and found that the 1 TiB sparse regression exceeded the
worker's intentional 512 MiB `RLIMIT_FSIZE`. The regression now creates a sparse 16 MiB-plus-one
file and asserts `R6_GEOMETRY_UNREADABLE` / `Invalid`, which still distinguishes the bounded reopen
from the old unbounded read followed by `R6_GEOMETRY` / `identity` while remaining inside the
installed profile's resource contract. That repair passed its former aggregate failure point; the
same installed run then failed at `c6-evaluation-adoption` because `run-prompt-evaluate-smoke`
directly built `src/main.align` without the static shim. The complete direct-main-build audit found
the same latent call in the three opt-in C4 measurement gates. All four now use
`scripts/run-main-with-shim`, closing the root-cause class rather than repairing only the aggregate
consumer. The direct-main audit leaves only the runtime provider owner's intentional real-shim
build outside the wrapper, and the complete privileged Linux/aarch64 `prompt-evaluate-smoke`
passes with the repaired derived generation child.

**Hosted publication incident.** The complete Linux/aarch64 exact-head preflight passed at
`d5d9ec4c98990899c13806f680bb4a11a1d0f477`: runtime-provider owner 230.318 seconds, hosted checks
521.062 seconds, fresh-focused 21.491 seconds, and fresh-installed 2,491.577 seconds. PR #164's
required hosted x86_64 pinned-compiler job then exposed one remaining ELF link-order defect. The
ordinary static shim is one archive object containing both the unavailable path and deterministic
engine functions that call libm, while pinned Align emits its automatic `-lm` before
`-lalign_ggml_shim`; GNU ld therefore reported unresolved `expf`, `powf`, `sincosf`, and `sqrtf`.
The application now explicitly records the shim's real `m` dependency after the shim with the
shipped empty `extern "C" link("m") {}` form. Align Request 54 owns the compiler root cause and its
cross-architecture archive regression. A Linux/aarch64 clean build with `ALIGNC_LINKER=system` and
the complete 49-assertion `runtime-provider-smoke` both pass after the repair. The change does not
move a canonical coding-baseline artifact, so the final chain above remains binding; it does
invalidate the publication stamp and required checks.

**Current next actions.** (1) Commit the explicit libm dependency and Request 54 record. (2) Re-run
exact-head Linux publication preflight. (3) Push PR #164, rerun every required check, merge with a
merge commit, pull current `main`, and continue the next eligible roadmap capability.

**Blocker.** None.

**Intentional uncommitted files.** None after the consolidated redesigned-candidate review repair
commit. Local configuration does not belong in the change.

## Merged checkpoint: R7-PROMPT (2026-09-01)

PR #163 merged as `88b77ed112d36cb29b948f7212442b3a4f02afcd`. The public prompt API and CLI
validate the exact model-carried chat template and tokenize one system/user conversation from a
single retained GGUF snapshot. Focused real-model parity passes against pinned llama.cpp build
10566 on eight cases, 1,538 rendered bytes, and 303 ids. Comprehensive review found three valid
owner/precedence/publication gaps; consolidated repair `1290304` closes all of them. Exact-head
Linux preflight and every required hosted, x86_64, and aarch64 check passed. The valid coding
baseline chain is source `dbbb52e` -> oracle `9359d7b` -> finalization `2586eae`, all reachable from
merged `main`.

## Merged checkpoint: R7-TOKENIZER evidence completion (2026-09-01)

PR #161 merged the implementation as `de44bf0971866d51dfe995e9ae9a03e6fe8ce081`; follow-up PR #162
merged the complete review evidence as `e68a3949dd2a02b006ae9c5f7e7bfdbd668b7415`. Together they ship the public GGUF
array readers, snapshot-stable private Qwen2 tokenizer, exact `--tokenize` / `--detokenize` CLI,
and Request 22's direct Move-field indexing migrations. The hosted owner now covers exact accepted
special-count/length, merge-bucket, adversarial-prefix, decode-output, one-shot-reader, and snapshot
replacement boundaries. The real 4,683,073,536-byte model passes 299 parity cases and two complete
API publication passes against pinned llama-tokenize build 10566: 50,893 input bytes and 69,485
compared ids. Exact-head Linux preflight and all hosted, x86_64, and aarch64 checks passed. The
implementation baseline chain is source `c49ff5720aabbe3468743e7aa252709077e26cdf` -> oracle
`207262bcbc54c0ca677781b79156f8e436f34f3c` -> finalization
`bd5f93257c4add753ec4ea407755fc79114fcba2`; all are ancestors of merged `main`.

## Merged checkpoint: DEV-OUTPUT-SUMMARY (2026-08-31)

PR #158 merged as `5e124c2354ae6b4297fb3aa11b4792247d33b5aa`. The shared wrapper retains
complete verification logs while success emits bounded phase/result/warning/log records and long
runs emit progress at least once per minute. Direct `layer-forward-smoke`, every external preflight
phase, hosted CI, and the fresh aggregate consume it; hosted logs are retained for 14 days.

Against the exact three-run 922-line / 185,927-byte baseline, repaired head `24a6686` emitted
7 lines / 872 bytes while retaining all 921 child lines / 185,893 bytes and the exact 910-warning
taxonomy. Both the 16-line / 2,048-byte maintenance ceiling and the 900-line / 180,000-byte
reduction floor are **MET**. Exact-head Linux publication preflight and all hosted, x86_64, and
aarch64 required checks passed. The comprehensive review's seven validated root-cause classes and
the later workflow-context publication incident each have focused regressions; no finding remains
open.

## Merged checkpoint: R6-PREFIX-TTFT publication (2026-08-30)

Branch `agent/r6-prefix-ttft`, based on `main` merge commit
`c16f14ea5ec2e42d61f7e6644716854d9ca61c2c` (C4-REPAIR-TEMPLATE, PR #156). Authoritative charter
`docs/specs/r6-prefix-key-corpus.md` section 11; capability ledger and closure matrix
`docs/specs/r6-prefix-ttft.md`. The pre-implementation design is commit `a3c5e9e`; implementation
is `17cce70`, the qualification-contract correction is `eb832bf`, and the first measurement record
is `8ebed6b`. The consolidated comprehensive-review repair and exact replacement-measurement head is
`de4cb6ee062d99f173ef8ee1d129588ce00f7d67`. The first reference-host measurement remains withdrawn;
the corrected replacement establishes a **MET** improvement gate and **MET** shipping verdict.

**Required first-action probe is complete.** A throwaway build changed only the Qwen cap to 2,048,
measured a 1,200-token resident `--decode-step` prefill three times, and restored the source. The
three first-token times were 131.686 s, 126.694 s, and 129.543 s; prefill compute was 125.288 s,
121.071 s, and 123.872 s. Mean compute share is 95.44%, and the first-token range is 38,606 ppm.
The precondition passes. Corrected raw ceiling before the measured container-read subtraction is
290,920 ppm at the mean compositional prefix share and 248,183 ppm at the worst, against the
unchanged 150,000 ppm floor. Swapouts moved by zero; compressor movements are recorded in the ledger.

**Settled design choices.** `MAX_PREFILL_TOKENS` becomes 2,048; the corpus uses `KV_WIDTH=1,536`
(168 MiB plane); `akvp` and document versions do not move, and compatibility is one-way because old
readers fail closed on token counts above 32. `canonical-v1e` exists, but its initial task prompts
reuse `prompt-v1` byte-for-byte and its repair prompts are provider-derived rather than frozen
source artifacts, so the corpus takes the charter's honest three-cluster fallback. The gate pairs
single-shot against keyed hit; miss/write cost is a required secondary with an observed break-even
reuse count. Five repeats, warm and >=20 GiB eviction-pressure protocols, and the charter's verdict
rule are fixed before implementation.

**Implementation checkpoint.** Both architecture caps and the independent reader are 2,048. The
hosted owner reaches dense, routed, suffix, and persisted-reader boundaries at 2,048, refuses 2,049,
and keeps long activations out of goldens; the fixed test arena is 512 MiB so the enlarged mask is
real rather than skipped. The repaired `eval/kv/prefix-corpus-v1` holds one 369-id shared prefix and
suffixes of 697, 1,050, and 828 ids. Generation passes the exact complete prompt through a temporary
file with `--no-escape`, proves the shared id prefix, and stores the exact tail; the model-free
checker retains its pinned identities and five malformed classes.
`scripts/run-decode-step --prefix-ttft` is an independent capable path: resident weights, fresh
processes, alternating legs, warm and complete-file eviction protocols, five-pair gate semantics,
compressor records, exact half-away arithmetic, miss cost, and canonical PASS/ERROR summaries.

**Latest durable verification.** With GNU make and the Homebrew library path, repaired
`gmake layer-forward-smoke prefix-corpus-check prefix-ttft-runner-check` passes: all seven owner
blocks, 167 dense decode documents (160 golden rows), the exact-cap oracle-S row, 70 routed decode
documents, shared 369 plus
`[697, 1050, 828]`, five malformed corpus classes, six-container scratch budgeting, safe summary
reservation, and the break-even zero clamp. `gmake fmt`, `gmake format-check`, Python
syntax compilation, and `git diff --check` pass. The pinned generator itself completed and proved
all three complete-prompt compositions. Focused real-OLMoE attempts with one prompt at `N=1` and
`N=2` stopped before any arm run because the callback produced one graph rather than the required
2 or 3; this is the runner's early-EOS prerequisite, not an arithmetic failure. Do not repeat the
unchanged shortened invocation. A fresh real-model pack audit independently walked all 147 dense
members and reproduced row 1,152 B, stage 2,359,296 B, and region 313,389,056 B; together with the
hosted routed boundary it owns the repair until a reference instrument configuration can pass that
prerequisite. The 4 GiB audit pack was moved to Trash after the result was checked.

**Withdrawn reference-host run at exact head `eb832bf34e8e1e8d31f6aa9d78590f211e009f55`.** The canonical
49,218-byte summary is outside Git at SHA-256 `aa1627a0…f833`. All 30 paired observations and 66
fresh processes completed. W has protocol mean 304,668 ppm and leave-one-suffix-out range
**283,489..324,752 ppm**; C has mean 298,502 ppm and range **289,169..314,613 ppm**. W is worse,
and the old arithmetic labelled its 283,489 ppm minimum above the floor. That label is invalid and
there is no current improvement or shipping verdict. C completed 33 reads of an existing unrelated 63,999,836,160-byte
file. W had zero swapouts; C had 4,108, all in duration pair 1's single-shot leg. The observation is
retained as incident evidence. An independent summary audit recomputed every pair and aggregate
exactly, but the corpus identity was invalid, so these numbers establish no improvement or shipping
verdict and must not be reused.

**Valid replacement run at exact head `de4cb6ee062d99f173ef8ee1d129588ce00f7d67`.** The canonical
49,283-byte summary is outside Git at SHA-256 `04ff7d8b…52009f`. All 30 paired observations and 66
fresh processes completed on the corrected 369-token compositional prefix. W has protocol mean
305,846 ppm and leave-one-suffix-out range **291,511..321,192 ppm**; C has mean 326,471 ppm and
range **306,038..336,707 ppm**. W is worse, and its 291,511 ppm minimum clears the 150,000 ppm
floor, so both the roadmap improvement gate and shipping verdict are **MET**. An independent
read-only audit reproduced the exact completion sequence, coordinates, alternating orders,
half-away reductions, aggregates, miss break-even values, 33 exact 63,999,836,160-byte eviction
reads, VM deltas, and final rule.

**Comprehensive review.** `codex review --base origin/main` reviewed head `8ebed6b` against base tip
and merge base `c16f14e` with Codex `gpt-5.6-sol` at xhigh. Four findings are accepted: P1 corpus
escape rewriting, P1 stale OLMoE cap arithmetic, P2 diagnostic repeats emitting an improvement
gate, and P2 unpacked embedding row sizes in the allocation ledger. The corpus fix also exposed a
BPE boundary merge; the final `".\n"` now belongs to each suffix so `shared ++ suffix` is exactly the
complete prompt's tokenization. The other repairs are committed in `de4cb6e`. Because this repair
materially changed the measured corpus, the replacement full measurement was run from zero and is
audited above. The required final comprehensive review of the corrected candidate is recorded below.

**Final comprehensive review.** `codex review --base origin/main` reviewed result-record head
`913055e` against base tip and merge base `c16f14e` with Codex `gpt-5.6-sol` at xhigh. Three
findings are accepted: P1 summary output could alias and overwrite an input, P2 scratch preflight
budgeted one of six live containers, and P2 a sufficiently fast miss could produce a negative reuse
count. The consolidated repair rejects existing, aliased, symlinked, work-tree, and unavailable
summary destinations before packing; exclusively reserves the output and uses a unique atomic
temporary; budgets all six containers; and clamps break-even reuse at zero. A new model-free owner
covers every root-cause class. The repair is commit `398eadd`. It changes preflight and secondary
reduction only, so the audited 30-pair timing evidence remains bound to `de4cb6e` and needs no
retake.

**Publication preflight incident.** Exact-head preflight at `398eadd` passed the named owner,
managed-toolchain ensure, and pinned build, then failed in hosted `gguf-smoke`: its leak guard
treated every repository `manifest.json` as a generated GGUF fixture and rejected the new tracked
prefix corpus manifest. The same basename-only root cause existed in `model-ir-smoke` and
`expert-trace-smoke`. The bounded repair keeps each generator's real leak contract — generated
extensions plus `$root_dir/manifest.json`, because root is the fixed cwd — without rejecting an
unrelated consumer manifest. Focused `gmake gguf-smoke model-ir-smoke expert-trace-smoke` passes.
The failed preflight retained 2,490 lines / 441,553 bytes and ended with a five-line actionable tail;
that exact baseline is recorded in roadmap item 40, which remains planned and inactive.

**Publication environment correction.** The leak-guard repair is commit `cd6c661`. A second
host-native preflight at that exact head passed the named owner, managed-toolchain ensure, pinned
build, and all hosted checks, then failed when `fresh-focused` reached
`run-fresh-source-identity-smoke` on macOS: `/proc/self/fd` is absent. The retained log is 4,374
lines / 815,682 bytes. This is not a product defect or a portable-owner gap: the Section 9 fresh
compiler and its descriptor-relative source identity are explicitly Linux-only, and Section 9.11
requires the focused and installed owners on a native aarch64 Linux host. No skip or Darwin
substitute is admissible. The publication preflight must therefore run from zero in the existing
unprivileged Docker-in-Docker Linux wrapper.

**Installed-profile baseline incident.** The corrected Linux preflight at `594dfb5` passed the named
owner (182,004 ms), managed-toolchain ensure/verify, every hosted owner (732,642 ms), and every
fresh-focused owner (21,101 ms). The installed image, trust, and boundary phases passed, but the
worker aggregate failed after 1,417,685 ms with the deliberately generic `ERROR CHILD aggregate`;
cleanup passed. A same-head installed-only diagnostic retry reproduced the failure after 1,518,283
ms and exposed the root cause: `baseline error: current evaluation artifacts differ from the
recorded baseline`. `Makefile` is one of the twenty canonical baseline artifacts and this capability
adds three focused targets, so Section 2.4 requires a fresh source, immutable-oracle, and canonical
finalization chain before capable evidence. The diagnostic captured 16,562 stderr bytes; its
bounded 8,192-byte tail was mostly repeated Git graft deprecation hints before the useful baseline
failure and Make lines. The full failed Linux preflight retained 4,632 lines / 840,851 bytes.

**Coding baseline refresh complete.** The required Linux/aarch64 chain is source
`94844afb1b0109154827b0c84dc6e2eea7456ae4` -> immutable oracle
`ad6a59c0f8ac3228575ab908c896d08762a84138` -> canonical finalization
`570ac2c13fc7895f059cf62a84d3495fb8f0561b`. The pending record used the unchanged pin
`3a34febe`, Linux 6.11.11-linuxkit, Python 3.12.3, and two passing samples at 225,612,542 ns and
180,063,625 ns. The oracle commit changes only
`eval/expected/coding-v1-reference-oracle.json`; the finalization commit changes only
`eval/baselines/coding-v1-reference.json` and its digest; the pending file is absent. Linux
`make baseline-check` passes the canonical verifier, every invalid/failure smoke, Git isolation,
and the complete strict chain checker.

**Next actions.** (1) Commit this completed-chain record without changing a recorded baseline
artifact. (2) Run exact-head publication preflight from zero in the unprivileged Docker-in-Docker
Linux wrapper. (3) Publish, merge without squash/rebase, verify all three baseline commits are
ancestors of refreshed `main`, and stop. This pull request is the user-requested stopping
checkpoint: do not start item 40 or another roadmap capability after merge.

**Next planned capability, not active: DEV-OUTPUT-SUMMARY, roadmap item 40.** Successful owner and
toolchain phases repeatedly emitted 912 lines / approximately 45,720 transport tokens and 564
lines / approximately 30,038 transport tokens before useful result/progress lines in this session;
publication attempts retained 2,490 lines / 441,553 bytes, 4,374 lines / 815,682 bytes, and 4,632
lines / 840,851 bytes before their actionable failure tails; the installed diagnostic's captured
16,562-byte stderr needed an 8,192-byte tail that was still dominated by repeated Git hints.
Item 40 should baseline exact bytes/lines, retain complete logs and digests, summarize warning classes
on success, expose bounded diagnostics on failure, preserve exit/signal/pipe semantics, and keep
minute-level progress visible. It is planned as a separate consumer-complete developer capability,
not folded into this performance claim.

**Blockers.** None. Request 22 remains non-blocking because the checked-in ids come from the pinned
Python/instrument path and Align consumes decimal ids only.

**Intentional uncommitted files.** This completed-chain record is the only intended work-tree
change until commit. Build products and measurement summaries remain outside Git.

## Merged checkpoint: C4-REPAIR-TEMPLATE review repair (2026-08-30)

Branch `agent/c4-repair-template`, merged with `agent/c4-repair-editset` (`6ccbb88`) and
`origin/main` (`451aa66`, PR #155) by merge, never rebase. Stable reviewed head was `6b73560`, with
base tip and merge base both `451aa66`. The consolidated review repair is committed as
`a36b15bfce75eebf2b961906220dcfc7842ba7d6`. Final-review re-scope was committed before
implementation as `f9cd0a59e6b734974614af816ee4f835cfa72c67`; its implementation is owner-verified
as `d738f56cca23209db1bd1b418c427def87ebc72a` and is the active publication candidate.

**Qualification correction.** The immutable evaluation has 12 initial plus 12 repair attempts:
**24 provider calls**, not the pre-committed maximum of 22. The wall time was 700.452 s inside the
separate 3,600 s ceiling, and the persisted arithmetic is `repair_recovery_paired_count: 1`, but the
named qualification failed its call-cost contract and has no `MET` verdict. The gate record's
`addressable_ran_attempts: 22` is a hard-coded producer error. The three JSON artifacts remain
unchanged; `docs/specs/c4-repair-template.md` section 11.4 and the evidence README own the
correction. Independently, the only observed recovery repairs an attempt-1 regression introduced by
version 3, candidate pass/gain counts do not improve, and C4 remains open. The secondary remains 10
against `< 10`; `PATH_NOT_EDITABLE` moves 2 -> 0 but becomes `UNCHANGED_FILES`.

**Comprehensive reviews.** Two explicitly disjoint independent adversarial reviews covered head
`6b73560`: (A) adapter/import-chain/version-3 producer found five issues; (B)
evaluator/scorer/validator, Align verifier, freeze, gate evidence, documentation, Makefile, and
baseline topology found six. Both verdicts were changes requested. All eleven were accepted and
repaired as root-cause classes: response identity survives post-generation errors and is tied to the
existing nonzero provider-request digest in all three validators; cleanup clears lower-priority
refusal classification; completion redaction is single-pass; base-adapter errors normalize; task
definition edit/source limits are preflighted; freeze `--check` is read-only; call and wall ceilings
fail publication closed; ran counts and agreement derive from rows; future records include image ID
and exact command; the immutable historical breach is corrected in prose; and the authoritative
ledger's member/declared-patch cells are synchronized.

**Repair verification.** All 13 macOS owners pass together: `gmake build check format-check
gate-topology-check prompt-verifier-smoke prompt-score-smoke prompt-gate-validator-smoke
prompt-render-parity-smoke prompt-template-adapter-smoke prompt-repair-adapter-smoke
prompt-measurement-adapter-smoke prompt-model-smoke prompt-state-smoke`. Linux/aarch64
`run-prompt-evaluate-smoke` and the full `run-prompt-template-adapter-smoke` pass in
`c4-repair-measure:latest`. `freeze-canonical-v1t --check` and `git diff --check` pass. Evaluator is
252,862 B, leaving 9,282 B in the four-chunk launch window; its Align source pin is `dc1c7eec…`.

**Coding-baseline chain, re-recorded.** `Makefile` is one of the canonical baseline's recorded
inputs. The replacement chain is
`a36b15bfce75eebf2b961906220dcfc7842ba7d6` ->
`37c09a36b1c79781ec76caa51a2f54c011827f9d` ->
`c1a52b568902fcb246d39ccd96cb916ea04dcc79` (clean source -> immutable oracle -> finalization),
measured on Linux/aarch64 with the pinned managed compiler. Linux `gmake baseline-check` ends
`baseline chain: PASS`. The first attempt mounted the Git common directory read-only and failed
only when the isolation smoke tried to create its temporary namespaced replacement ref; the normal
writable mount passed and the smoke removed its ref.

**Final review and re-scope.** Host-native Codex (`gpt-5.6-sol`, xhigh) comprehensively reviewed
`dc3107e1ca2c9f650c68e1c61e6328111fff9c26` against base/merge-base `451aa66` and requested changes:
two major and one minor. The repair had re-frozen measured `prompt-v1t` in place even though its
checked-in evidence binds the old scope and adapter digests; the call and wall ceilings were
post-hoc publication checks rather than cost-containment boundaries; and the response-identity
repair was missing from three ledger/mapping statements. Because the two major findings change the
approach, this is a re-scope rather than another repair/review loop.

**Re-scoped boundary, committed before its implementation.** Restore measured `prompt-v1t` at its
original immutable identity (`scope` `84a5e395…`, adapter runtime `PYTHON:03379e26…`) and mint
`prompt-v1u` at new paths and IDs for the repaired adapter. The old three JSON evidence artifacts
bind only `prompt-v1t`; `prompt-v1u` is explicitly unqualified. Before any provider probe or
generation, the gate derives the structurally possible call count from the selected corpus and
rejects the current 24-call topology against the fixed 22-call ceiling. Both the in-container
evaluator and host Docker boundary receive monotonic deadlines and terminate their exact process
group/container on expiry. Deterministic stubs own topology rejection, deadline cleanup, and
no-publication behavior.

**Re-scope implementation and verification.** The thirteen measured v1t files are restored
byte-for-byte to `6b73560`; its replacement freeze command is check-only and refuses writes. The
repaired fifth freeze is `canonical-v1u` + `prompt-v1u`, 31 members, and is marked `UNQUALIFIED`.
The gate derives 24 possible calls and rejects before provider probing or output-directory creation;
both the host Docker child and in-container evaluator have monotonic process-group deadlines, and
Linux uses `PR_SET_CHILD_SUBREAPER` to reap terminated grandchildren. Deterministic stubs cover the
24-vs-22 refusal, an admissible four-call topology, missing exact command, malformed image identity,
no publication, deadline cleanup, child termination, and Linux reaping.

All 13 macOS owners from section 11.5 pass together with the required Homebrew library path. The
full Linux/aarch64 template-adapter smoke and `run-prompt-evaluate-smoke` pass in immutable image
`sha256:33fa9e4446ab…` using the pinned-revision Linux compiler. Both v1t sealed verification and
v1u reproducibility check pass; the three historical gate JSON artifacts are unchanged. Linux
`make baseline-check` ends `baseline chain: PASS`; `make fmt`, Python syntax compilation, and
`git diff --check` pass. The provider qualification was not rerun.

**Next actions.** (1) Run exact-head fresh-image preflight with
`prompt-template-adapter-smoke` as owner. (2) Publish an English PR with all review envelopes,
finding dispositions, correction, and exact verification; merge with `--merge`. (3) Refresh `main`
and begin roadmap item 38, R6-PREFIX-TTFT.

**Blockers.** None technical. Do not rerun the provider qualification: its structurally possible 24
calls exceed the fixed 22-call contract, and section 11.4 records the required boundary
reconsideration.

## Merged checkpoint: R6-MOE-RESIDENT-DENSE (PR #155, `main` `451aa66`, 2026-08-30)

Branch `agent/r6-moe-resident-dense`, implemented on `agent/r6-olmoe-decode` head `bf7c87d` and then
**merged** with `origin/main` `45ff38e` (R6-OLMOE-DECODE, PR #148, which itself carried
R6-PREFIX-SUFFIX-PREFILL, PR #149) by `git merge` — **never a rebase**. One conflict, in
`docs/align-requests.md`, where both sides appended after Request 49: resolved by keeping this
capability's client paragraph **and** `main`'s next-free-number comment, with the comment extended
to record that this capability proposes none either.

The four things that merge re-checks all held:

- **roadmap item 35.** After the second merge `main` carries 30, 31, 32, 33 and **36** (36 is
  MF-SINGLE-TOKEN-LOGITS, PR #151); 34 is still claimed by `C4-REPAIR-EDITSET` and is not on `main`,
  so **35 is still this capability's**. The item was re-ordered to sit between 33 and 36 after the
  merge placed it below 36.
- **`R6_MOE_DECODE_STEP` schema 2**, unchanged by the merge.
- **next free Align request number 53.** `docs/align-requests.md` still ends at Request **52** after
  the second merge; this capability takes none and adds clients to 33, 35, 36, 38, 47, 48, 49 and
  **51**, and records **50** as explicitly not a client.
- **which goldens regenerate:** the implementation moved `scripts/moe-decode-step-golden.jsonl`
  59 -> 69 rows. Review repair adds one UTF-8 refusal row, making **70**. Main's later capabilities
  moved `scripts/decode-step-golden.jsonl` 116 -> 155; the same root-cause repair adds two refusal
  rows and corrects one forced-wrap counter, making **157**. `src/model_forward.align` stays
  byte-unchanged. `main` also moved `AGGREGATE_TIMEOUT` from 1,800 s to 3,600 s in the `Makefile`;
  nothing in this capability reads it.

**A second `git merge origin/main` took `334f524`** — PR #150 (C4-REPAIR-MEASURED: Track A only,
plus the `Makefile`'s `.PHONY`/`AGGREGATE_TIMEOUT` and the baseline chain) and PR #151
(MF-SINGLE-TOKEN-LOGITS). One conflict, in `HANDOFF.md`, where both sides opened a new `## Active`
block: resolved by keeping this capability's and relabelling MF-SINGLE-TOKEN-LOGITS' as the merged
checkpoint it became. **PR #151 adds `gathered: bool` to both `GraphMembers` records**; the merge
carried `gathered: false` into `moe_decode_step.decode_embed_members` from `main`'s side, which is
correct — that member bakes the token into its own `source`/`pack` offsets and reads one row
directly rather than gathering `pieces` — and this capability adds no other `GraphMembers` builder.
`scripts/moe-model-forward-golden.jsonl` gained a row from `main`'s side (98 -> 99) and
`src/moe_model_forward.align` changed there; neither is this branch's.

**Capability.** The dense member set of a routed model held resident across an `N`-step decode loop,
experts still streamed. CPU only, OLMoE-1B-7B-0125-Instruct Q4_K_M. Authoritative ledger
`docs/specs/r6-moe-resident-dense.md`: sections 1 to 6 are the pre-implementation design, committed
in `f8796ea` **before** the first line of implementation and not rewritten since; correction 18
adds one explicitly marked `Shipped:` note. Sections 12 to 14 record the results, every deviation,
and the ledger-to-diff mapping. All four design-gate triggers fire.

**State.** Implemented, measured, reviewed, repaired, and published as PR #155. Implementation and measurement are
committed through `a94ab24`; the consolidated review repair is `588bcbf`. A third merge takes
`origin/main` `c1ad71e` (the session-stop handoff, PR #154) without rebasing; its only conflict was
this active block, resolved by retaining the completed repair state and queuing the other unfinished
branch below. The tree is buildable and every hosted owner passes.

**Performance contract, committed with the design.** Owner `docs/specs/r6-resident-weights.md`
section 3.4. Baseline 3.63 s (`timings.elapsed_ns`, prompt 1, `N = 16`, `KV_WIDTH` 256, reference
host, item 32 section 12.3). Primary metric `weights.step_dense_pack_bytes`: 4,049,258,496 -> **0**.
Cost ceiling **276,000 ppm**, floor **150,000 ppm** adopted unchanged, predicted 2.63 s, margin
1.84x.

**Measured twice, and the measurement of record is the quiet-host run (section 12.4).** It was taken
with no `llama-server`, no container and a completely clear process table at **8.47 GB free**, and it
**reproduced the committed baseline**: streamed `[3.458, 3.551, 3.928]` s against 3.63 s, a median
21,693 ppm away, where the first run had drifted 857,000 ppm. Byte clauses hold exactly at all twelve
points, oracle D is `MATCH` on all four prompts, the region is 311,066,624 B reproduced independently
from the pack document, and `wrap_count` is 306 -> 1 — **identical in every field to the contended
run**, which is what a counter is supposed to be.

**The elapsed leg is `BELOW FLOOR` at 138,402 ppm against a 150,000 ppm floor** — 92 % of the floor,
50 % of the ceiling. Median 86,825 ppm, best-of-3 84,187 ppm, so no reading clears it. The other
three prompts at `N = 16` give 138,128, **156,687** and 147,670 ppm: one prompt does clear the floor
and it is not the fixed task, which section 3.7 chose before any number existed and which is not
changed now. `INDETERMINATE` does not apply (streamed spread 129,116 ppm inside the 276,000 ppm
ceiling) and neither does the `miss` label (the result is above half the ceiling). **No elapsed claim
is made; section 4.6 clause 12 puts the capability on clauses 1 to 11**, which hold exactly. Clause
12 is **`BELOW FLOOR`** and that is the settled answer, not an open item.

**The first run (section 12.5) is kept as evidence** with its drift stated. Getting the quiet host
took two attempts: one 4-hour poll at an 8 GB floor that never fired (80 samples; a Qwen
`llama-server` present in 80 of 80 and memory 2.05-5.82 GB), and a second at a 6 GB floor — the floor
the session's other benchmarks used — that fired on its 42nd sample at 8.47 GB, so the relaxation was
not load-bearing.

**`gmake moe-decode-step-qualification` refuses on this host**, at its own instrument cross-check
and before the arm runs, with the same two `result_output` sums `docs/specs/r6-olmoe-decode.md`
deviation 4 records (-113284.835938 against -111030.03125). The R2C `llama-eval-callback` is a
static `GGML_BLAS`/`GGML_ACCELERATE` build; the ggml the arm and `llama-debug` share is not; and the
`llama-debug` built from the pinned source that item 32's qualification of record used is not on
this host. **Section 15 of that document owns the fix and nothing here works around it** — no check
was relaxed and no switch was added. The measurement was taken by a standalone driver running the
**same** shipped invocations (section 12.3), which is sound because an instrument skew is identical
on both sides of oracle D and cancels, and the primary metric reads neither instrument.

**Blockers.** None. Nine Align gaps are met and all nine are already recorded (Requests 33, 35, 36,
38, 47, 48, 49, 50, 51); none blocks. Request 49 gains a new *shape* of client, Request 51 gains its
first reproduction by a reader who did not know the answer (`arena` is a reserved word, and cell
MRD-P1's probe hit repro 1 exactly), and Request 50 gains **no** client — recorded so the register is
not inflated.

**Constraints.** CPU only. Experts stay streamed **by design**: whole-model residency would make
`residency.expert_bytes` unreachable and `RESIDENT=weights` is refused by name on this arm. No TTFT
or throughput claim; the R6 gate stays unmet.

**Review.** Two independent reviewers covered disjoint risks at clean head `a94ab24`, ledger
`f8796ea`, merge base `334f524`: reviewer A covered implementation and returned request changes
with one major and three minor findings; reviewer B covered specification, evidence, and governance
and returned approve with repairs with four major and seven minor findings. All findings were
validated. The UTF-8 abort, wrap-counter semantics, stale handoff/request/count/cross-reference and
oracle-D prose, verdict vocabulary, spread denominator, worst-pairing description, and portability
precedent are repaired. The requested second fill-failure case is not added because no validated
pack can reach that failure; the forced wrap failure owns the same live-region teardown window.
Commit `de83ceb`'s misleading subject is accepted as historical metadata and not rewritten; its body
and `a94ab24` make the supersession explicit. A final host-native review of the consolidated delta
found one P3 documentation mismatch: three unchanged golden row counts still described the older
merge base. They are refreshed to 63, 29, and 99. No finding remains unresolved.

**Publication.** Exact-head preflight passed at `94482e3`; all three required GitHub checks passed,
and PR #155 merged as `451aa66`.

**Intentional uncommitted files.** None.

## Queued after C4-REPAIR-TEMPLATE

- Roadmap item **38**, R6-PREFIX-TTFT, follows item 39. Its charter is
  `docs/specs/r6-prefix-key-corpus.md` section 11.

**Host facts worth keeping:** serialize the 16 GiB host across Track A gates, DinD fresh-image
preflight, real-model qualification, and timing benchmarks. Run DinD as uid 501; bwrap inside Docker
needs `--security-opt systempaths=unconfined`. Do not pin >= 2-token decode-step or >= 4-token
prefill activations in a hosted golden because arm64 and x86_64 can differ in the last bit.

## Merged checkpoint: R6-PREFIX-KEY (PR #153, `main` `661dd3d`, 2026-08-30)

Branch `agent/r6-prefix-key-corpus`, cut from `agent/mf-single-token-logits` `40eb965` — that
branch's merge of `origin/main` `45ff38e` (PR #148). It was **stacked on roadmap item 36**, which
has since merged as **PR #151** (`main` `334f524`, item 36's final head `d538066`) and is now merged
into this branch by `git merge`, never a rebase. The stack existed because a store that *writes*
containers requires item 36's fix: item 33's `T_prefix >= 2` refusal existed only because a
one-token prefill computed the wrong embedding row, and a store would have persisted that wrong
plane and served it forever. **The merge moved the decode-step golden's base from 141 to 139 rows**:
item 36's `d538066` moved `ds-suffix-single-shot-2` and `ds-suffix-prefix-one` into
`BOUNDARY_CASES`, because a two-token decode step differs by one ULP between arm64 and x86_64. The
store rows sit on top of that base and none of them carries a decode activation. `origin/main`
`8d095a4` (PR #152, C4-REPAIR-EDITSET) is merged in on top by a second `git merge`, again never a
rebase; both conflicts were `Active`-block and roadmap-entry collisions resolved by keeping both
sides, and nothing that capability changed touches this one's arm, scripts, or goldens.

Roadmap item **37**. The design gate fires on all four `CLAUDE.md` triggers. The ledger is
`docs/specs/r6-prefix-key-corpus.md`, **committed at `8238df6` and not edited**: sections 1–10 are
the contract, section 11 is item 38's charter, **section 12 records every implementation deviation**,
and section 13 records the results.

**Implemented, verified, published as PR #153.** `--decode-step` gains a sixteenth operand,
`STORE`, a caller-created directory that is mutually exclusive with `KV_SAVE` and `KV_LOAD`. The arm
derives a 32-byte key — SHA-256 over a 152-byte preimage of three digests plus `pack_total_bytes`,
`kv_width`, `token_count`, `plane_layout_version`, `element_type`, `format_version`, `key_version` —
and addresses `<STORE>/<64-hex>.akvp`. **A hit loads through the unchanged L1–L14 path; a miss
prefills, saves through the unchanged writer, and continues**, and the two produce byte-identical
documents outside three store fields and oracle Q's own set (oracle K). **A miss is only a missing
file**: three hosted rows place a broken container at a key path and assert `R6_KV_DIGEST("plane")`,
`R6_KV_TOKENS`, and `R6_KV_IDENTITY("pack")` rather than a re-prefill. Schema **6** adds a `store`
object to every document; **no path is published**. `src/kv_plane.align`'s writer, reader, header
plan, and every bound are unchanged and the container is asserted byte-identical to a `KV_SAVE` one.

**Files.** `src/kv_plane.align` (+`derive_key`, `store_path`, four constants),
`src/decode_step.align` (the operand, step 2d, L0, `render_store`, schema 6),
`src/model_forward.align` (**five `Outcome` fields only** — section 12 deviation D1),
`scripts/kv_plane_reader.py` (a second preimage implementation and the `KEY` verdict),
`scripts/run-layer-forward-smoke` (a third preimage implementation, 16 golden rows, oracle K/D),
`scripts/run-decode-step` (the real-model store leg and a third analysis block),
`scripts/decode-step-golden.jsonl` (139 → 155 rows), plus `docs/specs/roadmap.md` (items 37 and 38),
`docs/align-development.md`, `docs/align-requests.md` (Request 53), and the ledger. **The Makefile
is untouched**: no target, no aggregate membership, and no check topology moves.

**Verification, all green at this head** (`gmake`, `LIBRARY_PATH=/opt/homebrew/lib:/opt/homebrew/opt/openssl@3/lib:/opt/homebrew/opt/zstd/lib`):
`gmake build`, `gmake check` (31 units), `gmake layer-forward-smoke` (159 documented cases, 155
golden rows, 42 codes), `gmake ggml-spike-smoke`, `gmake alignpack-smoke`,
`gmake gate-topology-check`, `gmake decode-step-qualification` (real model, 4 store prompts, PASS),
`gmake fmt` leaves no
diff, `gmake format-check`, `git diff --check`. The golden movement was verified **mechanically**:
all 139 pre-existing rows differ only in the document's own `schema_version` 5 → 6 plus a default
`store` object, in the same order, with no row removed — the container header's separate
`document_schema_version` stays 3 (section 12, D15). **Five ledger mutants were run at the final head
and all five died**: a preimage field dropped in one of the three implementations, a hit treated as a
miss, a key that ignores the token stream, the container's path published in the document, and a
miss that saves after the suffix pass.

**One comprehensive review is complete and its findings are repaired** (section 12, D15–D21 plus
addenda to D6, D7, and D14). Two code repairs: W5 maps `R6_KV_CLEANUP_FAILED` to `store[cleanup]`
so no writer code can leak the derived path into `error_detail` (D16), and `derive_key` bounds
`kv_width` and `token_count` from **above** as well as below, because both narrow to `u32` in the
preimage (D19). One new golden row, `ds-store-suffix-unwritable`, gives D14's moved call site its
own failure regression. The preimage is **unchanged** and every key in this document still holds:
D17 records the `document_schema_version` coupling that keeps it safe rather than spending reserved
bytes on it. D14 and a `KEY_VERSION` mutant were re-injected at the repair head and both died.

**One real defect was found and fixed during implementation, and it is deviation D14.** The
`KV_SAVE` writer's call site is *after* the suffix pass, which was correct for every prior run
because `SUFFIX` is illegal beside `KV_SAVE`; a keyed **miss** is the first run that has both, and
the first implementation inherited the position and persisted a plane carrying `T_prefix + S`
columns under a header declaring `columns_persisted = T_prefix`, with the suffix pass's
`prefill_argmax`. It round-trips through the arm, so oracle K passed — it was caught by the two
container assertions instead: the keyed container was **not** byte-identical to the `KV_SAVE`
container of the same prefix, and the independent reader refuses it as `ZEROTAIL`. The fix is one
guarded call site before the pass; the regression is `ds-store-suffix-vs-kv-save`, which is also the
fifth mutant.

**The real-model qualification is run and `PASS`** (section 13.6). `gmake
decode-step-qualification` on the reference host, **2026-08-30 04:48:38-05:04:16, 15 min 38 s**, of
which the store leg is **48.71 s** against risk 7's 120 s threshold (D7). Four prompts, a keyed miss
and a keyed hit each, resident at 16 GiB physical: **oracle K, oracle S on both legs, gate G1 on
both legs, and oracle B are all IDENTICAL**, four distinct keys address four 29,970,432 B containers
each byte-identical to `KV_SAVE`'s and accepted by the independent reader's `--check-name`, and
`store.lookup_ns` is 6.5-9.7 us. Gate G1 was the one assertion the dry run could not reach and it is
now closed on all eight legs. Getting the host took **three polling windows** — 18:30-20:01,
20:47-00:47, and 00:56-04:48 — against the 6 GB coordination floor, held in turn by two
Docker-in-Docker preflights, a `llama-server` resident on the same model for over eight hours, and
an aggregate `make` run. **Nothing was killed, nothing ran below the floor, and no degraded
measurement was recorded.**

**Next actions, in order.** (1) `python3 scripts/pre-pr
--owner-test layer-forward-smoke -- gmake layer-forward-smoke`. (2) Publish the pull request. One
comprehensive review is complete and repaired; another is **not** required — the qualification
recorded a result and changed no design, contract, or code. (3) Merge; item 36's precondition is
discharged.

**Blockers.** None. Item 36 merged as PR #151 and is merged into this branch, and the host
qualification is run and green.

**New Align request 53** (`std.fs` `create_dir` / `read_dir` / `is_dir`), `PROPOSED`, `medium`,
non-blocking; its resume condition is a store eviction/GC capability. **The number is re-checked
at both merges and holds**: `origin/main` `8d095a4` claims **52** for C4-REPAIR-MEASURED's `Option`
partial move — the request section 8 predicted and reserved — so the register runs 1-52 and 53 is
this capability's. Request 30
gains a third client (the store's check-then-create window, which at this pin lets a concurrent loser
**overwrite** rather than be refused — deviation D6), Request 49 gains a recorded **negative** client,
and Request 31 gains the correction a store owes it and **stays low and non-blocking** with its
reason.

## Merged checkpoint: C4-REPAIR-EDITSET (PR #152, `main` `8d095a4`, 2026-08-30)

Branch `agent/c4-repair-editset`, originally stacked on `agent/c4-repair-measured` at `c07775c`,
now merged with `origin/main` at `4940005` (PR #150, which merged that parent capability).
Implemented, verified, **measured**, and **reviewed three times** — two disjoint round-one reviewers
and one final delta review; every recorded finding is repaired and nothing is uncommitted.

**GATE RESULT: `NOT_MET` — a measured negative, and a directional one.** 12 rows, 22 provider calls,
**839.492 s = 13 min 59 s** against a 60-minute recorded ceiling. `repair_recovery_count: 0` and
`repair_recovery_paired_count: 0`. **`repair_editset_attempt_count: 6`** — exactly the addressable
arm stated before the run, so all six eligible repair prompts carried `EDITSET` and the drop ladder
never fired (8,348-16,904 bytes of 65,536). Evidence at `eval/prompt/c4-editset-gate/`; the per-row
table and the analysis are in spec section 11.4.

**The checked-in evidence is the run from the clean committed head `9516e75`** — the repaired head
— taken on the same terms C4-REPAIR-MEASURED used: `align_llm_clean: true` and all three
reachability fields `VERIFIED`. **Three runs of this corpus now exist and every correctness value is
identical in all three**: same verdict, same rows, same statuses and failure kinds, same
`patch_size_bytes`, same six-attempt denominator, same aggregates, same 8,348-16,904 assembled
bytes, the same **four** patch digests, and the same `edit_set` block digests, path for path. The
first ran from the uncommitted tree (`align_llm_clean: false`, and of the three reachability fields
only `align_llm_reachability: UNVERIFIED` — the one an uncommitted head makes unanswerable); the
second from `de56c60`; the third is this one, needed because review repair moved the repair
adapter's bytes and every row names that adapter by digest. The clocks moved: 839.492 s against
940.931 s and 823.67 s, and 8.33-52.69 s / median 21.73 s against 8.93-52.57 s / median 22.25 s and
8.58-51.54 s / median 19.09 s. So did per-run environment identity, which is neither a correctness
value nor a gate input: the sandbox directory is fresh each run and every `unittest` traceback frame
in `diagnostic_stderr` quotes it, so the `STDERR` section moves the repair prompt's own bytes —
`rendered_prompt_sha256` differs on six `REPAIR` attempts between the last two runs, with the
snapshot and request digests that bind them (spec section 11.4 names them). The repair provably
could not have reached any row: the largest
realized `edit_set_total_bytes` is **1,160 bytes** against a 16,384-byte limit. Digests:
`c4-editset-evaluation.json` `1b3ebbb6…`, evidence `549879df…`, record `6053086f…`.

**The question C4 could not answer is answered.** On all four rows where both attempts produced a
patch, `attempts[1].measurement.patch_sha256` equals `attempts[0]`'s **exactly** — the same bytes,
not merely the same byte count. And the persisted `edit_set` says more: on the two
`record-codec-round-trip` CANDIDATE rows the model re-emitted a byte-identical edit set, while on
the two PARENT rows it dropped the file it had reproduced unchanged and kept the other one
byte-identical, producing the same patch anyway. On the two `duration-half-away-from-zero` PARENT
rows, shown its own rejected answer, it returned the pinned files **unchanged** — a well-formed
answer that changes nothing, so every hunk is empty and no patch is synthesized. A mode change from
a wrong patch to a **no-op**. `c4-repair-measured.md` section 5.7's tie-breaker is answered **in
the negative**: the missing edit set was not the binding constraint, and the next capability is the
prompt, the template, and the edit policy rather than more adapter work.

**Capability.** Carry the failing attempt's own edit set into the repair prompt.
`docs/specs/c4-repair-editset.md` is the authoritative ledger and section 11 is the implementation
record. C4-REPAIR-MEASURED returned `repair_recovery_paired_count: 0` over ten repair attempts; its
evidence shows that on all **six** attempts where attempt 1 had produced a validated edit set —
`record-codec-round-trip` x4 and `duration-half-away-from-zero` PARENT x2 — attempt 2 returned a
patch of exactly the same byte count. That is the tie-breaker section 5.7 of that document named,
and this capability is its option B.

**The surface decision.** A new `scripts/prompt-repair-adapter.py` **loads the frozen
`scripts/prompt-measurement-adapter.py` by path** and calls its functions: containment, sealing,
redaction, process ownership, generation, validation, and edit parsing have exactly one copy. Only
`measurement()` and `assemble()` are near-copied, and their divergence from the frozen originals is
asserted against `eval/fixtures/c4-repair-editset/adapter-divergence.diff` — a 209-line normalized
unified diff that a reviewer reads as one artifact. Three digest pins hold the base file
byte-identical: a constant in the new adapter, the `canonical-v1e` file-set manifest, and the
per-invocation artifact snapshot; `scripts/freeze-canonical-v1e` asserts all three agree before it
mints anything.

**Schema.** `TASK_MEASUREMENT` 1 -> 2, gaining `edit_set`, `edit_set_total_bytes`, `patch_sha256`,
and `base_adapter_runtime_identity` as `Option` members. **`PROMPT_TASK_ROW` does not move** — the
row gains no field. The measurement's version is a checked function of the corpus: a task whose
`argv` names the repair adapter must emit version 2 and any other task must emit version 1.

**The design's characterization of the second failure mode was wrong, and the evidence corrected
it.** `c4-repair-editset.md` §1.2 originally read that `layer-precedence-frozen-module` "produced no
parsable `FILE:` block", so `validated_edit_set` never returned. Every `failure_kind: PATCH` row in
**both** gate runs — 6 of 6 in C4's, 8 of 8 in this one — carries
`diagnostic_summary: "the response reproduced the pinned files unchanged"`, which is
`synthesized_patch`'s refusal *after* the blocks parsed and every path was allowlisted. The mode is
a **no-op answer**, not a format failure, and the fallback capability is retargeted accordingly.
Two consequences are recorded: §1.2 carries the correction, and §11.3 deviation 14 records that
`edit_set` is `None` on exactly those rows because the adapter builds the blocks and then discards
them — conformant with §3.3's presence table, and the single most useful thing the next capability
can fix.

**Two rules the implementation had to add that the design did not anticipate**, both found by a
green-to-red owner test rather than by review:

1. **Which section kinds a sealed template must declare is selected by the corpus, not fixed.**
   Requiring the five-kind tuple unconditionally made `canonical-v1r`'s four-kind template
   undecodable, which would have left `eval/prompt/c4-repair-gate/` naming a corpus that can no
   longer be run. `make prompt-render-parity-smoke` caught it.
2. **`repair_editset_attempt_count` is present iff the corpus names the repair adapter**, not
   "present at version 2". `eval/prompt/c4-repair-gate/` is a merged version-2 document written
   before the quantity existed, and requiring it at version 2 rejected it outright. The new frozen
   version-2 chain regression in `make prompt-gate-validator-smoke` caught it. Both are recorded as
   deviations in spec section 11.3.

**Found by probe, and it is a real defect risk.** `runtime_identity()` in the frozen adapter is
`sha256(Path(__file__).read_bytes())`, and `src/prompt_score.align` requires it to equal the task
manifest's `measurement_adapter_runtime`. A repair adapter reusing the frozen `environment_probe()`
would persist the **frozen** file's digest while running its own code, and the existing check would
accept it. The repair adapter therefore defines its own identity and persists the base one
separately. The same probe found that no producer or runtime-identity check existed on an
*attempt-level* measurement's probe; ladder row 12 closes it in all three owners.

**Drop-ladder decision.** `STDOUT -> STDERR -> SUMMARY -> EDITSET`, `STATUS` never dropped.
`EDITSET` last, because dropping it first would silently degrade a row into the diagnostics-only
experiment that already measured zero recoveries; droppable at all, because it is the only section
that can blow the budget alone and a skipped attempt is a lost measurement.

**Freeze.** New `eval/prompt/canonical-v1e/` + `eval/tasks/prompt-v1e/`, **30** file-set members =
24 shared + 3 task manifests + the template + the policy + the repair adapter. The 24 shared members
carry identical digests in all three manifests, and all 86 member digests across the three corpora
recompute against the tree.

**Review repair (2026-08-29).** Two comprehensive reviews (implementation; spec/evidence/
governance) returned 7 major and 6 minor findings, all accepted and repaired in one commit. The one
behaviour change: the producer-side edit-set budget was a **greedy best fit** while §4.3, the
adapter's docstring, and `src/prompt_artifacts.align` all describe a **prefix cut**; the code moved
to break-on-first-overflow. That moves `scripts/prompt-repair-adapter.py`'s digest from `e54ab3c1…`
to `fa73f9dc…`, so `canonical-v1e` + `eval/tasks/prompt-v1e/` were **re-frozen — same member set**,
with only the adapter digest and the cascade below it moving, and the gate was **re-run from the
repaired head**. The provider service revision was re-derived and came back unmoved. Recorded as
spec §11.3 deviation 15. The other findings were falsifiability gaps and wording: five ladder-row
clauses had no falsifying case (edit-set path uniqueness/ascending in both the Align verifier and
the gate validator, three of the four version-1 absence clauses in the Align verifier, and the
validator's row-14 sum), the row-17 applied-edit cross-check refused a legitimately **truncated**
`diagnostic_summary`, and the divergence normalizer ended a function at the first column-0 line,
which a triple-quoted string can produce.

**Final delta review (2026-08-29).** A fresh review of the repaired head `6ccbb88` returned
**approve with minors**: four minors, all accepted and repaired in `21c6e30`. One changed behaviour:
the row-17 truncation exemption fired on the marker's **text alone**, so a short summary ending in
it could name any applied-edit list and escape the cross-check. Both owners now require the marker
**and** at least `SUMMARY_LIMIT` (4,096) bytes — the length a genuine `bounded_text` cut always has —
and each gained a rejection row for a forged cut beside an acceptance row whose summary is now built
the way the producer builds one. **It cannot move a recorded gate value**: across all 34 persisted
`diagnostic_summary` values in the evidence the longest is 94 bytes and none carries the marker, so
the exemption is unreachable by this corpus and the gate was not re-run. The other three were
wording: "only the clocks moved" (six repair-prompt digests move with the per-run sandbox path, no
correctness value does), §7.2's "two portable rows" for the prefix cut (one is portable; two are
Linux-gated), and a fixture comment claiming path uniqueness is checked before the block count (the
count is compared first). Recorded as spec §11.3 deviation 17.

**`origin/main` merged at `8890b27`** (a `git merge`, never a rebase). Conflicts resolved by keeping
both sides: the `.PHONY` union, roadmap item 31's merged result beside item 34, both handoff
sections, and one trailing-comma difference in `validate_attempt_record`'s call. `main`'s new
`validate_attempt_traces` / `snapshot_request_closure` / `count_ran_invocations` and this branch's
version-2 rows both survive, and the owner set was re-run at the merged head.

**Verification at the merged head `8890b27`.** `gmake build`, `gmake check` (31 units), `gmake fmt`,
`gmake format-check`, `gmake gate-topology-check` (EXPECTED unmoved), `git diff --check`, and the
nine macOS owners all PASS again. Under the Linux recipe below at the same head:
`run-prompt-evaluate-smoke`, `run-prompt-repair-adapter-smoke` (full launch rows),
`run-prompt-measurement-adapter-smoke` (74 rows), `test-prompt-fixed-adapter`,
`test-prompt-snapshot-helper`, and `test-prompt-source-verifier` all PASS. `EVALUATOR_SOURCE_SHA256`
is re-pinned in `21c6e30`, the same commit as that evaluator edit.

**Verification at the repaired head.** `gmake build`, `gmake check` (31 units), `gmake fmt`,
`gmake format-check`, `gmake gate-topology-check` (EXPECTED unmoved), `git diff --check`, and the
macOS owner set — `prompt-model-smoke`, `prompt-render-parity-smoke`, `prompt-score-smoke`,
`prompt-score-prefix-smoke`, `prompt-verifier-smoke`, `prompt-state-smoke`,
`prompt-gate-validator-smoke`, `prompt-measurement-adapter-smoke`, `prompt-repair-adapter-smoke` —
all PASS. Under the Linux recipe below: `run-prompt-repair-adapter-smoke` (full launch rows),
`run-prompt-evaluate-smoke`, `run-prompt-measurement-adapter-smoke`, `test-prompt-fixed-adapter`,
`test-prompt-snapshot-helper`, and `test-prompt-source-verifier` all PASS.
`scripts/freeze-canonical-v1e --check` and `scripts/freeze-canonical-v1r --check` each reproduce
their 10 frozen files. `EVALUATOR_SOURCE_SHA256` is re-pinned in the same commit as the evaluator
edit, inside the four-chunk window.

**Mutants, all killed**, across four owners. The original 23: skip EDITSET, drop EDITSET first,
remove the row-17 summary cross-check, drop the four members from `verifier_measurement_equal`,
remove ladder row 12, stop recomputing the EDITSET denominator, remove the version-versus-adapter
rule, stop summing `edit_set_total_bytes`, allow a version-2 member at version 1, allow the base
identity to be absent, trust the persisted denominator, disable the validator's row 11 / row 12 /
row 15 body-digest checks, and — in the adapter — drop `patch_sha256`, report the **frozen** file's
runtime identity, drop the edit set, digest before redaction, remove whole-block bounding, skip the
base-digest verification, and make the name assertion vacuous. **23 further mutants were injected
at the repaired head and all 23 died**: 11 in the Align verifier (four version-1 absence clauses,
the ascending rule and its strictness, the body digest, the declared length, the carried-body cap,
and both ends of the block bound), 9 in the gate validator (the same set less the strictness pair,
plus the row-14 sum and the row-17 truncation exemption), the adapter's greedy best fit, the
evaluator's truncation exemption, and the divergence normalizer's span. Every one of those 23
**survived** before the repair. The claim "23/23 killed" did not reproduce and is superseded; the
cause was one thing, not 23 — both fixtures built only well-formed edit-set blocks, so no rule
about a malformed one could fire (spec section 11.3 deviations 15 and 16).

**The provider service revision was re-derived, not inherited** (spec section 3.7):
`llama-server --version` reports build 10566 commit `bb4caa754`, the resolved binary hashes to
`b6ff7e91…`, and the 4,683,073,536-byte model file was re-hashed in full to `509287f7…`. The
observed string equals `canonical-v1r`'s, which is a measurement rather than a copy — the probe
fails closed had any component moved.

**Coding-baseline chain, re-recorded.** `Makefile` is one of the twenty recorded input artifacts and
this branch adds `c4-editset-gate` and `prompt-repair-adapter-smoke` to it, so `main`'s chain
(`69d223e` -> `ca17997` -> `c89d147`) no longer binds this head. The pending record was measured on
**Linux** (aarch64, kernel 6.11.11-linuxkit, Python 3.12.3) through the DinD wrapper at the merged
publication head, and the chain is **source `7828451` -> oracle `0badc51` -> finalization
`73de1e9`**. `gmake baseline-check` inside the same Linux image ends `baseline chain: PASS`.

**Next actions, in order.** (1) Publish the English pull request with the exact verification
commands, the measured result, the three review envelopes, and every finding's disposition, and post
the review record as a dedicated comment. (2) Merge with `--merge`; a squash or a rebase would make
the baseline chain commits unreachable from `main`. (3) If `origin/main` moves first, `git merge` it
— never a rebase — re-run the owner set, **re-record the baseline chain** (the `Makefile` edit makes
this head's chain its own) and re-stamp the fresh-image preflight, because the stamp belongs to an
exact unchanged `HEAD`. (4) On merge, C4's roadmap gate remains unmet by a model, and the fallback
capability named in spec section 6.4 — a prompt and edit-policy capability for the **unchanged-file
reproduction** mode, C4-REPAIR-TEMPLATE — becomes the next Track A item rather than a parallel one,
because this gate answered its tie-breaker in the negative. Its first sub-problem is this
capability's own recorded gap: **`edit_set` is `None` on every `PATCH` row** (spec section 11.3
deviation 14), so the answers that mode produces are exactly the ones no artifact shows.
`agent/c4-repair-template` is stacked on this branch's `6ccbb88` and must reconcile with the final
repair `21c6e30` and the merge `8890b27` — `scripts/prompt-evaluate.py`,
`scripts/prompt-gate-validator.py`, `scripts/prompt_gate_fixture.py`,
`scripts/run-prompt-evaluate-smoke`, `scripts/run-prompt-gate-validator-smoke`,
`src/prompt_evaluate.align` (the evaluator pin), `src/prompt_verifier_smoke.align`,
`docs/specs/c4-repair-editset.md`, `eval/prompt/c4-editset-gate/README.md`, `HANDOFF.md`,
`Makefile`, `docs/specs/roadmap.md`, and the three baseline-chain files.

**Blockers.** Host capacity only: a DinD preflight and Track B's model work contend for memory, and
the gate needs `llama-server` with the 4.7 GB model. No Align capability request blocks this; next
free number **53** stays free. Requests 22 and 52 both bite and both are mitigated by idioms already
proven at this pin, and both gained client evidence lines.

**Linux recipe** (unchanged from C4-REPAIR-MEASURED, and required before touching the evaluator or
its verifier — `make prompt-evaluate-smoke` cannot run on macOS):

```text
docker run --rm --platform linux/arm64 \
  --cap-add=SYS_ADMIN --security-opt seccomp=unconfined \
  --security-opt apparmor=unconfined --security-opt systempaths=unconfined \
  -v "$PWD:$PWD" -v /Users/hiro/Projects/align-llm/.git:/Users/hiro/Projects/align-llm/.git:ro \
  -v <scratchpad>/gate-run/linux-toolchain:/tc:ro -w "$PWD" \
  -e PYTHONDONTWRITEBYTECODE=1 -e ALIGNC=/tc/alignc \
  c4-repair-measure:latest sh -lc "python3 ./scripts/run-prompt-evaluate-smoke"
```

## Merged checkpoint: MF-SINGLE-TOKEN-LOGITS (PR #151, 2026-08-30)

Branch `agent/mf-single-token-logits`, cut from `origin/main` `553563e` (PR #147,
R6-RESIDENT-WEIGHTS) and brought up to `origin/main` by **three** `git merge`s, **never a rebase**:
`a9561a9` (PR #149, R6-PREFIX-SUFFIX-PREFILL), then `45ff38e` (PR #148, R6-OLMOE-DECODE), then
`4940005` (PR #150, C4-REPAIR-MEASURED). Every conflict was an `Active`-block or roadmap-entry
collision resolved by keeping both sides — `HANDOFF.md`, `docs/specs/roadmap.md`,
`docs/align-development.md`, and `scripts/decode-step-golden.jsonl` (taken from `main` and
regenerated). Sections 8.4, 8.5 and 8.6 of the plan record them one by one.
Roadmap item **36**: 31 and 32 have now landed (PRs #150 and #148), 34 and 35 are still reserved by
capabilities on branches or in draft, and this one merged out of order. A **bug fix**, filed by
`R6-PREFIX-SUFFIX-PREFILL` 11.2; `docs/specs/mf-single-token-logits.md` is the authoritative record
and carries the result in its **section 8**. No design gate (no CLI operand, exchanged or persisted
format, or ownership boundary moves), no Align gap, no new Align request.

**Defect.** `fill_members` and `compare_source` gathered a member's rows by token id only where
`m.pieces[at] > 1` — the piece count used as a proxy for "this member is the per-token embedding row
set". `build_embed_members` sets `pieces = tokens`, so a **one-token prefill** took the whole-member
branch and read row 0 of the embedding table instead of the prompt's row: wrong logits with
`status: ok` on four public arms — `--model-forward`, `--model-forward-gpu`, `--moe-model-forward`,
and `--decode-step`'s prefill. `--layer-forward` and `--moe-layer-forward` gather unconditionally
and were never affected. The resident path was **not** immune, correcting 11.2 of the filing
document: `stage_embed_row` staged the right row while `compare_source` still expected row 0, so a
one-token non-zero resident run with a reference reported `R5_SOURCE_DIVERGED` over a correct
result.

**Fix.** `gathered: bool` on both `GraphMembers` records, `true` from `build_embed_members` whatever
the count and `false` from every other builder across ten construction sites in four modules,
and the predicate `m.gathered && at == 0` at all four sites. `gathered` is true exactly where
`pieces > 1` was, so `T >= 2` is byte-identical.

**Evidence.** The gather fix alone adds six **new** golden rows and changes **none** — verified
mechanically at the implementation head, where all six corpora are pure appends. *(The lift below,
carried in the same branch, adds one more row and removes `ds-suffix-prefix-one`'s, so measured
against `origin/main` the branch adds seven golden rows, removes one, and changes none.)* `mf-tokens-one-zero` keeps the
`62a46efd…` digest the defect produced for
every one-token run and `mf-tokens-one` is now `867ebc4e…`, which `gf-tokens-one`, `ds-tokens-one`
and `ds-tokens-one-resident` also carry. Two mutants were run: reverting the four predicates to
`pieces > 1` kills exactly the six new rows and nothing else, and restores the
`R5_SOURCE_DIVERGED` false alarm on `ds-tokens-one-resident`; setting `gathered: false` at
`model_forward.build_embed_members` kills the three-token corpus as well.

**The lift, done in this branch.** Item 33's `T_prefix >= 2` bound existed only because of this
defect. Step 3c's term and its `R6_SUFFIX prefix[<n>]` detail are deleted; `ds-suffix-prefix-one` is
a passing oracle-S row at `T_prefix = 1` (`0cd795d9…`, byte-identical to the new
`ds-suffix-single-shot-2` comparand and to `--model-forward` at `3,5`), joined by
`ds-suffix-save-prefix-one` — a one-token prefill save whose `867ebc4e…` is the same digest
`mf-tokens-one` carries. `scripts/run-decode-step`'s split guard widens from `2 <= j` to `1 <= j`,
which adds no real-model run because no prompt that leg takes tokenizes to two ids or fewer — a
corpus property, and the comment there says so. `r6-prefix-suffix-prefill.md` gains **section 11.5** and its 2.3, 2.7,
3.7, 5.6, 5.7, 9.1, 11.1 corrections 8 and 10, 11.2 and 12.1 are corrected in place. The decode-step
corpus is 137 → **139** rows: three added and `ds-suffix-prefix-one` removed, because hosted CI
measured the **two-token decode step** as host-dependent (`.steps[0].bit_sum` 71850835819 on
macOS/arm64, 71850835587 on Linux/x86_64), so it and `ds-suffix-single-shot-2` are asserted from
`BOUNDARY_CASES` without golden rows exactly as item 33's four-token comparand is. The one-token
rows are identical on both hosts and stay pinned. Plan section 8.8.

**Real-model qualification, done.** Both legs pass at this head, streamed, exit 0.
`gmake model-forward-qualification` on dense Qwen: `llama-debug -p def` tokenizes to exactly one
non-zero id, **750**, and `--model-forward` at that id is **byte-identical** to
`llama-debug --save-logits` over all 152,064 logits — `d639adb97337394649a1a94ccc70767cf989b75c14b80e1de31cfdde4745fb96`,
argmax 914. `gmake moe-model-forward-qualification` on OLMoE: one non-zero id, **1545**,
byte-identical over 50,304 logits — `be4c699fbb888a3504b007c5d66925f621c8067a7f88191e0af42974c3c4ecc7`,
argmax 33007. The tokenization guard did not fire on either model. Every pre-existing six-token
assertion in both qualifications is unmoved. Recorded in section 8.7 of the plan.

**Review, done.** Two fresh independent comprehensive reviews of head `8dadcc2` — one on the
implementation, one on documents, goldens and governance. One blocking finding: this branch's plan
document ended with a blank line, so `git diff --check origin/main...HEAD` — the form
`scripts/pre-pr` runs — exited 2 while section 8.3 called it clean. The consolidated repair strips
it and applies every accepted minor: the golden claims are qualified wherever the branch's own lift
changes a row, the `3c ≺ L12` witness becomes `ds-suffix-over-cap` / `-over-cap-and-narrow`
(`ds-suffix-tokens-mismatch` is itself the L12 refusal), section 5.7's arithmetic becomes eleven
refusals and five successes, and the `2 <= j` → `1 <= j` widening now records its real invariant —
no prompt tokenizes to two ids or fewer. That repair was documents and comments only, so the
real-model legs above still bind.

**Hosted CI found one more, and it is a fixture property rather than a defect.** PR #151's first run
failed on `ds-suffix-single-shot-2` and `ds-suffix-prefix-one`: a two-token prefill's **decode step**
differs across hosts, both rows identically, so oracle S holds on each host and only the pinned file
cannot. Both move into `BOUNDARY_CASES` with every assertion intact — the same treatment item 33's
deviation 7 gave its four-token comparand — and the corpus is 139 rows, 143 documented cases. No
`.align` file, oracle, or refusal moves.

**Not started / next.** The rerun of
`python3 scripts/pre-pr --owner-test layer-forward-smoke -- gmake layer-forward-smoke` on the CI
repair head, then merge once the checks pass.

## Merged checkpoint: C4-REPAIR-MEASURED (PR #150, 2026-08-29)

Branch `agent/c4-repair-measured`, **merged as PR #150** (`4940005` on `main`). The branch is the
capability, three merges of `origin/main` (`553563e`, `a9561a9`, and `45ff38e`, all taken as
`git merge`, never a rebase, so every recorded commit stays reachable), the consolidated repair of
two disjoint comprehensive reviews' findings, the committed-head gate re-run record, the final
delta review's minors, and two baseline chains of which the later binds. Track A re-entry after the Track B R-wave; Track B's own sections below stay
active on their own branches.

**Capability.** One bounded model repair attempt in the provider-backed measurement path.
`docs/specs/c4-repair-measured.md` is the authoritative ledger; its section 10 carries the
ledger-to-diff mapping, **21** recorded deviations, the section 9.2 matrix-to-diff pass, and
the measured gate result. After a first-attempt validation `FAIL`, `scripts/prompt-evaluate.py`
renders a repair prompt from that attempt's **own** redacted validation status labels, diagnostic
summary, stdout, and stderr, calls `prompt generate` a second time against a fresh pinned checkout,
validates again, and records per-attempt identity and timing in `PROMPT_TASK_ROW` at
`schema_version: 2`.

**GATE RESULT: `NOT_MET` — a measured negative, delivered as one.** 12 rows, 3 tasks x 2 variants x
2 paired samples, temperature 0, `PAIRED_FIXED`, **22 provider generation calls** (exactly the
section 5.2 estimate of 12 + 10), **824.243 s = 13 min 44 s** against a 60-minute recorded ceiling.
`repair_recovery_count: 0` and `repair_recovery_paired_count: 0` — across ten repair attempts not
one row recovered. Evidence is checked in at `eval/prompt/c4-repair-gate/`; the per-row table,
aggregates, timings, and the analysis are in spec section 10.3.

**The checked-in evidence is a second run, from the clean committed head `f0314400`**, taken
because review asked for a record naming a reproducible commit: `align_llm_clean: true` and all
three reachability fields `VERIFIED`, against the first run's `UNVERIFIED`. Every correctness value
reproduced exactly — same rows, same per-attempt statuses and failure kinds, same
`patch_size_bytes` (716 / 758 / 0 / 1008), same ten repair attempts, same zero recoveries, same
aggregates, same 8,123-16,129 assembled bytes. Only the clocks moved. Digests:
`c4-repair-evaluation.json` `8793b1ff…`, evidence `a70a967e…`, record `18bdf25a…`.

The mechanism is proved even though the model is refuted: all ten repair prompts assembled from the
run's own persisted diagnostics, re-derived byte-exactly, and stayed far inside the prompt budget
(8,123-16,129 bytes against 65,536), so no section was ever dropped. Recomputed from the 22 attempt
records: `adapter_elapsed_ns` **7.98 s to 64.67 s**, mean 24.82 s, **median 18.59 s**, max/min
**8.1x**, sum 545.9 s; `adapter_overhead_ns` on the two passing attempts **91.04 ms and 91.77 ms**,
0.59 % and 1.00 % of those rows' own spans. The first run gave 8.13-73.82 s, median 18.27 s, 9.1x,
and 65.74 / 74.11 ms on the same corpus and seeds. **No speed claim is made**, and the two runs are
why.

`gate_eligible` stays `false`, and not for reachability: it is the **C6 acceptance** gate, which
requires `IMPROVED` with no serious-regression reason, and this run's status is
`SERIOUS_REGRESSION` from two `POLICY` reasons. The C4 verdict does not read it.

**What the `NOT_MET` supports, and what it does not.** Only `patch_size_bytes` is persisted — no
patch digest and no patch body — so "the model re-emitted its patch" is an inference, not a
verified fact, and section 10.3 states it that way. In the record-codec mode all four rows produced
1,008 bytes on both attempts with the same observable `TEST` failure; in the layer-precedence mode
attempt 1 already produced an **empty** patch, so that mode is a different failure and more
diagnostics are not obviously its missing input. Section 5.7's option B (a second corpus-member
adapter carrying the failing edits) addresses the first mode only. A persisted patch digest is now
a named deferral in section 5.4 and should land with it.

**The constraint that shaped it.** `scripts/prompt-measurement-adapter.py`,
`eval/runners/run-coding-task.py`, `scripts/prompt-fixed-adapter.py`,
`scripts/prompt-snapshot-helper.py`, and the three `eval/tasks/prompt-v1/*.json` manifests are
digest-verified members of `eval/prompt/canonical-v1/corpus-file-set.manifest`. Editing any of them
breaks the merged C6-MEASURED gate. So the loop is evaluator-owned, those files are byte-identical
(`git diff 3df063b..HEAD` over them is empty), and the corpus is a new freeze at
`eval/prompt/canonical-v1r/` + `eval/tasks/prompt-v1r/` with `maximum_repair_loops: 1`. The 24
file-set members the two corpora share carry identical digests in both manifests.

**Schema shape.** One `PromptTaskRow` with `Option` version-2 members — **there is no
`PromptTaskRowV2`**; spec sections 3.2 and 3.3 state the shipped shape and deviation 10 records how
the choice was reached. Presence never selects the version: the scorer reads `schema_version`
first, then requires every version-2 member present at 2 and absent at 1. Each attempt also carries
the four trace digests of its own contained invocation (`snapshot_request_sha256`,
`before_snapshot_result_sha256`, `after_snapshot_result_sha256`, `input_snapshot_sha256`), present
exactly when it ran; the `input_snapshots` bound is per invocation, which is the same bound at
version 1.

**Repair of the two reviews, and what it changed.** Reviewer A (evaluator/Align/runner) and
reviewer B (spec/evidence) each returned `request changes`; every finding has a disposition in the
pull request. Four changes matter beyond the documents:

1. **The verifier now resolves attempt trace digests instead of only checking their shape.**
   `verifier_attempt_trace_cross_valid` (`src/prompt_score.align`) resolves each of the four to
   **exactly one** persisted record of that row's task and applies the attestation path's closure,
   before/after-equality, and artifact-equality checks to the resolved records. This is a
   contract tightening, not a fix to a broken run: the checked-in evidence was validated against
   the new rule before it shipped and all 22 attempts resolve.
2. **`scripts/prompt-gate-validator.py` and its fixture were vacuous on the four digests** — the
   validator's `ATTEMPT_RECORD_FIELDS` omitted them, so it would have rejected every real
   version-2 attempt, and the fixture never emitted them, so no smoke case noticed. Both fixed;
   deleting the four names from the tuple now turns `prompt-gate-validator-smoke` red.
3. **`make prompt-evaluate-smoke` was red and is now green.** Running it exposed three defects the
   two reviews missed; spec deviation 21 records them. One of them — the terminal-adapter-error
   path abandoning its own row — is a published-artifact defect, not a test-only one.
4. **Section 10.3's statistics were wrong and are recomputed from the artifact.** The old text
   reported 11.40-81.19 s, "median 27.47 s", 113.7/115.2 ms overhead, and "about 10 minutes"; the
   correct figures are above. The section 5.7 inference was also over-scoped and is now bounded by
   what the evidence contains.

**The final delta review's one substantive minor, and what closed it.** The gate re-run head was
approved with minors; the load-bearing one was that item 2 above stopped at *pool membership*.
`scripts/prompt-gate-validator.py` now carries `validate_attempt_traces`,
`snapshot_request_closure`, and `count_ran_invocations`: the same exactly-one per-task resolution,
before/after equality, request closure (including a `FILE` expectation's canonical
mode/path/digest preimage and a `TREE` expectation's descendants), artifact-digest equality, and
section 3.8 row 23 invocation bound the Align verifier applies. The port was validated against the
published `c4-repair-evaluation.json` before it shipped — all 22 attempts resolve under the Python
implementation too — and six rejections were added at
`scripts/run-prompt-gate-validator-smoke:1105`, with six single-point mutants of the new code all
dying. Closing it forced a fixture correction: `scripts/prompt_gate_fixture.py` had every attempt
and attestation naming one placeholder request/result/input triple that was not closed over
itself, so the fixture now models a real observation. Spec deviation 19 and section 10.3 record it.

**Verification at the repair head.** `gmake build`, `gmake check` (31 units),
`gmake fmt`, `gmake format-check`, `gmake gate-topology-check`, `git diff --check`, and the seven
owner smokes — `prompt-model-smoke`, `prompt-render-parity-smoke`, `prompt-score-smoke`,
`prompt-score-prefix-smoke`, `prompt-verifier-smoke`, `prompt-state-smoke`,
`prompt-gate-validator-smoke` — all PASS, plus `make prompt-evaluate-smoke` under the Linux recipe
above. `scripts/freeze-canonical-v1r --check` reproduces all 10 frozen files; all 56 file-set member
digests across both corpora recompute. `EVALUATOR_SOURCE_SHA256` is re-pinned to
`53bcf1c3a6fd384918dbfce380d0b7f35faa66c8dce5aad239649bfec90cfee4` (217,056 bytes), inside the
four-chunk window.

Seven mutants were injected into `src/prompt_score.align` at the final head and run under
`gmake prompt-verifier-smoke`: the attempt-length bound, the repair-count bound, **both together**,
`verifier_row_references_trace` returning `true`, the attempt-trace resolution, and re-imposing
`measurement.repair_loop_count == 0` unconditionally all die against the new defect cases 9-13. The
seventh — weakening `declared_loops > maximum_repair_loops` in `verifier_row_repair_facts` —
survives and always will, because the walk's own bounds make that comparison unreachable; it is
commented as redundant defence in depth and deviation 13 records it rather than claiming coverage.

**`make prompt-evaluate-smoke` runs only in a Linux container, and running it found three real
defects.** It cannot run on macOS: the evaluator's retained-executable launch reads `/proc/self/fd`
and the validation runner needs `bwrap`. The recipe that works — and that the next session must use
before touching this evaluator or its verifier — is:

```text
docker run --rm --platform linux/arm64 \
  --cap-add=SYS_ADMIN --security-opt seccomp=unconfined \
  --security-opt apparmor=unconfined --security-opt systempaths=unconfined \
  -v "$PWD:$PWD" -v /Users/hiro/Projects/align-llm/.git:/Users/hiro/Projects/align-llm/.git:ro \
  -v <scratchpad>/gate-run/linux-toolchain:/tc:ro -w "$PWD" \
  -e PYTHONDONTWRITEBYTECODE=1 -e ALIGNC=/tc/alignc \
  c4-repair-measure:latest sh -lc "python3 ./scripts/run-prompt-evaluate-smoke"
```

The checkout must be mounted **at its own absolute path**: a linked worktree's `gitdir` file names
that path, so mounting it at `/work/align-llm` makes every `git rev-parse` fail. `ALIGNC` avoids a
40-minute in-container `cargo build` of the pinned compiler. Under this recipe the merge base
`3df063b` **passes** and the capability head did **not**. Spec deviation 21 records the three
defects: the Align verifier applied deviation 1's `repair_loop_count` rule unconditionally and so
refused every version-2 document the deterministic adapter produced from an expected-failure row;
the terminal-adapter-error path aborted before its own row and attestation were persisted, leaving
trace records referenced by nothing and refusing publication; and the owner itself read an omitted
`Option` with `[]` and raised `KeyError` where it meant to assert. All three are fixed and the
owner passes. **Neither review found any of them, because neither ran the owner.**

**`make prompt-gate-check` is still not runnable here**, needing a source bundle and the Linux
process-containment floor; spec section 10.3 records the `N/A` with the three substitute checks
that cover each of its claims. The evaluate smoke's descendant-cleanup boundary now reports SKIP
off Linux, like the gate validator smoke, instead of failing.

**Provider topology.** Validation stays in `bwrap` inside a Linux aarch64 Docker container (Docker
28.5.1), image `c4-repair-measure:latest` — the C6 measurement image plus `bubblewrap` and `socat`,
with `/usr/bin/python3` and `/usr/bin/git` keeping the digests the C6 gate locator pins. Generation
reaches the host `llama-server` through a container-local `socat` forwarder on `127.0.0.1:18080`,
so `evaluation-provider-control.json` stays byte-identical and no machine-specific hostname reaches
a persisted artifact. The server is **not** C6's (Homebrew llama.cpp 0.2.0, build 10566, commit
`bb4caa754`); the **model file did not move** (`509287f78cb4d4cf6b3843734733b914b2c158e43e22a7f4bf5e963800894d3c`,
exactly C6's `model-sha256`). `canonical-v1r/generation-policy.json` records the observed revision,
and a fail-closed host probe plus an in-band model-id check enforce it. The container needs four
explicit privilege values for `bwrap`'s namespaces; they are published in every run record's
`container_privileges` and recorded as deviation 17.

**Align capability request.** **Request 52** (`PROPOSED`) — `match` on an **owned** record's
`Option` field partially moves the payload out with no diagnostic, and a later `json.encode` of
that still-live record silently omits the field. Non-blocking: every `Option` member this
capability adds is read through a `borrow` binding. Requests 50 and 51 are Track B's; 53 is the
next free number.

**Host coordination.** A gate re-run needs the host `llama-server` and the 4.7 GB model. Track B
runs real-model CPU work in sibling worktrees; check `pgrep -f 'ggml-spike|run-decode-step|run-moe-decode-step'`
and free memory before starting `llama-server`, and never kill another agent's process.

**Coding-baseline chain, re-recorded.** This capability changes `Makefile`, one of the twenty
recorded baseline artifacts, so the chain on `main` does not bind this head. Exactly one of the
twenty digests moved (`Makefile`); `.align-revision` is unchanged and the twenty paths are
identical. The eval artifacts this capability adds — `eval/prompt/c4-repair-gate/` and
`eval/prompt/canonical-v1r/` — are **not** in the recorded set, which
`python3 scripts/check-baseline-chain` confirms against the manifest. The identity-bound chain is
`69d223e` -> `ca17997` -> `c89d147` (clean source, immutable oracle projection, finalization), with
the pending measurement recorded on Linux (aarch64, kernel 6.11.11-linuxkit, Python 3.12.3) through
the DinD wrapper, exactly as the R-wave's were. `gmake baseline-check` passes on Linux at the
finalized head. It **supersedes** this branch's first chain (`4652753` -> `5b88b6b` -> `9f9d458`),
which PR #148 (R6-OLMOE-DECODE) invalidated by changing `Makefile` itself; both chains stay
reachable in this branch's history and only the later one is named in the finalized baseline. The pull request must be a **merge**: squash or rebase would make the three commits
unreachable from `main`.

**Next actions, in order.**
1. At the final head, on a clean worktree:
   `python3 scripts/pre-pr --owner-test prompt-verifier-smoke -- gmake prompt-model-smoke
   prompt-render-parity-smoke prompt-score-smoke prompt-score-prefix-smoke prompt-verifier-smoke
   prompt-state-smoke prompt-gate-validator-smoke`. The branch changes `Makefile`, so the
   classifier selects the **`fresh-image`** profile — `hosted-checks`, `fresh-focused`, **and the
   installed `fresh-installed`** — and the installed profile is not substitutable by a Docker skip
   or an ambient `DOCKER_HOST`. On this macOS host that means running the whole preflight inside
   the Docker-in-Docker wrapper, with `gmake` on `PATH` and `LIBRARY_PATH` set as the
   `align-llm macOS host setup` notes require. `Makefile` is also one of the twenty recorded
   canonical baseline artifacts, so the three-commit baseline chain must be re-recorded on Linux
   through the same wrapper before the stamp; `python3 scripts/check-baseline-chain` names the
   tracked set, and the `eval/prompt/c4-repair-gate/` and `canonical-v1r` artifacts this
   capability adds are **not** in it.
2. Publish the pull request with the two review envelopes, every finding's disposition, and the
   consolidated repair commit.

**Blockers.** None.

**Intentional uncommitted files.** None.

## Merged checkpoint: R6-OLMOE-DECODE (PR #148, 2026-08-29)

Branch `agent/r6-olmoe-decode`, implemented on `agent/r6-resident-weights` head `6facd56` and then
**merged** with `origin/main` `553563e` (R6-RESIDENT-WEIGHTS, PR #147, carrying `cec1758`) by
`git merge` — **never a rebase** — a clean fast-forward touching five files, none of them this
capability's. The four things that merge re-checks all held: roadmap item **32** (30 is
RESIDENT-WEIGHTS, 31 is claimed by `agent/c4-repair-measured` on its own branch), the new document
kind `R6_MOE_DECODE_STEP` at schema **1** (which collides with nothing, because it is a new kind),
the next free Align request number (**53**; 52 is taken by the C4 branch, and this capability takes
none), and which goldens regenerate.

**Merged a second time, with `origin/main` `a9561a9`** — R6-PREFIX-SUFFIX-PREFILL, PR #149, which
landed during this capability's publication — again by `git merge` and never a rebase, so the
recorded baseline-chain commits stay reachable. Three files conflicted and all three keep **both**
sides: `scripts/build-ggml-shim` (three routed forced-build arms beside that capability's two
suffix ones), `docs/specs/roadmap.md` (item 32 beside item 33, with the reservation comment narrowed
to item 31, which is still on the C4 branch), and `HANDOFF.md`. The four re-checks hold again:
roadmap item **32**, document kind `R6_MOE_DECODE_STEP` at schema **1**, the next free request number
(the register on `main` still ends at **51**, PR #149 filed none, and this capability files none),
and the goldens — `scripts/decode-step-golden.jsonl` is that capability's at **137** rows and this
branch does not touch it, `scripts/moe-decode-step-golden.jsonl` is this one's at **59**.

**Capability.** `N` greedy decode steps on OLMoE-1B-7B-0125-Instruct Q4_K_M over an Align-owned KV
plane, each step resolving its own top-8 expert claims per layer and computing only those experts,
weights **streamed**. CPU only. Authoritative ledger `docs/specs/r6-olmoe-decode.md`; sections 1 to 5
are the pre-implementation design and 6 onward record what was built and every deviation. Three of
the four design-gate triggers fire, including — for the first time in this wave — the
coordinated-invariant one.

**Complete.** Cell **G-P1** (50,304 rows of Q4_K, 50,057 distinct fingerprints, two collision
classes covering 249 ids of which **two** are not all-zero: `{45382, 50278}`); `src/layer_olmoe.align`
with `OP_CONCAT`, `WHEN_DECODE`, `mm_row_issued_at`, a **thirty-seven-row** `mm_decode_a_node_table`,
`mm_decode_b_node_table` at its own base 58, `MM_SLOT_KPAST`/`VPAST` at the top of the slot map,
`MM_K_ROW`/`MM_V_ROW`/`MM_DECODE_K_CONCAT_ROW`/`MM_DECODE_V_CONCAT_ROW` derived by reading the
tables, `mm_write_mask_offset`, `mm_oracle_table_at`, `MAX_DECODE_STEPS := 64`, and
`MAX_PREFILL_TOKENS 6 -> 32`; `src/moe_decode_step.align` (~4,400 lines) with the arm, the plane, the
loop, the two-way claim accounting, and the `R6_MOE_DECODE_STEP` schema-1 document;
`src/moe_model_forward.align` widened to `pub` where the new module imports it, plus
`stage_carry_at`, `stage_plan_owned`, and the decode arm's `Outcome` fields; `scan_transcript_after`
on the routed side; one `import` and one `if` in `src/ggml_spike.align`; the fixture's routed decode
corpus; the **seventh** block of `scripts/run-layer-forward-smoke` and
`scripts/moe-decode-step-golden.jsonl`; `scripts/run-moe-decode-step` and one `Makefile` target.

**The `R5_ORACLE_TRUNCATED` guard is new, and its absence was a real gap.** The design predicted that
`--moe-layer-forward` and `--moe-model-forward` already shipped it, as the dense arms do. They did
not: at a cap of six tokens the condition was unreachable. The lift to 32 makes it reachable, so both
arms now refuse a prefill above six tokens **with** a transcript, and `moe-tokens-33` /
`mm-tokens-33` plus `*-tokens-seven-with-transcript` pin both halves.

**Golden movement, measured against the merged head.** Five goldens byte-unchanged
(`layer-forward`, `model-forward`, `gpu-forward`, `decode-step`, `ggml-spike`); one new
(`moe-decode-step-golden.jsonl`, **59** cases after the review repair); and `moe-layer-forward-golden.jsonl` and
`moe-model-forward-golden.jsonl` each **-1 renamed, +3 added, and zero pre-existing rows changed in
value** — `moe-tokens-seven` becomes `moe-tokens-33` and gains
`moe-tokens-seven-with-transcript` and `moe-tokens-seven-no-transcript`, and the same three on the
`mm-` side. The routed pack itself is byte-identical, because
`MOE_MODEL_DECODE_RESEEDED_ROWS` is empty: the routed decode chain is already non-degenerate.

**Result** (the qualification of record, `gmake moe-decode-step-qualification`, four prompts x
`N = 16` x three runs, Apple M1, `KV_WIDTH` 256, weights streamed, CPU only, **re-run at the review
repair head**, exit 0; **1 min 23.4 s** warm and **5 min 41.3 s** with the page cache evicted by a
concurrent build, against 3 min 18 s cold at the implementation head — the spread is the 4.2 GB
pack's residency and every correctness value is identical across the runs). Gate G
over 64 ids, oracle R **`MATCH` at 8,192 of 8,192** — the first full-axis routing identity in the
repository — oracle B `IDENTICAL`, oracle T `PASS` with `max_abs_diff` **0**, and the claim
accounting exact on all 64 steps. **Every correctness value reproduced exactly**; the residency
columns below are the repaired metric:

| prompt | oracle R | step bytes (arith) | step bytes (`pread`) | ampl | union keys | mean marginal | demands in prefill | distinct in prefill | reuse ppm |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `def add(a, b` | 2048/2048 | 487,587,840 | 487,587,840 | **0 ppm** | 585 | 57.9 MB | 1540/2048 (75.2 %) | 273/515 (53.0 %) | **748** |
| `The capital of` | 2048/2048 | 487,587,840 | 487,587,840 | **0 ppm** | 698 | 92.3 MB | 1064/2048 (52.0 %) | 240/627 (38.3 %) | **693** |
| `import os` | 2048/2048 | 487,587,840 | 487,587,840 | **0 ppm** | 614 | 95.4 MB | 1154/2048 (56.3 %) | 173/573 (30.2 %) | **720** |
| `return x +` | 2048/2048 | 487,587,840 | 487,587,840 | **0 ppm** | 607 | 83.1 MB | 1182/2048 (57.7 %) | 212/561 (37.8 %) | **726** |

**The two accountings agree to the byte and the read amplification is zero**, which is the strongest
form the primary claim could take: the arm read exactly what it claimed and not one byte more.
**The streamed-to-marginal gap is 5.1x to 8.4x at sixteen steps, not the 9.2x a four-step probe
suggested.**

**`step_reuse_per_mille` was the wrong quantity and is re-recorded.** The first implementation
published `(demands - |decode keys the prefill did not hold|) / demands` — prefill-relative reuse —
under section 3.11's name, which defines `distinct` as the decode steps' **own** key set. The
figures were 881/811/804/829; they are **748/693/720/726**. The fixture reproduced the
implementation's arithmetic verbatim, so the generator, the golden and the smoke assertion all
agreed with the wrong number: the oracle was co-derived with the subject, and it is now derived
independently from the routings alone. The hosted figure moved 833 -> 333. Section 12.3's "roughly
twice the adjacent-pair one" is **re-derived**: 1.55x to 1.67x R2D's pooled 447, about as much as an
adjacent-pair window captures at its *best* transition, not twice it.

**"Four fifths of every decode demand is already in the prefill" now has both of its fractions.**
Demand-weighted it is 52.0 % to 75.2 %; over **distinct** decode keys — the form section 2.4 reading
2 actually predicted at 79.9 % — it is **30.2 % to 53.0 %**, and that is the reading that collapses.

**Cell C-P1** selected oracle C′'s second branch and the fallback is now **implemented**, not
asserted on argmax alone: at all twelve checkpoints the runner reports the verdict with argmax
equality, top-ten **set** equality, and `max_abs_diff` in ten-thousandths over the union of the two
top-tens. Measured: 1 `IDENTICAL`, 6 `WITHIN`, 5 `FAIL`; argmax 12/12; the pre-committed 5000 bound
holds 12/12 (range 0 to 3,678); top-ten **set** equality holds only **7 of 12**. Section 4.4's
non-identical branch had already moved the acceptance weight to G, R and B, so the shipped rule
reports the verdict and gates on argmax alone — a first draft gated on the whole triple and refused
the run, and that refusal is the measurement.

**Verification, at the repair head.** `gmake build`, `gmake check`, `gmake layer-forward-smoke` (all
seven blocks, 80 s, 59 documented cases in the seventh, every golden as predicted),
`gmake ggml-spike-smoke`, `gmake gate-topology-check`, `gmake fmt` (no change), `gmake format-check`,
`git diff --check`, and the real-model qualification above. **Nine mutants re-injected by file-level
backup** (never by copying this linked worktree — its `.git` pointer writes through to the shared
worktree administration directory): eight die, including the three new ones — axis 0 mapped
unconditionally dies as `md-used-eight: routing MISMATCH`, axis 1 never mapped dies as
`md-used-eight: oracle T FAIL worst ffn_moe_up max_abs 8726`, and `step_reuse_per_mille` restored to
the prefill-relative quantity dies as `833, not the generator's 333`. The ninth, `MM_V_ROW` 13 -> 12,
is **inert and not a gap**: row 12 is the `MUL_MAT` and row 13 a `RESHAPE_3D` view over the same
buffer, so the plane receives the same bytes.

**The qualification needs one ggml build on both sides, and that is a toolchain debt this capability
records rather than pays** (section 15 of the ledger). `scripts/llama-eval-callback-toolchain` builds
the R2C instrument with `GGML_ACCELERATE=ON`/`GGML_BLAS=ON`; Homebrew's ggml at the **same commit**
has neither, and the same prompt gives `result_output` sums of -113,284.84 and -111,030.03. Every
earlier consumer of that instrument parsed text; this is the first to compare it numerically. The
runner's instrument cross-check caught it before the arm ran and reported it as an instrument skew,
which is what that check exists for.

**Constraints.** CPU only; streamed weights, **by design and not by cost** — residency would make the
primary metric zero. No TTFT, throughput, or performance claim, and no cost ceiling: this capability
makes a measurement claim and `docs/specs/r6-resident-weights.md` section 3.4 remains the owner of
Track B decode performance.

**Blockers.** None. Five Align gaps are met and all five are already recorded with named clients
(Requests 33, 36, 47, 48, 49); none blocks, and Request 49 gains its largest client — whose recorded
duplication count is corrected from 23 to **36**, regenerated from the source, with the predicted
duplicated `refill` removed because it does not exist.

**Final review minors applied.** One final delta review of the repair head `bf7c87d` returned
**approve with minors** — three stale "57" case counts in section 14 that the deviation-16 repair
took to 59, one deviation cross-reference (16 -> 18), a clause recording that the union-versus-
adjacent-pair ratio's *direction* is structural and only its magnitude informative, and one
108-column roadmap line. All four are applied in `a5c216a`, are **Markdown only**, and touch no
source, script, fixture, golden or `Makefile`, so the qualification recorded at `bf7c87d` stands.
Re-verified at `a5c216a`: `gmake build` ok, `gmake format-check` PASS, `gmake layer-forward-smoke`
PASS (seven blocks, 1 min 28 s, 13 no-document and 59 documented cases in the seventh),
`git diff --check` clean.

**Coding-baseline chain, re-recorded.** `Makefile` is in this publication diff, so `main`'s chain no
longer binds this head. The pending record was measured on **Linux** (aarch64, kernel
6.11.11-linuxkit, Python 3.12.3) through the DinD wrapper at the publication head, and the chain is
**source `a5c216a` -> oracle `4cab8a7` -> finalization `245f7f5`**. `gmake baseline-check` inside the
same Linux image ends `baseline chain: PASS`.

**Publication found one more thing, and it is deviation 19.** The `Installed Ubuntu 24.04
fresh-image profile (aarch64)` check failed **twice** at PR #148 with the canonical, detail-free
`fresh compiler: ERROR CHILD aggregate`, at `worker-aggregate` phase durations of **1,992 s** and
**2,000 s**, where `main` measured 1,867 s (PR #143) and 1,892 s (PR #144) and passed, `x86_64`
measured 1,778 s and passed, and this host's own installed-profile run passed at 1,875 s. The
aggregate child is `make capable-checks`, of which `layer-forward-smoke` — and therefore this
capability's seventh block — is a member, and it runs under one `AGGREGATE_TIMEOUT`. That constant is
**1,800 s -> 3,600 s** in `scripts/fresh-align-compiler`, with the measurement in its own comment.
`enforce_aggregate_quota` is unchanged, so what the child may *consume* is bounded exactly as before.

**Two environment findings worth carrying forward.** (1) The local DinD preflight must run
`scripts/pre-pr` as an **unprivileged uid**: R6-KV-PERSIST's `ds-kv-save-unwritable` builds a `0555`
directory and asserts `R6_KV_UNWRITABLE`, and root writes into it anyway, failing 26 assertions of
that block. GitHub's runners are unprivileged, which is why hosted CI never saw it.
`scratchpad/dind-prepr-r6m-user.sh` starts `dockerd` as root and drops to uid 501 for the preflight
itself. (2) The fresh worker's aggregate had been sitting at roughly 98 % of its wall-clock cap on
the slowest supported architecture; one added smoke block crossed it.

**Next actions, in order.**
1. `python3 scripts/pre-pr --owner-test layer-forward-smoke -- gmake layer-forward-smoke` on the
   unchanged head. The diff touches `Makefile`, `scripts/build-ggml-shim`, the fixture, the smoke and
   the goldens, so the classifier selects the **executable** row and the **installed fresh-image
   profile** (`--plan` reports scope `fresh-image`); do not substitute a Docker skip or an ambient
   `DOCKER_HOST`.
2. Open the English pull request with the verification table, the review envelope, the finding
   dispositions and the consolidated repair commit. It must be a **merge** commit: squash or rebase
   would make the baseline commits unreachable from `main`.
3. `gmake ci` is **not** selected: this repair changes no aggregate membership, no check topology and
   no integration behaviour, and `scripts/check-gate-topology`'s byte-literal EXPECTED does not move
   (`moe-decode-step-qualification` stays in `.PHONY` and in no aggregate).
4. After merge, refresh `main` and start the next eligible roadmap capability.

**Reproducing the qualification on this host, exactly.** All three of the arm, `llama-eval-callback`
and `llama-debug` must be **one ggml build** (deviation 4). The `r2c-v2` cache holds only a
statically linked `llama-eval-callback`, so configure the pinned source once with
`BUILD_SHARED_LIBS=ON` and the toolchain's other flags verbatim
(`CMAKE_BUILD_TYPE=Release`, `GGML_NATIVE=OFF`, `GGML_METAL=OFF`, `GGML_OPENMP=OFF`,
`GGML_CCACHE=OFF`, `LLAMA_CURL=OFF`, `LLAMA_BUILD_EXAMPLES=ON`, `LLAMA_BUILD_TESTS=OFF`,
`LLAMA_BUILD_NUMBER=10566`, `LLAMA_BUILD_COMMIT=bb4caa754`) and build the `llama-eval-callback` and
`llama-debug` targets. Then `ALIGN_LLM_GGML_INCLUDE=<source>/ggml/include`,
`ALIGN_LLM_GGML_LIB=<build>/bin`, and both instruments from `<build>/bin`. The runner's new preflight
checks that pairing by resolved object identity and refuses a mismatch. **Two repairs were needed to
make this a one-command run**: `ALIGN_LLM_GGML_LIB` now joins the loader path, and the real shim
records it as an `-Wl,-rpath` — macOS strips `DYLD_*` from `/usr/bin/time`, which is how the arm is
launched, so the environment variable alone aborts it inside `dyld`.

**Intentional uncommitted files.** None.

## Merged checkpoint: R6-PREFIX-SUFFIX-PREFILL (PR #149, 2026-08-29)

Merged as `a9561a9` on `main` while R6-OLMOE-DECODE was in publication, and taken into
that branch by `git merge origin/main` — never a rebase. The next actions this section
recorded are discharged by that merge; the record below is kept as the capability's own.

Branch `agent/r6-prefix-suffix-prefill`, cut from `origin/main` `553563e` — the merge of
R6-RESIDENT-WEIGHTS (PR #147). **The capability is committed** (`6cef75b`), with its review repair
and the final delta review's minors on top; the tree is clean and every hosted check passes at the
head. `origin/main` has not moved since the branch was cut, so **no merge is owed**: the merge base
is still `553563e` and the branch is three commits ahead of it.
`docs/specs/r6-prefix-suffix-prefill.md` is the authoritative ledger: sections 1 to 4 are the design,
5.1 to 5.4 the verification plan, **5.5 to 5.10 the hosted, mutation, real-model and TTFT results**,
**11 what implementation and the review found**, and 12 the ledger-to-diff mapping.

**Reviewed and repaired.** One comprehensive review of `6cef75b` over two disjoint reviewers — A on
`src` plus the runner, smoke and shim, B on the document and the reconciliation edits — returned
8 major and 16 minor findings, no blocker; 24 dispositions, all applied, two of them as evidence
rather than a code change (the `R6_TOKENS` precedence row does establish `3 ≺ 3c`, recorded in 5.6;
and section 11.2's recorded digest does reproduce once the command is runnable). A **final delta
review** of the repair — required because the repair added a contract, `T_prefix >= 2` — approved
with three minors, applied on top: the 11.2 reproduction needed `LIBRARY_PATH` exported before the
build line (it now runs end to end and reproduces `62a46efd73d18be1...` and the control
`99781f3e63a67b18...`), acceptance rule 7 points at the shipped matrix in 5.6 rather than 5.2's
superseded prediction, and the smoke's refusal-detail assertions are one named
`SUFFIX_REFUSAL_DETAILS` tuple of all **thirteen** documented details that the summary line counts,
instead of a literal loop counted from `STUB_CASES` membership. The one that changes behaviour is a
**contract addition**: `SUFFIX` now requires `T_prefix >= 2` and refuses `R6_SUFFIX`/`prefix[<n>]`
otherwise, because a one-token prefill computes the wrong embedding row (see the defect below) and
the equality oracle would have failed silently. The rest are the split guard (`2 <= j`), the witness
guard checking fields rather than blocks, the stub's suffix latch being cleared after the pass, and
document currency.

**Capability.** `R6-KV-PERSIST` made a prefill plane outlive its process, but only for the prompt it
was saved for — the arm had no graph that computes more than one column at `n_past > 0`. This ships
that graph. `--decode-step` gains a fifteenth operand, `SUFFIX` (a token id list or `-`), legal only
with `KV_LOAD`: the arm loads a container holding `T_prefix` columns for exactly the tokens in
`TOKENS`, runs **one suffix pass** over the `S` suffix tokens at absolute positions
`T_prefix .. T_prefix+S-1` causally masked over prefix-plus-suffix, writes their K and V into the
plane at columns `T_prefix ..`, verifies the plane over all `T_prefix + S` columns, and then
continues the existing `N`-step loop from `n_past = T_prefix + S`. **Nothing is re-saved and the
`akvp` format is byte-unchanged.** Dense Qwen2.5-Coder-7B Q4_K_M, CPU only. The oracle is that a
suffix run and a single-shot prefill of `TOKENS ++ SUFFIX` are **the same run**.

**Complete.** `SUFFIX` at `args[14]` with arity 15 and step 2c's conditional rule; `R6_SUFFIX` with
four details (`suffix[<text>]`, `prefix[<n>]`, `sequence[<n>]`, `token[<index>]`); step 3c and the
widened step 6; `mf_decode_layer_node_table(g, n_past, tokens, width)`
with **six** literals parameterised across three functions; `decode_layer_inputs`/`_values`,
`capture_plane`, and `verify_plane` at `tokens`; `decode_pass` at `tokens_in` with its own
`suffix_pass` counter; eleven `Outcome` fields and the `suffix` object at document **schema 5**;
`output`/`oracle_logits` moved to the pass's own logits on a completed run with the container's
vector kept in `kv`; 22 new cases and **21** new golden rows (three oracle-S splits, twelve refusals
including the repair's `ds-suffix-prefix-one`, three comparands, two forced builds, and a resident
leg, minus the four-token comparand kept out of the cross-platform golden), two stub
shim arms and two builder flavours;
`scripts/run-decode-step`'s per-split suffix leg with oracle S, oracle C″, oracle B, gate G, the
accounting, and the three-leg TTFT diagnostic; roadmap item **33**, `docs/align-development.md`,
Request 49's negative client line and Request 22's cheaper-absence line, and
`docs/specs/r6-kv-persist.md`'s `document_schema_version` correction.

**`src/kv_plane.align`, `scripts/kv_plane_reader.py`, `src/ggml_ffi.align`, `scripts/ggml_shim.c`,
`src/ggml_spike.align`, the `Makefile`, and `scripts/layer_forward_fixture.py` are byte-unchanged.**
No new ggml op, shim symbol, node row, slot, or Align surface, and no aggregate membership or check
topology change, so `scripts/check-gate-topology`'s byte-literal EXPECTED does not move.
`scripts/ggml_shim_stub.c` and `scripts/build-ggml-shim` are not unchanged: two arms in the test
double, recorded as section 11.3 deviation 3.

**Risk 1 was discharged first, as the design asked.** `ds-suffix-3` was run before any refusal case
was written, and oracle C″ was byte-identical on the **first** implementation checkpoint: the
column-count sensitivity R6 measured in llama.cpp does not appear between this arm's own two paths
at `S >= 2` **and** `n_past > 0`. It never reappeared on any later run, hosted or real-model.

**Goldens.** `scripts/decode-step-golden.jsonl` 116 → **137**. A programmatic diff confirms the only
fields that changed in a pre-existing row are `.schema_version` (4 → 5) and the added `.suffix` — the
prediction exactly. **Every other golden in `scripts/` is byte-unchanged**, all six.
**Hosted CI refused one added row and it is out**, recorded as section 11.3 deviation 7:
`ds-suffix-single-shot-4`, a four-token single-shot prefill, has `.schedule[1].l_out_bit_sum`
12,689,786,356 on macOS/arm64 against 12,689,786,355 on Linux/x86_64. It moves into
`BOUNDARY_CASES` on `ds-resident-stage-full`'s precedent — still run, still recorded, still compared
by oracle S **within one host** — and only the committed row goes. Risk 4's five-column mitigation is
wrong as stated: a 1-ULP disagreement is available at any width and this fixture reaches it at four
tokens, which the next capability adding a multi-token prefill case needs to know.

**Findings, in section 11.** Oracle S's exclusion list needed four more fields and
`plane.roundtrip_bytes_compared` a fifth, each **compensated by an explicit assertion** rather than
dropped, with a witness guard so a later widening fails; two refusal details in the design's matrix
were wrong and the implementation follows `R6_TOKENS`' own shape; the decode table holds six
token-count literals and not five; the suffix pass's specs must carry `compare = false` or a run
with a transcript panics; and `output`'s digest is taken twice so that a failed pass publishes the
container's vector.

**A pre-existing defect this capability found and did not fix — follow-up capability
`MF-SINGLE-TOKEN-LOGITS`, no roadmap number yet (section 11.2, and a named follow-up under roadmap
item 33).** **A one-token prompt
computes the logits of token 0.** `model_forward.fill_members` gathers by id only when
`pieces > 1`, and `build_embed_members` sets `pieces = tokens`, so at `tokens == 1` it reads the
embedding table's first row. Measured: `--model-forward` at `0`, `3`, and `17` returns one digest.
Reachable from the shipped CLI, silent, and **not shared by the resident path**. No golden exercises
`token_count == 1`, so it has been latent since R5B. It is not fixed here because the honest fix is a
discriminator on `model_forward.GraphMembers` — eighteen construction sites, three modules, four
arms — needing its own regression and its own review, and it is a distinct failure domain, which is
`CLAUDE.md`'s own reason to split. This capability depends on none of it: the hosted matrix has no
`T_prefix = 1` case and the real-model leg's smallest split is already `j = 2`. **The review found
that avoiding it in the corpus is not the same as refusing it on the surface**, so the arm now
refuses `T_prefix = 1` with a `SUFFIX`. Completing `MF-SINGLE-TOKEN-LOGITS` removes that refusal,
which widens the surface rather than moving it. Reproduction, evidence, owner surface, blast radius,
and the regression it must add are the field table in section 11.2; it needs a
`python3 scripts/pre-pr` of its own and takes a roadmap number when it is picked up.

**Blockers.** None. No Align request is proposed; Request 49 gains a **negative** client (the gap
shaped nothing, because the plane's only mutator is already in `decode_step`) and Request 22 gains a
note that a suffix is an operand rather than decoded text.

**Classifier scope.** `src` and executable scripts change, so the classifier selects the executable
row and **hosted** preflight: `python3 scripts/pre-pr --owner-test layer-forward-smoke -- gmake
layer-forward-smoke`. `make ci` is **not** selected — no aggregate membership, check topology, or
integration behaviour changes and this is not a `.align-revision` change — and `baseline-check` is
`N/A` on R6-STEP-N's condition (the `Makefile` is byte-unchanged and both new shim arms are inputs
to the **stub**). Re-checked at the publication head:
`python3 scripts/verification_scope.py --base origin/main --head HEAD` returns
`{"docs_only":false,"fresh_focused":false,"fresh_installed":false,"hosted":true,"scope":"hosted"}`,
so no fresh-image profile and no Docker are selected and the baseline artifacts are not consulted.

**Four merge re-checks this family always carries.** Roadmap item **33** (31 and 32 are on
branches), document schema **5**, next free Align request **53** (52 is expected to be claimed by a
parallel branch), and `scripts/decode-step-golden.jsonl` regenerated from the merged head. All four
hold at the publication head and `origin/main` is unmoved, so nothing was merged in; if it moves
before this lands, merge it by `git merge`, **never a rebase**, so every stacked branch's recorded
commits stay reachable, and re-check all four.

**Verification checkpoint (publication head).** `gmake build`, `gmake check`, `gmake fmt`,
`gmake format-check`, `git diff --check`, `gmake gate-topology-check`, `gmake ggml-spike-smoke`, and
`gmake layer-forward-smoke` (all six blocks; **139** documented decode-step cases, **137** with a
golden row, 42 codes, **13** suffix refusals each with its detail asserted, 52 `KV_REFUSALS` rows)
all pass; the owner is 65.9 s real at the repaired head and ~50 s at the publication head.
`python3 scripts/pre-pr --owner-test layer-forward-smoke -- gmake layer-forward-smoke` is stamped at
the publication head, and hosted CI passes there on all three jobs.
**`gmake decode-step-qualification` was not re-run for the repair or the minors**, and the reason is
that no changed line can reach it: the `2 <= j` guard removes a split the four prompts never
produce (the smallest `|L|` is 3), the `T_prefix >= 2` refusal cannot fire at `j >= 2`, the stub
latch lives in a forced build the qualification never builds, and the remaining changes are the
witness guard, the smoke's own assertions (this leg does not run that runner), comments, and
documents. The five recorded splits and every verdict below stand.
**`gmake decode-step-qualification`
exits 0 on the real model at `N = 16`**, with five prefix/suffix splits over the four prompts and
every one of oracle S, oracle C″, oracle B over `T_prefix + S` columns, and gate G1 **IDENTICAL** —
`case1` at `(T_prefix, S) = (2, 4)` and `(3, 3)`, the other three prompts at `(2, 1)` because they
tokenize to three ids. Both `case1` splits decode the same four ids, which is oracle S's claim seen
from outside: where the split falls does not change the run. It was run **twice** — the first run
found the TTFT trio's own comparability defect (section 11.3 deviation 6) and the second is at the
corrected head; the acceptance verdicts are identical in both. Instruments unchanged:
`ALIGN_LLM_LLAMA_DEBUG=/opt/homebrew/bin/llama-debug` (build 10566, `bb4caa754`) and the R2C-patched
`llama-eval-callback` from the `r2c-v2` cache. **The host was under memory pressure during both
runs** (another agent's OLMoE qualification had just finished), so R6-RESIDENT-WEIGHTS' own scaling
leg reports slower absolute elapsed times than its recorded run; that leg still reports its floor
MET and it is **not** this capability's claim — every verdict this capability owns is byte identity
and is unaffected by host load.

**Eight mutants injected at the repaired head, eight killed under `gmake layer-forward-smoke`.**
Suffix positions off by one; the mask offset wrong for `S > 1`; the write-back column base wrong
**at `S > 1` only**; the verify range at R6-STEP-N's exact old bound, which is correct for every
step and wrong only at `S > 1`; `mf_decode_row_tail`'s sixth literal back to a hardwired `1`, which
dies as `R5_SHAPE suffix[]node[26]`; and oracle S's exclusion list widened three ways — by the
**blocks** `decode`/`steps`/`output`, by the **field** `("decode", "token_ids")`, and by
`("decode", "n_past_first")`/`("n_past_last")`. **The `token_ids` field mutant survived at
`6cef75b`** and is why the witness guard now names fields rather than blocks; all three die now. The
two suffix-only arithmetic mutants die naming the exact case and the exact column
(`suffix[]layer[0]tensor[k]col[2]` and `col[-1]`).

**Next actions, in order.** (1) Publish the English pull request with the review envelope, every
finding's disposition, the consolidated repair commit, and the exact commands and results. (2) Merge
once the required checks pass. If `origin/main` moves first, `git merge` it — **never a rebase** —
re-check the four merge items above, regenerate `scripts/decode-step-golden.jsonl` from the merged
head, and re-stamp `python3 scripts/pre-pr --owner-test layer-forward-smoke -- gmake
layer-forward-smoke`, because the stamp belongs to an exact unchanged `HEAD`. (3) Re-check the four
items at the merged head. (4) Pick up `MF-SINGLE-TOKEN-LOGITS` or the next eligible roadmap
capability.

**Intentional uncommitted files.** None. The tree is clean and there is no scratch file inside it.


## Merged checkpoint: R6-RESIDENT-WEIGHTS (PR #147, 2026-08-29)

Branch `agent/r6-resident-weights`. Implemented on `agent/r6-kv-persist` head `9699848`, then
**merged** with that branch's review repair `1971c61` and its own `main` merge `bdb34eb` — which
carries `main` `3df063b` (R6-STEP-N, PR #145) and R5E-MOE-MODEL-PREFILL — by `git merge`, **never a
rebase**, so every stacked branch's recorded commits stay reachable. The four things that merge
re-checks all held: roadmap item **30** (29 is KV-PERSIST), document schema **4** (KV-PERSIST took
3), Align Request **50** (1–49 taken), and `scripts/decode-step-golden.jsonl` regenerated from the
merged head. Both R6 branches have now landed: `origin/main` is at `a6e545b` (R6-KV-PERSIST, PR #146, carrying
its final review minors `5c53ea1`), taken here by `git merge origin/main` — a clean merge, two files,
no conflict — and all four re-checks held again: roadmap item **30**, schema **4**, the next free
Align request number (now **52**, because this capability's review filed **51**), and the golden.

**Capability.** The whole weight set held **resident for one process's lifetime**, so that after one
fill every decode step reads exactly zero pack bytes. Dense Qwen2.5-Coder-7B Q4_K_M, **CPU only**.
`docs/specs/r6-resident-weights.md` is the authoritative ledger; sections 1 to 4 are the
pre-implementation design, 5.8 to 5.10 the result, and 11.1 the corrections implementation found.
Three of the design gate's four triggers fire: a changed CLI arm, a changed exchanged format
(schema 4, a `weights` object), and — the load-bearing one — a changed **ownership/allocation
boundary**, because the weight `buffer` and its `ggml_backend_buffer` wrap move from per-graph to
run scope. `docs/specs/r5c-metal-prefill.md` section 5.4 refused that hoist once and said it belongs
to "the capability that also re-establishes the invariant it weakens"; section 4.3 is that
re-establishment, in a separate counter pair at run scope.

**Complete.** Cell RW-P1's probe (a 4.68 GB `buffer_from_host` wrap **accepted**, two context
generations placing into one wrap, interior offsets above `INT_MAX` exact, `RW-P1: PASS`);
`model_forward.ResidentLayout` + `plan_resident`/`stream_layout`/`stage_embed_row` and eight
`Outcome` fields; the `RESIDENT` operand at `args[13]` with arity 14; `R6_RESIDENT`,
`R6_RESIDENT_BUDGET`, `R6_RESIDENT_UNAVAILABLE`; `fill_resident` (one chunked pass, whole
`token_embd.weight` first); the run-scope wrap with its own counter pair and its teardown before
`backend_close`; document schema 4 with the `weights` object in **every** document; eight new smoke
cases with oracle R at one and three steps, plus `ds-force-resident-wrap` from the review repair and
`ds-resident-stage-full` from the final review; `scripts/run-decode-step`'s 12 GiB physical-memory
preflight, `vm_stat` compressor recording, both scaling legs at three runs each, oracle R on the
real model, and the arena's size recomputed independently from `pack.json`; roadmap item 30,
`docs/align-development.md`, **Align Request 50** (`std.os.physical_memory`), Request 35 raised to
**high** with the 4.68 GB abort as its evidence, and Request 38's measured Darwin `pread` boundary.

**The `Makefile` is byte-untouched.** No target, no `.PHONY` word, no build-list entry, so aggregate
membership and check topology are unchanged by construction and `scripts/check-gate-topology`'s
byte-literal EXPECTED does not move. `src/ggml_ffi.align`, `scripts/ggml_shim.c`,
`src/ggml_spike.align`, and `src/layer_qwen2.align` are **byte-unchanged**: no new shim symbol and
no new Align surface were needed, because the zero-copy placement path has been the primary weight
path since R4.5. `scripts/ggml_shim_stub.c` is **not** unchanged — one function in the test double,
recorded as section 5.9 deviation 1.

**Result** (run 4, the **interleaved** re-measurement at the repair head, which is the measurement
of record). On the reference host (Apple M1, 16 GiB), `def add(a, b):`, `KV_WIDTH` 256, baseline
re-taken back to back in the same session, three runs per point, legs alternating:

| `N` | streamed elapsed | resident elapsed | `weights.step_pack_bytes` |
| --- | --- | --- | --- |
| 1 | 5.355 s | 6.800 s | 4,370,560,992 -> **0** |
| 4 | 7.594 s | 7.721 s | 17,482,243,968 -> **0** |
| 16 | 17.112 s | **10.049 s** | 69,928,975,872 -> **0** |

**412,763 ppm of the `N = 16` fixed task against a 150,000 ppm floor: MET**, 2.75x the floor and
70 % of the 586,000 ppm ceiling recorded before implementation. That is a **shortfall with a named
cause** — the one-time fill the ceiling assumed away — and not a ceiling-estimation miss:
`docs/specs/c8-speed-first.md` section 1 reserves that label for a result *far* below its ceiling and
its own worked precedent is 41 % of one. The runner now prints the percentage on every run and
applies the label only below one half. **The qualification has now been run four times — 412,763 /
449,779 / 507,887 / 511,125 ppm — and the byte metric was identical in all four.** Run 4 is the
interleaved one: the first three took all three streamed repeats and then all three resident ones,
which confounded the leg with the clock, and the review found it. Interleaving moved the streamed
leg from 18.016 s to 17.112 s and the resident leg from 8.808 s to 10.049 s, landing **37,016 ppm
below the lowest blocked run and 98,362 below the highest** — comparable to their own 61,346 ppm
spread, so with one interleaved run the magnitude is **not separated from noise**. What is
established is that the confound is removed; the direction section 3.4 argued from thermal drift was
not confirmed. The conservative reading is the worst of the four, 412,763 ppm. Arena 4,677,533,696 B,
fill 4,669 `pread`s of 4,677,120,000 B in 1.6–2.6 s, paid once whatever `N` is. Peak footprint
504 MB -> 4.74 GB. **Residency is slower at `N = 1`, a coin toss at `N = 4`** where the four runs
disagree about the sign, and decisive from 16 up; the crossover is stated in section 5.8.1 with the
disagreement shown rather than averaged away, and it is the practical reason the operand is opt-in.
The streamed leg's total pack reads reproduce
R6-STEP-N section 5.4's recorded 8,741,169,024 / 21,852,852,000 / 74,299,583,904 **exactly at all
three points**, so the baseline this claim is made against is that document's, byte for byte.
Oracle R PASS on the real model at `N = 16` with the transcript, logits blob, and reference GGUF all
supplied.

**Goldens.** `scripts/decode-step-golden.jsonl` moves — every row to schema 4 plus a `weights`
object, and 9 new rows, 107 becoming **116** (115 at the implementation head; the review repair adds
`ds-force-resident-wrap`). A programmatic diff of the old and new files confirms the **only** fields
that changed in a pre-existing row are `.schema_version` and `.weights`, which is exactly what
section 4.5 predicted, and the repair's own regeneration is **one added row, no removal, and no
changed row**. The final review's `ds-resident-stage-full` is a **117th documented case with no
golden row**: hosted CI showed that a 32-token prefill's activations differ in the last bit between
macOS/arm64 and Linux/x86_64, so a committed row for it would pin the regenerating machine. Section
5.9 deviation 9 records it; the case is asserted by oracle R against its streamed twin, which is a
within-host comparison. The other **six** goldens — `scripts/layer-forward-golden.jsonl`,
`scripts/model-forward-golden.jsonl`, `scripts/gpu-forward-golden.jsonl`,
`scripts/moe-layer-forward-golden.jsonl`, `scripts/moe-model-forward-golden.jsonl`, and
`scripts/ggml-spike-golden.jsonl` — are byte-unchanged, verified by regenerating all six and
observing no diff.

**`arena` is a reserved word in Align at this pin.** `fn f(borrow arena: slice<u8>)` fails to parse
with `error: expected ':'` at the parameter name and cascades into a wall of unrelated top-level
errors; `arena := 3` reports at the `:=`, one token past the cause. Every identifier is
`resident_*`, `pool`, or `layout`. The reserved word is the language's prerogative and is not
requested; the **diagnostic** is **Align Request 51**, filed by the review repair with three minimal
repros at the pin.

**Blockers.** None. Request 35 makes a graceful out-of-memory refusal impossible and Request 50
makes a host-memory check impossible inside the arm; both are compensated by `RESIDENT` being
opt-in and by the runner's 12 GiB preflight, and both are recorded rather than worked around.

**Constraints.** CPU only; `--model-forward-gpu` keeps its per-graph wrap because R5C section 2.6
measured that an unfreed Metal buffer aborts at `exit`. `--model-forward` and `--moe-layer-forward`
are byte-unchanged and deferred, because they pay the streaming cost once rather than `N` times. The
measuring host is a 16 GiB Apple M1 that compresses memory under pressure, so every timed run
records `vm_stat`'s compressor counters.

**Review.** One comprehensive review of `c73d4b8` was taken as two independent adversarial passes —
one on implementation and measurement, one on specification, measurement, and governance — and
returned four major and thirteen minor findings. Every one is dispositioned; the consolidated repair
is one commit on top of the `origin/main` merge. A **delta review of the repair head `6facd56`**
returned approve-with-minors: six wording and count corrections plus one new hosted case, applied in
the final commit and changing no emitted byte of a real-model run. The load-bearing finding was the run-scope balance
assertion (`docs/specs/r6-resident-weights.md` section 11.1 correction 12): it read
`created != 1 || freed != 1`, so a resident run that failed **before** the wrap existed reported
`graph_balance_failures: 1` and `released_before_owner_scope_end: false` on a teardown that was in
fact perfect. It now asserts balance, with "exactly one" kept for successful runs, and
`ds-force-resident-wrap` — the early-exit case the first implementation retired as unnecessary — is
its regression.

**Verification checkpoint (final-minors head).** `gmake build`, `gmake format-check`,
`git diff --check`, `gmake ggml-spike-smoke`, and
`gmake layer-forward-smoke` (all six blocks; **117** documented decode-step cases, 116 of them with
a golden row, reaching 41 codes)
all pass at the final head; `gmake check` (31 units), `gmake fmt`, and `gmake gate-topology-check`
passed at the repair head `6facd56`, whose Align sources and `Makefile` the final commit does not
touch. `gmake decode-step-qualification` **exits 0** on the real model at `N = 16` in 827 s of the
1800 s cap at `6facd56`, with the scaling row interleaved for the first time; oracle R PASS, arena
reproduced independently from `pack.json`, floor MET at 412,763 ppm. It is **not** re-run for the
final minors: they touch documentation, one hosted case, and one source comment, and change no
emitted byte of a real-model run. Instruments unchanged:
`ALIGN_LLM_LLAMA_DEBUG=/opt/homebrew/bin/llama-debug` (Homebrew build 10566, commit `bb4caa754`) and
the R2c-patched `llama-eval-callback` from the `r2c-v2` cache.

**Six mutants injected, five killed under `gmake layer-forward-smoke`.** The arena refilled per decode step;
a layer filled at the wrong arena base; the run-scope wrap never freed; the wrap created **and**
freed twice (which is what the repaired condition's `created > 1` clause carries); and the
pre-repair balance condition restored, which `ds-force-resident-wrap` kills by name. A sixth —
`stage_embed_row`'s bound restored to the whole arena — is **not** killed by anything in the corpus,
and that is recorded in section 5.10 rather than papered over: the repair is defence in depth
against a future caller, not a fix for a reachable defect. That mutant loosens the bound; its
**tightening** direction is now covered by `ds-resident-stage-full`, the final review's case, which
runs a resident prefill of exactly `MAX_PREFILL_TOKENS` distinct ids — the highest slot either call
site can produce — against its streamed twin under oracle R.

**Merged** as PR #147; `origin/main` `553563e` is that merge and is the base of the branch above.

**Process correction this capability owes the next one.** Sections 1 to 4 of
`docs/specs/r6-resident-weights.md` were written before implementation, but the file's first commit
is the implementation commit, so the repository holds **no evidence** of that ordering and a reviewer
is right to say so. **The next Track B performance capability commits its sections 1 to 4 — ledger,
baseline, cost ceiling, and floor — before the first line of implementation**, so the ordering is a
fact about the repository rather than a claim in a document.

**Intentional uncommitted files.** None. The RW-P1 probe (`src/r6w_probe.align` and its binary) is a
throwaway that lives outside the work tree and is not committed; section 5.8 records its whole
output.

## Merged checkpoint: R6-KV-PERSIST (PR #146, 2026-08-29)

Branch `agent/r6-kv-persist`, stacked on `agent/r6-step-n`, which is merged into it at `6ca1eef`
(the STEP-N review repair) by `git merge` — **never a rebase**, so both stacked branches' recorded
commits stay reachable. **Three commits and nothing uncommitted:** `9699848` is the capability,
`1971c61` is the consolidated repair of the first comprehensive review's findings, and the head is
the merge of `origin/main` at `3df063b` — R6-STEP-N, PR #145, which itself carries
R6-DECODE-KV-STEP1 (PR #144) and R5E — again taken as `git merge origin/main` and never a rebase.
Both stacked prerequisites have now landed, so the reconciliation they were waiting on is **done**:
roadmap numbering is unchanged (27 / 28 / **29**), `docs/align-requests.md` now runs 1–49 on this
branch so the next free number is **50** and this capability still claims none, and `Makefile` and
`.gitattributes` moved on `main` rather than here.

**Capability.** The R6 KV plane persisted to disk and reloaded in a **fresh process**, dense
Qwen2.5-Coder-7B Q4_K_M, CPU. `docs/specs/r6-kv-persist.md` is the authoritative ledger. **All
four** of the design gate's triggers fire — a changed public CLI arm, a **new persisted format**
plus a document schema bump, a **process ownership boundary**, and a coordinated invariant across
three or more modules: the plane's layout stops being private to `src/decode_step.align` and becomes
a published contract with an independent second reader.

**Complete.** `src/kv_plane.align` (new module: the `akvp` v1 constants, the 192-byte header, the
192-byte identity record, non-wrapping region arithmetic, five `crypto.sha256` digests, and the
writer; no `unsafe`, no `extern`); `--decode-step` arity 12 and 13 with `KV_SAVE`/`KV_LOAD` and the
`-` convention; `R6_KV_ARGS` at step 2b, `R6_KV_TOO_LARGE` at 6a, `R6_KV_EXISTS` at 6b, the pack
identity read and its degenerate-digest refusal at step 7/7b, the save path W1–W4 after step 10, and
the load path L1–L14 replacing steps 9–10; the chunked refill through `model_forward.window_put`;
document schema 3 with `plane.source`, the `kv` object, and `timings.first_token_ns`;
`scripts/kv_plane_reader.py` (a second implementation written from the specification, driven as a
subprocess, 13 reject kinds); `scripts/layer_forward_fixture.py`'s `kv_container` (a **third**
implementation) plus 39 mutants, an honest short-prompt container, a zero-identity pack, and a
non-degenerate pack source-identity record; the fifth smoke block's 55 new cases;
`scripts/run-decode-step`'s save → separate-process load → compare leg with the determinism, `du`,
and TTFT-proxy legs; roadmap item 29, `docs/align-development.md`, and client lines under Align
Requests 21, 29, 30, 31, 38, 39, and 49 including **one correction to Request 31's own forward
text**.

**The review repair added four rules to the format, and they are contract additions rather than bug
fixes** (spec section 11.4): the **canonical region layout** is now enforced by the arm as well as
the reader (`R6_KV_REGION("layout")`); **inter-region padding must be zero** in the arm too
(`R6_KV_RESERVED("padding")`, and no digest covers the gaps); `MAX_KV_PLANE_BYTES` and
`MAX_KV_LOGITS_BYTES` are re-checked **on load** ahead of the length comparison (`R6_KV_TOO_LARGE`);
and a **thirty-two-zero-byte pack identity** is refused rather than compared
(`R6_KV_IDENTITY("pack_absent")`). Spec section 5.2.1 is the rule-by-rule arm-to-reader parity
table: three asymmetries survive and all three are stated — `ZEROTAIL` by design, `pack_absent`
because its subject is the pack, and two places where the two implementations refuse the same file
and only the name differs.

**The `Makefile` is byte-untouched** — no target, no `.PHONY` word, no build-list entry;
`src/kv_plane.align` enters through `src/decode_step.align`'s import graph — so aggregate
membership and check topology are unchanged by construction. `src/ggml_ffi.align`,
`scripts/ggml_shim.c`, `scripts/ggml_shim_stub.c`, `scripts/build-ggml-shim`, and
`src/ggml_spike.align` are **byte-unchanged**: the refill's only crossing is
`align_ggml_window_copy`, which shipped with R5B, and every new refusal is reachable from a
malformed file rather than from a forced compute failure, so this capability needs **no new forced
shim build**.

**Goldens.** `scripts/decode-step-golden.jsonl` moves — every row to schema 3, plus 55 new rows, 52
becoming 107. `scripts/layer-forward-golden.jsonl`, `scripts/model-forward-golden.jsonl`,
`scripts/gpu-forward-golden.jsonl`, `scripts/moe-layer-forward-golden.jsonl`, and
`scripts/ggml-spike-golden.jsonl` are **byte-unchanged**, verified by regenerating all five and
observing no diff — which is the check that the new `Outcome` fields and the fixture's new pack
source record moved no other arm's document.

**Oracle Q's exclusion list is sixteen groups, eight more than the design drafted, and the reason is
recorded.** The design named `kv`, `plane.source`, `plane.readback_ns`, `plane.upload_ns`, `graph`,
`schedule`, `timings`, and `lifetime`. An empirical diff of a save-run document against a load-run
document found eight more keys that differ: `pack.reader_pread_count`, `pack.reader_bytes_read`,
`head.node_count`, `head.pread_ns`, `head.compute_ns`, `window.reuse_count`,
`window.member_placements`, and the `reference` block. Seven are counts of work the load path did
not do; the eighth is a **verdict** — `reference.verdict`, whose byte comparison against the source
GGUF lives in the prefill pass, so a load run performs none of it and now publishes `"-"` rather
than claiming `IDENTICAL` over zero comparisons. That is a public field's behaviour changing, not
only a test exclusion, and the qualification asserts it positively on the save run. What stays
**inside** the comparison is unchanged and is the point: `decode` in full, every `steps[]` object,
`plane.roundtrip_*`, `output`, `oracle_logits`, `oracle_decode`, `model`, `selection`, and `abi`.

**Six mutants were injected and all six die under `gmake layer-forward-smoke`**: a wrong pack
identity accepted, the plane digest skipped, the plane read offset off by four, the logits region
not persisted, a truncated file accepted, and the independent reader accepting a flipped reserved
byte. The last is the one that matters most — it fails in the reader, on a file the arm refuses
correctly.

**Verification checkpoint** (repair head). `gmake build`, `gmake check` (31 units), `gmake fmt`,
`gmake format-check`, `git diff --check`, `gmake gate-topology-check`, `gmake ggml-spike-smoke`, and
`gmake layer-forward-smoke` (all five blocks; **107** documented decode-step cases reaching 40
codes; the akvp block's 51 refusal rows over 13 reject kinds) pass.

`gmake decode-step-qualification` **exits 0** on the real model at `N = 16`, 10 min 41 s (641 s) of
the 1800 s cap. It ran **twice** — once at the implementation head and once at the repair head,
which adds four refusals to the load path — and every correctness value reproduced exactly: the same
64 ids, the same four container digests, the same byte counts and verdicts, only the timings moving.
Instruments: `ALIGN_LLM_LLAMA_DEBUG=/opt/homebrew/bin/llama-debug`, the **pinned Homebrew build**
`version: 0.2.0 (build 10566, commit bb4caa754)`, and the R2c-patched `llama-eval-callback` from the
`r2c-v2` cache.

**Every rule this capability owns passes on all four prompts**: oracle Q `IDENTICAL`, gate G `PASS`
on the load path, oracle B `IDENTICAL` over 26,607,616 B (`T = 6`) and 21,102,592 B (`T = 3`) on the
load path, oracle C′ byte-identical at `k ∈ {1, 8, 16}` on the load path, containers of exactly
29,970,432 B that `du` confirms are dense, and three writes per prompt — one under a perturbed
environment — producing one digest. **`oracle_logits.verdict` is `IDENTICAL` and `byte_identical` on
all four prompts on both paths**, so gate G1 holds unconditionally.

The only `FAIL` in the run is oracle A′ on prompt 1 at step 1, `2391/1e-4` on `ffn_inp-27` — the
exact value R6-STEP-N recorded, admitted under R6's rule because oracle C′ at `k = 1` is
byte-identical, so the divergence is llama.cpp's decode-versus-prefill kernel selection and not this
arm's arithmetic. Nothing about it is this capability's. `docs/specs/r6-kv-persist.md` section 5.6
records every number; the earlier "this host has no `llama-debug`" narrative and its section 5.6.1
are **deleted**, because they were wrong: the `r2c-v2` cache holds only `llama-eval-callback`, and
that is not evidence about `llama-debug`.

`gmake baseline-check` is `N/A` — no `Makefile` line and no build input moved — and
must be re-checked at the publication head, because R5E moved `Makefile` and the baseline artifacts.

**Merged.** PR #146, `origin/main` at `a6e545b`, carrying the final review minors `5c53ea1`. The
comprehensive review's finding that the repair's four added refusals were contract additions rather
than bug fixes is recorded in `docs/specs/r6-kv-persist.md` section 11.4. Nothing here is open.

**Reproducing the qualification on this host.** Both instruments exist and neither is built here.
`ALIGN_LLM_LLAMA_DEBUG` **must** be the pinned Homebrew `llama-debug`, `version: 0.2.0 (build 10566,
commit bb4caa754)` at `/opt/homebrew/bin/llama-debug` — never a local source build, because
`oracle_logits` is a byte comparison and a source build has been measured to disagree with the
pinned build. `ALIGN_LLM_LLAMA_EVAL_CALLBACK` is the R2c-patched instrument under
`~/.cache/align-llm/llama.cpp/r2c-v2/<revision>-<digest>/build/bin/llama-eval-callback`; **that
cache holds `llama-eval-callback` and nothing else**, so its lack of a `llama-debug` says nothing
about the host. `docs/align-development.md`'s `--decode-step` section states both as rules.

**Blockers.** None. R6-STEP-N's publication is a sequencing dependency, not a blocker.

**Constraints.** **No new Align request is proposed** and number **50** stays free — re-check after
`git merge origin/main`, because this branch's register still lacks 47 and 48. Requests 21, 29, 30,
31, 38, 39, and 49 each gain a cited client and **none changes status**. **No durability claim and
no TTFT claim**: `timings.first_token_ns` and the runner's invocation wall clock are labelled
diagnostics and no acceptance decision is taken from either. The R6 roadmap gate stays **unmet**.

## Merged checkpoint: R6-STEP-N (2026-08-29)

Merged as `3df063b` (PR #145). The record below is the branch's own.

Branch `agent/r6-step-n`, in publication. **Three commits and nothing uncommitted:** `a9c6161` is
the capability, `6ca1eef` is the consolidated repair of the two disjoint comprehensive reviews'
findings, and the head is the merge of `origin/main` at `d9a91e4` — R6-DECODE-KV-STEP1, PR #144 —
taken as `git merge origin/main` and never a rebase, so every recorded commit stays reachable.

**Capability.** An N-step greedy decode loop over the R6 KV plane, dense Qwen2.5-Coder-7B Q4_K_M,
CPU, gated on **token ids**. `docs/specs/r6-step-n.md` is the authoritative ledger. The design gate
is triggered on two of its four triggers — a changed public CLI arm and a changed exchanged document
schema — and the third, a coordinated invariant across three or more modules, is recorded as **not
fired** with its reason: the invariant is R6's and is unchanged, only its consumers move.

**Complete.** The `STEPS` operand and its two refusals (`R6_STEPS`, and `R6_KV_WIDTH` for
`T + N > KV_WIDTH`, with the precedence between them asserted); `LOGITS` accepting `-`; the
write-back of each step's own K and V column into the plane, before verification, with oracle B's
bound widened from `n_past` to `n_past + 1`; per-step iteration of the node table, the offset mask,
and the position image; `MAX_PREFILL_TOKENS` 8 -> 32 with `R5_ORACLE_TRUNCATED` byte-unchanged;
schema 2 with `steps[]`, `decode.token_ids`, and `plane.first_mismatch_step`; the fixture's
three-step reference loop and four-graph transcript; thirteen new smoke cases including two new
forced builds; `scripts/run-decode-step` extended with gate G and oracle C' at three checkpoints;
`scripts/decode_step_fingerprint.py`; roadmap item 28, `docs/align-development.md`, and one
recorded client line under Align Request 22.

**The `Makefile` is byte-untouched** — no target, no `.PHONY` word — so aggregate membership and
check topology are unchanged by construction. `src/ggml_ffi.align`, `scripts/ggml_shim.c`, and
`src/ggml_spike.align` are **byte-unchanged** too: the loop needs no new ggml op, FFI symbol, node
row, or slot.

**Gate G's load-bearing measurement, taken before the gate was claimed.** The transcript does not
print the sampled token and `result_output`'s argmax is not derivable from six of 152,064 printed
values, so the ids are gated through each decode graph's
`embd = GET_ROWS(token_embd.weight, [d_k])`. Over all 152,064 rows of the qualification model's
`token_embd.weight` (Q4_K) there are **149,710 distinct printed fingerprints and exactly one
collision class**, and that class is **precisely the 2,355 all-zero rows** — the unused vocabulary
slots. Every row with any non-zero element is unique. The gate therefore holds unconditionally on
the used vocabulary, and the runner refuses per step if a decoded id is ever a member of the
colliding class. Section 3.2's fallback G3 — a patch bump to log the sampled id — is **not taken**.

**Verification checkpoint, at the repair head.** `gmake build`, `gmake check`, `gmake fmt`,
`gmake format-check`, `git diff --check`, `gmake gate-topology-check`, `gmake ggml-spike-smoke`, and
`gmake layer-forward-smoke` (all five blocks; 52 documented decode-step cases reaching 24 codes;
34.0 s whole owner, 6.9 s decode block) pass.

`gmake decode-step-qualification` passed on the real model at the capability head, at `N = 16` in
**8 min 27 s** of the 1800 s cap, so the documented fallback to `N = 8` is not taken; ledger section
5.1 records every number. It was run **twice** there, and every correctness value reproduced exactly
— the same 64 ids, gate verdicts, byte counts, and per-step maxima; only the timings moved. Headline
results: gate G `PASS` on all four prompts over sixteen ids each; oracle B `IDENTICAL` over
26,607,616 B (`T = 6`) and 21,102,592 B (`T = 3`); oracle C' byte-identical at `k ∈ {1, 8, 16}` on
all four; oracle A' `PASS` at `max_abs_diff` **0** at every one of sixteen steps on three prompts,
and `FAIL` on the `T = 6` prompt at 2391/1e-4 at step 1, admitted under R6's rule.

**It was not re-run at the repair head, and the reason is that nothing it reads moved.** The repair
changes the hosted fixture's synthetic weights, the fifth smoke block's own assertions, the
error-document accounting rule (which only a document with `status: error` can show, and the
qualification asserts `ok` on every run), three comment literals, and the *ordering* of one
`numpy` preflight in `scripts/run-decode-step`, which on a host that has `numpy` changes nothing at
all. Success-path arithmetic, the goldens the qualification does not read, and every asserted value
in section 5.1 are untouched.

**Eight mutants were injected into `src/decode_step.align` at the repair head and all eight die
under `gmake layer-forward-smoke`** (ledger section 5.2): a write-back column off by one and a
skipped write-back, both as `R6_PLANE_MISMATCH step[1]layer[0]tensor[k]col[3]`; a frozen `n_past` on
the plane's column count and every per-step oracle; a transcript-graph skip off by one on
`R6_ORACLE_MISSING step[3]`; **`token = first_token`, the mutant the first review found the owner
could not see**, now dying on `decoded [24, 24, 24], not the reference loop's [24, 9, 27]`; an
unsliced position image and an unsliced offset mask, both on per-step oracle A'; and oracle B's
bound narrowed back to `n_past`, which drops the column its own step wrote. Two more are not
hosted-reachable and are unchanged: gate G compared against graph `k` or `k+2` disagrees at step 1
on every prompt, and oracle C' with its step index off by one differs at every checkpoint.

**`scripts/build-ggml-shim` gains two forced-build arms** — `engine+compute-step2` and
`engine+writeback-offset` — which are inputs to the **stub** shim only and never to an ordinary
build. That is the one build-adjacent file this capability touches; the `Makefile` itself is
byte-unchanged, so `gmake baseline-check` needs no re-record. Re-checked at the merge head after
R5E and R6 both moved `Makefile` and the baseline artifacts: none of the baseline's twenty tracked
artifacts is in this capability's publication diff, and the source → oracle → finalization chain
`e61993d` → `3cde6e2` → `cb8d2ce` stays reachable from the merge commit.

**Numbering, reconciled 2026-08-29.** R5E merged as PR #143 (`main` `5ccc2aa`), so roadmap item 26
is R5E and Align Requests **47 and 48 are real on `main`**. R6-DECODE-KV-STEP1 keeps roadmap item
**27** and Request 49, so this capability is roadmap item **28** and the next free Request number is
**50** — which stays free, because this capability proposes none. R5E also moved `Makefile`,
`.gitattributes`, the baseline artifacts, and `docs/align-development.md`; none is a
`MAX_PREFILL_TOKENS` consumer and none conflicts with this diff, but all are re-checked at the
merge.

**The merge, taken and reconciled.** Two conflicts, both resolved by keeping **both** sides:
`docs/align-development.md` (R5E's "MoE whole-model prefill development" section above this
capability's renamed `--decode-step` heading) and `scripts/run-layer-forward-smoke` (R5E's fifth
block above this capability's renamed sixth-block banner). Roadmap item **28** and Align Request
numbering (**49** real, **50** free) are confirmed unchanged by the merge. R6's own final repair
`5445c14` had recorded the prefill cap as **8** in `docs/specs/r5a-dense-layer-forward.md` and
`docs/specs/r5b-model-prefill-forward.md`; the merge commit moves both to **32** — `TOKENS` 1 to 32,
the range `7 .. 32` open for arithmetic and closed for comparison — with `R5_ORACLE_TRUNCATED`
byte-unchanged, and brings the two source comments that narrate the lift
(`src/layer_forward.align`, `src/model_forward.align`) and `docs/align-development.md`'s
`R5_ORACLE_TRUNCATED` paragraph with them. Ledger sections 8 and 9 record it. **No golden moved:**
all six golden files were byte-identical to what the merged runner produces, so the documented
`ALIGN_LLM_LAYER_FORWARD_GOLDEN_UPDATE=1` regeneration was not needed.

**Verification at the merge head.** `gmake build`, `gmake layer-forward-smoke` (all six blocks,
2 min 32 s), `gmake ggml-spike-smoke`, `gmake format-check`, and `git diff --check` pass.
`gmake decode-step-qualification` was run a **third** time on the real model, at the merge head, and
**every correctness value in ledger section 5.1 reproduced exactly** — the same fingerprint
partition (149,710 / 1 class / 2,355 ids / 0 non-zero), the same 64 ids, gate G `PASS` × 4, oracle B
`IDENTICAL` over 26,607,616 B and 21,102,592 B, oracle C′ byte-identical at `k ∈ {1, 8, 16}` × 4,
and oracle A′ identical to the last digit including the `T = 6` prompt's admitted 2391/5878/1295.
Only the timings moved, downward. Section 5.1 records the third run.

**Next actions, in order.**
1. `python3 scripts/pre-pr --owner-test layer-forward-smoke -- gmake layer-forward-smoke` at the
   pushed head. The publication diff touches `src/`, goldens, fixtures, and runners, so the
   classifier selects the executable row and the **hosted** profile: none of its twenty-four
   `FRESH_IMAGE_PATTERNS` is in the diff, `Makefile` and `.gitattributes` are byte-untouched
   relative to `origin/main`, and none of the baseline's twenty tracked artifacts (`src/main.align`
   and `Makefile` among them) moved, so `gmake baseline-check` passes without re-recording the
   chain. The stamp belongs to the exact unchanged head; re-merge and re-stamp if `main` moves.
2. The English pull request, with the review envelope and the exact commands and results.
3. **No further review.** Two disjoint comprehensive reviews read `a9c6161` against base `1671810`
   and their nine findings are all accepted and consolidated into `6ca1eef`; the repair did not
   expand scope, change approach, or change behavior, design, specification, or governance, so the
   final-review rule is not triggered. The merge is a base change and carries **fresh integration
   evidence** rather than a fresh review: it materially changes no reviewed risk — it adds R5E's
   already-reviewed sections beside this capability's, and moves two prose caps in the direction the
   reviewed ledger section 2.5 already specifies.

**Blockers.** None. R6 publication is a sequencing dependency, not a blocker.

**Constraints.** No new Align request is proposed and number **50** stays free. Request 22
(indexing arrays of Move element types) stays `PROPOSED` and **non-blocking**, and gains one
recorded line in `docs/align-requests.md`: it is now avoided in a **fourth** place, and the first
outside a container reader — `model_forward.StepColumns` carries its three string columns as the
stream-plus-column shape rather than `array<str>`. The tokenizer contact is unchanged: the gate is
on ids, not text, and the one place text would help — the external `llama-debug` corroboration leg —
stays hand-measured exactly as R6 left it. Requests 41 and 49 each gain a cited client and no
workaround is built for either. No hypothetical surface is consumed anywhere.

## Merged checkpoint: R6-DECODE-KV-STEP1 (2026-08-29)

Merged as `d9a91e4` (PR #144). The record below is the branch's own.

Branch `agent/r6-decode-kv-step1`, started from `main` at `c21b9e4` and **merged** twice rather than
rebased, so its recorded commits stay reachable: with `main` `76246f3` (R3-DECODE-RESIDENCY, PR #142)
and then with `main` `5ccc2aa` (R5E-MOE-MODEL-PREFILL, PR #143). Nothing uncommitted. `73557dc` is
the capability, `1671810` is the consolidated review repair, and `5445c14` is the narrow repair of
the final delta review's minors; the rest of the branch is the two merges, the re-recorded baseline
chain, and its record. Reviewers read `73557dc` against base tip `76246f3` with merge base `c21b9e4`;
the final delta review read `1671810`.

**Capability.** One decode step at `n_past = T` over an Align-owned KV plane, dense Qwen2.5-Coder-7B
Q4_K_M, CPU. `docs/specs/r6-decode-kv-step1.md` is the authoritative ledger. The design gate is
triggered — new public CLI surface, new exchanged format, coordinated invariant across six modules —
and the design was complete before implementation began.

**Complete and committed.** `align_ggml_op_concat` across the six FFI surfaces; `WHEN_DECODE`,
`OP_CONCAT`, the two plane slots (64/65), `mf_write_mask_offset`, the thirty-eight-row decode layer
table and its oracle map in `src/layer_qwen2.align`; the id/position split in
`src/model_forward.align`; the multi-graph transcript scan in `src/layer_forward.align`;
`src/decode_step.align` and its `--decode-step` arm; the fixture's decode reference and two-graph
transcript; the fifth `layer-forward-smoke` block and `scripts/decode-step-golden.jsonl`;
`scripts/run-decode-step` and the `decode-step-qualification` target; roadmap item 27,
`docs/align-development.md`, and Align Request 49. The real-model qualification is recorded in
ledger section 5.1.

**Review and repair.** One comprehensive review of `73557dc` over two independent reviewers on
disjoint risks. Reviewer B (spec/docs/governance) requested changes: 1 blocker, 4 major, 8 minor.
Reviewer A (Align/C/FFI) approved with 1 major and 6 minor. All 20 findings have a disposition and
are repaired in `1671810`, except the blocker, which is a **publication step** rather than a code
change and is next action 1 below. One final delta review of that repair approved it with three
minors — the R5A/R5B ledgers still described `MAX_PREFILL_TOKENS` as 6 and carried no
`R5_ORACLE_TRUNCATED` row; `verify_plane`'s size-disagreement early return named `k` even when only
the V concat row disagreed; and neither of that function's size guards has a shipped case — and
`5445c14` repairs all three. The repair narrows records and one diagnostic rather than expanding
scope, so no further full review is required.

The repair changes behaviour in two places and both are recorded in the ledger:

1. **A new refusal, `R5_ORACLE_TRUNCATED`** (ledger 2.7). Section 2.7 lifted `MAX_PREFILL_TOKENS`
   from 6 to 8 and documented at the constant that the cap was the oracle's. Documenting it was not
   a mitigation: `printed_count` clamps to six on both sides, so `--layer-forward`/`--model-forward`
   would have accepted `T` of 7 or 8 **with a transcript** and reported `PASS` over six of seven
   rows. Both arms now refuse that combination at their token stage. Without a transcript the same
   token count is admitted, which is what `--decode-step`'s own characterization pass needs.
2. **`graph.slot_high_water` is a maximum again.** `src/decode_step.align`'s copy of
   `model_forward.account` had dropped the `slot_high_water` line, so a run failing inside the
   prefill published 0.

Everything else is consistency: the shipped acceptance rule is now stated **once**, in ledger
section 2.11 (A, B, and C are all acceptance; an oracle A `FAIL` is admitted only inside the 0.5
bound **and** with oracle C byte-identical), with sections 3.3/3.4/5.1/10.2, the runner, the
roadmap, and `docs/align-development.md` pointing at it rather than paraphrasing it.

**Three mutants became shipped cases.** `ds-force-plane-stage-offset` (`R6_PLANE_MISMATCH`, which
was previously reachable only by mutating the source and was absent from `REQUIRED_CODES`),
`ds-force-decode-position`, and `ds-force-mask-offset`. Each is keyed on a slot only the decode
graph writes.

**Verification checkpoint (repair head).** `gmake build`, `gmake check`, `gmake fmt`,
`gmake format-check`, `git diff --check`, `gmake gate-topology-check`, `gmake ggml-spike-smoke`, and
`gmake layer-forward-smoke` — all five blocks, 40 documented decode-step cases reaching 23 codes —
pass. The four reviewer mutants and the new plane mutant were re-injected at the repair head and all
five still die with their distinct diagnoses: `R5_SHAPE node[24]` / `node[22]`, oracle A `FAIL` at
8092 on `q_rope` / 514 on `kqv`, and `R6_PLANE_MISMATCH layer[0]tensor[k]col[0]`.

**`gmake decode-step-qualification` was re-run on the real model at the repair head and again at the
publication head; both passed.** Every recorded value in ledger 5.1 reproduced on each: decoded
tokens 671/715/2691/526, oracle A `FAIL` at 2391 on `ffn_inp-27` for the first prompt and `PASS` at
0 for the other three over 5,058 elements each, oracle B `IDENTICAL` over 688,128 and 344,064 bytes,
oracle C byte-identical on all four with the argmax pairs 26312/262/1159/11844, `plane.bytes`
29,360,128, nodes 958/1014. Only the timings moved. Ledger 5.1 records all four runs. The
publication-head run took 3 m 48 s wall and was taken concurrently with an unrelated aggregate on
this host; no structural quantity moved.

**Goldens that moved, and why.** Ledger section 5.3 is exact. `gpu-forward-golden.jsonl` and
`moe-layer-forward-golden.jsonl` are byte-unchanged. `layer-forward-golden.jsonl` and
`model-forward-golden.jsonl` each rename one row for the token-cap lift and **add two**
(`*-tokens-seven-transcript` refused, `*-tokens-eight-no-transcript` admitted); no existing row's
bytes change. `decode-step-golden.jsonl` adds the three forced-build rows and changes seven existing
rows in one field, `graph.slot_high_water`, which is repair (2) above.

**Coding-baseline chain, re-recorded — reviewer B's blocker, discharged.** The capability changes
`Makefile`, one of the twenty recorded baseline artifacts, so the chain on `main` does not bind this
head. (`scripts/build-ggml-shim` also changes but is **not** a recorded artifact and does not itself
invalidate the chain; an earlier draft of this record said it did.) The identity-bound chain is
`e61993d` → `3cde6e2` → `cb8d2ce` — clean source, immutable oracle projection, finalization — with
the pending measurement recorded on Linux (aarch64, kernel 6.11.11-linuxkit, Python 3.12.3) through
the DinD wrapper, exactly as R5D's and R5E's were. Exactly one of the twenty artifact digests moved
(`Makefile`); `.align-revision` is unchanged at `3a34febe` and the twenty paths are identical.
`gmake baseline-check` passes on Linux at the finalized head. This chain **supersedes** the one this
branch first recorded against `main` `76246f3` (`e4548b1` → `6d1c152` → `1bbacaa`), which PR #143
invalidated by changing recorded artifacts of its own; both chains stay in this branch's history and
only the later one is named in the finalized baseline.

**Next actions, in order.**
1. `python3 scripts/pre-pr --owner-test layer-forward-smoke -- gmake layer-forward-smoke`, on the
   unchanged head. The diff touches `Makefile`, `scripts/build-ggml-shim`, and the goldens, so the
   classifier selects the executable row and the installed fresh-image profile; do not substitute a
   Docker skip or an ambient `DOCKER_HOST`.
2. Open the English pull request with the verification table, the review envelope, and the finding
   dispositions. It must be a **merge** commit: squash and rebase would make the three baseline
   commits unreachable from `main`.
3. The next capability is step 2 and the decode loop, which needs a write-back at column `n_past` —
   the one thing that makes the plane both a read and a write target in one graph.

**Deviations from the ledger, recorded rather than hidden.** Ledger section 10 is authoritative and
now carries all of them: the decode layer is **thirty-eight** rows and not thirty-six (10.1); oracle
C is computed by the runner rather than by the arm, though it is acceptance (10.2); there is
deliberately no `R6_ORACLE_SHAPE` and the seam's `R5_ORACLE_SHAPE` reaches the document unchanged
(10.3); the golden rows that moved and why (10.4); the deferred closure cells, now including the
external oracle-C chain the review recommended and why it is deferred (10.5); and the nine
re-implemented functions, **each diffed against its original with every divergence named**,
plus the 1,328-byte `model_forward.Outcome` this created (10.6).

**Open decision for the user, unchanged from the design.** Whether to extend the R2c patch to
`examples/debug/debug.cpp` so a decode step gets a byte-exact external logits reference. It would
close ledger risk 3 at the cost of a new patch digest, a cache-generation bump to `r2c-v3`, and
re-running the R2c qualification. R6 ships without it. It is also the honest route to making the
review's "drive the C chain externally" recommendation possible: the operand `llama-debug` needs is
a prompt **string** and the runner holds token ids, so an external chain today would have to guess
the decoded token's text.

**Numbering, re-checked at the merge with `main` `5ccc2aa`.** Roadmap item **27** and Align Request
**49** are unchanged and are now contiguous rather than reserved: `main` carries roadmap items to
**26** and requests to **48**, because `agent/r3-decode-residency` landed item 25 as PR #142 and
`agent/r5e-moe-model-prefill` landed item 26 and Requests 47 and 48 as PR #143. The numbering hazard
ledger section 8 recorded is therefore closed — the numbers this branch chose against unmerged
claims are the numbers that are free.

## Merged checkpoint: R5E-MOE-MODEL-PREFILL (2026-08-28)

PR #143 merged as `5ccc2aa` on `main`. The publication and merge named in the next actions below
are complete; the rest of this record is unchanged.


Branch `agent/r5e-moe-model-prefill`, based on the merged MOE-PREREQ-DISCHARGE (PR #133, `35a0df6`)
and then **merged** with `main` `e312bd7` — the merged R5D at PR #139, which itself carries PR #134's
pin move, PR #135 (R3-RESIDENCY-SIM), PR #136, PR #138, and PR #140 (R2C-DECODE-INSTRUMENT) — rather
than rebased over it, so this branch's recorded baseline-chain commits stay reachable. The branch is
`5e3356d` (design ledger), `053de09` (implementation), `e7f727f` (review repair), the merge commit,
and the reconciliation and baseline commits on top. Design ledger
`docs/specs/r5e-moe-model-prefill.md` is authoritative and carries the implementation's corrections
C1–C25 and the cell-to-case map. **The capability is implemented, reviewed, verified, and committed**;
`src/moe_model_forward.align`, `scripts/run-moe-model-forward`,
`scripts/sweep-moe-model-forward-excerpt.py`, `scripts/moe-model-forward-golden.jsonl`, and
`eval/fixtures/olmoe-model-6tok.txt` are new, and `src/layer_olmoe.align`, `src/ggml_spike.align`,
`scripts/layer_forward_fixture.py`, `scripts/run-layer-forward-smoke`, `scripts/build-ggml-shim`,
and `scripts/ggml_shim_stub.c` are extended. **No `extern` symbol is added and `scripts/ggml_shim.c`
is unchanged.** No intentional uncommitted files. Merge is the only remaining step.

**What it does.** R5's **third** gate stage — 最小モデル on the routed path, after R4.5/MOE-PREREQ's
単一block and R5D's 単一layer: `ggml-spike --moe-model-forward` computes a
whole sixteen-layer OLMoE prefill of at most six tokens — per-layer routing, only the routed experts'
planes read into **one** Align-owned claim window reserved at the arithmetic union bound and reused
across layers, the narrowing inside layer fifteen where the instrument does, and the output head —
and emits one `R5_MOE_MODEL_FORWARD` (`schema_version: 1`) document with the per-layer union curve.
`KV_WIDTH` is a **mandatory** fifth operand, not R5B's optional trailing one, because on a routed
model the declared attention width changes which experts the router selects and therefore which bytes
the arm reads.

**Measured on the real model** at the adopted pin: the final logits are **byte-identical** to
`llama-debug --save-logits`, `sha256 a56195da2c913d8dd7fa608917a381200c4b59d1c534fae2d4bbb828f80d2383`;
the self-reference oracle is **227 of 227** nodes byte-identical over 34 graphs; the transcript oracle
is `PASS` over **16 of 16 layers, 227 of 227 nodes, 21,372 elements**, max |Δ| 0 ten-thousandths and
max |Δsum| 0 millionths; the routing-identity oracle is `MATCH` at **546 of 546** printed ids over 728
slots and 16 of 16 block sums; and the runtime-width run is `WITHIN`, argmax 2262, reading the same
1,301,446,656 expert bytes. **Residency: 1,301,446,656 of 3,900,702,720 expert bytes = 333,644 ppm
(33.36%)**, 1,029 of 3,072 planes, 343 of 1,024 keys — two thirds of this model's expert weights are
never touched by a prefill. Peak resident weight bytes 280,342,528 against 4,212,193,280 for the
container, **6.66%**; dense window 84,520,960 B; claim window 195,821,568 B reserved at `U_max` 48
with a 101,990,400 B peak use at layer 0; activation peak 4,440,064 B; 34 graphs, 918 ggml nodes.

**The residency *policy* stays deferred, deliberately.** Within one prefill there are 343 demands and
343 distinct `(layer, expert)` keys, so no cache can hit; a policy needs repeated prefills or decode
before a hit rate is a measurement. What this capability hands R6 and any residency work is the shape:
claim `pread` **560.8 ms** against **147.3 ms** of graph compute in this run — the claim read is
**3.8×** compute — so a six-token routed prefill of this model on this CPU is I/O bound even with the
pack in page cache. Both timings are single-run diagnostics inside the spreads ledger correction C16
records (109.9–252.8 ms compute, 519.9–612.0 ms claim `pread`); the exact-integer half carries no
measurement risk.

**Review.** One comprehensive review of the stable candidate, two complementary reviewers over
explicitly disjoint risks at implementation head `053de09`: reviewer A returned **no blocker** with 1
medium and 4 low findings; reviewer B returned **changes requested** with 3 medium, 3 low, and 2 info
findings. **All thirteen were validated and accepted**, none rejected, and all are repaired in the one
consolidated commit `e7f727f`; ledger corrections C17–C22 record the contract changes. The repair
built and measured the two promised window-budget fixtures (a member declaring 2^40 bytes reaches
`R4_PACK_OFFSET`, not `R5_WINDOW_BUDGET` or `R5D_CLAIM_BUDGET`, so both are recorded as fail-closed
guards and `R5_INDEX` as never emitted), fixed the coverage denominator at the 36 declared `R5*` codes
(32 reached plus 5 inherited, asserted in both directions), published `oracle.sums_expected` /
`sums_matched`, added the reference arm's non-aliasing assertion, made `residency.keys_distinct` a
real run-level set cardinality, refused a non-UTF-8 path with `R5E_PATH`, and corrected
`expert_bytes_read_ppm` to 333,644 at all three sites. After the merge with `main` a **final
comprehensive review of the merged candidate** was run because the merge brought in R5D's own review
repair, which this branch had not carried. It returned **approve after repair** with 13 findings — 1
high, 3 medium, 9 low/info — **no defect in shipped behaviour**; all were validated and accepted and
repaired in one consolidated commit, recorded as corrections **C24** and **C25** plus in-place record
fixes. Its envelope and every finding's disposition are on the pull request.

**Align capability requests.** Two new, both `PROPOSED` and non-blocking: **Request 47** (a `Borrow`
argument must be a stable named local or field) and **Request 48** (same-call aliasing between a
`borrow mut` owner and its own `Copy` scalar field, where the nested read-only-borrow spelling of the
same shape compiles). They were drafted as 46 and 47 and renumbered at reconciliation because R3's
pair merged first and took 45 and 46. Both probes were re-measured unchanged at the adopted
`3a34febe`. R5E is also appended as a **third client** of Requests 45 and 46 — the two it could only
anticipate while they lived on `agent/r3-residency-sim`.

**Verification, re-run in full at the merged head against the managed `3a34febe` compiler**, on this
macOS host with `gmake`, the recorded Homebrew
`LIBRARY_PATH=/opt/homebrew/lib:/opt/homebrew/opt/openssl@3/lib:/opt/homebrew/opt/zstd/lib`, and the
`CARGO` wrapper (`docs/align-development.md`):

```text
gmake check                    ok: checked 31 unit(s) per-unit (153 s)
gmake build                    ok
gmake ggml-spike               ok, stub shim and real shim (37 s)
gmake ggml-spike-smoke         PASS - 7 no-document, 43 documented cases; olmoe 22 blocks /
                               69 members, 16 ExpertBlocks, claim surface PASS
gmake layer-forward-smoke      PASS x3, byte-identical apart from the mktemp path, 41 / 37 / 37 s -
                               R5A/R5B's 8 no-document and 75 documented cases, 59 model-forward,
                               28 gpu-forward, R5D's 8 / 78 with 29 codes, and R5E's 14 no-document
                               (R5E_ARITY, R5E_PATH) and 96 documented cases, 32 of the 36 declared
                               R5* codes plus 5 inherited R4/R2 codes, all four oracles, the routing
                               identity element-wise complete over a whole model, and
                               arm-r5a/r5b/r5d-unchanged
gmake alignpack-smoke          PASS - 27 positive fixtures, 128 negative sources, 20,303 assertions
gmake residency-sim-smoke      PASS - PR #135's owner, unchanged by this branch
gmake expert-trace-smoke       PASS - PR #140's parser owner, unchanged by this branch
gmake gate-topology-check      PASS
gmake format-check             PASS; gmake fmt leaves no diff; git diff --check clean
```

The focused qualification — opt-in, capable-only, in **no** aggregate — on the host that holds the
model, at the adopted pin:

```text
gmake moe-model-forward-qualification   every section 5.2 assertion PASS

the two instruments agree (result_output sum -111030.031250, tokens 1545,823,9,66,13,270)
self-reference IDENTICAL (227/227 nodes byte-identical over 34 graphs)
routing identity MATCH, 546/546 printed ids over 728 slots, 16/16 block sums
transcript PASS, 16/16 layers, 227/227 nodes, 21372 elements, max |d| 0, max |dsum| 0
logits IDENTICAL at the reconciliation width, sha256 a56195da2c913d8dd...
logits WITHIN at the runtime width, argmax 2262, top-ten set 10/10
residency 1301446656/3900702720 expert bytes = 333644 ppm (33.36%), 1029/3072 planes, 343/1024 keys
peak resident weight bytes 280342528 against 4212193280 - 6.66%
34 graphs, 918 ggml nodes, activation peak 4440064 B, slot high water 80/128
microbenchmark B = 147.318 ms; dense pread 126.5 ms, claim pread 560.8 ms
```

**No golden byte changed at the new pin**, and every exact-integer quantity in ledger section 7 is
identical to the pre-pin run, so the adoption needs no behavioural correction row; ledger correction
C23 records the pin move, the request renumbering, and the appended client evidence.

**Baseline chain, re-recorded.** This branch changes `Makefile` and `.gitattributes`, both among the
twenty recorded canonical baseline artifacts, so the chain that shipped with R5D no longer binds this
head. See the pull request for the re-recorded identity-bound chain (clean source -> immutable oracle
-> finalization), measured on Linux (aarch64, kernel 6.11.11-linuxkit, Python 3.12.3) with `make
baseline-check` there ending `baseline chain: PASS`. **This pull request must merge with a merge
commit**; squash and rebase merges would make the recorded commits unreachable.

**Next action.** Merge the pull request. `main` moved three times during publication — PR #139
(R5D), PR #141 (R2D-DECODE-LOCALITY-GATE) and PR #142 (R3-DECODE-RESIDENCY), the last two from a
parallel session — and this branch **merges** all three rather than rebasing over them. R2D took
roadmap item **24** and R3-DECODE-RESIDENCY item **25**, so R5E is item **26**. `make ci` is **not** selected: `HOSTED_CHECK_TARGETS`
membership is unchanged because R5E's owner is `layer-forward-smoke`'s fifth block, already a member,
and the one new Makefile target, `moe-model-forward-qualification`, joins no aggregate. The `Makefile`
edit is still an executable-contract boundary, so publication takes the **fresh-image
(Docker-in-Docker)** installed profile, not the documentation lane.

## Merged checkpoint: R3-DECODE-RESIDENCY (2026-08-29)

Branch `agent/r3-decode-residency` merged as PR #142, merge commit `76246f3` on `main`, by a
**parallel session**. It is the residency consumer of R2D's capture and closes the **decode half of
the R3 roadmap gate**; no design gate, no Align source change, no `Makefile` change, no aggregate
membership change, so R5E's baseline chain is unaffected by it.

`scripts/run-decode-residency-gate` replays `main --simulate-residency` four times at section 7.4's
975,175,680 B budget over the same 40-prompt corpus: mixed, decode-only, a prefill-only coverage
control, and a head-4 stream-length control. **The gate is met in the decode direction but the
answer is narrower than the prefill one**: `recent_reuse` beats `lru` by 59 to 238 per mille at
budgets of 15/31/62/125 per mille of the expert footprint, and at 250 and 500 per mille **no
candidate beats the baseline at all** on any decode arm. The prefill-only control at the same
250-per-mille budget is still `BEATS_BASELINE`, and the head-4 control — eleven per cent *fewer*
demands than that winning arm — is not, so what removes the win is the presence of decode demands
rather than coverage, working-set ratio, or stream length. R4B's decode-corpus resume condition is
discharged **negatively**, and R6's KV tiering is ordered ahead of a runtime expert-residency policy.
`docs/specs/r3-residency-sim.md` section 8 is the authoritative record.

**What it means for R5E.** R5E defers any residency policy because a single prefill has 343 demands
and 343 distinct keys. Item 25 is the first measurement of a policy in the decode regime that
deferral names, and it says the policy question is open at realistic budgets rather than settled —
which is the reason R5E ships the per-layer union curve (`schedule[].routed`) as an input to that
work instead of a policy of its own.

## Merged checkpoint: R2D-DECODE-LOCALITY-GATE (2026-08-29)

Branch `agent/r2d-decode-locality-gate` merged as PR #141, merge commit `c21b9e4` on `main`, by a
**parallel session**. It started from `main` `89d8721` (R2c PR #140) and merged `main` `e312bd7`
(R5D PR #139) rather than rebasing over it. It is the first measurement consumer of PR #140's
patched instrument and it closes the **decode half of the R2 roadmap gate**; no design gate was
triggered.

**The gate is met in the decode direction.** On the same 40-prompt corpus against
`OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf` — 40 prefill and 640 decode graphs over 832 token positions
— all three arms are `LOCALITY` against a 125 per mille null: `prefill@8` **371** per mille,
cluster-robust [338, 405]; `decode@8` **447** per mille, cluster-robust [426, 468], 16 of 16 layers
clearing; `boundary` **364** per mille, cluster-robust [325, 405]. Greedy decode's token-repetition
rate is 51 per mille and excluding those pairs leaves the decode arm at 429 per mille, still
`LOCALITY`. `docs/specs/r2a-expert-trace.md` section 9 is the authoritative record; section 8's
prefill gate and its 286 per mille are untouched. It adds no `Makefile` target and changes no
recorded baseline artifact, so R5E's baseline chain is unaffected by it.

**What it means for R5E and for R3.** R5E records claim-level expert residency as a **decode-time**
property and defers any residency policy because a single prefill has 343 demands and 343 distinct
keys. R2D is the first direct measurement of the regime that deferral names: expert reuse between
consecutive decode steps is materially higher than in prefill (447 against 371 per mille). It does
not by itself make a cache-hit claim — that still needs a multi-prefill or decode **replay**, which
`docs/specs/r3-residency-sim.md` owns — but it removes the "decode was never observed" caveat that
R3's own measurement section records.

## Merged checkpoint: R5D-MOE-LAYER-FORWARD (2026-08-28)

Branch `agent/r5d-moe-layer-forward` merged as PR #139, merge commit `e312bd7` on `main`, preserving
its recorded baseline chain `7c4830a` -> `c6cee0c` -> `09de0fd` with a merge commit. Design ledger
`docs/specs/r5d-moe-layer-forward.md` remains authoritative.

**What it delivers.** R5's second gate stage for a **routed** OLMoE layer: one prefill of at most six
tokens through `blk.0`, computed by ggml over attention weights and only the routed experts' planes
held in Align-owned buffers, checked against llama.cpp's own numbers. The routed layer reads
**101,990,400 of 261,095,424** expert bytes (390,625 ppm, 75 of 192 planes, 25 block reads); the
self-reference oracle is 46 of 46 byte-identical; the routing-identity oracle is `MATCH` at 36 of 48
printed ids plus the exact sum 1,471; the transcript oracle is `PASS`, 26 nodes, 2,376 elements, max
|Δ| 0 ten-thousandths. Required microbenchmark B is **5.64 ms**. The residency win is a **decode-time
property**: 39% of the layer's expert bytes at six prefill tokens, 12.5% at one, 73% at eighteen. The
boundary change is five new FFI symbols plus one widened one; no new Align capability request was
needed, and Requests 37, 42, 45, and 46 gained R5D as a non-blocking client.

R5E is built directly on it: `src/layer_olmoe.align` is R5D's topology module, extended with
layer-parameterized tables, and R5E's arm is a fifth `ggml-spike` arm beside R5D's fourth. R5E takes
main's repaired R5D verbatim — R5D's `stage_claim_types` refusal, its stable-insertion-sort stub
`argsort`, its `view_2d` F32 gate, and its `moe-engine-claim-type-mismatch` case are unmodified by
R5E.

## Merged checkpoint: R3-QUALIFICATION-PREREQUISITES (2026-08-28)

Branch `fix/r3-qualification-prerequisites` merged as PR #138, merge commit `1b11245` on `main`,
authored by a **parallel Codex session** rather than by the session that produced R3 and R5D. It
started from `main` `95c47e7`, the merge of R3 PR #135. A second R3 implementation was independently completed before that merge became visible;
its duplicate PR #137 is closed and will not be integrated. Its final review nevertheless exposed
one root-cause class that applies to the merged qualification: the wrapper generated a Model IR but
did not validate it or the requested budget until after every prompt had invoked the external
instrument, so a locally knowable defect could consume up to 40 600-second prompt runs.
Published and merged as PR #138; R5D merges it in rather than rebasing over it, so this branch's
recorded baseline-chain commits stay reachable.

## Merged checkpoint: R2C-DECODE-INSTRUMENT (2026-08-28)

Branch `agent/r2c-decode-instrument` merged as PR #140, merge commit `89d8721` on `main`, authored
by a **parallel Codex session** rather than by the session that produced R3 and R5D. It started from
`main` `1b11245`, the merge of R3 follow-up PR #138.
It **takes** decision (c): the source build of llama.cpp at exact commit
`bb4caa7540188872173c44d161602d9271386413` with the minimal R2c instrument patch is pinned and
shipped, which unblocks R6 and therefore R7-R9. Its first measurement consumer,
**R2D-DECODE-LOCALITY-GATE**, is merged (above). R5 microbenchmark C remains independently blocked
on Align Request 41.

**Merged contents.** The triggered design ledger is `docs/specs/r2c-decode-instrument.md`
(`d8e4818`); the reviewed implementation head is `5f1eb3e`, the first consolidated review repair is
`46432de`, and the final review's three accepted findings are repaired in `76400f5`.
`.llama-revision` and the 2,170-byte patch pin the external source and
two-file diff. The `r2c-v2` managed builder has completed a fresh CPU build with Metal and
llama/ggml shared libraries disabled, verified build 10566 / commit `bb4caa7`, and emitted a
schema-1 attestation. The patch preserves the omitted/nonpositive `-n` one-prefill behavior, emits
up to `-n` one-token decode graphs with common sampling and EOG stop, and prints every
`ffn_moe_topk` axis while leaving all other debug tensors at three-plus-three.

The source-to-client check found and corrected one pre-existing R2A contradiction: prose said a
full-axis R2c transcript needed no parser change, but `src/expert_trace.align` accepted exactly six
values whenever an extent exceeded six and derived truncation flags from extent. Schema 1 now
admits exact compact or full forms based on the ellipsis actually observed. Existing compact
documents remain unchanged; the independent generator now owns full slot/token success and eight
malformed/mixed/non-router refusals. `make check`, `scripts/run-r2c-instrument-smoke` (54 contract
groups), and `scripts/run-expert-trace-smoke` (108 fixtures, 17 error codes) pass. The compiled dense
qualification passes through the product parser: omitted, zero, and negative `-n` each produce one
prefill graph, while `-n 2` produces one prefill plus two decode graphs. The real OLMoE half also
passes: three graphs including decode, 48 full-width groups, 384 selections, and full-axis extent
eight. Independent parity reports 16 layers, 64 experts, top-8, 488 retained selections, and the
known token-reduced final layer. No model or transcript is committed.

**Review envelope.** Host-native Codex (`gpt-5.6-sol`, xhigh) first reviewed
`5f1eb3e7614a8a8e1cfd4ee13e8b31db3b8c26a8` against base tip and merge base
`1b11245cee98bf3bba8ab874683206b4243d1761`. Verdict: four valid findings — two P1 and two P2 — all
accepted, none rejected. That repair compares staged and unstaged tracked source to `HEAD`; disables
Metal and advances the cache recipe to `r2c-v2`; requires an applicable router extent above six;
and downloads the tiny model to a hash-validated temporary sibling before atomic rename. The same
pass corrected the remaining compact-only normative prose in R2A. Deterministic owners and fresh
dense/MoE materialization pass after repair.

The required final comprehensive review covered `46432ded7e8d60d8bca4f4d33fdc80a252099aae`
against the same base tip and merge base. It found three further valid findings, all accepted and
none rejected: R2/R3 historical replays still changed from six to eight observed slots under the
R2c instrument; explicit/XDG/HOME cache roots could resolve inside the checkout; and router axis 2
could change compact/full print form between groups or blocks. The final repair makes historical
gates share an exact compact-axis admission check, rejects lexical and symlink-mediated checkout
cache containment, and settles the axis-2 form across every applicable group/block with a new
`R2_ROW_COUNT` fixture. The repair is limited to those recorded findings and their plan/owner
evidence, so the workflow requires repair-delta inspection and affected owner verification rather
than a third comprehensive review. Both are complete.

**Candidate contents.** The pin, patch, managed builder, deterministic smoke, focused qualification,
R2A parser/source oracle changes, R2A specification correction, roadmap and developer-guide
changes, and this handoff update belong to this capability. `Makefile` and aggregate topology are
intentionally unchanged, so the canonical coding baseline artifact set is unchanged.

Published and merged as PR #140. R5D merges it in rather than rebasing over it, so this branch's
recorded baseline-chain commits stay reachable; `Makefile` and the canonical baseline artifact set
are unchanged by it, so R5D's chain still binds.

**Latest durable verification.** On WSL2 x86_64 with GNU 14.2.0 and the managed Align
`3a34febe` toolchain:

```text
scripts/run-r2c-instrument-smoke                         PASS, 54 contract groups
make expert-trace-smoke                                  PASS, 108 fixtures / 17 error codes
make residency-sim-smoke                                 PASS, oracle and admission owners
make check                                               PASS, 31 units per-unit
scripts/run-r2c-instrument-qualification                 dense PASS; MoE PASS
scripts/run-expert-trace-parity                          MoE PASS; model read-only proof PASS
scripts/llama-eval-callback-toolchain verify             bb4caa7540188872173c44d161602d9271386413
scripts/llama-eval-callback-toolchain attest instrument  r2c-v2, instrument sha256 2911b1ffed36...
```

## Merged checkpoint: R3-RESIDENCY-SIM (2026-08-28)

PR #135 merged as `95c47e7` after all three GitHub checks passed. Design ledger
`docs/specs/r3-residency-sim.md` remains authoritative. Implementation, real-model qualification,
review, publication, and merge are complete.

**What it delivers.** The R3 roadmap gate, measured. `main --simulate-residency` replays the demand
stream implied by a set of real `R2_ACTIVATION_TRACE` documents against ten expert-residency cache
policies in four families — `lru`, `lfu`, three fixed-window `recent_reuse`, two `topk_prefetch`
degrees, plus the `null` / `compulsory` / `belady` references — at a nine-point budget sweep, with a
leave-one-document-out jackknife over the corpus and a headroom measure against the miss-optimal
offline reference, and emits one `R3_RESIDENCY_SIM` (`schema_version: 1`) document. The design gate
triggered on three counts: a new public CLI verb, a new versioned exchanged format, and a coordinated
invariant across three modules plus the `Makefile`.

**The gate is met.** On the real 40-prompt corpus (`eval/prompts/expert-locality-v1.txt`, md5
`d7fff23f5a1d4f6237e6f848f3318d8b`) against `OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf`: a stream of
17,280 demands over 938 distinct `(layer, expert)` keys of 1,024, 192 token positions, slot coverage
750 per mille. At the requested budget of 975,175,680 B (250 per mille of the 3,900,702,720 B expert
footprint), verdict `BEATS_BASELINE` — `recent_reuse_w32` fetches 26,033,848,320 B against the `lru`
baseline's 33,532,231,680 B, 223 per mille fewer against a 50-per-mille materiality floor, with a
40-fold jackknife minimum gain of 213 per mille (stable) and 574 per mille of headroom still left to
the offline optimum. Across the sweep: `BEATS_BASELINE` at 1/3/6/12/25 per cent,
`NO_POLICY_BEATS_BASELINE` at 0 and 50 per cent, `NO_HEADROOM` at 100 per cent. Top-k prefetch buys
hits and pays for them with more bytes than it saves: under the shipped MRU insertion rule
`topk_prefetch_k1` issues 219 prefetches of which 102 are later hit (465 per mille) and
`topk_prefetch_k8` issues 3,332 of which 1,590 are (477 per mille), and no `topk_prefetch` cell is
below `lru` at any budget. Roadmap section R3's other three policies — score-based, impact-driven
prefetch, CPU fallback — are deferred with named prerequisites (a router-weight column R2A does not
capture; R4.5's and R5's measured transfer costs; R5's microbenchmark) rather than simulated against
invented constants.

**Committed on the branch.** Nothing is uncommitted. After the rebase onto `4f01553` the branch is
`4951ff6` (design ledger), `424a516` (implementation), `a22f839` (review repair), `2e058f7` (final
review repair), and the reconciliation and baseline commits on top; before the two rebases the first
four were `198850b`, `ff4f76d`, `c7cfe1a`, and `967aadf`, and the review record on the pull request
names the pre-rebase heads the reviewers read. Two prerequisites the branch once carried are now in
`main` and are no longer part of this diff: the merged R2 wave's corrected `src/expert_trace.align`
and its four owners, without which every real OLMoE capture fails `R2_TOKEN_COUNT` on layer 15's
token-reduced `ffn_moe_topk`. **The `Makefile` changes** (`residency-sim-smoke`, a new
`HOSTED_CHECK_TARGETS` member, and `residency-sim-qualification`, in no aggregate), so the classifier
selects executable preflight and the baseline commit chain has to be re-recorded on this branch.

**Integration with PR #134 and PR #136.** C8-OPTIONAL-TARGETED-STAGE merged while this branch was
in publication, and GCC14-FP-CONTRACT-PORTABILITY (PR #136) merged after it — the ggml shim's
Clang-only `#pragma STDC FP_CONTRACT OFF` under GCC 14.2 and `-Werror`, a pre-existing hosted-check
failure this capability's own preflight surfaced; both are merged into this branch. PR #134 moved `.align-revision` from `4b515f8d` to **`3a34febe`** (Align PR #892, its own
Request 44). That renumbered this capability's two register entries — R3's requests are now
**Request 45** (the compiler soundness defect) and **Request 46** (the `borrow mut` array gaps) —
and it invalidated both the first preflight stamp and the first baseline chain, because
`.align-revision` is itself one of the twenty recorded baseline artifacts. Every owner below is
re-run against the managed `3a34febe` compiler; nothing in R3's own behaviour changed with the pin.

**Review envelope.** Two complementary reviewers covered explicitly disjoint risks at the pre-rebase
implementation head `ff4f76d` (`424a516` after the rebases): reviewer A the Align source and the
simulation semantics (1 blocker, 1 major, 4 minor, 1 observation), reviewer B the governance,
contract, and verification surface (1 high, 3 medium, 5 low). **All fourteen findings were accepted**,
none rejected, and all are repaired in one consolidated commit (`c7cfe1a`, `a22f839` after the
rebases), recorded as items 16 to 23 of the ledger's correction register. Two changed shipped
behaviour rather than prose: an `ExpertBlock` with `byte_size: 0` took `SIGABRT` through a
`resident_list` overrun and is now refused with `R3_EXPERT_BLOCK_SIZE`, and `best_policy` could name
a jackknife-**unstable** candidate beside `jackknife_stable: true` and now names the qualifying one.
Six hosted cases and five error-code cases were added, and the prefetch insertion rule is now
specified as MRU — which moved only the two `topk_prefetch` rows and changed no verdict, sweep row,
or non-prefetch policy on the fixtures or on the real corpus. The final review at `c7cfe1a` is
**approve** with five documentation-only findings, all repaired in `967aadf` (`2e058f7` after the
rebases); that repair is documentation-only apart from the smoke's new explicit-template B1
self-check, so no further comprehensive review is required. The reconciliation commits onto the
merged MoE prerequisites and onto PR #134 are documentation-only.

**Verification.** Durable owner evidence at the rebased head, on this macOS host with the recorded
Homebrew `LIBRARY_PATH` and the `CARGO` wrapper the managed `3a34febe` build needs
(`docs/align-development.md`):

```text
gmake check                    ok: checked 31 unit(s) per-unit
gmake build                    ok
gmake residency-sim-smoke      PASS x3, byte-identical - 2 model IRs, 23 traces, every policy at
                               every sweep budget in both orders against the independent Python
                               oracle, both CLI forms, the golden, determinism, the section 2.6
                               error corpus, and CLI arity/isolation
gmake expert-trace-smoke       PASS - 98 fixtures, 17 error codes
gmake model-ir-smoke           PASS - 49 qwen, 31 gpt-oss, 29 olmoe, 62 R0 fixtures re-run
gmake ggml-spike-smoke         PASS - 7 no-document, 43 documented cases; olmoe claim surface PASS
gmake alignpack-smoke          PASS - 27 positive fixtures, 128 negative sources, 20,300 assertions
gmake verify-loop-smoke        PASS - PR #134's schema-v2 owner, unchanged by this branch
gmake gate-topology-check      PASS
gmake format-check             PASS; gmake fmt leaves no diff; git diff --check clean
```

The focused qualification, on the host that holds the models (MEASURED, in no aggregate):

```text
gmake residency-sim-qualification  BEATS_BASELINE - the numbers above; 40 captures in 55.7-64.1 s
                                   across three post-repair runs, every transcript deleted after
                                   conversion
```

**Measurement.** This is a policy claim about the named MoE model and this corpus, not a platform or
throughput claim. It compares fetched bytes only; elapsed time is printed as a diagnostic. The stream
is prefill-only, replayed in decode order because decode is the regime being modelled and not because
decode was observed; the instrument prints six of eight router slots; the corpus is 40 independent
prompts of at most six tokens, so cross-prompt reuse carries most of the cache pressure. Read the
result as "across a session of many short requests, frequency-aware residency beats recency", not as
"within a generation, expert reuse is high".

**Baseline chain, re-recorded.** The `Makefile` change, plus PR #134's `.align-revision` move that
this branch adopts, invalidate the chain that shipped with C8-OPTIONAL-TARGETED-STAGE, so the
identity-bound chain is re-recorded on this branch as `ec5ca39` -> `e729b68` -> `4bf5976` (clean
source -> immutable oracle -> finalization), measured on Linux (aarch64, kernel 6.11.11-linuxkit,
Python 3.12.3) and checked there with `make baseline-check` ending `baseline chain: PASS`. Three of
the twenty recorded artifacts changed: `.align-revision` (`4b515f8d` -> `3a34febe`, PR #134's, adopted
unchanged), `Makefile`, and `src/main.align`, the latter two this capability's own. The other
seventeen hashes are unchanged and the twenty paths are identical. PR #135 merged with merge commit
`95c47e7`, preserving the recorded source, oracle, and finalization commits.

**Align capability requests.** Implementation added Requests 45 and 46 (filed as 44 and 45 before
PR #134 took 44), both `PROPOSED`, non-blocking, and shipped around with documented workarounds.
**Request 45 is priority high**: a compiler soundness defect, where the region checker accepts a move
of a Move-typed field out of a `json.decode`d record through a two-hop field-access chain with no
diagnostic and the built program corrupts the heap at run time on the decoded record's recursive
`Drop`; the shipped fix is one `.clone()`. Request 46 is two related array-shape gaps
(`borrow mut array<T>` loop invalidation, and no element assignment through an array field). R3 also
strengthened Requests 21, 23, and 26 with new client evidence.

## Merged checkpoint: MOE-PREREQ-DISCHARGE (2026-08-28)

Branch `agent/moe-prereq-discharge` merged as PR #133 at `35a0df6`, preserving its recorded
baseline chain with a merge commit. Design ledger `docs/specs/moe-prereq-discharge.md` remains
authoritative. Implementation, review, publication, and merge are complete.

**What it delivers.** The per-expert half of the R4 and R4.5 gates, measured on the real olmoe
model rather than on the synthetic corpus. Two verdicts stop being constants and become rules over
the block set the run measured:

- `scripts/run-alignpack-qualification` reports the container's `ExpertBlock` improvement —
  1,024 blocks, 3,072 -> 1,024 ranges, 165,368,823,808 -> 3,900,702,720 span bytes,
  42,394,624 -> 1,000,000 ppm, 0 -> 1,024 of 1,024 contiguous;
- `scripts/run-ggml-spike` selects both arms by `role_id` out of the pack document it just wrote
  and computes real expert claims: all three members of the first `ExpertBlock` and member 0 of the
  last (block 1,056, plane 63 of 64), every one `EXTERNAL`, `IDENTICAL`, and bit-identical to the
  same plane read from the original GGUF.

Admitting the claim form required `R4_5_EXTERNAL_BUFFER` `schema_version: 2`, the split of step 7
into 7a (the slice pair) and 7b (the shape by form), and the new `R4_5_SLICE` code — the shipped arm
had refused a real expert claim with `R4_5_SHAPE`, detail `n_dims[3]`, so R4.5's own claim that the
CLI already addressed an `ExpertBlock` with no new surface is refuted and removed. R4's expert
hotness ordering and prefetch groups, and R4.5's GPU expert arm and discrete-VRAM half, stay
deferred and are unchanged.

**Committed on the branch.** Nothing is uncommitted. After the rebase onto `e15e3d3` the branch is
`4656d88` (design ledger), `eed850e` (implementation), `4bf25b8` (review repair), `0dd4ea8` (the
developer guide, which still described both qualifications as they were before this capability
changed them), and the reconciliation and baseline commits on top; the first three were `49f8e4c`,
`ee041a7`, and `5015daf` before the rebase, and the review record below names the pre-rebase head it
read. **The `Makefile`
changes** — `ggml-spike-smoke` gains a `build` prerequisite, because its claim cells are taken from
a container `main --pack` wrote — so the classifier selects executable preflight and the baseline
commit chain has to be re-recorded on this branch.

**Review envelope.** One comprehensive reviewer covered the whole diff at the pre-rebase
implementation head `ee041a7` (`eed850e` after the rebase): verdict **approve**, eight findings —
four minor, two low, two nits. **All eight were accepted**, none rejected, and all are repaired in
one consolidated commit on top of it (`4bf25b8`). The repair is narrow — a reclaim pattern, a
detail token, two documentation corrections, one added qualification run with its digest, a report
count, one assertion strengthened from a prefix to exact lines, and named refusals in the selector —
so it does not trigger a second comprehensive review, and the reconciliation commit onto the merged
R1C is documentation-only.

**Verification.** Durable owner evidence at the rebased head, on this macOS host with the recorded
Homebrew `LIBRARY_PATH` (`docs/align-development.md`):

```text
gmake check                    ok: checked 30 unit(s) per-unit
gmake build                    ok
gmake ggml-spike               ok, stub shim and real shim
gmake ggml-spike-smoke         PASS - 7 no-document, 43 documented cases; olmoe 22 blocks /
                               69 members, 16 ExpertBlocks, n_expert 8, claim surface PASS
gmake alignpack-smoke          PASS - 27 positive fixtures, 128 negative sources, 20,298
                               assertions; qualification-verdict MoE PASS and dense N/A
gmake model-ir-smoke           PASS - 49 qwen, 31 gpt-oss, 29 olmoe, 62 R0 fixtures re-run
gmake expert-trace-smoke       PASS - 98 fixtures, 17 error codes
gmake layer-forward-smoke      PASS - 59 + 28 documented cases, three oracles
gmake gate-topology-check      PASS
gmake format-check             PASS; gmake fmt leaves no diff; git diff --check clean
```

Both focused qualifications, on the host that holds the models:

```text
gmake alignpack-qualification  PASS (olmoe) - identity, sequential read, and the MoE verdict above
gmake ggml-spike-qualification PASS (olmoe) - dense + three expert claims + the last plane;
                               1 dense, 3 expert, 1 last-plane digest checked
                               PASS (qwen2) - dense arm, expert arm N/A, 1 dense digest checked
```

**Consequence.** R3 residency simulation may now be reconciled onto the merged MoE result and
implemented after the bounded C8 re-entry. R2b's corpus-wide stratification consumes the merged
locality gate's corpus and aggregator.

**Measurement.** The layout numbers are a claim about this container on this named model, not a
platform or throughput claim; neither qualification asserts an elapsed bound.

**Baseline chain, re-recorded.** The `Makefile` change invalidates the chain that shipped with R5C,
so the identity-bound chain is re-recorded on this branch as
`157278c` -> `2dace6c` -> `b2267c7` (clean source -> immutable oracle -> finalization), measured on
Linux (aarch64, kernel 6.11.11-linuxkit, Python 3.12.3) and checked there with `make baseline-check`
ending `baseline chain: PASS`. Two of the twenty recorded artifacts changed against the R5C chain:
`Makefile`, and `src/main.align` — the latter from the merged R1C, which changed no `Makefile` and
so required no re-record of its own. The other eighteen hashes are unchanged and the twenty paths
are identical. PR #133 merged with merge commit `35a0df6`, so these commits remain reachable.

## Pending decisions (2026-08-28)

**Decision (a) taken 2026-08-28.** `OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf` (allenai;
4,213,512,192 B; sha256 `4ddc0e53159ed512b8dd67914a66e27bc618f694672ba43a9a0454eabd9c684f`; arch
`olmoe`; 16 layers, 64 experts, top-8 routing; types F32/Q4_K/Q6_K) is downloaded to the local
models directory (path withheld from this file by convention). Disk free is now ~16 GiB on this
host. **Decision (b) is now infeasible on this host**: `gpt-oss-20b-mxfp4.gguf` at 12.1 GB no
longer fits alongside the downloaded model and its alignpack space; R1B's real-model
`model-ir-parity` qualification stays open pending a host with more free disk. **Decision (c) is
now TAKEN and merged** as PR #140; decision (d) is unchanged and still pending.

1. **Small MoE GGUF, 1-4 GB. — TAKEN.** `OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf` (3.9 GiB) is on
   this host. It unblocked the R2 locality gate (merged, PR #131), R1C's `olmoe` frontend (merged,
   PR #132), and R4's per-expert half with R4.5's expert matmul (merged, PR #133). R3's residency
   simulation (merged, PR #135), its qualification-prerequisite follow-up (merged, PR #138), R5D's
   routed layer (merged, PR #139), and R5E's whole routed model, in publication above, follow from
   the same file rather than from another download, as does R2D's decode locality gate (merged,
   PR #141).
2. **`gpt-oss-20b-mxfp4.gguf`, 12.1 GB.** Unblocks R1B's real-model `model-ir-parity` qualification
   and every `ASSUMED` row of `docs/specs/r1b-gptoss-moe-ir.md` section 2.5 — including the two
   rows R1C has now contradicted from the olmoe side. **Infeasible on this host** after decision 1
   (disk free ~16 GiB); it stays open pending a host with more free disk.
3. **Build llama.cpp from source at `bb4caa754`** and apply the R2c minimal instrument patch (decode-
   step graphs, untruncated `ffn_moe_topk`). **TAKEN**, shipped and merged as PR #140,
   `docs/specs/r2c-decode-instrument.md`: `.llama-revision` and a 2,170-byte two-file patch pin the
   source, and the `r2c-v2` managed builder materializes the instrument into an identity-addressed
   cache outside Git. It unblocks R6 (Persistent KV) and, through it, R7-R9, and it is what extends
   the merged locality gate past prefill — R2D-DECODE-LOCALITY-GATE is doing exactly that now. The
   cost stands as recorded: a clone plus a cmake build, and a qualification reproducible only on
   hosts that repeat the build.
4. **Align Request 41** (non-`Copy` capture in `spawn` closures), Align-side. Unblocks R5's required
   microbenchmark C.

**Align capability requests.** Requests 1-20 CLOSED, Requests 21-43 and 45-48 PROPOSED and
non-blocking, and Request 44 ALIGN_LLM_VERIFIED, closed by PR #134. **Requests 47 and 48 are new,
filed by R5E-MOE-MODEL-PREFILL** (see above), drafted as 46 and 47 and renumbered at reconciliation
when R3's pair took 45 and 46; both probes re-measured unchanged at `3a34febe`. `.align-revision` now selects
`3a34febe`. Requests 45 and 46 are new, filed by R3-RESIDENCY-SIM (see above) and renumbered from
44 and 45 when PR #134 took 44; Request 45 is priority **high** — an accepted-but-unsound compiler
defect — rather than the medium/low of the rest of this range. **R5E added two requests and appended client evidence to two more**: Requests 45 and 46 each gain
R5E as a third client — `layer_olmoe.parse_geometry`'s decoded-record reads, reused unchanged, and
sixteen per-layer routing decisions that repeat R5D's two array-shape gaps once per layer. **R5D added no request and appended
client evidence to four**: Requests 45 and 46 gain `src/layer_olmoe.align`'s `parse_geometry` and its
routing decision (the two R5D could only anticipate before PR #135 merged them), Request 37 gains
R5D's per-unit check times — 15.6 s for the arm's own unit against 0.67 s for the 1,403-line module
beside it, which retires R5B's and R5C's under-10 s single-unit target rather than restating it — and
Request 42 gains the second exact repeat of one region diagnostic. Top clients by reference count in
`docs/align-requests.md` (grep-verified against the register): Request 34 (`Result` payloads beyond
scalars, 9 mentions), Requests 21 and 23 (read-only open; huge-struct-copy lint, 8 each — Request 23
gained R1C's `src/frontend_olmoe.align` and then R3's `residency_sim$Derived`, making six clients
across five wide records), and Requests 33 and 32 (aligned allocation; FFI by-value structs, 6 each);
Requests 32, 33, and 37 are also R5's own named clients.

**R2-LOCALITY-GATE merged checkpoint (PR #131, head `fff5806`, merge `546b5cc`).** The R2 gate is
**met in the prefill direction**. `scripts/run-expert-locality-gate` over
`eval/prompts/expert-locality-v1.txt` (40 prompts, all ≤ 6 tokens, md5
`d7fff23f5a1d4f6237e6f848f3318d8b`), one invocation per prompt, 51.8 s:

```text
verdict=LOCALITY prompts=40 layers=15 layers_clearing=15 pairs=2280 hits=3924 trials=13680
p0_per_mille=125 p_hat_per_mille=286 wilson_lo_per_mille=279 wilson_hi_per_mille=294 clusters=40
deff_per_mille=10460 cluster_lo_per_mille=262 cluster_hi_per_mille=311 ratio_per_mille=2288
entropy_per_mille=992 top8_mass_per_mille=180 truncated_documents=0 token_reduced_documents=40
token_reduced_layers=15
```

Adjacent-token expert reuse is 286 per mille against a 125 per mille null (`k/n` = 8/64), 2.29× the
null against a 1.5× materiality threshold, with all 15 contributing layers clearing the null on
their own stratum. The verdict is judged on the cluster-robust interval `[262, 311]` (design effect
10.460 over 40 prompt clusters), not the naive Wilson `[279, 294]`. The router histogram is nearly
uniform (entropy 992 per mille, all 64 experts used), so the effect is conditional structure rather
than popularity. Working sets grow sublinearly: 10.278 experts over two consecutive tokens where
independence predicts 11.437, 16.495 over four where it predicts 20.830. **Prefill only** — build
10566 evaluates one graph per invocation, `phase_split.decode` is `null`, and nothing there licenses
a decode or cache-policy claim. R2's contingency to shrink repo-expert-profile investment does
**not** fire; R3 has a measured demand signal. The same capability discharged R2A's `MOE-PREREQ`
cells (`expert trace parity (MoE): PASS` over 934 callback blocks) and added correction 20: build
10566 applies the output-token `GET_ROWS` reduction before the last layer's feed-forward, so a
*token-reduced* highest-index layer is parsed and validated but contributes no `selections[]` row
and is listed in the additive `moe.token_reduced_layers` field (`schema_version` stays 1). Full
numbers and every caveat: `docs/specs/r2a-expert-trace.md` section 8.

**R5C merged checkpoint.** Metal microbenchmark A, unified memory: self-reference `IDENTICAL` 479 of
479 nodes over 30 graphs; logits `WITHIN`, max `|Δ|` 2,936 of 6,000 ten-thousandths against R5B's
byte-identical CPU vector, `argmax` 671, top ten identical in order; bit-deterministic across paired
runs (`b6e473e8…` on both passes); transfer 59 wraps at ~12.4 ms each (732 ms total, both passes);
end-to-end wall ratio 0.99×/1.05×/1.31× across three paired runs, recorded **unresolved** rather than
claimed — the spread is `pread`'s. Correction C21 found and repaired a real cross-architecture NaN
sign-bit/payload difference (arm64's default NaN vs. x86-64 SSE's QNaN) surfacing only in the forced
non-finite-readback goldens, masked in golden normalization alone. Full ledger:
`docs/specs/r5c-metal-prefill.md`.

**Resume in another environment.** Fetch `origin`, check out `main`, then check out
`agent/r5e-moe-model-prefill` and read `docs/specs/r5e-moe-model-prefill.md` in full (and
`docs/specs/r5d-moe-layer-forward.md` for the layer half) before touching `src/layer_olmoe.align`,
`src/moe_model_forward.align`, or `scripts/run-moe-model-forward`. R5E's only remaining step is the
merge. After it merges, **no capability is active** here: R2D merged as PR #141 and R3-DECODE-RESIDENCY
as PR #142, and item 25 explicitly orders **R6 (Persistent KV)** ahead of a runtime
expert-residency policy. R6 is the next eligible roadmap work — decision (c)'s merged instrument
unblocks it, and its first task is naming the decode oracle. A separate worktree on
`agent/r6-decode-kv-step1` already exists in this session's scratchpad. R5's deferred microbenchmark
C stays blocked on Align Request 41. Decision 1 is taken; R2's
gate, R1C's frontend, R4's per-expert half, R4.5's expert matmul, C8's optional targeted stage, R3's
residency simulator, R2c's decode instrument, R5D's routed layer, R2D's decode locality gate, and R3's
decode residency gate are all merged, so R5E waits on no further decision. For the rest: decision 2 -> R1B's `model-ir-parity` qualification (section R1);
decision 3 is **taken and merged** as item 22, and its first consumer, item 24's decode locality
gate, is merged too, so R6 (section R6) and R7-R9 are unblocked; decision 4 -> R5's deferred
microbenchmark C (section R5).

**DinD preflight note.** The installed profile requires true Docker-in-Docker on macOS. The recipe
lives in this session's memory, not in the repository, and the scripts that ran it lived only in a
scratchpad and were never committed. Rebuild them from `docs/development-preflight.md` if that file
exists by the time work resumes; otherwise rebuild from the CLAUDE.md rules (the repository wrapper,
`scripts/pre-pr`, and the workflow classifier table) rather than relying on a cached copy.

## Merged checkpoints

Track B, dense local model (R0 → R5C), plus the merged R2 locality gate, the R1C olmoe frontend, the
MoE prerequisite discharge, the R3 residency simulator and its decode half, the R2c decode
instrument, R5D's routed layer, and R2D's decode locality gate; C8's optional targeted stage is the one merged Track A re-entry. The R3-DECODE-RESIDENCY, R2D, R5D, R2C,
R3-RESIDENCY-SIM, MOE-PREREQ-DISCHARGE, R2, and R5C checkpoints are above; the rest, newest first:

- **GCC14-FP-CONTRACT-PORTABILITY** (PR #136, merge `aad872f`): `#pragma STDC FP_CONTRACT OFF` is
  Clang-only, and GCC 14.2 diagnoses it as unknown while `scripts/build-ggml-shim` compiles with
  `-Werror`; the pragma is now guarded and the cross-compiler `-ffp-contract=off` flag plus the
  behavioural probe stay mandatory. It was discovered by **this capability's** publication preflight
  and merged as its prerequisite.
- **C8-OPTIONAL-TARGETED-STAGE** (PR #134, merge `4f01553`): authored and merged by a **parallel
  Codex session**, not by the session that produced the R3 and R5D capabilities above; it is recorded
  here because R3 and R5D both consume its pin move. The targeted verification stage becomes
  optional, `R2`-unrelated, on a fresh fixed-task baseline measuring a 326,093 ppm removable ceiling
  against C8's 2,000 ppm floor; the 101-pair acceptance improves 60,515,456 ns to 40,475,113 ns
  (331,160 ppm). It adopted Align `3a34febe` (Align PR #892) as `.align-revision` and closed
  Request 44 at `ALIGN_LLM_VERIFIED`. Ledger: `docs/specs/c8-optional-targeted-stage.md`.
- **R1C-OLMOE-MOE-IR** (PR #132, head `3580a62`, merge `e15e3d3`): `src/frontend_olmoe.align`, a
  three-way architecture dispatch, and two roles appended to the frozen `role_id` list
  (`attn_q_norm` 27, `attn_k_norm` 28). The real olmoe file reaches `R1_MODEL_IR` at the unchanged
  `schema_version: 2`, the size-sum oracle closes at
  `1,781,760 + 4,211,730,432 = 4,213,512,192`, and the Block IR reaches 1,058 blocks / 3,219 claims;
  `model-ir-parity` PASS against both real models, the first discharged against a real MoE model.
  It also contradicts two of R1B's `ASSUMED` rows — the stacked gate/up/down axis order and the
  required split expert biases — recorded as corrections in `docs/specs/r1b-gptoss-moe-ir.md`
  section 7. Ledger: `docs/specs/r1c-olmoe-moe-ir.md`.
- **R5B-MODEL-PREFILL-FORWARD** (PR #128, head `3470646`, merge `870bf31`): a whole 28-layer Qwen2
  CPU prefill computed over one Align-owned alignpack window, final logits byte-identical to
  `llama-debug --save-logits`. Ledger: `docs/specs/r5b-model-prefill-forward.md`.
- **R5A-DENSE-LAYER-FORWARD** (PR #127, head `0397228`, merge `ccbd8ae`): one Qwen2 dense layer
  computed by ggml over Align-owned weight windows, bit-exact self-reference oracle. Ledger:
  `docs/specs/r5a-dense-layer-forward.md`.
- **R4.5-EXTERNAL-BUFFER-SPIKE** (PR #126, head `d46fce6`, merge `fa567b1`): a ggml matmul over an
  Align-owned quantized DRAM buffer with no silent copy; dense-block gate achieved, expert-block half
  was `MOE-PREREQ`, now unblocked by decision (a) above. Ledger: `docs/specs/r4-5-external-buffer.md`.
- **R4-ALIGNPACK-LAYER-MAJOR** (PR #125, head `a7e72dc`, merge `991eab1`): the alignpack v1
  container, its layer-major layout, and its verifier. Ledger: `docs/specs/r4-alignpack-layer-major.md`.
- **R2A-EXPERT-TRACE-CAPTURE** (PR #124, head `ab5f7d8`, merge `b8e1cb6`): `--expert-trace` CLI
  producing an `R2_ACTIVATION_TRACE` document from a `llama-eval-callback` transcript. Ledger:
  `docs/specs/r2a-expert-trace.md`.
- **R1B-GPTOSS-MOE-IR** (PR #123, head `3bf5c9c`, merge `d8d4ef6`): gpt-oss MoE frontend and
  per-expert Block IR, `R1_MODEL_IR schema_version: 2`; the gpt-oss `model-ir-parity` qualification
  stays open — decision (b) above records it infeasible on this host. Ledger:
  `docs/specs/r1b-gptoss-moe-ir.md`.
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
