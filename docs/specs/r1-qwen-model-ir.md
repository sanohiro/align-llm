# R1-QWEN-MODEL-IR: Qwen2 model frontend, Model IR, and Block IR

Status: plan of record for the first Track B R1 capability named by `docs/specs/roadmap.md` section
R1. It is authoritative for the R1 public contract: the `main --model-ir` CLI, the
`R1_MODEL_IR` exchanged document (`schema_version: 1`), the new public producer surface
`src/gguf.align` must expose, and the `src/frontend_qwen.align` owner module.
`docs/specs/roadmap.md` remains authoritative for delivery order; `docs/specs/align-llm.md` remains
authoritative for the architecture, including the `BlockKind` enumeration this document maps onto a
real file; `docs/specs/r0-gguf-inspection.md` remains authoritative for the GGUF container contract
this capability consumes.

This document triggers the `CLAUDE.md` proportional design gate on three counts: it adds a public
CLI surface (`main --model-ir`), a new versioned exchanged document (`R1_MODEL_IR`), and a
coordinated invariant across three modules (`src/gguf.align`, `src/frontend_qwen.align`,
`src/main.align`) plus the build and verification graph.

## 1. Purpose, scope, non-goals, and the gate

### 1.1 Goal

Turn one real Qwen2-architecture GGUF file into the two intermediate representations
`docs/specs/align-llm.md` section 5 places between the GGUF reader and the layout planner:

- **Model IR** — the architecture-level hyperparameters a runtime needs to build an execution
  graph: architecture, layer count, embedding width, head counts, head dimension, feed-forward
  width, rope parameters, RMS epsilon, vocabulary size, expert count, trained context length, and a
  quantization summary.
- **Block IR** — the placeable, evictable, prefetchable units of `docs/specs/align-llm.md` section
  5.2, each carrying its `BlockKind`, its layer index, its constituent tensor names, each tensor's
  absolute byte offset, and each tensor's byte size.

R0 answers *what the file declares*. R1 answers *what the model is* and *what the runtime must
move*. The two are deliberately separate modules: architecture-specific knowledge must not leak
into the container reader, exactly as `docs/specs/align-llm.md` section 5.1 requires.

R1 is also the first real consumer of `src/gguf.align`. R0 shipped one public function, `inspect`,
which returns a rendered document and a handful of scalars. That is enough to *describe* a file and
not enough to *compute* over it. Section 2.3 designs the producer surface that closes the gap, and
section 6 records the corrections that surface forces on `docs/specs/r0-gguf-inspection.md`.

### 1.2 In scope

1. A public, non-rendering GGUF table surface on `src/gguf.align` that a frontend can query by key
   and by index without re-parsing the container and without consuming any `PROPOSED` Align
   surface.
2. A `qwen2` frontend that derives the complete Model IR from that table, with every value either
   read from a named metadata key or derived by a stated formula from values that were.
3. Block IR construction for a dense Qwen2 model: one embedding `WeightBlock`, one `AttentionBlock`
   and one `MlpBlock` per layer, and one output `WeightBlock`.
4. Per-tensor byte sizes computed from the GGML block-geometry table — elements per block and bytes
   per block — and the declared dimensions. No byte of the tensor data section is read.
5. A self-verification oracle: `data_offset + Σ tensor_nbytes == file_size`.
6. Distinct, ordered, documented rejection of every input this frontend cannot honestly describe,
   including an unknown GGML type id, which is an error and never a guessed size.
7. One canonical `R1_MODEL_IR` JSON document, emitted through `main --model-ir`.

### 1.3 Non-goals

These are deliberate exclusions, not deferred work items inside this capability.

- **No tokenizer and no vocabulary materialization.** `tokenizer.ggml.tokens` is a 152,064-element
  `STRING` array; `tokenizer.ggml.merges` is a 151,387-element one. Reading either as data requires
  indexing an `array<string>`, which Request 22 records as rejected at the pin. R1 reads the
  *length* of those arrays — which R0's decoder already records without materializing an element —
  and nothing else. Building a usable tokenizer is a later capability with its own contract, and
  making it part of this one would turn Request 22 from non-blocking into blocking. Section 5.2.
- **No MoE and no gpt-oss frontend.** `ExpertBlock` and `RouterBlock` are the reason those kinds
  exist in `docs/specs/align-llm.md` section 5.2, and a dense Qwen2 file produces neither. A model
  declaring a nonzero expert count is rejected rather than half-described. Section 5.1.
- **No tensor payload decode and no dequantization.** R1 computes sizes from the type geometry
  table; it never unpacks a block, never reads a scale, and never touches a payload byte. R0's
  section 1.3 non-goal stands unchanged, with the one clarification of section 6, item 28.
- **No layout plan, no `.alignpack`, no reordering, and no prefetch policy.** Block IR is the
  *input* to that planner. Choosing an order or a placement is R2. Section 5.3.
- **No KV-cache sizing and no runtime state.** `KVBlock` describes memory a running model
  allocates, not bytes a file contains; no tensor backs it. Section 3.2 records it as `N/A` with
  that reason rather than inventing a projected size from an assumed context length.
- **No execution.** R1 links no runtime, invokes no provider, and loads no weights. It must be
  usable and testable before `align-runtime` exists, exactly as R0 is.
- **No writing to the model file.** The capability is strictly read-only on the model path, and
  inherits R0's `fs.open_rw` precondition and its Request 21 consequence unchanged.
- **No architecture other than `qwen2`.** A file whose `general.architecture` is anything else —
  including `qwen3`, which shares much of the key vocabulary — is rejected. Silently accepting a
  near-relative would produce a Model IR that is wrong in exactly the places that matter.

### 1.4 Gate statement

The roadmap gate for R1 is: *Model IR and Block IR can be produced.* This document discharges it in
three parts:

1. `make model-ir-smoke` — the self-contained owner (section 4.2). It produces both IRs from a
   synthetic qwen2-shaped fixture and asserts every field, every block, every byte size, and every
   error code, with no model and no network.
2. The size-sum oracle (section 4.3). A Model IR whose blocks account for every byte between
   `data_offset` and the end of the file is a Block IR that is complete and correctly sized, proved
   from inside the program on any real model.
3. `make model-ir-parity` — the focused, opt-in qualification (section 4.4) that compares the
   derived hyperparameters against `llama-cli -v`'s `print_info` block on a real model, which is
   how "the IR is right" is checked against an existing implementation rather than against itself.

## 2. Public-contract ledger

### 2.1 Verified Align surface at pin `4b515f8d`

Every surface below was checked against the sibling checkout at
`4b515f8d37de2e9a9ba06170c5842fd12dc1cba2` before being written into this plan. R1 consumes only
these. It proposes no new Align surface, builds no compatibility layer, and does not write against
Request 21 or Request 22.

| Surface | Exact form at the pin | Consequence for R1 |
| --- | --- | --- |
| `array<i64>` as a record field | Shipped. `src/c6c2_request10_adoption.align:4` declares `RecursiveRecord { ordinal: i64, inner: Option<RecursiveInner>, values: array<i64>, value_count: i64 }` | The `GgufTable` column representation of section 2.3 is expressible |
| `array<i64>` indexing and `.len()` | Ordinary Copy-element indexing; `src/gguf.align:878-893` indexes a `borrow offsets: array<i64>` parameter | Every parallel column is read by position with no borrow ceremony |
| `array_builder<i64>` | Language intrinsic, not an import; `.push(v)`, `.build() -> array<i64>` (`docs/language-spec.md:982-1001`); `src/gguf.align:1027-1028` uses it | The columns are accumulated during the walk and frozen once |
| `array<string>` indexing | **Rejected** as a general expression (`align_sema` `check_index`, Request 22). Admitted **only** as a direct argument to a shared-`borrow` parameter (`docs/language-spec.md:207-215`), as `src/c6_borrowed_array_adoption.align:24` does with `task.argv[0]` | Section 2.3 rejects the `array<string>` option on this basis |
| `str` range slicing | `s[a..b]` yields a borrowed sub-`str`, no allocation, region-tied to the source; a bound that splits a UTF-8 scalar aborts (`docs/language-spec.md:617-620`, `:648-652`) | Names and text values are sliced out of one owned stream by explicit start/end offsets |
| `str` predicates | `.len()`, `==`, `.contains`, `.starts_with`, `.ends_with`, `.find`/`.rfind -> Option<i64>` (`docs/language-spec.md:636-638`) | Key and tensor-name lookup are plain byte comparisons |
| `.clone()` on an owned `string` leaf reached through a borrow | Admitted (`docs/language-spec.md:191-193`); `src/gguf.align:1055` clones through a `borrow row: KvRow` | The accessors of section 2.3 return owned `string`, which needs no return-region reasoning |
| `Option<T>` over Copy scalars and `string` | Shipped; `src/prompt_score.align:587` returns `Option<i64>`, `src/prompt_experiment.align:221` returns `Option<string>` | The typed KV accessors return `Option`, so "absent" is a value rather than a sentinel |
| `builder`, `b.write/write_int/write_float`, `b.to_string()` | Shipped and used throughout `src/gguf.align` | Document rendering, unchanged from R0 |
| `builder` / `array_builder<T>` as a **parameter** type | **Not** available at the pin (`docs/specs/r0-gguf-inspection.md` section 6, item 3) | A shared walk helper that accumulates both the R0 document and the R1 columns cannot exist; section 2.3.4 states what R1 does instead |
| Integer `as` | Value conversion with defined truncating wrap for `int -> int` | `u64 <-> i64` bit round-trip is exact and is how float bit patterns ride an `array<i64>` |
| `Result<T, Error>`, `Error`, `?` | Unchanged from R0 | R1's public functions return `Result<_, Error>` |

Three surfaces a naive R1 would reach for are **NOT FOUND at this pin** and are named here so no
reviewer rediscovers them: any bit-cast between `f32`/`f64` and an integer, any `MAX`/`MIN` integer
constant, and general indexing of an `array<string>`. Sections 2.3 and 2.6 give R1's substitutes.

One surface is **unverified** and is treated as such. Whether an `array<i64>` reached through a
struct-field path off a `borrow` parameter (`t.tensor_offsets[i]` where `t` is `borrow t:
GgufTable`) is admitted was not provable from the checked-in specification alone: the spec's
indexing paragraph (`docs/language-spec.md:201-204`) states the rule for region-bearing Copy
elements and for Move elements, and plain `array<i64>` off a borrowed struct field is neither.
Section 2.3.5 records the pre-implementation compile probe that must settle it and the exact
fallback if it fails. No line of this plan depends on the answer.

### 2.2 CLI surface

| Command | Exact arguments | Document destination | Stdout | Exit |
| --- | --- | --- | --- | --- |
| `./main --model-ir MODEL_GGUF` | Exactly one operand (`args.len() == 3`) | The document is written to stdout, followed by one newline, and nothing else is printed | The document only | `0` on `status: "ok"`, `Err(Error.Invalid)` on `status: "error"` |
| `./main --model-ir MODEL_GGUF MODEL_IR_JSON` | Exactly two operands (`args.len() == 4`) | The document is written to `MODEL_IR_JSON` via `fs.write_file` | The section 2.4 human summary block | `0` on `status: "ok"`, `Err(Error.Invalid)` on `status: "error"` |

The document bytes are **byte-identical** between the two forms. Only the destination and the
presence of the summary block differ. This is the complete option and detail-level matrix for this
surface: there is no verbosity flag, no field-selection flag, no block-kind filter, and no
alternate encoding. The shape deliberately mirrors `--inspect-gguf` (`docs/specs/r0-gguf-inspection.md`
section 2.2) rather than inventing a second CLI grammar in the same repository.

Dispatch extends the existing `src/main.align` chain by one arm, immediately after `--inspect-gguf`
(`src/main.align:645`). `args[0]` is the executable name and is never interpreted as a mode. A mode
is selected only when `args[1] == "--model-ir"`; arity is then checked before any path or file
work. `args.len() < 3` or `args.len() > 4` returns `Err(Error.Invalid)` with no filesystem access
and no document. An unrecognized `args[1]` continues to reach the existing help path and return
`Ok(())`.

`MODEL_GGUF` must be a nonempty UTF-8 string of at most 4,096 bytes with no embedded NUL — R0's
`MAX_PATH_BYTES` bound, enforced by the same `gguf.valid_path` guard, because the path reaches the
filesystem only through `gguf.read_table`. No environment variable, locale, provider setting,
current time, or random seed changes any byte of the document. The path string appears in the
document verbatim as given, in the `path` field, and is never normalized or absolutized.

### 2.3 The producer boundary: what `src/gguf.align` must expose

This is the first design problem of R1 and it is decided here rather than during implementation.

#### 2.3.1 Why R0's public surface is not enough

R0 exposes exactly `pub fn inspect(path: str) -> Result<GgufInspection, Error>` plus
`pub fn value_type_name(id: i64) -> str` and `pub fn ggml_type_name(id: i64) -> str`
(`src/gguf.align:187`, `:217`, `:997`). `GgufInspection` (`src/gguf.align:52-68`) carries eleven
scalars and one `document: string`. `KvRow` and `TensorRow` are private, and the tensor bodies never
exist as an addressable collection at all: they are accumulated into one NUL-separated `builder`
stream with two parallel `array_builder<i64>` columns (`src/gguf.align:1016-1022`) precisely because
Request 22 rejects indexing an array of Move elements.

A frontend therefore has three ways to get at the tensor table and the metadata, and only one of
them is honest:

- **Re-decode the JSON document with `core.json`.** It would need declared records with
  `array<string>` and `array<Struct>` fields, and reading an element back out is the exact operation
  Request 22 rejects. It also makes the rendered document — a human- and tool-facing wire format —
  load-bearing for an internal computation, so a rendering change would silently become a semantic
  change. Rejected.
- **Re-parse the container inside the frontend.** Two decoders for one format, guaranteed to drift,
  and a direct violation of R0's "sole owner of GGUF container knowledge" claim
  (`src/gguf.align:6-8`). Rejected.
- **Add a public, non-rendering table surface to `src/gguf.align`.** Chosen. The rest of section 2.3
  designs it.

#### 2.3.2 Option A — `GgufTable`: concatenated text streams plus parallel Copy columns

One public record whose every collection field is either an owned `string` holding all text
back-to-back or an `array<i64>` of Copy scalars. Text is addressed by explicit start/end byte
offsets into its stream; every other field is addressed by position.

```text
pub GgufTable {
  // Container-level results, identical in meaning to the same-named `GgufInspection` fields.
  status: GgufStatus,
  error_code: string,
  error_offset: i64,
  file_size: i64,
  bytes_read: i64,
  version: i64,
  alignment: i64,
  metadata_end: i64,
  tensor_table_end: i64,
  data_offset: i64,
  architecture: string,
  architecture_present: bool,

  // Metadata columns. Every column has exactly `kv_count` entries.
  kv_count: i64,
  keys: string,                    // every decoded key, concatenated, no separator
  key_starts: array<i64>,
  key_ends: array<i64>,
  key_valid: array<i64>,           // 1 when the key decoded as UTF-8, else 0
  kv_types: array<i64>,            // the GGUF value type id
  kv_ints: array<i64>,             // UINT8..INT64 and BOOL; 0 when `kv_has_int` is 0
  kv_has_int: array<i64>,
  kv_float_bits: array<i64>,       // the raw IEEE-754 pattern, `as i64`; see below
  kv_has_float: array<i64>,
  texts: string,                   // STRING values and rendered float decimals, concatenated
  kv_text_starts: array<i64>,
  kv_text_ends: array<i64>,
  kv_has_text: array<i64>,
  kv_array_elem_types: array<i64>, // -1 when the value is not an ARRAY
  kv_array_lengths: array<i64>,    // -1 when the value is not an ARRAY

  // Tensor columns. Every column has exactly `tensor_count` entries.
  tensor_count: i64,
  names: string,                   // every decoded tensor name, concatenated, no separator
  name_starts: array<i64>,
  name_ends: array<i64>,
  name_valid: array<i64>,
  tensor_n_dims: array<i64>,
  tensor_dim0: array<i64>,         // 1 for an axis the tensor does not declare
  tensor_dim1: array<i64>,
  tensor_dim2: array<i64>,
  tensor_dim3: array<i64>,
  tensor_types: array<i64>,        // the raw `ggml_type` id
  tensor_offsets: array<i64>,      // tensor-relative, exactly as stored
  tensor_absolute_offsets: array<i64>,  // `data_offset + offset`, or -1 when unrepresentable
}
```

Four properties make this work at the pin.

**No separator, therefore no separator hazard.** R0's private tensor stream splits on a raw NUL and
justifies it by the fact that a *rendered JSON* body cannot contain one (`src/gguf.align:896-898`).
That reasoning does not transfer: a raw GGUF key, string value, or tensor name may legitimately
contain `U+0000` — R0's own positive fixture ships one (`docs/specs/r0-gguf-inspection.md` section
4.1). `GgufTable` therefore stores no separator at all and addresses every element by an explicit
`[start, end)` pair, which is also O(1) per access instead of a scan.

**The streams are always valid UTF-8, so slicing can never abort.** `decode_text`
(`src/gguf.align:481-500`) already yields `TextValue { text: "", valid: false }` for a region that
fails `as_str()`. Only decoded, valid text is appended, so every recorded boundary is a scalar
boundary and `s[a..b]` cannot hit the split-scalar abort of `docs/language-spec.md:648`. A non-UTF-8
key or name is a zero-length span with its `*_valid` column set to `0`.

**Four fixed dimension columns, not a jagged array.** `GGML_MAX_DIMS` is 4 and R0 already rejects
`n_dims` outside `[1, 4]` with `GGUF_BAD_DIMS` (`src/gguf.align:760-762`), so the dimension list is
a format constant rather than a heuristic. Four `array<i64>` columns are exact, indexable, and need
no nested-array type — which `docs/language-spec.md:987` records as outside the array-builder type
representation anyway. An axis the tensor does not declare holds `1`, the multiplicative identity,
so an element-count product is a fixed four-term multiplication with no branch.

**Floats ride as bits and as pre-rendered text.** There is no bit-cast at the pin. R0 already reads
each float twice at the same offset — once as `f32`/`f64` for `write_float`, once as `u32`/`u64` for
the exact pattern (`src/gguf.align:431-477`) — so `GgufTable` carries the *pattern* in
`kv_float_bits` (via `raw as i64`, whose `int -> int` wrap is defined and therefore exactly
reversible with `as u64`) and the *rendering* in the `texts` stream. A KV is never simultaneously a
`STRING` and a float, so one text stream serves both without ambiguity: `kv_types[i]` says which it
is. A non-finite float has `kv_has_text == 0`, matching R0's `null` rendering.

Public functions over the record, all of which return owned or Copy values and therefore raise no
return-region question:

```text
pub fn read_table(path: str) -> Result<GgufTable, Error>

pub fn find_key(borrow t: GgufTable, key: str) -> i64        // index, or -1
pub fn find_tensor(borrow t: GgufTable, name: str) -> i64    // index, or -1

pub fn kv_type(borrow t: GgufTable, key: str) -> i64         // GGUF type id, or -1 when absent
pub fn kv_int(borrow t: GgufTable, key: str) -> Option<i64>
pub fn kv_float_bits(borrow t: GgufTable, key: str) -> Option<i64>
pub fn kv_string(borrow t: GgufTable, key: str) -> Option<string>
pub fn kv_float_text(borrow t: GgufTable, key: str) -> Option<string>
pub fn kv_array_length(borrow t: GgufTable, key: str) -> Option<i64>

pub fn tensor_name(borrow t: GgufTable, index: i64) -> string
pub fn tensor_dim(borrow t: GgufTable, index: i64, axis: i64) -> i64

pub fn ggml_block_size(id: i64) -> i64   // elements per block; 0 when the id has no verified entry
pub fn ggml_type_size(id: i64) -> i64    // bytes per block;    0 when the id has no verified entry
```

An accessor returns `None` when the key is absent, when its key bytes were not valid UTF-8, or when
the stored value is not of the requested class. That is deliberately not the same as "absent": the
frontend distinguishes the two with `kv_type`, which is why both accessors exist. `tensor_name`
returns `""` for an index outside `[0, tensor_count)` and for a name that failed UTF-8; the
`name_valid` column is the discriminator, exposed through `find_tensor` never matching an invalid
name.

#### 2.3.3 Option B — `array<string>` columns with borrow-parameter accessors

`docs/language-spec.md:207-215` admits one narrow use of a Move-element index: it may be passed as a
direct argument to an explicit shared-`borrow` parameter.
`src/c6_borrowed_array_adoption.align:24` proves it compiles at the pin
(`inspect_owned_text(task.argv[0])` where `argv: array<string>`). So `GgufTable` could hold
`names: array<string>` and `keys: array<string>`, with every read routed through a helper such as
`fn name_eq(borrow name: string, want: str) -> bool`.

Rejected, for four reasons in increasing order of weight:

1. **It is not an expression.** The indexed element may not be bound to a local, matched, returned,
   compared inline, or read back out of a call result. Every use becomes a bespoke helper, and the
   frontend's shape is dictated by a compiler restriction rather than by the problem.
2. **It spreads the restriction across a module boundary.** `GgufTable` would be a public type whose
   safe use requires knowing an unwritten rule. Section 2.3.2's columns are ordinary data that any
   consumer can read without knowing why they look that way.
3. **N allocations instead of one.** 339 tensor names and 29 keys become 368 separate heap
   `string`s; the concatenated form is two.
4. **The migration is worse, not better.** When Request 22 ships, option A's *internals* can become
   an indexed `array<TensorEntry>` with **no change to any public signature**, because every
   accessor is already index-in / owned-value-out. Option B's public field types would themselves
   have to change, invalidating every consumer. Section 5.4.

#### 2.3.4 Option C — a visitor or callback surface

`gguf.walk(path, sink)`, where the frontend supplies per-KV and per-tensor callbacks. Rejected on
three independent grounds, any one of which is sufficient:

- **Dependency inversion.** The sink type is architecture-specific. Either `src/gguf.align` imports
  the frontend — destroying the "imports `core.json`, `std.fs`, and nothing else" property that
  makes R0 testable before any runtime exists (`src/gguf.align:6-8`) — or the sink is a generic
  parameter, and R1 would be proposing a generic public API as its first act.
- **It cannot accumulate.** `builder` and `array_builder<T>` are not parameter types at the pin
  (`docs/specs/r0-gguf-inspection.md` section 6, item 3), which is the same constraint that already
  forced R0's walk to live inline in `inspect`. A callback that must build up a frontend-side
  structure has nowhere to put it.
- **Two passes are needed anyway.** `absolute_offset` is knowable only after the whole tensor table
  has been walked, and Block IR assembly is name-directed rather than file-ordered. A streaming
  visitor would have to be run twice, or buffer — at which point it is option A with extra steps.

`fn(str, str, i64) -> bool` function values do exist at the pin (`src/main.align:665` passes
`decline_repair` into the verification loop), so option C is not rejected for lack of function
values. It is rejected because the *data* it would carry cannot be typed or accumulated here.

#### 2.3.5 Decision, and the one probe it owes

**Option A is chosen.** It is the only one of the three that is expressible entirely in surfaces
verified at the pin, keeps GGUF knowledge in one module, keeps the public signatures stable across
the Request 22 migration, and allocates two strings rather than 368.

The single unverified surface is section 2.1's last row: reading `t.tensor_offsets[i]` where `t` is
a `borrow t: GgufTable` parameter. Before any R1 implementation commit, a throwaway Align program —
following the out-of-tree probe precedent of `docs/specs/r0-gguf-inspection.md` section 6, item 16 —
must declare a record with an `array<i64>` field, pass it as `borrow`, index it through the field
path, and compile under the pinned `alignc`. The probe is recorded in the pull request as evidence,
not committed.

If the probe fails, the fallback is mechanical and changes no public field and no error code: each
accessor takes the columns it needs as explicit `borrow` parameters, exactly as R0's shipped
`check_tensor_ranges(borrow offsets: array<i64>, borrow offset_fields: array<i64>, ...)`
(`src/gguf.align:878-883`) and `render_tensors(prefixes: str, borrow offsets: array<i64>, ...)`
(`src/gguf.align:899`) already do. The frontend then destructures `GgufTable` once into locals at
the top of `build_model_ir` and passes columns down. It is more verbose; it is not a redesign.

#### 2.3.6 One decoder, two walks

`read_table` and `inspect` are two `pub` functions in `src/gguf.align` that call the same private
`decode_header`, `decode_kv`, `decode_tensor`, `resolve_data_offset`, and `check_tensor_ranges`
helpers over the same `Cursor`. They cannot share a single walk function, because `builder` and
`array_builder<T>` are not parameter types at the pin, so each accumulates its own bodies inline —
the same constraint R0 already recorded and lives with.

`read_table` calls `decode_kv` / `decode_tensor` unchanged and discards their `json` field. That
wastes the rendering work for 29 keys and 339 tensors on the reference model — microseconds against
a 4.68 GB file — and buys the property that matters: **there is exactly one implementation of GGUF
container interpretation in the repository**, so `--inspect-gguf` and `--model-ir` cannot disagree
about what a file says. Optimizing the discard away would mean a second decode path, and section
4.5 makes no performance claim that would justify it.

The residual risk is that the two *walks* drift — a guard added to one and not the other. Section
3.1 closes it with a named regression, `table-inspect-parity`, which runs both CLI arms over every
positive and negative fixture in the combined corpus and asserts agreement on version, alignment,
`data_offset`, both counts, every tensor name, offset, and type id, and the container error code.

### 2.4 Stable CLI summary

For the two-operand form only, and after the document has been written, the CLI prints exactly these
logical lines through the existing `print` primitive, one newline per line:

```text
qwen model ir:
status:
OK | ERROR
arch:
<general.architecture, control-byte escaped; "-" when absent, non-STRING, or non-UTF-8>
layers:
<decimal i64>
embd:
<decimal i64>
heads:
<decimal i64>
heads kv:
<decimal i64>
head dim:
<decimal i64>
ff:
<decimal i64>
vocab:
<decimal i64>
experts:
<decimal i64>
context:
<decimal i64>
blocks:
<decimal i64>
tensor bytes:
<decimal i64>
size sum:
OK | MISMATCH
```

On `status: "error"` every field that was not derived prints `-1`, `size sum` prints `MISMATCH`
whenever the oracle did not run or did not hold, and two further pairs are appended:

```text
error:
<error code>
detail:
<error detail, control-byte escaped>
```

The `arch` and `detail` lines carry container-controlled text into a block a consumer reads
positionally, so both are escaped by the existing private `sanitize_summary_line`
(`src/main.align:425`): every byte below `0x20`, and `0x7f`, is replaced by `\xNN` in lowercase
hexadecimal. `-` on the `arch` line is reserved for an architecture the container does not supply —
absent, non-STRING, or non-UTF-8 — so a key that is present and empty prints an **empty line**,
distinguished through `GgufTable.architecture_present`. This is the R0 contract
(`docs/specs/r0-gguf-inspection.md` section 2.3 and section 6, items 18 and 20) reused verbatim, not
a second escaping grammar.

This block is a human convenience. The JSON document is the authoritative result, and normal Align
error reporting remains the source of truth for a returned `Err`.

### 2.5 Exchanged document — `R1_MODEL_IR`, `schema_version: 1`

Canonical UTF-8 JSON in declaration order, produced by the same `builder` splicing and the same
`json_string` escaping boundary R0 uses (`src/gguf.align:147-151`), so a container-supplied
architecture or tensor name carrying a quote, a backslash, a control byte, an embedded NUL, or a
4-byte scalar survives into valid, parseable JSON. Field order is the order below and is normative.
Any field addition, removal, reordering, or type change requires `schema_version: 2`.

#### 2.5.1 Top level

```json
{
  "schema_version": 1,
  "kind": "R1_MODEL_IR",
  "path": "MODELS_DIR/qwen2.5-coder-7b-instruct-q4_k_m.gguf",
  "status": "ok",
  "error_code": "",
  "error_detail": "",
  "source": {},
  "model": {},
  "quant": {},
  "coverage": {},
  "blocks": []
}
```

| Field | Type | Contract |
| --- | --- | --- |
| `schema_version` | integer | Always `1` for this document version |
| `kind` | string | Always `"R1_MODEL_IR"` |
| `path` | string | The `MODEL_GGUF` operand verbatim, JSON-escaped. Never normalized or absolutized |
| `status` | string | `"ok"` or `"error"`. No third value |
| `error_code` | string | `""` when `status` is `"ok"`; otherwise exactly one code from section 2.6 |
| `error_detail` | string | `""` when `status` is `"ok"`; otherwise a bounded, JSON-escaped identifier naming the offending key, tensor name, or container code. Never free prose and never a file path |
| `source` | object | Section 2.5.2. Always present |
| `model` | object | Section 2.5.3. Present with `-1` / `null` sentinels for anything not derived |
| `quant` | object | Section 2.5.4 |
| `coverage` | object | Section 2.5.5 |
| `blocks` | array | Section 2.5.6, in emission order. `[]` when block assembly was not reached |

On `status: "error"` the document is still written and every value derived before the failure is
present and truthful. This mirrors R0's failure-persistence behavior
(`docs/specs/r0-gguf-inspection.md` section 2.4.1) and the existing `--index` behavior, and it is
what makes a partially-describable model diagnosable rather than opaque.

`error_detail` is bounded at 256 bytes; a longer identifier is truncated at a UTF-8 scalar boundary
and the truncation is not marked, because the field is a diagnostic and not a contract on the
identifier's completeness.

#### 2.5.2 `source`

```json
"source": {
  "gguf_version": 3,
  "alignment": 32,
  "file_size": 4683073536,
  "data_offset": 5953536,
  "tensor_count": 339,
  "metadata_kv_count": 29,
  "bytes_read": 6291456
}
```

Every value is copied from `GgufTable` without reinterpretation. `bytes_read` retains its R0
definition — the exact sum of the counts returned by every `pread` — and is the evidence that R1,
like R0, reads header and metadata only. Section 4.5.

#### 2.5.3 `model`

```json
"model": {
  "arch": "qwen2",
  "n_layer": 28,
  "n_embd": 3584,
  "n_head": 28,
  "n_head_kv": 4,
  "head_dim": 128,
  "n_ff": 18944,
  "n_vocab": 152064,
  "n_expert": 0,
  "context_length": 131072,
  "rms_eps": 1e-06,
  "rms_eps_bits": "358637bd",
  "rope": {
    "type": 2,
    "type_name": "neox",
    "type_source": "architecture",
    "freq_base": 1000000.0,
    "freq_base_bits": "49742400",
    "dim_count": 128,
    "dim_count_source": "derived",
    "scaling_type": null
  }
}
```

Every value in the example is the real reference model, cross-checked in section 4.4.
`MODELS_DIR` is a placeholder for whatever directory holds it on the running host.

| Field | Source | Rule |
| --- | --- | --- |
| `arch` | `general.architecture` | Must be exactly `"qwen2"`; anything else is `R1_UNSUPPORTED_ARCH` |
| `n_layer` | `qwen2.block_count` | Required, `UINT32`, in `[1, 512]` |
| `n_embd` | `qwen2.embedding_length` | Required, `UINT32`, in `[1, 1048576]` |
| `n_head` | `qwen2.attention.head_count` | Required, `UINT32`, in `[1, 4096]` |
| `n_head_kv` | `qwen2.attention.head_count_kv` | Required, `UINT32`, in `[1, n_head]`, and `n_head % n_head_kv == 0` |
| `head_dim` | derived | `n_embd / n_head`, requiring `n_embd % n_head == 0` |
| `n_ff` | `qwen2.feed_forward_length` | Required, `UINT32`, in `[1, 16777216]` |
| `n_vocab` | derived | `dims[1]` of `token_embd.weight`; see section 2.5.7 |
| `n_expert` | `qwen2.expert_count` | Optional `UINT32`; absent means `0`. A present non-`UINT32` value is `R1_KEY_TYPE_MISMATCH`; any nonzero value is `R1_UNSUPPORTED_MOE` |
| `context_length` | `qwen2.context_length` | Required, `UINT32`, in `[1, 134217728]` |
| `rms_eps` | `qwen2.attention.layer_norm_rms_epsilon` | Required, `FLOAT32`. The JSON number is the `write_float` rendering; `null` if non-finite |
| `rms_eps_bits` | same key | Lowercase hexadecimal of the raw IEEE-754 pattern, 8 characters. Authoritative |
| `rope.freq_base` | `qwen2.rope.freq_base` | Required, `FLOAT32`, same rendering rule |
| `rope.freq_base_bits` | same key | 8 hexadecimal characters. Authoritative |
| `rope.type` / `type_name` | architecture | Fixed at `2` / `"neox"` for `qwen2`; `type_source` is always `"architecture"`. See below |
| `rope.dim_count` | `qwen2.rope.dimension_count` when present, else `head_dim` | Optional `UINT32`, in `[1, head_dim]`; `dim_count_source` is `"metadata"` or `"derived"` accordingly |
| `rope.scaling_type` | `qwen2.rope.scaling.type` | Optional `STRING`; `null` when absent. Reported, never interpreted |

**`rope.type` is architecture-owned and is not read from the file, and that is stated rather than
hidden.** The reference model declares no rope-type key; llama.cpp assigns `qwen2` the NEOX rope
layout, and `llama-cli -v` prints `rope type = 2` for exactly this file. A frontend that guessed
"the file did not say, so use the default" would be wrong in a way no fixture could catch, so R1
records the value, its source, and — in section 4.4 — the parity row that is its evidence.
`type_source` exists so a consumer can tell a derived constant from a declared one; it is the only
field in `model` whose value comes from architecture knowledge rather than from the container.

`rms_eps` and `rope.freq_base` carry both a rendering and a bit pattern for the reason R0 gives in
its section 2.4.3: `write_float` is exact and round-trips, but never uses exponent notation, so it
is not a stable string to compare across tools. Every comparison in section 4 is on the bits or on
the other tool's own formatting of our bits; the decimal is for humans.

#### 2.5.4 `quant`

```json
"quant": {
  "file_type": 15,
  "file_type_present": true,
  "type_counts": [
    { "type": 0,  "type_name": "F32",  "tensor_count": 141, "bytes": 1333248 },
    { "type": 12, "type_name": "Q4_K", "tensor_count": 169, "bytes": 3427909632 },
    { "type": 14, "type_name": "Q6_K", "tensor_count": 29,  "bytes": 1247877120 }
  ],
  "total_tensor_bytes": 4677120000
}
```

`file_type` is `general.file_type` as a raw integer, with `file_type_present` false and `file_type`
`-1` when the key is absent or is not `UINT32`. **It is deliberately not given a name.** The
`LLAMA_FTYPE_*` enumeration is a llama.cpp concept, not a GGUF-normative one; mapping `15` to
`"Q4_K - Medium"` would be R1 asserting knowledge of another project's private numbering. The
authoritative quantization summary is `type_counts`, which is decoded from the file.

`type_counts` holds one row per distinct `ggml_type` id present in the tensor table, ordered by
ascending id, so the array is deterministic. `bytes` is the summed byte size of that type's tensors
and the rows' `bytes` sum to `total_tensor_bytes`. The three example rows are the real reference
model; `141 + 169 + 29 = 339` and the byte total satisfies the section 4.3 oracle exactly.

#### 2.5.5 `coverage`

```json
"coverage": {
  "tensor_count": 339,
  "assigned_tensor_count": 339,
  "unassigned_tensors": [],
  "block_count": 58,
  "data_offset": 5953536,
  "total_tensor_bytes": 4677120000,
  "computed_end": 4683073536,
  "file_size": 4683073536,
  "size_sum_ok": true
}
```

This object is the self-verification oracle made visible. `computed_end` is
`data_offset + total_tensor_bytes`; `size_sum_ok` is `computed_end == file_size`. On the reference
model both are 4,683,073,536. `unassigned_tensors` lists the names of tensors the Block IR did not
claim, bounded to the first 16 entries, and is empty on a well-formed model; a nonempty list is
always accompanied by `error_code: "R1_UNASSIGNED_TENSOR"`, because a partial Block IR is not a
Block IR.

#### 2.5.6 Block record

```json
{
  "index": 1,
  "kind": "AttentionBlock",
  "layer": 0,
  "expert": -1,
  "tensor_count": 8,
  "byte_size": 17020928,
  "first_absolute_offset": 312514560,
  "end_absolute_offset": 461627392,
  "contiguous": false,
  "tensors": [
    {
      "name": "blk.0.attn_norm.weight",
      "role": "attn_norm",
      "type": 0,
      "type_name": "F32",
      "n_dims": 1,
      "dims": [3584],
      "n_elements": 3584,
      "block_size": 1,
      "type_bytes": 4,
      "nbytes": 14336,
      "offset": 306561024,
      "absolute_offset": 312514560
    }
  ]
}
```

The example is the real reference model's layer-0 attention block, and it is
**`contiguous: false`** — which is a measured fact about that file, not a defect. Its writer grouped
tensors by *role* across all layers, so `blk.0.attn_norm.weight` sits at absolute offset
312,514,560 while `blk.0.attn_v.weight` sits at 460,122,112, and the block's eight tensors span
149,112,832 bytes to carry 17,020,928 bytes of weights. Essentially every `AttentionBlock` and
`MlpBlock` in the reference model is non-contiguous by that measure; the embedding `WeightBlock`,
being one tensor, is trivially contiguous.

That is exactly the observation `docs/specs/align-llm.md` sections 6 and 7 build on — reading one
layer from NVMe today means eight scattered reads spanning 142 MiB — and exactly the thing R2's
layout planner exists to change. R1 reports it and takes no action on it.

`index` is the zero-based position of the block in `blocks` and is the emission order of section
2.5.8, not file order. `layer` is the zero-based layer index, or `-1` for a block that is not
per-layer. `expert` is always `-1` in R1 and exists so that an `ExpertBlock` from a later frontend
does not force `schema_version: 2`; section 5.1.

`byte_size` is the sum of the block's `nbytes`. `first_absolute_offset` is the minimum
`absolute_offset` over the block's tensors and `end_absolute_offset` the maximum
`absolute_offset + nbytes`; `contiguous` is `end_absolute_offset - first_absolute_offset ==
byte_size`, which is `true` when the block's tensors occupy one unbroken byte range. It is computed
here because a layout planner needs it and recomputing it per consumer invites an off-by-one.

`role` is R1's stable, architecture-independent name for the tensor's function within its block
(`attn_norm`, `attn_q`, `attn_q_bias`, `attn_k`, `attn_k_bias`, `attn_v`, `attn_v_bias`,
`attn_output`, `ffn_norm`, `ffn_gate`, `ffn_up`, `ffn_down`, `token_embd`, `output_norm`, `output`).
It exists so a consumer does not have to string-match GGUF naming conventions, and it is the seam a
second frontend maps its own names onto.

`dims` has exactly `n_dims` entries in on-disk order, fastest-varying first — the same convention
R0 reports (`docs/specs/r0-gguf-inspection.md` section 2.4.5). `n_elements` is their product.
`block_size` and `type_bytes` are the section 2.5.7 geometry for `type`, reported so that `nbytes`
is auditable from the document alone without a copy of the table.

#### 2.5.7 GGML block geometry, and why an unknown id is an error

`nbytes = (n_elements / block_size) * type_bytes`, requiring `n_elements % block_size == 0`. The
table below is data in `src/gguf.align`, not control flow, and every row is the shipped GGML
block layout for that type:

```text
id  name    block_size  type_bytes        id  name    block_size  type_bytes
0   F32     1           4                 10  Q2_K    256         84
1   F16     1           2                 11  Q3_K    256         110
2   Q4_0    32          18                12  Q4_K    256         144
3   Q4_1    32          20                13  Q5_K    256         176
6   Q5_0    32          22                14  Q6_K    256         210
7   Q5_1    32          24                15  Q8_K    256         292
8   Q8_0    32          34                24  I8      1           1
9   Q8_1    32          40                25  I16     1           2
28  F64     1           8                 26  I32     1           4
30  BF16    1           2                 27  I64     1           8
```

**Every other id — including all `IQ*` and `TQ*` types, and every id GGML adds after the pin — has
no entry and produces `R1_UNKNOWN_TENSOR_TYPE`.** This is the deliberate asymmetry with R0. R0
reports an unknown type id with `type_known: false` and keeps going, because R0 only *describes*
and a wrong label is a small harm. R1 *computes a byte size*, and a guessed size silently corrupts
every downstream offset, the coverage sum, and any layout plan built on it. A frontend that cannot
size a tensor must say so.

The set above is exactly the set whose geometry was transcribed and cross-checked before this plan
was written. The `IQ*` and `TQ*` rows are deliberately omitted rather than transcribed from memory;
adding one is a two-column data change plus a fixture, gated on a named GGML revision as its source
and on the section 4.3 oracle passing against a real model that uses it. Section 5.5.

`ggml_type_name` (`src/gguf.align:217`) keeps its full R0 table and is unchanged: naming a type and
sizing it are different claims, and R1 narrows only the second.

#### 2.5.8 Block IR for a dense Qwen2 model

Emission order is fixed and is not file order:

```text
index 0                          WeightBlock       layer -1   token_embd.weight
index 1 + 2*L      (L = 0..n_layer-1)   AttentionBlock  layer L
index 2 + 2*L                            MlpBlock        layer L
index 1 + 2*n_layer              WeightBlock       layer -1   output_norm.weight, output.weight
```

giving `2 * n_layer + 2` blocks: 58 for the reference model.

| Block | Roles and GGUF names |
| --- | --- |
| embedding `WeightBlock` | `token_embd` = `token_embd.weight` |
| `AttentionBlock` (layer L) | `attn_norm` = `blk.L.attn_norm.weight`; `attn_q` = `blk.L.attn_q.weight`; `attn_q_bias` = `blk.L.attn_q.bias`; `attn_k` = `blk.L.attn_k.weight`; `attn_k_bias` = `blk.L.attn_k.bias`; `attn_v` = `blk.L.attn_v.weight`; `attn_v_bias` = `blk.L.attn_v.bias`; `attn_output` = `blk.L.attn_output.weight` |
| `MlpBlock` (layer L) | `ffn_norm` = `blk.L.ffn_norm.weight`; `ffn_gate` = `blk.L.ffn_gate.weight`; `ffn_up` = `blk.L.ffn_up.weight`; `ffn_down` = `blk.L.ffn_down.weight` |
| output `WeightBlock` | `output_norm` = `output_norm.weight`; `output` = `output.weight`, or `token_embd.weight` when `output.weight` is absent |

Every name above was read out of the reference model, not assumed: it declares exactly
`3 + 28 * 12 = 339` tensors with these names. Qwen2 attention carries QKV **biases**, which many
architectures do not; omitting them would leave 84 tensors unassigned and fail the coverage check,
which is precisely what that check is for.

Expected shapes, asserted per tensor and yielding `R1_TENSOR_SHAPE_UNEXPECTED` on a mismatch:

```text
token_embd.weight    [n_embd, n_vocab]              output.weight     [n_embd, n_vocab]
output_norm.weight   [n_embd]                       attn_norm.weight  [n_embd]
attn_q.weight        [n_embd, n_head * head_dim]    attn_q.bias       [n_head * head_dim]
attn_k.weight        [n_embd, n_head_kv * head_dim] attn_k.bias       [n_head_kv * head_dim]
attn_v.weight        [n_embd, n_head_kv * head_dim] attn_v.bias       [n_head_kv * head_dim]
attn_output.weight   [n_head * head_dim, n_embd]    ffn_norm.weight   [n_embd]
ffn_gate.weight      [n_embd, n_ff]                 ffn_up.weight     [n_embd, n_ff]
ffn_down.weight      [n_ff, n_embd]
```

**Tied embeddings.** When `output.weight` is absent, the output `WeightBlock` references
`token_embd.weight` under role `output`, the tensor appears in two blocks, and the coverage
accounting counts its bytes **once**. `model` gains no field for this: the condition is visible in
the document as two blocks naming the same tensor, and inventing a `tied_embedding` boolean would
duplicate a fact the document already states. The reference model is *not* tied — it declares a
distinct `output.weight` — so this path is owned by a fixture rather than by the parity run.

**The four `BlockKind` values R1 emits nothing for**, each with its reason, because
`docs/specs/align-llm.md` section 5.2 lists seven and silence about four would be a gap:

| Kind | Why no block | Owner |
| --- | --- | --- |
| `ExpertBlock` | A dense Qwen2 file declares no expert tensors; `n_expert != 0` is rejected outright | Section 5.1, gpt-oss frontend |
| `RouterBlock` | Same: no router tensor exists in the file | Section 5.1 |
| `KVBlock` | Runtime state, not file content. No tensor backs it, and its size depends on a chosen context length and cache policy that R1 does not own | Runtime / R2 |
| `DequantBlock` | Produced at execution time from a quantized `WeightBlock`. R1 explicitly does not dequantize | Runtime / R2 |

`blocks` therefore contains only `WeightBlock`, `AttentionBlock`, and `MlpBlock` for a dense Qwen2
model. The `kind` field is a string rather than an integer so that a later frontend adding
`ExpertBlock` and `RouterBlock` needs no schema change.

### 2.6 Validation order and error codes

Validation is strictly ordered and the **first** applicable row wins. Within a step, tensors are
examined in file order and metadata keys in the fixed order of the section 2.5.3 table, so a file
with several defects always reports the same one. No document is written and no stdout is produced
before the whole derivation completes, so no partial output can be observed for any failure.

1. CLI selector and exact arity.
2. Path lexical validation: nonempty, at most 4,096 bytes, no embedded NUL.
3. `gguf.read_table`. An `Err` — invalid path or an OS failure on open, `len`, or `pread` —
   propagates unchanged, with no document. A `status: Error` table becomes `R1_GGUF_ERROR`.
4. Architecture: present, UTF-8, exactly `"qwen2"`.
5. Required metadata presence, then type, key by key in section 2.5.3 order.
6. Hyperparameter plausibility and derivation, including every divisibility requirement.
7. Expert count.
8. Tensor geometry pass, in file order: duplicate name, then type geometry, then element product,
   then block alignment, then the running byte total.
9. `n_vocab` derivation and its cross-check.
10. Block assembly in the section 2.5.8 emission order: required tensor present, then shape.
11. Coverage: every tensor assigned to at least one block.
12. The size-sum oracle.

| Code | Condition | Detected in | `error_detail` |
| --- | --- | --- | --- |
| `R1_GGUF_ERROR` | `gguf.read_table` returned `status: Error` | step 3 | the container `error_code` |
| `R1_UNSUPPORTED_ARCH` | `general.architecture` is absent, non-STRING, non-UTF-8, or not `"qwen2"` | step 4 | the architecture, or `""` |
| `R1_MISSING_KEY` | a required key of section 2.5.3 is absent | step 5 | the key |
| `R1_KEY_TYPE_MISMATCH` | a required key is present with a value type other than the one section 2.5.3 names | step 5 | the key |
| `R1_KEY_VALUE_IMPLAUSIBLE` | a value is outside its section 2.5.3 bound, or a divisibility requirement fails | step 6 | the key |
| `R1_UNSUPPORTED_MOE` | `qwen2.expert_count` is present and nonzero | step 7 | the decimal count |
| `R1_DUPLICATE_TENSOR` | two tensor-table entries declare the same name | step 8 | the name |
| `R1_UNKNOWN_TENSOR_TYPE` | a tensor's `ggml_type` id has no section 2.5.7 entry | step 8 | the decimal id |
| `R1_TENSOR_SHAPE_UNALIGNED` | `n_elements % block_size != 0` | step 8 | the name |
| `R1_SIZE_OVERFLOW` | the dimension product, a tensor's `nbytes`, or the running total is not representable as `i64` | step 8 | the name |
| `R1_MISSING_TENSOR` | a tensor a block requires is absent | steps 9, 10 | the name |
| `R1_TENSOR_SHAPE_UNEXPECTED` | a tensor's `dims` disagree with the section 2.5.8 expectation | step 10 | the name |
| `R1_VOCAB_MISMATCH` | `tokenizer.ggml.tokens` is present as an ARRAY and its length differs from `token_embd.weight` `dims[1]` | step 9 | the two decimal lengths, separated by `!=` |
| `R1_UNASSIGNED_TENSOR` | a tensor in the table was claimed by no block | step 11 | the first unassigned name |
| `R1_SIZE_SUM_MISMATCH` | `data_offset + total_tensor_bytes != file_size` | step 12 | the two decimal values, separated by `!=` |

Thresholds, all recorded as named constants in `src/frontend_qwen.align`:

| Constant | Value | Observed reality | Rationale |
| --- | --- | --- | --- |
| `MAX_LAYERS` | 512 | 28 | An order of magnitude above the deepest shipping dense model |
| `MAX_EMBD` | 1,048,576 | 3,584 | Far above any embedding width; a value above it is corruption |
| `MAX_HEADS` | 4,096 | 28 | Same |
| `MAX_FF` | 16,777,216 | 18,944 | Same |
| `MAX_CONTEXT` | 134,217,728 | 131,072 | Three orders of magnitude of headroom |
| `MAX_UNASSIGNED_REPORTED` | 16 | 0 | The `coverage.unassigned_tensors` bound; a document must not grow with the size of the defect |
| `MAX_DETAIL_BYTES` | 256 | — | The `error_detail` bound |

**Every arithmetic guard is written in non-wrapping form**, following the class audit
`docs/specs/r0-gguf-inspection.md` section 6, item 15 forced on R0. Align integer overflow is
two's-complement wrap with no trap, and there is no `i64` `MAX` constant at the pin, so
`src/frontend_qwen.align` declares the same `I64_MAX` literal R0 does (`src/gguf.align:45`) and:

- the element product accumulates one axis at a time, testing `product > I64_MAX / extent` **before**
  each multiplication, with `extent == 0` short-circuiting to a zero product;
- `nbytes` is `(n_elements / block_size) * type_bytes` — the division first, so the intermediate is
  never larger than `n_elements` — guarded by `blocks > I64_MAX / type_bytes`;
- the running byte total is guarded by `total > I64_MAX - nbytes` before each addition;
- the oracle sum `data_offset + total_tensor_bytes` is formed only after
  `total_tensor_bytes <= I64_MAX - data_offset`, and reports `R1_SIZE_OVERFLOW` otherwise rather
  than a mismatch, because an unrepresentable total is a different fact from a wrong one.

### 2.7 Ownership, allocation, and owner modules

`src/frontend_qwen.align` is a new module and the sole owner of Qwen2 architecture knowledge. It
imports `gguf` and nothing else — no provider, no runtime, no evaluation surface, and no
`core.json` beyond what `gguf` already owns for escaping.

`docs/specs/roadmap.md` section R1 and `docs/specs/align-llm.md` section 5.1 sketch a directory
`frontends/qwen/`. Align's unit of modularity is one `.align` file per module and this repository
keeps every module flat under `src/`, so the frontend is `src/frontend_qwen.align` and the grouping
those documents describe is carried by the `frontend_` name prefix. This is a naming decision, not a
scope change; section 5.1 names the sibling that will test it.

```text
pub QwenIrStatus { Ok, Error }

pub QwenModelIr {
  status: QwenIrStatus,
  error_code: string,
  error_detail: string,
  arch: string,
  arch_present: bool,
  n_layer: i64,
  n_embd: i64,
  n_head: i64,
  n_head_kv: i64,
  head_dim: i64,
  n_ff: i64,
  n_vocab: i64,
  n_expert: i64,
  context_length: i64,
  rope_freq_base_bits: i64,
  rms_eps_bits: i64,
  block_count: i64,
  total_tensor_bytes: i64,
  size_sum_ok: bool,
  document: string,
}

pub fn build_model_ir(path: str) -> Result<QwenModelIr, Error>
```

The scalar fields exist for the section 2.4 summary block and for the smoke's assertions; the
document is the authoritative result. `build_model_ir` returns `Err` only for an invalid path
argument or an operating-system failure, both propagated unchanged from `gguf.read_table`. Every
defect in the file or in the model is data: it returns `Ok` with `status: Error`, a populated
`error_code` and `error_detail`, and a complete document. `src/main.align` maps `status: Error` to
its existing `Err(Error.Invalid)` process exit *after* writing or printing the document, exactly as
the `--inspect-gguf` arm does (`src/main.align:505-511`).

| Value | Owner | Allocation | Release |
| --- | --- | --- | --- |
| `file` handle, window `buffer` | `gguf.read_table` locals | one fd, one window; unchanged from R0 | scope `Drop`; no `f.close()` at this pin |
| `GgufTable` streams (`keys`, `texts`, `names`) | the `GgufTable` record | three owned `string`s for the whole file, built once by `builder.to_string()` | with the record |
| `GgufTable` columns | the `GgufTable` record | one `array<i64>` per column, each frozen once from an `array_builder<i64>` | with the record |
| accessor results | the caller | one owned `string` per `kv_string` / `kv_float_text` / `tensor_name` call | caller scope |
| block and tensor JSON | one `builder` in `build_model_ir` | accumulated once, in emission order | moved out by `to_string()` |
| final document | `builder` moved out by `to_string()` | one owned `string` | **moved** into `QwenModelIr.document`, then to the caller |

The document is **moved**, not cloned, into its sole owning result record, following the
`C8-MOVE-RESULT-DOCUMENTS` rule of `docs/specs/c8-speed-first.md` section 2.8, as `GgufInspection`
already does. `GgufTable` is likewise moved out of `read_table` and lives as one local in
`build_model_ir`. No cache, alias, or shared mutable state is introduced, and no module holds
process-global state, so two `--model-ir` invocations in one process, or in two processes, are
independent.

**Accessor allocation is bounded and counted.** `build_model_ir` performs at most 16 `kv_*` lookups
— the eleven metadata keys of section 2.5.3 other than `general.architecture`, which is a
`GgufTable` field rather than a lookup, with each of the two floats costing a bits lookup and a
text lookup, plus `general.file_type` and `tokenizer.ggml.tokens` — and `2 * tensor_count` `tensor_name`
calls, one during the geometry pass and one during block assembly, for at most 694 owned strings on
the reference model, each short-lived. That is a deliberate
trade against option A's zero-copy `str`-returning variant, which section 2.3.5 defers until the
compile probe settles the return-region question. Section 4.5 makes no performance claim, so the
simpler, provably-safe form ships.

### 2.8 Ledger dimensions

| Dimension | Contract | Owner | Acceptance |
| --- | --- | --- | --- |
| Exact command/API | Section 2.2 (`--model-ir`, two forms), section 2.3.2 (`read_table` and nine accessors plus two geometry functions), section 2.7 (`build_model_ir`). No aliases, no flags | `src/gguf.align`, `src/frontend_qwen.align`, `src/main.align` | `model-ir-smoke` CLI cases |
| Inputs and defaults | One model path; optional destination path; `n_expert` defaults to 0 when the key is absent; `rope.dim_count` defaults to `head_dim`; `rope.type` is fixed at 2; no ambient options | `src/frontend_qwen.align` | arity, option-isolation, and default cases |
| Results and errors | `Ok` + `status: "ok"`; `Ok` + `status: "error"` for every model defect; `Err` only for argument or OS failure | `src/frontend_qwen.align`, `src/main.align` | one fixture per row of section 2.6 |
| Multi-invalid precedence | Section 2.6 is strictly ordered; within a step, file order for tensors and section 2.5.3 order for keys; the first applicable row wins | `src/frontend_qwen.align` | `error-precedence` cases |
| Ownership and lifetime | Section 2.7. Every retained text is owned; the document is moved into its sole owner | `src/frontend_qwen.align` | `document-move`, ownership review |
| Allocation | Three streams and 25 columns per table; one document; at most `2 * tensor_count + 11` short-lived accessor strings | `src/gguf.align`, `src/frontend_qwen.align` | `bytes_read` bound and the descriptor-budget run |
| Persisted/cache identity | `N/A`. R1 writes one caller-named output document and reads nothing it wrote. It creates no cache, no index, no digest-addressed artifact, and changes no Align compiler cache policy. `GgufTable` is an in-process value with no persisted form, so there is no nominal-versus-structural fingerprint question | `N/A` with this reason | no cache behavior is claimed or tested |
| Schema version | `schema_version: 1`; any field addition, removal, reorder, or type change requires version 2. `blocks[].kind` and `blocks[].expert` are deliberately shaped so a MoE frontend needs no bump | `src/frontend_qwen.align` | golden document bytes, field-order assertion |
| Validation order | Section 2.6, deterministic and side-effect ordered; no output before derivation completes | `src/frontend_qwen.align` | ordered malformed corpus, untouched-destination assertion |
| Prerequisites | The pinned toolchain, plus the section 2.3.5 compile probe before implementation. Every consumed surface is verified present at `4b515f8d` in section 2.1. Requests 21 and 22 remain `PROPOSED`, non-blocking, and unconsumed | `src/gguf.align` | `make check`, `make build`, the recorded probe |
| Acceptance evidence | `model-ir-smoke` for correctness and the error corpus; the size-sum oracle for completeness; `model-ir-parity` for the roadmap gate | section 4 | sections 4.2, 4.3, 4.4 |
| Metrics | Primary: correctness parity against `llama-cli` plus the size-sum oracle. Secondary: `bytes_read` and tensor coverage | section 4.5 | parity run, oracle assertion, `bytes_read` bound |
| Text/wire boundary | Canonical UTF-8 JSON, declaration order, through R0's `json_string` escaping. A non-UTF-8 tensor name never reaches the document, because such a tensor matches no block name and surfaces as `R1_UNASSIGNED_TENSOR` with an escaped, bounded `error_detail` | `src/frontend_qwen.align` | escape and invalid-UTF-8 fixtures |
| Runtime-inspection fields | Every field is decoded from the file or derived by a stated formula from decoded values, except `rope.type`, which is architecture-owned and marked `type_source: "architecture"`. No reflection, no source read, no environment read | `src/frontend_qwen.align` | producer-provenance review, environment-perturbation case |
| Platform scope | Platform-independent derivation. The container codec assumes a little-endian host, which Align already assumes. No target-local boundary changes, so no platform profile is selected by this capability's own content | `src/frontend_qwen.align` | no target-local claim |
| Milestone ordering | R1 consumes no R2 decision: no layout, no ordering, no prefetch, no `.alignpack`. It emits `contiguous` as an observation, not a policy | this document | section 5.3 |

## 3. Closure matrix

This is the pre-implementation closure contract. Every applicable cell names its implementation
owner and the exact regression that closes it. `N/A` carries a concrete reason; `DEFERRED` is an
intentional design decision recorded in section 5, not a missing owner. Regression names are cases
inside `scripts/run-model-ir-smoke` (section 4.2) unless another runner is named.

### 3.1 `src/gguf.align` — the new public table surface

| Case | Contract to close | Implementation | Exact regression |
| --- | --- | --- | --- |
| Construction — table | Every `GgufTable` field is explicitly initialized, including empty streams and zero-length columns on an early container failure | `read_table` epilogue | `table-error-sentinels`: a `bad-magic` fixture yields `kv_count 0`, `tensor_count -1`, empty streams, and the container code |
| Construction — columns | Each column is one `array_builder<i64>` frozen exactly once by `.build()`; no column is built twice or left unbuilt | `read_table` epilogue | `table-column-lengths`: every column's `.len()` equals `kv_count` or `tensor_count` on all positive fixtures |
| Column/stream agreement | For every `i`, `0 <= start[i] <= end[i] <= stream.len()`, and spans are non-overlapping and ascending | accumulation sites | `table-span-invariants`, asserted through the emitted document for every fixture |
| Success — decoder reuse | `read_table` calls the same `decode_header`/`decode_kv`/`decode_tensor`/`resolve_data_offset`/`check_tensor_ranges` as `inspect`; no second container interpretation exists | `read_table` body | `table-inspect-parity`: both CLI arms over the whole corpus agree on version, alignment, `data_offset`, both counts, every tensor name/offset/type, and the container error code |
| Success — text spans | A key, string value, or tensor name containing a quote, a backslash, a control byte, an embedded NUL, and a 4-byte scalar round-trips through the stream and into valid JSON | `decode_text`, accessors | `wire-escapes`, reusing the R0 `full` fixture members through `--model-ir` |
| Success — float columns | `kv_float_bits` reproduces the exact IEEE pattern after the `as i64` / `as u64` round trip; `kv_has_text` is 0 for a non-finite float | float accumulation | `float-bits`: `rms_eps_bits` and `freq_base_bits` compared to `struct.pack` values, plus an infinity and a NaN fixture |
| Success — dimension columns | An axis a tensor does not declare holds `1`; a declared axis holds its extent | `decode_tensor` accumulation | `tensor-dims`: 1-, 2-, 3-, and 4-dimension tensors, asserting the emitted `dims` and `n_elements` |
| Success — lookup | `find_key` / `find_tensor` return the first matching index and `-1` when absent; an invalid-UTF-8 key or name never matches | `find_key`, `find_tensor` | `lookup-miss` and `lookup-invalid-utf8` |
| Success — geometry table | `ggml_block_size` / `ggml_type_size` return the section 2.5.7 pair for every listed id and `0` for every other id | geometry data | `type-geometry`: one fixture tensor per listed id with a generator-computed `nbytes`, plus ids 5, 21, and 199 asserting `R1_UNKNOWN_TENSOR_TYPE` |
| Failure — container | Every R0 error code still surfaces through `read_table` with the same code and offset | shared guards | `table-inspect-parity` over the R0 negative corpus |
| Failure — OS | An absent or unreadable path returns `Err` with no table and no document | `?` propagation | `missing-path`, `denied-path` |
| Malformed — accessor class | `kv_int` on a `STRING`, `kv_string` on a `UINT32`, and `kv_array_length` on a scalar each return `None` rather than a coerced value | accessor guards | `accessor-class`, driven through `R1_KEY_TYPE_MISMATCH` fixtures |
| Early exit | On a container failure the columns hold exactly the entries completed before it and nothing after is decoded | `read_table` walk guards | `table-partial`: a failure injected at KV 3 of 6 and at tensor 2 of 3, asserting exact column lengths |
| Cleanup | The fd and the window are released by scope `Drop`; the table's streams and columns drop with the record on both the success and the failure path | scope structure | `repeat-model-ir`: 64 sequential invocations, byte-identical documents, plus one run under `ulimit -n 64` |
| Branch joins | `Ok`/`Error` table construction has exactly one owner and both produce a complete, well-formed table | `read_table` return | `table-error-sentinels`, `table-column-lengths` |
| Loop joins | The metadata and tensor loops each terminate on count, on failure, and on a zero count | loop guards | `empty-container`: 0 KVs and 0 tensors reaches `R1_UNSUPPORTED_ARCH`, not an abort |
| Move-out | `GgufTable` is moved out of `read_table`, not cloned | `read_table` epilogue | `document-move`; ownership reviewed against `docs/specs/c8-speed-first.md` section 2.8 |
| Borrow discipline | No accessor returns a view derived from a `borrow` parameter; every text result is an owned `string` | accessor signatures | `make check`; section 2.3.5 probe recorded in the pull request |
| Bounds precondition | Every codec call is still reached only through `ensure`; `read_table` adds no new codec call site | unchanged `decode_*` | `table-inspect-parity` over the R0 truncation corpus, asserting a recorded code and **no abort** |
| Generic monomorphization | `N/A`: the surface declares no generic type or function | `N/A` with this reason | — |
| Shared/process-global state | `N/A`: no process-global or connection-global state; every value is per-call | `N/A` with this reason | `repeat-model-ir` |
| Concurrency | `N/A`: read-only, no lock. Two concurrent reads of one file are independent; no atomicity is claimed for a file mutated during the walk | `N/A` with this reason | documented unsupported caller case |
| Per-unit vs whole-program | The public surface compiles identically imported and whole-program | module boundary | `make check` (`check-per-unit`), `make build` |

### 3.2 `src/frontend_qwen.align` — Model IR and Block IR

| Case | Contract to close | Implementation | Exact regression |
| --- | --- | --- | --- |
| Construction — result | `QwenModelIr` is built with every field explicitly initialized, including the `-1` / `""` / `false` sentinels | `build_model_ir` epilogue | `ir-error-sentinels`: a `wrong-arch` fixture asserts each unreached field |
| Construction — table intake | `read_table` is called exactly once; its `Err` propagates and its `status: Error` becomes `R1_GGUF_ERROR` before any architecture work | `build_model_ir` prologue | `gguf-error`, asserting `error_detail` carries the container code |
| Success — hyperparameters | Every section 2.5.3 field is read or derived by its stated rule | `read_hyperparameters` | `model-fields`, against generator-declared golden values |
| Success — derivation | `head_dim = n_embd / n_head`; `rope.dim_count` prefers the key and falls back to `head_dim` with the right `dim_count_source` | `derive_shape` | `head-dim`, `rope-dim-metadata`, `rope-dim-derived` |
| Success — optional keys | An absent `qwen2.expert_count` yields 0; an absent `qwen2.rope.scaling.type` yields `null`; neither is an error | optional lookups | `optional-keys-absent`, `rope-scaling-present` |
| Success — geometry pass | `n_elements`, `block_size`, `type_bytes`, and `nbytes` are computed for every tensor in file order | `size_tensors` | `type-geometry`, `tensor-dims` |
| Success — block assembly | 2 * n_layer + 2 blocks in the section 2.5.8 emission order, with the right kind, layer, roles, and names | `build_blocks` | `block-order`, `block-roles`, `block-count` |
| Success — block arithmetic | `byte_size`, `first_absolute_offset`, `end_absolute_offset`, and `contiguous` follow section 2.5.6 | `close_block` | `block-bytes`, plus `block-noncontiguous` on a fixture with a deliberately permuted data layout |
| Success — tied embedding | An absent `output.weight` puts `token_embd.weight` in two blocks and counts its bytes once | `build_blocks` output arm | `tied-embedding`, asserting `size_sum_ok` still holds |
| Success — quant summary | `type_counts` has one ascending row per distinct id, and the rows' `bytes` sum to `total_tensor_bytes` | `summarize_quant` | `quant-summary`, with three distinct types in the fixture |
| Success — coverage | Every tensor is assigned; `computed_end == file_size` | `check_coverage` | `size-sum-oracle` on every positive fixture |
| Failure — every error code | Each of the 15 rows of section 2.6 is produced by at least one fixture, with the correct `error_detail` | ordered guards | `error-corpus`, one negative fixture per row |
| Failure — precedence | A file with two defects reports the earlier row | ordered guards | `error-precedence`: wrong arch + missing key; missing key + bad shape; unknown type + size-sum mismatch; duplicate tensor + unassigned tensor |
| Failure — overflow class | Every guard of section 2.6 is tested before the arithmetic it protects | `size_tensors`, `check_coverage` | `overflow-corpus`: a dimension product above `i64`, an `nbytes` above `i64`, a running total above `i64`, and an oracle sum above `i64` |
| Malformed — non-UTF-8 name | A tensor whose name is not UTF-8 matches no block and surfaces as `R1_UNASSIGNED_TENSOR` with an escaped, bounded detail; the document stays valid JSON | `check_coverage` | `invalid-utf8-name`, whose document is parsed with Python's `json` |
| Malformed — JSON safety | Every container-supplied string reaching the document goes through `json_string` | `render_*` | `wire-escapes` |
| Early exit | On any failure, derivation stops immediately and `blocks` holds exactly the blocks completed before it | guard returns | `ir-partial`: a failure injected at layer 1 of 2 asserts the exact block count |
| Early exit — no side effect | No output file is written and no stdout is produced before derivation completes | `src/main.align` ordering | `untouched-destination`, on the argument and OS-failure paths |
| Cleanup | The `GgufTable`, every accessor string, and the partial document drop on both paths with no observable leak | scope structure | `repeat-model-ir` under an fd-count assertion |
| Branch joins | `Ok`/`Error` status construction and the document return have exactly one owner | `build_model_ir` return | `document-move`, asserting a complete document for both statuses |
| Loop joins | The layer loop, the geometry loop, and the coverage loop each terminate on count, on failure, and on a zero count | loop guards | `zero-layer`: `qwen2.block_count = 0` reports `R1_KEY_VALUE_IMPLAUSIBLE`, never an empty success |
| Move-out | The document is moved into `QwenModelIr.document` | epilogue | `document-move` |
| `KVBlock` / `DequantBlock` | `N/A`: neither is backed by a file tensor; both are runtime constructs | `N/A` with the section 2.5.8 reason | — |
| `ExpertBlock` / `RouterBlock` | `DEFERRED` to the gpt-oss frontend; a nonzero expert count is rejected rather than partially described | section 5.1 | `moe-rejected` asserts `R1_UNSUPPORTED_MOE` |
| Generic monomorphization | `N/A`: no generic type or function is declared | `N/A` with this reason | — |
| Shared/process-global state | `N/A`: no process-global state; the module is pure over its input path | `N/A` with this reason | `env-perturbation` |
| Per-unit vs whole-program | Compiles identically imported and whole-program | module boundary | `make check`, `make build` |

### 3.3 `src/main.align` — CLI arm

| Case | Contract to close | Implementation | Exact regression |
| --- | --- | --- | --- |
| Construction — dispatch | `--model-ir` is selected only at `args[1]`, after the `--inspect-gguf` arm; arity is checked before any path or file work | `main` dispatch chain | `cli-arity`: 1, 2, 3, 4, and 5 arguments |
| Construction — path validation | Empty and over-length paths are rejected before `fs.open_rw`; a NUL-bearing path cannot be delivered through `argv` and is `N/A` at the CLI, with the module guard retained | `model_ir_demo` | `cli-path`, asserting no file is created |
| Success — one operand | The document goes to stdout with a trailing newline and nothing else is printed | `model_ir_demo` | `stdout-document`, piping stdout into a JSON parser |
| Success — two operands | The document goes to the named file; the summary block goes to stdout | `model_ir_demo` | `file-document` |
| Byte identity across forms | Both forms emit identical document bytes | `model_ir_demo` | `form-parity`, diffing the two outputs |
| Summary block | The section 2.4 lines appear in order; `arch` and `detail` are control-byte escaped and each occupies exactly one line | `model_ir_demo`, `sanitize_summary_line` | `summary-order`, `summary-control-bytes` |
| Failure mapping | `status: "error"` becomes `Err(Error.Invalid)` **after** the document is emitted; the destination holds the complete failure document, never a partial write | `model_ir_demo` epilogue | `error-corpus` asserts a nonzero exit and a parseable failure document |
| Failure — OS | An absent or unreadable path returns `Err` with no document and no summary | `?` propagation | `missing-path`; `denied-path` copies a positive fixture, `chmod 000`s it, and asserts a nonzero exit, empty stdout, and an untouched sentinel, printing an explicit `SKIPPED` note when running as root |
| Early exit | An arity or path failure produces no output at all | guard ordering | `cli-arity`, `cli-path` assert empty stdout |
| Unknown-selector compatibility | An unrecognized `args[1]` still prints help and returns `Ok(())`; the `--inspect-gguf` arm is unchanged | unchanged chain | `unknown-selector`, plus the full `gguf-smoke` run |
| Option/environment isolation | No environment variable changes any document byte | no env read exists | `env-perturbation` with a perturbed locale, `TZ`, `HOME`, `SOURCE_DATE_EPOCH`, and two invented `ALIGN_LLM_*` variables |
| Help text | One new usage line names both forms | `print_help` | `cli-arity` no-argument case matches the help block |
| Cleanup | `N/A`: the arm owns no resource beyond the `QwenModelIr` record it receives | `N/A` with this reason | — |

### 3.4 `Makefile` and `scripts/` — build and verification graph

| Case | Contract to close | Implementation | Exact regression |
| --- | --- | --- | --- |
| Target definition | `model-ir-smoke` depends on `build` and runs `./scripts/run-model-ir-smoke`; it is added to `.PHONY` | `Makefile` | `make model-ir-smoke` from a clean tree |
| Aggregate membership | `model-ir-smoke` **joins** `HOSTED_CHECK_TARGETS`. It is the hosted owner of a new consumer surface (`--model-ir`), needs no model, no network, and no reference tool, generates its own fixtures, and runs in seconds — the same justification that admitted `gguf-smoke` (`Makefile:99-103`) | `Makefile` | `make gate-topology-check` after the membership change |
| Topology consistency | The `.PHONY` list, the target list, and `HOSTED_CHECK_TARGETS` agree | `Makefile` | `python3 scripts/check-gate-topology` |
| Qualification exclusion | `model-ir-parity` is a focused, opt-in target and joins **no** aggregate, exactly like `gguf-reference-parity` (`Makefile:107-109`) | `Makefile` | `make gate-topology-check` asserts its absence from both lists |
| Preflight profile selection | Changing `Makefile` matches `FRESH_IMAGE_PATTERNS` (`scripts/verification_scope.py:23`), so the classifier returns scope `fresh-image` with `fresh_focused` and `fresh_installed` set, and `scripts/pre-pr` selects the fresh-image **installed** profile. That is expected for this capability and must not be replaced by a Docker skip or an ambient `DOCKER_HOST` endpoint | `Makefile`, `scripts/pre-pr` | `python3 scripts/pre-pr --plan` names the installed profile before the run; the run itself is the evidence |
| Fixture generation | `scripts/gguf_fixture.py` gains the qwen2 corpus and still writes only into a caller-supplied temporary tree | `scripts/gguf_fixture.py` | the smoke's repository leak sweep for `*.gguf` and `manifest.json` |
| Fixture independence | The generator derives no value from `src/gguf.align` or `src/frontend_qwen.align`; the block geometry table and every expected `nbytes` are computed in Python | `scripts/gguf_fixture.py` | code review; the generator's import list is unchanged |
| Generator compatibility | The new corpus does not change any existing fixture's bytes, so `gguf-smoke` keeps passing unmodified | `scripts/gguf_fixture.py` | `make gguf-smoke` before and after |
| Cleanup | Every fixture path is removed by a shell `trap` on `EXIT`, including on failure; the runner's last assertion is that the temp root is still present | `scripts/run-model-ir-smoke` | the R0 `stale-fixture` shape (`docs/specs/r0-gguf-inspection.md` section 6, item 21) |
| Reference skip | An unset or absent `ALIGN_LLM_GGUF_MODEL` or `ALIGN_LLM_LLAMA_CLI` prints one exact `N/A` line and exits 0 | `scripts/run-model-ir-parity` | run with each variable unset; assert the exact skip line |
| Reference isolation | The parity runner never modifies the model and never writes outside its temp root | `scripts/run-model-ir-parity` | model size and `mtime` compared before and after |
| Parse failure fails closed | A `print_info` block that does not yield every required key, or yields a required key twice with different values, exits nonzero — never a silent pass and never a skip | `scripts/run-model-ir-parity` | a synthetic truncated-log unit inside the runner |
| Documentation | `docs/specs/roadmap.md` section R1 and `HANDOFF.md` name this document and the two runners; `docs/specs/r0-gguf-inspection.md` receives the section 6 corrections | integration commit | out of scope for this design-only file; recorded as a follow-on and listed in section 6 |

## 4. Fixture and qualification design

### 4.1 `scripts/gguf_fixture.py` — the qwen2 corpus

The existing generator is extended, not replaced. It keeps its independence property: it emits
container bytes from its own `struct`-packing tables and computes every expected value in Python,
importing nothing from `src/`. The block-geometry table of section 2.5.7 is transcribed into it
separately from the Align table, which is what makes `nbytes` a real differential check rather than
a mirror of the implementation.

**The positive fixture `qwen2-full.gguf`** is a complete, valid v3 container, well under 1 MiB, with
a real data section of exactly the declared size that the frontend must never decode:

```text
general.architecture                        STRING   "qwen2"
general.file_type                           UINT32   15
general.quantization_version                UINT32   2
qwen2.block_count                           UINT32   2
qwen2.context_length                        UINT32   512
qwen2.embedding_length                      UINT32   64
qwen2.feed_forward_length                   UINT32   128
qwen2.attention.head_count                  UINT32   4
qwen2.attention.head_count_kv               UINT32   2
qwen2.rope.freq_base                        FLOAT32  1000000.0
qwen2.attention.layer_norm_rms_epsilon      FLOAT32  1e-06
tokenizer.ggml.tokens                       ARRAY of STRING, length 32
```

giving `head_dim = 16`, `n_vocab = 32`, `n_expert = 0`, and 27 tensors: `token_embd.weight`,
`output_norm.weight`, `output.weight`, and 12 per layer for 2 layers. Shapes follow section 2.5.8
exactly, so `token_embd.weight` is `[64, 32]`, `blk.L.attn_k.weight` is `[64, 32]`,
`blk.L.ffn_gate.weight` is `[64, 128]`, and `blk.L.ffn_down.weight` is `[128, 64]`.

Quantization types are mixed on purpose: norms and biases are `F32`; `attn_q.weight`,
`attn_k.weight`, `ffn_gate.weight`, and `token_embd.weight` are `Q4_K`; `attn_v.weight`,
`ffn_down.weight`, and `output.weight` are `Q6_K`; `attn_output.weight` is `Q8_0`;
`ffn_up.weight` is `Q4_0`. That exercises a 256-element K-block, a 32-element legacy block, and a
1-element unquantized type in one file, and gives `quant.type_counts` five ascending rows. Every
quantized tensor's element count is a multiple of its block size — `64 * 64 = 4096`,
`64 * 32 = 2048`, `64 * 128 = 8192` are all multiples of 256 — so the fixture is representable
rather than contrived.

The generator computes each tensor's `nbytes`, lays the data section out contiguously in tensor-table
order at aligned offsets, and sets the file length so that `data_offset + Σ nbytes == file_size`
exactly. That single property is what makes the oracle testable without a 4.68 GB model.

Three further positive variants:

- `qwen2-tied.gguf` — no `output.weight`; the output block references `token_embd.weight` and the
  oracle still holds, because the shared tensor's bytes are counted once.
- `qwen2-rope-dim.gguf` — declares `qwen2.rope.dimension_count = 16` and
  `qwen2.rope.scaling.type = "linear"`, pinning `dim_count_source: "metadata"` and a non-null
  `scaling_type`.
- `qwen2-permuted.gguf` — the same logical model with the data section laid out in a different
  order, so that at least one block is non-contiguous and the `contiguous` field is asserted in both
  states while the oracle still holds.

**The negative corpus** is one file per reachable row of section 2.6, each carrying its expected code
and `error_detail`, both computed by the generator from the bytes it wrote:

| Fixture | Defect | Expected |
| --- | --- | --- |
| `qwen2-bad-magic.gguf` | the R0 `bad-magic` bytes | `R1_GGUF_ERROR`, detail `GGUF_BAD_MAGIC` |
| `qwen2-wrong-arch.gguf` | `general.architecture = "llama"` | `R1_UNSUPPORTED_ARCH`, detail `llama` |
| `qwen2-missing-key.gguf` | no `qwen2.block_count` | `R1_MISSING_KEY`, detail the key |
| `qwen2-key-type.gguf` | `qwen2.embedding_length` as `STRING` | `R1_KEY_TYPE_MISMATCH` |
| `qwen2-implausible.gguf` | `qwen2.attention.head_count = 0` | `R1_KEY_VALUE_IMPLAUSIBLE` |
| `qwen2-indivisible.gguf` | `n_embd = 65`, `n_head = 4` | `R1_KEY_VALUE_IMPLAUSIBLE` |
| `qwen2-moe.gguf` | `qwen2.expert_count = 4` | `R1_UNSUPPORTED_MOE`, detail `4` |
| `qwen2-duplicate.gguf` | two `blk.0.attn_norm.weight` entries | `R1_DUPLICATE_TENSOR` |
| `qwen2-unknown-type.gguf` | one tensor with `ggml_type` 21, one with 199 | `R1_UNKNOWN_TENSOR_TYPE`, detail `21` |
| `qwen2-unaligned.gguf` | a `Q4_K` tensor with 100 elements | `R1_TENSOR_SHAPE_UNALIGNED` |
| `qwen2-overflow-dims.gguf` | an `F32` tensor with dims `[2^31, 2^31, 2^31]`, so the element product alone exceeds `i64` | `R1_SIZE_OVERFLOW` |
| `qwen2-overflow-total.gguf` | two `F32` tensors of dims `[2^30, 2^30]`: each `nbytes` is `2^62` and representable, their sum is `2^63` and is not | `R1_SIZE_OVERFLOW` |
| `qwen2-missing-tensor.gguf` | no `blk.1.ffn_up.weight` | `R1_MISSING_TENSOR` |
| `qwen2-bad-shape.gguf` | `blk.0.attn_q.weight` as `[64, 63]` | `R1_TENSOR_SHAPE_UNEXPECTED` |
| `qwen2-vocab-mismatch.gguf` | `tokenizer.ggml.tokens` length 31 against `token_embd` `dims[1] = 32` | `R1_VOCAB_MISMATCH`, detail `31!=32` |
| `qwen2-extra-tensor.gguf` | an extra `blk.9.attn_q.weight` beyond `n_layer` | `R1_UNASSIGNED_TENSOR` |
| `qwen2-invalid-name.gguf` | a tensor name containing `0xFF` | `R1_UNASSIGNED_TENSOR`, escaped bounded detail |
| `qwen2-size-sum.gguf` | 64 extra trailing bytes past the data section | `R1_SIZE_SUM_MISMATCH`, detail `A!=B` |
| `qwen2-nonfinite.gguf` | `qwen2.rope.freq_base` as an infinity | `status: "ok"`, `freq_base: null`, `freq_base_bits: "7f800000"` |

Plus the four precedence pairs named in section 3.2, each asserting the earlier code.

`qwen2-nonfinite.gguf` is deliberately a *positive* case: a non-finite rope base is a wire-rendering
problem, not a structural one, and R0 already established that `null` plus the exact bits is the
honest rendering. Rejecting it would be R1 inventing a plausibility rule the format does not have.

### 4.2 Owner — `scripts/run-model-ir-smoke`, `make model-ir-smoke`

The narrow durable owner, following the `scripts/run-gguf-smoke` shape exactly: resolve the
repository root, `mktemp -d`, `trap cleanup EXIT`, generate fixtures, run `./main --model-ir`, and
assert with an inline Python block that parses the document with the standard `json` module. It
requires no model, no network, and no reference tool, runs in seconds, and therefore joins
`HOSTED_CHECK_TARGETS`.

It covers every closure cell in sections 3.1, 3.2, and 3.3 that names a case without another runner,
and additionally:

- runs both `--model-ir` forms on every fixture and diffs the bytes (`form-parity`);
- runs `--inspect-gguf` on the same corpus and asserts the `table-inspect-parity` agreement;
- re-runs the entire existing R0 corpus through `--model-ir`, which is where the container error
  codes and the truncation sweep are re-proved against the second walk;
- asserts top-level, `model`, `rope`, `quant`, `coverage`, and block field order against the section
  2.5 declaration order, so a reordering is a test failure rather than a silent schema change;
- performs the repository leak sweep and the temp-root presence assertion.

### 4.3 The size-sum oracle

```text
data_offset + Σ_{t in tensors} nbytes(t) == file_size
```

This is the capability's own proof that its Block IR is complete and correctly sized, and it is
computed from inside the program on every input, real or synthetic. Four properties make it strong:

1. **It is not self-referential.** `data_offset` comes from the container walk, `file_size` from
   `f.len()`, and each `nbytes` from the declared dimensions and the independent geometry table. No
   term is derived from another.
2. **It catches the failure modes that matter.** A wrong `block_size` or `type_bytes`, a transposed
   dimension, a missed tensor, a double-counted tensor, and a misread `n_dims` all move the sum.
3. **It is exact, not a bound.** GGUF's data section is exactly the concatenation of the tensors at
   their declared offsets, with alignment padding accounted for by `data_offset`. On the reference
   model `5,953,536 + 4,677,120,000 = 4,683,073,536`, which is the file's byte length to the byte.
4. **A shared tensor is counted once.** The tied-embedding case sums over the *tensor table*, not
   over block membership, so a tensor appearing in two blocks does not double the total. The
   `qwen2-tied.gguf` fixture pins it.

A mismatch is `R1_SIZE_SUM_MISMATCH` and a failed status, never a warning. An unrepresentable sum is
`R1_SIZE_OVERFLOW`, because "too large to add" and "does not add up" are different facts and
conflating them would hide an arithmetic bug behind a data complaint.

The oracle does **not** hold for every GGUF file in existence — a container with padding between
tensors, or trailing bytes, would fail it legitimately. R1 treats that as out of scope: no such file
is known among the models this repository targets, and accepting a slack sum would give up the whole
value of the check. If one appears, the resolution is a new error code distinguishing "sum is less
than the file" from "sum exceeds the file", not a tolerance.

### 4.4 Focused qualification — `scripts/run-model-ir-parity`, `make model-ir-parity`

Opt-in, never in an aggregate, and never in CI. It discharges the roadmap gate by comparing the
derived Model IR against llama.cpp's own reading of the same file.

Inputs, both required, both explicitly skippable, **neither with a default**:

- `ALIGN_LLM_GGUF_MODEL` — path to the model. An unset value is a skip, never a guess at a local
  path (the rule `docs/specs/r0-gguf-inspection.md` section 6, item 24 already established).
- `ALIGN_LLM_LLAMA_CLI` — path to the reference executable, expected to be `llama-cli`.

If either is unset or absent, the runner prints one exact line —
`model ir parity: N/A (ALIGN_LLM_LLAMA_CLI unset)` or the model equivalent — and exits 0. A
qualification that silently passes when its subject is missing is worse than no qualification, so
the skip is explicit, is named in the pull request as the `N/A` reason, and never counts as a pass.

**Reference invocation and build identity.** The runner first records
`"$ALIGN_LLM_LLAMA_CLI" --version`, whose output on the development host is
`version: 0.2.0 (build 10566, commit bb4caa754)` followed by
`built with AppleClang 21.0.0.21000101 for Darwin arm64`. The build string is printed and recorded
in the pull request, because `print_info` is a diagnostic log and not a stable interface: a future
build may rename a field, and the recorded build is what makes a later failure diagnosable rather
than mysterious. The comparison itself is then
`"$ALIGN_LLM_LLAMA_CLI" -m "$MODEL" -v -n 0 --no-warmup -p hi`, with stdout and stderr merged. A
nonzero exit from the reference is a **hard failure**, not a skip.

**Parser contract.** Every rule below is stated because the log format is not a contract:

1. Each candidate line is first stripped of an optional leading `-v` log prefix matching
   `^\S+\s+I\s+`, which is how the observed output spells it
   (`0.00.248.535 I print_info: n_layer               = 28`).
2. The remainder must match `^print_info:\s+(?P<key>.+?)\s*=\s*(?P<value>.*)$`. The key is
   everything before the run of whitespace preceding `=`, right-trimmed, and may contain spaces
   (`rope type`, `file type`). The value is right-trimmed and may be empty.
3. The reference loads the model more than once in a single run — the observed output contains two
   complete `print_info` blocks — so all occurrences are collected. If any required key appears with
   two different values, the runner exits nonzero with `parity: AMBIGUOUS <key>`. It never takes the
   first or the last.
4. If any required key is missing after parsing, the runner exits nonzero with
   `parity: UNPARSED <key>`. **Parse failure fails closed**; it is never a skip and never a pass.

**Compared rows.** For the named reference model the expected values are the right-hand column:

| Model IR field | `print_info` key | Comparison | Expected |
| --- | --- | --- | --- |
| `model.arch` | `arch` | string equality | `qwen2` |
| `model.n_layer` | `n_layer` | integer equality | 28 |
| `model.n_embd` | `n_embd` | integer equality | 3584 |
| `model.n_head` | `n_head` | integer equality | 28 |
| `model.n_head_kv` | `n_head_kv` | integer equality | 4 |
| `model.head_dim` | `n_embd_head_k` **and** `n_embd_head_v` | integer equality against both | 128 |
| `model.n_ff` | `n_ff` | integer equality | 18944 |
| `model.n_expert` | `n_expert` | integer equality | 0 |
| `model.n_vocab` | `n_vocab` | integer equality | 152064 |
| `model.context_length` | `n_ctx_train` | integer equality | 131072 |
| `model.rope.type` | `rope type` | integer equality | 2 |
| `model.rope.freq_base_bits` | `freq_base_train` | `"%.1f" % unpack(bits) == value` | `1000000.0` |
| `model.rms_eps_bits` | `f_norm_rms_eps` | `"%.1e" % unpack(bits) == value` | `1.0e-06` |

The two float rows are the reason `*_bits` exists in the schema. The runner reconstructs our value
in Python with `struct.unpack("<f", struct.pack("<I", bits))[0]` — so our side is bit-exact — and
then formats it with the reference's own `printf` precision (`%.1f` and `%.1e`) and compares
strings. That is exact in both directions and needs no tolerance: the decoded `f32` for the epsilon
is `9.999999974752427e-07`, whose `%.1e` rendering is `1.0e-06`, which is what llama.cpp prints for
the same bytes.

**A second, independent row set** comes from the loader's own type census, which needs no
`print_info` parsing:

```text
llama_model_loader: - type  f32:  141 tensors
llama_model_loader: - type q4_K:  169 tensors
llama_model_loader: - type q6_K:   29 tensors
```

Each line is matched case-insensitively against a row of `quant.type_counts` by type name, and the
tensor counts must agree exactly, with no row on either side unmatched. This is the closest thing to
a direct check of the Block IR's tensor classification that an external tool offers.

**Deliberately outside parity scope**, recorded so the boundary is explicit rather than discovered:
`file type = Q4_K - Medium` (a llama.cpp enumeration R1 refuses to assert, section 2.5.4);
`model params` and `file size` (rounded, human-formatted); every tokenizer row (section 1.3);
`rope scaling`, `freq_scale_train`, and `n_ctx_orig_yarn` (rope-scaling interpretation R1 reports
but does not derive); and `n_rot`, which agrees with `head_dim` here but is a llama.cpp-side
derivation with its own rules.

The runner additionally asserts the section 4.3 oracle against an independent `stat` of the file,
asserts the section 4.5 `bytes_read` bound, records the wall-clock duration of the `--model-ir`
invocation as a diagnostic, and verifies that the model's size and modification time are unchanged
before and after — the read-only proof.

### 4.5 Metrics

**Primary — correctness.** Two pass/fail measurements, both required: the section 4.4 parity
comparison passes on the reference model, and the size-sum oracle holds on every positive fixture
and on the reference model. Neither is a speed metric.

**Secondary — coverage.** `coverage.assigned_tensor_count == coverage.tensor_count` with
`unassigned_tensors` empty: 339 of 339 on the reference model, distributed over 58 blocks.

**Secondary — `bytes_read`.** Inherited from R0 unchanged and re-asserted here, because `read_table`
is a second walk and could silently start reading more: `bytes_read < data_offset + WINDOW_BYTES`,
with the reference-model expectation of roughly 6.3 MB against a 4.68 GB file — under 0.14 percent.
The parity runner asserts the bound; the smoke asserts the exact value on single-window fixtures.

R1 makes **no performance claim**. Wall-clock duration is recorded by the parity runner as a
diagnostic so a later regression is visible, but no threshold is asserted and no baseline is
established. Under `CLAUDE.md` a speed claim would require a reproducible benchmark and a named
baseline; R1 has neither and does not pretend to. In particular, section 2.3.6's discarded rendering
work and section 2.7's per-lookup string allocations are recorded as known, bounded costs — not as
regressions to be optimized before there is a measurement that says they matter.

## 5. Deferred surfaces

### 5.1 The gpt-oss / MoE frontend

`docs/specs/roadmap.md` section R1 names `frontends/gpt_oss/` alongside `frontends/qwen/`, and
`docs/specs/align-llm.md` section 5.2 defines `ExpertBlock` and `RouterBlock` for exactly that
shape. R1 delivers only the qwen2 half, deliberately: a dense frontend and an MoE frontend are two
consumer-complete capabilities, not one, and the second is where the interesting decisions live —
per-expert block granularity, router placement, and the expert-reuse measurement R2 is built to
take.

The seam is already cut. `blocks[].kind` is a string and `blocks[].expert` exists with value `-1`,
so adding `ExpertBlock` and `RouterBlock` needs no `schema_version: 2`. `src/gguf.align`'s
`GgufTable` is architecture-neutral, so a second frontend imports it unchanged. Section 2.7's
`frontend_` naming convention gives `src/frontend_gpt_oss.align` its place.

What R1 does **not** do is prepare for it speculatively. `n_expert != 0` is rejected today rather
than partially described, because a Model IR that silently omits the expert tensors would satisfy
neither the coverage check nor a consumer.

### 5.2 Tokenizer and vocabulary

Building a tokenizer needs the 152,064 entries of `tokenizer.ggml.tokens` and the 151,387 entries of
`tokenizer.ggml.merges` as addressable data. At the pin that is an `array<string>` read, which
Request 22 records as rejected as a general expression. Section 2.3.3 explains why the narrow
call-argument admission is not a foundation to build a tokenizer on.

R1 therefore reads only what R0's decoder already records without materializing an element: the
array's declared length, which is enough for the `n_vocab` cross-check of section 2.5.3 and for
nothing else. **This is what keeps Request 22 non-blocking.** Making the tokenizer part of this
capability would reclassify it as blocking under the `CLAUDE.md` rule that a non-blocking request
reaching its first consumer becomes blocking — and would stall a capability that is otherwise
complete.

The resume condition is stated in Request 22 already: Align ships borrow indexing for Move arrays.
When it does, the tokenizer becomes its own capability with its own contract, and the natural
producer surface is a `gguf.read_string_array(path, key) -> Result<array<string>, Error>` on
`src/gguf.align`. R1 does not write against it, name it in code, or shape any current field around
it.

### 5.3 R2 hooks — `align-pack` and the layout planner

`blocks[].tensors[].absolute_offset`, `nbytes`, `type`, and each block's `byte_size`,
`first_absolute_offset`, and `contiguous` are exactly the inputs a layout planner needs, which is
why `contiguous` is computed here rather than left to each consumer to rediscover. R1 defines no
`.alignpack` format, no reordering policy, no residency tier, and no prefetch plan; it observes the
current layout and reports it.

The one decision R1 deliberately leaves open for R2 is block **granularity**.
`docs/specs/align-llm.md` section 5.2 says the initial unit is the layer and the expert, with
sub-blocks and neuron clusters as future work. R1 ships layer granularity. Splitting an
`AttentionBlock` into per-projection sub-blocks is a schema-compatible change — the `role` field is
already the seam — and should be made when a measurement, not a preference, asks for it.

### 5.4 The Request 22 migration

When Request 22 reaches `ALIGN_MERGED`, `GgufTable`'s internals can become indexable
`array<KvEntry>` / `array<TensorEntry>` records with **no change to any signature in section
2.3.2**: every accessor is already index-in / owned-value-out, and the stream-plus-column
representation is entirely behind them. That is the property option A was chosen for
(section 2.3.3, reason 4), and it is also the second half of Request 22's own acceptance criterion 3
— which today names only `src/gguf.align`'s `render_tensors` workaround. The register entry should
be extended to name `GgufTable` as a second align-llm verification target when this capability
merges; that is a documentation follow-on for the implementation commit, not a change to the
request's status.

Request 21 (`fs.open_ro`) is inherited unchanged: R1 opens the model through `gguf.read_table`,
which uses `fs.open_rw`, so the same non-blocking read-only-mount limitation and the same
`Err(Error.Denied)` surfacing apply. R1 adds no new evidence and no new urgency, and does not
duplicate the request.

### 5.5 Other deferred items

- **`IQ*` and `TQ*` block geometry.** Section 2.5.7 ships the verified rows only; every other id is
  `R1_UNKNOWN_TENSOR_TYPE`. Adding one is a two-column data change plus a `type-geometry` fixture,
  gated on a named GGML revision as the transcription source and on the size-sum oracle passing
  against a real model that uses the type. Deferred rather than guessed.
- **`general.file_type` naming.** Section 2.5.4. Deferred permanently unless GGUF itself normatively
  defines the enumeration.
- **Additional architectures.** `qwen3`, `llama`, and their relatives share much of the key
  vocabulary and differ in exactly the places a Model IR must be right about. Each is a separate
  frontend under the section 2.7 naming convention, not a widened `if` in this one.
- **Non-contiguous and padded containers.** Section 4.3 records why the oracle is exact rather than
  a bound and what a real counterexample would justify.
- **Big-endian GGUF, multi-shard models, and the mmap arena alternative.** All inherited from
  `docs/specs/r0-gguf-inspection.md` sections 5.3 and 5.4 unchanged. R1 introduces no new evidence
  for or against any of them.

## 6. Corrections this capability owes `docs/specs/r0-gguf-inspection.md`

R0's plan describes an R1 consumer contract that does not exist: `GgufKv` and `GgufTensor` are named
as public record types, but `KvRow` and `TensorRow` are private, the tensor bodies are a
NUL-separated stream with parallel columns rather than a collection, and `GgufInspection`
(`src/gguf.align:52-68`) exposes eleven scalars plus `document: string`. Those sentences were written
before implementation and were never corrected, because R0 had no consumer to falsify them. R1 is
that consumer.

The corrections below are recorded here now and **applied to
`docs/specs/r0-gguf-inspection.md` section 6 in the R1 implementation commit**, so that plan, code,
and consumer change together. This document does not edit that file.

| # | Amends | Exact sentence to change | Correction |
| --- | --- | --- | --- |
| 25 | section 1.1, third paragraph (`:26-27`) | "Both consume the record types defined here rather than re-parsing the container." | Replace with: "Both consume the public `GgufTable` surface `docs/specs/r1-qwen-model-ir.md` section 2.3 adds to this module rather than re-parsing the container. No record type defined in this document is public." |
| 26 | section 5.1, second sentence (`:942-944`) | "R1 frontends under `frontends/qwen/` and `frontends/gpt_oss/` consume `GgufKv` and `GgufTensor` records to build a Model IR." | Replace with: "R1 frontends — `src/frontend_qwen.align`, and later `src/frontend_gpt_oss.align`, flat under `src/` because Align's unit of modularity is one file per module — consume `gguf.read_table` and its typed accessors to build a Model IR. `GgufKv` and `GgufTensor` were never implemented: Request 22 rejects indexing an array of Move elements, so the table is carried as concatenated text streams plus parallel `array<i64>` columns." |
| 27 | section 5.1, fourth paragraph (`:946-948`) | "First, a caller needing the full 152,064-entry token array cannot get it from the section 2.4 document; it will call a future `gguf.read_string_array(path, key)` that R1 owns." | Replace with: "First, a caller needing the full 152,064-entry token array cannot get it from the section 2.4 document, and R1 does not add one: `docs/specs/r1-qwen-model-ir.md` section 5.2 keeps the tokenizer out of scope precisely so that Request 22 stays non-blocking. A `gguf.read_string_array(path, key)` becomes possible when Request 22 merges, and is owned by the tokenizer capability, not by R1." |
| 28 | section 1.3, second bullet, and section 2.5.4 | "No dequantization. No GGML block format is unpacked. The tensor `type` field is reported as an id and a name; its element layout, block size, and scale encoding are R2 concerns." | Amend the last clause to: "…its scale encoding and element layout are R2 concerns. Its **block geometry** — elements per block and bytes per block — is exposed by this module as `ggml_block_size` / `ggml_type_size` (`docs/specs/r1-qwen-model-ir.md` section 2.5.7), because both R1 and R2 need it and duplicating a GGML table into each frontend would be worse than owning it beside `ggml_type_name`. No block is unpacked and no scale is read; the non-goal is otherwise unchanged." |
| 29 | section 2.5.3, allocation table row (`:537`) | "\| decoded `string` values \| the owning `GgufKv` / `GgufTensor` record \| one per retained text value \| with the record \|" | Replace the owner cell with: "the `KvRow` / `TensorRow` value, which is private and short-lived; retained text reaches a caller either inside `GgufInspection.document` or inside a `GgufTable` stream". |
| 30 | section 2.5.4, the public-API block (`:551-569`) | The block lists only `GgufStatus`, `GgufInspection`, and `pub fn inspect`. | Extend it with the section 2.3.2 surface — `GgufTable`, `read_table`, the nine accessors, and the two geometry functions — and add the sentence: "`inspect` and `read_table` are two walks over one decoder; `docs/specs/r1-qwen-model-ir.md` section 2.3.6 records why they cannot share a walk function at this pin and the `table-inspect-parity` regression that keeps them from drifting." |

Items 25 through 27 correct claims about a consumer contract. Item 28 narrows a non-goal that would
otherwise be violated by an obviously correct change. Items 29 and 30 correct the ownership table
and the public-API block to match what shipped plus what R1 adds. None is a deferral, and none
changes `R0_GGUF_INSPECTION`'s `schema_version`.
