# R0-GGUF-INSPECT: read-only GGUF header, metadata, and tensor-table inspection

Status: plan of record for the first Track B capability named by `docs/specs/roadmap.md` section
R0, implemented at pin `4b515f8d` by `src/gguf.align`, the `src/main.align` `--inspect-gguf` arm,
`scripts/run-gguf-smoke`, and `scripts/run-gguf-reference-parity`. Section 6 records every
correction implementation forced on this contract. This document triggers the `CLAUDE.md`
proportional design gate on two counts: it adds a public CLI surface (`main --inspect-gguf`) and a
new versioned exchanged document (`R0_GGUF_INSPECTION`, `schema_version: 1`).

This document is authoritative for the R0 public contract. `docs/specs/roadmap.md` remains
authoritative for delivery order; `docs/specs/align-llm.md` remains authoritative for the
architecture in which the GGUF reader sits.

## 1. Purpose and scope

### 1.1 Goal

Make one real GGUF model file self-describing to align-llm without linking, embedding, or invoking
any external model runtime. The capability delivers one consumer-complete path: a caller names a
`.gguf` path and receives one canonical JSON document that answers what the file declares about
itself — its header, every metadata key/value with its declared GGUF type, its complete tensor
table, its architecture, its alignment, and the exact byte offset at which tensor data begins.

R0 is the measurement and correctness foundation for every later Track B slice. R1 model frontends
must read metadata to build a Model IR; R2 `align-pack` must read the tensor table to plan a
physical layout. Both consume the public `GgufTable` surface `docs/specs/r1-qwen-model-ir.md` section 2.3 adds to
this module rather than re-parsing the container. No record type defined in this document is public.

### 1.2 In scope

1. Decoding the 24-byte GGUF header: magic, version, tensor count, metadata KV count.
2. Decoding every metadata key/value pair, including all thirteen GGUF value types and typed
   arrays, under a bounded rendering contract for very large arrays.
3. Decoding the complete tensor table: name, dimension count, dimensions, GGML type id and name,
   and the tensor-relative data offset.
4. Resolving `general.architecture` and `general.alignment`, and computing the absolute
   data-section offset from the tensor-table end and the alignment.
5. Reporting `bytes_read`, so that the "header and metadata only" claim is measurable rather than
   asserted.
6. Distinct, ordered, documented rejection of malformed, truncated, implausible, and
   unrepresentable input.

### 1.3 Non-goals

These are deliberate exclusions, not deferred work items inside this capability.

- **No tensor payload decode.** No byte of the tensor data section is ever interpreted. A trailing
  read window may incidentally *contain* payload bytes (section 4.3 states the exact bound); those
  bytes are never decoded, retained, or rendered.
- **No dequantization.** No GGML block format is unpacked. The tensor `type` field is reported as an
  id and a name; its scale encoding and element layout are R2 concerns. Its **block geometry** —
  elements per block and bytes per block — is exposed by this module as `ggml_block_size` /
  `ggml_type_size` (`docs/specs/r1-qwen-model-ir.md` section 2.5.7), because both R1 and R2 need it
  and duplicating a GGML table into each frontend would be worse than owning it beside
  `ggml_type_name`. No block is unpacked and no scale is read; the non-goal is otherwise
  unchanged.
- **No runtime dependency.** `src/gguf.align` imports no provider, no inference code, and no
  `align-runtime` surface. R0 must be usable and testable before any runtime exists.
- **No memory mapping.** Section 5.3 records the mmap/arena alternative as an explicitly deferred
  R2 surface with the condition that would select it.
- **No tokenizer materialization.** A 152,064-entry token array is summarized, not reconstructed.
  Building a usable tokenizer is an R1 frontend concern.
- **No writing, rewriting, repair, splitting, or merging** of GGUF files. The capability is
  strictly read-only on the model path.
- **No multi-shard resolution.** `split.no`, `split.count`, and `split.tensors.count` are reported
  as ordinary metadata; following a shard chain to sibling files is not performed.
- **No big-endian GGUF.** GGUF v3 permits big-endian files. R0 decodes little-endian only and
  rejects nothing on this basis, because the container carries no endianness flag; section 2.6
  records this as a known limitation with its detection consequence.

### 1.4 Gate statement

The roadmap gate for R0 is: *the metadata and tensor list of the target GGUF agree with an existing
tool.* This document discharges that gate as the focused, opt-in
`scripts/run-gguf-reference-parity` qualification of section 4.4, and adds a self-contained,
CI-eligible `gguf-smoke` owner (section 4.2) that does not depend on a multi-gigabyte local model.

## 2. Public-contract ledger

### 2.1 Verified Align surface at pin `4b515f8d`

Every surface below was checked against the sibling checkout at
`4b515f8d37de2e9a9ba06170c5842fd12dc1cba2` before being written into this plan. R0 consumes only
these; it proposes no new Align surface and builds no compatibility layer.

| Surface | Exact form at the pin | Consequence for R0 |
| --- | --- | --- |
| `fs.open_rw(path)` | `-> Result<file, Error>`; opens `O_RDWR`, the file must already exist | The only random-access constructor. `fs.open_read`/`fs.open_ro` are NOT FOUND; see the gap in section 2.7 |
| `f.len()` | `-> Result<i64, Error>`; a live `fstat`, not cached | `file_size` is read once, before any decode, and is the bound for every range check |
| `f.pread(b: mut buffer, off: i64)` | `-> Result<i64, Error>`; buffer first, offset second; returns the actual count, `0` at EOF | The one read primitive. There is no `seek` and no cursor by design |
| `buffer(cap)` | builtin constructor, capacity required; owned growable heap handle; freed by scope `Drop` | The read window. Must be a `mut` local to be a `pread` sink |
| `b.bytes()` | `-> bytes` (`slice<u8>`), borrowing the buffer | The decode view. `bytes` is a spelling of `slice<u8>`, not a nominal type |
| `bytes.<scalar>(off)` | `-> <scalar>`, a plain Copy value, **not** a `Result` | The codec. Eighteen names: `u8`, `i8`, and `_le`/`_be` forms of `u16 i16 u32 i32 u64 i64 f32 f64` |
| codec bounds policy | An out-of-range read (`off < 0` or `off + width > len`) **aborts**, the same fail-closed policy as `slice[i]` | Bounds checking is a correctness obligation of R0, not an optimization. See section 2.5 |
| `xs[a..b]` | Half-open range slicing; violating `0 <= a <= b <= len` aborts | The only sub-view form. `bv.slice(off, len)` is NOT FOUND |
| `bytes.as_str()` | `-> Result<str, Error>`; validates UTF-8, `Error.Invalid` on failure; zero-copy view bound to the receiver | The single UTF-8 gate. Its `Err` is the `invalid_utf8` fallback trigger, never a hard failure |
| `.clone()` | On `str`/`string` (and `box<T>`); returns an owned `string`. NOT available on `slice<u8>` | `bv[a..b].as_str()?.clone()` is the one route from window bytes to a retained value |
| `builder`, `b.write/write_int/write_bool/write_float/write_char`, `b.to_string()` | `to_string()` consumes the builder and returns an owned `string` | Document rendering, identical to the `src/patch_eval.align` idiom |
| `b.write_float(x)` | Emits the shortest round-trip decimal (Rust `Display`) | Round-trip exact, but see the exponent-notation constraint in section 2.4 |
| `u64` and bit operators | `u64` exists; `& | ^ ~ << >>` are operators; `>>` is logical on unsigned; shift amount shares the value's type | The `u64`-above-`i64::MAX` test is written by hand as `(raw >> 63) != 0` |
| `as` | Value conversion only. `int -> int` truncates/extends with **defined wrap** | A `u64` above `i64::MAX` silently becomes negative under `as i64`. R0 must reject before converting |
| `Result<T, E>`, `Error { NotFound, Invalid, Denied, Timeout, Code(i32) }`, `?` | `?` requires the identical `E`, no implicit conversion; `?` keeps the `Ok` payload region | R0's public functions return `Result<_, Error>`, matching every existing module |

Three surfaces that a naive design would reach for are **NOT FOUND at this pin** and are named here
so no reviewer has to rediscover them: `seek`, any bit-cast (`f32_from_bits`, `bitcast`,
`transmute`, `raw.ptr_cast`), and any `MAX`/`MIN` integer constant. Section 2.4 and section 2.5
give R0's exact substitutes.

`docs/specs/roadmap.md` section R0 says that a little-endian decode API is to be added to the Align
standard library alongside this capability. That work is **already shipped** at the pin as the
eighteen-name `bytes.<scalar>(off)` codec recorded above. R0 therefore opens no Align request for
it, and the roadmap sentence should be read as satisfied rather than pending.

### 2.2 CLI surface

| Command | Exact arguments | Document destination | Stdout | Exit |
| --- | --- | --- | --- | --- |
| `./main --inspect-gguf MODEL_GGUF` | Exactly one operand (`args.len() == 3`) | The document is written to stdout, followed by one newline, and nothing else is printed | The document only | `0` on `status: "ok"`, `Err(Error.Invalid)` on `status: "error"` |
| `./main --inspect-gguf MODEL_GGUF INSPECTION_JSON` | Exactly two operands (`args.len() == 4`) | The document is written to `INSPECTION_JSON` via `fs.write_file` | The section 2.3 human summary block | `0` on `status: "ok"`, `Err(Error.Invalid)` on `status: "error"` |

The document bytes are **byte-identical** between the two forms. Only the destination and the
presence of the summary block differ. This is the complete option/detail-level matrix for this
surface: there is no verbosity flag, no field-selection flag, and no alternate encoding.

The one-operand form exists because `docs/specs/roadmap.md` specifies `align-inspect model.gguf`
and because a machine consumer — including `scripts/run-gguf-reference-parity` — should not need a
temporary file. The two-operand form exists because every other document-producing arm in
`src/main.align` (`--index`, `--select-tests`, `--evaluate-patch`, `--verify-loop`,
`--persist-result`) takes an explicit destination path, and consistency there is worth more than
minimality.

Dispatch follows the existing `src/main.align` contract exactly. `args[0]` is the executable name
and is never interpreted as a mode. A mode is selected only when `args[1] == "--inspect-gguf"`;
arity is then checked before any path or file work. `args.len() < 3` or `args.len() > 4` returns
`Err(Error.Invalid)` with no filesystem access and no document. An unrecognized `args[1]` continues
to reach the existing help path and return `Ok(())`; R0 does not change unknown-selector behavior.

`MODEL_GGUF` must be a nonempty UTF-8 string of at most 4,096 bytes with no embedded NUL. That is an
application validation bound, not a claim about host filesystem limits. No environment variable,
locale, provider setting, current time, or random seed changes any byte of the document. Relative
paths are resolved by `std.fs` from the caller's working directory; no home or environment
expansion and no path normalization is performed. The path string appears in the document verbatim
as given, in the `path` field.

### 2.3 Stable CLI summary

For the two-operand form only, and after the document has been written, the CLI prints exactly
these logical lines through the existing `print` primitive, one newline per line:

```text
gguf inspection:
status:
OK | ERROR
architecture:
<general.architecture, control-byte escaped; "-" when absent, non-STRING, or non-UTF-8>
version:
<decimal u32>
tensors:
<decimal i64>
metadata:
<decimal i64>
alignment:
<decimal i64>
data offset:
<decimal i64>
bytes read:
<decimal i64>
```

On `status: "error"` the header fields that were not decoded print `-1`, and one further pair is
appended:

```text
error:
<error code>
```

This block is a human convenience. The JSON document is the authoritative result, and normal Align
error reporting remains the source of truth for a returned `Err`. R0 adds no second diagnostic
grammar.

**Correction (section 6, items 17 and 18): the architecture line is escaped, and `-` means absent.**
The block is a fixed sequence of logical lines that a consumer reads positionally, and
`general.architecture` is container-controlled text. Every control byte in it — every byte below
`0x20`, and `0x7f` — is therefore replaced by `\xNN` (lowercase hexadecimal) before it is printed,
so the value always occupies exactly one line and cannot inject a `status:` or an `error:` pair.
The JSON document is unaffected: its encoder already escapes the same bytes. `-` is reserved for an
`architecture` the container does not supply — absent, non-STRING, or non-UTF-8 — so a key that is
present and empty prints an **empty line**, which is what the container actually declares. The CLI
distinguishes the two through the `architecture_present` field of section 2.5.4.

### 2.4 Exchanged document — `R0_GGUF_INSPECTION`, `schema_version: 1`

The document is canonical UTF-8 JSON in declaration order, produced by `json.encode` over declared
records spliced with `builder` exactly as `src/patch_eval.align` `render_document` does. Field
order is the order below and is normative. Any field addition, removal, reordering, or type change
requires `schema_version: 2`.

#### 2.4.1 Top level

```json
{
  "schema_version": 1,
  "kind": "R0_GGUF_INSPECTION",
  "path": "MODELS_DIR/qwen2.5-coder-7b-instruct-q4_k_m.gguf",
  "status": "ok",
  "error_code": "",
  "error_offset": -1,
  "file_size": 4683073536,
  "bytes_read": 5345312,
  "header": {
    "magic": "GGUF",
    "version": 3,
    "tensor_count": 339,
    "metadata_kv_count": 29
  },
  "architecture": "qwen2",
  "alignment": 32,
  "alignment_source": "default",
  "metadata_end": 5934224,
  "tensor_table_end": 5953528,
  "data_offset": 5953536,
  "metadata": [],
  "tensors": []
}
```

The example above is the real reference model; `MODELS_DIR` is a placeholder for whatever directory
holds it on the running host, and `path` is always the operand verbatim. Every value in it was
independently decoded from that model and cross-checked against `llama-gguf`, except `bytes_read`,
which is the computed lower bound of section 4.3 rather than a measured figure.

| Field | Type | Contract |
| --- | --- | --- |
| `schema_version` | integer | Always `1` for this document version |
| `kind` | string | Always `"R0_GGUF_INSPECTION"` |
| `path` | string | The `MODEL_GGUF` operand verbatim, JSON-escaped. Never normalized or absolutized |
| `status` | string | `"ok"` or `"error"`. No third value |
| `error_code` | string | `""` when `status` is `"ok"`; otherwise exactly one code from section 2.6 |
| `error_offset` | integer | `-1` when `status` is `"ok"`; otherwise the absolute file offset at which the failing field begins |
| `file_size` | integer | The `f.len()` result, read once before decoding |
| `bytes_read` | integer | The exact sum of the counts returned by every `f.pread` call. See section 4.3 |
| `header` | object | Always present. Fields not decoded hold `-1`, and `magic` holds the decoded four bytes when they are valid UTF-8 and `""` when they are not. `GGUF_TOO_SMALL` and a non-UTF-8 `GGUF_BAD_MAGIC` both leave all four unset; see section 6, item 19 |
| `architecture` | string or null | The `general.architecture` STRING value; `null` when absent, non-STRING, or non-UTF-8 |
| `alignment` | integer | The effective alignment; `32` when `general.alignment` is absent |
| `alignment_source` | string | `"general.alignment"` or `"default"` |
| `metadata_end` | integer | Absolute offset one past the last metadata byte; `-1` if not reached |
| `tensor_table_end` | integer | Absolute offset one past the last tensor-table byte; `-1` if not reached |
| `data_offset` | integer | `tensor_table_end` rounded up to `alignment`; `-1` if not reached |
| `metadata` | array | KV records, in file order, for every pair decoded before a failure |
| `tensors` | array | Tensor records, in file order, for every entry decoded before a failure |

On `status: "error"` the document is still written and every field decoded before the failure is
present and truthful. Fields never reached hold `-1`, `null`, `""`, or `[]` as typed above. This
mirrors the existing `--index` failure-persistence behavior in `src/repo_index.align` and makes a
corrupt file diagnosable rather than opaque.

#### 2.4.2 GGUF value types

The thirteen types are exactly the GGUF `gguf_metadata_value_type` enumeration. `type` is the
on-disk `u32` id and `type_name` is its name. An id outside this table is rejected; there is no
"unknown metadata type" rendering.

| id | `type_name` | On-disk width | `value` JSON shape |
| --- | --- | --- | --- |
| 0 | `UINT8` | 1 | integer |
| 1 | `INT8` | 1 | integer |
| 2 | `UINT16` | 2 | integer |
| 3 | `INT16` | 2 | integer |
| 4 | `UINT32` | 4 | integer |
| 5 | `INT32` | 4 | integer |
| 6 | `FLOAT32` | 4 | number, plus `value_bits` |
| 7 | `BOOL` | 1 | `true` or `false` |
| 8 | `STRING` | 8 + n | string, or `null` with `invalid_utf8` |
| 9 | `ARRAY` | variable | object, see 2.4.4 |
| 10 | `UINT64` | 8 | integer, rejected above `i64` max |
| 11 | `INT64` | 8 | integer |
| 12 | `FLOAT64` | 8 | number, plus `value_bits` |

`BOOL` is one byte. Any nonzero byte renders `true`; R0 does not reject a byte outside `{0, 1}`,
because writers in the wild are not consistent and the distinction carries no information.

**Correction (section 6, item 4): a non-finite float renders `null`.** `write_float` emits Rust's
`Display`, whose spelling for an infinity or a NaN is `inf` / `-inf` / `NaN` — none of which is
JSON. A `FLOAT32` or `FLOAT64` whose exponent bits are all set therefore renders `"value": null`
(and `{"value": null, "bits": "…"}` inside an array preview), while `value_bits` still carries the
exact pattern and remains the authoritative rendering. The test is `(bits & 0x7F800000) ==
0x7F800000` on the raw `u32`, or the `f64` equivalent, so it needs no float classifier and no
bit-cast. This is a wire-boundary correctness fix, not a schema change: `value` was already
documented as "number", and `null` is the only honest rendering of a value JSON cannot express.

#### 2.4.3 Scalar KV record

```json
{
  "index": 12,
  "key": "qwen2.rope.freq_base",
  "key_invalid_utf8": false,
  "type": 6,
  "type_name": "FLOAT32",
  "value": 1000000.0,
  "value_bits": "49742400"
}
```

`index` is the zero-based position in the metadata block and is always present. `key` is the
decoded key or `null`, with `key_invalid_utf8` set accordingly; when the key is `null` the pair is
still reported, with its index, type, and value, so a file with one bad key remains fully
inspectable.

`value_bits` is present **only** on `FLOAT32` and `FLOAT64`. It is the lowercase hexadecimal of the
raw IEEE-754 bit pattern read as an unsigned integer, most-significant nibble first, zero-padded to
8 characters for `FLOAT32` and 16 for `FLOAT64`. For `1000000.0f32` it is `"49742400"`.

`value_bits` exists because there is no bit-cast at this pin and none is needed: the implementation
performs **two codec reads at the same offset** — `bv.f32_le(off)` for the numeric value and
`bv.u32_le(off)` for the bits — rather than converting between them. `as` is a numeric value
conversion with defined truncating wrap and would destroy the bit pattern, so it is never used on a
float here.

`value_bits` also removes every float-formatting question from the parity contract. `write_float`
emits Rust's shortest round-trip `Display`, which is exact but **never uses exponent notation**: an
`f32` near its maximum renders as a 39-digit decimal and a subnormal `f64` renders as roughly a
thousand characters. That is valid JSON and it round-trips, but it is not a stable string to
compare against another tool's output. Consumers and the parity qualification compare `value_bits`
for exactness and treat `value` as the human-readable rendering.

`UINT64` renders as a JSON integer only when the on-disk value is at most `i64` max; otherwise the
document fails with `GGUF_VALUE_OVERFLOW`. `UINT8`, `UINT16`, and `UINT32` always fit in `i64` and
are never rejected on this basis.

A `STRING` whose bytes fail `as_str()` renders as:

```json
{
  "index": 3,
  "key": "general.finetune",
  "key_invalid_utf8": false,
  "type": 8,
  "type_name": "STRING",
  "value": null,
  "invalid_utf8": true,
  "byte_length": 13
}
```

`invalid_utf8` and `byte_length` are present only on a `STRING` value that failed UTF-8 validation.
A valid `STRING` carries neither. A non-UTF-8 string is never a hard failure: the container is
structurally sound and the caller still learns the key, the type, and the byte length.

#### 2.4.4 Array KV record

```json
{
  "index": 17,
  "key": "tokenizer.ggml.tokens",
  "key_invalid_utf8": false,
  "type": 9,
  "type_name": "ARRAY",
  "value": {
    "element_type": 8,
    "element_type_name": "STRING",
    "length": 152064,
    "preview": ["!", "\"", "#", "$", "%", "&", "'", "("],
    "truncated": true
  }
}
```

The bounded array contract is: **`ARRAY_PREVIEW := 8`**. `preview` holds the first
`min(length, 8)` elements, each rendered by the scalar rules of section 2.4.3. `truncated` is
`length > 8`. When `truncated` is `false`, `preview` is the complete array and no information is
lost.

Eight is chosen because it is large enough to identify a tokenizer family, a rope scaling vector, or
a dimension list at a glance, and small enough that the worst realistic case — a 152,064-element
string array — costs a handful of short strings instead of several megabytes of document. A caller
that needs the full token list is an R1 frontend and will consume the record types directly rather
than this document.

Inside `preview`, a `FLOAT32`/`FLOAT64` element is rendered as `{"value": <number>, "bits": "<hex>"}`
rather than a bare number, so that the exactness rule of section 2.4.3 holds for array elements too.
A non-UTF-8 `STRING` element is rendered as `{"value": null, "invalid_utf8": true, "byte_length": n}`.
Every other element type is a bare JSON number or boolean.

An `element_type` of `9` — a nested array — is rejected with `GGUF_NESTED_ARRAY`. The GGUF container
does not define nesting and no writer produces it.

#### 2.4.5 Tensor record

```json
{
  "index": 0,
  "name": "token_embd.weight",
  "name_invalid_utf8": false,
  "n_dims": 2,
  "dims": [3584, 152064],
  "type": 12,
  "type_name": "Q4_K",
  "type_known": true,
  "offset": 0,
  "absolute_offset": 5953536
}
```

`dims` has exactly `n_dims` entries, in on-disk order (GGML's fastest-varying dimension first).
`offset` is the tensor-relative offset exactly as stored. `absolute_offset` is
`data_offset + offset`, precomputed because every consumer needs it and recomputing it invites an
off-by-one.

`type` is the raw `ggml_type` id. `type_name` is its name when known and `null` otherwise, with
`type_known` set accordingly. An unknown id is **not** an error: new quantization types are added to
GGML regularly, and a tool that refuses to describe a file because one tensor uses a newer type is
less useful than one that reports the id. The known-id table R0 ships is the GGML enumeration as of
the pin:

```text
0 F32     1 F16     2 Q4_0    3 Q4_1    6 Q5_0    7 Q5_1    8 Q8_0    9 Q8_1
10 Q2_K   11 Q3_K   12 Q4_K   13 Q5_K   14 Q6_K   15 Q8_K
16 IQ2_XXS 17 IQ2_XS 18 IQ3_XXS 19 IQ1_S 20 IQ4_NL 21 IQ3_S 22 IQ2_S 23 IQ4_XS
24 I8     25 I16    26 I32    27 I64    28 F64    29 IQ1_M  30 BF16
34 TQ1_0  35 TQ2_0
```

Ids 4, 5, 31, 32, and 33 are GGML types that were defined and later removed. They are deliberately
absent from the table, so a file using one reports `type_known: false` rather than a name that no
longer means anything. This table is data in `src/gguf.align`, not control flow; extending it is a
one-line change that does not touch the decoder.

### 2.5 Reading strategy, ownership, and allocation

#### 2.5.1 The window cursor

`file` is a random-access handle with no cursor and no `seek`: every access carries an explicit
offset. GGUF is a variable-length forward format, so R0 supplies its own cursor over `pread`.

```text
Cursor {
  file_size: i64,      // f.len(), read once
  window_base: i64,    // absolute offset of window byte 0
  window_len: i64,     // bytes actually returned by the last pread
  pos: i64,            // absolute offset of the next byte to decode
  capacity: i64,       // current window capacity
  bytes_read: i64,     // running sum of every pread return value
}
```

**Correction (section 6, item 1): the handle and the window are not cursor fields.** `file` never
rides an aggregate other than its constructor's `Result<file, Error>`, and every native buffer fill
requires its buffer argument to be a bare local declared `mut`, so neither `handle: file` nor
`window: buffer` can live in a record. Both stay locals in `gguf.inspect` and travel to the cursor
operations as `borrow handle: file` and `borrow mut window: buffer`, alongside `borrow mut c:
Cursor`. The reading contract is unchanged; only where the three pieces of state live changes.

Three operations define it, and they are the whole reading contract:

1. **`ensure(n)`** guarantees that bytes `[pos, pos + n)` are inside the window. If `pos + n` exceeds
   `file_size`, it fails `GGUF_TRUNCATED` **before** any codec call. If `n` exceeds `capacity`, it
   grows (2.5.2). Otherwise, if the range is not already resident, it refills at `pos`.
2. **`refill(n)`** calls `handle.pread(window, pos)`, sets `window_base = pos`, sets `window_len` to
   the returned count, and adds that count to `bytes_read`. A refill always starts at the first
   unconsumed byte, so no *consumed* byte is ever read twice; an unconsumed window tail that an
   oversized item forces past is re-read, and `bytes_read` counts it, because `bytes_read` is
   defined as the I/O actually performed rather than the distinct bytes touched.

   **Correction (section 6, item 16): a refill completes a short read.** `f.pread` reads *one*
   window and publishes exactly the count the syscall returned, so a count below the requested `n`
   is surfaced to the caller as-is. Treating that as a truncated container would report
   `GGUF_TRUNCATED` for a perfectly good file, so `refill` takes the needed length and loops until
   `window_len >= n`. Each continuation reads at `window_base + window_len` into its own bare `mut`
   buffer local — the runtime always fills a buffer from *its* capacity, so a continuation cannot be
   read into `window` itself — and is appended to the window, whose total never exceeds the capacity
   `ensure` already reserved. Every continuation count enters `bytes_read` on the same rule.
3. **`skip(n)`** advances `pos` by `n` without reading. If the target is inside the resident window
   it is a pointer move; otherwise the window is simply invalidated and the next `ensure` refills at
   the new position. Skipped bytes never enter `bytes_read`.

**Correction (section 6, item 2): the window buffer is reused across refills.** The condition this
plan named — "if a future adoption verifies that `pread` resets the buffer length, reuse becomes a
mechanical, behavior-preserving change" — was verified at the pin before implementation:
`align_rt_io_file_pread` fills from the buffer's *capacity*, then publishes exactly the returned
count as its length on every call, including a short read and an EOF read of zero. One
`buffer(WINDOW_BYTES)` is therefore allocated in `gguf.inspect` and replaced only by the explicit
growth path of 2.5.2. The reference model allocates one window instead of six, and `bytes_read` is
unaffected.

**Bounds checking is a correctness obligation, not an optimization.** At this pin
`bytes.<scalar>(off)` **aborts** on an out-of-range read — the same fail-closed policy as `slice[i]`
— and returns a plain scalar, not a `Result`. A missing check is therefore a process abort on a
truncated file, not a recoverable error. Every codec call in `src/gguf.align` is reached only
through `ensure`, and no codec call takes an offset computed anywhere but from `pos - window_base`.
This is the single most important invariant in the module and section 3 gives it its own closure
cell and its own regression.

#### 2.5.2 Bounded growth

`WINDOW_BYTES := 1_048_576` is the initial and normal capacity. A single item larger than the
current capacity — a long chat template, a wide tensor-name run — triggers explicit growth:
capacity doubles until it is at least the requested `n`, capped at
`MAX_ITEM_BYTES := 16_777_216`. A request above the cap fails `GGUF_ITEM_TOO_LARGE` without
allocating. Growth is monotone within one inspection and the window is never shrunk.

**Correction (section 6, item 17): a failed growth allocation is detected by its consequence.**
`buffer(cap)` reserves fallibly and degrades to a **zero-capacity** window rather than aborting the
process, and a `pread` into a zero-capacity buffer returns `0` without issuing a syscall. A
`buffer`'s capacity is not observable at this pin — `b.len()` is the last read's byte count and
there is no `b.cap()` — so R0 cannot test the reservation directly. It tests the observable
consequence instead: `ensure` has already proved `pos + n <= file_size`, so any read of zero bytes
at a position strictly inside the file is impossible for a healthy window, and it is reported as
`GGUF_WINDOW_UNAVAILABLE` rather than as `GGUF_TRUNCATED`. The same code covers the other cause of
that observation, a file that shrank under the inspection, which section 3.1 already records as an
unsupported caller case.

Fixed-width array tails use `skip`. After the first `ARRAY_PREVIEW` elements of an array whose
element type is not `STRING`, the remaining `(length - 8) * width` bytes are skipped rather than
read. On the reference model this removes 608,224 of the 608,256 bytes of the
`tokenizer.ggml.token_type` array from `bytes_read`. `STRING` arrays cannot be skipped, because
each element's length prefix is interleaved
with its bytes and the end of the array is not computable without walking it.

#### 2.5.3 Ownership and lifetime

The rule that governs every retained value: **a `str` obtained from the window is borrowed from the
window and must not outlive the next `ensure`.** `bytes` is `slice<u8>` and has no `.clone()`;
`as_str()` yields a zero-copy view region-bound to its receiver. Therefore every retained text value
is materialized immediately:

```text
key := match cursor.view(key_offset, key_len).as_str() {
  Ok(text) => text.clone(),      // owned string, safe across the next refill
  Err(_)   => "".clone(),        // rendered as null with key_invalid_utf8: true
}
```

`.clone()` before the borrow scope ends is mandatory for: every metadata key, every `STRING` value,
every `STRING` array preview element, every tensor name, and `architecture`. Scalars need no clone —
a codec read returns a Copy value that carries no region.

| Value | Owner | Allocation | Release |
| --- | --- | --- | --- |
| `file` handle | `gguf.inspect` local | one fd | scope `Drop`; there is no `f.close()` at this pin |
| window `buffer` | `gguf.inspect` local, a bare `mut` (section 6, items 1 and 2) | one `capacity`-byte window, allocated once and replaced only by the explicit growth path, plus one short-lived continuation buffer per short read | scope `Drop` when replaced and at end |
| decoded `string` values | the `KvRow` / `TensorRow` value, which is private and short-lived; retained text reaches a caller either inside `GgufInspection.document` or inside a `GgufTable` stream | one per retained text value | with the record |
| per-record JSON | `json.encode` result, cloned once into the record | one per record | with the record |
| final document | `builder` moved out by `to_string()` | one owned `string` | moved into `GgufInspection.document`, then to the caller |

The final document is **moved**, not cloned, into its sole owning result record, following the
`C8-MOVE-RESULT-DOCUMENTS` rule already established in `docs/specs/c8-speed-first.md` section 2.8.
No cache, alias, or shared mutable state is introduced. The module holds no process-global state, so
two `--inspect-gguf` invocations in one process, or in two processes, are independent.

#### 2.5.4 Owner module and public API

`src/gguf.align` is a new module and the sole owner of GGUF container knowledge. It imports
`core.json`, `std.fs`, and nothing else — no provider, no runtime, no evaluation surface.

```text
pub GgufStatus { Ok, Error }

pub GgufInspection {
  status: GgufStatus,
  error_code: string,
  file_size: i64,
  bytes_read: i64,
  version: i64,
  tensor_count: i64,
  metadata_kv_count: i64,
  alignment: i64,
  data_offset: i64,
  architecture: string,
  architecture_present: bool,
  document: string,
}

pub fn inspect(path: str) -> Result<GgufInspection, Error>

pub GgufTable { … }   // `docs/specs/r1-qwen-model-ir.md` section 2.3.2 declares every field

pub fn read_table(path: str) -> Result<GgufTable, Error>

pub fn find_key(borrow t: GgufTable, key: str) -> i64
pub fn find_tensor(borrow t: GgufTable, name: str) -> i64
pub fn kv_type(borrow t: GgufTable, key: str) -> i64
pub fn kv_int(borrow t: GgufTable, key: str) -> Option<i64>
pub fn kv_float_bits(borrow t: GgufTable, key: str) -> Option<i64>
pub fn kv_string(borrow t: GgufTable, key: str) -> Option<string>
pub fn kv_float_text(borrow t: GgufTable, key: str) -> Option<string>
pub fn kv_array_length(borrow t: GgufTable, key: str) -> Option<i64>
pub fn tensor_name(borrow t: GgufTable, index: i64) -> string
pub fn tensor_dim(borrow t: GgufTable, index: i64, axis: i64) -> i64

pub fn ggml_block_size(id: i64) -> i64
pub fn ggml_type_size(id: i64) -> i64

pub fn json_string(value: str) -> string
```

`inspect` and `read_table` are two walks over one decoder; `docs/specs/r1-qwen-model-ir.md` section
2.3.6 records why they cannot share a walk function at this pin and the `table-inspect-parity`
regression that keeps them from drifting. `json_string` is public for the same reason: it is the one
text-to-JSON boundary in the repository, and a frontend splicing container-supplied text into its own
document must cross it rather than invent a second escaping grammar.

`architecture_present` (section 6, item 18) is `true` only when `general.architecture` was decoded
as a valid UTF-8 `STRING`. It is what lets a consumer — including the section 2.3 summary —
distinguish a key that is present and empty from one that is absent, non-STRING, or non-UTF-8,
which `architecture` alone cannot express. The document's `architecture` field already carries the
same distinction as `""` versus `null`; this is the record-level equivalent, not a new document
field, so `schema_version` stays `1`.

`inspect` returns `Err` only for an invalid path argument or an operating-system failure (open,
`len`, or `pread`). Every structural defect in the file is data: it returns `Ok` with
`status: Error`, a populated `error_code`, and a complete document. `src/main.align` maps
`status: Error` to its existing `Err(Error.Invalid)` process exit *after* writing or printing the
document. This is the same split `docs/specs/c7-persisted-result.md` draws between a valid negative
measurement and a malformed record.

`src/main.align` owns one new arm, `inspect_gguf_demo(args)`, and one new help line. It contains no
GGUF knowledge: it validates arity, calls `gguf.inspect`, writes or prints, prints the summary, and
maps the status.

### 2.6 Validation order and error codes

Validation is strictly ordered and the **first** applicable row wins. No document is written and no
stdout is produced before the walk completes, so no partial output can be observed for any failure.

1. CLI selector and exact arity.
2. Path lexical validation: nonempty, at most 4,096 bytes, no embedded NUL.
3. `fs.open_rw` and `f.len()`.
4. Header: size, magic, version, counts.
5. Metadata pairs, in file order; within a pair: key length, key bytes, value type, value.
6. `general.alignment`, if present, at the point it is decoded.
7. Tensor entries, in file order; within an entry: name, `n_dims`, dims, type, offset.
8. `data_offset` computation and file-size containment.
9. Per-tensor absolute-range containment.

Alignment is resolved in step 6, before step 7 needs it, because the metadata block always precedes
the tensor table in the container. This ordering is a property of the format, not an assumption.

| Code | Condition | Detected in |
| --- | --- | --- |
| `GGUF_TOO_SMALL` | `file_size < 24` | step 4 |
| `GGUF_BAD_MAGIC` | bytes `[0, 4)` are not `47 47 55 46` (`GGUF`) | step 4 |
| `GGUF_UNSUPPORTED_VERSION` | `version` is not `2` or `3` | step 4 |
| `GGUF_COUNT_OVERFLOW` | a `u64` count, length, or dimension has bit 63 set and cannot be represented as `i64` | steps 4, 5, 7 |
| `GGUF_COUNT_IMPLAUSIBLE` | `metadata_kv_count > 4096`, `tensor_count > 1048576`, or an array `length > 16777216` | steps 4, 5 |
| `GGUF_STRING_TOO_LARGE` | a declared string length exceeds `16777216` | steps 5, 7 |
| `GGUF_UNKNOWN_VALUE_TYPE` | a metadata value type id, or an array element type id, is greater than `12` | step 5 |
| `GGUF_NESTED_ARRAY` | an array declares element type `9` | step 5 |
| `GGUF_VALUE_OVERFLOW` | a `UINT64` value has bit 63 set | step 5 |
| `GGUF_ITEM_TOO_LARGE` | a single item needs a window larger than `16777216` (see section 6, item 6: unreachable while `MAX_STRING_BYTES == MAX_ITEM_BYTES`; retained as a fail-closed guard) | steps 5, 7 |
| `GGUF_BAD_ALIGNMENT` | `general.alignment` is not `UINT32`, is `0`, or is not a power of two | step 6 |
| `GGUF_BAD_DIMS` | `n_dims` is `0` or greater than `4` | step 7 |
| `GGUF_OFFSET_OVERFLOW` | a tensor offset has bit 63 set | step 7 |
| `GGUF_TENSOR_MISALIGNED` | a tensor offset is not a multiple of `alignment` | step 7 |
| `GGUF_TENSOR_OUT_OF_RANGE` | `offset > file_size - data_offset`, the non-wrapping form of `data_offset + offset > file_size` (section 6, item 15) | step 9 |
| `GGUF_TRUNCATED` | any required range extends past `file_size`, including `data_offset > file_size` | steps 4, 5, 7, 8 |
| `GGUF_WINDOW_UNAVAILABLE` | a `pread` returned zero bytes at a position strictly inside the file: the window's capacity could not be reserved, or the file shrank during the inspection (section 6, item 17). Like `GGUF_ITEM_TOO_LARGE` it is a fail-closed guard with no fixture, because neither cause can be provoked deterministically from a test | steps 4, 5, 7 |

Thresholds and their justification, all recorded as named constants in `src/gguf.align`:

| Constant | Value | Observed reality | Rationale |
| --- | --- | --- | --- |
| `MAX_METADATA_KV` | 4,096 | 29 in the reference model | Two orders of magnitude of headroom over any shipping model; a count above it is corruption, not a new format |
| `MAX_TENSORS` | 1,048,576 | 339 in the reference model | Comfortably above the largest MoE checkpoints, which are in the low tens of thousands |
| `MAX_STRING_BYTES` | 16,777,216 | 2,509 for `tokenizer.chat_template` | Nearly four orders of magnitude of headroom; also the single-item window cap |
| `MAX_ARRAY_ELEMENTS` | 16,777,216 | 152,064 for `tokenizer.ggml.tokens` | Two orders of magnitude of headroom |
| `MAX_TENSOR_DIMS` | 4 | 2 in the reference model | `GGML_MAX_DIMS` is 4; this is a format constant, not a heuristic |
| `MAX_ITEM_BYTES` | 16,777,216 | — | The largest window a single item may force |
| `MAX_PATH_BYTES` | 4,096 | — | Matches the existing repository path bound |

There is no `i64` `MAX` constant at this pin, so the representability test is written as
`(raw >> 63) != 0` on the `u64` value. `>>` is logical on unsigned types and the shift amount shares
the value's type, so this is exact. It is performed **before** any `as i64`, because `as` truncates
and extends with defined wrap and would silently produce a negative count.

Signed arithmetic wraps in two's complement without trapping, so the same rule governs every sum of
file-derived values: it must be proved in range before it is formed. Every addition in
`src/gguf.align` is bounded by `file_size` plus a capped constant, the one multiplication
(`(length - ARRAY_PREVIEW) * width` in the fixed-width skip path) is bounded by
`MAX_ARRAY_ELEMENTS * 8`, and the two `data_offset + offset` sums are written in non-wrapping form
— the containment test as a subtraction, the rendering behind an explicit representability test
against a locally declared `I64_MAX` literal. Section 6, item 15 records the defect that forced
this and the audit that closed the class.

A version-1 GGUF file is rejected rather than supported. v1 encodes counts and array lengths as
`u32` rather than `u64`, so it is a structurally different container, and no model align-llm targets
ships as v1. v2 and v3 share the layout R0 decodes. v3's only addition over v2 is permission to
write big-endian files; the container carries no endianness flag, so a big-endian v3 file is
undetectable in general and will fail as `GGUF_COUNT_IMPLAUSIBLE` or `GGUF_BAD_MAGIC` rather than
being silently misread. That failure mode is recorded here as a known limitation.

### 2.7 Align capability request — read-only random access

`fs.open_rw` is the only random-access constructor at the pin. `fs.open_read` and `fs.open_ro` are
NOT FOUND; the latter is recorded in Align's own roadmap as a deferred escape hatch. `fs.open`
returns a sequential `reader` with no `pread` and no offset.

R0 therefore must request `O_RDWR` on a file it never writes. That is a genuine Align standard-library
gap under the `CLAUDE.md` classification rule, and it is recorded as such **even though it does not
block R0**: model files in a developer checkout are normally writable by their owner. It becomes
blocking the moment a model lives on a read-only mount, in a root-owned shared cache, or in a
container image layer — all ordinary deployment shapes for the runtime this repository is building.

The request is filed as Request 21 in `docs/align-requests.md`, `Status: PROPOSED`, `Blocking: no`,
proposing `fs.open_ro(path) -> Result<file, Error>` opening `O_RDONLY` and supporting `pread`/`len`
but not `pwrite`, with acceptance criteria naming `--inspect-gguf` against a `chmod 444` model file.
R0 ships on `fs.open_rw`; this section is the evidence that the gap was classified rather than
worked around.

Two things R0 explicitly does **not** do: it does not build a compatibility layer, and it does not
write against the proposed surface. It uses `fs.open_rw` today. The one visible consequence is a
documented precondition — the model path must be writable by the invoking user — and a
correspondingly clear error: an `EACCES` from `fs.open_rw` surfaces as `Err(Error.Denied)` from
`inspect`, with no document, which a caller can distinguish from every structural code above.

`fs.read_bytes_view` further limits the blast radius: it is an existing arena-scoped mmap surface
that needs no write permission, so a future R0 variant has a real fallback. Section 5.3 records why
it is not the primary strategy today.

### 2.8 Ledger dimensions

| Dimension | Contract | Owner | Acceptance |
| --- | --- | --- | --- |
| Exact command/API | Section 2.2 and `gguf.inspect` only; no aliases, no flags | `src/gguf.align`, `src/main.align` | `gguf-smoke` CLI cases |
| Inputs and defaults | One model path; optional destination path; `alignment` defaults to 32; `ARRAY_PREVIEW` is fixed at 8; no ambient options | `src/main.align`, `gguf.inspect` | arity, option-isolation, and default-alignment cases |
| Results and errors | `Ok` + `status: "ok"`; `Ok` + `status: "error"` for structural defects; `Err` only for argument or OS failure | `gguf.inspect`, `src/main.align` | error-code corpus, one fixture per row of section 2.6 |
| Multi-invalid precedence | Section 2.6 is strictly ordered; the first applicable row wins | `src/gguf.align` | multi-defect fixtures asserting the earlier code |
| Ownership and lifetime | Every retained text is cloned before the next `ensure`; the document is moved into its sole owner | `src/gguf.align` | refill-boundary and large-file cases |
| Allocation | One fd, one window buffer for the whole inspection (growth and short-read continuations excepted), one `string` per retained text, one document. Rendering holds the tensor JSON twice at its peak — see the deferred item in section 5.4 | `src/gguf.align` | `bytes_read` and window-count assertions |
| Persisted/cache identity | `N/A`. R0 writes one caller-named output document and reads nothing it wrote. It creates no cache, no index, no digest-addressed artifact, and changes no Align compiler cache policy | `N/A` with this reason | no cache behavior is claimed or tested |
| Schema version | `schema_version: 1`; any field addition, removal, reorder, or type change requires version 2 | `src/gguf.align` | golden document bytes, field-order assertion |
| Validation order | Section 2.6, deterministic and side-effect ordered; no output before the walk completes | `src/gguf.align` | ordered malformed corpus, untouched-destination assertion |
| Prerequisites | None beyond the pinned toolchain. Every consumed surface is verified present at `4b515f8d` in section 2.1; no Align request gates implementation | `src/gguf.align` | `make check`, `make build` |
| Acceptance evidence | `gguf-smoke` for correctness; `gguf-reference-parity` for the roadmap gate | section 4 | section 4.2, section 4.4 |
| Metrics | Primary: correctness parity against a reference tool. Secondary: `bytes_read` | section 4.5 | parity run and `bytes_read` bound |
| Text/wire boundary | Canonical UTF-8 JSON, declaration order; non-UTF-8 input becomes `null` plus a flag, never invalid JSON; embedded NUL in a GGUF string is escaped by the existing encoder | `src/gguf.align` | escape and invalid-UTF-8 fixtures |
| Runtime-inspection fields | Every field is decoded from the file or computed from decoded values. No reflection, no source read, no environment read | `src/gguf.align` | producer-provenance review, environment-perturbation case |
| Platform scope | Platform-independent decoding. The codec assumes a little-endian host, which Align already assumes | `src/gguf.align` | no target-local claim; no platform profile is selected |
| Milestone ordering | R0 consumes no R1 or R2 decision. It defines record types those slices will read; it does not define Model IR, Block IR, or layout | this document | section 5 |

## 3. Closure matrix

This is the pre-implementation closure contract. Every applicable cell names its implementation
owner and the exact regression that closes it. `N/A` carries a concrete reason; `DEFERRED` is an
intentional design decision recorded in section 5, not a missing owner.

The regression names below are cases inside `scripts/run-gguf-smoke` (section 4.2) unless another
runner is named.

### 3.1 `src/gguf.align` — cursor and container decode

| Case | Contract to close | Implementation | Exact regression |
| --- | --- | --- | --- |
| Construction — handle | `fs.open_rw` result is bound to a local before any method call; `f.len()` is read once into `file_size` before decoding | `gguf.inspect` prologue | `open-and-size` case asserts `file_size` equals the fixture's byte length |
| Construction — window | `buffer(WINDOW_BYTES)` is a `mut` local; the first `ensure` triggers the first `pread` at offset 0 | `gguf.inspect` prologue, `refill` (section 6, item 1) | `bytes-read-exact` case asserts the exact `bytes_read` for a single-window fixture |
| Construction — record | `GgufInspection` is built with every field explicitly initialized, including the `-1`/`""`/`null` sentinels | `gguf.inspect` epilogue | `error-sentinels` case asserts each unreached field on a header-only failure |
| Bounds precondition | Every codec call is reached only through `ensure`; no codec offset is computed outside `pos - window_base` | `ensure`, all `decode_*` | `truncated-every-boundary` case: one fixture truncated at each of 9 structural boundaries, each yielding `GGUF_TRUNCATED` and **no abort** |
| Refill boundary | An item that spans a window boundary decodes identically to one that does not | `ensure`, `refill` | `refill-boundary` case: the same logical file emitted twice with window sizes forcing a split mid-key, mid-string, and mid-dims |
| Borrow expiry | Every retained `str` is `.clone()`d before the next `ensure`; no borrowed view survives a refill | all `decode_*` | `refill-boundary` case compares every key, string value, preview element, and tensor name against the single-window run |
| Explicit growth | Capacity doubles to fit an oversized item and never shrinks; a request above `MAX_ITEM_BYTES` fails without allocating | `ensure` growth path | `window-growth` case: a fixture with one string larger than the initial window; `item-too-large` case asserts `GGUF_ITEM_TOO_LARGE` |
| Skip path | Fixed-width array tails advance `pos` without reading and contribute nothing to `bytes_read` | `skip` | `skip-accounting` case asserts `bytes_read` is lower by exactly `(length - 8) * width` versus a string-array control |
| Success — header | Magic, version, and both counts decode from the 24-byte prologue | `decode_header` | `header-fields` case against fixture-declared values |
| Success — all 13 types | Each value type decodes to its section 2.4.2 JSON shape | `decode_value` | `all-value-types` case: one KV per type with fixture-declared golden values |
| Success — float exactness | `value` and `value_bits` come from two codec reads at the same offset; no `as` conversion touches a float | `decode_f32`, `decode_f64` | `float-bits` case asserts `value_bits` for `+0.0`, `-0.0`, `1.0`, `f32` max, `f64` pi, and a subnormal |
| Success — arrays | `preview`, `length`, `truncated` follow section 2.4.4 for every element type | `decode_array` | `array-shapes` case: length 0, 1, 8, and 9 for `INT32` and for `STRING` |
| Success — tensor table | Name, `n_dims`, `dims`, type id/name/known, `offset`, `absolute_offset` | `decode_tensor` | `tensor-table` case, including a 1-dim, a 2-dim, and a 4-dim tensor |
| Success — alignment | `general.alignment` overrides the default and sets `alignment_source` | `resolve_alignment` | `alignment-default` and `alignment-override` cases (32 default, 64 override) |
| Success — data offset | `data_offset` is `tensor_table_end` rounded up by remainder arithmetic, not bit masking | `compute_data_offset` | `data-offset` case for a table end that is already aligned and one that is not |
| Success — architecture | `general.architecture` is surfaced to the top level when it is a valid UTF-8 STRING | `resolve_architecture` | `architecture` case, plus an `architecture-absent` case asserting `null` |
| Failure — every error code | Each reachable code of section 2.6 is produced by at least one fixture, with the correct `error_offset`; the two unreachable fail-closed guards are named in section 6, items 6 and 17 | `decode_*` guards | `error-corpus` case: one negative fixture per code, asserting code and offset |
| Failure — precedence | A file with two defects reports the earlier row of section 2.6 | ordered guards | `error-precedence` case: bad magic + bad version; implausible KV count + truncation; misaligned tensor + out-of-range tensor |
| Failure — u64 representability | Bit 63 is tested before any `as i64` | `read_u64_checked` | `overflow-corpus` case: counts, string lengths, array lengths, `UINT64` values, and tensor offsets each set to `0x8000000000000001` |
| Malformed — non-UTF-8 | A bad key, a bad string value, a bad preview element, and a bad tensor name each render as `null` plus their flag, and none is fatal | `decode_text` | `invalid-utf8` case with a `0xFF` byte in each of the four positions |
| Malformed — JSON safety | A GGUF string containing `"`, `\`, a control byte, an embedded NUL, and a 4-byte scalar survives into valid, parseable JSON | existing `core.json` encoder | `wire-escapes` case parses the document with Python's `json` and compares to fixture-declared values |
| Early exit | On any failure the walk stops immediately; `metadata` and `tensors` contain exactly the records completed before it; nothing after is decoded | `?` and guard returns in `gguf.inspect` | `partial-document` case asserts the exact record counts for a failure injected at KV 3 of 6 and at tensor 2 of 3 |
| Early exit — no side effect | No output file is written and no stdout is produced before the walk completes | `src/main.align` ordering | `untouched-destination` case: a sentinel file at the destination path is byte-unchanged after a structural failure |
| Cleanup | The fd and every window buffer are released by scope `Drop`; there is no `f.close()` at this pin, and none is synthesized | scope structure | `repeat-inspect` case: 64 sequential inspections in one process leak no descriptor, asserted by comparing open-fd counts |
| Cleanup — error path | A failure mid-walk drops partially decoded owned records with no observable leak | Align `Drop` | `error-corpus` case run under the same fd-count assertion |
| Branch joins | `Ok`/`Error` status construction and the document return have exactly one owner | `gguf.inspect` return | `document-move` case asserts both statuses produce a complete document |
| Loop joins | The metadata loop and the tensor loop each terminate on count, on failure, and on a zero count | loop guards | `empty-container` case: 0 KVs and 0 tensors, valid document, `status: "ok"` |
| Move-out | The document `string` is moved into `GgufInspection.document`, not cloned | `gguf.inspect` epilogue | `document-move` case; ownership reviewed against `docs/specs/c8-speed-first.md` section 2.8 |
| Generic monomorphization | `N/A`: R0 declares no generic type or function | `N/A` with this reason | — |
| Shared/process-global state | `N/A`: the module holds no process-global or connection-global state; every value is per-call | `N/A` with this reason | `repeat-inspect` case also serves as the same-process pairing evidence |
| Concurrency | `N/A`: R0 is read-only and holds no lock. Two concurrent inspections of one file are independent; no atomicity is claimed for a file mutated during inspection | `N/A` with this reason | documented unsupported caller case |
| Per-unit vs whole-program | The public surface compiles identically imported and whole-program | module boundary | `make check`, `alignc check-per-unit`, `make build` |

### 3.2 `src/main.align` — CLI arm

| Case | Contract to close | Implementation | Exact regression |
| --- | --- | --- | --- |
| Construction — dispatch | `--inspect-gguf` is selected only at `args[1]`; arity is checked before any path or file work | `main` dispatch chain | `cli-arity` case: 1, 2, 3, 4, and 5 arguments |
| Construction — path validation | Empty, over-length, and NUL-bearing paths are rejected before `fs.open_rw` | `inspect_gguf_demo` | `cli-path` case, asserting no file is created |
| Success — one operand | The document goes to stdout with a trailing newline and nothing else is printed | `inspect_gguf_demo` | `stdout-document` case pipes stdout directly into a JSON parser |
| Success — two operands | The document goes to the named file; the summary block goes to stdout | `inspect_gguf_demo` | `file-document` case |
| Byte identity across forms | Both forms emit identical document bytes | `inspect_gguf_demo` | `form-parity` case diffs the two outputs |
| Failure mapping | `status: "error"` becomes `Err(Error.Invalid)` **after** the document is emitted | `inspect_gguf_demo` epilogue | `error-corpus` cases assert both a nonzero exit and a complete document |
| Failure — OS | An unreadable or absent path returns `Err` with no document and no summary | `?` propagation | `missing-path` and `denied-path` cases; `denied-path` copies the positive fixture, `chmod 000`s it, and asserts a nonzero exit, empty stdout, and an untouched destination sentinel. Running as root ignores mode bits, so there the case prints an explicit `SKIPPED` note instead of asserting |
| Early exit | An arity or path failure produces no output at all | guard ordering | `cli-arity` and `cli-path` cases assert empty stdout |
| Unknown-selector compatibility | An unrecognized `args[1]` still prints help and returns `Ok(())` | unchanged dispatch chain | `unknown-selector` case, asserting exit 0 |
| Option/environment isolation | No environment variable changes any document byte | no env read exists | `env-perturbation` case runs with a perturbed environment and diffs the document |
| Help text | One new usage line names both forms | `print_help` | `cli-arity` no-argument case matches the help block |
| Cleanup | `N/A`: the arm owns no resource beyond the `GgufInspection` record it returns | `N/A` with this reason | — |

### 3.3 `Makefile` and `scripts/` — build and verification graph

| Case | Contract to close | Implementation | Exact regression |
| --- | --- | --- | --- |
| Target definition | `gguf-smoke` depends on `build` and runs `./scripts/run-gguf-smoke`; it is added to `.PHONY` | `Makefile` | `make gguf-smoke` from a clean tree |
| Aggregate membership | `gguf-smoke` joins `HOSTED_CHECK_TARGETS`. It is self-contained, needs no model and no network, and runs in seconds | `Makefile` | `make gate-topology-check` after the membership change |
| Topology consistency | The `.PHONY` list, the target list, and `HOSTED_CHECK_TARGETS` agree | `Makefile` | `python3 scripts/check-gate-topology` |
| Qualification exclusion | `gguf-reference-parity` is a focused, opt-in target and joins **no** aggregate | `Makefile` | `make gate-topology-check` asserts its absence from both lists |
| Fixture generation | `scripts/gguf_fixture.py` writes every fixture into a `mktemp -d` tree and nothing into the repository | `scripts/run-gguf-smoke` | `git status --porcelain` is empty after the smoke run |
| Fixture independence | The generator derives no value from `src/gguf.align`; it writes bytes from its own struct-packing tables | `scripts/gguf_fixture.py` | code review; the generator imports only `struct`, `hashlib`, and `pathlib` |
| Cleanup | Every fixture path is removed by a shell `trap` on `EXIT`, including on failure | `scripts/run-gguf-smoke` | `stale-fixture` case, restated (section 6, item 21) to what a runner can prove about its own cleanup: exactly one `trap cleanup EXIT` owns the `mktemp -d` root on every exit path, and the run's last assertion is that the root is **still present** at that point, so nothing removes it early and nothing but the trap removes it at all. The complementary `git`-independent leak sweep asserts that no `*.gguf` or `manifest.json` reached the repository |
| Reference skip | Absent `ALIGN_LLM_GGUF_REFERENCE` or absent model prints an explicit `N/A` line and exits 0 | `scripts/run-gguf-reference-parity` | run with the variable unset; assert the exact skip line |
| Reference isolation | The parity runner never modifies the model file and never writes outside its temp root | `scripts/run-gguf-reference-parity` | model `mtime` and size compared before and after |
| Documentation | `docs/specs/roadmap.md` section R0 and `HANDOFF.md` name this document and the two runners | integration commit | out of scope for this design-only file; recorded as a follow-on |

## 4. Fixture and qualification design

### 4.1 `scripts/gguf_fixture.py`

An independent GGUF writer. It emits container bytes from its own `struct`-packing tables and an
ordered field list transcribed from section 2.4; it never imports, parses, or derives a value from
`src/gguf.align`. Its expected-value tables are computed in Python and asserted against the
document, which is what makes it a real differential check rather than a mirror of the decoder.

Fixtures are generated into a `mktemp -d` tree at test time and are **never committed**. A model
file, even a synthetic one, is a build input, not source; committing one would put binary blobs in a
repository that already forbids weights.

The positive fixture is a complete, valid v3 container under 64 KiB containing:

- One KV of every one of the thirteen types, with fixture-declared golden values, including
  `UINT8`, `INT8`, `UINT16`, `INT16`, `UINT64`, `INT64`, and `FLOAT64` — none of which appear in the
  reference model, which is precisely why the synthetic fixture is required and the parity
  qualification is not sufficient on its own.
- Float edge values: `+0.0`, `-0.0`, `1.0`, `f32` max, the `f32` nearest to `1e-6`, `f64` pi, and an
  `f64` subnormal, each with its expected `value_bits` computed by `struct.pack`.
- `UINT64` at exactly `i64` max (accepted) — its overflow twin lives in the negative corpus.
- A `STRING` containing `"`, `\`, `/`, the five short-escape control bytes, `U+0001`, an embedded
  NUL, and a 4-byte UTF-8 scalar.
- A `STRING` whose bytes contain `0xFF`, exercising the `invalid_utf8` fallback.
- A key whose bytes contain `0xFF`, exercising `key_invalid_utf8`.
- Arrays of length 0, 1, 8, and 9 for `INT32`, and of length 0, 1, 8, and 9 for `STRING`, pinning
  both sides of the `truncated` boundary.
- An array of `FLOAT32`, pinning the `{"value": …, "bits": …}` element shape.
- Four tensors: three with 1, 2, and 4 dimensions and type ids `0` (`F32`), `12` (`Q4_K`), and `199`
  (unknown, asserting `type_known: false`), plus a fourth whose name bytes contain `0xFF`, which is
  the tensor-name half of the `invalid-utf8` cell. All four carry aligned offsets, and the container
  has real padding before the data section.
- A minimal data section of the exact declared size, which the inspection must not decode.

Two variants of the positive fixture are generated: one without `general.alignment` (default 32) and
one with `general.alignment = 64`. A third variant re-emits the same logical content with padding
that forces items to straddle a window boundary, which is what closes the refill-boundary and
borrow-expiry cells of section 3.1.

Three further positive containers pin the section 2.3 architecture contract: one whose
`general.architecture` is present and empty, one whose value carries a newline, a tab, and `0x7f`,
and one whose `general.architecture` is a `UINT32`. Each declares the exact summary line the CLI
must print, so the escaping and the meaning of `-` are asserted rather than assumed.

The negative corpus is one file per reachable row of the section 2.6 table, plus the precedence
pairs. Each carries its expected code and its expected `error_offset`, both computed by the
generator from the byte layout it wrote. Two of those files are wrap-specific: a single-tensor
container and a two-tensor container whose last entry declares the alignment-correct, representable
offset `0x7FFFFFFFFFFFFFE0`, for which `data_offset + offset` wraps negative. Both must report
`GGUF_TENSOR_OUT_OF_RANGE`, exit nonzero, and render `absolute_offset: -1`; the two-tensor file
exists so that a check of only the first entry cannot pass.

### 4.2 Owner — `scripts/run-gguf-smoke`, `make gguf-smoke`

The narrow durable owner. It follows the `scripts/run-index-smoke` shape: resolve the repository
root, `mktemp -d`, `trap cleanup EXIT`, generate fixtures, run `./main --inspect-gguf`, and assert
with an inline Python block that parses the document with the standard `json` module.

It requires no model, no network, and no reference tool, runs in seconds, and is therefore added to
`HOSTED_CHECK_TARGETS`. It covers every closure cell in sections 3.1 and 3.2 that names a case
without another runner.

### 4.3 `bytes_read` — definition and measurement

`bytes_read` is the exact sum of the counts returned by every `f.pread` call during one `inspect`.
It is not an estimate, not `data_offset`, and not derived from the file size. It is incremented in
exactly one place, `refill`, by exactly the value `pread` returned.

Three properties follow, and each is asserted:

1. **Deterministic for a small file.** For a fixture smaller than `WINDOW_BYTES`, `bytes_read`
   equals the file size exactly: the header read returns 24 and the single refill returns the
   remainder. The `bytes-read-exact` case asserts the literal number.
2. **Skips are excluded.** The `skip-accounting` case asserts that a fixed-width array tail lowers
   `bytes_read` by exactly `(length - 8) * width` relative to a control fixture.
3. **Bounded for a large file.** `bytes_read < data_offset + WINDOW_BYTES`. The upper term is the
   final window, which may over-read past the tensor table into the data section. Those bytes are
   never decoded, retained, or rendered — the honest statement is that R0 does not *interpret*
   tensor payload, not that it never touches a payload byte.

For the reference model the prediction is concrete and falsifiable: `data_offset` is 5,953,536,
608,224 bytes of the `tokenizer.ggml.token_type` array are skipped, so the assertion is
`5,345,312 <= bytes_read < 7,002,112`. The lower bound is the exact unskipped prefix; the upper
bound is that value plus one full window. Against a 4,683,073,536-byte file the measured value is
under 0.15 percent, which is the whole claim R0 makes about read volume.

### 4.4 Focused qualification — `scripts/run-gguf-reference-parity`

Opt-in, never in an aggregate, and never in CI. It discharges the roadmap gate by comparing the R0
document against a llama.cpp reference reader on a real model.

Inputs, both required, both explicitly skippable:

- `ALIGN_LLM_GGUF_REFERENCE` — path to the reference executable, expected to be `llama-gguf`.
- `ALIGN_LLM_GGUF_MODEL` — path to the model. There is no default: an unset value is a skip, never
  a guess at a local path.

If either is unset or absent, the runner prints one exact line —
`gguf reference parity: N/A (ALIGN_LLM_GGUF_REFERENCE unset)` or the model equivalent — and exits 0.
A qualification that silently passes when its subject is missing is worse than no qualification, so
the skip is explicit, is named in the pull request as the `N/A` reason, and never counts as a pass.

**Parity scope is honest about what the reference provides.** `llama-gguf FILE r n` prints the
version, the alignment, the data offset, the KV count, the ordered key names, the tensor count, and
each tensor's name and offset. It does **not** print value types, values, dimension counts, or
dimensions. The comparison therefore covers exactly:

| R0 field | Reference line | Comparison |
| --- | --- | --- |
| `header.version` | `version:` | integer equality |
| `alignment` | `alignment:` | integer equality |
| `data_offset` | `data offset:` | integer equality |
| `header.metadata_kv_count` | `n_kv:` | integer equality |
| `metadata[i].key` | `kv[i]: key = …` | ordered string equality across all pairs |
| `header.tensor_count` | `n_tensors:` | integer equality |
| `tensors[i].name` | `tensor[i]: name = …` | ordered string equality across all entries |
| `tensors[i].offset` | `tensor[i]: … offset = …` | integer equality across all entries |

For the named model the expected values are 3, 32, 5,953,536, 29, and 339. Value types, values,
dims, and `type_name` are **outside** reference parity and are owned by the synthetic corpus of
section 4.1 instead. Recording that boundary is the point: the roadmap gate says "agrees with an
existing tool", and this is exactly how far that agreement reaches with the tool available.

The runner also asserts the section 4.3 `bytes_read` bound, records the wall-clock duration, and
verifies that the model's size and modification time are unchanged, which is the read-only proof.

If a richer reference becomes available — the Python `gguf` package exposes every KV value and each
tensor's dims and type — the runner gains an optional second mode comparing values by `value_bits`
and by `struct.pack('<f', …)` round-trip rather than by decimal string, because the two tools format
floats differently while agreeing bit-for-bit. That mode is additive and does not change the
contract above.

### 4.5 Metrics

**Primary — correctness parity.** The section 4.4 comparison passes on the reference model, and the
full synthetic corpus of section 4.1 passes in `gguf-smoke`. This is a pass/fail correctness metric,
not a speed metric.

**Secondary — `bytes_read`.** Defined and measured as in section 4.3, with the exact assertion
`bytes_read < data_offset + WINDOW_BYTES` and the reference-model expectation of roughly 5.35 MB
against a 4.68 GB file.

R0 makes **no performance claim**. Wall-clock duration is recorded by the parity runner as a
diagnostic so that a later regression is visible, but no threshold is asserted and no baseline is
established. Under `CLAUDE.md`, a speed claim would require a reproducible benchmark and a named
baseline; R0 has neither and does not pretend to.

## 5. Deferred surfaces

### 5.1 R1 hooks — model frontends

R0 deliberately stops at "what the file declares". It does not interpret `qwen2.block_count`,
`qwen2.attention.head_count_kv`, or the rope parameters, and it does not map tensor names to layers.
R1 frontends — `src/frontend_qwen.align`, and later `src/frontend_gpt_oss.align`, flat under `src/`
because Align's unit of modularity is one file per module — consume `gguf.read_table` and its typed
accessors to build a Model IR. `GgufKv` and `GgufTensor` were never implemented: Request 22 rejects
indexing an array of Move elements, so the table is carried as concatenated text streams plus
parallel `array<i64>` columns. The seam is deliberate: architecture-specific knowledge must not leak
into the container reader, exactly as `docs/specs/align-llm.md` section 5.1 requires.

Two consequences are accepted now. First, a caller needing the full 152,064-entry token array cannot
get it from the section 2.4 document, and R1 does not add one: `docs/specs/r1-qwen-model-ir.md`
section 5.2 keeps the tokenizer out of scope precisely so that Request 22 stays non-blocking. A
`gguf.read_string_array(path, key)` becomes possible when Request 22 merges, and is owned by the
tokenizer capability, not by R1. Second, `type_name` is a label only — element layout, block size, and scale encoding are
R2's.

### 5.2 R2 hooks — `align-pack`

`data_offset`, per-tensor `absolute_offset`, `type`, and `dims` are exactly the inputs a layout
planner needs, which is why `absolute_offset` is precomputed here rather than left to each consumer.
R0 defines no `.alignpack` format, no reordering policy, and no prefetch plan.

### 5.3 The mmap arena alternative

`fs.read_bytes_view(path) -> Result<bytes, Error>` exists at the pin and returns an arena-scoped
mmap view. Align's own `docs/open-questions.md` motivates it with this exact use case: "a multi-GB
binary file (GGUF) cannot be mmap'd today". It is a real alternative to the pread window, and it is
deferred, not overlooked.

It would be simpler — no cursor, no refill, no growth, and `bv.u32_le(off)` directly over the whole
file — and it needs no write permission, sidestepping the section 2.7 gap entirely. Three reasons
select the window instead for R0:

1. **The metric.** `bytes_read` is the named secondary metric and the evidence for the
   "header and metadata only" claim. Under mmap the program cannot observe how many bytes the kernel
   faulted in, so the claim would become unmeasurable from inside the process.
2. **Bounded, visible memory.** A 1 MiB window whose every growth step is explicit is easier to
   reason about and to review than a 4.6 GB mapping, and `CLAUDE.md` requires allocation to stay
   visible.
3. **Region escape.** A `bytes` view is region-bound to its `arena {}` block and is caught escaping
   through return, arena-block value, and match-arm unwrap. The entire decode and document
   construction would have to live inside that block, with the owned document `string` as the only
   value crossing out. That is workable but it couples R0's control flow to arena semantics for no
   correctness gain.

The condition that would select mmap: R2 needs random access across the *data* section for layout
planning, where a forward window is the wrong shape and where page-fault behavior is the thing being
measured rather than an obstacle to measurement. At that point R0's decoder should be refactored to
take a `bytes` view instead of a cursor, and the pread path retained only for the metric.

### 5.4 Other deferred items

- **Big-endian GGUF v3.** Undetectable from the container; recorded as a limitation in section 2.6.
  The `_be` codec names exist at the pin, so support is a data change, not a language gap, if a
  heuristic ever justifies it.
- **Multi-shard models.** `split.*` metadata is reported; following the chain is deferred to
  whichever slice first needs a sharded model.
- **`fs.open_ro`.** Section 2.7. Non-blocking, recorded, not worked around.
- **One-pass tensor rendering.** `absolute_offset` needs `data_offset`, which is known only after
  the whole table has been walked, so each entry is accumulated up to its `offset` field and closed
  during rendering. `render_tensors` therefore builds a second complete copy of the tensor JSON, and
  peak memory during rendering is twice the tensor-array size — at `MAX_TENSORS` a bounded but real
  cost, and roughly 60 KB for the 339-tensor reference model. Closing it needs either a rewritable
  placeholder in the accumulated bytes or an indexable record array, which Request 22 currently
  blocks. Deferred deliberately: R0 makes no performance claim, and the alternative would trade a
  measured cost for an unmeasured one.
- **Full array extraction.** Section 5.1.
- **A GGUF writer.** Out of scope permanently for R0; if `align-pack` needs to emit GGUF rather than
  `.alignpack`, that is an R2 decision with its own contract.

## 6. Implementation corrections to this plan

The capability was implemented against this plan at pin `4b515f8d`. Every item below is a
correction to a promise this document made, recorded here with the section it amends, the evidence
that forced it, and the owner test that now holds it. Plan, code, and tests changed together; no
item below is a deferral.

| # | Amends | Correction | Evidence | Owner |
| --- | --- | --- | --- | --- |
| 1 | 2.5.1, 2.5.3, 3.1 | `GgufCursor` cannot own `handle: file` or `window: buffer`. `file` never rides an aggregate other than its constructor's `Result<file, Error>`, and every native buffer fill requires a bare `mut` buffer **local**. Both are locals in `gguf.inspect` and reach the cursor operations as `borrow handle: file` / `borrow mut window: buffer`. The reading contract is unchanged | `draft.md` §18.2; `align_sema::require_mut_buffer_local` | `make check`; every `gguf-smoke` case |
| 2 | 2.5.1, 2.5.3 | The window buffer is **reused** across refills rather than reallocated per refill. The plan's own release condition was verified: `align_rt_io_file_pread` fills from the buffer's capacity and publishes exactly the returned count as its length on every call, including short and EOF reads. One window is allocated; growth is the only reallocation | `align_runtime` `align_rt_io_file_pread` plus its `file_pread_short_at_eof_returns_actual_count` unit | `bytes-read-exact`, `window-growth` |
| 3 | 2.5.4, 3.1 | `builder` and `array_builder<T>` are not parameter types at this pin, so a `walk` helper cannot accumulate the document bodies. The walk lives in `gguf.inspect`, and each fallible step records its fault as a value and leaves the walk immediately. This is exactly the section 2.6 early-exit contract, expressed without a helper | `unknown type: 'builder'` from the pinned compiler | `partial-document` assertions in the error corpus |
| 4 | 2.4.2, 2.4.3, 2.4.4 | A non-finite `FLOAT32`/`FLOAT64` renders `"value": null` (and `{"value": null, "bits": …}` in a preview). `write_float` spells an infinity `inf` and a NaN `NaN`, neither of which is JSON, so the previous contract could emit an unparseable document. `value_bits` is unchanged and remains authoritative | Rust `Display` for `f32`/`f64` | `full` fixture `kv.float32.inf`, `kv.float64.nan`; the whole corpus is parsed with Python's `json` |
| 5 | 2.4.3 | The `FLOAT32` example renders `1000000.0`, not `1000000`. `write_float` always emits a decimal point | observed output | `float-bits` comparisons |
| 6 | 2.6, 3.1, 4.1 | `GGUF_ITEM_TOO_LARGE` is **unreachable** while `MAX_STRING_BYTES == MAX_ITEM_BYTES == 16777216`: every declared string or name length above the cap is already rejected as `GGUF_STRING_TOO_LARGE` before `ensure` is reached, and no other item can request more than 32 bytes. The guard is retained as fail-closed defense and carries no negative fixture. With `GGUF_WINDOW_UNAVAILABLE` (item 17) the section 2.6 table has 17 rows and the error corpus covers the 15 reachable ones | validation order of section 2.6 | none; recorded as an unsatisfiable closure cell |
| 7 | 3.1 | In `truncated-every-boundary`, a cut below the 24-byte header yields `GGUF_TOO_SMALL`, not `GGUF_TRUNCATED` — the container is too small to describe itself at all. The invariant asserted at every boundary is the one that matters: a recorded error code and a recorded exit, **never** an abort | section 2.6 step 4 precedes step 5 | 13 `truncated-boundary-*` cases, each asserting a non-signal exit |
| 8 | 2.6, 3.1 | `error_offset` for `GGUF_TRUNCATED` is the cursor position at the failing `ensure` — the first byte of the range that could not be read. For an arbitrary truncation point that value is not independently predictable, so the boundary sweep asserts `0 <= error_offset <= cut`; the two hand-computed truncations assert the exact offset. Every other code asserts an exact, generator-computed offset | — | `error-truncated-after-header` (24), `error-truncated-mid-header` (24), `error-truncated-data-offset` |
| 9 | 3.2 | `untouched-destination` splits in two. A structural failure **does** replace the destination, with the complete failure document — that is the failure-persistence contract, and the assertion is that the destination parses and carries the expected `error_code`, never a partial write. The byte-unchanged sentinel assertion belongs to the argument and OS-failure paths, where no document exists | section 2.5.4 | `untouched-destination` (absent model) and the structural-failure replacement assertion |
| 10 | 3.1 | `repeat-inspect` cannot be "64 inspections in one process": the CLI contract is one inspection per invocation and R0 ships no in-process repeat driver. It is replaced by 64 sequential invocations asserting byte-identical documents, plus one inspection under `ulimit -n 64`, which bounds descriptor use directly | CLI surface of section 2.2 | `repeat-inspect`, the low-descriptor run |
| 11 | 3.2 | A NUL-bearing path cannot be delivered through `argv`, so that third `cli-path` case is `N/A` at the CLI. The empty and over-length cases are asserted, and the module-level NUL guard remains | POSIX `execve` | `cli-path` |
| 12 | 3.3, 4.1 | The generator imports `json`, `math`, `struct`, `sys`, and `pathlib` — `json` to emit the expectation manifest, `math` for the float edge values. It still imports nothing from `src/`, and derives no value from the decoder | — | code review |
| 13 | 3.3 | Fixture cleanliness is proven by searching the repository for any `*.gguf` or `manifest.json` after the run rather than by requiring `git status --porcelain` to be empty, which cannot hold in a working tree under development | — | `run-gguf-smoke` epilogue |
| 14 | 4.3 | Property 2 is asserted in its exact arithmetic form rather than against a same-size string-array control, whose byte layout cannot be made comparable. For the skip fixture the assertion is `bytes_read == WINDOW_BYTES + (file_size - array_end)` **and** `file_size - bytes_read == array_end - WINDOW_BYTES`, both computed by the generator from the layout it wrote. The STRING control asserts that at most 64 bytes go unread | — | `skip-accounting`, `skip-accounting-string-control` |

Items 15 through 24 are the corrections the first comprehensive review forced. Items 15 to 20 are
code corrections; 21 to 24 correct claims this document made that the shipped runners never held.

| # | Amends | Correction | Evidence | Owner |
| --- | --- | --- | --- | --- |
| 15 | 2.4.5, 2.6, 3.1, 4.1 | **`data_offset + offset` wrapped.** Align integer overflow is two's-complement wrap with no trap, and `read_u64_checked` bounds a tensor offset only to `[0, i64::MAX]`. The step 9 containment test and the `absolute_offset` rendering both formed that sum before testing it, so an alignment-correct offset such as `0x7FFFFFFFFFFFFFE0` produced `status: "ok"`, exit `0`, and a negative `absolute_offset`. The containment test is now the subtraction `offset > file_size - data_offset` — both operands non-negative, with `data_offset <= file_size` guaranteed by `resolve_data_offset` — and the rendering forms the sum only when `offset <= I64_MAX - data_offset`, emitting `-1` otherwise. **Class audit:** every other addition on a file-derived value is bounded by `file_size` plus a capped constant (`ensure`, `skip`, `resolve_data_offset`, every `pos + width`, every window-relative offset), and the single multiplication `(length - ARRAY_PREVIEW) * width` is bounded by `MAX_ARRAY_ELEMENTS * 8 = 134,217,728`; no third site can wrap | reproduction before the fix: `status: "ok"`, exit `0`, `absolute_offset: -9223372036854775712` | `error-tensor-offset-overflow`, `error-tensor-offset-overflow-second-entry` |
| 16 | 2.5.1 | **A short `pread` is completed, not reported as truncation.** `f.pread` reads one window and publishes exactly the count the syscall returned, so a short read on a large item would have surfaced as a spurious `GGUF_TRUNCATED`. `refill` now takes the needed length and loops until the range is resident, reading each continuation into its own bare `mut` buffer local — the runtime fills a buffer from its own capacity, so a continuation cannot be read into `window` — and appending it to the window, which never exceeds the capacity `ensure` reserved. Every continuation count enters `bytes_read`. The loop cannot be provoked from a fixture: on a regular file `ensure` has already proved that at least `n` bytes remain, so `pread` never returns fewer, and the completion is defensive on the item 6 precedent. The mechanism itself was verified out of tree with a throwaway Align program that preads 4 bytes, preads 4 more into a continuation buffer, appends, and observes an 8-byte window ending in the eighth byte | `align_rt_io_file_pread`; `docs/language-spec.md:1043` "reads one window"; the out-of-tree append probe | `make check`; every `gguf-smoke` case, `window-growth` and `refill-boundary-*` in particular |
| 17 | 2.5.2, 2.6 | **A failed window allocation no longer reports `GGUF_TRUNCATED`.** `buffer(cap)` reserves fallibly and degrades to zero capacity, and a `pread` into a zero-capacity buffer returns `0` with no syscall. Capacity is not observable at this pin (`b.len()` is the last read's count; there is no `b.cap()`), so the observable consequence is tested instead: a zero-length read at a position `ensure` has already proved strictly inside the file reports the new `GGUF_WINDOW_UNAVAILABLE`. The same code covers a file that shrank mid-inspection | `align_rt_buffer_new` (`try_reserve_exact` -> `cap = 0`), `align_rt_io_file_pread` (`cap == 0` returns `0`) | none; a fail-closed guard on the item 6 precedent |
| 18 | 2.3, 2.5.4 | **`GgufInspection` carries `architecture_present`.** The summary printed `-` for a `general.architecture` that was present and empty, although section 2.3 reserves `-` for absent or non-UTF-8. The record now exposes presence explicitly, and the CLI prints an empty line for present-and-empty and `-` only for absent, non-STRING, or non-UTF-8. The document is unchanged — it already distinguished `""` from `null` — so `schema_version` stays `1` | section 2.3 as written | `architecture-present-empty`, `architecture-non-string`, `empty-container` |
| 19 | 2.4.1 | **The header sentence was too strong.** It claimed only `GGUF_TOO_SMALL` leaves all four header fields unset, but a magic that is not valid UTF-8 also leaves `magic` as `""` with the other three at `-1`. R0 records the magic as text or not at all — a hexadecimal rendering would change the field's type for one failure mode — so the sentence is widened to state both cases, and a fixture pins the behavior | `decode_text` returns `valid: false` with an empty text | `error-bad-magic-invalid-utf8` |
| 20 | 2.3, 3.2 | **The summary escapes control bytes.** `general.architecture` was printed verbatim into a block that a consumer reads positionally, so a value containing a newline injected lines into it. Every byte below `0x20` and `0x7f` is now replaced by `\xNN` before printing. The JSON document is unaffected | the smoke's own positional parse of the block | `architecture-control-bytes`, which also asserts that the value occupies exactly one line |
| 21 | 3.2, 3.3 | **Two verification cells did not match their runners.** `denied-path` had no unreadable-path fixture; the runner now copies the positive fixture, `chmod 000`s it, and asserts a nonzero exit, empty stdout, and an untouched destination sentinel, skipping with an explicit note when running as root, where mode bits do not deny access. `stale-fixture` claimed the temp root is absent after a run, which a runner cannot observe about its own `EXIT` trap; the cell now states what is actually proved — one trap owns the root on every exit path and the root is still present at the last assertion — beside the existing repository leak sweep | the runner asserts the root has **not** vanished mid-run | `denied-path`, `run-gguf-smoke` epilogue |
| 22 | 2.8, 5.4 | **Peak rendering memory is recorded.** `render_tensors` builds a second complete copy of the tensor JSON, because `absolute_offset` is knowable only after the walk. It is bounded and small for real models (roughly 60 KB at 339 tensors) but doubles at `MAX_TENSORS`, and closing it needs a rewritable placeholder or the indexable record array Request 22 blocks. Recorded as a deferred item rather than repaired | section 5.4 | none; a deferral with its resume condition |
| 23 | 4.1 | The positive fixture ships **four** tensors, not three: the fourth carries a `0xFF` byte in its name and is the tensor-name half of the `invalid-utf8` cell | `full_tensors()` | `full` |
| 24 | 4.4 | `ALIGN_LLM_GGUF_MODEL` has **no default**. The runner never guessed a path, and a documented default would have been both wrong and a machine-specific path in a specification | `scripts/run-gguf-reference-parity` | the unset-variable skip line |

### 6.1 Measured results

The reference model `qwen2.5-coder-7b-instruct-q4_k_m.gguf` (4,683,073,536 bytes) inspects as:

```text
version 3   alignment 32 (default)   tensor_count 339   metadata_kv_count 29
metadata_end 5,934,224   tensor_table_end 5,953,528   data_offset 5,953,536
architecture qwen2       bytes_read 6,291,456 (0.1343% of the file)
```

Every one of those figures except `bytes_read` matches the independently decoded values recorded in
section 2.4.1. `bytes_read` is six full one-megabyte windows, inside the section 4.3 predicted band
`5,345,312 <= bytes_read < 7,002,112`; the lower bound is not reached because the window is refilled
to capacity rather than to the exact remaining need, which is the honest meaning of "the I/O
actually performed". `scripts/run-gguf-reference-parity` compared the version, alignment, data
offset, KV count, all 29 ordered keys, the tensor count, and all 339 ordered tensor names and
offsets against `llama-gguf`, and confirmed the model's size and mtime unchanged.

### 6.2 Closure cell to shipped case

Section 3 was written before implementation and names cells by contract; the runners name cases by
fixture. This table is the mapping for every cell whose name differs, so a reviewer can move from a
closure cell to the evidence that closes it without searching. Cells whose names already match a
shipped case (`window-growth`, `skip-accounting`, `empty-container`, `repeat-inspect`,
`cli-arity`, `cli-path`, `unknown-selector`, `missing-path`, `denied-path`, `error-precedence` as
`precedence-*`) are omitted.

| Section 3 cell | Shipped evidence |
| --- | --- |
| `open-and-size` | every case: the runner compares `file_size` against the fixture's byte length before any other assertion |
| `bytes-read-exact` | `full` (`bytes_read == file_size`) and `skip-accounting` (the exact predicted count) |
| `error-sentinels` | `error-too-small` and `error-bad-magic-invalid-utf8`, which assert `magic: ""`, three `-1` header fields, `-1` for the three offsets, and `architecture: null` |
| `truncated-every-boundary` | the 13 `truncated-boundary-*` cases plus `error-truncated-after-header`, `error-truncated-mid-header`, and `error-truncated-data-offset` |
| `refill-boundary`, borrow expiry | `straddle-reference` plus the five `refill-boundary-*` variants, compared field by field through the manifest's `straddle_role` |
| `header-fields` | `full`, whose `top` block declares magic, version, and both counts |
| `all-value-types` | `full`, one KV per type with generator-computed golden values |
| `float-bits` | the `kv.float32.*` / `kv.float64.*` rows of `full`, compared through the `$f32`/`$f64` bit markers |
| `array-shapes` | the `kv.array.*` rows of `full`: lengths 0, 1, 8, and 9 for `INT32` and `STRING`, plus `FLOAT32`, `BOOL`, `UINT64`, and an invalid-UTF-8 element |
| `tensor-table` | `full` (1-, 2-, and 4-dimension tensors, a known type, an unknown type, and a non-UTF-8 name) |
| `alignment-default` | `full` and `data-offset-already-aligned` (`alignment_source: "default"`); the override is `alignment-override` |
| `data-offset` | `data-offset-already-aligned` for an already-aligned table end; `full` for one that needs padding |
| `architecture` | `full` (`testarch`), `architecture-present-empty`, `architecture-control-bytes` |
| `architecture-absent` | `empty-container` and `architecture-non-string`, both asserting `architecture: null` and a `-` summary line |
| `error-corpus` | the `error-*` cases, one per reachable section 2.6 row, each with its generator-computed `error_offset` |
| `overflow-corpus` | `error-count-overflow-tensor-count`, `error-array-length-overflow`, `error-string-length-overflow`, `error-value-overflow`, `error-dims-overflow`, `error-tensor-name-length-overflow`, `error-offset-overflow` |
| `invalid-utf8` | the `kv.string.invalid`, `bad\xffkey`, `kv.array.str.invalid`, and `bad\xffname` members of `full` |
| `wire-escapes` | the `kv.string.escapes` member of `full`; every document in the corpus is parsed with Python's `json` |
| `partial-document` | the `metadata_count` / `tensors_count` assertions on `error-unknown-value-type`, `error-unknown-array-element-type`, `error-value-overflow`, `error-offset-overflow`, `error-tensor-misaligned`, and `error-tensor-out-of-range` |
| `document-move` | every case asserts a complete document for both statuses; `full` additionally asserts top-level, header, and tensor field order |
| `stdout-document` | the per-case stdout run, whose bytes are parsed and compared to the written document |
| `file-document` | the per-case two-operand run, which is the primary assertion path |
| `form-parity` | the per-case byte comparison of the stdout form against the written document plus one newline, and of the two exit statuses |
| `env-perturbation` | the perturbed-environment run of `full` (locale, `TZ`, `HOME`, `SOURCE_DATE_EPOCH`, and two invented `GGUF_*` variables) |
| `untouched-destination` | the absent-model and `denied-path` sentinel assertions, plus the structural-failure replacement assertion on `bad-magic.gguf` |
| `stale-fixture` | item 21 above |

### 6.3 Corrections the R1 consumer forced

`docs/specs/r1-qwen-model-ir.md` section 6 records the first six items as owed by that capability and
they are applied here in its implementation commit, so plan, code, and consumer changed together.
Items 25 through 27 correct claims about a consumer contract that was written before any consumer
existed. Item 28 narrows a non-goal that would otherwise be violated by an obviously correct change.
Items 29 and 30 correct the ownership table and the public-API block to match what shipped plus what
R1 adds. Item 31 was found by R1's review rather than by its implementation and corrects a claim
about float rendering that was wrong in both plans. None is a deferral, and none changes
`R0_GGUF_INSPECTION`'s `schema_version`.

| # | Amends | Correction | Evidence | Owner |
| --- | --- | --- | --- | --- |
| 25 | 1.1 | "Both consume the record types defined here" was false: no record type in this document is public. Both consume the `GgufTable` surface R1 adds to this module | `src/gguf.align`: `KvRow` and `TensorRow` have no `pub` | `make check`; `model-ir-smoke` |
| 26 | 5.1 | `GgufKv` and `GgufTensor` were never implemented, and the frontends are flat `src/frontend_*.align` modules rather than `frontends/qwen/` directories, because Align's unit of modularity is one file per module. The table is concatenated text streams plus parallel `array<i64>` columns, which is what Request 22 leaves expressible | Request 22; `docs/specs/r1-qwen-model-ir.md` section 2.3.3 | `src/frontend_qwen.align`; `model-ir-smoke` |
| 27 | 5.1 | R1 does not add `gguf.read_string_array`. Keeping the tokenizer out of R1's scope is precisely what keeps Request 22 non-blocking; the surface is owned by the later tokenizer capability | `docs/specs/r1-qwen-model-ir.md` section 5.2 | none; a deferral with its resume condition |
| 28 | 1.3, 2.5.4 | Block **geometry** — elements and bytes per block — is now exposed as `ggml_block_size` / `ggml_type_size`. Both R1 and R2 need it, and duplicating a GGML table into each frontend would be worse than owning it beside `ggml_type_name`. No block is unpacked and no scale is read | `docs/specs/r1-qwen-model-ir.md` section 2.5.7 | `type-geometry` in `model-ir-smoke` |
| 29 | 2.5.3 | The allocation row named a record that does not exist. Retained text is owned by the private, short-lived `KvRow` / `TensorRow` and reaches a caller only inside `GgufInspection.document` or inside a `GgufTable` stream | `src/gguf.align` | ownership review; `document-move` |
| 30 | 2.5.4 | The public-API block listed only `GgufStatus`, `GgufInspection`, and `inspect`. It now also lists `GgufTable`, `read_table`, the ten accessors, the two geometry functions, and `json_string`, which R1 needs as the one text-to-JSON boundary | `src/gguf.align` | `make check`; `model-ir-smoke` |
| 31 | 2.1 (the `write_float` row) and 2.4.3 | "`write_float` emits Rust's shortest round-trip `Display`, which is exact but **never uses exponent notation**: an `f32` near its maximum renders as a 39-digit decimal" is false. Rust's `f32` `Display` renders `1e-45` and `3.4028235e+38`, and the decoder reproduces that verbatim. Read the sentence as: the rendering is exact and round-trips, but its **spelling** is not stable to compare across tools, which is exactly why `value_bits` is authoritative. Nothing in R0 or R1 depended on the false half — every comparison is on the bits | a FLOAT32 fixture with bit patterns `0x00000001` and `0x7f7fffff` rendered `1e-45` and `3.4028235e+38` through `--inspect-gguf`; `docs/specs/r1-qwen-model-ir.md` section 7 item 20 | `float-bits` in `gguf-smoke`, which compares bit patterns and is unaffected |
