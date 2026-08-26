# R2A-EXPERT-TRACE-CAPTURE: eval-callback transcript parser and the `R2_ACTIVATION_TRACE` document

Status: plan of record for the first Track B R2 capability named by `docs/specs/roadmap.md` section
R2 ("R2a: callbackでrouter tensorを観測"). It is authoritative for the R2A public contract: the
`main --expert-trace` CLI arm, the `R2_ACTIVATION_TRACE` document at `schema_version: 1`, the new
`src/expert_trace.align` owner module, the bounded streaming line reader it needs, and the parsing
contract bound to llama.cpp build 10566.

`docs/specs/roadmap.md` remains authoritative for delivery order and for the R2 gate itself.
`docs/specs/align-llm.md` remains authoritative for the architecture this measurement serves —
section 5.2's `BlockKind`, section 6's VRAM / DRAM / NVMe tiers, and section 7.4's score-based cache.
`docs/specs/r1b-gptoss-moe-ir.md` remains authoritative for the per-`(layer, expert)` `ExpertBlock`
that is the placeable unit this trace measures the *demand* for; R2A produces no Block IR and reads
no GGUF byte.

This document triggers the `CLAUDE.md` proportional design gate on three counts: it adds a public
CLI verb (`--expert-trace`), it introduces a new versioned exchanged format
(`R2_ACTIVATION_TRACE` 1), and it introduces a coordinated invariant across three modules
(`src/expert_trace.align`, `src/main.align`, and the new fixture and qualification graph) plus a
`Makefile` change whose preflight consequence is recorded in section 3.5.

The capability is **designed, not implemented**. Section 5 records what it deliberately does not do,
and section 1.4 states plainly which half of the roadmap R2 gate it can discharge on this host and
which half it cannot.

## 1. Purpose, scope, non-goals, and the gate

### 1.1 Goal

Turn one llama.cpp eval-callback transcript into one machine-readable document that answers the R2
question — **does conditional locality exist, and can it be judged numerically** — for the
transcripts that exist, and that says so honestly and in the document itself when it cannot.

R2 uses the existing runtime as an instrument. The instrument is
`llama-eval-callback`, whose whole output is a text transcript on stdout. R2A is the parser and the
aggregator: it consumes a transcript, recovers per-`(token, layer)` expert selections from the
`ffn_moe_topk-N` nodes, computes the locality aggregates section R2 names ("token間expert reuse",
"prefill/decode差"), and emits them with explicit observation counts so that no reader can mistake a
partially observed prefill for a measured one.

Three properties are load-bearing, and each is argued rather than assumed below:

- **Streaming.** A transcript for a 5-token prompt against a dense 7B model is already 1.4 MB;
  a MoE decode trace of a few thousand steps is hundreds of MB. The document must be derivable
  without holding the transcript, or any single unbounded string, in memory. Section 2.4.
- **Fail-closed on grammar.** The transcript grammar is a debug print, not a contract. A parser that
  silently ignores what it does not recognize would report a confident `moe: false` for a MoE model
  whose print format moved. Section 2.6 makes every unrecognized shape an error code.
- **Honest observation accounting.** The instrument truncates every axis longer than six entries to
  three-plus-three (section 2.2). During prefill that means at most six of `n_tokens` tokens are
  ever printed. Every aggregate therefore carries the number of tokens it saw and the number it did
  not. Section 2.5.7.

### 1.2 In scope

1. A new CLI arm `main --expert-trace CALLBACK_LOG [OUT.json]`, in the two-form shape
   `--inspect-gguf` and `--model-ir` already use (section 2.3).
2. A new module `src/expert_trace.align` owning the bounded line reader, the transcript grammar, the
   graph segmentation, the selection table, the locality aggregates, and the whole document
   renderer.
3. A **bounded streaming line reader** over `fs.open_rw` + `f.pread` + `f.len`, reusing the
   `Cursor` / window / `refill` idiom `src/gguf.align` already proves at this pin, extended with
   line reassembly across window boundaries and an explicit `MAX_LINE_BYTES` cap (section 2.4).
4. The `R2_ACTIVATION_TRACE` document at `schema_version: 1`: run identity, graph shape,
   MoE facts, per-`(token, layer)` selections with phase and truncation flags, and the locality
   aggregates (section 2.5).
5. A **dense transcript is a first-class success.** A transcript with no `ffn_moe_topk-N` node
   yields `status: "ok"` and `moe.present: false`, with every non-MoE field populated. That is the
   only case verifiable on this host today, and it is the case the owner test asserts hardest.
6. A synthetic transcript generator `scripts/eval_callback_fixture.py`, independent of `src/`, with
   the dense, MoE, truncated, malformed, huge-line, and window-boundary corpora of section 4.1.
7. The owner `scripts/run-expert-trace-smoke` and `make expert-trace-smoke`, and the opt-in
   qualification `scripts/run-expert-trace-parity` (section 4.4).
8. One checked-in **format-fidelity fixture** captured from the real instrument on this host, whose
   provenance, command, and sanitization are recorded in section 4.3.

### 1.3 Non-goals

- **No inference, no model, no GGUF read.** R2A links no runtime, loads no weights, and opens no
  `.gguf`. Its single input is a text file. `bytes_read` is bounded by the transcript size and
  nothing else.
- **No transcript acquisition.** R2A does **not** invoke `llama-eval-callback`. The CLI consumes a
  file that already exists. This is the decision that keeps the `command.run()` whole-stdout
  limitation of section 5.5 non-blocking, and it is deliberate rather than incidental.
- **No residency decision, no cache policy, no scoring.** R2A measures reuse. Choosing a tier,
  an eviction rule, a prefetch group, or a cache score is R3 and `docs/specs/align-llm.md`
  section 7.4. R2A assigns no tier to any expert. Section 5.4.
- **No model-architecture claim.** A transcript contains node names, not `general.architecture`.
  R2A reports the *graph shape class* it observed and refuses to name a model architecture from it.
  Section 2.5.4 argues this rather than assuming it.
- **No language, task, or repository stratification.** Section R2's "language別偏り", "task別偏り",
  and "repo別偏り" each need many transcripts and a labelling scheme. R2A produces the per-transcript
  document those comparisons are computed *from*. Section 5.1.
- **No patch to llama.cpp.** R2c owns that, and section 5.2 states exactly what it would have to
  change and why R2A's document is the thing that proves the patch is needed.
- **No decode-phase claim on this host.** Section 2.2, finding 7, records that build 10566's
  `llama-eval-callback` performs exactly one graph evaluation per invocation, so an unpatched
  transcript from this host contains prefill only. R2A parses a multi-graph transcript correctly;
  it does not pretend one exists here.
- **No MoE model download.** No MoE GGUF is present on this host and this capability fetches none.
  Section 4.5 names the decision the user owns.

### 1.4 Gate statement

The roadmap gate for R2 is *条件付き局所性が存在するか、数値で判断できること* — that conditional
locality can be judged numerically. **R2A cannot discharge that gate, and claiming otherwise would
be the exact failure `CLAUDE.md` warns about.** It discharges the part it owns and names the rest:

1. **Discharged — parser and aggregate correctness.** `make expert-trace-smoke` proves, with no
   model and no network, that the grammar of section 2.2 is parsed exactly, that every error code of
   section 2.6 fires on its own fixture, that a MoE transcript with generator-known expert ids
   round-trips to the exact selections, and that every locality aggregate matches an independently
   computed Python value.
2. **Discharged — real-instrument format fidelity.** The section 4.3 fixture is real output from
   build 10566 on this host, and the smoke parses it and asserts `moe.present: false` with the exact
   node families, layer count, and token count that run produced.
3. **NOT discharged — the measurement itself.** There is no MoE transcript, because there is no MoE
   model on this host. Until one exists, `moe.present` is `false` on every real input, every
   locality aggregate is `null`, and **the R2 roadmap gate stays open.** Section 4.5 names the one
   user decision — download a small MoE GGUF — that closes it, and section 4.4's parity
   qualification is the thing that would then run.

R2A's honest terminal state is therefore: *the instrument is understood and the parser is correct;
the number the gate asks for does not exist yet.* That is a checkpoint worth shipping, because the
parser is the long pole and because section 2.2's findings materially change what R2b and R2c must
do — but it is not the gate.

## 2. Public-contract ledger

### 2.1 Verified Align surface at pin `4b515f8d`

R2A consumes **no** surface R0, R1, or R1B did not already prove. The rows below are the ones it
leans on hardest, each with the in-repository evidence that it works at the pin.

| Surface | Status at the pin | Consequence for R2A |
| --- | --- | --- |
| `fs.open_rw(path) -> Result<file, Error>`, `f.pread(b: mut buffer, off: i64)`, `f.len()` | **Shipped.** `src/gguf.align:288-360` is the working windowed reader; `docs/align-requests.md` Request 21 records the surface verbatim and the writable-path precondition | The line reader of section 2.4 is the same handle, the same `pread`, the same `bytes_read` accounting |
| `buffer(capacity)`, `window.bytes()`, `view.u8(i)`, `window.append(tail.bytes())` | **Shipped.** `src/gguf.align:302-330, 375-380` | Byte-level newline scanning needs no new codec surface |
| `array<i64>` field indexed through a `borrow` record parameter | **Shipped.** `docs/specs/r1-qwen-model-ir.md` section 7 item 1; every `GgufTable` and `BlockPlan` accessor | The selection table of section 2.7 is five parallel `array<i64>` Copy columns |
| `array_builder<i64>` as a `borrow mut` parameter | **Shipped.** Same item 2 | Columns accumulate across helper boundaries and are frozen once |
| Owned `string` sliced through a `borrow` record parameter (`t.names[a..b]`) compared against a `str` | **Shipped.** Same item 1; `src/model_ir.align:96-100` | The node-name stream is addressed by explicit `[start, end)` spans |
| `s.find(needle) -> Option<i64>` used as `... else default`, `.rfind`, `.starts_with`, `.contains`, `.trim`, `[a..b]` slicing, `.len()` | **Shipped.** `src/failure_memory.align:77, 219-246`; `src/patch_eval.align:246-266` | Header-line field extraction needs no regex and no new surface |
| `s.split(...)` | **NOT available.** Align ships `split` only as a `regex` method; the `str` form is unimplemented at this pin | The header parser composes `find` + `[a..b]` explicitly, which it would do anyway: finding 2 shows a name may contain the space a naive split would cut on |
| Hand-rolled decimal integer parse | **Necessary, not preferred.** Align has **no** `str`-to-number surface at all at this pin — no `parse_int`, no `parse_i64`, no `parse_f64`. The three existing call sites (`src/main.align:71`, `src/failure_memory.align:176`, `src/c6f1_request11_adoption.align:6`) do not hand-roll one: each is a two-line `json.decode` detour, which is the escape hatch this gap forces | R2A cannot take that detour — `12.0000` is not a JSON integer and an expert id must not be routed through a float — so it writes the one genuine private parser, bounded, over `window.bytes()`. Section 2.2 finding 5 at least removes any need for a *float* parse. The gap is genuine; section 5.5.2 states it and `docs/align-requests.md` Request 26 records it |
| `sort()` over `array<i64>` | **Shipped.** `docs/specs/r1-qwen-model-ir.md` section 2.7 | The per-graph node-name index and the per-layer expert histogram each sort once |
| `builder` local + `to_string()` move-out; owned-`string`-returning render helpers | **Shipped.** `src/model_ir.align`; Request 24 stays unconsumed | The renderer is the same shape as `model_ir`'s and passes no `builder` across a boundary |
| `Result<T, Error>`, `Option<T>`, `match`, integer `as` | **Shipped**, unchanged | unchanged |

**No `PROPOSED` request is consumed.** Requests 21–24 remain `PROPOSED` and unconsumed:

- **Request 21** (`fs.open_ro`): inherited unchanged and **strengthened**. R2A opens a transcript it
  never writes, so it asks the kernel for `O_RDWR` on a second class of read-only input. A transcript
  captured into a root-owned or read-only artifact directory — which is exactly where a CI-produced
  trace would live — cannot be opened at all. This is new client evidence for an existing request,
  not a new request; recording it in Request 21 is a documentation follow-on for the implementation
  commit.
- **Request 22** (indexing arrays of Move elements): unconsumed. R2A holds no `array<string>`. The
  node-name stream repeats the `GgufTable` / `BlockPlan` shape for the same reason.
- **Request 23** (huge-struct-copy warning on `borrow` parameters): unconsumed, and R2A is a **third**
  client. Its `TranscriptScan` record is another wide stream-plus-columns record read through
  `borrow` accessors, so the same spurious warning fires. Additional evidence for an existing
  request; no status change.
- **Request 24** (`builder` as a `borrow mut` parameter): unconsumed. The renderer returns owned
  `string`s, exactly as `model_ir` does.

**Genuine gaps are recorded, not worked around.** Section 5.5 states the two the plan already
foresaw: the `command.run()` whole-stdout limitation as Request 25, and the absent `str`-to-number
surface as Request 26. Implementation added two more, recorded in section 7.5 and shipped to the
register: Request 27 (string *sorting* — the ordering is shipped, the sort is not) and Request 28
(a readable append-only accumulator). All four are **non-blocking for R2A** — 25 by construction,
because the CLI consumes a file; 26 because a private parser is writable; 27 because `sort_spans`
is; 28 because a `buffer` is readable while it grows. This document does not edit
`docs/align-requests.md`; the orchestrator owns the register edits, and they are done.

### 2.2 Verified instrument grammar at llama.cpp build 10566

Everything in this section was measured on this host, not read from upstream source. It is the
parsing contract of section 2.6, and every claim below names how it was established.

**Instrument identity.**

```text
$ /opt/homebrew/bin/llama-eval-callback --version
version: 0.2.0 (build 10566, commit bb4caa754)
built with AppleClang 21.0.0.21000101 for Darwin arm64
```

**Capture command** (the one the section 4.3 fixture and every finding below come from):

```text
llama-eval-callback -m MODEL.gguf -p "Write a function" -n 1 -t 4 > transcript.txt 2> log.txt
```

`--no-warmup` is **rejected** by this build's argument parser (`error: invalid argument:
--no-warmup`); the warmup run does not reach the callback and needs no suppression.

**Finding 1 — the header line has exactly one format string, and it is the whole contract.**
The only producer is `common_debug_cb_eval` in `common/debug.cpp`, and its format string is present
verbatim in `libllama-common.0.2.0.dylib`:

```text
%s: %24s = (%s) %10s(%s{%s}, %s}) = {%s}
```

with the source-operand helper `%s{%s}`. This yields, for every callback line:

```text
common_debug_cb_eval:<space><name right-aligned in 24><space>=<space>(<type>)<space><op right-aligned in 10>(<src0>{<dims>}, <src1>{<dims>}}) = {<dims>}
```

The doubled `}` before `)` is not a typo: the helper renders `src1{dims}` and the outer format adds
its own `}`. When `src1` is absent the helper yields the empty string and the line reads `, })`.
Field widths were confirmed by measurement over all 958 callback lines of one run: the name field is
`%24s` (padding-plus-name is 25, 26, 29, or 30 including the format's own separating space, never
less than 25) and the op field is `%10s`.

**Finding 2 — node names contain spaces and parentheses.** `Qcur-0 (view) (permuted)` and
`cache_v_l0 (view)` are real names. A parser must not split the header on whitespace. The observed
name character set over one run is `[A-Za-z0-9_()\- ]`. Source-operand names additionally carry a
backend prefix — `MTL0#embd#0`, `MTL0#leaf_398#0` — so `#` appears inside the argument field.

**Finding 3 — the layer index is a `-N` suffix on the node name, not a `blk.N.` prefix.** llama.cpp's
`cb(cur, "name", il)` appends `-il`. The complete family set observed for the dense qwen2 model, with
occurrence counts for a 28-layer model, is:

```text
per-layer (suffix -0 .. -27):
  attn_norm-N 28   Qcur-N 112   Kcur-N 112   Vcur-N 84    norm-N 56
  kqv_out-N 28     ffn_inp-N 28 ffn_norm-N 28 ffn_gate-N 28 ffn_up-N 28
  ffn_swiglu-N 28  ffn_out-N 28 l_out-N 28
whole-graph (no suffix):
  embd 1   norm 1   result_norm 1   result_output 1
unnamed graph nodes:
  node_NNN (ggml's fallback name; 44 in this run)
```

`n_layer` is therefore recoverable as `max(N) + 1` over every suffixed family, and R2A derives it
that way. Operations observed: `MUL_MAT` 197, `ADD` 140, `RESHAPE` 112, `VIEW` 84, `RMS_NORM` 57,
`MUL` 57, `ROPE` 56, `FLASH_ATTN_EXT` 28, `PERMUTE` 28, `SWIGLU` 28, `GET_ROWS` 3. Types observed:
`f32` 790, `f16` 168.

**Finding 4 — the MoE node names are present in this build's `libllama` and follow the same
convention.** `ffn_moe_topk`, `ffn_moe_probs`, `ffn_moe_logits`, `ffn_moe_weights`,
`ffn_moe_argsort`, `ffn_moe_gate`, `ffn_moe_up`, `ffn_moe_down`, `ffn_moe_out`, and the rest of the
family are all string constants in `libllama.0.2.0.dylib`. With the `-il` suffix rule of finding 3,
the node R2A keys on is exactly **`ffn_moe_topk-N`**, and `ggml_top_k(probs, n_expert_used)` gives
it shape `{n_expert_used, n_tokens, 1, 1}`. This is verified as *present in the build*; it is not
verified *in a transcript*, because no MoE model exists here. Section 3.2 marks every cell that
depends on it, and section 4.5 names the decision that would close them.

**Finding 5 — every element prints through `%12.4f`, including integer tensors.** `%12.4f` is the
**only** element format string in the entire `libllama-common` library (verified by exhaustive
`strings` match against `^%1?[0-9]*(\.[0-9]+)?[dfiu]$`). An `I32` tensor such as `ffn_moe_topk` is
therefore printed as a decimal float, and an expert id 12 appears as `     12.0000`.

This is the single most consequential grammar fact for R2A, and it is why the selection parser is
specified as: trim, require the text to match `-?<digits>.<digits>`, reject a leading `-`, require
the fractional part to be all `0`, and parse the integral part with the bounded integer parse of
section 2.1. **No float parse is needed and none is used**, which removes an entire class of
rounding question from a value that must be an exact array index. A `nan`, an `inf`, or a non-zero
fraction is `R2_EXPERT_ID_NOT_INTEGRAL` and never a rounded id.

**Finding 6 — the value block has exactly nine line shapes and three truncation markers, and the
truncation rule is `min(ne, 6)` with a three-plus-three split.** The complete set of block-structure
strings in the library is:

```text
    [                 open axis 3
        ...,          axis-2 truncation marker (trailing space is significant)
        [             open axis 2
            ...,      axis-1 truncation marker (trailing space is significant)
            [         open axis 1 (start of a row)
   ...,               axis-0 truncation marker (inline, inside a row)
  ],                  close a row
        ],            close axis 2
    ]                 close axis 3
    sum = %f          the block terminator
```

Measured over one run across twelve distinct shapes: an axis of extent 4 or 5 prints in full, and an
axis of extent 28, 256, or 119040 prints exactly six entries with the marker between the third and
the fourth. The rule is therefore **`printed = ne` when `ne <= 6`, else `printed = 6` as
`{0, 1, 2, ne-3, ne-2, ne-1}`**. Every callback line in every run was followed by exactly one
`    sum = ` line (958 of 958).

The rule is verified for axes 1 and 2 on this host. For axis 0 every observed extent exceeded six,
so the `ne <= 6` branch on axis 0 is an **inference from the single shared loop shape**, and section
3.2 records it as a cell the MoE prerequisite closes. It matters: for a model with
`n_expert_used = 4` the expert-id row prints in full, and for `n_expert_used = 8` it prints ids
`{0, 1, 2, 5, 6, 7}` and hides two.

**Finding 7 — build 10566's `llama-eval-callback` performs exactly one graph evaluation per
invocation, and `-n 1` does not add a decode step.** Two runs (5-token and 3-token prompts) each
produced exactly one `embd` node and exactly one `result_output` node, and the last-token reduction
`node_946 = GET_ROWS(l_out-26{3584, 5, 1, 1}, ...) = {3584, 1, 1, 1}` happens *inside the same
graph*. An unpatched transcript from this build is therefore **prefill only**, with `n_tokens` equal
to the whole prompt length.

Combined with finding 6, this bounds what R2a can observe from one unpatched invocation: **at most
six token positions per layer, all in prefill, from one graph.** That is the finding that decides
R2b's acquisition strategy and justifies R2c, and section 5.1 and section 5.2 carry it forward.

**Finding 8 — the callback writes to stdout and the logs to stderr, and the build string is in
neither.** Callback lines are unprefixed on stdout; llama.cpp's logger writes timestamped lines
(`0.02.233.039 I system_info: ...`) to stderr. A transcript captured with `2>&1` therefore
interleaves log lines with the callback stream. **No build identifier appears in either stream at
default verbosity**, so `run.instrument.build` is nullable by design (section 2.5.2) and the owner
harness of section 4.2 prepends `--version` output explicitly rather than hoping for it.

**Finding 9 — sizes.** A 5-token prompt against `qwen2.5-coder-7b-instruct-q4_k_m.gguf` produced
21,110 lines and 1,487,718 bytes; a 3-token prompt produced 16,633 lines and 1,101,250 bytes. Both
contain 958 callback blocks, because the graph shape does not depend on the token count. Per-line
cost is roughly 70 bytes and the per-block line count is roughly 22. Extrapolating finding 7's
one-graph shape to a patched multi-graph capture, a thousand decode steps of a 24-layer MoE model is
on the order of hundreds of megabytes — which is the whole reason section 2.4 refuses a whole-file
read.

### 2.3 CLI surface

```text
main --expert-trace CALLBACK_LOG              # document to stdout, and nothing else
main --expert-trace CALLBACK_LOG OUT.json     # document to OUT.json, plus the summary block
```

The grammar, arity rules, `MAX_PATH_BYTES` guard, byte-identical-document requirement across the two
forms, and exit mapping are `--model-ir`'s, reused verbatim rather than re-invented
(`src/main.align:529-600`): exit `0` on `status: "ok"`, `Err(Error.Invalid)` on `status: "error"`,
and arity checked before any path or file work so an arity failure produces no output at all. The
`MAX_PATH_BYTES` guard covers **both** operands — an empty, over-long, or NUL-bearing `CALLBACK_LOG`
*or* `OUT.json` is `Err` with no output and no scan (section 2.6 step 2, section 6 item 18).

**Precondition: the transcript must be writable by the invoking user.** `src/expert_trace.align`
opens it with `fs.open_rw`, the only random-access `file` constructor Align ships at this pin, so a
transcript in a root-owned or read-only artifact directory — the ordinary home of a CI-produced
trace — is refused by the kernel with `EACCES` before a byte is read, and the arm exits nonzero with
no document. This is the R0 model-path precondition applied to a second class of read-only input;
`docs/align-requests.md` Request 21 records it, and `read-only-transcript` asserts it.

There is **no `--build` flag, no `--arch` flag, and no `--strict` flag.** A build flag would be a
second source of truth for a fact the transcript either states or does not (finding 8), and a
mismatch between the two would need an error code of its own. An architecture flag would invite
exactly the model-architecture claim section 2.5.4 refuses. A strict flag would make the fail-closed
contract optional, which is the opposite of what section 1.1 argues for.

**There is no acquisition verb.** `--expert-trace` does not run the instrument. Section 1.3 and
section 5.5 record why.

The two-operand summary block, in this exact order:

```text
expert trace:
status:            OK | ERROR
graphs:            <integer>
layers:            <integer>
tokens observed:   <integer>
tokens total:      <integer>
moe:               YES | NO
experts:           <integer or ->
experts used:      <integer or ->
selections:        <integer>
reuse:             <integer per mille, or ->
error:             <code>          # only when status is ERROR
detail:            <identifier>    # only when status is ERROR
```

`reuse` is printed as an integer per mille rather than a decimal, because the summary block is a
stable stdout contract and this repository has no float formatting contract; the JSON document
carries the same value as an exact numerator/denominator pair (section 2.5.7) and is the
authoritative result. `-` is reserved for a value the transcript does not supply, reusing the R0
convention rather than inventing a second one.

### 2.4 The streaming decision

**The constraint.** The input is a text file of unbounded size whose useful content is a small
fraction of its bytes: 958 header lines out of 21,110, and for a MoE transcript only the
`ffn_moe_topk-N` blocks matter at all. Align at this pin offers three ways to read it.

**Option A — `fs.read_bytes_view` / whole-file read.** One owned `string` or one arena mapping of
the whole transcript, then `str.find("\n")` in a loop. It is the shortest code and it is what
`src/failure_memory.align:77` does for a small document. It is rejected for the same reason
`docs/align-requests.md` Request 21 rejects mapping a 4.68 GB model for a 5 MB read: it commits the
entire size for a scan, and `draft.md:2897` records that concurrent truncation of a mapped file
raises `SIGBUS` with no handler installed. A transcript is exactly the kind of file another process
is still appending to.

**Option B — `fs.open` sequential `reader`.** A cursorless sequential reader would suit a pure
forward scan, but it offers no `pread` and no offset, so a diagnostic that must report *where* a
grammar failure occurred cannot name a byte offset, and the `bytes_read` accounting R0 established
has no anchor. Rejected: the error contract of section 2.6 depends on byte offsets.

**Option C — chosen: the `src/gguf.align` windowed reader, extended with line reassembly.**
`fs.open_rw` + `f.len()` + a `WINDOW_BYTES` buffer + `f.pread` at an explicit offset is already the
proven idiom at this pin, it already accounts `bytes_read` as the exact sum of the counts `pread`
returned, and it already fails closed on a short read rather than mistaking it for EOF
(`src/gguf.align:288-330`).

The one thing `gguf.align`'s `ensure(handle, window, c, n)` cannot do is serve a caller that does not
know `n` in advance, which is exactly a line reader's situation. R2A therefore adds one function
beside it rather than changing it:

```text
next_line(handle, window, c) -> Result<LineSpan, Fault>

  1. If the window already holds a `0x0A` at or after `c.pos`, return the span
     [c.pos, newline) and advance `c.pos` past the newline. No syscall.
  2. Otherwise refill the window at `c.pos` and rescan.
  3. If the refilled window is full and still holds no newline, grow the window
     by doubling — capped at MAX_LINE_BYTES — and refill again at `c.pos`.
  4. If the window has reached MAX_LINE_BYTES with no newline, fail
     `R2_LINE_TOO_LONG` with `c.pos` as the detail.
  5. At end of file with a non-empty residue and no trailing newline, return the
     residue as a complete final line. A transcript need not end in a newline.
```

Because the window is always refilled **at the start of the unconsumed line**, a line never spans two
windows: reassembly is achieved by re-reading, not by concatenating, and no partial-line buffer
exists to get wrong. The cost is at most one extra `pread` per window boundary, which for a 1 MiB
window and 70-byte lines is one in roughly fifteen thousand lines. `bytes_read` counts the re-read
bytes honestly, so the section 4.6 bound is stated against transcript size times a small constant
rather than against transcript size exactly.

**No line is ever materialized as an owned `string` unless it is kept.** Header parsing works on the
byte view (`window.bytes()` + `view.u8(i)`), and only the node-name substring of a header the parser
decided to keep is appended to the name stream. A value row is scanned in place and produces at most
six integers.

**Bounds.** Every one of these is a named constant in `src/expert_trace.align`, checked before the
work it protects, in non-wrapping form, following `src/model_ir.align`'s rule 2:

| Constant | Value | Why this value |
| --- | --- | --- |
| `WINDOW_BYTES` | `1048576` | Identical to `src/gguf.align:25`; one value, one tuning story |
| `MAX_LINE_BYTES` | `65536` | Real lines are ~70 bytes and the widest observed is under 200 (finding 1). 64 KiB is three orders of magnitude of headroom and still a hard stop against a binary file fed in by mistake |
| `MAX_TRANSCRIPT_BYTES` | `68719476736` | 64 GiB. Finding 9 puts a thousand-step MoE decode trace in the hundreds of megabytes; 64 GiB admits a two-order-of-magnitude larger capture and still leaves `i64` arithmetic nowhere near wrapping |
| `MAX_LINES` | `1073741824` | 2^30. At the measured ~70 bytes per line this is reached at roughly 70 GB, so `MAX_TRANSCRIPT_BYTES` normally binds first; the line cap exists so the scan loop terminates on a pathological file of empty lines |
| `MAX_GRAPHS` | `65536` | One graph is one decode step (finding 7). 65,536 steps is far beyond any trace R3 needs and bounds the per-graph column set at 512 KiB per column |
| `MAX_NODES_PER_GRAPH` | `8192` | The measured dense graph has 958 nodes; a 120B MoE graph is a few thousand. 8,192 bounds the per-graph name index at 64 KiB |
| `MAX_LAYERS` | `1024` | Matches the `n_layer` plausibility bound the R1 frontends already use |
| `MAX_EXPERTS` | `1024` | Identical to `src/frontend_gpt_oss.align`'s `MAX_EXPERTS`; the two documents describe the same experts |
| `MAX_EXPERTS_USED` | `64` | `n_expert_used` is 4 for gpt-oss and 8 for the widest shipped MoE; 64 is generous and keeps a selection row narrow |
| `MAX_TOKENS_PER_GRAPH` | `1048576` | A batch axis bound. Only `min(n_tokens, 6)` are ever *observed* (finding 6), so this bounds the reported total, not the stored rows |
| `MAX_SELECTIONS` | `1048576` | The real memory bound: five `array<i64>` columns at 8 MiB each, 40 MiB total. Finding 6 caps observations at `6 * n_layer * n_expert_used` per graph, so for a 24-layer 4-slot model this admits over 1,800 graphs of prefill or over 10,000 decode steps |
| `MAX_REUSE_WINDOW` | `64` | The largest working-set window reported (section 2.5.7) |
| `MAX_NAME_BYTES` | `256` | A node name is a `%24s` field; 256 is a fail-closed stop, not a target |
| `MAX_DETAIL_BYTES` | `256` | Identical to `src/model_ir.align:26` |

### 2.5 Exchanged document — `R2_ACTIVATION_TRACE`, `schema_version: 1`

#### 2.5.1 Top level

```json
{
  "schema_version": 1,
  "kind": "R2_ACTIVATION_TRACE",
  "path": "traces/qwen-prefill.txt",
  "status": "ok",
  "error_code": "",
  "error_detail": "",
  "source": {},
  "run": {},
  "graph": {},
  "moe": {},
  "graphs": [],
  "selections": [],
  "locality": {}
}
```

| Field | Type | Contract |
| --- | --- | --- |
| `schema_version` | integer | Always `1` for this document version |
| `kind` | string | Always `"R2_ACTIVATION_TRACE"` |
| `path` | string | The `CALLBACK_LOG` operand verbatim, JSON-escaped. Never normalized, never absolutized |
| `status` | string | `"ok"` or `"error"`. No third value |
| `error_code` | string | `""` when `status` is `"ok"`; otherwise exactly one code from section 2.6 |
| `error_detail` | string | `""` when `status` is `"ok"`; otherwise a bounded, JSON-escaped identifier — a node name, a byte offset, or a bounded escaped line prefix. Never free prose and never a file path |
| `source` | object | Section 2.5.2. Always present |
| `run` | object | Section 2.5.3. Always present |
| `graph` | object | Section 2.5.4. Always present, with `-1` / `null` sentinels for anything not derived |
| `moe` | object | Section 2.5.5. Always present; `{"present": false, ...nulls}` for a dense transcript |
| `graphs` | array | Section 2.5.6, one entry per graph evaluation in transcript order. `[]` when segmentation was not reached |
| `selections` | array | Section 2.5.6, in observation order. `[]` for a dense transcript, and `[]` on an error before the MoE pass |
| `locality` | object | Section 2.5.7. Every aggregate is `null` when `moe.present` is `false` |

On `status: "error"` the document is still written and every value derived before the failure is
present and truthful, mirroring R0's failure-persistence behavior and R1's section 2.5.1. This is
what makes a transcript from an unrecognized build *diagnosable* — the reader gets the offset, the
offending line prefix, and the graph and node counts that parsed cleanly before it.

#### 2.5.2 `source`

```json
"source": {
  "file_size": 1487718,
  "line_count": 21110,
  "bytes_read": 1495040,
  "callback_line_count": 958,
  "skipped_line_count": 0
}
```

`file_size` is `f.len()` at open. `bytes_read` retains its R0 definition — the exact sum of the
counts every `pread` returned — and exceeds `file_size` by at most one window per line-boundary
re-read (section 2.4). `skipped_line_count` counts lines outside any value block that matched no
recognized shape: finding 8's interleaved stderr logs land here, and a nonzero value on a
stdout-only capture is a signal worth seeing rather than an error.

#### 2.5.3 `run`

```json
"run": {
  "instrument": "llama-eval-callback",
  "build": 10566,
  "build_source": "transcript",
  "contract_build": 10566,
  "build_matches_contract": true,
  "version_line": "version: 0.2.0 (build 10566, commit bb4caa754)"
}
```

| Field | Type | Contract |
| --- | --- | --- |
| `instrument` | string | Always `"llama-eval-callback"`. The document names what it was designed against, not what produced it |
| `build` | integer or `null` | The build number from a `version: ... (build N, ...)` line if the transcript carries one. `null` otherwise, which is the default case (finding 8) |
| `build_source` | string | `"transcript"` or `"absent"`. Never `"assumed"` |
| `contract_build` | integer | Always `10566`. The build this parser's grammar was derived from |
| `build_matches_contract` | boolean or `null` | `null` when `build` is `null` |
| `version_line` | string or `null` | The verbatim, JSON-escaped, `MAX_DETAIL_BYTES`-bounded line |

**A build mismatch is recorded, never an error.** The parsing contract is enforced by the grammar
codes of section 2.6, which fire on what the transcript actually contains. Refusing a transcript
because a version line says 10567 would fail on a build whose print format never moved, and — worse
— would pass a build whose format *did* move but which omits the version line. The grammar is the
check; the build number is provenance.

#### 2.5.4 `graph`

```json
"graph": {
  "graph_count": 1,
  "n_layer": 28,
  "node_families": ["Kcur", "Qcur", "Vcur", "attn_norm", "ffn_gate", "ffn_inp",
                    "ffn_norm", "ffn_out", "ffn_swiglu", "ffn_up", "kqv_out",
                    "l_out", "norm"],
  "unsuffixed_nodes": ["embd", "norm", "result_norm", "result_output"],
  "ops": ["ADD", "FLASH_ATTN_EXT", "GET_ROWS", "MUL", "MUL_MAT", "PERMUTE",
          "RESHAPE", "RMS_NORM", "ROPE", "SWIGLU", "VIEW"],
  "shape_class": "dense-ffn",
  "shape_class_basis": "ffn_gate/ffn_up/ffn_swiglu present, ffn_moe_topk absent"
}
```

| Field | Type | Contract |
| --- | --- | --- |
| `graph_count` | integer | Graph evaluations segmented from the transcript; `0` when segmentation was not reached |
| `n_layer` | integer or **`null`** | `max(N) + 1` over every `-N` suffix observed (finding 3). **`null`** — never a sentinel — when the transcript carries no suffixed node at all, which is what a six-block excerpt, a capture that began mid-graph, and a transcript with no callback line each produce (section 6, item 17) |
| `node_families` | array of string | The distinct `-N` family prefixes, sorted byte-lexicographically and de-duplicated |
| `unsuffixed_nodes` | array of string | The distinct names carrying no `-N` suffix, same ordering |
| `ops` | array of string | The distinct operation names, same ordering |
| `shape_class` | string | `"dense-ffn"`, `"moe-ffn"`, or `"unknown"` |
| `shape_class_basis` | string | The evidence for `shape_class`, in every case |

`node_families` and `ops` are sorted, de-duplicated, and bounded at `MAX_NODES_PER_GRAPH` entries.

**`shape_class` is a graph shape class, not a model architecture.** Its closed value set is
`"dense-ffn"`, `"moe-ffn"`, and `"unknown"`, selected solely by the presence of `ffn_moe_topk-N` and
of the dense feed-forward families, with `shape_class_basis` naming the evidence in every case. A
transcript contains node names; it does not contain `general.architecture`. Reporting `"qwen2"` from
a graph that is merely qwen2-shaped would repeat the `general.file_type` mistake
`docs/specs/r1-qwen-model-ir.md` section 2.5.4 refuses to make, and it would be wrong for every model
that shares a graph shape. The authoritative architecture is the one `R1_MODEL_IR` decodes from the
container, and joining the two documents is R2b's job (section 5.1), not a guess R2A makes alone.

#### 2.5.5 `moe`

```json
"moe": {
  "present": false,
  "n_expert": null,
  "n_expert_used": null,
  "n_expert_source": null,
  "topk_layers": [],
  "slots_truncated": false
}
```

| Field | Type | Contract |
| --- | --- | --- |
| `present` | boolean | `true` if and only if at least one `ffn_moe_topk-N` block parsed successfully |
| `n_expert` | integer or `null` | Axis 0 of `ffn_moe_probs-N` when present, else axis 0 of `ffn_moe_logits-N`, else axis 1 of the router weight operand of the `MUL_MAT` producing `ffn_moe_logits-N`, else `null`. `ffn_moe_topk` cannot supply it |
| `n_expert_used` | integer | Axis 0 of `ffn_moe_topk-N`, required to be identical on every layer of every graph |
| `n_expert_source` | string or `null` | `"ffn_moe_probs"`, `"ffn_moe_logits"`, `"router_weight"`, or `null`. Which rule was applied, in the `head_dim_source` tradition of R1 |
| `topk_layers` | array of integer | Ascending layer indices with at least one parsed `ffn_moe_topk` block |
| `slots_truncated` | boolean | `true` when `n_expert_used > 6`, so slot ids `3 .. n_expert_used-4` were never printed (finding 6) |

A dense transcript reaches this object with `present: false` and every other field at its `null` or
empty sentinel, and `status` stays `"ok"`. That is section 1.2 item 5, and it is the shape of every
document this host can produce today.

#### 2.5.6 `graphs` and `selections`

```json
"graphs": [
  {
    "ordinal": 0,
    "n_tokens": 5,
    "phase": "prefill",
    "tokens_observed": 5,
    "tokens_truncated": false,
    "observed_token_indices": [0, 1, 2, 3, 4],
    "node_count": 958
  }
]
```

| Field | Type | Contract |
| --- | --- | --- |
| `ordinal` | integer | Position in the transcript, from `0` |
| `n_tokens` | integer | Axis 1 of `embd`, cross-checked against axis 1 of every `ffn_moe_topk-N` in the same graph |
| `phase` | string | `"prefill"` when `n_tokens > 1`; `"decode"` when `n_tokens == 1` and `ordinal > 0`; `"single_token_first_graph"` when `n_tokens == 1` and `ordinal == 0` |
| `tokens_observed` | integer | `min(n_tokens, 6)` (finding 6) |
| `tokens_truncated` | boolean | `n_tokens > 6` |
| `observed_token_indices` | array of integer | `[0 .. n_tokens-1]` when not truncated, else `[0, 1, 2, n_tokens-3, n_tokens-2, n_tokens-1]` |
| `node_count` | integer | Callback blocks in this graph |

**`phase` has three values and not two.** A first graph of one token is genuinely ambiguous: it is
what a one-token prompt's prefill looks like and what a decode step looks like, and the transcript
carries nothing that separates them. Collapsing it into `"decode"` would let a single-token prompt
masquerade as decode evidence in exactly the prefill-versus-decode comparison section R2 asks for.

**A graph boundary is a repeated node name.** ggml node names are unique within one graph, so the
first callback line whose name is already in the current graph's name index opens the next graph.
The index is the packed-hash ascending `array<i64>` of `src/model_ir.align:60-66`, bounded at
`MAX_NODES_PER_GRAPH`. This is stated rather than assumed because finding 7 means the only
transcripts available here have exactly one graph, so section 4.1 owns a concatenated multi-graph
fixture and section 3.2 marks the cell.

```json
"selections": [
  {"graph": 0, "layer": 3, "token": 0, "slot": 0, "expert": 12},
  {"graph": 0, "layer": 3, "token": 0, "slot": 1, "expert": 5}
]
```

One entry per printed element of every `ffn_moe_topk-N` block, in observation order: graph ordinal,
layer, exact token index (recovered through finding 6's three-plus-three rule, so a truncated axis
still yields *exact* indices for the six it printed), slot ordinal within `n_expert_used`, and the
expert id parsed by finding 5's integral rule. Bounded at `MAX_SELECTIONS`.

Exactness of `token` under truncation is what makes section 5.1's multi-transcript union possible,
and it is why the design records a token index rather than a row ordinal.

#### 2.5.7 `locality`

```json
"locality": {
  "adjacent_pair_count": 0,
  "reuse_numerator": null,
  "reuse_denominator": null,
  "reuse_per_mille": null,
  "per_layer": [],
  "working_set": [],
  "phase_split": {"prefill": null, "decode": null}
}
```

Every aggregate is computed **only over adjacent observed token pairs** — pairs of token indices
differing by exactly one, within one graph and one layer. Truncation breaks adjacency in the middle
of a long prefill, and pretending otherwise would silently compare token 2 against token `n-3`.

| Field | Contract |
| --- | --- |
| `adjacent_pair_count` | Total adjacent pairs the aggregates were computed from. `0` means every aggregate is `null` and the gate has no answer |
| `reuse_numerator` / `reuse_denominator` | Over every adjacent pair and every layer: the number of experts selected at token `t` that are selected again at `t+1`, summed; and the number of experts selected at `t+1`, summed. Exact integers, so a consumer can re-derive any rounding it wants |
| `reuse_per_mille` | `reuse_numerator * 1000 / reuse_denominator`, integer division. The summary block's value |
| `per_layer` | One object per layer in `moe.topk_layers`: `layer`, `adjacent_pair_count`, `reuse_numerator`, `reuse_denominator`, `reuse_per_mille`, and `histogram` — an array of `[expert_id, count]` pairs over observed selections, sorted by expert id |
| `working_set` | One object per window `w` in `{1, 2, 4, 8, 16, 32, 64}` with `w <= MAX_REUSE_WINDOW`: `window`, `sample_count`, `unique_sum`, `unique_mean_per_mille`. A sample is a run of `w` consecutive adjacent observed tokens within one graph and layer; `unique` is the count of distinct expert ids across it. `sample_count == 0` yields `null` for the mean |
| `phase_split` | The same reuse triple computed separately over graphs whose `phase` is `"prefill"` and over graphs whose `phase` is `"decode"`. `"single_token_first_graph"` contributes to neither, and a `null` on either side means that phase was not observed |

**No aggregate is reported without its denominator.** This is the section 1.1 property that keeps
the R2 gate honest: a document from this host's dense model shows `adjacent_pair_count: 0` and
`null` everywhere, and no reader can mistake it for a measured zero.

### 2.6 Validation order and error codes

The first applicable row wins, lines are examined in file order, and **no document and no stdout is
produced before the whole derivation completes**. Steps 1 and 2 return `Err` and produce no document
at all; every later step produces a `status: "error"` document and then maps to
`Err(Error.Invalid)`.

1. CLI selector and exact arity. *(`src/main.align`)*
2. Path lexical validation of **both** operands against `MAX_PATH_BYTES`, plus emptiness and a NUL
   byte. *(`src/main.align`; `expert_trace.build_trace` re-checks the transcript path as the
   module's own fail-closed contract)*
3. Open, `f.len()`. The transcript must be writable by the invoking user (section 2.3); a mode
   `0444` or root-owned transcript fails here as `Error.Denied`. *(`src/expert_trace.align`)*
4. Size and emptiness bounds.
5. Line scan: line length, line count.
6. Per-line shape classification: header, value-block structure, `sum`, or ignorable.
7. Header field extraction: name, type, op, operand dims, result dims.
8. Graph segmentation and per-graph bounds.
9. Value-block structure: row and element counts against finding 6's `min(ne, 6)` rule.
10. `ffn_moe_topk` element parse and expert bounds.
11. MoE consistency across layers and graphs.
12. Selection-table and aggregate bounds.

| Code | Condition | Step | `error_detail` |
| --- | --- | --- | --- |
| `R2_TRANSCRIPT_UNREADABLE` | Open, `len`, or `pread` failed at the OS level | 3 | the Align `Error` variant name |
| `R2_TRANSCRIPT_EMPTY` | `file_size == 0` | 4 | `""` |
| `R2_TRANSCRIPT_TOO_LARGE` | `file_size > MAX_TRANSCRIPT_BYTES` | 4 | `file_size` |
| `R2_LINE_TOO_LONG` | A line reaches `MAX_LINE_BYTES` with no newline | 5 | the line's start offset |
| `R2_LINE_LIMIT` | Line count would exceed `MAX_LINES` | 5 | `MAX_LINES` |
| `R2_HEADER_GRAMMAR` | A line begins `common_debug_cb_eval:` but does not match section 2.2 finding 1 — including a NUL byte anywhere in it, which is what keeps the name stream NUL-free by construction, and including a multi-byte UTF-8 scalar where the grammar requires a specific ASCII byte (section 6, item 15) | 6, 7 | the escaped line prefix, bounded at `MAX_DETAIL_BYTES` |
| `R2_NODE_NAME_TOO_LONG` | The name field exceeds `MAX_NAME_BYTES` | 7 | the escaped prefix |
| `R2_DIMS_INVALID` | A dimension list is not exactly four non-negative integers, or a product would wrap | 7 | the node name |
| `R2_VALUE_GRAMMAR` | Inside a value block, a line matches none of finding 6's nine shapes | 6 | the line's start offset |
| `R2_SUM_MISSING` | A callback block is not terminated by a `    sum = ` line, including at end of file | 6 | the node name |
| `R2_GRAPH_LIMIT` | Graph count would exceed `MAX_GRAPHS` | 8 | `MAX_GRAPHS` |
| `R2_NODE_LIMIT` | One graph's node count would exceed `MAX_NODES_PER_GRAPH` | 8 | the graph ordinal |
| `R2_LAYER_INDEX` | A `-N` suffix parses to a value outside `[0, MAX_LAYERS)` | 7 | the node name |
| `R2_ROW_COUNT` | A block's printed row count is not `min(ne1, 6)`, or its element count is not `min(ne0, 6)`, or its axis-2 slice count is not `min(ne2, 6)` | 9 | the node name |
| `R2_TOKEN_COUNT` | `n_tokens` outside `[1, MAX_TOKENS_PER_GRAPH]`, or `embd` and an `ffn_moe_topk` in one graph disagree on it | 8, 11 | the node name |
| `R2_EXPERT_ID_NOT_INTEGRAL` | An `ffn_moe_topk` element is not `<digits>.<zeros>` — a non-zero fraction, a sign, `nan`, or `inf` | 10 | the escaped element text |
| `R2_EXPERT_BOUNDS` | `n_expert_used` outside `[1, MAX_EXPERTS_USED]`; `n_expert` outside `[1, MAX_EXPERTS]`; an expert id outside `[0, n_expert)`, or outside `[0, MAX_EXPERTS)` when `n_expert` is unknown | 10 | the node name |
| `R2_MOE_INCONSISTENT` | `n_expert_used` or `n_expert` differs between two layers or two graphs | 11 | the node name of the second observation |
| `R2_SELECTION_LIMIT` | Selections would exceed `MAX_SELECTIONS` | 12 | `MAX_SELECTIONS` |

**`R2_HEADER_GRAMMAR` and `R2_VALUE_GRAMMAR` are the parsing contract's binding to build 10566.**
They are the reason a transcript from a build whose print format moved is refused instead of
half-read. Section 2.5.3 argues why the binding is expressed as grammar codes rather than as a
version check.

**`R2_ROW_COUNT` is not defensive.** It is the check that finding 6's truncation rule actually held,
and it is the difference between recovering an exact token index and inventing one. If a future
build changes `3` to some other split, this code fires on the first block rather than producing a
document full of wrong token indices.

**Unrecognized lines outside a value block are not an error.** Finding 8's interleaved stderr logs,
a shell banner, and a trailing blank line are all counted into `source.skipped_line_count` and
ignored. Inside a value block the opposite rule holds, because there a stray line means the block
structure was misread. That asymmetry is deliberate and is closed by its own fixture (section 3.3).

### 2.7 Ownership, allocation, and owner modules

| Module | Owns | Imports |
| --- | --- | --- |
| `src/expert_trace.align` | the line reader, the transcript grammar, graph segmentation, `TranscriptScan`, `ExpertTrace`, the selection table, the locality aggregates, the whole document renderer, every `R2_*` code | `core.json`, `std.fs` |
| `src/main.align` | `--expert-trace` arity, path guard, destination, summary block, exit mapping | `expert_trace` |

`src/expert_trace.align` imports no GGUF module and no frontend. R2A's input is a text file; a
dependency on `src/gguf.align` would create a false coupling between a container reader and a log
parser and would drag the whole geometry table into a module that has no tensors. The `Cursor` /
window idiom is **reused by transcription, not by import** — this is a deliberate, recorded
duplication of roughly forty lines, on the same reasoning `docs/align-requests.md` Request 24 records
for `gguf.inspect` / `gguf.read_table`: the alternative at this pin is a shared `borrow mut`
`builder`-style abstraction Align does not admit. Section 5.5's Request 25 candidate is the general
form of this observation.

| Value | Owner | Allocation | Release |
| --- | --- | --- | --- |
| `file` handle + `window` | bare locals in `expert_trace.scan`, exactly as `src/gguf.align:75` requires | one `buffer` of `WINDOW_BYTES`, grown by doubling only for a long line, capped at `MAX_LINE_BYTES` | scope `Drop` |
| `TranscriptScan` | one local in `scan`, **moved** into `build` as a `borrow` argument's owner local | one owned `string` name stream, ten `array<i64>` columns each frozen once from an `array_builder<i64>`, and eighteen scalars | scope `Drop` after `build` returns |
| node-name index | one local per graph in `scan` | one `array<i64>`, sorted once per graph, reset at each graph boundary | scope `Drop` |
| selection table | five parallel `array<i64>` columns in `TranscriptScan` — `sel_graph`, `sel_layer`, `sel_token`, `sel_slot`, `sel_expert` | frozen once each from `array_builder<i64>`; `MAX_SELECTIONS` bounds all five at 40 MiB total | scope `Drop` |
| per-layer histogram | one local in the aggregate pass | one `array<i64>` of packed `(layer, expert, count)`, built and sorted once | scope `Drop` |
| document | one `builder` in `build` | accumulated once, in declaration order | moved out by `to_string()` |
| final document | `builder` moved out by `to_string()` | one owned `string` | **moved** into `ExpertTrace.document`, then to the caller |

The document is moved, not cloned, following `docs/specs/c8-speed-first.md` section 2.8, as
`GgufInspection` and `ModelIr` already do.

**`TranscriptScan` is the `GgufTable` / `BlockPlan` shape, third instance.** One concatenated
`names` stream addressed by explicit `[start, end)` spans plus parallel Copy columns, chosen for the
reason those two chose it: a raw node name may contain any byte a line may contain, `array<string>`
indexing is Request 22, and a span is the shape this pin proves. The NUL-free property is not
assumed — it is *enforced*, by making a NUL inside a header line `R2_HEADER_GRAMMAR` (section 2.6).

**Work stays bounded.** The scan is one forward pass, `O(file_size)` in bytes plus one extra window
read per line boundary. Graph segmentation is `O(nodes log nodes)` per graph. The aggregate pass
sorts the selection table once by `(graph, layer, token, slot)` and walks it with one cursor, so
adjacency, histograms, and every working-set window are computed in one sweep rather than one sweep
per window: `O(s log s)` in the selection count. `MAX_SELECTIONS` bounds `s`.

### 2.8 Ledger dimensions

| Dimension | Contract | Owner | Acceptance |
| --- | --- | --- | --- |
| Exact command/API | Section 2.3 (`--expert-trace`, two forms, no flags, no acquisition verb); `pub fn build_trace(path: str) -> Result<expert_trace.ExpertTrace, Error>`; `expert_trace.TranscriptScan`, `expert_trace.ExpertTrace`. No aliases | `src/main.align`, `src/expert_trace.align` | `expert-trace-smoke` CLI cases |
| Inputs and defaults | One transcript path; optional destination path. No environment input, no ambient options, no default transcript | `src/main.align` | `env-perturbation`, `cli-arity` |
| Results and errors | `Ok` + `status: "ok"`; `Ok` + `status: "error"` for every transcript defect; `Err` only for argument or OS failure. Section 2.6's table is complete and ordered | `src/expert_trace.align` | one fixture per row |
| Multi-invalid precedence | Section 2.6 is strictly ordered; within a step, file order; the first applicable row wins | ordered guards | `precedence-*` cases |
| Ownership and lifetime | Section 2.7. `TranscriptScan` and the document are moved into their sole owners; no accessor returns a view derived from a `borrow` parameter | `src/expert_trace.align` | `document-move`, ownership review |
| Allocation | Section 2.7's table; one handle, one window, one scan record, one document per invocation. Peak is `WINDOW_BYTES` plus the five selection columns | `src/expert_trace.align` | `bytes_read` bound, descriptor-budget run, `repeat-expert-trace` |
| Bounded work | One forward pass in bytes; `O(s log s)` in selections; every `MAX_*` of section 2.4 checked before the work it protects, in non-wrapping form | `src/expert_trace.align` | `bounded-work` over the huge-line and many-graph fixtures |
| Owner module | Section 2.7's table. One parser for the grammar; one renderer for the format | this document | `make check` (`check-per-unit`), import-graph review |
| Persisted/cache identity | `N/A`. R2A writes one caller-named output document and reads nothing it wrote. No cache, no digest-addressed artifact, no compiler-cache policy change | `N/A` with this reason | no cache behavior is claimed or tested |
| Schema version | **`schema_version: 1`.** Any addition, removal, reorder, or type change requires version 2. The three-valued `phase`, the closed `shape_class` set, and the exact-integer reuse triple are normative | `src/expert_trace.align` | golden document bytes; field-order assertions |
| Validation order | Section 2.6, deterministic; no output before derivation completes | `src/expert_trace.align` | ordered malformed corpus, untouched-destination assertion |
| Prerequisites | The pinned toolchain at `4b515f8d`; every consumed surface verified present (section 2.1). Requests 21–24 remain `PROPOSED`, non-blocking, unconsumed. **One capability prerequisite**: the section 4.3 format-fidelity fixture, captured and sanitized before the implementation commit. **One open prerequisite**: a real MoE transcript, which does not exist (section 4.5) | `src/expert_trace.align` | `make check`, `make build`, the recorded capture |
| Acceptance evidence | `expert-trace-smoke` for the grammar, the error corpus, and the aggregates; the section 4.3 fixture for real-instrument fidelity; `expert-trace-parity` for the R2 gate, with the section 4.4 `N/A` | section 4 | sections 4.2, 4.3, 4.4 |
| Metrics | Primary: correctness — every fixture's parsed selections and aggregates equal the generator's independently computed values, and the real fixture parses to its measured shape. Secondary: `bytes_read` bound and peak allocation. **No performance claim**; section 4.6 | section 4.6 | oracle assertions, `bytes_read` bound |
| Text/wire boundary | Canonical UTF-8 JSON in declaration order. A node name is copied to the document only after passing the header grammar; a non-UTF-8 byte in a name is `R2_HEADER_GRAMMAR` and never reaches the document. `error_detail` is escaped and bounded | `src/expert_trace.align` | `wire-escapes`, `invalid-utf8-name` |
| Runtime-inspection fields | Every field is decoded from the transcript or derived by a stated formula from decoded values, except `contract_build` (a constant naming what the parser was built against) and the `*_source` markers, which report *which rule was applied*. No reflection, no environment read, no model read | `src/expert_trace.align` | producer-provenance review, `env-perturbation` |
| Platform scope | Platform-independent text parsing. No target-local boundary changes, so this capability's own content selects no platform profile. **The `Makefile` change does select the fresh-image installed profile** — section 3.5 | `src/expert_trace.align` | `python3 scripts/pre-pr --plan` |
| Milestone ordering | R2A consumes no R2b, R2c, or R3 decision: no acquisition strategy, no runtime patch, no cache policy, no residency tier. It emits observations and their denominators | this document | section 5 |
| Normative examples | The JSON blocks of section 2.5 are declarations. The counts in them come from the real run of section 2.2 and from the section 4.3 fixture; no other extent is asserted by any test | this document | section 4.3 |

## 3. Closure matrix

Every applicable cell names its implementation owner and the exact regression that closes it. `N/A`
carries a concrete reason; `DEFERRED` is an intentional decision recorded in section 5. Regression
names are cases inside `scripts/run-expert-trace-smoke` unless another runner is named.

**`MOE-PREREQ` marks a cell whose real-input evidence does not exist on this host.** Each such cell is
closed by the synthetic corpus *and* is listed in section 4.5 as reopening the moment a MoE
transcript exists. Marking them is the section 1.4 honesty requirement made mechanical.

### 3.1 `src/expert_trace.align` — the line reader

| Case | Contract to close | Implementation | Exact regression |
| --- | --- | --- | --- |
| Construction | Handle and window are bare locals; the window is one `WINDOW_BYTES` buffer | `scan` prologue | `descriptor-budget`, `peak-allocation` |
| Success — short file | A transcript smaller than one window is read in one `pread` | `next_line` | `window-single-read`, shipped as the runner's per-fixture assertion `size <= WINDOW_BYTES` implies `bytes_read in {0, size}`, applied to every fixture rather than to one named case |
| Success — window boundary | A line straddling a window boundary is returned whole, exactly once, with correct content | `next_line` step 3 | `window-boundary`: the generator places a header line at offsets `WINDOW_BYTES - k` for `k` in `{1, 2, 40, 200}` and asserts identical documents |
| Success — no trailing newline | A final line without `\n` is a complete line | `next_line` step 5 | `no-trailing-newline` |
| Success — CRLF and blank lines | A `\r` is part of the line and is rejected by the header grammar, not silently stripped; a blank line is ignorable | grammar | `crlf-transcript`, `blank-lines` |
| Failure — long line | A line reaching `MAX_LINE_BYTES` is `R2_LINE_TOO_LONG` with its start offset | `next_line` step 4 | shipped as two cases, not one `huge-line`: `huge-line-first` (a 200,000-byte first line, detail `0`) and `huge-line-late` (the same line after 500 valid blocks, detail its exact byte offset, `callback_line_count` 501) |
| Failure — line count | `MAX_LINES` is enforced before the line is classified | scan loop guard | `line-limit`: a generated file of `MAX_LINES + 1` empty lines, run against a lowered constant in a debug fixture rather than a 70 GB file |
| Failure — OS | Missing, unreadable, or a directory is `R2_TRANSCRIPT_UNREADABLE` | `scan` prologue | `unreadable-transcript`, `directory-operand` |
| Failure — bounds | Empty and oversize are their own codes | step 4 | `empty-transcript`; `oversize-transcript` against a lowered constant |
| `bytes_read` | Counts exactly the `pread` returns, including re-reads | `refill` | `bytes-read-bound`: `file_size <= bytes_read <= file_size + line_count_at_boundaries * WINDOW_BYTES` |
| Early exit | On any failure the scan stops and the partial document reports what parsed | guard returns | `partial-scan`: a defect at line 500 of 1,000 asserts the exact `callback_line_count` |
| Cleanup | The handle closes on `Drop`; the destination is untouched on failure | scope | `untouched-destination`, `descriptor-budget` |
| Concurrency | `N/A`: read-only, no lock; no atomicity claimed for a transcript appended to during the scan. The bounded window makes a torn read a grammar error, not a crash | `N/A` with this reason | documented unsupported caller case |

### 3.2 `src/expert_trace.align` — the grammar and the selections

| Case | Contract to close | Implementation | Exact regression |
| --- | --- | --- | --- |
| Success — header fields | Name, type, op, both operands, and the result dims are extracted from a `%24s` / `%10s` line, including names with spaces and parentheses and operands with `#` | `parse_header` | `real-transcript` (section 4.3) plus `header-name-spaces`, `header-backend-prefix` |
| Success — unary operand | `, })` yields an absent `src1` and is not an error | `parse_header` | `header-unary` |
| Success — layer suffix | `-N` yields the layer; an unsuffixed name yields none; `node_946` is not read as layer 946 | `parse_layer_suffix` | `layer-suffix`: asserts `node_NNN` and `MTL0#leaf_398#0` produce no layer |
| Success — `n_layer` | `max(N) + 1` over every suffixed family | aggregate pass | `real-transcript` asserts `28` |
| Success — value structure | The nine shapes of finding 6 are classified and the block terminates on `sum` | `scan_block` | `value-shapes` over all twelve real shapes of the section 4.3 fixture |
| Success — truncation rule | Row, element, and slice counts equal `min(ne, 6)`; token indices under truncation are `{0,1,2,n-3,n-2,n-1}` | `scan_block`, `token_index_of_row` | `truncation-map`: generator emits `n_tokens` in `{1, 4, 5, 6, 7, 8, 64}` and asserts the exact index set |
| Success — axis-0 full print | An axis-0 extent `<= 6` prints in full | `scan_block` | `topk-slots-4`. **MOE-PREREQ**: verified synthetically only; finding 6 records that no real axis-0 extent under seven was observed on this host |
| Success — expert id parse | `     12.0000` yields `12`; no float parse is used | `parse_expert_id` | `expert-id-format`: every id 0..255 rendered as `%12.4f` and round-tripped |
| Success — `n_expert` source | `ffn_moe_probs` wins, then `ffn_moe_logits`, then the router weight; `n_expert_source` reports which | `derive_n_expert` | `n-expert-probs`, `n-expert-logits`, `n-expert-router`, `n-expert-absent`. **MOE-PREREQ** |
| Success — dense document | A transcript with no `ffn_moe_topk` is `status: "ok"`, `moe.present: false`, `selections: []`, `locality` all `null` | `build` | `real-transcript`, `dense-synthetic` |
| Success — graph segmentation | A repeated node name opens the next graph; ordinals, `n_tokens`, and `node_count` are per graph | `scan` | `multi-graph`: three concatenated transcripts with `n_tokens` 5, 1, 1 assert phases `prefill`, `decode`, `decode` |
| Success — phase | The three-valued rule of section 2.5.6 | `phase_of` | `phase-prefill`, `phase-decode`, `phase-ambiguous` |
| Success — aggregates | Reuse triple, per-layer histograms, working sets, and the phase split equal independently computed Python values | aggregate pass | `aggregate-oracle` (section 4.3's in-runner oracle). **MOE-PREREQ** for the non-`null` half |
| Success — adjacency | Only token pairs differing by one contribute; a truncated prefill yields `adjacent_pair_count` `4`, not `5` | aggregate pass | `adjacency-truncated`: `n_tokens = 64` asserts exactly 4 adjacent pairs |
| Failure — every error code | Each row of section 2.6 fires on its own fixture with the correct detail | ordered guards | `error-corpus`, one case per row |
| Failure — precedence | A transcript with two defects reports the earlier row | ordered guards | `precedence-line-then-header`, `precedence-header-then-rowcount` |
| Failure — grammar drift | A header with a changed field width, a missing `}`, or an unknown op shape is `R2_HEADER_GRAMMAR`, never partially parsed | `parse_header` | `grammar-drift`: five mutations of a real header line |
| Failure — value drift | A stray line inside a value block is `R2_VALUE_GRAMMAR`; the same line outside one is skipped | `scan_block` | `value-drift-inside`, `value-drift-outside` |
| Failure — row count | A block printing 5 rows for `ne1 = 28` is `R2_ROW_COUNT` | step 9 | `rowcount-mismatch` |
| Failure — expert bounds | An id `>= n_expert`, a negative id, `nan`, and a non-zero fraction each fire their row | step 10 | `expert-out-of-range`, `expert-negative`, `expert-nan`, `expert-fraction` |
| Failure — MoE inconsistency | Two layers disagreeing on `n_expert_used` is `R2_MOE_INCONSISTENT` | step 11 | `moe-inconsistent-layers`, `moe-inconsistent-graphs` |
| Failure — limits | Graph, node, and selection limits each fire against lowered debug constants | ordered guards | `graph-limit`, `node-limit`, `selection-limit` |
| Malformed — non-UTF-8 / NUL | A NUL or an invalid UTF-8 byte in a header line is `R2_HEADER_GRAMMAR`; the document stays valid JSON | `parse_header` | `invalid-utf8-name`, `nul-in-header` |
| Malformed — multi-byte UTF-8 at a computed offset | *Valid* multi-byte UTF-8 where the grammar requires a specific ASCII byte is refused as data — a recorded code and a truthful partial document — and never aborts the process. Every `str[a..b]` uses offsets an ASCII match already proved (section 6, item 15) | `parse_header`, the row classifier | `multibyte-type-close`, `multibyte-header-tail`, `multibyte-src0-separator`, `multibyte-src1-tail` (each `R2_HEADER_GRAMMAR`), `multibyte-value-row` (`R2_VALUE_GRAMMAR`) |
| Success — multi-byte UTF-8 in every field | A transcript whose names, types, operations, and operands all carry multi-byte scalars parses, interns, sorts byte-lexicographically, and renders | `scan`, `build` | `multibyte-everywhere` |
| Success — saturated token index | A token index at the top of the packed key's token field does not carry into the layer field and manufacture a cross-layer adjacent pair (section 6, item 16) | aggregate pass | `moe-saturated-token`: `n_tokens = MAX_TOKENS_PER_GRAPH` over two layers, every aggregate asserted against the generator oracle |
| Malformed — interleaved logs | A `2>&1` capture parses identically to the stdout-only capture, with `skipped_line_count` equal to the log line count | classification | `interleaved-stderr`: the real stdout and the real merged capture produce byte-identical documents except `source` counts |
| Branch joins | `Ok` / `Error` construction and the document return have exactly one owner | `build` return | `document-move` |
| Loop joins | The scan loop, the block loop, the row loop, the element loop, and the aggregate sweep each terminate on count, on failure, and on a zero count | loop guards | `zero-graph` (0 callback lines, `graph_count` 0, `n_layer` null, `selections` 0); `zero-selection` shipped as `zero-graph`'s `selection_count: 0` assertion plus every dense fixture's empty `selections`; `zero-layer` shipped as `dense-zero-layer` |
| Move-out | The document is moved into `ExpertTrace.document`; `TranscriptScan` is moved into `build`'s owner local | epilogue | `document-move`; review against `docs/specs/c8-speed-first.md` section 2.8 |
| Borrow discipline | No helper returns a view derived from a `borrow` parameter; every text result is owned | signatures | `make check` |
| Generic monomorphization | `N/A`: no generic type or function is declared | `N/A` with this reason | — |
| Shared/process-global state | `N/A`: no process-global state; the module is pure over its one input | `N/A` with this reason | `repeat-expert-trace`, `env-perturbation` |
| Per-unit vs whole-program | The module compiles identically imported and whole-program | module boundary | `make check` (`check-per-unit`), `make build` |

### 3.3 `src/main.align` — the CLI arm

| Case | Contract to close | Implementation | Exact regression |
| --- | --- | --- | --- |
| Construction — arity | Two and three operands accepted; anything else is `Err` before any file work | `expert_trace_demo` | `cli-arity`: zero output on an arity failure |
| Success — both forms | Both forms emit byte-identical document bytes | `expert_trace_demo` | `form-parity` over every positive fixture |
| Success — summary block | Section 2.3's lines keep their order; `-` for absent values; control bytes sanitized | `expert_trace_demo` | `summary-order`, `summary-control-bytes` |
| Failure — path guard | An empty, over-`MAX_PATH_BYTES`, or NUL-bearing operand — transcript **or** destination — is `Err` with no output and no scan | `valid_cli_path`, applied to both operands before the derivation | `path-too-long`, `destination-path-guard` |
| Failure — read-only transcript | A transcript the invoking user cannot write cannot be opened at this pin; the arm exits nonzero with no document and an untouched destination | `fs.open_rw` (section 2.3 precondition) | `read-only-transcript` (mode `0444`; skipped under root) |
| Failure mapping | `status: "error"` becomes `Err(Error.Invalid)` after the document is emitted | epilogue | `error-corpus` exit codes |
| Selector isolation | `--expert-trace` in an operand position is an operand, not a selector | dispatch shape | `selector-as-operand`, following the `c7_selector` precedent at `src/main.align:371` |
| Help text | The usage block gains one line and no other line changes | `usage` | `usage-diff` |
| Everything else | **inherited** from `docs/specs/r1-qwen-model-ir.md` section 3.3: unknown selector, environment isolation, OS failure | unchanged | the R1 CLI cases re-run |

### 3.4 `scripts/eval_callback_fixture.py` — the generator

| Case | Contract to close | Implementation | Exact regression |
| --- | --- | --- | --- |
| Independence | The generator derives no value from `src/`; every expected selection and every aggregate is computed in Python | module imports | code review; the import list |
| Format fidelity | The generator's renderer reproduces the section 2.2 format string, the `%12.4f` element, the three markers, and the `min(ne, 6)` rule exactly | `render_block` | `fixture-selfcheck`: the generator re-parses the section 4.3 real fixture with its own reader and asserts an identical token stream |
| Corpus coverage | Every fixture named in sections 3.1–3.3 is emitted, with a manifest naming each case's expected code or expected document | `main` | the runner asserts every manifest case ran |
| Determinism | Two runs produce byte-identical fixtures | fixed seed | `fixture-determinism` |
| Cleanup | Writes only into a caller-supplied temporary tree | `main` | the runner's repository leak sweep |

### 3.5 `Makefile` and `scripts/` — build and verification graph

| Case | Contract to close | Implementation | Exact regression |
| --- | --- | --- | --- |
| Target definition | One new target `expert-trace-smoke` and one new focused qualification `expert-trace-parity`; the new module is reached through `check-per-unit $(ENTRY)`, which follows imports | `Makefile` | `python3 scripts/check-gate-topology` |
| Aggregate membership | `expert-trace-smoke` joins `HOSTED_CHECK_TARGETS`: no model, no network, no reference tool, runs in seconds — the same argument that admitted `model-ir-smoke` | `Makefile:17, 36` | `make gate-topology-check` |
| Qualification exclusion | `expert-trace-parity` stays outside `HOSTED_CHECK_TARGETS`, `CAPABLE_ONLY_CHECK_TARGETS`, and every aggregate | `Makefile` | `make gate-topology-check` |
| **Preflight profile selection** | **The `Makefile` IS modified, so `FRESH_IMAGE_PATTERNS` (`scripts/verification_scope.py:22`) matches and the classifier selects the fresh-image installed profile.** This is the opposite of R1B's case and must not be discovered late: `python3 scripts/pre-pr --plan` must be run and recorded before the real run, and the required installed profile must **not** be replaced by a Docker skip or an ambient `DOCKER_HOST` endpoint | `scripts/pre-pr` | `--plan` output recorded in the pull request, then the full `scripts/pre-pr --owner-test expert-trace-smoke -- make expert-trace-smoke` |
| Fixture cleanup | Every fixture path is removed by the `trap` on `EXIT`; the last assertion is that the temp root is still present | `scripts/run-expert-trace-smoke` | the `run-model-ir-smoke` shape, reused |
| Parity skip | An unset or absent `ALIGN_LLM_GGUF_MODEL` or `ALIGN_LLM_LLAMA_EVAL_CALLBACK` prints one exact `N/A` line and exits 0; a parse failure fails closed | `scripts/run-expert-trace-parity` | a synthetic-log unit inside the runner |
| Documentation | `docs/specs/roadmap.md` section R2 and `HANDOFF.md` name this document; `docs/align-requests.md` receives the Request 21 and Request 23 client evidence, the section 5.5 candidates (25, streaming stdout; 26, `str`-to-number), and the two implementation added (27, string sorting; 28, a readable accumulator). It receives **no** Request 22 evidence: R2A holds no `array<string>` | integration commit | the register edits are applied; `docs/align-development.md`'s expert-trace section is finalized |

## 4. Fixture and qualification design

### 4.1 `scripts/eval_callback_fixture.py` — the synthetic corpus

A new generator, independent of `src/`, that renders transcripts from its own copy of the section 2.2
format string and computes every expected value in Python. It emits a `manifest.json` naming each
case, its expected `status`, its expected `error_code`, and — for positive cases — the full expected
document. Six families:

1. **Dense.** A qwen2-shaped graph with `n_layer` in `{1, 2, 28}` and `n_tokens` in `{1, 5, 64}`.
   Expected: `status: "ok"`, `moe.present: false`, `shape_class: "dense-ffn"`, `locality` all `null`.
2. **MoE with known ids.** A graph carrying `ffn_moe_logits-N`, `ffn_moe_probs-N`, and
   `ffn_moe_topk-N` for `n_expert` in `{4, 8, 32, 128}` and `n_expert_used` in `{1, 2, 4, 8}`, with
   the expert ids drawn from a fixed seed so the generator knows every selection and every aggregate
   in advance. This is the corpus that closes every **MOE-PREREQ** cell synthetically, and the one
   the section 4.5 decision would replace with a real transcript.
3. **Truncated axes.** `n_tokens` in `{6, 7, 8, 64, 1024}` crossed with `n_expert_used` in
   `{4, 6, 7, 8}`, exercising every combination of full and three-plus-three printing on axes 0 and
   1, and a three-axis tensor exercising axis 2. Expected: exact `observed_token_indices`, exact
   `slots_truncated`, and `adjacent_pair_count` equal to `min(n_tokens, 6) - 1` when
   `n_tokens <= 6` and `4` when `n_tokens > 6`.
4. **Malformed.** One fixture per row of section 2.6's table, each defective in exactly one way, plus
   the two precedence fixtures defective in two ordered ways.
5. **Huge line.** A single 200,000-byte line, both as the first line and as a line after 500 valid
   blocks, asserting `R2_LINE_TOO_LONG` with the right offset and a truthful partial document.
6. **Window boundary.** The same logical transcript emitted with padding chosen so that a header
   line, a value row, a `sum` line, and a truncation marker each straddle offset `WINDOW_BYTES`,
   asserting a byte-identical document across all four paddings and against the unpadded original.

Families 5 and 6 are the two that a whole-file parser would pass trivially and a streaming parser can
fail silently; they exist because section 2.4 chose streaming.

### 4.2 Owner — `scripts/run-expert-trace-smoke`, `make expert-trace-smoke`

One runner, in the `scripts/run-model-ir-smoke` shape: `unset GIT_DIR GIT_COMMON_DIR GIT_WORK_TREE`,
`PYTHONDONTWRITEBYTECODE=1`, a `mktemp -d` tree removed by the `EXIT` trap, the generator invoked
into it, then one embedded Python driver over the manifest. It needs no model, no network, and no
reference tool, which is why it joins `HOSTED_CHECK_TARGETS`.

Beyond the closure cells of section 3, the runner:

- asserts `schema_version == 1` and the exact top-level field order on every document;
- asserts the exact field order of `source`, `run`, `graph`, `moe`, every `graphs` entry, every
  `selections` entry, and `locality`;
- recomputes every selection and every locality aggregate **in Python from the generator's own
  seed** and compares, rather than trusting the document's internal consistency — the section 4.3
  oracle;
- parses the checked-in real fixture of section 4.3 and asserts its measured shape;
- runs both CLI forms over every fixture and diffs the document bytes;
- keeps the repository leak sweep, temp-root assertion, descriptor budget, `env-perturbation`, and
  `repeat-expert-trace`.

Lowered `MAX_*` constants for the limit cases are supplied the way the corpus supplies extents — the
generator emits a transcript that exceeds a *real* constant where that is cheap (`MAX_LINE_BYTES`,
`MAX_EXPERTS_USED`, `MAX_LAYERS`), and the three constants whose real value cannot be exceeded
cheaply (`MAX_LINES`, `MAX_TRANSCRIPT_BYTES`, `MAX_SELECTIONS`) are closed by a
`debug_limits`-suffixed fixture the runner drives against a second entry point compiled with the
lowered values. That second entry point exists only in the smoke's build and is named in the
Makefile target, not in `main`.

### 4.3 The format-fidelity fixture and the aggregate oracle

**The fixture.** `eval/fixtures/expert-trace/qwen2-prefill-build10566.txt` — real output from this
host, captured with the section 2.2 command, reduced to **171 lines and 11,764 bytes** by selecting
six complete callback blocks that together cover every grammar case:

```text
common_debug_cb_eval:                     embd = (f32)   GET_ROWS(token_embd.weight{3584, 152064, 1, 1}, inp_tokens{5, 1, 1, 1}}) = {3584, 5, 1, 1}
common_debug_cb_eval:                   norm-0 = (f32)   RMS_NORM(MTL0#embd#0{3584, 5, 1, 1}, }) = {3584, 5, 1, 1}
common_debug_cb_eval:                   Qcur-0 = (f32)    RESHAPE(Qcur-0{3584, 5, 1, 1}, }) = {128, 28, 5, 1}
common_debug_cb_eval: Qcur-0 (view) (permuted) = (f32)    PERMUTE(Qcur-0 (view){128, 28, 5, 1}, }) = {128, 5, 28, 1}
common_debug_cb_eval:        cache_v_l0 (view) = (f16)       VIEW(cache_v_l0{512, 119040, 1, 1}, }) = {128, 4, 256, 1}
common_debug_cb_eval:            result_output = (f32)    MUL_MAT(output.weight{3584, 152064, 1, 1}, result_norm{3584, 1, 1, 1}}) = {152064, 1, 1, 1}
```

covering, in order: two operands and a full axis-1 print; the `, }` unary form with a backend-prefixed
operand; axis-1 truncation (`ne1 = 28`); a name containing spaces and parentheses; the `f16` type
with axis-2 truncation (`ne2 = 256`); and a single-row result with a `152064` axis. Each header is
followed by its complete real value block and its real `sum` line.

**Sanitization is asserted, not assumed.** The file is swept for the seven path fragments `/Users/`,
`/home/`, `/private/`, `/opt/`, `/var/`, `/tmp/`, and `\\`; for a Windows drive prefix; for any byte
outside printable ASCII; and for the invoking account's own name — `USER`, `LOGNAME`, and the home
directory's basename, each swept when it is at least four bytes long, below which a name would
collide with the grammar's own vocabulary rather than detect anything. It contains none: the
transcript's own content is node names, dimensions, and floats, and the model path appears only in
the *stderr* stream, which this fixture does not include. The smoke runs **all four** sweeps on
every invocation and prints what it swept, so a future re-capture cannot smuggle a path or a
username in, and the md5 assertion means any re-capture must re-record the provenance block above.

**Provenance recorded with the fixture** (the header comment in
`scripts/run-expert-trace-smoke`, not in the fixture, so the fixture stays byte-exact instrument
output):

```text
instrument : llama-eval-callback, version: 0.2.0 (build 10566, commit bb4caa754)
built with : AppleClang 21.0.0.21000101 for Darwin arm64
command    : llama-eval-callback -m MODEL.gguf -p "Write a function" -n 1 -t 4 > transcript.txt
model      : a dense qwen2 7B Q4_K_M GGUF (n_layer 28, n_embd 3584)
full run   : 21110 lines / 1487718 bytes / 958 callback blocks
excerpt    : 171 lines / 11764 bytes / 6 callback blocks, md5 81df3252be98a5e790e57fa77ba1e4b2
```

The `real-transcript` case asserts, against this fixture: `status: "ok"`, `moe.present: false`,
`graph.graph_count == 1`, `graph.n_layer == 28`, `graphs[0].n_tokens == 5`,
`graphs[0].phase == "prefill"`, `graphs[0].tokens_observed == 5`,
`graphs[0].tokens_truncated == false`, `source.callback_line_count == 6`, and
`locality.adjacent_pair_count == 0` with every aggregate `null`.

**The aggregate oracle.** Every locality value is recomputed in the runner, in Python, from the
generator's own selection list, using a deliberately naive implementation — nested loops over
adjacent pairs and set intersections — rather than the one-sweep algorithm section 2.7 specifies.
Two independent implementations of the same definition is what makes the sweep's cursor arithmetic
trustworthy; a Python reimplementation of the sweep would share its bugs.

### 4.4 Focused qualification — `scripts/run-expert-trace-parity`, and its explicit `N/A`

Opt-in, never in an aggregate, never in CI, both inputs required with no default, a hard failure on a
nonzero reference exit, a fail-closed parser, and the `</dev/null` / `timeout` / `ulimit -f`
wrappers `docs/specs/r1-qwen-model-ir.md` section 7 items 6 and 21 established.

```text
ALIGN_LLM_GGUF_MODEL            path to the model
ALIGN_LLM_LLAMA_EVAL_CALLBACK   path to llama-eval-callback
```

What it does:

1. Records `--version` output, then runs the instrument on the model with a fixed prompt into a
   temporary transcript, asserting the model's size and mtime are unchanged.
2. Runs `main --expert-trace` on that transcript.
3. **Cross-checks the document against an independent Python parse of the same transcript** — a
   second implementation of section 2.2's grammar, written in the runner, that recovers the node
   families, the layer count, the token count, and (for a MoE model) every `ffn_moe_topk` selection.
   Every field is compared exactly; any disagreement fails.
4. For a MoE model, recomputes the locality aggregates from the Python selections and compares.

**Neither variable has a default.** A qualification that silently passes when its subject is missing
is worse than no qualification, so a missing input prints exactly one of these four lines, in this
order, and exits 0 without claiming a pass:

```text
expert trace parity: N/A (ALIGN_LLM_LLAMA_EVAL_CALLBACK unset)
expert trace parity: N/A (ALIGN_LLM_LLAMA_EVAL_CALLBACK is not executable)
expert trace parity: N/A (ALIGN_LLM_GGUF_MODEL unset)
expert trace parity: N/A (ALIGN_LLM_GGUF_MODEL is absent)
```

**The two halves are emitted, not authored.** A run that reaches the instrument ends by printing its
own verdict for each half, so the pull-request record quotes lines the runner produced:

```text
expert trace parity (dense): PASS
expert trace parity (MoE): N/A - no MoE GGUF on this host; see section 4.5.
```

`(MoE)` prints `PASS` instead when `moe.present` is true, which is the one line that changes the day
section 4.5's decision is answered.

The dense half is runnable on this host today and is the strongest available evidence that the parser
matches the real instrument across a whole 958-block transcript rather than the six-block excerpt.

### 4.5 The MoE prerequisite, and the decision the user owns

Every cell marked **MOE-PREREQ** in section 3, and the R2 roadmap gate itself, need one thing that
does not exist here: **a transcript from a real MoE model.** The capability cannot create it and
does not download anything.

**What the user must decide:**

1. **Whether to obtain a small MoE GGUF at all.** Without one, `moe.present` is `false` on every
   real input, every locality aggregate is `null`, and section 1.4 item 3 stands: the R2 gate is
   open. The parser is still correct and still worth shipping; the measurement does not exist.
2. **Which model.** The constraint is small, MoE, and GGUF — small enough to run on this host, not
   the 12.1 GB `gpt-oss-20b` that `docs/specs/r1b-gptoss-moe-ir.md` section 4.4 already deferred for
   the same reason. A quantized small MoE in the low single-digit gigabytes would discharge every
   MOE-PREREQ cell and produce the first real reuse number. The exact model is the user's choice and
   this document deliberately does not name a download.
3. **Where it lives and whether it is retained.** The qualification never writes to the model and
   asserts its size and mtime are unchanged, but the storage is the user's to allocate.
4. **Whether the R2b acquisition strategy of section 5.1 is worth building before (1) is answered.**
   It is not: a strategy for collecting many transcripts is worthless until one transcript contains
   an expert selection.

Until (1) is answered yes, the MoE half is `N/A` with this reason, and it never counts as a pass.

### 4.6 Metrics

**Primary — correctness.** Three pass/fail measurements: every synthetic fixture's parsed selections
and aggregates equal the generator's independently computed values; the real fixture parses to its
measured shape; and the parity cross-check agrees field for field with an independent Python parse of
a full real transcript. None is a speed metric.

**Secondary — `bytes_read`.** `file_size <= bytes_read <= file_size + boundary_lines * WINDOW_BYTES`,
asserted on every fixture, which is the evidence that the reader streams rather than re-scans. The
window-boundary corpus is what makes the upper bound non-vacuous.

**Secondary — peak allocation.** `WINDOW_BYTES` plus the frozen selection columns, asserted through
the descriptor-budget and `peak-allocation` cases. A 400 MB transcript must not produce a 400 MB
resident set; that is the whole claim of section 2.4 and it is measured, not asserted.

**R2A makes no performance claim.** No baseline is established, no throughput threshold is asserted,
and `bounded-work` remains a complexity guard rather than a performance target. Under `CLAUDE.md` a
speed claim would require a reproducible benchmark and a named baseline, and R2A has neither. If a
later capability wants "transcript bytes per second", it owns the benchmark.

## 5. Deferred surfaces

### 5.1 R2b — acquisition, and the union strategy finding 7 makes possible

R2b collects transcripts and compares across them — section R2's "language別偏り", "task別偏り",
"repo別偏り". R2A defines the per-transcript document those comparisons are computed from and stops.

Two findings hand R2b a concrete strategy it should not have to rediscover:

- **Finding 7** means one unpatched invocation yields one prefill graph, so R2b cannot get a decode
  sequence from this instrument at all without R2c.
- **Finding 6** plus section 2.5.6's *exact* token indices mean that repeated invocations with
  prompts of increasing length recover the full per-position selection: a prompt of `n` tokens
  reveals positions `{0, 1, 2, n-3, n-2, n-1}`, and the union over `n` covers everything in
  `O(n_tokens / 6)` runs. Because attention is causal, the hidden state at position `p` — and
  therefore the router's choice at `p` — does not depend on whether `p` was reached by prefill or by
  decode, so the union is a valid reconstruction of the decode-time selection sequence.

Whether that reconstruction is *cheap enough* is R2b's measurement to make; the alternative is R2c.
R2A's contribution is that the token index it records is exact rather than a row ordinal, which is
the property the union needs. R2A also does not join the trace to `R1_MODEL_IR`; a consumer that
wants the authoritative architecture (section 2.5.4) reads both documents, and defining a join key
is R2b's decision once it knows how many transcripts it is joining.

### 5.2 R2c — the minimal patch, and exactly what it would change

Section R2 admits a minimal patch "不足時のみ" — only when the instrument is insufficient. Findings 6
and 7 are the evidence that it is, and R2A names the two changes rather than leaving them to be
rediscovered:

1. **Print the full axis for small integer tensors**, or exempt `ffn_moe_topk` from truncation. Today
   an `n_expert_used` above six loses the middle slots (`moe.slots_truncated`), and an
   `n_tokens` above six loses every middle token.
2. **Emit a graph per decode step.** `llama-eval-callback` decodes the prompt once and stops.

R2A takes no position on whether either is worth doing, because that depends on numbers R2b has not
produced. What R2A guarantees is that a patched transcript needs **no parser change**: multi-graph
segmentation, decode phase, and untruncated axes are all already in section 2.5's contract and all
already have fixtures (`multi-graph`, `phase-decode`, `topk-slots-4`). If R2c ships, R2A's document
gets *more* rows, not a schema 2.

### 5.3 R3 — the consumer

`docs/specs/roadmap.md` section R3 simulates LRU, LFU, recent reuse, score-based, top-k prefetch,
impact-driven prefetch, and CPU fallback. Its input is exactly the `selections` array of section
2.5.6, joined against R1B's per-`(layer, expert)` `ExpertBlock` byte ranges: the trace says *which*
expert was demanded at each step, and the Block IR says *how many bytes* that costs to fetch.

R2A defines no policy, no hit-rate metric, and no simulator. It deliberately emits `selections` as a
flat, sorted, exactly-indexed sequence rather than a pre-aggregated summary, because every one of
those seven policies needs the sequence and none of them can be reconstructed from the aggregates.
The `locality` object is a *summary for the gate*, not the simulator's input.

### 5.4 Residency tiers and cache scoring

`docs/specs/align-llm.md` section 6 places "hot expert" in VRAM, "warm expert" in DRAM, and "cold
expert" in NVMe; section 7.4 scores a cache entry by recent activation, frequency, router score, miss
penalty, transfer cost, layer position, and task / language / repo profile. R2A supplies exactly two
of those inputs — recent activation and frequency, as `locality.per_layer[].histogram` and the reuse
triple — and assigns no tier, computes no score, and reads no router *weight*.

**Router scores are deliberately not captured.** `ffn_moe_probs-N` and `ffn_moe_weights-N` carry
them, and R2A reads `ffn_moe_probs-N`'s *shape* to derive `n_expert` while ignoring its *values*.
Capturing them would mean parsing `%12.4f` floats whose printed precision is four decimals — enough
to rank experts, not enough to reproduce a gating computation — and no consumer exists yet.
Section 7.4's "router score" input becomes a schema 2 field when R3 asks for it, with a stated
precision limit, rather than a four-decimal number recorded now and trusted later.

### 5.5 Candidate Align capability requests

**These two were foreseen before implementation; Requests 27 and 28 were added during it and are
recorded in section 7.5 items 2 and 3.** All four are now in `docs/align-requests.md`. None is
consumed, and no compatibility layer is written for any of them.

#### 5.5.1 Request 25 — `std.process` has no streaming stdout

`docs/align-requests.md` Request 1 records `std.process` capture as COMPLETE. The shipped surface is
a command builder, not a free function: `c := process.command(cmd, argv)` then `out := c.run()?`
(or `c.run_bytes()?`), where `out.stdout()` is a zero-copy `str` — or `slice<u8>` — view of the
child's **entire** standard output, region-bound to `out`. There is no incremental, chunked, or
streaming stdout surface anywhere in the shipped API. `process.spawn` does no redirection at all —
the child inherits the parent's descriptors — so it is not an alternative, and the deferred
raw-bytes tier does not add one either.

**Evidence measured on this host.** `llama-eval-callback` writes its whole transcript to stdout.
The two runs of section 2.2 produced 1,487,718 and 1,101,250 bytes for 5-token and 3-token prompts
against a dense 7B model, and finding 9 extrapolates a patched multi-graph MoE capture to hundreds of
megabytes. An align-native `--expert-trace-run` that invoked the instrument directly would therefore
have to materialize the entire transcript as one `str` value before reading its first line, for a
scan that needs at most 1 MiB resident.

**Why it is genuine and not an application concern.** The consumer shape — run a child that emits an
unbounded text stream, process it incrementally, discard it — is the ordinary shape of every
compiler, test runner, profiler, and tracer this repository will drive, and `align-coder`'s
verification loop is already a client of `std.process`. The limitation is in the language's process
surface, not in this repository's use of it.

```text
Status: PROPOSED (now in the register)
Priority: medium
Blocking: no
Blocked gate or slice: none. R2A-EXPERT-TRACE-CAPTURE consumes a transcript *file* and
  never invokes the instrument (section 1.3), so the gap is designed around rather than
  hit. It becomes blocking for the first capability that must run an unbounded-output
  child in-process.
Independent work that may continue: all of R2A, R2b's transcript collection through the
  shell, and every existing `verify` / `repair` client whose child output is small.
Resume condition: Align ships an incremental stdout surface on `std.process` — a
  chunk-yielding read, a `reader` handle on the child, or a bounded-buffer callback —
  and align-llm adopts it in a future acquisition verb.
Align commit or pull request: none
align-llm verification: pending — an acquisition verb streams a transcript of at least
  100 MB with resident memory bounded by WINDOW_BYTES.
```

The workaround — capture with the shell, parse the file — is the shipped design and is a good design
on its own merits; that is precisely why the language-owned requirement is recorded rather than
hidden.

#### 5.5.2 Request 26 — no `str`-to-number conversion in the standard library

Align at this pin has **no** surface that converts text to a number. There is no `parse_int`, no
`parse_i64`, no `parse_f64`, no `to_i64`, and no `str` method of any kind that yields a number.
Formatting exists in one direction only — `builder.write_int`, `builder.write_float` — and
`write_float` takes no precision or width argument, so the conversion is not even round-trippable.
The two places the runtime does parse a number from text are unreachable as a general surface: it is
buried inside `json.doc`'s `as_i64` / `as_f64`, and inside `std.cli`'s `p.get_i64(name)` for command
-line flags.

**Evidence from this repository, which is the point.** Every existing call site that needs a number
out of text takes the JSON detour rather than writing a parser: `src/main.align:71` (`parse_i64`,
for CLI timeouts), `src/failure_memory.align:176` (`parse_integer`, for a persisted document field),
and `src/c6f1_request11_adoption.align:6` (`parse_i64`) are each two lines of `json.decode(value)?`
wrapped in a `Result`. That is the shape of the gap: three call sites route a plain decimal integer
through a JSON decoder because the standard library offers nothing else.

`src/expert_trace.align` cannot even do that, which is the stronger half of the argument. Section
2.2 finding 5 means an expert id arrives as `     12.0000` — not a JSON integer, and decoding it as
a JSON *number* would route an exact array index through a float. Every tensor dimension and every
layer suffix arrives as text too, inside lines that are not JSON at all. So this module writes the
one genuine private parser, `parse_uint` at `src/expert_trace.align:317`, with its own overflow
bound and its own sign rule, and `parse_integral_element` on top of it.

The `json.decode` detour therefore deserves naming twice: as the workaround three call sites already
take, and as the workaround the fourth cannot. It allocates a document, needs an enclosing
`arena {}` in the general case, and answers a different question than "is this text a bounded
decimal integer".

```text
Status: PROPOSED (now in the register)
Priority: medium
Blocking: no
Blocked gate or slice: none. Three consumers take the json.decode detour and R2A
  writes a private parser. It never blocks; it accumulates.
Independent work that may continue: all of it. This is a duplication and
  correctness-surface concern, not a capability gate.
Resume condition: Align ships a checked text-to-integer conversion returning
  Result<i64, Error> or Option<i64>, with a stated overflow contract; align-llm then
  drops the three json.decode detours and expert_trace's private parser and passes the
  owning smokes of each.
Align commit or pull request: none
align-llm verification: pending — src/main.align:71, src/failure_memory.align:176, and
  src/c6f1_request11_adoption.align:6 drop the json.decode detour and
  src/expert_trace.align:317 drops parse_uint; `make check failure-memory-smoke
  expert-trace-smoke` passes.
```

Whether Align wants a float parse as well is Align's call, and R2A takes no position: finding 5 lets
this repository need only the integer form. The requirement is the capability, not the spelling.

### 5.6 Inherited deferrals

Request 21's read-only-open limitation (now with a second client, section 2.1); Request 22's
`array<string>` indexing; Request 23's spurious huge-struct-copy warning (now with a third client);
and Request 24's `builder` parameter type, whose absence is what makes section 2.7's forty-line
reader duplication the shipped form. All inherited from `docs/specs/r1-qwen-model-ir.md` section 5
and `docs/specs/r1b-gptoss-moe-ir.md` section 5.6, unchanged in status. R2A introduces no new
evidence for or against Requests 22 and 24.

## 6. Correction ledger

The capability is now **implemented**. This section records every place where implementation and
measurement contradicted the plan above, what the shipped contract is, and the exact case that
closes it. Sections 1 to 5 remain authoritative except where a row below supersedes them; each row
names the superseded text. Cases without a runner prefix are cases inside
`scripts/run-expert-trace-smoke`.

| # | Superseded text | Shipped contract | Why | Case |
| --- | --- | --- | --- | --- |
| 1 | Section 2.5.1 "every later step produces a `status: "error"` document"; section 2.6 step 3 | An operating-system failure at `open`, `len`, or `pread` returns `Err(Error)` with **no document and no stdout**, exactly as `gguf.inspect` and `--model-ir` do. `R2_TRANSCRIPT_UNREADABLE` names the fault class inside the module and never appears in a document | Section 2.3, section 3.1's Cleanup row, and section 3.3 all require the destination to be untouched on an OS failure, which is incompatible with writing a document for it. The R0/R1 precedent already fixed the shape | `unreadable-transcript`, `directory-operand`, `untouched-destination` |
| 2 | Section 2.5.2's `"skipped_line_count": 0` | A blank line is ignorable and counted, as section 2.6 states. The real full run reports `1` (its trailing blank) and the section 4.3 excerpt reports `5` | Two normative statements — section 2.5.2's field contract and section 2.6's "a trailing blank line … counted into `source.skipped_line_count`" — outrank one illustrative constant | `real-transcript`, `run-expert-trace-parity` |
| 3 | Section 2.4's `next_line` step 3, window doubling | The window is never grown. `WINDOW_BYTES` is sixteen times `MAX_LINE_BYTES`, so a window that starts at a line and fills without a newline already proves the line is over the cap; the cap is additionally enforced on the length of every returned line, so a line between 64 KiB and 1 MiB whose newline *is* resident still fails | Unreachable code is worse than an argued absence, and the second enforcement point is the one a 200,000-byte line actually needs | `huge-line-first`, `huge-line-late`, `window-header-*`, `window-row-40`, `window-sum-40`, `window-marker-40` |
| 4 | Section 2.5.6 "A graph boundary is a repeated node name. ggml node names are unique within one graph" | **False at build 10566.** One 958-block qwen2 prefill graph carries **650** distinct names and prints `Qcur-0` four times. The shipped rule: the first callback node of the transcript names the graph **entry point**, and every later occurrence of that name opens the next graph | Finding 3's own occurrence counts (`Qcur-N 112` over 28 layers) already implied four per layer; finding 7 established that build 10566 emits exactly one `embd` and one `result_output` per graph evaluation, which is the property a boundary can rest on | `multi-graph`, `graph-limit`, `moe-inconsistent-graphs`, `run-expert-trace-parity` over all 958 blocks |
| 5 | Section 2.6's `R2_ROW_COUNT` condition | Extended with the axis-3 group count, which must equal `ne3` **exactly**: axis 3 carries no truncation marker among the nine shapes and the printer loops `i3` over `ne3` with no truncation branch, so the `min(ne, 6)` rule does not apply to it | Silently accepting a wrong number of `    [` … `    ]` groups would mis-associate every row that follows | `axis-shapes` (a `{4, 3, 2, 3}` tensor) |
| 6 | Section 2.5.6's three-valued `phase` | `graphs[].n_tokens` and `graphs[].phase` are `null` for a graph that carries neither `embd` nor an `ffn_moe_topk`. The three values remain normative for every graph whose token axis was derived | Nothing is fabricated and a capture that began mid-graph stays diagnosable. `R2_TOKEN_COUNT` then fires exactly on section 2.6's stated condition — an out-of-range value, or two sources disagreeing | partial documents across the error corpus |
| 7 | Section 2.5.5's third `n_expert` rule and the `"router_weight"` value of `n_expert_source` | **Withdrawn.** The only identifier for the router weight operand is the `ffn_moe_logits-N` node, whose own axis 0 is already rule two, so the third rule can never be selected. `n_expert_source` is `"ffn_moe_probs"`, `"ffn_moe_logits"`, or `null` | Dead code that no fixture can reach is not a contract | `n-expert-logits`, `n-expert-absent`; the `n-expert-router` cell is withdrawn with it |
| 8 | Section 4.3's `real-transcript` assertions | The excerpt asserts `graph.n_layer == 1`, `graph.shape_class == "unknown"`, and `source.skipped_line_count == 5`. `n_layer == 28` and `shape_class == "dense-ffn"` are the **full run's** values and are asserted by the parity qualification instead | The six-block excerpt contains only `-0` suffixed nodes and no dense feed-forward family; asserting 28 against it would assert a number the fixture does not contain | `real-transcript`, `run-expert-trace-parity` |
| 9 | Section 2.3's column-aligned summary block | The same lines in the same order, rendered one value per line (`print(label)` then `print(value)`), following the R0 and R1 arms verbatim | It keeps the property `summary-control-bytes` asserts: a transcript-controlled value occupies exactly one line whatever bytes the transcript declares | `summary-order`, `summary-control-bytes` |
| 10 | Section 2.6's `R2_HEADER_GRAMMAR` detail | The escaped, bounded line prefix when the line is valid UTF-8; the line's **start offset** when it is not | There is no `str` to escape for a non-UTF-8 line, and inventing a lossy one would hide the byte that caused the failure | `invalid-utf8-name`, `nul-in-header` |
| 11 | Section 2.6's `R2_EXPERT_ID_NOT_INTEGRAL` detail | The element text **verbatim, padding included** | The `%12.4f` field width is itself part of the grammar; trimming would hide a width change that is evidence of drift | `expert-fraction`, `expert-negative`, `expert-nan`, `expert-inf` |
| 12 | Section 2.6's `R2_NODE_LIMIT` condition | Also fires when the distinct-name interning table is exhausted — `MAX_NODES_PER_GRAPH` names or `MAX_NODES_PER_GRAPH * MAX_NAME_BYTES` name bytes — with the graph ordinal as the detail | The name table is the memory the node count actually bounds, and a graph's nodes are drawn from it | `node-limit` |
| 13 | Section 2.4's constant table | Adds `MAX_OPS` = 1024 and `OP_STREAM_BYTES` = 16384, the bound on distinct operation names and their text. Exhausting either is `R2_HEADER_GRAMMAR` | `graph.ops` is a rendered list and needed its own bound; the measured graph uses twelve operations | bounded by construction; no fixture reaches 1,024 distinct operations |
| 14 | Section 2.5.7's "the same reuse triple" | Each `phase_split` side is `{"adjacent_pair_count", "reuse_numerator", "reuse_denominator", "reuse_per_mille"}`, in that order, or `null` | Schema 1 needs a named field set, not a description | `phase-*`, field-order assertions |
| 15 | Section 2.6's `R2_HEADER_GRAMMAR` and `R2_VALUE_GRAMMAR` conditions, and section 2.4's implicit "no line is materialized unless it is kept" | **Valid multi-byte UTF-8 where the grammar requires a specific ASCII byte is a grammar fault, not a crash.** A `str` range slice at a length-relative offset ABORTS the process ("not a UTF-8 boundary", exit 134, no document) when the offset lands inside a scalar. Every such offset is now proved by an ASCII match — `starts_with` / `ends_with` at the five sites `parse_header` and the row classifier used a fixed-width slice — and rule 5 of the module header states the class | A transcript is arbitrary UTF-8: a node name, a type, an operation, or an operand may carry any scalar (finding 2 already records `(view)` and `#`). A header ending `…{1, 1, 1, 1}é` took the whole process down and produced no document, which is the exact opposite of section 2.5.1's fail-closed-with-evidence contract. `bounded_detail` remains the one offset computed from a length, and it walks back over continuation bytes itself | `multibyte-type-close`, `multibyte-header-tail`, `multibyte-src0-separator`, `multibyte-src1-tail`, `multibyte-value-row`, `multibyte-everywhere` |
| 16 | Section 2.5.7's "pairs of token indices differing by exactly one, within one graph and one layer" | Adjacency compares the `(graph, layer)` prefix of the packed group key **separately** from the token step: `(previous >> GROUP_TOKEN_BITS) == (current >> GROUP_TOKEN_BITS) && previous + 1 == current`, with `GROUP_TOKEN_BITS` = `LAYER_SHIFT - TOKEN_SHIFT` = 20 | `previous + 1 == current` on the packed key alone was *not* the stated contract: at `token = MAX_TOKENS_PER_GRAPH - 1` the increment carries out of the token field into the layer field, so the last token of layer N and the first token of layer N+1 were counted as an adjacent pair. Measured on a two-layer, `n_tokens = 1048576` transcript: `adjacent_pair_count` 9 where the definition gives 8, with `per_layer`, `working_set`, and the phase split all inflated with it | `moe-saturated-token`, asserted against the generator's independent oracle |
| 17 | Section 2.5.4's `"n_layer": 28` | `graph.n_layer` is `null`, never `-1`, when the transcript carries no `-N` suffixed node. The three producers are the six-block excerpt with no suffixed family, a transcript with no callback line, and a capture that began mid-graph | `-1` is a value a JSON reader cannot tell from a derived layer count, and every other underived field in this schema is already `null` (`run.build`, `moe.n_expert`, `graphs[].n_tokens`). Section 2.5.4 now carries the field table that states it | `dense-zero-layer`, `zero-graph`, `real-transcript` |
| 18 | Section 2.6 step 2, "Path lexical validation against `MAX_PATH_BYTES`" | Step 2 validates **both** operands — emptiness, `MAX_PATH_BYTES`, and a NUL byte — in `src/main.align`, before the derivation. `expert_trace.build_trace` keeps its own transcript-path check as the module's fail-closed contract | The destination never reaches `expert_trace`, so an unusable one was only discovered by `fs.write_file` after a whole transcript had been scanned and a document built. Step 2 is ordered before step 3 precisely so that cannot happen | `path-too-long`, `destination-path-guard` |
| 19 | Section 7.5 item 2, "No string ordering and no string sort" | Half withdrawn. `str` satisfies `Ord` at this pin and `<` **is** the byte-lexicographic comparison, so `span_less` / `span_same` are two expressions over `span_text`, not a hand-written byte loop. The genuine remaining gap is the *sort*: `array<T>.sort()` rejects `str` elements, `array_builder<str>` is rejected outright, and `sort_by_key` — which does admit a `str` key — cannot reach these columns because "a lambda cannot capture the owned value 'starts' yet"; there is no comparator `sort_by` — so `sort_spans` stays | Claiming a gap that does not exist weakens the register. `docs/align-requests.md` Request 27 and section 7.5 item 2 now state the shipped half and the missing half separately | `make check`, `make expert-trace-smoke` (every `node_families` / `unsuffixed_nodes` / `ops` list), `multibyte-everywhere` |

**One finding, not a correction.** Because `R2_ROW_COUNT` enforces `printed = min(ne, 6)`, no
`(graph, layer)` pair can ever carry more than six observed token indices, so a run of consecutive
observed tokens is at most six long and every `locality.working_set` window above `4` reports
`sample_count: 0` on **every transcript this parser accepts**. Windows 8 through 64 become
non-vacuous only if R2c ships section 5.2's first change. The windows are still emitted, with their
zero sample counts visible, because a reader must be able to see that the question was asked.

## 7. Verification record and unclosed cells

### 7.1 Shipped surface

| Path | Role |
| --- | --- |
| `src/expert_trace.align` | the line reader, the grammar, graph segmentation, `TranscriptScan`, `ExpertTrace`, the selection table, the locality aggregates, the renderer, every `R2_*` code |
| `src/main.align` | the `--expert-trace` arm: arity, destination, summary block, exit mapping |
| `scripts/eval_callback_fixture.py` | the synthetic corpus and every expected value, independent of `src/` |
| `scripts/run-expert-trace-smoke` | the narrow durable owner; `make expert-trace-smoke`, in `HOSTED_CHECK_TARGETS` |
| `scripts/run-expert-trace-parity` | the opt-in focused qualification; `make expert-trace-parity`, in no aggregate |
| `eval/fixtures/expert-trace/qwen2-prefill-build10566.txt` | the format-fidelity excerpt, 171 lines / 11,764 bytes, md5 `81df3252be98a5e790e57fa77ba1e4b2` |
| `Makefile`, `scripts/check-gate-topology` | the two targets and both pinned aggregate lists |
| `.gitattributes` | `eval/fixtures/expert-trace/*.txt -whitespace`, so the truncation markers' significant trailing space survives `git diff --check` and every whitespace-stripping tool |

### 7.2 Cells closed by a case

Every applicable cell of section 3 maps to a passing case in `scripts/run-expert-trace-smoke`
(95 corpus fixtures plus the real excerpt and the CLI cases) or in `scripts/run-expert-trace-parity`,
except the rows below. Seventeen of the nineteen section 2.6 codes fire on their own fixture and the
runner asserts that none is missing.

**Four section 3 cells are closed by a case whose shipped name differs from the planned one.** They
are listed here rather than left to a reader's search, because a cell that names a case nobody can
find is indistinguishable from an unclosed one:

| Planned cell name | Shipped case | Note |
| --- | --- | --- |
| `n-expert-probs` (section 3.2) | `n-expert-probs` | Now a fixture of that exact name — a graph carrying both `ffn_moe_probs-N` and `ffn_moe_logits-N`, asserting `n_expert_source: "ffn_moe_probs"`. Every `moe-E*-U*` fixture exercises the same rule |
| `zero-selection` (section 3.2) | `zero-graph`'s `selection_count: 0` assertion, plus every dense fixture's empty `selections` and `null` locality | There is no separate fixture: a transcript with zero selections is either a dense one or one with no callback line, and both are already in the corpus |
| `window-single-read` (section 3.1) | the runner's per-fixture assertion: `file_size <= WINDOW_BYTES` implies `bytes_read in {0, file_size}` | Applied to all 95 fixtures rather than to one named case, which is strictly broader |
| `huge-line` (section 3.1) | `huge-line-first` and `huge-line-late` | Split so the start-offset detail is asserted both at `0` and at a real mid-file offset (correction 3) |

### 7.3 Cells not closed, with the reason

| Cell | Status | Reason |
| --- | --- | --- |
| `line-limit` / `R2_LINE_LIMIT` | **not closed by a case** | `MAX_LINES` is 2^30, so a fixture needs at least a 1 GiB transcript and roughly 10^9 scan iterations — not a hosted-smoke cost. `MAX_TRANSCRIPT_BYTES` binds first on every realistic transcript. The guard is implemented and ordered before line classification, and it is reachable only through a file `oversize-transcript` already refuses |
| `n-expert-router` | **withdrawn** | Correction 7: the rule is unreachable and is not implemented |
| `peak-allocation` | **closed indirectly** | Align at this pin exposes no resident-set measurement. The claim is carried by `bytes-read-bound` (a 1.2 MB transcript reads one window at a time, proven by `bytes_read > file_size` on the straddling corpus) and by `descriptor-budget` |
| every **MOE-PREREQ** cell | **closed synthetically only** | No MoE model and no MoE transcript exists on this host. `moe-E*-U*`, `trunc-T*-U*`, `expert-id-format`, `multi-graph`, and the aggregate oracle close them against the generator's known ids; section 4.5's decision is what would replace them with real input. Section 1.4 item 3 stands: **the R2 roadmap gate is open** |
| `topk-slots-4` (axis-0 full print) | **synthetic only** | Finding 6 recorded that no real axis-0 extent under seven was observed on this host. `moe-E4-U1`, `moe-E8-U2`, `moe-E32-U4`, and `trunc-*-U4`/`-U6` exercise the `ne <= 6` branch on axis 0 |
| `fixture-selfcheck` (section 3.4) | **discharged differently** | Instead of the generator re-parsing the real excerpt, `scripts/run-expert-trace-parity` runs a second, independent implementation of the section 2.2 grammar over a **whole 958-block real transcript** and compares node families, operations, layer count, graph count, token counts, phases, line censuses, and every selection field for field. That is strictly stronger than a six-block self-check |

### 7.4 Commands and results

```text
make check                      PASS   (check-per-unit over 28 units, expert_trace included)
make build                      PASS
make fmt                        PASS   (no diff; idempotent on src/expert_trace.align)
make format-check               PASS
make gate-topology-check        PASS   (both pinned lists updated)
make expert-trace-smoke         PASS   95 fixtures, 17 error codes, the real build-10566 excerpt,
                                       both CLI forms, the aggregate oracle, fixture determinism,
                                       the window-boundary, huge-line, and multi-byte corpora,
                                       CLI arity, the destination-path guard, and the read-only
                                       transcript case; about 9 s
make gguf-smoke                 PASS   (unchanged owner)
make model-ir-smoke             PASS   (unchanged owner)
make test-selection-smoke       PASS   (unchanged owner)
make patch-eval-smoke           PASS   (unchanged owner)
make verify-loop-smoke          PASS   (unchanged owner)
git diff --check                clean
git diff --check d8d4ef6..HEAD  clean
```

**`git diff --check` is clean only because the fixture is exempted, and that is deliberate.** The
checked-in excerpt's axis-1 and axis-2 truncation markers (`"            ..., "` and
`"        ..., "`) end in a space the grammar of section 2.2 finding 6 matches literally, so seven
lines of `eval/fixtures/expert-trace/qwen2-prefill-build10566.txt` are trailing whitespace by
`git diff --check`'s definition and load-bearing by this parser's. The file is byte-exact instrument
output and must not be stripped, so `.gitattributes` carries
`eval/fixtures/expert-trace/*.txt -whitespace`, following the `corpus-file-set.manifest -text`
precedent already in that file. Both the working-tree and the full-branch range form of the check are
recorded above because the range form is the one that reads the fixture's added lines.

Three lines the smoke prints on this host, quoted because they are the evidence for section 4.3's
sanitization claim, `docs/align-requests.md` Request 21's client evidence, and the corpus size:

```text
expert trace smoke: real-transcript sanitization swept 7 path fragment(s), the Windows drive prefix, every non-printable byte, and 1 account name(s) ['hiro']
expert trace smoke: read-only-transcript exits 3 with no document (Request 21 client evidence: `fs.open_rw` requires O_RDWR on a transcript R2A never writes)
expert trace smoke: 95 fixtures, 17 error codes, the real build-10566 excerpt, both CLI forms, the aggregate oracle, and CLI arity/isolation PASS
```

The parity qualification, run against the local dense model and the local instrument. Every line
below is the runner's own output, not an author's summary:

```text
expert trace parity: PASS
  instrument build
    version: 0.2.0 (build 10566, commit bb4caa754)
    built with AppleClang 21.0.0.21000101 for Darwin arm64
  graphs             1
  nodes              958
  layers             28
  shape class        dense-ffn (ffn_gate/ffn_up/ffn_swiglu present, ffn_moe_topk absent)
  moe                false
  selections         0
  bytes / lines      1101250 / 16633
  bytes_read         1101339 (100.01% of the file)
  elapsed            0.042 s (diagnostic only; R2A makes no performance claim)
  locality           N/A - moe.present is false, so the R2 gate stays open (section 4.5)
expert trace parity (dense): PASS
expert trace parity (MoE): N/A - no MoE GGUF on this host; see section 4.5.
expert trace parity: model size and mtime unchanged (read-only proof)
```

`make ci` is not selected: this capability changes no aggregate topology beyond adding one hosted
target, which `gate-topology-check` owns, and makes no performance claim.

**Preflight profile, as section 3.5 predicted.** The `Makefile` **is** modified, so it matches
`FRESH_IMAGE_PATTERNS` (`scripts/verification_scope.py:22`) and the shared classifier selects the
fresh-image installed profile. `python3 scripts/pre-pr --plan` refuses a dirty worktree
(`preflight error: preflight requires a clean worktree`), so it must be run on the committed
candidate before publication, its output recorded in the pull request, and the full
`python3 scripts/pre-pr --owner-test expert-trace-smoke -- make expert-trace-smoke` run after it.
The required installed profile must not be replaced by a Docker skip or an ambient `DOCKER_HOST`
endpoint.

### 7.5 Align limitations met while implementing

Classified, not worked around. The register in `docs/align-requests.md` is the orchestrator's to
edit; this section is the client evidence.

1. **No `str`-to-number conversion** (section 5.5.2, Request 26). Confirmed as a genuine language
   gap, and the shape of the evidence is not what the plan assumed. The three existing align-llm
   call sites do not hand-roll a parser: `src/main.align:71`, `src/failure_memory.align:176`, and
   `src/c6f1_request11_adoption.align:6` are each a two-line `json.decode` detour. R2A cannot take
   that detour — `     12.0000` is not a JSON integer and an expert id must not travel through a
   float — so `expert_trace.parse_uint`, plus `parse_integral_element` on top of it, is the one
   genuine private parser in the repository. Finding 5 kept it to the integer form.
2. **No string *sort*** (Request 27) — and, on measurement, **not** the "no string ordering" gap this
   section first claimed. `str` satisfies `Ord` at this pin and `<` is exactly the byte-lexicographic
   comparison `graph.node_families`, `graph.unsuffixed_nodes`, and `graph.ops` need, so `span_less`
   and `span_same` are one expression each over `span_text` and no byte loop is written. What is
   genuinely missing is the sort, verified three ways against the pinned toolchain in this module's
   own shape: `array<T>.sort()` over the names is "'sort' needs a numeric element type, got str";
   materializing the spans first is "heap `array_builder<str>` requires a Copy scalar, `string`, or
   a closed heap record"; and `index.sort_by_key(fn i { span_text(names, starts[i], ends[i]) })` —
   which is otherwise exactly right, since `sort_by_key` *does* admit a `str` key — is "a lambda
   cannot capture the owned value 'starts' yet (capture supports copy values like
   int/float/bool/char)", with "field access is only supported on a local binding" for the column
   that lives on a `borrow` parameter. There is no comparator-based `sort_by` overload. `sort_spans`,
   a bottom-up merge sort over an index array ordered by the shipped comparison, stays.
   Correction 19 records the withdrawal of the wrong half.
3. **No readable accumulator.** `builder` and `array_builder` are write-only until `build()`, so an
   interning table that must compare a candidate against text it has already accumulated cannot use
   either. The module accumulates node and operation text into a `buffer` — which *is* readable
   through `.bytes()` while still growing — and keeps its spans in pre-sized mutable `array<i64>`s.
   This works and is bounded, but it is a workaround for a missing "append and read" collection.
   Recorded as `docs/align-requests.md` Request 28, `PROPOSED` and non-blocking.
4. **`builder` and `array_builder` are not parameter types** (Request 24, unconsumed). The whole
   forward pass is therefore one function, as `gguf.inspect` already is. Third client, no status
   change.
5. **`fs.open_rw` for a read-only input** (Request 21, unconsumed). Second class of read-only
   input, and R2A opens no GGUF at all: a transcript captured into a root-owned or read-only
   artifact directory cannot be opened. Asserted rather than argued — `read-only-transcript` sets a
   valid transcript to mode `0444` and observes `main --expert-trace` exit **3** with no document
   and an untouched destination, and the case is written to flip the day `fs.open_ro` ships. The
   precondition is stated in sections 2.3 and 2.6 and in `docs/align-development.md`. New client
   evidence for an existing request.
6. **Huge-struct-copy warning** (Request 23, unconsumed). Four lines of `make check` at the pinned
   toolchain, verbatim:

   ```text
   src/expert_trace.align:403:31: warning: huge struct copy: returning `expert_trace$Header` (176 bytes) by value copies it out; narrow the struct (split hot/cold fields) or return a handle
   src/expert_trace.align:418:31: warning: huge struct copy: returning `expert_trace$Header` (176 bytes) by value copies it out; narrow the struct (split hot/cold fields) or return a handle
   src/expert_trace.align:820:78: warning: huge struct copy: returning `expert_trace$TranscriptScan` (424 bytes) by value copies it out; narrow the struct (split hot/cold fields) or return a handle
   src/expert_trace.align:1607:24: warning: huge struct copy: `expert_trace$TranscriptScan` (424 bytes) is passed by value — every call copies it; narrow the struct (split hot/cold fields) or pass a `slice`/view
   ```

   Only the last is Request 23's defect: `build`'s parameter is `borrow t: TranscriptScan`, so no
   call copies the 424 bytes, yet the lint reports "is passed by value — every call copies it"
   because it consults the parameter's struct type and never its `ParamMode`. Third client, no
   status change. The three `returning … by value` lines are the lint working as designed on
   genuine by-value returns and are *not* evidence for Request 23; they are recorded here so the
   register's client evidence names the one line that is.
7. **A `str` range slice aborts on a non-boundary offset, with no fallible form.** `text[a..b]`
   panics — "string slice index N is not a UTF-8 boundary within length M", process exit 134 — when
   either offset falls inside a multi-byte scalar. There is no `Option`/`Result`-returning slice, no
   `is_char_boundary`, and no "round to the nearest boundary" helper, so a parser over arbitrary
   text must prove every offset itself against an ASCII match. This is not recorded as a request:
   the abort is Align's stated fail-fast contract for an invalid index, exactly as `view.u8(i)`
   aborts out of range, and the discipline it forces is the correct one (rule 5 of the module
   header, correction 15). Recorded so the next text-parsing client inherits the rule rather than
   the bug.
8. **A `Fault` record cannot carry a `str` field across a loop iteration.** Assigning a record with
   a `str` field out of a `match` arm inside a loop is rejected as "use of invalidated borrow … its
   source was dropped at the end of the loop iteration", even when every value the field can hold is
   a `'static` literal. The fix is one `.clone()` per fault construction, which is cheap; the
   diagnostic is nevertheless conservative about literals. Minor, non-blocking, recorded for
   completeness.
