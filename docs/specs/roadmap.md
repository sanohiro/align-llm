# align 開発ロードマップ v2.0

## 1. 開発戦略

一人開発であるため、align-runtimeとalign-coderを同時に全面開発しない。

最初にalign-coderで最終価値を検証し、既存モデルを使ってコード生成・検証ループを成立させる。

align-runtimeは、重要な技術spikeと小さな実装を並行して進め、後からbackendとして統合する。

```text
優先順位:

1. コーディングタスクの評価基盤
2. repo解析と検証ループ
3. prompt/contextの局所改善
4. local runtimeへの置き換え
5. 巨大モデル最適化
```

## 2. Capability delivery model

Roadmap gates define acceptance, not pull request count. Deliver work as consumer-complete
capabilities. Ledger rows, closure-matrix cells, helper layers, and historical slice labels remain
useful for implementation and test ownership, but they are internal checkpoints unless they have an
independent consumer or a distinct operational failure domain. Do not reduce the product contract
to make a larger capability fit; combine the pieces needed to exercise it end to end.

The current forward delivery order is:

1. **FRESH-IMAGE — installable minimum-platform profile.** Image provisioning, keys, supervisor
   installation, cgroup delegation, and platform attestation are a separate operational failure
   domain and the trust root for capable worker evidence. FRESH-WORKER development may progress in
   parallel, but its capable acceptance and merge require this installed and attested profile.
2. **FRESH-WORKER — usable fresh-compiler repository worker.** Treat the merged Section 9 design,
   attestation wire, manifest wire, source-manifest wire, and source-identity work as foundations of
   one capability, not as a precedent for more helper-only pull requests. Combine private-root
   admission, source/cache materialization, compiler bundle, process ownership, cleanup, Make
   integration, and the core end-to-end functional smoke. Do not merge it with synthetic or direct
   host evidence while FRESH-IMAGE is unavailable.
3. **C6-LIFECYCLE — usable offline prompt lifecycle.** Complete the artifact, renderer, scorer,
   verifier, activation, persistence, and CLI path required to load, inspect, accept, and roll
   back a deterministic candidate. Existing C6a/C6b/C6c/C6d labels are acceptance and ownership
   cells inside this capability.
4. **C6-EVALUATION — deterministic end-to-end comparison.** Combine the trusted workspace/source
   boundary, paired evaluator, fixed adapter, result/evidence publication, and functional corpus so
   the lifecycle is exercised by a real contained task.
5. **C6-MEASURED — provider proposal and measured gate.** Add the bounded provider proposal, real
   consumer, checked-in measurement evidence, acceptance, and rollback proof. Performance and
   provider-quality checks run here because this capability makes those claims.
6. **C7-PERSISTED-RESULT — owned-result verification consumer.** After its platform and Align
   prerequisites are adopted, deliver records, codec, algorithm, CLI, persistence, and core
   functional verification as one vertical capability. Keep generated differential, mutation,
   fuzz, stress, and benchmark work in focused qualification commands unless a later core contract
   specifically requires it.
7. **C7-P — aarch64 platform profiles.** Deliver the two reviewed non-x86 C7 acceptance
   environments required by section 11 of `docs/specs/c7-persisted-result.md`: discharge the
   Section 9 reuse condition for `aarch64-unknown-linux-gnu`, and add the separate minimal
   `aarch64-apple-darwin` profile (Section 10 of `docs/specs/check-gate-topology.md`) whose trust
   content is digest attestation rather than kernel mediation. Both gates are named focused
   qualifications; neither joins an aggregate. It is listed after the consumer because the consumer
   defines the exact targets a profile must gate, and because the profiles gate *evidence*, not
   implementation.
8. **C8 — speed-first optimization. Closed.** Nine consumer-complete capabilities each preserved
   their correctness contract, named one changed path, and closed a paired fixed-task benchmark
   before claiming an improvement. The section C8 gate is met and `docs/specs/c8-speed-first.md` is
   authoritative for every baseline and measurement. Its retrospective promoted one reusable rule —
   the ppm-floor rule with a 2,000 ppm shipping floor — into section 1 of that document and one
   clause into the `CLAUDE.md` performance-claim row. A deferred C8 surface reopens only with a
   recorded cost ceiling above the floor or as a genuine Align capability request.
9. **R0-GGUF-INSPECT — read-only GGUF header, metadata, and tensor-table inspection. Gate met,
   closed.** The first Track B capability. It delivers one consumer-complete path: a caller names a
   `.gguf` path and receives one canonical `R0_GGUF_INSPECTION` document describing what the file
   declares about itself. It triggered the proportional design gate on a public CLI surface and a
   versioned exchanged document, so `docs/specs/r0-gguf-inspection.md` is the authoritative plan and
   owns the contract ledger, closure matrix, and fixture design. It makes no performance claim, so
   the C8 performance row does not apply to it. Merged as PR #121 (head `dcd8801`, merge
   `6640dcf`); the `scripts/run-gguf-reference-parity` qualification ran once against a real
   Qwen2.5-Coder-7B Q4_K_M model and passed: 29 metadata KV pairs, 339 tensors, `data_offset`
   5,953,536, `bytes_read` 6,291,456.
10. **R1-QWEN-MODEL-IR — Qwen2 Model IR and Block IR. Gate met, closed.** Turned one real
    Qwen2-architecture GGUF file into the Model IR and Block IR that `docs/specs/align-llm.md`
    section 5 places between the GGUF reader and the layout planner. `docs/specs/r1-qwen-model-ir.md`
    is the authoritative plan and owns the contract ledger, closure matrix, and fixture design.
    Merged as PR #122 (head `85a3a97`, merge `08492dc`); the `scripts/run-model-ir-parity`
    qualification ran once against a real Qwen2.5-Coder-7B Q4_K_M model and passed: 339 tensors over
    58 blocks, size-sum oracle `data_offset` 5,953,536 + `total_tensor_bytes` 4,677,120,000 =
    `computed_end` 4,683,073,536, matching `file_size`.
11. **R1B-GPTOSS-MOE-IR — gpt-oss MoE frontend and per-expert Block IR. Gate met, closed.** Merged
    as align-llm PR #123 (head `3bf5c9c`, merge `d8d4ef6`) onto `main` at `08492dc`. It discharged
    the MoE half of the R1 roadmap gate: a new architecture-neutral `src/model_ir.align` builder, a
    new `src/frontend_gpt_oss.align`, per-expert `ExpertBlock`/`RouterBlock` block kinds, and
    `R1_MODEL_IR` at `schema_version: 2`. `docs/specs/r1b-gptoss-moe-ir.md` is the authoritative plan
    and owns the contract ledger, closure matrix, and fixture design. **One qualification stays an
    open standing item**: the gpt-oss `model-ir-parity` qualification and real-model inspection
    against ledger section 2.5 remain the documented explicit `N/A` pending the user decision to
    download `gpt-oss-20b-mxfp4.gguf` (12.1 GB); the qwen half of the gate is real-model verified.
12. **R2A-EXPERT-TRACE-CAPTURE — expert-trace capture from a callback transcript. Merged as
    PR #124** (head `ab5f7d8`, merge `b8e1cb6`), from branch `agent/r2a-expert-trace`.
    `docs/specs/r2a-expert-trace.md` is the authoritative plan for R2a: `main --expert-trace
    CALLBACK_LOG [OUT.json]` consumes a `llama-eval-callback` transcript (recorded instrument
    build 10566) into an `R2_ACTIVATION_TRACE`, `schema_version: 1` document with per-(token,
    layer) expert ids and locality aggregates; a dense transcript yields `moe: false`. **The gate
    is met for parser correctness** on the dense case — `scripts/run-expert-trace-parity` PASS,
    `expert-trace-smoke` a hosted member — while **the R2 roadmap gate stays open** pending a real
    MoE transcript, a separate pending user decision (a small 1-4 GB MoE GGUF).
13. **R4-ALIGNPACK-LAYER-MAJOR — the alignpack v1 container, its layer-major writer, and its
    verifier. Active.** On branch `agent/r4-alignpack-layer-major`.
    [`r4-alignpack-layer-major.md`](r4-alignpack-layer-major.md) is the authoritative plan and owns
    the contract ledger, closure matrix, fixture design, correction ledger, and cell-to-case map.
    `main --pack MODEL OUT.alignpack [DOC.json]` writes a layer-major container whose every block is
    one contiguous range, and `main --pack-verify MODEL PACK [DOC.json]` re-reads both files and
    compares every claimed byte; both emit `schema_version: 1` documents
    (`R4_ALIGNPACK`, `R4_ALIGNPACK_VERIFY`). It consumes R1's Block IR through
    `model_ir.resolve_claims` and `model_ir.derive_status` and imports no frontend. **It discharges
    the R4 gate on the qwen half with real weights**: one qualification run over
    Qwen2.5-Coder-7B Q4_K_M reported byte identity and 89 → 58 ranges, 11,130,544,128 → 4,677,120,000
    span bytes, 2,379,786 → 1,000,000 ppm, and 27 → 58 of 58 contiguous blocks. The per-expert half
    is closed synthetically and stays **MOE-PREREQ**, pending the same small MoE GGUF decision R2
    names.

**I0 is substantively covered and is not scheduled as its own capability.** I0 asks that align-coder
prove its value on an existing model, and the merged C6-MEASURED wave (align-llm PR #103, `c9a510d`)
already did so end to end: `src/provider_llama.align` drives a real local provider, and the frozen
`eval/prompt/canonical-v1/` scope names `LOCAL_OPENAI` at
`http://127.0.0.1:18080/v1/chat/completions` with model `qwen2.5-coder-7b-instruct-q4_k_m` and a
recorded `provider_service_revision`. The measured run reported `IMPROVED` with
`gate_eligible: true`, zero serious regressions, and completion gain 2, against a parent-vs-parent
null replicate that flipped no cell. That evidence carries no paired timing, so I0's claim is the
completion-gain path only; the remaining I0 work is absorbed by later Track B integration rather
than by a separate align-coder capability.

**ALIGN-ADOPTION is an internal prerequisite checkpoint, not a standalone capability.** Within the
next consumer branch, batch its merged Align requests into one compiler-pin update, run every named
focused real-client acceptance target, and then run one final fresh `make ci`. Preserve each
request's lifecycle evidence without opening a pin-only pull request. As of R2A-EXPERT-TRACE-CAPTURE,
no Align request has merged since R0; `.align-revision` stays pinned to `4b515f8d` and there is
nothing to batch.

Only design the next eligible capability in implementation detail; later ledger entries may retain
their accepted contracts but must not generate speculative implementation pull requests. The
roughly eight-hour checkpoint and 24-hour substantial-progress expectations in `CLAUDE.md` are
diagnostics for workflow problems, not split thresholds or delivery quotas.

---

# Track A: align-coder

## C0: 固定評価セット

最初に、改善を測定できる環境を作る。

### 成果物

```text
eval/
  tasks/
  expected/
  runners/
  baselines/
```

### タスク例

```text
- 小さなbug fix
- 型エラー修正
- test failure修正
- 小規模feature
- refactor
- 性能改善
- 境界条件修正
```

### 比較対象

```text
- cloud coding model
- existing local model
- same model without align-coder
```

### Gate

同じタスクを繰り返し再現・採点できること。

---

## C1: Provider-independent Coding Loop

モデルbackendを抽象化する。

```text
ModelProvider:
  generate()
  stream()
  count_tokens()
  model_info()
```

初期対応。

```text
- cloud API
- llama.cpp互換server
- OpenAI互換local server
```

### Gate

同じcoding taskを複数providerで実行し、結果を共通形式で保存できること。

---

## C2: Repo Index MVP

最初から高度な独自静的解析器を作らない。

既存ツールを使って次を構築する。

```text
- files
- symbols
- imports
- definitions
- references
- related tests
```

### 初期対象言語

align自身で最も必要な1言語、または対象repoで最も頻度が高い1言語に絞る。

### Gate

変更対象symbolから、関連ファイルとテスト候補を取得できること。

---

## C3: Patch Evaluator

git diffを解析する。

```text
align-coder evaluate <patch>
```

出力。

```text
- touched files
- touched symbols
- risk score
- unrelated diff
- public API change
- complexity delta
- recommended tests
```

### Gate

固定評価タスクに対して、人間が危険と判断する差分を一定割合で検出できること。

---

## C4: Verification Loop

```text
generate
  ↓
evaluate
  ↓
build / test
  ↓
failure summary
  ↓
repair
```

### 初期機能

```text
- build command
- targeted test
- full test
- timeout
- structured error extraction
- repair prompt generation
```

### Gate

少なくとも一部の固定タスクで、初回失敗から自動修正してtest passまで到達すること。

---

## C5: Failure Memory

失敗と修正結果をrepo profileへ保存する。

```text
repo.alignprof:
  failed_attempts
  root_causes
  successful_repairs
  test_relationships
  risky_symbols
```

### Gate

過去と類似する失敗で、関連情報を次の修正promptへ再利用できること。

---

## C6: Prompt and Context Optimizer

LLMにprompt/context改善候補を提案させる。

ただし固定評価セットによるA/B評価を必須とする。

```text
align-coder prompt experiment
align-coder prompt evaluate
align-coder prompt accept
align-coder prompt rollback
```

### Gate

採用したprompt patchが、固定タスク全体で改善し、重大な回帰を起こさないこと。

---

## C7: Algorithm Verification

アルゴリズムや性能変更向け機能を追加する。

```text
- property-based testing
- fuzzing
- differential test
- invariant checks
- benchmark comparison
```

### First planned consumer slice: C7-PersistedResult

The first planned C7 consumer is the `C7-PersistedResult` slice: retain a declared verification
result after its input document and borrowed views have expired, then verify the persisted value
through the algorithm-testing gate. This is a named roadmap slice, not an implementation contract;
its own design must define the persisted artifact schema, validation boundary, and adoption test
before implementation starts. Align Request 9 is now `ALIGN_MERGED` at named commit
`2bb93a93a2f30da1daabd5b65d83863dab617560`, and the consumer design explicitly names the accepted
owned record shapes. Its managed pin and C7 adoption target remain a blocking prerequisite for the
consumer; C6 work remains independent.

### Platform profiles: C7-P

C7 evidence is target-bound, so each required non-x86 acceptance environment has its own reviewed
platform profile before it may provide that evidence: `aarch64-unknown-linux-gnu` reuses the
Section 9 fresh-compiler topology under that section's own stated condition, and
`aarch64-apple-darwin` has the separate minimal profile in Section 10 of
`docs/specs/check-gate-topology.md`, gated by `make darwin-profile-gate`. Both are named focused
qualifications run at a pin bump, a C7 owner-boundary change, or an explicit audit.

### Gate

意図的に入れた境界条件バグ、性能劣化、挙動差を検出できること。

---

## C8: Speed-first Optimization

評価対象を、モデル速度からタスク完了速度へ移す。

```text
- context縮小
- stable context reuse
- targeted tests（最初のcapabilityはtracked-file rankingを121走査から1走査へ変更）
- parallel checks
- small-model routing
- cached static analysis
```

性能主張と固定passing-patch benchmarkのrecordは
[`c8-speed-first.md`](c8-speed-first.md)をsource of truthとする。最初のcapabilityは公開selection
documentと検証順序を変えず、4種類のscore bucketを一度のtracked-file走査で構築する。次の
capabilityは同じ公開fieldを保ったまま、各testのbasename/directory signalをscore用とreason用に
二重計算せず一度だけ求める。第3capabilityは、全test candidateで不変なchanged pathのstemと
directoryをtracked-file loopの前に一度だけ求める。第4capabilityは正の関連候補がある場合に
score 0のgeneric候補をcontextから省き、正の候補がない場合だけgeneric全件をfallbackにする。
第5capabilityはその契約を保ちつつ、generic pathをGit listing内のoffsetとして一時保持し、fallback
が必要と確定した場合だけJSONへserializeする。第6capabilityは、関連候補がある通常経路ではその
offset保持も省き、正の候補がない場合だけ既に所有しているGit listingを再走査してgeneric fallbackを
構築する。第7capabilityは、候補・修正patchの事前checkと適用をGitの原子的な1 invocationにまとめ、
成功時の重複processとcheck専用stage recordを省く。第8capabilityは、各layerで完成したowned JSON
bufferを唯一のresult ownerへ移し、return直前の同一buffer再allocationを省く。第9capabilityは、
test selectionをrevision付きCLI entryとrevision不要なevaluation entryに分け、評価経路が消費しない
`git rev-parse --verify HEAD`のspawnを省いて`git ls-files -z`のみを実行する。CLI documentはbyte
単位で不変で、非repositoryは`git ls-files`が失敗するため引き続きfailするが、commitのないunborn
HEAD repositoryは評価経路で`ok`（candidate 0件、あるいはindexが持つ候補）を返すようになる。

### Gate

baselineと比べて、固定タスクの中央値でtime to passing patchが短縮すること。

**達成済み。C8は9個のcapabilityでcloseした。** 9個すべてが固定タスクのpaired benchmarkで
中央値の短縮を測定しており、最後の第9capabilityは10,793 ppm（1.08%）の短縮を記録した。個々の
baseline・測定値・host・binary digestは
[`c8-speed-first.md`](c8-speed-first.md)のsection 3〜11がsource of truthである。同じretrospective
で**ppm-floor rule**（cost ceilingを実装前にledgerへ記録し、shipping floorである2,000 ppmを
下回るseamは実装せずdeferred surfacesに記録する）をsection 1へ昇格させた。残るdeferred surface
は、floorを超えるcost ceilingを持つか、genuineなAlign capability requestになった場合にのみ
新しいcapabilityとして再開する。R0のgateは達成済みでcloseした。R1（Qwen2 Model IR）のgateも
達成済みでcloseし、R1B（gpt-oss/MoEフロントエンド）もPR #123としてmergeされ、R1のgateはgpt-oss側を
含めてcloseした（gpt-oss実モデルによるqualificationのみ、ユーザー判断待ちのopen項目として残る）。
次の実装対象はTrack BのR2a（expert trace）である。

---

# Track B: align-runtime

## R0: GGUF Inspection

```text
main --inspect-gguf MODEL.gguf
```

### 実装

```text
- GGUF header
- metadata
- tensor table
- offset
- dtype / quant type
- architecture判定
```

little-endian decode APIはすでにAlign標準ライブラリが提供している。pin
`4b515f8d`時点で`bytes`（`slice<u8>`）は`u8`/`i8`と`u16 i16 u32 i32 u64 i64 f32 f64`の
`_le`/`_be`形、計18個のscalar decoderを持つ（例: `bv.u32_le(off)`）。range外読み出しは
`slice[i]`と同じくabortするfail-closedなので、bounds checkはR0側の正しさの責務である。
したがってR0は新しいAlign surfaceを提案せず、compatibility layerも作らない。

R0のauthoritative planは[`r0-gguf-inspection.md`](r0-gguf-inspection.md)である。公開CLI
（`main --inspect-gguf`）と versioned exchanged document（`R0_GGUF_INSPECTION`,
`schema_version: 1`）を追加するため、`CLAUDE.md`のproportional design gateが発動する。契約・
validation順序・error code・closure matrix・fixture設計はすべてその文書が持つ。

実装中に見つかったAlignのgapは2件で、`docs/align-requests.md` Request 21
（read-only random-access file open）とRequest 22（Move要素配列のborrow indexing）として記録した。
Request 21: pin時点の唯一のrandom-access constructorは`fs.open_rw`で、書き込まないmodel fileに
`O_RDWR`を要求する。Request 22: `array<string>`やMove fieldを持つrecordの配列は`check_index`が
indexingを拒否するため、`src/gguf.align`はtensorの`absolute_offset`をNUL区切りのprefix streamと
並行する`array<i64>`として持つ。いずれもnon-blockingであり、R0は現行surfaceのまま進む。

### Gate

対象GGUFのmetadataとtensor一覧が既存toolと一致すること。この gateは
`scripts/run-gguf-reference-parity`（opt-in focused qualification、llama.cppの`llama-gguf`と比較）
が担い、model不要の`make gguf-smoke`が日常のownerとなる。

**達成済み。** 実モデル（Qwen2.5-Coder-7B Q4_K_M）に対する`scripts/run-gguf-reference-parity`は
PASSし、metadata KVペア29件、tensor 339件、`data_offset` 5,953,536、`bytes_read` 6,291,456を記録した。

---

## R1: Qwen / gpt-oss Frontend

```text
frontends/
  qwen/
  gpt_oss/
```

R1のauthoritative planは[`r1-qwen-model-ir.md`](r1-qwen-model-ir.md)である。Alignの1ファイル1
モジュールという慣習に沿い、上記`frontends/qwen/`が指すQwen2 frontendは`src/frontend_qwen.align`
としてflatな`src/`配下に実装する。tokenizer/vocabulary（`tokenizer.ggml.tokens`のようなMove要素
配列のindexingを要する、Request 22）はこのcapabilityから意図的に除外し、Request 22を
non-blockingのまま保つ。gpt-oss/MoE frontend（`ExpertBlock`/`RouterBlock`）は別capability
R1B-GPTOSS-MOE-IRとしてPR #123でmergeされた（[`r1b-gptoss-moe-ir.md`](r1b-gptoss-moe-ir.md)）。その
MoE frontendは`R1_MODEL_IR`を`schema_version: 2`へ引き上げ、block tensor recordへ
`claimed_absolute_offset`/`claimed_nbytes`の2フィールドを追加してper-expertのbyte claimを
表現する（同文書section 2.4）。`schema_version: 2`は既に出荷済みである。

### Gate

Model IRとBlock IRを生成できること。

**達成済み。** 実モデル（Qwen2.5-Coder-7B Q4_K_M）に対する
`scripts/run-model-ir-parity`はPASSし、`n_layer` 28、`n_embd` 3584、`n_head` 28、
`n_head_kv` 4、`head_dim` 128、`n_ff` 18944、`n_vocab` 152064、`n_expert` 0を記録した。
size-sum oracleは`data_offset` 5,953,536 + `total_tensor_bytes` 4,677,120,000 =
`computed_end` 4,683,073,536で`file_size`と一致し、339 tensorすべてが58 blockへ割り当てられた。
gpt-oss/MoEの半分（`n_expert > 0`、per-expert `ExpertBlock`）はR1B-GPTOSS-MOE-IR（PR #123）で
実装・mergeされ、合成corpusおよびsize-sum/claim-tiling oracle、MXFP4 library oracleで検証済み。
gpt-oss実モデルに対する`model-ir-parity` qualificationのみ、`gpt-oss-20b-mxfp4.gguf`（12.1 GB）の
ダウンロードに関するユーザー判断待ちのopen項目として残る。

---

## R2: Expert Trace

既存runtimeを測定器として利用する。測定器は`llama-eval-callback`（build 10566）である。

```text
R2a:
  callbackでrouter tensorを観測

R2b:
  callbackでtrace取得

R2c:
  不足時のみ最小patch
```

R2aのauthoritative planは[`r2a-expert-trace.md`](r2a-expert-trace.md)である。branch
`agent/r2a-expert-trace`でActive: `main --expert-trace CALLBACK_LOG [OUT.json]`が
`llama-eval-callback`のtranscriptを`R2_ACTIVATION_TRACE`（`schema_version: 1`）document
へ変換し、token・layerごとのexpert idとlocality aggregateを記録する。dense（非MoE）transcript
は`moe: false`を返す。

### 測定

```text
- token間expert reuse
- language別偏り
- task別偏り
- repo別偏り
- prefill/decode差
```

### Gate

条件付き局所性が存在するか、数値で判断できること。

局所性が弱ければ、repo expert profileへの投資を縮小する。

このgateは実際のMoE transcriptを必要とする。R2a実装が生成できるのはdense（`moe: false`）transcript
の`R2_ACTIVATION_TRACE`のみで、局所性の数値判断には小さなMoE GGUF（1-4 GB）が別途必要であり、
それを取得するかどうかはユーザー判断待ちである。取得されるまでgateはopenのままとなる。

---

## R3: Cache Simulator

```text
align-sim
```

比較policy。

```text
- LRU
- LFU
- recent reuse
- score-based
- top-k prefetch
- impact-driven prefetch
- CPU fallback
```

### Gate

対象ハードウェア条件で、baselineより有効なpolicyを特定できること。

---

## R4: alignpack v1

```text
align-pack model.gguf
```

基本layout。

```text
layer-major
  + layer-local block grouping
  + expert hotness
  + prefetch group
```

### Gate

元GGUFとのtensor内容一致と、連続read量の改善を確認できること。

このgateはR4-ALIGNPACK-LAYER-MAJORが所有する。実装・contract ledger・closure
matrix・fixture設計・correction ledgerはすべて
[`r4-alignpack-layer-major.md`](r4-alignpack-layer-major.md)にある。qwen側は実weightで達成済み
（89 → 58 range、2,379,786 → 1,000,000 ppm、27 → 58/58 contiguous、byte identity）。per-expert側は
合成fixtureのみで、実MoE GGUFが前提（**MOE-PREREQ**）。

---

## R4.5: External Buffer Spike

alignが所有するDRAM/VRAM buffer上の量子化weightを、ggml backendで計算できるか確認する。

### Gate

```text
- align owns buffer lifetime
- no silent copy
- quantized layout preserved
- one expert matmul succeeds
```

失敗時はruntime設計を見直す。

---

## R5: Minimal Runtime

```text
- alignpack loading
- DRAM → VRAM
- cache slot
- CPU fallback
- ggml computation
```

### 必須microbenchmark

```text
A: transfer + GPU compute
B: CPU compute
C: async prefetch + GPU compute
```

### Gate

単一block、単一layer、最小モデルの順に正しい出力を得ること。

---

## R6: Persistent KV

```text
- session KV
- repo stable prefix KV
- DRAM tier
- NVMe tier
- invalidation
```

### Gate

同一prefixを使う反復coding taskでTTFTが改善すること。

---

## R7: Codex / align-coder Integration

```text
align-coder
  ↓ ModelProvider
align-runtime
```

### Gate

既存providerからalign-runtimeへ差し替えても、同じ固定coding taskを実行できること。

---

## R8: Hybrid Expert Execution

```text
- score-based cache
- CPU/GPU decision
- impact-driven prefetch
- router lookahead
```

### Gate

llama.cpp等のlocal baselineに対して、対象ハードウェア上でtime to passing patchまたはdecode latencyが改善すること。

---

## R9: Speculative Execution

small coding modelをdraftとして利用する。

### 評価

```text
- acceptance rate
- task type
- language
- repo
- actual speedup
```

速くならない組み合わせは無効化する。

---

## R10: Large-model Pressure Test

初期目標ではない。

候補。

```text
- Qwen大型Coder MoE
- DeepSeek系巨大MoE
```

目的。

```text
- NVMe → DRAM → VRAM
- expert streaming
- physical layout
- persistent KV
- extreme memory pressure
```

### Gate

「起動できる」ではなく、coding taskで意味のある速度が得られること。

---

# Integration Track

## I0: Existing Model + align-coder

align-coderの価値を既存modelで証明する。

## I1: Local Model + align-coder

クラウド依存を減らし、local baselineを作る。

## I2: align-runtime + align-coder

KV、profile、cacheを共有する。

## I3: Self-optimizing Local Coding Loop

```text
generate
verify
repair
measure
update profile
propose prompt patch
evaluate
accept or rollback
```

この状態がalignの最初の完成形となる。

---

# 優先して作らないもの

```text
- 3つ以上のモデルfrontendを同時開発
- 多数言語の静的解析
- 独自IDE
- 汎用chat
- multimodal
- 全自動prompt変更
- 独自GPU kernel
- 1Tモデルを動かすだけのデモ
- Codex CLI全体の再実装
```

---

# 開発判断の停止条件

次の場合は設計を縮小・変更する。

```text
- repo別expert profileがlanguage/task profileを上回らない
- alignpackの物理配置が実測で改善しない
- CPU/GPU hybridが既存runtimeを上回らない
- prompt自己改善が固定評価セットで回帰を起こす
- 巨大モデルが遅すぎてcoding loopに使えない
- 対応モデル追加が本質的検証を遅らせる
```

---

# 最初の実装順

```text
1. 固定coding評価タスクを作る
2. ModelProvider abstractionを作る
3. Patch Evaluatorを作る
4. build/test/repair loopを作る
5. Repo Indexを追加する
6. Failure Memoryを追加する
7. Prompt OptimizerのA/B評価を作る
8. 並行してalign-inspectを実装する
9. expert traceとcache simulatorを実行する
10. align-runtimeをproviderとして統合する
```

この順番なら、align-runtimeが完成する前から、align-coderの価値と局所最適化の仮説を検証できる。
