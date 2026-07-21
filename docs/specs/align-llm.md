# align プロジェクト統合仕様書 v2.0

## 1. プロジェクトの目的

alignは、クラウドAIの劣化コピーを高価なローカル環境に再現するプロジェクトではない。

目的は、一般的なCPU、consumer GPU、大容量DRAM、NVMeを最大限に使い、**特定のコードベースに対する生成・検証・修正・最適化を高速に反復することで、クラウドcoding agentに限りなく近い、または局所的には上回る実用性を得ること**である。

alignが重視するのは、モデル単体の総合知能ではない。

```text
実用的なコーディング能力
  =
モデルの能力
× 反復速度
× 検証精度
× repo固有知識
× 継続的な局所最適化
```

クラウドは広く強い。

alignは、次の条件に極端に最適化する。

```text
- 特定repo
- 特定言語
- 特定ビルド環境
- 特定テスト環境
- 特定ハードウェア
- 特定ユーザー
- 繰り返される修正パターン
```

alignの勝ち筋は、汎用知能ではなく、**局所性・速度・検証・記憶・反復**である。

---

## 2. プロジェクト構成

alignは、役割の異なる2つの主要コンポーネントに分ける。

```text
align-runtime
  ローカルLLM実行基盤

align-coder
  コード生成・検証・局所最適化基盤
```

両者は連携するが、独立して開発・評価できるようにする。

### 2.1 全体構成

```text
User / Codex CLI
        ↓
align-coder
        ↓
Model Provider Interface
        ├─ align-runtime
        ├─ llama.cpp / 既存local server
        └─ cloud API
```

align-coderは、align-runtimeの完成を待たずに開発できる。

初期は既存ローカルモデルやクラウドモデルを利用し、コード検証・局所学習部分を先に育てる。align-runtimeが実用段階に達したら、推論backendを差し替える。

---

# Part I: align-runtime

## 3. align-runtimeの目的

align-runtimeは、open-weightモデルを限られたローカルハードウェアで効率よく実行するための基盤である。

主な責務は次。

```text
- GGUFモデルの読み込み
- モデル構造のBlock IR化
- alignpackへの再配置
- VRAM / DRAM / NVMe階層管理
- KV cache管理
- MoE expert cache
- CPU/GPU hybrid execution
- prefetchとoffload
- profile収集
- Codex互換APIへの推論提供
```

align-runtime単体は、repoの編集、テスト実行、修正判断などのagent機能を所有しない。

```text
Codex / align-coder owns the coding workflow.
align-runtime owns local model execution.
```

---

## 4. Runtimeの基本原則

### 4.1 モデルは作らない

alignは、独自基盤モデルの学習を目的としない。

既存のopen-weightモデルを利用し、モデルの配置・実行・キャッシュ・再利用を最適化する。

### 4.2 入力形式はGGUFを基本とする

```text
model.gguf
  ↓
align-pack
  ↓
model.alignpack
model.alignidx
model.alignprof
  ↓
align-runtime
```

モデル変換、量子化、配布形式の全てを自作しない。

### 4.3 初期モデル対象を絞る

```text
Core implementation targets:
  - Qwen
  - gpt-oss
```

コーディング用途ではQwen Coder系を主要評価対象とする。

将来候補は、実装対象ではなく圧力試験として扱う。

```text
Future pressure targets:
  - Qwen大型Coder MoE
  - DeepSeek系巨大MoE

Lightweight baseline:
  - Gemma系
```

対応モデル数でllama.cppと競争しない。

一人開発では、対象を増やすほどモデルごとの差異の検証が薄くなるため、少数のモデルを深く扱う。

### 4.4 独自kernelは後回し

初期はggml、llama.cpp、CUDAライブラリなどの既存計算kernelを利用する。

alignが所有するのは、主に次。

```text
- memory placement
- cache policy
- prefetch policy
- profile
- physical layout
- execution scheduling
```

---

## 5. Runtime内部構造

```text
GGUF Reader
  ↓
Model Frontend
  ↓
Model IR
  ↓
Block IR
  ↓
Layout Plan
  ↓
alignpack
  ↓
Runtime Scheduler
```

### 5.1 Model Frontend

モデル固有処理はfrontend内に閉じ込める。

```text
frontends/
  qwen/
  gpt_oss/
```

runtime本体にモデル固有の条件分岐を増やさない。

### 5.2 Block IR

実行・配置・退避・先読み可能な単位をBlockとして扱う。

```text
BlockKind:
  WeightBlock
  ExpertBlock
  AttentionBlock
  RouterBlock
  MlpBlock
  KVBlock
  DequantBlock
```

初期はlayerおよびexpert単位を中心とし、将来的にsub-blockやneuron cluster単位を検討する。

---

## 6. 階層メモリ

### VRAM

```text
- active weight
- hot expert
- router / norm
- active KV
- GPU workspace
- prefetch staging
```

### DRAM

```text
- model weight store
- warm expert
- pinned staging buffer
- reusable KV
- CPU execution weight
- profile
```

### NVMe

```text
- cold expert
- DRAMを超えるweight
- persistent KV
- alignpack
- profile database
```

NVMeは細かいrandom readに使用しない。

alignpackでblockを連続配置し、大きなchunkとして読み込む。

---

## 7. Runtime最適化

### 7.1 prefillとdecodeを分離する

```text
prefill:
  bandwidth
  sequential layout
  prefix KV reuse
  TTFT

decode:
  latency
  expert cache
  token間reuse
  prefetch
```

### 7.2 Persistent Prefix KV

同一token列の最長共通prefixのみを安全に再利用する。

```text
KVCacheKey:
  model_id
  model_arch
  quant_type
  tokenizer_id
  prompt_template_version
  prefix_token_hash
  prefix_detector_version
```

### 7.3 CPU/GPU hybrid scheduling

VRAM miss時に必ずGPUへ転送するとは限らない。

```text
if block in VRAM:
  GPU compute

elif transfer + GPU compute is cheaper:
  DRAM → VRAM
  GPU compute

else:
  CPU compute
```

判断は実測microbenchmarkに基づく。

### 7.4 Score-based cache

LRUだけに依存しない。

cache scoreには次を利用する。

```text
- recent activation
- frequency
- router score
- miss penalty
- transfer cost
- layer position
- task profile
- language profile
- repo profile
```

### 7.5 Impact-driven prefetch

「次に使われそうか」だけでなく、missした際の損失が大きいblockを優先する。

### 7.6 Speculative decoding

初期対象外だが、offload環境の重要な将来機能とする。

```text
small draft model
  ↓ multiple token candidates
large target model
  ↓ verify
```

repo・言語・taskごとのacceptance rateをprofileし、速くなる場合のみ使用する。

---

## 8. Runtimeの非目標

```text
- 全モデル対応
- 独自基盤モデルの学習
- 初期段階での独自CUDA kernel
- 汎用chat UI
- multimodal
- agent loopの所有
- 巨大モデルが動くことだけを成果とすること
- 毎token全layerをdiskから読む単純layer streamingを最終方式とすること
```

「405Bが8GBで起動した」ことより、実用速度とtime to passing patchへの貢献を重視する。

---

# Part II: align-coder

## 9. align-coderの目的

align-coderは、特定repoに対するコード生成・検証・修正・最適化を高速に反復するためのシステムである。

モデルの出力を信用するのではなく、ローカル環境で検証し続ける。

```text
generate patch
  ↓
static analysis
  ↓
build / type check
  ↓
test
  ↓
property / fuzz / differential check
  ↓
benchmark
  ↓
patch evaluation
  ↓
repair
  ↓
profile / prompt update
  ↓
repeat
```

align-coderは、モデル単体の知能不足を検証と反復で補う。

---

## 10. align-coder内部構造

```text
Repo Index
Static Analysis Adapters
Context Builder
Patch Evaluator
Test Selector
Build/Test Runner
Algorithm Verifier
Benchmark Runner
Failure Memory
Prompt Optimizer
Evaluation Gate
Model Provider Interface
```

### 10.1 Repo Index

保持する情報。

```text
- file graph
- symbol index
- import graph
- call graph
- type graph
- public API
- related tests
- frequently co-changed files
```

初期から独自parserを全言語向けに作らない。

既存のcompiler、language server、静的解析ツール、tree-sitterなどをadapter経由で利用する。

### 10.2 Patch Evaluator

生成されたdiffを評価する。

```text
- changed files
- changed symbols
- diff size
- unrelated changes
- API compatibility
- complexity change
- risky file access
- test coverage
- performance risk
```

### 10.3 Test Selector

変更symbolとdependency graphから、実行すべきテストを優先順位付きで選択する。

全テストを毎回実行するのではなく、高速な局所ループを作る。

最終gateでは必要に応じて全テストを実行する。

### 10.4 Algorithm Verifier

アルゴリズム変更では次を利用する。

```text
- property-based testing
- fuzzing
- differential testing
- invariant checking
- overflow / boundary check
- complexity regression check
- benchmark comparison
```

### 10.5 Failure Memory

失敗をそのまま大量保存するのではなく、再利用可能な形へ圧縮する。

```text
- task
- attempted patch
- failed test
- root cause
- relevant symbols
- repair result
- successful strategy
- unsuccessful strategy
```

---

## 11. Repo-local Learning

align-coderは、repoごとに局所的に強くなる。

```text
repo.alignprof
  runtime:
    stable_prefix
    kv_profile
    expert_profile

  coder:
    symbol_graph
    test_graph
    risky_files
    successful_patches
    failed_patches
    failure_patterns
    performance_baselines
    prompt_versions
    context_selection_history
    model_task_scores
```

学習対象はモデルweightではなく、まず次を優先する。

```text
- context selection
- prompt
- test selection
- repair strategy
- model selection
- cache policy
- benchmark policy
```

---

## 12. Prompt Optimizer

LLM自身がpromptの改善案を提案できる。

ただし、無条件に自己変更させない。

### 12.1 Promptの階層

```text
Base Prompt:
  人間が管理する固定原則

Repo Prompt:
  repo固有ルール

Task Prompt:
  今回の作業内容

Learned Prompt Patch:
  LLMが提案した改善候補
```

### 12.2 更新手順

```text
failure or opportunity
  ↓
LLM proposes prompt patch
  ↓
fixed evaluation tasks
  ↓
before / after comparison
  ↓
accept / reject / experimental
```

評価を通過したpromptだけを採用する。

全変更はversion管理し、rollback可能にする。

### 12.3 Prompt評価指標

```text
- task completion rate
- test pass rate
- repair loop count
- unrelated diff count
- patch size
- benchmark regression
- time to passing patch
```

---

## 13. Model Selection

全タスクを同じモデルに処理させない。

```text
small / fast model:
  - repo検索
  - error分類
  - test選択
  - patch review
  - prompt patch提案

large model:
  - 難しい実装
  - algorithm design
  - complex repair
  - final verification
```

将来的には、task type、過去成功率、速度、必要context、hardware stateからmodelを自動選択する。

---

## 14. 最重要評価指標

alignの主指標はtokens/secではない。

### Primary Metrics

```text
- time to passing patch
- task completion rate
- build success rate
- test pass rate
- repair loop count
- unrelated diff count
- performance regression rate
- cost per completed task
```

### Secondary Runtime Metrics

```text
- TTFT
- tokens/sec
- KV hit rate
- expert cache hit rate
- PCIe transfer
- NVMe read
- CPU fallback rate
```

### Learning Metrics

```text
- prompt patch acceptance rate
- context selection improvement
- repeated-task speedup
- repo-specific success improvement
- regression rate after self-optimization
```

---

## 15. align-coderの非目標

```text
- 汎用チャット
- 一般質問への回答
- 画像生成
- あらゆる言語への同時対応
- 独自compiler/static analyzerの全面実装
- 評価なしのprompt自己改変
- 人間の承認なしで危険な変更を本番へ反映すること
- Codex CLIのUIや全agent機能を最初から再実装すること
```

---

## 16. プロジェクト原則

### 原則1

```text
「巨大モデルが動く」より
「修正が通る」を優先する。
```

### 原則2

```text
一発の賢さより
高速な検証と反復を優先する。
```

### 原則3

```text
汎用性より
特定repoでの深い局所最適化を優先する。
```

### 原則4

```text
自己改善は
必ず評価とrollbackを伴う。
```

### 原則5

```text
対応範囲を増やすより
少数対象で効果を証明する。
```

### 原則6

```text
高額GPUでクラウドの劣化コピーを作らない。
普通のローカル資源を賢く使い切る。
```

---

## 17. 最終像

```text
Local repository
  ↓
align-coder observes and indexes
  ↓
LLM generates a small patch
  ↓
align-coder verifies and measures
  ↓
failure and success become repo knowledge
  ↓
prompt / context / tests / model policy improve
  ↓
align-runtime executes increasingly efficiently
  ↓
time to passing patch continues to fall
```

alignの最終目的は、単にローカルLLMを動かすことではない。

**特定のコードベースを見続け、検証し続け、局所的に改善し続ける、速度重視のローカルcoding systemを作ることである。**
