# R6-PREFIX-TTFT: long-prefix capacity, pinned corpus, and the R6 TTFT gate

Status: **design, written before implementation**. Branch `agent/r6-prefix-ttft`, based on
`main` merge commit `c16f14ea5ec2e42d61f7e6644716854d9ca61c2c`. Section 11 of
[`r6-prefix-key-corpus.md`](r6-prefix-key-corpus.md) is the charter; this document settles the
choices that charter deliberately left to its successor.

Sections 1 through 6 are committed before the first production-source change. Later measurements
and implementation deviations are appended rather than rewriting the pre-implementation ceiling,
floor, verdict, or closure cells.

## 1. Decision and boundary

### 1.1 Consumer-complete capability

`R6-PREFIX-KEY` shipped a content-addressed KV store, but `MAX_PREFILL_TOKENS = 32` prevents the
store from serving a real repository prompt. This capability makes that consumer usable end to end:

1. lift the dense and routed prefill caps from 32 to 2,048;
2. pin the token ids of the shared repository prefix and three independent coding-task suffixes;
3. run paired single-shot and keyed-hit TTFT measurements on those checked-in ids; and
4. decide both the roadmap improvement gate and the 150,000 ppm shipping floor by the rule already
   committed in `r6-prefix-key-corpus.md` section 11.2.

The implementation does not add a new inference operation. It enlarges an existing accepted input
domain and gives the existing store its first real workload consumer.

### 1.2 Design-gate triggers

Three triggers fire.

| Trigger | Fired | Reason |
| --- | --- | --- |
| Public CLI or API | **No** | `--decode-step` keeps the schema-6 arm and its sixteen operands. Existing operands accept longer token lists, but no position, default, result field, or error code changes |
| Persisted or exchanged format | **Yes** | `akvp` v1's `token_count` field may now contain 33..2,048. The byte layout and all three version fields stay unchanged, but a container in that range is deliberately unreadable by the older 32-token reader |
| Ownership / allocation boundary | **Yes** | The resident embedding staging reservation grows from 458,752 B to 29,360,128 B for Qwen and from 262,144 B to 16,777,216 B for OLMoE. The owner and lifetime stay run-scoped |
| Coordinated invariant across at least three modules | **Yes** | Two declarations, four Align consumers, the persisted-plane reader, and two runners must agree on 2,048 and on the 2,049 refusal boundary |

### 1.3 Scope and non-goals

**In scope:** CPU dense Qwen2.5-Coder-7B Q4_K_M for the measured gate; the OLMoE cap lift and its
synthetic owner coverage; `MAX_PREFILL_TOKENS = 2,048`; `KV_WIDTH = 1,536` for the corpus; resident
weights on both measured legs; `STEPS = 1`; warm and eviction-pressure cache protocols; three
suffix clusters and five paired repeats per protocol.

**Out of scope:** a new tokenizer or detokenizer; text generation; a new container format; a schema
bump; longest-common-prefix lookup; KV eviction or garbage collection; appending to a container;
Metal; GPU residency; a Linux or fanned-host performance claim; changing the six-token transcript
oracle; and an `align-coder` text consumer, which remains R7. The corpus has three independent
suffix clusters: section 3.4 records why the landed `canonical-v1e` freeze does not add three.

## 2. Baseline probe and performance contract

### 2.1 Probe method

The charter requires the first implementation action to be a probe rather than production code.
That ordering was observed. At unchanged `main`, a throwaway measurement build changed only
`layer_qwen2.MAX_PREFILL_TOKENS` from 32 to 2,048, built `ggml-spike`, measured three runs, and then
restored the source byte-for-byte. The worktree was clean after the probe.

The probe used:

| Input | Value |
| --- | --- |
| Host | Apple M1, 16 GiB, Darwin arm64 |
| Model | `qwen2.5-coder-7b-instruct-q4_k_m.gguf`, 4,683,073,536 B, SHA-256 `509287f78cb4d4cf6b3843734733b914b2c158e43e22a7f4bf5e963800894d3c` |
| Pack source header | 5,953,536 B, SHA-256 `df727e6ef8f16650aacabfa673463efc22a51e5d552c64c5ed23bfe516e1a0ba` |
| llama.cpp revision | `bb4caa7540188872173c44d161602d9271386413`, `llama-debug` build 10566 |
| Prompt shape | 1,200 repetitions of valid Qwen token id 1. Shape probe only; it is not corpus evidence |
| Arm | `--decode-step`, `KV_WIDTH=1536`, `STEPS=1`, no transcript, no logits, no save/load/store, `RESIDENT=weights` |
| Command shape | `ggml-spike --decode-step PACK GEOMETRY TOKENS DOCUMENT MODEL - 1536 - 1 - - weights - -` |

The repeated id deliberately removes corpus provenance from the feasibility question. Prefill graph
shape and compute are functions of the 1,200-column dimensions; the pinned corpus remains the only
input to the gate.

### 2.2 Probe result

All times are read from the arm's document except `wall`, which is `/usr/bin/time -p` around the
process.

| Repeat | `first_token_ns` | `timings.compute_ns` | Compute share | Resident fill | Wall |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 131,686,130,625 | 125,288,369,961 | 0.951417 | 2,172,659,291 | 132.48 s |
| 2 | 126,694,053,500 | 121,070,543,999 | 0.955613 | 1,683,247,250 | 126.79 s |
| 3 | 129,543,415,375 | 123,871,843,208 | 0.956219 | 1,557,188,750 | 129.63 s |
| **Mean** | **129,307,866,500** | **123,410,252,389** | **0.954416** | **1,804,365,097** | **129.63 s** |

The first-token range is 38,606 ppm of the mean and the compute range is 34,177 ppm. The compressor
record moved by 165,419 / 6,932 / 20,556 stored pages and 62,877 / 5,170 / 6,827 occupied pages;
swapouts moved by zero on all three runs. These runs are retained as observed, not discarded or
retaken.

The precondition is met by a wide margin: compute is 95.44% of first-token time, above the 49.0%
mean-prefix and 57.5% worst-prefix requirements. The observed throughput is 9.7 prompt tokens/s,
well below the roughly 200 tokens/s failure boundary from the charter.

### 2.3 Ceiling, floor, and verdict

The floor remains **150,000 ppm**. The probe's 38,606 ppm full first-token range is 25.7% of that
floor and supplies no measured reason to replace it.

Before subtracting the container read, the probe fixes the ceiling at:

| Prefix share | Share | Raw ceiling |
| --- | ---: | ---: |
| Mean of the original three tasks | 0.30582 | **291,880 ppm** |
| Worst original task | 0.26075 | **248,864 ppm** |

The read term is not guessed. At the 129.31 s probe mean, the read could cost 18.35 s at the mean
share or 12.78 s at the worst share before the corresponding ceiling reaches the floor. The actual
168 MiB read is measured as part of the keyed hit and is also reported separately.

The pre-committed verdict from the charter is unchanged:

| Verdict | Rule |
| --- | --- |
| **MET** | Leave-one-suffix-out jackknife minimum paired reduction is greater than zero under both protocols, and the worse protocol's minimum is at least 150,000 ppm |
| **NOT_MET** | The jackknife maximum is below 150,000 ppm under either protocol |
| **INDETERMINATE** | Every other result, including a reduction separated from zero that straddles the floor |

The roadmap improvement gate and the shipping floor are reported separately. A positive interval
below 150,000 ppm improves TTFT but does not ship the performance claim.

### 2.4 Miss cost decision

The gate measures the **keyed hit**, because repeated tasks are the consumer and section 11.2 fixed
the two paired legs before this design. A miss is not put into that pair: doing so would compare one
single-shot prefill against a prefill plus a container write and answer a different question.

Miss cost is nevertheless a required secondary result. Once per `(suffix, protocol)` before the
five hit pairs, the runner records miss `first_token_ns`, write elapsed time, and container bytes.
It reports the observed break-even reuse count
`ceil((miss - single_shot) / (single_shot - hit))`, or `N/A` when the denominator is not positive.
No miss is silently amortized into the hit claim.

## 3. Public-contract ledger

### 3.1 Constants and accepted domain

| Surface | Pre-change | Shipped contract | Owner |
| --- | ---: | ---: | --- |
| `layer_qwen2.MAX_PREFILL_TOKENS` | 32 | **2,048** | `src/layer_qwen2.align` |
| `layer_olmoe.MAX_PREFILL_TOKENS` | 32 | **2,048** | `src/layer_olmoe.align` |
| Dense and routed layer prefill guards | counts 1..32 | counts **1..2,048**; 2,049 refuses with the existing token error | `src/layer_forward.align`, `src/moe_layer_forward.align` |
| Dense model prefill | counts 1..32 | counts **1..2,048**; the six-token transcript rule is unchanged | `src/model_forward.align` |
| Decode prefix plus suffix | sequence at most 32 | sequence at most **2,048**; 2,049 is existing `R6_SUFFIX sequence[2049]` | `src/decode_step.align` |
| Persisted `token_count` | 1..32 | **1..2,048** | `src/kv_plane.align`, `scripts/kv_plane_reader.py` |
| Token stream region | 4..128 B | **4..8,192 B** | `src/kv_plane.align` |

`MAX_ATTENTION_WIDTH = 4,096`, `MAX_DECODE_STEPS = 64`, and
`MAX_KV_PLANE_BYTES = 536,870,912` are unchanged.

### 3.2 Allocation and ownership

`model_forward.plan_resident` continues to reserve the maximum stage independently of the current
prompt, so one pack has one resident layout at every prompt length.

| Model | Row bytes | 32-token stage | 2,048-token stage | Resident arena consequence |
| --- | ---: | ---: | ---: | ---: |
| Qwen2.5-Coder-7B | 14,336 | 458,752 B | **29,360,128 B** | probe observed **4,681,596,928 B** total |
| OLMoE-1B-7B | 8,192 | 262,144 B | **16,777,216 B** | dense-resident arena grows by 16,515,072 B |

The same run-scope `buffer` owns the stage and the same one wrap covers it. No allocation is added
per layer, per token, or per decode step. Existing `R6_RESIDENT_BUDGET` and degraded-reservation
refusals remain the failure channels.

### 3.3 Persisted compatibility and versions

`akvp` remains format version 1, plane layout version 1, and document schema version 3. The
`R6_DECODE_STEP` document remains schema 6. No byte offset, alignment, digest preimage, key version,
or naming rule changes.

Compatibility is deliberately one-way:

- every old container with `token_count <= 32` remains readable and has the same store key;
- a new container with `token_count` 33..2,048 is readable by the new build;
- the older build refuses it at `R6_KV_HEADER token_count` before using its regions; and
- 2,049 is refused by both the arm and independent reader.

This is a reader-policy expansion over a self-describing field, not a format reinterpretation, so a
format or schema bump would falsely say the bytes changed.

### 3.4 Corpus format

The checked-in corpus is `eval/kv/prefix-corpus-v1/`:

```text
manifest.json
shared-prefix.ids
duration-half-away-from-zero.initial.suffix.ids
layer-precedence-frozen-module.initial.suffix.ids
record-codec-round-trip.initial.suffix.ids
```

`manifest.json` is `KV_PREFIX_CORPUS`, schema 1. It carries:

- `corpus_id: "prefix-corpus-v1"` and `kv_width: 1536`;
- the model size and SHA-256, `.llama-revision`, `llama-debug --version`, and pack source-header
  size and SHA-256 from section 2.1;
- the exact environment-variable command form used to generate the token binaries;
- for every id file: repository-relative path, id count, SHA-256 of the canonical id bytes, and
  every source artifact's repository path plus its embedded `content_sha256`; and
- the complete prompt byte length and SHA-256 before tokenization.

Id files contain one unsigned decimal Qwen token id plus newline per record, with no blank lines,
sign, leading zero, comma, BOS insertion, chat template, or detokenized text. The checker validates
the grammar, count, range against `n_vocab = 152,064`, id-file digest, prompt/source digests, and
`shared + suffix <= 2,048` without loading the model.

`canonical-v1e` is present as a corpus identity, but it did **not** land a second fixed prompt
family. All three of its task manifests point `task_prompt_path` back to the same
`eval/tasks/prompt-v1/<task>/task-prompt.json` bytes, and its scope reuses the same base and
repository prompts. Counting those three again would turn duplicate suffixes into fake clusters and
make the jackknife look stronger without adding an observation.

Its repair attempts are not the missing family either. They are derived from provider output and
diagnostics rather than frozen source prompt artifacts; the measured sample-1 parent repairs
assemble to 11,417, 8,348, and 15,308 bytes, and their exact text is intentionally not independently
derivable from the freeze alone. The charter asked for the second family *if available* and
explicitly permits three suffixes otherwise. This implementation therefore takes the honest
three-cluster fallback and names the reason rather than silently duplicating them.

### 3.5 Corpus generation and Request 22

`scripts/check-prefix-corpus` owns both `generate` and default check modes. Generation requires
`ALIGN_LLM_LLAMA_DEBUG` and `ALIGN_LLM_GGUF_MODEL`, verifies their recorded identities, writes one
temporary prompt at a time outside Git, invokes `llama-debug --save-logits`, extracts the
`*-tokens.bin` little-endian int32 ids, and removes logits immediately. Check mode is model-free and
read-only.

Request 22 remains non-blocking. Align receives checked-in decimal ids and indexes no
`array<string>`; Python reads the token binary the already-pinned instrument produces. R7's text
path remains the first tokenizer/detokenizer consumer.

### 3.6 Qualification surface

`scripts/run-decode-step --prefix-ttft` is the named capable-host qualification path.
`gmake prefix-ttft-qualification` invokes it. The ordinary `decode-step-qualification` command and
its cost are unchanged.

Required environment is the existing decode-step set plus:

| Variable | Contract |
| --- | --- |
| `ALIGN_LLM_PREFIX_TTFT_TMPDIR` | Scratch root; defaults by the existing runner convention |
| `ALIGN_LLM_PREFIX_TTFT_EVICTION_FILE` | Existing unrelated regular file at least 20 GiB; absence makes protocol C explicitly `N/A`, never MET |
| `ALIGN_LLM_PREFIX_TTFT_REPEATS` | Defaults to and may only equal 5 for a gate run; other values are diagnostic and cannot produce a verdict |

The runner verifies at least 12 GiB physical memory, enough free space for the pack plus one 168 MiB
container and 3 GiB headroom, corpus consistency, model and instrument identity, and an eviction
file at least 20 GiB before timing. Any missing prerequisite prints one named `N/A` and exits zero;
it cannot print MET.

## 4. Measurement protocol

### 4.1 Fixed task and legs

For each of three suffixes and each protocol, the runner first creates the warm store with an
unmeasured setup run. Every paired observation then uses fresh processes:

- single-shot: `TOKENS = shared ++ suffix`, `STEPS=1`, `RESIDENT=weights`;
- keyed hit: `TOKENS = shared`, `SUFFIX = suffix`, the populated `STORE`, `STEPS=1`,
  `RESIDENT=weights`;
- both: no transcript and no logits path, `KV_WIDTH=1536`.

Repeat is outer and leg is inner. Leg order alternates by repeat (`single,hit` then `hit,single`) so
one leg does not always inherit the immediately preceding cache state. A separate process is used
for every leg.

### 4.2 Cache protocols

| Protocol | Required action |
| --- | --- |
| W — warm | No deliberate eviction between legs. Store and pack pages remain as prior runs leave them |
| C — eviction pressure | Read the complete unrelated >=20 GiB file before **each leg**, not only before a pair. Record bytes and elapsed time |

The runner records `vm_stat` compressor fields immediately before and after every timed process.
Movement is reported and never causes a discard, retry, or replacement observation.

### 4.3 Statistic

For pair `(suffix, repeat)`:

```text
reduction_ppm = round_half_away_from_zero(
  (single_first_token_ns - hit_first_token_ns) * 1,000,000 / single_first_token_ns)
```

The runner reports all 30 pairs, per-suffix means, protocol means, and all three leave-one-suffix-out
means per protocol. `jackknife_min` and `jackknife_max` are the minimum and maximum of those three
values. The worse protocol is the one with the smaller `jackknife_min`; ties select C. No pair is
removed as an outlier.

The measurement also reports hit `kv.read_ns`, `store.lookup_ns`, `weights.fill_ns`, container
bytes, and the miss secondary from section 2.4. Only `timings.first_token_ns` enters the verdict.

### 4.4 Output and publication

The runner writes no tracked file. It emits one canonical JSON summary to the requested scratch
path and a concise verdict line. The post-measurement section appended to this document records the
exact head, host, command, all aggregate figures, protocol verdicts, miss cost, compressor movement,
and summary SHA-256. Individual-pair output stays attached to the pull request as check evidence.

## 5. Closure matrix

| Cell | Implementation | Exact regression or evidence |
| --- | --- | --- |
| Dense declaration | Qwen cap 2,048 | `layer-forward-smoke`: 2,048-token synthetic boundary passes; 2,049-token `R5_TOKENS` refusal |
| Routed declaration | OLMoE cap 2,048 | `layer-forward-smoke`: 2,048-token routed synthetic boundary passes; 2,049-token refusal |
| Dense staging construction | `plan_resident` reserves 29,360,128 B | dense boundary case asserts stage bytes, arena bytes, high slot 2,047, pointer identity, and balanced teardown |
| Routed staging construction | dense-resident OLMoE stage is 16,777,216 B | routed boundary case asserts stage bytes, region arithmetic, high slot 2,047, oracle D, and balanced teardown |
| Suffix success | prefix plus suffix exactly 2,048 | `ds-suffix-at-cap`, oracle S against its single-shot comparand, no golden activation row |
| Suffix malformed / over cap | sequence 2,049 | `ds-suffix-over-cap` and `-and-narrow`, exact detail `sequence[2049]` |
| Persisted old success | token_count 32 | existing save/load/store rows remain byte-identical outside path/timing normalization |
| Persisted expanded success | token_count 33 and corpus prefix count | independent reader and arm accept; writer/reader/store key agree; no activation golden |
| Persisted malformed / over cap | token_count 2,049 | arm and Python reader both refuse `token_count` before region use |
| Token region layout | counts 33 and 2,048 | independent arithmetic asserts identity/logits/plane offsets and 8-byte alignment |
| Allocation failure | resident total over `MAX_WINDOW_BYTES` | existing `R6_RESIDENT_BUDGET`; unchanged, fail before allocation |
| Early exit | failure after resident construction | existing forced-wrap regression balances the run-scope wrap at the enlarged layout |
| Cleanup | success and every timed failure | existing lifetime counters plus runner trap removes scratch store, plane, token binary, and logits |
| Corpus construction | three independent suffixes plus shared prefix | generation reproduces manifest; default checker is read-only and model-free |
| Corpus malformed | source, digest, grammar, count, or prompt mismatch | checker fixtures mutate one field/class each and fail with a bounded named reason |
| Warm measurement success | 15 interleaved pairs | qualification JSON contains every `(suffix, repeat, leg)` exactly once and applies the fixed statistic |
| Eviction-pressure success | 15 interleaved pairs | each leg has a preceding >=20 GiB read and before/after compressor record |
| Measurement partial failure | process, document, cache-pressure, or parse failure | no verdict; summary is `ERROR` with completed coordinates, trap cleanup still runs |
| Cross-platform golden safety | long real activations | no real activation at four or more tokens is checked into a golden; long rows are qualification-only |
| Six-token oracle | `R5_ORACLE_TRUNCATED` | seven-token transcript cases remain refusals; no cap-derived edit touches the oracle constant |

## 6. Verification, review, and delivery

Development owner after each coherent batch:

```text
gmake layer-forward-smoke prefix-corpus-check
```

Named performance qualification on the reference host:

```text
gmake prefix-ttft-qualification
```

Publication preflight:

```text
python3 scripts/pre-pr --owner-test R6-PREFIX-TTFT -- \
  gmake layer-forward-smoke prefix-corpus-check
```

`make ci` is not selected merely by enlarging the cap or adding a focused qualification. It is
selected only if implementation changes aggregate membership or topology. The stable candidate
receives one comprehensive review over the design, constant lift, persisted compatibility, corpus,
measurement runner, and measured claim. The pull request records the exact design commit that
precedes implementation, exact owner and qualification results, and every finding disposition.

## 7. Deferred work

- R7 owns a text consumer and makes Request 22 blocking.
- A longer repository preamble or file-header prefix is the next corpus only if this gate is
  NOT_MET or INDETERMINATE for a measured prefix-share reason.
- KV tiering, eviction, compaction, and store garbage collection remain separate ownership and
  policy capabilities.
- Cross-host performance portability needs a separately fixed host class and baseline; this result
  claims only the reference host and protocols above.

## 8. Implementation and measurement record

### 8.1 Final implementation and bounded deviations

The pre-implementation design is commit `a3c5e9e`. The measured implementation head is
`eb832bf34e8e1e8d31f6aa9d78590f211e009f55`: `17cce70` implements the cap, corpus, owners, and
runner; `eb832bf` corrects the runner's qualification-only validation of a keyed hit. A hit skips
the prefix graph by definition, so its `reference.verdict` is `-`, while a miss and a single-shot
run compute that graph and remain `IDENTICAL`. Hosted oracle K and oracle S own the skipped graph's
equivalence. The first attempted qualification stopped at exactly that validation, emitted an
`ERROR` summary with its two completed timed coordinates, removed scratch state, and made no
verdict; none of its observations were reused in the run below.

Three implementation details refine, but do not change, sections 3 through 5:

1. The synthetic F32 fixture's embedding row is 32 B. Its exact-cap single-shot gather therefore
   raises the planner high-water from the 49,152 B layer block to 65,536 B, while the suffix run
   loads only the two-row prefix before continuing and keeps the layer high-water. The exact-cap
   oracle S excludes only the five fields identifying that high-water block and asserts both
   layouts exactly; every semantic field and every other window field stays in the equality.
2. The stub arena is 512 MiB instead of 4 MiB so the 2,048-column attention mask is really
   allocated and computed. Expanded persisted fixtures cover counts 33, the corpus prefix count
   370, 2,048, and the 2,049 refusal independently of real-model activation goldens.
3. `ALIGN_LLM_PREFIX_TTFT_SUMMARY` is the optional requested-output path section 4.4 anticipated.
   It defaults to `align-r6-prefix-ttft-summary.json` under the scratch root and must resolve
   outside the work tree. The run directory is still removed; the canonical summary survives at
   that explicit path. Non-five repeat counts are labelled `DIAGNOSTIC` and cannot emit a gate
   verdict.

The generated corpus passed its model-free checker with a 370-id shared prefix and suffix counts
696, 1,049, and 825. Owner verification passed at the implementation checkpoint: all seven
`layer-forward-smoke` blocks, including 167 dense decode documents and 70 routed decode documents,
plus the corpus's five malformed classes. Long real activations remain absent from goldens.

### 8.2 Reference-host command and evidence identity

The gate run used the section 3.6 environment-variable command form below. `$MODEL` was the exact
model identity in section 2.1; `$EVICTION` was an existing unrelated 63,999,836,160-byte Docker
disk image. Paths are intentionally not persisted.

```text
PATH=$GNU_MAKE_PATH:$PATH \
LIBRARY_PATH=$GGML_LIB:$OPENSSL_LIB \
ALIGN_LLM_GGML_INCLUDE=$GGML_INCLUDE \
ALIGN_LLM_GGML_LIB=$GGML_LIB \
ALIGN_LLM_GGUF_MODEL=$MODEL \
ALIGN_LLM_LLAMA_EVAL_CALLBACK=$LLAMA_EVAL_CALLBACK \
ALIGN_LLM_LLAMA_DEBUG=$LLAMA_DEBUG \
ALIGN_LLM_PREFIX_TTFT_EVICTION_FILE=$EVICTION \
ALIGN_LLM_PREFIX_TTFT_TMPDIR=$SCRATCH \
ALIGN_LLM_PREFIX_TTFT_SUMMARY=$SUMMARY \
gmake prefix-ttft-qualification
```

Host: Apple M1, arm64, 16 GiB physical memory, macOS 26.5.2. Both instruments reported build
10566 at commit `bb4caa754`; the model was 4,683,073,536 B at SHA-256 `509287f7…d3c`. The canonical
49,218-byte summary is SHA-256
`aa1627a074bfec80a5a291a93d2e22b118b2eeea7b7514a0db18e13873f5f833`. An independent read-only
recalculation verified all 30 unique pair coordinates, alternating orders, every per-pair
half-away result, both protocol means, all six suffix means, the six leave-one-suffix-out means, 66
completed fresh processes, and the final rule.

### 8.3 TTFT result

All figures below are reductions in ppm. No pair was discarded or replaced.

| Protocol | Duration suffix | Layer-precedence suffix | Record-codec suffix | Protocol mean | Leave-one-out values | Jackknife range |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| W | 347,025 | 264,500 | 302,479 | 304,668 | 283,489 / 324,752 / 305,762 | **283,489..324,752** |
| C | 317,170 | 266,282 | 312,056 | 298,502 | 289,169 / 314,613 / 291,726 | **289,169..314,613** |

The worse protocol is W because its jackknife minimum, **283,489 ppm**, is smaller. Both protocol
minima are positive, and the worse minimum clears the 150,000 ppm shipping floor by **133,489
ppm**. The roadmap improvement gate is **MET** and the shipping verdict is **MET**.

Mean first-token times, in seconds, show the paired quantities behind that result:

| Protocol | Suffix | Single-shot | Keyed hit | Pair reduction range |
| --- | --- | ---: | ---: | ---: |
| W | duration | 168.860 | 109.934 | 283,080..432,427 ppm |
| W | layer precedence | 193.201 | 142.090 | 256,429..276,538 ppm |
| W | record codec | 154.738 | 108.001 | 285,360..326,914 ppm |
| C | duration | 142.044 | 97.030 | 235,941..356,025 ppm |
| C | layer precedence | 187.838 | 137.811 | 251,829..283,305 ppm |
| C | record codec | 161.987 | 111.450 | 284,296..340,571 ppm |

Across all hits, the container is 176,771,072 B. Mean hit `kv.read_ns` is 152,434,203 under W and
158,201,417 under C; mean lookup is 7,086 ns and 6,305 ns; mean resident fill is 1,827,265,386 ns
and 1,942,992,111 ns. These remain reported components, not alternate verdict inputs.

### 8.4 Miss, eviction, and compressor observations

Miss cost is secondary as precommitted. Break-even is the exact section 2.4 formula against that
suffix/protocol's five mean legs; zero is possible when the single observed miss happened to be
faster than the five-run single-shot mean.

| Protocol | Suffix | Miss first token | Container write | Bytes | Break-even reuses |
| --- | --- | ---: | ---: | ---: | ---: |
| W | duration | 140.107 s | 376.092 ms | 176,771,072 | 0 |
| W | layer precedence | 193.235 s | 356.708 ms | 176,771,072 | 1 |
| W | record codec | 159.452 s | 454.219 ms | 176,771,072 | 1 |
| C | duration | 135.811 s | 325.249 ms | 176,771,072 | 0 |
| C | layer precedence | 177.941 s | 222.426 ms | 176,771,072 | 0 |
| C | record codec | 163.760 s | 348.238 ms | 176,771,072 | 1 |

Protocol C completed 33 full-file reads — one before each of 30 timed legs and one before each of
three miss setups — at exactly 63,999,836,160 B each. Elapsed read time ranged 18.300..19.845 s,
mean 19.119 s. W deliberately recorded no eviction.

Summed over all 33 processes per protocol, W moved stored/occupied compressor pages by
+66,898/+17,796 and swapouts by zero. C moved them by -252,375/-120,566 and swapouts by +4,108.
All C swapouts occurred in duration pair 1's single-shot leg. The observation is retained exactly
as section 4.2 requires. It does not carry the verdict: C's **minimum** leave-one-suffix-out value is
the 289,169 ppm row that excludes the entire duration cluster, and W — with zero swapouts — is the
worse protocol and independently clears the floor.

### 8.5 Closure disposition

Every section 5 cell maps to the final diff or retained evidence:

- the dense/routed declarations and staging cells map to `src/layer_qwen2.align`,
  `src/layer_olmoe.align`, the 512 MiB stub arena, and the exact 2,048 boundary rows in
  `layer-forward-smoke`;
- suffix success/refusal and allocation/early-exit/cleanup map to the exact-cap oracle-S row, both
  2,049 sequence refusals, the unchanged budget refusal, and the enlarged resident lifetime rows;
- persisted compatibility and layout map to the 32-token legacy goldens plus independent 33, 370,
  2,048, and 2,049 arm/reader fixtures;
- corpus construction/malformed cells map to `scripts/check-prefix-corpus` and its five mutation
  classes;
- W/C measurement success maps to the 30-pair summary above, while partial failure maps to the
  discarded first invocation's bounded `ERROR` summary and cleanup; and
- long real activations remain qualification-only, while the seven-token transcript refusals and
  six-token oracle constant are unchanged and pass in the same owner.

There is no deferred applicable closure cell.
