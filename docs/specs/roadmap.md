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

### Gate

意図的に入れた境界条件バグ、性能劣化、挙動差を検出できること。

---

## C8: Speed-first Optimization

評価対象を、モデル速度からタスク完了速度へ移す。

```text
- context縮小
- stable context reuse
- targeted tests
- parallel checks
- small-model routing
- cached static analysis
```

### Gate

baselineと比べて、固定タスクの中央値でtime to passing patchが短縮すること。

---

# Track B: align-runtime

## R0: GGUF Inspection

```text
align-inspect model.gguf
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

同時にalign標準ライブラリへlittle-endian decode APIを追加する。

### Gate

対象GGUFのmetadataとtensor一覧が既存toolと一致すること。

---

## R1: Qwen / gpt-oss Frontend

```text
frontends/
  qwen/
  gpt_oss/
```

### Gate

Model IRとBlock IRを生成できること。

---

## R2: Expert Trace

既存runtimeを測定器として利用する。

```text
R2a:
  callbackでrouter tensorを観測

R2b:
  callbackでtrace取得

R2c:
  不足時のみ最小patch
```

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
