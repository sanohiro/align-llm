# R7-PROMPT

Status: design active, 2026-09-01.

R7-TOKENIZER converts text and token ids, but the shipped runtime still starts at a caller-built
token-id list. The existing provider boundary starts with exactly two text messages,
`GenerationRequest.system` and `.user`. This capability closes the missing boundary between those
two surfaces for the dense Qwen2.5-Coder reference model: validate the chat template carried by the
same GGUF snapshot, render one system turn plus one user turn and the assistant generation prefix,
then encode the complete prompt with the shipped Qwen2 tokenizer.

The result is directly consumable as the `TOKENS` operand of `--decode-step`. This capability does
not yet add a provider enum arm, execute the model, sample non-greedily, stop on EOG, stream output,
or detokenize a completion. Those are later R7 boundaries.

## 1. Capability boundary

### 1.1 In scope

- dense Qwen2.5-Coder-7B-Instruct's model-carried chat template;
- the existing provider request's system and user messages, including empty strings, embedded NUL,
  and arbitrary valid UTF-8;
- no tools, no history, and `add_generation_prompt = true`;
- one retained `GgufSnapshot` for template metadata and tokenizer arrays;
- an owned public token result and the exact `--prepare-prompt` CLI token array;
- synthetic hosted ownership plus focused parity against pinned llama.cpp `/apply-template` and
  `llama-tokenize` when the reference prerequisites are supplied.

### 1.2 Out of scope

Jinja parsing; a template registry; a caller-supplied template; tools, tool results, assistant
history, or alternate roles; default-system injection; BOS/EOS insertion; truncation; prompt cache
lookup; pack or geometry loading; inference; sampling; EOG classification; completion decoding;
provider dispatch; streaming; timing or speed claims; Qwen variants with another template; and
every architecture other than Qwen2.

The implementation supports one exact semantic contract, not “any template containing ChatML
markers.” A different template is a recoverable unsupported-model result. Adding another template
requires its own identity, renderer, and parity corpus; it cannot silently reuse this renderer.

## 2. Public-contract ledger

This section is authoritative. Other normative prose must agree with it.

| Field | Contract |
| --- | --- |
| Capability | `R7-PROMPT` |
| Consumer | a caller needing the exact prompt token ids accepted by the shipped dense runtime |
| Owner module | `src/tokenizer_qwen2.align`; prompt construction stays beside the private tokenizer so template metadata and all tokenizer payloads share one snapshot |
| Public API | `prepare_prompt_model` and `PromptIdsResult` in section 2.1 |
| Public CLI | `main --prepare-prompt MODEL SYSTEM_FILE USER_FILE` |
| Inputs/defaults | three explicit paths at the CLI; API takes model path plus two strings; no default, environment read, or ambient template |
| Result | owned identities, counts, byte counts, and owned token-id array; CLI emits only canonical compact token JSON plus LF |
| Errors | OS/path errors use outer `Result`; model/operation errors use `PromptIdsResult.status=Error`; CLI maps any inner error to `Error.Invalid` before stdout |
| Ownership/allocation | one open GGUF snapshot; one cloned template scalar; the existing private tokenizer arrays/indexes; one bounded prompt builder; one owned result array |
| Cache/persisted identity | no cache and no persisted artifact; `template_id` and `tokenizer_id` identify the two model-carried inputs |
| Schema version | N/A: the CLI emits a JSON array, not an object schema; its exact lexical form is fixed below |
| Validation order | section 2.3 |
| Prerequisites | merged R7-TOKENIZER and `.align-revision` `27770420555d19b98eced133369c168e9c6d4a2f` |
| Acceptance | `make prompt-smoke`; focused `make prompt-parity`; section 4 |
| Metrics | N/A: no performance or resource improvement claim |

### 2.1 Public API

`src/tokenizer_qwen2.align` adds exactly:

```align
pub PromptIdsResult {
  status: TokenizerStatus,
  error_code: string,
  error_detail: string,
  template_id: string,
  tokenizer_id: string,
  vocab_size: i64,
  merge_count: i64,
  system_bytes: i64,
  user_bytes: i64,
  prompt_bytes: i64,
  token_ids: array<i64>,
}

pub fn prepare_prompt_model(
  model_path: str,
  system: str,
  user: str,
) -> Result<PromptIdsResult, Error>
```

The function borrows all three text inputs for the call and returns a fully owned result. It reads
only `model_path`; it performs no write, environment access, process execution, network access, or
global mutation. `system_bytes` and `user_bytes` always publish the two input lengths, including on
model failure. `prompt_bytes` is `0` until the complete rendered prompt size passes validation; it
then publishes that size on tokenizer failure and success. `template_id` becomes available after
the supported template is hashed. `tokenizer_id`, vocabulary size, and merge count follow
R7-TOKENIZER's existing publication rules. An error result owns an empty token array.

The outer `Result` carries path grammar and unchanged `std.fs` failures. It never wraps those as
data. All declared `R7_*` codes are inner recoverable data so API callers can distinguish an
unsupported model from I/O failure.

### 2.2 Supported template and exact rendering

The accepted `tokenizer.chat_template` is exactly 2,509 UTF-8 bytes with SHA-256:

```text
d5495a1e5db0611132a97e46a65dbb64a642a499421228b9c8b93229097fa9a4
```

That is the value in the reference GGUF whose model digest is
`509287f78cb4d4cf6b3843734733b914b2c158e43e22a7f4bf5e963800894d3c`. The hash is
over the complete scalar bytes, including its final LF. `template_id` is that lowercase hash.
Length equality is not support; hash equality is required.

For this capability's fixed message shape (`tools` absent, first message system, second message
user, generation prompt true), the template renders exactly the following concatenation with no
escaping, normalization, trimming, BOS, EOS, or extra LF:

```text
<|im_start|>system\n
SYSTEM
<|im_end|>\n
<|im_start|>user\n
USER
<|im_end|>\n
<|im_start|>assistant\n
```

`SYSTEM` and `USER` above are their exact input bytes. The five fixed fragments total 80 bytes.
The complete prompt is encoded with `EncodeSpecials.ParseControl`, so the template delimiters use
their model-carried control ids. Delimiter spellings inside message content follow the same parsing
rule, matching whole-prompt llama.cpp tokenization; this capability does not claim an injection
boundary.

### 2.3 Validation order and error vocabulary

`MAX_CHAT_TEMPLATE_BYTES = 4,096` and `MAX_PROMPT_BYTES = 1,048,576`. Validation is strictly:

| Step | Check | Result |
| ---: | --- | --- |
| 1 | `model_path` satisfies R7-TOKENIZER's path grammar | outer `Err(Error.Invalid)` |
| 2 | open one `GgufSnapshot` and complete structural table validation | unchanged `R7_GGUF`, `code@offset` |
| 3 | first `tokenizer.chat_template` exists as valid GGUF STRING | `R7_CHAT_TEMPLATE_METADATA`, exact key |
| 4 | template byte length is at most 4,096 | `R7_CHAT_TEMPLATE_SIZE`, decimal byte length |
| 5 | complete template SHA-256 equals section 2.2 | `R7_UNSUPPORTED_CHAT_TEMPLATE`, `sha256[64hex]` |
| 6 | `system.len + user.len + 80` is representable and at most 1,048,576 | `R7_PROMPT_SIZE`, `system[a]user[b]prompt[c]`; `c=-1` if addition is unrepresentable |
| 7 | load and validate the tokenizer through the same snapshot | unchanged R7-TOKENIZER model code/detail and known counts |
| 8 | render the five fixed fragments and two inputs to exactly the validated size | terminal OOM only; a size mismatch is `R7_PROMPT_RENDER`, `bytes[n]` |
| 9 | encode the whole prompt with parse-control mode | unchanged `R7_TOKEN_COUNT` if the encoded array exceeds its cap; otherwise success |

Step separation is observable. A model with both a wrong template and malformed tokenizer reports
the template failure. Oversized inputs beat malformed tokenizer arrays after the supported
template is established. Within step 7, R7-TOKENIZER's existing sixteen-stage precedence is
unchanged. No later stage replaces an earlier code.

These are the only new codes:

| Code | Meaning |
| --- | --- |
| `R7_CHAT_TEMPLATE_METADATA` | template key absent, wrong GGUF class, or invalid scalar text |
| `R7_CHAT_TEMPLATE_SIZE` | template exceeds 4,096 bytes |
| `R7_UNSUPPORTED_CHAT_TEMPLATE` | bounded valid template does not have the supported complete hash |
| `R7_PROMPT_SIZE` | rendered prompt would exceed 1 MiB or its size is not representable |
| `R7_PROMPT_RENDER` | builder output length differs from the already validated arithmetic size |

`R7_PROMPT_RENDER` is a checked internal invariant, not a model-input condition. Keeping it in the
recoverable result makes a future fragment edit fail closed instead of passing an incorrectly sized
prompt to the tokenizer.

### 2.4 Snapshot, identity, and cleanup

`prepare_prompt_model` opens `model_path` once. It clones the bounded template scalar from that
snapshot's already decoded table, then consumes the same snapshot through a private tokenizer
loader. No later path resolution or open is allowed. Atomic replacement of `model_path` therefore
cannot combine a template from one generation with arrays from another.

The template clone, tokenizer arrays and indexes, regex handles, rendered prompt, and all scratch
builders drop on every success, data failure, and outer-error path. Only `PromptIdsResult` escapes.
There is no resident handle, cache, borrowed result field, or path in an identity preimage.

### 2.5 CLI

The exact grammar is:

```text
main --prepare-prompt MODEL SYSTEM_FILE USER_FILE
```

Arity is checked first, then all three paths use the existing tokenizer path grammar before any
file work. `SYSTEM_FILE` is read before `USER_FILE`; each read is bounded at 1 MiB by the existing
input reader. The API's combined-size check remains authoritative. Input files are complete UTF-8
strings and may contain NUL.

Success writes the exact decimal token ids as compact JSON followed by one LF, for example
`[151644,8948,...]\n`. There are no spaces and no summary. Any path, read, UTF-8, model, template,
size, tokenizer, JSON-render, or pre-write sink preparation failure writes zero stdout and returns
nonzero. A stdout failure propagates the OS status and may leave the kernel-written prefix.

## 3. Implementation plan

1. Split R7-TOKENIZER's private loader into `load_snapshot(GgufSnapshot)` plus the unchanged
   `load_model(path)` wrapper. Existing encode/decode behavior and error order stay byte-identical.
2. Add template validation, prompt construction, and encoding inside the owner module so all model
   reads share the snapshot.
3. Add the CLI adapter without changing `--tokenize` or `--detokenize`.
4. Extend the independent synthetic GGUF writer with the exact checked-in template and ChatML
   control spellings; add a small API harness and runner.
5. Add the focused real-model parity runner and aggregate/topology ownership.

The expected hand-written implementation is below 1,000 changed lines. No larger-boundary
exception is required.

## 4. Acceptance

### 4.1 Hosted owner: `make prompt-smoke`

The owner generates bounded GGUF files and independently computes expected prompt bytes and token
ids. It covers:

- empty, ASCII, multiline, embedded-NUL, CJK/emoji, and literal delimiter content;
- exact five-fragment placement and parse-control ids;
- public success identities/counts/byte counts and empty output on every failure;
- missing, wrong-type, invalid-text, exact-cap, over-cap, and wrong-hash template metadata;
- exact and over-limit combined prompt size;
- template-before-tokenizer and size-before-tokenizer multi-invalid precedence;
- one-source snapshot construction, plus the existing deterministic GGUF replacement owner that
  proves selected arrays remain on the retained handle;
- CLI arity/path/read/UTF-8 failures and byte-exact compact JSON stdout;
- repeated success/failure cleanup under the repository's available lifetime probes.

The synthetic owner needs no model, network, llama.cpp, GPU, or special host. It joins
`HOSTED_CHECK_TARGETS` once.

### 4.2 Focused real-model parity: `make prompt-parity`

The opt-in runner requires:

- `ALIGN_LLM_GGUF_MODEL`, with the exact reference model size and SHA from R7-TOKENIZER;
- `ALIGN_LLM_LLAMA_SERVER`, an executable built from `.llama-revision` build 10566; and
- `ALIGN_LLM_LLAMA_TOKENIZE`, the same pinned tokenizer used by R7-TOKENIZER.

An unset or absent prerequisite prints one explicit `N/A` line and exits zero. A named wrong model,
tool revision, server failure, malformed response, timeout, template mismatch, or id mismatch is a
hard failure. The runner starts the server on a loopback ephemeral port with generation disabled by
using only `/apply-template`, asks it to render a frozen corpus of system/user pairs, compares the
exact returned prompt string to section 2.2, tokenizes that string through pinned llama-tokenize,
and compares every id to `--prepare-prompt`. It shuts the server down on every path. The target is
focused and joins no aggregate.

The corpus includes the hosted text classes plus the existing provider demo's system message and
the frozen coding task prompt `python-inclusive-range`. No inference or completion claim is made.

### 4.3 Publication gate

```text
make fmt
make tokenizer-smoke prompt-smoke
make prompt-parity
python3 scripts/pre-pr --owner-test R7-PROMPT -- make tokenizer-smoke prompt-smoke
```

Adding `prompt-smoke` to hosted aggregate membership requires one capable `make ci` through the
publication preflight or exact hosted workflow. The final stamp and comprehensive review bind the
unchanged final head.

## 5. Closure matrix

| Owner / path | Construction | Success | Failure / malformed | Early exit | Cleanup | Regression |
| --- | --- | --- | --- | --- | --- | --- |
| private tokenizer loader split | consume one opened snapshot; unchanged arrays and indexes | encode/decode results unchanged | all existing sixteen stages unchanged | first existing failure | snapshot and partial tokenizer drop once | `tokenizer-smoke`; `tokenizer-parity` |
| template validation | clone first scalar from snapshot table; bounded SHA-256 | exact template id | metadata, size, unsupported in steps 3-5 | before input arithmetic/tokenizer arrays | scalar/digest drop | `prompt-smoke` template matrix |
| prompt arithmetic | checked `system + user + 80` | exact published byte counts | `R7_PROMPT_SIZE` before tokenizer | no builder on failure | scalar lengths only | exact/over boundary and multi-invalid case |
| prompt builder | five fixed fragments and two borrowed inputs | byte-exact complete prompt | length mismatch is `R7_PROMPT_RENDER` | no encode after mismatch | builder drops after encode | independent prompt bytes and mutation tripwire |
| prompt encode | existing private tokenizer, parse-control | exact owned ids and identities | existing count/model errors | no result ids before success | prompt/tokenizer scratch drops | text corpus and real parity |
| public result | empty owned result, fill fields at settled transitions | coherent identities/counts/ids | known fields retained, ids empty | first code wins | result alone transfers | API harness success/error rows |
| CLI input | arity, three lexical paths, system then user bounded reads | two complete UTF-8 strings | outer failure, zero stdout | no later path read after first failure | files and buffers drop | CLI matrix |
| CLI output | compact id renderer after inner success | exact JSON plus LF | pre-write failure has zero stdout | one stdout write | output buffer drops | byte golden and sink failure |
| synthetic fixture | independent GGUF writer plus frozen exact template | deterministic accepted model | single-root and multi-invalid mutants | temporary-only files | runner temp tree removed | `prompt-smoke` |
| real parity | exact pin/model/tool checks, loopback server | prompt bytes and ids equal | wrong prerequisite/result hard fails | absent prerequisite one N/A line | server and temp files always stopped/removed | `prompt-parity` |
| Makefile/topology | one hosted owner, one focused qualification | owner reached once | omission/duplication fails | parity outside aggregates | N/A | `gate-topology-check`; `make ci` |

## 6. Deferred next boundary

After R7-PROMPT, a caller can transform the existing provider request into exact runtime token ids.
The next eligible capability integrates those ids with the existing resident dense decode loop,
defines EOG/maximum-token termination, and returns decoded completion text through a new explicit
align-runtime provider arm. That capability, not this one, is responsible for R7's provider-swap
gate and a fixed coding-task run.
