# R8 OLMoE text boundary

Status: design active, 2026-09-02

## 1. Decision and boundary

R8-PARTIAL-LRU-CACHE makes the selected expert cache executable, but the only shipped
`ModelProvider` runtime arm still prepares Qwen2 text and executes the dense decoder. The smallest
independently useful prerequisite for an OLMoE provider is the missing text boundary: accept the
reference OLMoE model's `gpt2`/`olmo` tokenizer profile, render its exact model-carried chat
template for the existing system/user request shape, and emit the prompt token ids already accepted
by `--moe-decode-step`.

This capability extends the existing `encode_model`, `decode_model`, `prepare_prompt_model`,
`--tokenize`, `--detokenize`, and `--prepare-prompt` surfaces. It adds no verb, argument, result
field, provider kind, runtime dispatch, cache policy, generation, or performance claim. Qwen2
behavior and tokenizer identity remain byte-identical. The Align `8cefc803` pin adoption is an
internal checkpoint in this consumer branch, not a pin-only pull request.

The proportional design gate fires because the accepted model profile, tokenizer identity,
pre-tokenization semantics, prompt construction, malformed-model order, and two public APIs/three
public CLI operations change together. This document is their authoritative ledger and closure
matrix.

## 2. Public-contract ledger

| Field | Settled contract |
| --- | --- |
| Capability | `R8-OLMOE-TEXT` |
| Consumer | a caller needing exact text/token conversion or provider-ready prompt ids for the shipped OLMoE runtime |
| Public API | existing tokenizer and prompt functions; signatures and result records are unchanged |
| Public CLI | existing `--tokenize`, `--detokenize`, and `--prepare-prompt`; grammar and output are unchanged |
| Accepted profiles | existing `gpt2/qwen2`, unchanged; new `gpt2/olmo` profile |
| OLMo pre-tokenizer | pinned llama.cpp GPT-2 expression in section 2.1, including case-sensitive contractions, multi-digit numeric runs, and trailing-whitespace behavior |
| OLMo prompt | exact 508-byte template SHA-256 plus model-carried BOS id, then the fixed system/user/assistant rendering in section 2.2 |
| Result/errors | existing result publication rules; unsupported model/pre remains `R7_UNSUPPORTED_TOKENIZER`; OLMo prompt metadata errors are ordered in section 2.3 |
| Ownership | the existing one-snapshot prompt path and private tokenizer ownership; profile and BOS id are Copy scalars; no new escaping object |
| Identity | Qwen schema 1 remains unchanged; OLMo uses its own domain and includes exact `gpt2`, `olmo`, classifier identity, tokens, original types, and merges |
| Persisted/cache identity | N/A: no persisted state or text cache; the tokenizer and template ids identify model-carried inputs |
| Schema version | N/A: public record layouts and canonical token-id JSON do not change |
| Prerequisites | R8 partial LRU cache merged; Align `8cefc803d5c7f883a8db5b67250ed4ed069b43a4` materialized and verified |
| Acceptance | focused synthetic owner plus real OLMoE parity against pinned llama.cpp build 10566; Qwen regression owner |
| Metric | N/A: this is a correctness prerequisite and makes no latency or time-to-passing-patch claim |

### 2.1 OLMo pre-tokenization

The new profile implements the pinned llama.cpp GPT-2 expression:

```text
's|'t|'re|'ve|'m|'ll|'d
| ?\p{L}+
| ?\p{N}+
| ?[^\s\p{L}\p{N}]+
|\s+(?!\S)
|\s+
```

The existing scalar classifier identity and Unicode tables remain authoritative. OLMo differs from
Qwen2 in four observable ways: contractions match lowercase spellings only; only one ASCII space
may prefix a letter, number, or punctuation run; a numeric run is one piece; and CR/LF receives no
special punctuation attachment rule. The negative-lookahead whitespace alternative is implemented
by emitting all but the last scalar of a multi-scalar whitespace run when non-whitespace follows.
Every fallback advances one scalar. Special-token partition still runs before pre-tokenization and
retains both existing explicit modes.

OLMo `tokenizer_id` is SHA-256 over the R7 canonical token/type/merge encoding with domain
`R8OLMOTK`, identity schema 1, model `gpt2`, pre-tokenizer `olmo`, and the same classifier identity.
The separate domain prevents profile confusion. The Qwen `R7QW2TOK` preimage is not rewritten.

### 2.2 Supported OLMoE template and rendering

The admitted OLMoE template is exactly 508 UTF-8 bytes with SHA-256:

```text
fe689ffbd6a4e2d0532d7480696b065b10e0e1eff3f9b9fc4bea415761e4bf4a
```

For the fixed system/user shape and `add_generation_prompt=true`, rendering is exactly:

```text
BOS<|system|>\nSYSTEM\n<|user|>\nUSER\n<|assistant|>\n
```

`BOS` is the token text selected by the model's first `tokenizer.ggml.bos_token_id`. The id must be
present, non-negative, below vocabulary size, and an effective control token after tokenizer load.
The reference model selects id 50279, `|||IP_ADDRESS|||`; that surprising model-carried value is
preserved rather than repaired. The fixed fragments excluding `BOS`, `SYSTEM`, and `USER` total 36
bytes. The complete prompt must remain within the existing 1 MiB cap and is encoded in
`ParseControl` mode. Message bytes are not escaped, normalized, or injection-isolated.

Qwen continues to require its existing template hash and exact 80 fixed bytes. Template selection
uses the tokenizer profile; a Qwen template on an OLMo profile, or the reverse, is unsupported.

### 2.3 Validation and error order

Tokenizer load keeps every R7 step and failure code, except the profile check now accepts exactly
`qwen2` or `olmo` when model is `gpt2`. Profile is established before arrays are materialized.

Prompt preparation retains one snapshot and this order:

1. path and complete GGUF structure;
2. chat-template presence/type and the existing 4,096-byte cap;
3. tokenizer model/pre presence and supported profile;
4. template hash for that profile;
5. for OLMo, BOS metadata presence and integer class;
6. profile-specific checked prompt size;
7. complete tokenizer load from the same snapshot;
8. for OLMo, BOS range and effective-control validation;
9. exact render, encode, and existing token-count publication.

Existing `R7_*` result codes remain the wire vocabulary. Missing or wrong-type OLMo BOS metadata is
`R7_CHAT_TEMPLATE_METADATA` with detail `tokenizer.ggml.bos_token_id`; an out-of-range or non-control
id is `R7_UNSUPPORTED_CHAT_TEMPLATE` with detail `bos_token_id[n]`. A wrong profile-specific hash
retains `R7_UNSUPPORTED_CHAT_TEMPLATE` with `sha256[...]`. No partial ids escape.

## 3. Acceptance and cost

The focused synthetic owner builds one tiny OLMo GGUF and checks:

- lowercase versus uppercase contractions, multi-digit runs, leading-space categories, CR/LF,
  trailing/non-trailing whitespace, Unicode, special parsing, and exact decode;
- deterministic OLMo identity distinct from the unchanged Qwen identity;
- exact prompt bytes/ids for empty, ASCII, multiline, NUL, Unicode, and delimiter-bearing inputs;
- cross-profile template rejection plus missing, wrong-type, out-of-range, and non-control BOS cases;
- first-failure publication and unchanged CLI JSON/stdout isolation.

The real qualification requires the exact 4,213,512,192-byte model with SHA-256
`4ddc0e53159ed512b8dd67914a66e27bc618f694672ba43a9a0454eabd9c684f`, pinned
`llama-tokenize`, and pinned `llama-server`. It compares a fixed lexical corpus in both special
modes, exact decoded bytes, and six `/apply-template` prompt cases plus their ids. Missing opt-in
prerequisites are N/A; a named wrong prerequisite or mismatch fails.

The focused synthetic owner has a five-minute ceiling and the real qualification an approximately
five-minute ceiling on the reference host. Publication uses the focused owner and normal hosted
checks selected by `scripts/pre-pr`; it does not select `make ci`, installed/native profiles,
benchmarks, stress, the 40-prompt trace, or the OLMoE runtime matrix solely for this text change.

## 4. Closure matrix

| Owner / path | Construction | Success | Failure / malformed | Early exit | Cleanup | Regression |
| --- | --- | --- | --- | --- | --- | --- |
| profile load | model/pre scalars select Qwen or OLMo before arrays | exact private profile | all other pairs unsupported | before payload materialization | scalars and snapshot drop | synthetic cross-profile matrix |
| scanner | scalar spans plus existing classifiers | exact ordered pieces | valid UTF-8 is guaranteed by `str` | total one-scalar fallback | regex and piece arrays drop | lexical table plus real parity |
| identity | profile-specific domain and canonical arrays | deterministic distinct digest | no digest before valid model | after all bounded validation | preimage drops | repeated API publication and Qwen golden |
| template selection | profile plus complete template digest | matching renderer only | crossed/wrong hash refuses | before prompt allocation | digest/scalar drop | crossed-template mutants |
| OLMo BOS | first integer metadata then loaded token lookup | exact model spelling | absent/type/range/control errors | no render before validation | Copy id; tokenizer owns text | four BOS mutants and real prompt |
| prompt renderer | profile-specific fixed fragments | exact bytes and ids | size/render mismatch uses existing errors | no encode after mismatch | builder and tokenizer scratch drop | synthetic prompt corpus and `/apply-template` |
| public API/CLI | existing signatures and grammar | owned results/canonical output | first error, empty output | first failure stops | only result escapes | focused API/CLI owner |
| pin adoption | managed compiler at exact revision | focused consumer compiles and passes | identity mismatch refuses | before product test | managed toolchain owns cache | ensure/verify plus owner |

## 5. Deferred boundary

The next capability may connect `prepare_generation_snapshot` to an OLMoE stop set, add a
stop-aware resident MoE generation seam, and expose it through an explicit provider configuration
that consumes the shipped partial cache. That capability owns provider cache budget, EOG behavior,
end-to-end task evidence, and any time-to-passing-patch claim; none is implied here.

## 6. Author consistency pass

The ledger, algorithms, errors, acceptance rows, and closure matrix agree: only two exact tokenizer
profiles and two exact template identities are admitted; Qwen is unchanged; OLMo uses its own
scanner/identity/rendering and model-carried BOS; every new failure is recoverable and ordered; the
pin is verified through this real consumer; and no runtime or performance promise is made.
