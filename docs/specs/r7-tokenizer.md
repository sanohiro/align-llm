# R7-TOKENIZER

Status: contract ready after consolidated final-review redesign, 2026-08-31; align-llm source
blocked on Align Request 22

## 1. Decision and boundary

### 1.1 The consumer-complete capability

R6 ends at token ids. The existing `ModelProvider` boundary starts with text and ends with text.
The smallest independently useful bridge between them is therefore not another inference arm: it
is a tokenizer that can read the vocabulary carried by the same GGUF model, encode a UTF-8 file to
ids, and decode ids to exact UTF-8 without invoking an external tokenizer at runtime.

R7-TOKENIZER ships exactly that bridge for the dense runtime's reference model:

- GGUF `tokenizer.ggml.model = "gpt2"` and `tokenizer.ggml.pre = "qwen2"`;
- the Qwen2 pre-tokenizer, GPT-2 byte alphabet, and byte-pair merge algorithm;
- explicit control-special parsing and rendering modes;
- `main --tokenize` and `main --detokenize` as real file-to-stdout consumers;
- a hosted synthetic owner and an opt-in real-model parity qualification against the pinned
  `llama-tokenize`.

The implementation reads the model's own `tokenizer.ggml.tokens`,
`tokenizer.ggml.token_type`, and `tokenizer.ggml.merges`. It does not carry a copied Qwen vocabulary,
download a tokenizer, call Python, contact a server, or invoke llama.cpp in the product path.

### 1.2 Why the proportional design gate fires

All applicable triggers fire.

- **Public API:** two GGUF array readers and two tokenizer operations become imported-module
  surfaces.
- **Public CLI:** `--tokenize` and `--detokenize` acquire exact operands, modes, output, and error
  behavior.
- **Exchanged format:** tokenize stdout and detokenize input use one canonical JSON array of token
  ids.
- **Ownership/resource boundary:** roughly 303,000 owned strings are materialized on the reference
  model, indexed, and released on every success and failure path.
- **Coordinated invariant:** GGUF types, special-token classification, Qwen2 splitting, byte
  encoding, BPE rank order, CLI modes, the synthetic oracle, and llama.cpp parity must agree.

This document is the one authoritative public-contract ledger and closure matrix for the
capability. A design-only publication checkpoint is justified by an external coordination need,
not by an internal desire to split the work: section 1.4's compiler change must ship before any
align-llm source may consume the contract.

### 1.3 In scope and non-goals

**In scope.** Valid UTF-8, including embedded NUL; empty text; the Qwen2 pre-tokenizer; GPT-2 byte
encoding; ranked BPE; GGUF token types NORMAL (1), UNKNOWN (2), CONTROL (3), USER_DEFINED (4),
UNUSED (5), and BYTE (6); the Qwen2 `</s>` control promotion used by the pinned oracle; exact token
ids; exact decoded bytes followed by whole-result UTF-8 validation; and path-independent tokenizer
identity.

**Out of scope.** Chat-template rendering; automatic BOS, EOS, padding, FIM, or stop insertion;
EOG classification as a generation policy; `ModelProvider`; weight loading; inference; sampling;
streaming generation; a resident tokenizer handle; any architecture or pre-tokenizer other than
`gpt2`/`qwen2`; normalization or cleanup of decoded spaces; binary text that is not valid UTF-8;
and any speed, memory-efficiency, TTFT, decode-latency, or time-to-passing-patch claim.

The absence of a resident public handle is deliberate. Align has no opaque application-defined
record: exporting the internal hash tables would freeze representation as API. The two public
operations load and release one private tokenizer per call. That is useful for the CLI and for a
future provider's one prompt encode plus one final decode. A resident handle may be added only
with its own public ownership contract when a consumer measures that the second load matters.

### 1.4 Blocking Align dependency

Align Request 22 in [`../align-requests.md`](../align-requests.md) asks for non-consuming ordinary
indexing of `array<string>` and arrays whose element record has a Move field. Current Align `main`
at `4b515f8d` and the pinned `.align-revision` reject that expression outside the already-shipped
direct-borrow-call exception. A real tokenizer needs to compare an indexed token or merge string
many times and cannot be built on the exception.

The request is therefore **blocking** now. The allowed order is exact:

1. publish and coordinate this contract;
2. implement and merge Request 22 in Align, including compiler owners and documentation;
3. advance the request to `ALIGN_MERGED`, update `.align-revision`, and materialize the managed
   compiler;
4. implement this capability against the shipped surface and migrate the request's previously
   named align-llm workarounds;
5. pass every request owner plus the tokenizer owners, then advance through
   `ALIGN_LLM_VERIFIED` to `CLOSED`.

No align-llm source on this branch may name a proposed accessor, imitate it with an FFI helper,
flatten the vocabulary into another stream-plus-column compatibility representation, or use an
external tokenizer as the product implementation before step 3.

## 2. Public-contract ledger

### 2.1 GGUF array producers

`src/gguf.align` remains the sole owner of GGUF container interpretation and adds these exact
surfaces:

```align
pub fn kv_array_element_type(borrow table: GgufTable, key: str) -> i64
pub fn read_string_array(path: str, key: str) -> Result<array<string>, Error>
pub fn read_i32_array(path: str, key: str) -> Result<array<i64>, Error>
```

| Field | Contract |
| --- | --- |
| Key selection | The first valid UTF-8 metadata key equal to `key`, matching `find_key` and every existing R1 accessor. A later duplicate is ignored |
| `kv_array_element_type` | Returns the GGUF element type id for an ARRAY; `-1` when `key` is lexically invalid, absent, or not an ARRAY. It allocates nothing and has no error channel |
| `read_string_array` success | The selected value is ARRAY/STRING; every element is valid UTF-8 and within the bounds below; result order equals file order; every result element is an owned `string`; no view or file handle escapes |
| `read_i32_array` success | The selected value is ARRAY/INT32; each little-endian element is sign-extended to `i64`; result order equals file order; the result is owned |
| Structural validation | Each reader first obtains a successful complete `read_table(path)`. A table with `GgufStatus.Error`, a missing key, wrong outer or element type, truncated payload, invalid UTF-8 string element, or violated materialization bound is `Err(Error.Invalid)` |
| Reader OS errors | `NotFound`, `Denied`, and other `std.fs` errors propagate unchanged. For `read_string_array` and `read_i32_array`, a lexically invalid path or key is `Error.Invalid` |
| Allocation | At most one selected array is materialized. The temporary table, window, and file are released before return; success transfers only the returned array |
| Effects | Reads the named path. No write, mapping, process, network, environment, cache, or cwd effect |
| Persisted/cache identity | N/A: the readers persist and cache nothing. File order and bytes are the result's identity |

The path grammar remains R0's: non-empty, at most 4,096 UTF-8 bytes, no NUL. The key is non-empty,
at most 4,096 bytes, and contains no NUL. Because the scalar accessor cannot return `Error`, an
invalid key is indistinguishable from an absent/non-array key and returns `-1`; the two fallible
readers reject the same key as `Error.Invalid` before path work. The generic GGUF caps remain the
outer container-validity limit: `MAX_ARRAY_ELEMENTS = 16,777,216` and
`MAX_STRING_BYTES = 16,777,216`. Materialization is a narrower public operation: both readers
refuse more than 1,048,576 elements; the string reader also refuses an item over 4,096 bytes or
cumulative string payload over 16,777,216 bytes. Those checks happen from declared length
prefixes before each clone, so an accepted container cannot force a multi-gigabyte temporary array
before section 2.8's tokenizer check.

The implementation may retain each selected value's absolute payload offset in `GgufTable` and
reopen that bounded region after the complete walk. It may not create a second GGUF type grammar or
make `read_table`, `inspect`, and the array readers disagree about malformed input.

### 2.2 Public tokenizer types and functions

`src/tokenizer_qwen2.align` exports only this inventory:

```align
pub TokenizerStatus { Ok, Error }
pub EncodeSpecials { ParseControl, LiteralControl }
pub DecodeSpecials { RenderControl, SkipControl }

pub TokenIdsResult {
  status: TokenizerStatus,
  error_code: string,
  error_detail: string,
  tokenizer_id: string,
  vocab_size: i64,
  merge_count: i64,
  token_ids: array<i64>,
}

pub TokenTextResult {
  status: TokenizerStatus,
  error_code: string,
  error_detail: string,
  tokenizer_id: string,
  vocab_size: i64,
  merge_count: i64,
  token_count: i64,
  text: string,
}

pub fn encode_model(
  model_path: str,
  text: str,
  specials: EncodeSpecials,
) -> Result<TokenIdsResult, Error>

pub fn decode_model(
  model_path: str,
  borrow token_ids: array<i64>,
  specials: DecodeSpecials,
) -> Result<TokenTextResult, Error>
```

| Surface | Result, ownership, and effects |
| --- | --- |
| `encode_model` | Loads one private tokenizer, borrows `text` for the call, and returns an owned id array. Empty text returns `Ok(status=Ok, token_ids=[])`. It reads only `model_path` |
| `decode_model` | Loads one private tokenizer, borrows but never mutates `token_ids`, and returns one owned string no larger than `MAX_OPERATION_OUTPUT_BYTES`. Every outer-`Ok` result publishes `token_count=token_ids.len()`, including model and operation failures. Empty ids return `Ok(status=Ok, token_count=0, text="")`. It reads only `model_path` |
| Recoverable OS failure | The outer `Result` is `Err` with the unchanged `std.fs` error. No partially initialized result is published |
| Model or operation failure | The outer `Result` is `Ok`; `status=Error`, `error_code` and bounded `error_detail` name the first validation failure, output is empty, and any identity/count known before the failure remains published as specified in 2.9 |
| Success | `status=Ok`, error strings are empty, `tokenizer_id` is 64 lowercase hex digits, counts are non-negative, and the output field is authoritative |
| Mutation | No input mutation, no global state, no cache, no environment read, no process, no network, and no write |
| Cleanup | The private token strings, merges, indexes, special trie, regex handles, scratch arrays, heap, and canonical-identity buffer are dropped before return on every path; only the result escapes |

There is no overload, default argument, bool mode, model-dispatch registry, public load function,
or public tokenizer record in this capability.

### 2.3 Required metadata and validation

The first occurrence of every key wins. Load validates in this order:

| Step | Requirement | Failure |
| --- | --- | --- |
| 1 | `model_path` obeys the path grammar | outer `Err(Error.Invalid)` |
| 2 | complete `gguf.read_table` succeeds structurally | existing GGUF code as `R7_GGUF`, detail `code@offset` |
| 3 | `tokenizer.ggml.model` and `.pre` are present STRING values | `R7_TOKENIZER_METADATA`, detail key |
| 4 | values equal `gpt2` and `qwen2` respectively | `R7_UNSUPPORTED_TOKENIZER`, detail `model/pre` |
| 5 | `tokens` is ARRAY/STRING, `token_type` ARRAY/INT32, `merges` ARRAY/STRING | `R7_TOKENIZER_METADATA`, detail key |
| 6 | validate declared counts before payload materialization: tokens first, then token types, then merges, with the exact details in 2.9 | `R7_VOCAB_SIZE` or `R7_MERGE_COUNT` |
| 7 | materialize tokens, types, then merges through the GGUF producers | `R7_TOKENIZER_ARRAY`, detail key |
| 8 | sum token bytes, then merge bytes, and require their combined total at most `MAX_TOKENIZER_TEXT_BYTES` | `R7_TOKENIZER_TEXT_SIZE`, exact three-count detail in 2.9 |
| 9 | every token is non-empty and type is in 1 through 6 | `R7_TOKEN_EMPTY` or `R7_TOKEN_TYPE`, detail `token[i]` or `token[i]type[n]` |
| 10 | build the bounded-bucket token index while scanning ids ascending; report duplicate text before bucket exhaustion | `R7_TOKEN_DUPLICATE` or `R7_HASH_BUCKET`, detail `token[i]` |
| 11 | after `</s>` promotion, the UNKNOWN/CONTROL/USER_DEFINED count is at most `MAX_SPECIAL_TOKENS` | `R7_SPECIAL_COUNT`, detail decimal count |
| 12 | every effective special candidate is at most `MAX_SPECIAL_TOKEN_BYTES`, checked in ascending id order | `R7_SPECIAL_TEXT`, detail `token[i]` |
| 13 | every NORMAL token consists only of GPT-2 alphabet scalars; every BYTE token is exact ASCII `<0xHH>` | `R7_TOKEN_TEXT`, detail `token[i]` |
| 14 | every merge has one non-empty left part and non-empty remainder after the first ASCII space found at byte 1 or later; left, right, and their concatenation resolve to token ids | `R7_MERGE` or `R7_MERGE_TOKEN`, detail in 2.9 |
| 15 | build the bounded-bucket merge index in rank order; a duplicate id pair keeps the first rank | `R7_HASH_BUCKET`, detail `merge[i]` |
| 16 | the 256 GPT-2 byte-alphabet strings resolve to NORMAL tokens | `R7_BYTE_ALPHABET`, detail `byte[n]` |
| 17 | construct the bounded special trie, then compute the canonical tokenizer identity | terminal OOM only; section 2.8 proves every arithmetic capacity |

`tokenizer.ggml.scores`, BOS/EOS/PAD ids, `add_bos_token`, `add_eos_token`, and
`tokenizer.chat_template` are neither required nor interpreted. They cannot affect either public
operation. Callers who want a BOS, EOS, FIM marker, or chat marker must supply the literal in
`ParseControl` mode or supply its id to `decode_model`; no hidden token is added or removed.

Empty token strings are rejected rather than rewritten to llama.cpp's synthetic `[EMPTY_i]`
spelling. The reference model has none, and rewriting container data would make tokenizer identity
and decode output depend on a hidden repair.

Duplicate token strings are rejected. Pinned llama.cpp first overwrites the text-to-id entry but
then aborts on its `id_to_token.size() == token_to_id.size()` assertion, so it exposes no usable
later-id behavior to copy. R7 turns that malformed-model abort into recoverable
`R7_TOKEN_DUPLICATE`; accepted-model behavior remains parity-compatible. Duplicate merge pairs
follow the pinned rule: the first rank wins. Their original array order remains part of identity.

The three successful GGUF array readers return exactly their declared lengths or fail before
publication. Actual-versus-declared mismatch is therefore a producer invariant, not an additional
recoverable tokenizer outcome. Step 6 checks the three declarations directly: token count must be
`1..MAX_TOKENIZER_ENTRIES`; token-type count must equal token count and be within the same cap; and
merge count must be `0..MAX_TOKENIZER_ENTRIES`.

### 2.4 Special-token modes

Effective classes begin with GGUF token type. For this Qwen2 capability only, a NORMAL token whose
text is exactly `</s>` is promoted to CONTROL before the special index is built. This reproduces
the pinned llama.cpp Qwen2 load, which reports id 128247 as a control-looking EOG token even though
the GGUF type is NORMAL. No other spelling-based promotion is admitted.

Special candidates are UNKNOWN, CONTROL, and USER_DEFINED tokens. An accepted model has at most
`MAX_SPECIAL_TOKENS = 256` candidates, and each candidate is at most
`MAX_SPECIAL_TOKEN_BYTES = 32` UTF-8 bytes. Partition is left-to-right; at a byte position the
longest candidate wins. Token text is unique by section 2.3, so no equal-spelling id tie exists.
Because both input and candidate are valid UTF-8, every match boundary is a scalar boundary.
Section 3.5 fixes the bounded trie that implements this order without a candidate-by-candidate
scan.

| Mode/class | UNKNOWN | CONTROL, including promoted `</s>` | USER_DEFINED | UNUSED | NORMAL/BYTE |
| --- | --- | --- | --- | --- | --- |
| `ParseControl` | atomic id | atomic id | atomic id | ordinary BPE input | ordinary BPE input |
| `LiteralControl` | ordinary BPE input | ordinary BPE input | **atomic id** | ordinary BPE input | ordinary BPE input |
| `RenderControl` | stored token text | stored token text | stored token text | empty | decoded piece |
| `SkipControl` | empty | empty | **stored token text** | empty | decoded piece |

The bold USER_DEFINED cells are intentional. They are the pinned tokenizer's behavior: Qwen2.5's
`<tool_call>` and `</tool_call>` remain atomic under `llama-tokenize --no-parse-special`, and they
remain visible during detokenization when control tokens are suppressed. The CLI names say
`control`, not the ambiguous `special`, so this cannot be mistaken for an all-literals/all-hidden
switch.

Special partition happens before Qwen2 pre-tokenization. Adjacent raw fragments are not recombined
across an atomic special token.

### 2.5 CLI

`src/main.align` adds two exact arms:

```text
main --tokenize MODEL INPUT.txt <parse-control|literal-control>
main --detokenize MODEL TOKENS.json <render-control|skip-control>
```

| Field | Contract |
| --- | --- |
| Selection | Only exact `args[1]` selects an arm |
| Arity | Exactly five arguments including program name. Too few or too many is `Error.Invalid` before path work |
| `MODEL` | GGUF path, lexical grammar from 2.1 |
| `INPUT.txt` | UTF-8 text path. Empty files and embedded NUL bytes are valid content |
| `TOKENS.json` | UTF-8 JSON path whose complete value decodes as `array<i64>` |
| Mode | Exact lowercase spelling shown above. Wrong mode is `Error.Invalid` before path or file work |
| Tokenize stdout | Canonical ASCII `[id,id,...]\n`: no spaces, non-negative decimal ids, exactly one trailing LF |
| Detokenize stdout | Exact decoded UTF-8 bytes and **no added byte**. Empty output writes zero bytes |
| Failure stdout | Every failure before the final stdout call writes zero bytes. If the output sink accepts a prefix and then fails (for example, `ENOSPC`, `EPIPE`, or `SIGPIPE`), that prefix may remain; the OS error/signal is authoritative. Diagnostics and textual `Error` rendering are runtime-owned and not stable |
| Exit | Success only for `TokenizerStatus.Ok`; a data error maps to `Error.Invalid`; an outer OS error propagates |
| Writes | None. Callers may redirect stdout; the command never opens, truncates, renames, or removes a destination |

Both input paths use one bounded streaming reader: accumulate at most `MAX_OPERATION_INPUT_BYTES +
1`, reject overflow before JSON decode or tokenizer work, then validate the complete UTF-8 region
once. No `fs.read_file` allocation precedes the bound. Each CLI arm invokes its public one-shot
operation exactly once; it does not preload a private tokenizer. CLI validation order is:

1. exact arity;
2. exact mode;
3. both path grammars;
4. bounded-read the operation input;
5. for detokenize, JSON-decode and enforce the id-count cap;
6. invoke `encode_model` or `decode_model`, which loads and validates the model once;
7. complete operation validation and computation;
8. construct the complete output in memory;
9. write stdout once.

Thus malformed or oversized operation input wins over an invalid model after all cheap lexical
checks. Once the public operation begins, its section 2.3 model order wins over id-range or decoded
output failures. All product validation and output construction finish before the stdout call, so
no product failure can leave a valid output prefix. The final file-descriptor write is not
transactional: a sink failure may leave any accepted prefix while retaining the OS error or signal.

### 2.6 Token-id JSON

The exchanged token-id form is a top-level JSON array of signed 64-bit integers. The parser accepts
ordinary JSON whitespace, but no object wrapper, float, string, boolean, null, nested array, or
trailing value. Each id must then satisfy `0 <= id < vocab_size`.

The producer is stricter and canonical: `[`; ids in order as shortest unsigned decimal text,
separated by `,`; `]`; LF. An empty array is `[]\n`. This schema has no version field because it is
the JSON spelling of the existing runtime operand — an ordered id vector — and has no optional or
evolving fields. A future need for identity or metadata must use a new document, not change this
array's shape.

### 2.7 Tokenizer identity

`tokenizer_id` is lowercase hex SHA-256 of this canonical byte preimage:

```text
8 bytes   ASCII "R7QW2TOK"
u32le     identity schema = 1
u64le     len("gpt2"), then those bytes
u64le     len("qwen2"), then those bytes
u64le     len(classifier_id), then the exact classifier_id bytes below
u64le     token count
repeat token count times:
  u64le   token byte length
  bytes   token UTF-8 bytes
  i32le   original GGUF token type (before `</s>` promotion)
u64le     merge count
repeat merge count times:
  u64le   merge byte length
  bytes   merge UTF-8 bytes
```

`classifier_id` is this one ASCII string (one line, no trailing byte):

```text
align-regex-v1;regex=1.13.1+f020237b6c8eed93db2e2cb53c00c60a8e1bc73da7d073199a1180401450218d;regex-automata=0.4.16+8fcfdb36bda0c880c5931cdc7a2bcdc8ba4556847b9d912bca70bc94708711ad;regex-syntax=0.8.11+d6f6ff9a378485b298a5286656da665ba74413d36db0979633275d2e708145d4
```

Those versions and Cargo checksums are the exact dependency identities in current Align
`Cargo.lock`; the `regex-syntax` package's generated category and Perl-space tables identify
Unicode 16.0.0. `tokenizer-smoke` resolves the managed checkout selected by `.align-revision` and
requires all three lock entries to equal this constant before compiling or executing the product.
An Align pin whose classifier dependency identity differs must update the identity schema and this
contract before it can be adopted; it cannot silently reuse an old tokenizer id.

The path, tensor bytes, quantization, chat template, special ids, and unrelated GGUF metadata are
excluded because they cannot affect these operations. File order, duplicate merge entries, unused
tokens, and original token types remain included because they can affect ids or decoding;
duplicate token text is rejected before identity. The spelling-promotion, scanner, and
special-trie rules are fixed by identity schema 1 and are not duplicated in the preimage. The
classifier identity is included because its Unicode category tables can change scanner output even
when all model arrays are identical.

The one-shot `crypto.sha256` input is built only after all size checks. `MAX_TOKENIZER_TEXT_BYTES`
plus checked per-entry prefixes bounds it. No identity cache or persisted tokenizer exists.

### 2.8 Resource and arithmetic bounds

| Constant | Value | Applies before | Reference-model observation / reason |
| --- | ---: | --- | --- |
| `MAX_TOKENIZER_ENTRIES` | 1,048,576 | materializing tokens or merges | 152,064 tokens; 151,387 merges; over 6x headroom without accepting R1's 4M shape into several indexes |
| `MAX_TOKENIZER_ITEM_BYTES` | 4,096 | cloning one token or merge | maximum token 256 bytes; maximum merge 257 bytes |
| `MAX_TOKENIZER_TEXT_BYTES` | 16,777,216 | building indexes or identity after summing both materialized arrays | observed token bytes 1,374,166 plus merge bytes 1,520,452; cap is over 5.7x combined |
| `MAX_HASH_BUCKET_ENTRIES` | 16 | token/merge index insertion or lookup | reference token buckets peak at 5 and merge-id-pair buckets at 6 |
| `MAX_SPECIAL_TOKENS` | 256 | building the special trie | 23 effective candidates after `</s>` promotion; over 11x headroom |
| `MAX_SPECIAL_TOKEN_BYTES` | 32 | inserting or probing a special candidate | observed maximum 20 bytes |
| `MAX_SPECIAL_TRIE_NODES` | 8,193 | allocating dense trie columns | root plus `256 * 32`; exact structural ceiling |
| `MAX_OPERATION_INPUT_BYTES` | 1,048,576 | reading text or token JSON | enough for repository prompts; prevents a CLI typo from becoming unbounded tokenizer state |
| `MAX_OPERATION_TOKEN_IDS` | 1,048,576 | decoding or publishing ids | one id per input byte is the normal worst case; atomic specials cannot increase it |
| `MAX_OPERATION_OUTPUT_BYTES` | 1,048,576 | appending decoded raw bytes | repeated maximum-size token ids otherwise amplify a bounded id array into gigabytes |
| `MAX_DETAIL_BYTES` | 256 | publishing an error result | matches existing R1/R2 bounded-detail convention |

Every addition and multiplication involving a file count, text length, hash-table capacity, heap
capacity, trie capacity, JSON capacity, or identity-preimage capacity is checked before formation.
Token and merge indexes each use the smallest power-of-two bucket-head array at least twice their
entry count, never over 2,097,152 heads, plus one next-link per entry. A bucket holds at most 16
entries; the seventeenth distinct key is a recoverable model rejection. Token insertion and lookup
therefore perform at most 16 length checks and complete-byte comparisons. Since complete bytes are
compared only after equal length and combined tokenizer text is at most 16 MiB, token insertion plus
the three token lookups per merge read at most 64 times that combined text in complete equality
checks — at most 1 GiB — rather than quadratic input. Hashing is another fixed linear pass. Merge
then indexes only a pair of Copy token ids; operation-time merge lookup is at most 16 Copy-pair
checks. The reference model's exact bucket peaks, measured with the hashes in section 3.4, are 5
and 6.

The special trie has exactly 256 `i64` transition slots per node, so its complete transition column
is at most 2,097,408 entries (16,779,264 bytes), plus two 8,193-entry terminal-id columns. Partition
performs at most
`MAX_OPERATION_INPUT_BYTES * MAX_SPECIAL_TOKEN_BYTES = 33,554,432` transition reads; candidate
count cannot multiply that work. A BPE word of `b` source bytes has at most `b` initial symbols, at
most `b-1` accepted merges, and fewer than `3b` queued candidates; the five Copy-scalar heap
columns are reserved only after proving that bound, and its fewer than `3b` merge-index lookups
perform fewer than `48b` Copy-pair checks. All counts fit `i64` by several orders under the declared
caps.

The admitted maxima make every capacity arithmetic result representable. A checked-arithmetic
failure while forming an index, heap, trie, JSON buffer, or identity preimage is therefore an
internal invariant violation, not a model-dependent recoverable result. Actual allocation failure
follows Align's terminal OOM policy; it is not converted into a data error. All accepted
attacker-controlled dimensions are nevertheless bounded before allocation.

### 2.9 Errors and first-failure publication

`error_detail` is truncated at a UTF-8 boundary to 256 bytes. Every `n`, `m`, `a`, `b`, `c`, or `i`
below is shortest unsigned decimal with no separator other than the shown punctuation. Step 6 tests
`tokens[n]`, then `tokens[n]types[m]`, then `merges[n]`; later conditions cannot replace the first
failure. These codes are exhaustive:

| Code | First condition | Detail |
| --- | --- | --- |
| `R7_GGUF` | complete table has structural error | `<gguf-code>@<offset>` |
| `R7_TOKENIZER_METADATA` | required key absent or wrong GGUF class | key |
| `R7_UNSUPPORTED_TOKENIZER` | model/pre value differs | `<model>/<pre>` |
| `R7_VOCAB_SIZE` | declared token count is zero or over cap; otherwise token-type count differs or is over cap | `tokens[n]` for token range; otherwise `tokens[n]types[m]` |
| `R7_MERGE_COUNT` | declared merge count is over cap | `merges[n]` |
| `R7_TOKENIZER_ARRAY` | selected payload cannot be materialized | key |
| `R7_TOKENIZER_TEXT_SIZE` | combined token and merge string bytes exceed 16,777,216 | `tokens[a]merges[b]total[c]` |
| `R7_TOKEN_EMPTY` | empty vocabulary entry | `token[i]` |
| `R7_TOKEN_TYPE` | token type outside 1 through 6 | `token[i]type[n]` |
| `R7_TOKEN_DUPLICATE` | token text duplicates an earlier id | `token[i]` for the later id |
| `R7_HASH_BUCKET` | seventeenth distinct token or merge key hashes to one bucket | `token[i]` or `merge[i]` |
| `R7_SPECIAL_COUNT` | effective special candidate count exceeds 256 | decimal count |
| `R7_SPECIAL_TEXT` | effective special candidate exceeds 32 UTF-8 bytes | `token[i]` |
| `R7_TOKEN_TEXT` | NORMAL text contains a non-alphabet scalar or BYTE spelling is not exact | `token[i]` |
| `R7_MERGE` | malformed merge entry | `merge[i]` |
| `R7_MERGE_TOKEN` | merge left, then right, then concatenated result text is absent from the token index | `merge[i]left`, `merge[i]right`, or `merge[i]result` |
| `R7_BYTE_ALPHABET` | one GPT-2 byte scalar has no NORMAL token | `byte[n]` |
| `R7_TEXT_SIZE` | encode text exceeds 1 MiB | decimal bytes |
| `R7_TOKEN_COUNT` | decode id count exceeds cap | decimal count |
| `R7_TOKEN_ID` | id negative or not below vocabulary size | `token[i]id[n]` |
| `R7_OUTPUT_SIZE` | the next decoded piece would exceed 1 MiB | decimal attempted bytes |
| `R7_DECODE_UTF8` | complete decoded byte stream is not valid UTF-8 | `output` |

Model validation steps 2 through 17 always precede operation validation. After a successful load,
`encode_model` checks text byte length before partition or BPE. `decode_model` checks token count,
then every id in ascending input position, then appends pieces with the output cap, then validates
whole-result UTF-8. Thus the first bad id precedes every output-size/UTF-8 fault, the first attempted
oversize append precedes final UTF-8, and no later operation condition replaces an earlier one.

On a model-validation failure before step 7, `tokenizer_id=""`, vocabulary and merge counts are
`-1`, and output is empty. `TokenTextResult.token_count` is nevertheless the supplied array length
for every outer-`Ok` result; it is not a processed-prefix count. Once one model-array count is
trusted, that count is retained in its result field; identity stays empty until the complete
preimage is hashed. An operation failure after load retains identity and both model counts. There is
no partial token-id array or partial text in an error result.

### 2.10 Prerequisites and metrics

| Prerequisite | State |
| --- | --- |
| R0 GGUF decoder and R1 first-key accessors | shipped |
| R6 token-id runtime and frozen prompt corpus | shipped |
| Align Request 22 | blocking; `PROPOSED` at contract publication |
| `std.regex` Unicode `\p{L}`, `\p{N}`, and `\s` classifiers | shipped; exact dependency identity is in 2.7 and no look-around is required by section 3.2 |
| `std.crypto.sha256`, `std.encoding`, bounded buffer append, and raw stdout writer | shipped |
| pinned llama.cpp tokenizer | `.llama-revision`, build 10566 commit `bb4caa754`; qualification only |

The capability makes no performance claim and therefore records no cost gate. Owner evidence may
report model-load time, encode time, decode time, total allocated strings, and output ids as
characterization only. The primary product metric remains time to a passing patch and is not
claimed by this capability.

## 3. Algorithm contract and provenance

### 3.1 The observed reference model

The reference file is
`qwen2.5-coder-7b-instruct-q4_k_m.gguf` (the same model R1 and dense R5/R6 use), exactly
4,683,073,536 bytes with SHA-256
`509287f78cb4d4cf6b3843734733b914b2c158e43e22a7f4bf5e963800894d3c`. A bounded metadata probe on
2026-08-31 observed:

| Field | Value |
| --- | ---: |
| vocabulary | 152,064 entries, 1,374,166 UTF-8 bytes, maximum 256 |
| token types | NORMAL 151,643; CONTROL 20; USER_DEFINED 2; UNUSED 399 |
| effective special candidates | 23 after `</s>` promotion; 298 total UTF-8 bytes; maximum 20 |
| merges | 151,387 entries, 1,520,452 UTF-8 bytes, maximum 257 |
| BOS / PAD | 151643, `<|endoftext|>` |
| EOS | 151645, `<|im_end|>` |
| `add_bos_token` | false |

The two USER_DEFINED strings are `<tool_call>` and `</tool_call>`. The twenty CONTROL strings are
ids 151643 through 151656 and 151659 through 151664. Ids 151665 through 152063 are UNUSED padding
entries. Pinned llama.cpp additionally promotes NORMAL id 128247, `</s>`, to CONTROL.

The implementation is transcribed against
[`src/llama-vocab.cpp`](https://github.com/ggml-org/llama.cpp/blob/bb4caa754/src/llama-vocab.cpp)
and
[`src/unicode.cpp`](https://github.com/ggml-org/llama.cpp/blob/bb4caa754/src/unicode.cpp)
at that exact commit. The former owns Qwen2 regex selection, BPE rank/left tie order, special
partition, and token-to-piece rules; the latter owns the custom Qwen2 scanner and GPT-2 byte map.
The qualification compares behavior, not source resemblance.

### 3.2 Qwen2 pre-tokenization without look-around

The normative Qwen2 expression is:

```text
(?:'[sS]|'[tT]|'[rR][eE]|'[vV][eE]|'[mM]|'[lL][lL]|'[dD])
|[^\r\n\p{L}\p{N}]?\p{L}+
|\p{N}
| ?[^\s\p{L}\p{N}]+[\r\n]*
|\s*[\r\n]+
|\s+(?!\S)
|\s+
```

`std.regex` deliberately omits look-around, so the source does **not** compile an approximation of
that expression. It ports the pinned `unicode_regex_split_custom_qwen2` state machine:

1. split one valid UTF-8 raw fragment into scalar byte spans;
2. compile and reuse exactly three one-scalar classifiers: `^\p{L}$`, `^\p{N}$`, and `^\s$`;
3. scan in the seven alternatives' order, case-folding only ASCII `S/T/R/E/V/M/L/D` for
   contractions;
4. a number always forms one piece;
5. the newline branch consumes through the last CR or LF in the current whitespace run;
6. a non-terminal whitespace run longer than one emits all but its final scalar, reproducing
   `\s+(?!\S)`; the next iteration may attach that scalar to the following piece;
7. terminal or single whitespace uses the final `\s+` branch;
8. a scalar matching no class becomes one piece, so progress is total.

Scalar categories, not ASCII approximations, decide letters, numbers, and whitespace. Combining
marks are not letters in Qwen2 and therefore do not silently join the preceding letter. Partition
restarts for every raw fragment around an atomic special. Section 2.7's `classifier_id` binds the
three compiled classifier semantics into tokenizer identity; the owner refuses a managed Align
checkout whose locked regex dependency identities differ.

### 3.3 GPT-2 byte alphabet

Each pre-token piece is transformed byte-for-byte, after splitting:

- bytes `0x21..0x7e`, `0xa1..0xac`, and `0xae..0xff` map to the Unicode scalar with the same value;
- every remaining byte, in ascending byte order, maps to successive scalars beginning at U+0100.

The implementation constructs UTF-8 from the numeric scalar with checked one-, two-, or three-byte
encoding and validates the resulting view before BPE. The reverse table is exact and total over
those 256 scalars. No locale, normalization, replacement character, or lossy conversion exists.

### 3.4 Indexes and BPE

The private tokenizer owns the three GGUF arrays plus Copy-scalar indexes:

- a token bucket-head array plus one next-link per vocabulary id, keyed by FNV-1a-64 of token bytes;
- a merge bucket-head array plus next-link, left-id, right-id, and result-id columns per first-ranked
  merge, keyed by FNV-1a-64 of `u64le(left_id) || 0xff || u64le(right_id)`;
- one `merge_split: array<i64>` giving each original merge's first separator byte;
- one dense byte trie with 256-way `special_next: array<i64>` transitions and separate
  `special_parse_terminal` / `special_literal_terminal` id columns;
- the fixed 256 byte-to-token ids.

FNV-1a-64 uses offset basis `14695981039346656037` and prime `1099511628211`, wrapping unsigned
64-bit multiplication after every byte. A bucket is `hash & (bucket_count - 1)`. Token insertion
scans the existing chain, comparing length before complete bytes; a duplicate wins over the bucket
cap, otherwise the seventeenth distinct entry is `R7_HASH_BUCKET`. Merge construction resolves the
left text, right text, and their concatenation through that bounded token index before hashing the
Copy id pair. The concatenated lookup hashes and compares the two borrowed spans in sequence; it
does not allocate a joined string. An existing pair keeps its first rank; otherwise its seventeenth
distinct bucket entry is `R7_HASH_BUCKET`. Insertion prepends the accepted entry. Every lookup stops
after 16 links; because no accepted inserted key lies deeper, absence after that scan is
authoritative.

Hash equality never establishes token-text equality: complete bytes decide. Pair equality uses the
two complete token ids, whose text is unique. The fixed hashes are implementation indexes only;
`tokenizer_id` is SHA-256 and no persisted/cache/wire field contains FNV output or bucket layout.
Pinned llama.cpp can limp past a merge whose component/result text is absent and later fall back to
smaller pieces; R7 instead rejects that malformed model as `R7_MERGE_TOKEN`. The reference model has
zero such rows, and all accepted merges therefore carry their result id directly.

For each byte-encoded pretoken:

1. make one linked symbol per mapped byte, represented by Copy token id, `length`, `prev`, and
   `next` columns;
2. add every adjacent pair present in the merge index to a min-heap;
3. heap order is lower rank first, then lower left symbol index;
4. a heap entry records both original symbol lengths and is stale if either is zero, lengths
   changed, or the pair is no longer adjacent;
5. merge a valid pair by replacing the left symbol's id with the merge row's prevalidated result id,
   adding the lengths, unlinking the right, and enqueueing only the new left and right adjacencies;
6. walk remaining symbols in order and emit their already-valid token ids.

The heap is five mutable Copy-scalar arrays: rank, left symbol, right symbol, original left length,
and original right length. It stores no borrowed view and remains valid across symbol mutation.
Merge lookup compares Copy id pairs and never rehashes a growing symbol string. This is the pinned
llama.cpp priority rule, including the left-index tie breaker; greedy left-to-right merge without a
heap is not equivalent and is forbidden.

### 3.5 Special partition

The loader inserts effective candidates into a dense byte trie in ascending id order. A node has
256 `i64` transition slots initialized to `-1`; the root is node zero, and at most one node is
created per candidate byte. Each node also has two terminal ids initialized to `-1`. Token-text
uniqueness means each enabled terminal is written at most once. CONTROL/UNKNOWN write only the
parse terminal; USER_DEFINED writes both. UNUSED never enters the trie.

Partition maintains one raw-span start and scans input byte positions left-to-right. At each
position it walks at most `MAX_SPECIAL_TOKEN_BYTES` trie transitions, recording the deepest enabled
terminal for the selected mode. If a terminal was found, it tokenizes the preceding raw span once,
appends the recorded id, and resumes after the complete matched bytes; otherwise it advances the
input position by one byte without tokenizing yet. The final raw span is tokenized once. Thus the
deepest terminal gives longest-byte match, and a disabled CONTROL/UNKNOWN spelling flows through
ordinary Qwen2 BPE. USER_DEFINED remains atomic in both encode modes. Adjacent raw spans are never
recombined across an atomic id.

This trie is a deliberate bounded replacement for pinned llama.cpp's candidate-by-candidate
partition loop. Section 2.8 proves its node, allocation, and transition-work ceilings. The hosted
owner covers common-prefix candidates at exact count/length/input maxima, so neither the number of
accepted candidates nor adversarial shared prefixes can multiply work beyond that ceiling.

### 3.6 Decode

After the id-count cap is accepted, ids are validated in order before any output is published. For
each id:

- UNKNOWN and CONTROL append stored token text only in `RenderControl`;
- USER_DEFINED always appends stored token text;
- UNUSED appends nothing;
- NORMAL maps every GPT-2 alphabet scalar in stored token text back to its one raw byte;
- BYTE requires exact `<0xHH>` ASCII spelling and appends that byte; malformed spelling is a
  model-load `R7_TOKEN_TEXT` failure rather than a decode-time guess.

All ids are range-validated before allocation. Before each raw piece append, checked arithmetic
proves the new length is at most `MAX_OPERATION_OUTPUT_BYTES`; the first excess is
`R7_OUTPUT_SIZE`. Only after every id is processed does `bytes.as_str()` validate the entire
sequence. Failure is `R7_DECODE_UTF8` with no partial text. There is no leading-space removal and
`clean_up_tokenization_spaces` is false, matching Qwen2.

For every accepted UTF-8 text `x` whose encoded sequence contains no UNUSED id, both of these are
owner properties:

```text
decode(encode(x, ParseControl), RenderControl) == x
decode(encode(x, LiteralControl), RenderControl) == x
```

The condition is necessary: UNUSED participates in ordinary BPE but decode suppresses it, so a
synthetic accepted model can intentionally make one such spelling non-reversible. The hosted owner
pins that counterexample instead of claiming a universal inverse. The conditional properties are
not a substitute for id parity: the real-model qualification separately requires the encoded id
array to equal pinned llama.cpp.

## 4. Acceptance and verification

### 4.1 Hosted owner: `make tokenizer-smoke`

`scripts/tokenizer_fixture.py` builds bounded GGUF v3 files at runtime. Its positive Qwen2 fixture
contains the complete 256-entry GPT-2 byte alphabet, selected ASCII/Unicode merges, CONTROL,
USER_DEFINED, UNUSED, BYTE, and a NORMAL `</s>` promotion case. An independent Python oracle owns
the expected split, byte map, rank queue, special partition, and decode bytes; it imports no Align
source and reads no product-generated expectation.

`scripts/run-tokenizer-smoke` exercises both public APIs through both CLI arms and asserts:

- empty, ASCII, mixed-case contractions, one-digit splitting, leading/terminal whitespace runs,
  CR/LF mixtures, punctuation, embedded NUL, CJK, combining marks, emoji, and 4-byte scalars;
- BPE rank conflicts and equal-rank left-index order;
- parse/literal control, USER_DEFINED in both modes, UNUSED suppression, `</s>` promotion, and
  render/skip control;
- encode/decode round trips plus arbitrary valid and invalid id streams;
- one BPE-reachable UNUSED token whose encode/decode pair demonstrates the documented non-roundtrip;
- exact canonical token JSON and exact no-newline decoded stdout;
- arity, mode, path, invalid JSON, oversize input, and zero stdout for every pre-write failure;
- first-key wins, duplicate-token rejection, duplicate merge first-wins, exact combined tokenizer
  text cap, and token/merge bucket acceptance at 16 versus rejection at 17 distinct colliders;
- exact special count/length rejection boundaries, prefix trie matching, and a 1 MiB
  adversarial-prefix case that completes within the owner timeout with expected output;
- the managed Align checkout's exact three regex lock identities from 2.7 before product compile;
- every error code in 2.9 through missing/wrong arrays, declared count mismatch, text/bucket caps,
  invalid UTF-8, empty/duplicate token, invalid type, malformed or unresolved merge/BYTE, missing
  byte alphabet, bad id, output cap, and invalid final UTF-8;
- complete cleanup by repeated success/failure under the repository's available leak/lifetime
  probes; no fixture or temporary file remains after the runner exits.

The fixture needs no model, network, reference tool, GPU, or special host. It runs in seconds and
joins `HOSTED_CHECK_TARGETS` as the narrow durable owner.

### 4.2 Real-model qualification: `make tokenizer-parity`

The focused qualification uses exactly:

- `ALIGN_LLM_GGUF_MODEL`, the 4,683,073,536-byte Qwen2.5-Coder-7B Q4_K_M model with SHA-256
  `509287f78cb4d4cf6b3843734733b914b2c158e43e22a7f4bf5e963800894d3c`;
- `ALIGN_LLM_LLAMA_TOKENIZE`, expected to be pinned `llama-tokenize` build 10566 commit
  `bb4caa754`.

Either variable unset or naming an absent file prints one explicit `N/A` line and exits zero. A
named model with the wrong byte length or SHA-256, wrong tool version, tool failure, malformed
output, timeout, or mismatch is a hard failure. Every reference invocation has a 120-second
subprocess timeout; the fixed corpus has no separate target-wide timeout. The target stays outside
`HOSTED_CHECK_TARGETS`, `CAPABLE_ONLY_CHECK_TARGETS`, and every aggregate.

The parity corpus is frozen independently of product output. Its first 16 cases are the following
exact UTF-8 byte strings, in row order. `-` is the zero-byte string; every other cell is lowercase
hex with no separator. These rows, rather than the category labels in section 4.1, are normative.

| Case | Exact UTF-8 bytes |
| --- | --- |
| `00-empty` | `-` |
| `01-ascii` | `48656c6c6f2c20776f726c6421` |
| `02-contractions` | `49276d2049274d207765276c6c205745274c4c206865276420484527442063616e27742043414e2754` |
| `03-digits` | `61313233343562` |
| `04-whitespace` | `20616c706861202062657461202020` |
| `05-newlines` | `610d0a200a0d0a62` |
| `06-punctuation` | `666f6f2e2e2e3f21202d2d20626172` |
| `07-nul` | `610062` |
| `08-cjk` | `e6bca2e5ad97e3818be381aae382abe3838a` |
| `09-combining` | `65cc8120636166c3a9` |
| `10-emoji` | `f09f91a9e2808df09f92bbf09f9a80` |
| `11-four-byte` | `f0908d88f48fbfbf` |
| `12-control-boundary` | `783c7c696d5f73746172747c3e79` |
| `13-adjacent-controls` | `3c7c696d5f73746172747c3e3c7c696d5f656e647c3e` |
| `14-mixed-specials` | `3c746f6f6c5f63616c6c3e3c7c696d5f656e647c3e3c2f746f6f6c5f63616c6c3e` |
| `15-promoted-control` | `613c2f733e62` |

The next 23 cases are the exact effective-special spellings below in ascending id order. The table
also makes the Qwen2 `</s>` promotion and USER_DEFINED membership independently auditable rather
than deriving the parity inputs from Align output.

| Id | Original type | Exact spelling |
| ---: | --- | --- |
| 128247 | NORMAL, promoted CONTROL | `</s>` |
| 151643 | CONTROL | `<|endoftext|>` |
| 151644 | CONTROL | `<|im_start|>` |
| 151645 | CONTROL | `<|im_end|>` |
| 151646 | CONTROL | `<|object_ref_start|>` |
| 151647 | CONTROL | `<|object_ref_end|>` |
| 151648 | CONTROL | `<|box_start|>` |
| 151649 | CONTROL | `<|box_end|>` |
| 151650 | CONTROL | `<|quad_start|>` |
| 151651 | CONTROL | `<|quad_end|>` |
| 151652 | CONTROL | `<|vision_start|>` |
| 151653 | CONTROL | `<|vision_end|>` |
| 151654 | CONTROL | `<|vision_pad|>` |
| 151655 | CONTROL | `<|image_pad|>` |
| 151656 | CONTROL | `<|video_pad|>` |
| 151657 | USER_DEFINED | `<tool_call>` |
| 151658 | USER_DEFINED | `</tool_call>` |
| 151659 | CONTROL | `<|fim_prefix|>` |
| 151660 | CONTROL | `<|fim_middle|>` |
| 151661 | CONTROL | `<|fim_suffix|>` |
| 151662 | CONTROL | `<|fim_pad|>` |
| 151663 | CONTROL | `<|repo_name|>` |
| 151664 | CONTROL | `<|file_sep|>` |

The following four prompt cases reuse the already-frozen R6 `prefix-corpus-v1` byte identities,
not a newly selected "canonical prompt." Before tokenization the runner executes
`python3 scripts/check-prefix-corpus`, reconstructs each complete prompt from the manifest's named
source `text` fields with the composition rule in `scripts/check-prefix-corpus`, and requires this
exact row order, byte count, and SHA-256:

| Entry id | Bytes | Complete-prompt SHA-256 |
| --- | ---: | --- |
| `shared-prefix` | 1,733 | `3c2e3a26638ea3958a2edb57f7dbf65a11fe4a7496b7eebfc3c3602f0e5ca604` |
| `duration-half-away-from-zero.initial.suffix` | 4,711 | `00aa28784d5a3a2078b328882d7778d04fdbb8276025f8fe301da5f166c5a9b3` |
| `layer-precedence-frozen-module.initial.suffix` | 6,506 | `17efb05144ba8724e2e8efa37bddc82a76957cd7d6e00f21c178394cfe375aa3` |
| `record-codec-round-trip.initial.suffix` | 5,545 | `09273a5180788584c7dd7518581defc669646797a7b118d325f18337ecb242e8` |

The final 256 cases are numbered `unicode-000` through `unicode-255`. They use
`splitmix64-v1`, initial state `0x52375157454e3231`, and unsigned 64-bit wrap. Its exact
`next_u64()` is:

```text
state = state + 0x9e3779b97f4a7c15
z = state
z = (z xor (z >> 30)) * 0xbf58476d1ce4e5b9
z = (z xor (z >> 27)) * 0x94d049bb133111eb
return z xor (z >> 31)
```

Each case has `1 + next_u64() % 64` scalars; each scalar candidate is
`next_u64() % 0x110000`, retrying only `0xd800..0xdfff`. This fixes seed, generator, case count,
lengths, scalar domain, rejection rule, and order independently of Python's PRNG or Unicode tables.
Thus the corpus has exactly 299 cases in the order above: 16 fixed byte rows, 23 exact special rows,
4 frozen R6 prompts, and 256 generated Unicode rows. The runner fails before either tokenizer when
any table spelling, special id/type/text read independently from the pinned model, prompt identity,
case count, or generated bytes differ. For every case:

- `ParseControl` ids equal
  `llama-tokenize -m MODEL --stdin --ids --no-bos --no-escape`; build 10566's tokenize-specific
  default parses control tokens and exposes no positive `--parse-special` option;
- `LiteralControl` ids equal
  `llama-tokenize -m MODEL --stdin --ids --no-bos --no-escape --no-parse-special`;
- Align `RenderControl` of either exact reference id list equals the original UTF-8 bytes;
- `SkipControl` equals the independent expected filtering of effective CONTROL/UNKNOWN ids;
- repeated Align runs publish the same ids, text, counts, and `tokenizer_id`.

The runner records tool version, model SHA-256, tokenizer identity, case count, input bytes, output
ids, and first mismatch. It never copies the model or writes model-derived vocabulary into Git.

### 4.3 Align Request 22 adoption owners

The same executable capability closes all previously named real-client targets of Request 22:

1. `src/gguf.align` replaces the NUL-separated `TensorRow.json_prefix` stream with a directly
   indexed owned record array; `make gguf-smoke` passes.
2. `GgufTable`, each frontend `BlockPlan`, and `model_forward.StepColumns` replace their documented
   Move-field stream-plus-column workarounds behind unchanged public accessors; `make model-ir-smoke`
   and `make layer-forward-smoke` pass with unchanged semantic goldens.
3. `gguf.read_string_array` and the tokenizer use ordinary borrowed Move-element indexing;
   `make tokenizer-smoke` and `make tokenizer-parity` pass.

The migrations are representation changes only. They may not change R0/R1/R5/R6 documents,
goldens, field order, error precedence, hashes, or runtime arithmetic. If one cannot be performed
without public behavior change, Request 22 stays short of `ALIGN_LLM_VERIFIED` and the difference
returns to its register rather than being hidden in R7.

### 4.4 Publication gate

After a coherent implementation batch:

```text
make fmt
make gguf-smoke model-ir-smoke layer-forward-smoke tokenizer-smoke
make tokenizer-parity
python3 scripts/pre-pr --owner-test R7-TOKENIZER -- make gguf-smoke model-ir-smoke layer-forward-smoke tokenizer-smoke
```

Adding `tokenizer-smoke` to `HOSTED_CHECK_TARGETS` changes aggregate membership, so `make ci` is
also required once on a capable authenticated fresh worker, either directly where allowed or as
the exact hosted workflow evidence selected by preflight. `scripts/pre-pr --plan` is not evidence.
The final successful stamp, owner evidence, request lifecycle state, and comprehensive review must
all bind the unchanged final head.

## 5. Closure matrix

`S` is success, `F` a recoverable operation failure, `M` malformed/untrusted input, `E` early exit,
and `C` cleanup. Every applicable cell names its implementation and exact regression owner before
coding.

| Owner / path | Construction | S | F / M | E | C | Regression |
| --- | --- | --- | --- | --- | --- | --- |
| `src/gguf.align`: array offsets/accessor | Complete `read_table` records first-key array type and payload offset from the one decoder | Borrowed lookup returns exact type | Invalid/absent/wrong-type key is `-1`; structural table status remains data | Invalid key returns before lookup; no payload open before table success | temporary columns/table drop | `tokenizer-smoke`: invalid/first-key/wrong-type/structural corpus; `gguf-smoke` parity |
| `src/gguf.align`: `read_string_array` | Reopen selected bounded payload only after complete validation | owned strings, file order | invalid key/UTF-8/truncation/cap is `Invalid` | invalid key before path; stop materialization at first bad element | file/window/partial builder drop | `tokenizer-smoke`: invalid key, early/tail invalid strings, truncation, caps |
| `src/gguf.align`: `read_i32_array` | same selected-offset route | sign-extended owned `i64` values | invalid key/wrong width/truncation/cap is `Invalid` | invalid key before path; first bad scalar | same | `tokenizer-smoke`: invalid key, types positive/wrong/truncated |
| Request 22 migrations | Build direct Move-record/string arrays | unchanged accessors/documents | existing failure documents unchanged | existing first-failure order | element-wise Drop exactly once | `gguf-smoke`, `model-ir-smoke`, `layer-forward-smoke` |
| `src/tokenizer_qwen2.align`: loader | tokens, types, merges in step order; checked tables, trie, and identity | private immutable tokenizer | first code in 2.3/2.9, no partial output | no later index after failure | all arrays/regex/index/trie/preimage state drop | `tokenizer-smoke` full model matrix |
| token hash index | ascending ids into head/next buckets; 16-link cap | complete-string lookup within 16 links | duplicate is `R7_TOKEN_DUPLICATE` before distinct-entry `R7_HASH_BUCKET`; hash never equals without byte compare | no seventeenth insertion or lookup | Copy heads/links drop | exact 16/17 colliders, duplicate precedence, ordinary collision fixture |
| merge hash index | resolve left/right/result ids, then insert first-ranked Copy pair into 16-link bucket | first rank and prevalidated result id | missing component/result is `R7_MERGE_TOKEN`; duplicate ignored before distinct-entry `R7_HASH_BUCKET` | malformed/unresolved row before insert; no seventeenth insert | Copy id/head/link arrays drop; strings stay owned by merges | missing left/right/result, exact 16/17 colliders, rank/duplicate cases |
| special trie/partition | ascending unique ids into checked dense transitions and two mode terminals | longest atomic match within 32 probes per position | count/length cap errors; disabled control flows to BPE | raw segment flush before atomic id | trie and raw-span scratch drop | all modes, overlaps, exact maximum common-prefix case |
| Qwen2 scanner | exact managed-regex identity, scalar spans, then three compiled classifiers | ordered complete pieces | lock mismatch rejects in the owner; invalid UTF-8 cannot enter from `str` | total fallback advances one scalar | regex handles/scalar columns drop | lock-identity check + lexical category table + seeded cases |
| GPT-2 byte map | fixed numeric map, validated byte alphabet | reversible mapped bytes | missing/mistyped byte token is load error | first missing byte | fixed Copy tables drop | all 256 bytes and multilingual roundtrip |
| BPE heap | one token id per mapped byte, adjacent Copy-id candidates | rank/left exact ids; merge carries result id | accepted-model pair lookup is bounded and total | stale candidates skipped without mutation | id/symbol/heap scratch drops per piece | rank conflict, stale heap, long word, fewer-than-48b pair-check ceiling |
| decode | validate ids, append pieces to a 1 MiB-bounded raw buffer | whole valid UTF-8 string | bad id precedes output cap; first oversize append is `R7_OUTPUT_SIZE`; invalid final UTF-8 is data error | no partial result | raw buffer/private tokenizer drop | negative/high ids, exact/over output cap, byte fragments, modes |
| public result construction | empty error result first, fill only at settled transitions | identity/count/output coherent | output empty, known metadata retained | one first code | result alone transfers | all error rows and repeat loop |
| `src/main.align` | arity/mode/path, model, bounded input, operation | one stdout write | product/pre-write failure has zero stdout; sink failure may retain a prefix and propagates OS status/signal | cheap validation prevents file work | readers/buffers/results drop | CLI matrix, byte-exact success, zero stdout for pre-write failures |
| `scripts/tokenizer_fixture.py` | temporary independent GGUF and manifest | deterministic corpus | explicit mutants one root cause each | no committed/generated fixture | runner-owned temp trap | `make tokenizer-smoke` |
| `scripts/run-tokenizer-smoke` | managed compiler + fixture | all API/CLI assertions | refuses missing case/output and vacuous corpus | first command failure stops | trap removes temp tree | itself |
| `scripts/run-tokenizer-parity` | validates two opt-in operands, pin, 299-case frozen corpus, and R6 prompt manifest | exact ids/roundtrips | wrong pin/tool/model/corpus/mismatch hard fails | absent prerequisite one N/A line | temporary inputs/results removed | `make tokenizer-parity` |
| `Makefile` / topology | add two phony targets; hosted owner once | hosted graph reaches smoke | topology duplication/omission fails | parity never enters aggregate | N/A | `gate-topology-check`, `make ci` |

## 6. Risks and mitigations

1. **Unicode category drift.** Align's Rust regex Unicode tables and pinned llama.cpp's generated
   flags could differ on rare scalars. The scanner shape is exact, and qualification covers every
   category plus seeded Unicode, but that is not an exhaustive cross-implementation table proof.
   Align-side behavior is nevertheless reproducible: section 2.7 binds the exact regex engine and
   Unicode-table package checksums into `tokenizer_id`, and the owner rejects dependency drift. A
   demonstrated llama.cpp mismatch is a genuine standard-library/table dependency to record, not
   a reason to replace Unicode with ASCII.
2. **Move-array lifetime error.** Hundreds of thousands of strings make a shallow copied element a
   double-free risk. This is why Request 22 blocks source. Compiler tests plus repeated load/error
   owners must prove borrow-only reads and element-wise Drop.
3. **Hash collision or probe denial.** Hashes select buckets only; complete token bytes or Copy id
   pairs decide equality. Sixteen-link bucket caps bound every operation, the fixture covers exact
   16/17 distinct colliders and duplicate precedence, and the real-model peaks are recorded.
4. **Wrong BPE priority.** Selecting the first available pair or omitting stale checks can pass
   simple words. Rank conflicts, equal-rank left order, and stale candidates are separate owner
   cases, and real ids are compared exactly.
5. **Special-mode ambiguity.** llama.cpp uses “parse special” while USER_DEFINED remains parsed.
   The public names say control and the four-class table is normative. Build 10566 exposes only the
   negative CLI flag: its verified tokenize-specific default owns ParseControl, while
   `--no-parse-special` owns LiteralControl.
6. **Decode appears valid per token but fails jointly.** UTF-8 is validated after concatenating all
   pieces. The negative corpus includes individually incomplete byte pieces that become valid
   jointly and a sequence that remains invalid.
7. **Unbounded model amplification.** Counts, each item, combined token-plus-merge text, bucket work,
   tables, identity, operation input, ids, decoded output, canonical JSON, heap, and special-trie
   nodes/work all have checked caps. Outer GGUF validation happens first.
8. **Repeated model load.** Two public operations each load once. This capability makes no latency
   claim; a resident handle waits for a measured consumer and an opaque ownership surface.
9. **Oracle circularity.** The hosted Python oracle neither imports nor parses Align source. The
   real qualification uses the pinned llama.cpp executable for ids and byte equality for roundtrip;
   its 299 inputs are fixed by exact bytes, pinned model metadata, existing R6 identities, or the
   specified generator before either tokenizer runs.
10. **Aggregate creep.** Only the bounded synthetic owner joins hosted checks. The 4.4 GB model and
    external tokenizer stay opt-in.
11. **Malformed duplicate vocabulary.** Pinned llama.cpp mutates its lookup and then asserts, so
    there is no successful oracle result to imitate. R7 rejects the later id recoverably before
    identity/index publication and tests that exact divergence.

## 7. Deferred work

- chat-template parsing/rendering and role/message records;
- a resident tokenizer handle or cache keyed by `tokenizer_id`;
- `ModelProvider` backed by align-runtime;
- automatic BOS/EOS/EOG/stop handling;
- incremental detokenization and UTF-8 carry across generated tokens;
- sampling, streaming, and cancellation;
- other Qwen revisions, architectures, tokenizer models, pre-tokenizers, or normalization rules;
- memory/time optimization and any performance claim;
- a versioned generation artifact binding model, tokenizer, prompt, ids, logits, and decoded text.

Each is independently useful or a distinct failure domain. None is smuggled into this capability's
acceptance.

## 8. Align capability-request lifecycle

At design publication, Request 22 is `PROPOSED`, priority high, blocking R7-TOKENIZER. Its current
sibling evidence and requested language surface remain authoritative in
[`docs/align-requests.md`](../align-requests.md). This document adds no proposed Align spelling.

When Align merges:

- record the exact Align commit/PR in the request;
- update `.align-revision` and materialize the managed release compiler;
- use only the shipped borrow-index spelling;
- run the Align adoption owners in 4.3 plus this capability's owners;
- record exact commands/results before `ALIGN_LLM_VERIFIED`;
- close only after the shipped ownership limits and all three client targets are documented.

If Align chooses `arr.at(i)` rather than changing `arr[i]`, only implementation spelling changes.
The GGUF/tokenizer public surfaces, behavior, ownership, errors, CLI, and acceptance in this ledger
do not.

## 9. Author consistency pass

The author pass checks these statements as one contract:

1. Roadmap item 41, `HANDOFF.md`, Request 22, and this section all name the same active capability
   and blocking resume condition.
2. The public inventory in 2.1/2.2 exactly covers the CLI and no hypothetical Align surface.
3. Qwen2 regex and its locked classifier identity, bounded special-trie classification, duplicate
   rejection, bounded bucket indexes, byte map, BPE priority, decode rules, and the pinned oracle's
   tokenize-specific parse default match source and the 2026-08-31 reference-model observation.
4. Every malformed condition has one first code, one bounded detail, and a closure-matrix owner.
5. Every allocation and attacker-controlled loop has a preceding count/byte/capacity/work bound
   and one cleanup owner.
6. Token JSON, tokenizer identity, defaults, effects, persistence, cache identity, and metrics are
   explicit; genuinely inapplicable fields say why.
7. The hosted owner is aggregate-safe; the exact 299-case real-model parity corpus is opt-in;
   aggregate membership change names `make ci`.
8. Request 22 cannot reach `ALIGN_LLM_VERIFIED` from a pin update or tokenizer alone; all previously
   named migrations remain acceptance.

Result: consistent after the consolidated final-review redesign. Final ledger-to-diff
reconciliation remains pending until the blocked implementation exists.

## 10. Final ledger-to-diff mapping

Pending implementation. Before review of the executable candidate, replace this paragraph with a
table mapping every public ledger row and applicable closure-matrix cell to exact source, fixture,
runner, and passing evidence, plus explicit deviations or deferrals. A missing mapping is a missing
part of the capability, not review prose to fill later.
