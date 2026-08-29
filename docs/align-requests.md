# Align language/stdlib requests from align-llm

This document records capabilities that the **Align language and standard library** need,
discovered by building `align-llm` (a local LLM coding system) as a real client. It is the
register that `AGENTS.md` requires ("If this project needs missing Align functionality, document
the dependency clearly").

**How to use this document.** `align-llm` is a continuing real-client testbed and driver: its purpose
is to surface genuine Align needs, not to force-build around them. Record a language,
compiler/runtime, or standard-library requirement whenever real implementation work exposes it,
including a non-blocking requirement or one that an application workaround could temporarily hide.
The existence of a workaround does not make a language-owned requirement an application concern.
Each request below is meant to be implemented **in the Align repository** (`../align`), under the
current `../align/CLAUDE.md` delivery and test rules, and can be handed directly to Align's own
tooling. Update the relevant design when the request changes a public contract, but do not infer a
separate design pull request or one pull request per register row; Align may deliver mutually
dependent prerequisites as one consumer-complete capability wave. `align-llm` does not work around
these; it waits for the Align capability and then exercises it as a real client.

Verified against the `../align` compiler on 2026-07-24. File paths are stable references; line
numbers are approximate and may drift — locate by function name.

## Request protocol

Every new or reopened request must begin with this metadata:

```text
Status: PROPOSED | ACCEPTED | IMPLEMENTING | ALIGN_MERGED | ALIGN_LLM_VERIFIED | CLOSED
Priority: critical | high | medium | low
Blocking: yes | no
Blocked gate or slice: <consumer capability or acceptance cell, or "none">
Independent work that may continue: <work that does not assume the requested surface>
Resume condition: <observable Align and align-llm gate>
Align commit or pull request: <named commit/PR, or "pending">
align-llm verification: <command/result, or "pending">
```

The lifecycle is:

```text
PROPOSED -> ACCEPTED -> IMPLEMENTING -> ALIGN_MERGED -> ALIGN_LLM_VERIFIED -> CLOSED
```

The currently pinned Align commit is
`3a34febe912db5096c58c74fede36ff53f223e04`, selected by the Request 44 consumer adoption. The reviewed
`docs/specs/check-gate-topology.md` fresh-compiler design and its FRESH-WORKER/FRESH-IMAGE base
capabilities are merged. The closed Request 6 installed profile extends that same trust boundary to
two separately evidenced native Linux rows, x86_64 and aarch64; emulation is not acceptance
evidence. A later request may change `.align-revision` and advance to `ALIGN_LLM_VERIFIED` after the
feature-specific consumer owner passes against the managed pin. The merged Align CI result owns the
compiler's supported-platform coverage; the pin change does not make align-llm rerun every native
row. A request adds target-local evidence only when it changes that platform boundary, makes a
target-specific performance claim, or names a concrete provider-CI gap. A consumer outside the
reviewed profiles must still define its own profile before claiming target-local acceptance.

A blocking request pauses only its dependent consumer capability. Record that pause and its resume
condition in `HANDOFF.md`; continue independent work when it remains valid. Do not implement a
workaround or write code against a proposed surface. A non-blocking request must name its first
expected consumer and becomes blocking if that consumer is reached before `ALIGN_MERGED`.

After Align merges the capability, adopt all merged requests required by the next consumer in one
pin wave when practical: rebuild the release compiler/runtime once, update `.align-revision` once,
run every acceptance target that owns the changed consumer boundary, then run the final integration
owner named by the accepted request. A pin change alone selects managed materialization and the
feature owner, not a blanket `make ci` or platform matrix. Close each request only after this file
records Align's response and its real-client verification.

Older entries use terms such as “adoption slice,” “enabling slice,” or “separate target” to name
dependency and acceptance cells. Those terms do not mandate separate align-llm branches or pull
requests. Unless an entry identifies a distinct external/platform failure domain, perform its
adoption target as an ordered checkpoint on the consumer capability branch and review it with the
consumer that first uses the shipped surface. A focused adoption or qualification target does not
join routine hosted/capable aggregates merely because it is important; run it when its owning
boundary changes or an explicit audit selects it, not for an unrelated pin change.

> **Status (2026-08-28): Requests 1–20 are CLOSED, Requests 21–43 and 45–46 are PROPOSED and non-blocking, and
> Request 44 is ALIGN_LLM_VERIFIED pending publication closure. C8-OPTIONAL-TARGETED-STAGE is the
> active stable candidate; its schema/owner matrix and paired acceptance pass at the adopted pin.
> R5C-METAL-PREFILL-ARM merged as align-llm PR #129, and following the user's
> decision to download `OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf`, Track B started two consumers on
> that model: R2-LOCALITY-GATE merged as align-llm PR #131 (`fff5806` -> `546b5cc`) with the R2
> locality gate met in the prefill direction, R1C-OLMOE-MOE-IR merged as align-llm PR #132, and
> MOE-PREREQ-DISCHARGE merged as align-llm PR #133. R3-RESIDENCY-SIM (branch
> `agent/r3-residency-sim`, the expert-residency policy simulator) is the single active Track B
> consumer, in publication. See the end of this narrative for the next consumer
> named for each remaining pending user/Align decision.** C6-EVALUATION merged as align-llm PR #100 (`282062bf00416f5e0df678b8bd885709084b4e16`); its final capable integration gate passed at head `049172f5be57002c2426f012fe23038f570f5069` in CI run 32490981785, including both installed native profiles, closing Requests 11 and 14. C6-MEASURED then shipped the consuming provider transport and made `c6e-request2-adoption` a hosted-lane member; its focused owner and the complete capable check graph plus the wired `prompt-gate-check` gate passed at head `7273f65bfc1a2604daf37b2bd7748a46d2bd59f2`, closing Request 2 when PR #103 (`c9a510dc6ef4dc123f586eb33f447f02348061fb`) merged. C7-PERSISTED-RESULT then ran Request 9's named adoption fixture, implemented its owned-result consumer, and passed the C7 lifetime/artifact qualification plus the supervised final `make ci` on the same branch, closing Request 9 at the unchanged pin when PR #104 (`a52b9ac69cdd3a47574a5a4dc426e7edc8294dbf`) merged. C7-P then added Request 20 while building the `aarch64-apple-darwin` platform profile: Align CI's `macos-15` leg executed no test binary, so Request 9's own `m5_owned_json` boundary regressions did not run on macOS even though its contract is target-local. Align PR #887 closed that provider-side gap; align-llm pins the containing Align `main`, both the Darwin client profile and supervised capable graph passed, and publication PR #107 (`eb6108693c74ae9933b224db4e6786058b34e9d6`) closed the request. Align PR #891 (`4b515f8d37de2e9a9ba06170c5842fd12dc1cba2`) closed Request 19's provider-side compile-cost gap; align-llm adopted that merge, restored `prompt-verifier-smoke` to the hosted topology, passed its focused owner and the complete fresh-worker graph with the member restored, and publication PR #108 merged as `75d7cc39b40b287d47b1185306d6bd8e7eb582dc`. The request changes no target-local align-llm boundary, so the already-green Align platform CI owns compiler portability and no duplicate pin-bump platform qualification is selected. R0-GGUF-INSPECT then added Request 21, the missing read-only random-access `file` constructor: both constructors Align ships (`fs.create_rw` and `fs.open_rw`) demand `O_RDWR`, so inspecting a model requires write access to a file the client never writes. It is non-blocking — R0 ships on `fs.open_rw` with a documented writable-path precondition — and becomes blocking for the first consumer that must read a model from a read-only mount, a root-owned cache, or an image layer. R0-GGUF-INSPECT also added Request 22, the missing borrow-indexing of Move-element arrays (`array<string>`, arrays of a record with a Move field): `check_index` rejects it outright, so `src/gguf.align` carries deferred tensor `absolute_offset` values as a NUL-separated prefix stream plus a parallel `array<i64>` instead of an indexable record array. It is also non-blocking — the workaround is in place — with all of R0 as independent work.
> R1-QWEN-MODEL-IR then added Request 23, the huge-struct-copy lint firing on `borrow`/`borrow mut`
> parameters: it consults only the parameter's struct type and never its `ParamMode`, so all ten
> `borrow t: GgufTable` accessors in `src/gguf.align` get the by-value warning even though no call
> copies the 552-byte struct. It is non-blocking — the warnings are noise, not a build failure — with
> all of R1-QWEN-MODEL-IR as independent work. R1-QWEN-MODEL-IR also added Request 24, admitting
> `builder` (not just `array_builder<T>`) as a `borrow mut` parameter type: `array_builder<T>` is
> already admitted in that position at this pin, but the plain text `builder` is rejected as an
> unknown type, so `gguf.inspect` and `gguf.read_table` duplicate one decode-and-accumulate walk
> instead of sharing it through a borrowed builder parameter. It is non-blocking — the duplication is
> in place and `table-inspect-parity` guards the two walks from drifting — with all of
> R1-QWEN-MODEL-IR as independent work. R1-QWEN-MODEL-IR then merged as align-llm PR #122
> (`85a3a97` -> `08492dc`), closing no request but discharging the dense half of the R1 roadmap
> gate. R1B-GPTOSS-MOE-IR (`docs/specs/r1b-gptoss-moe-ir.md`) then merged as align-llm PR #123
> (`3bf5c9c` -> `d8d4ef6`), consuming no `PROPOSED` request and adding new client evidence to
> Request 23 (its narrower `BlockPlan` record) without changing any request's status; all of R1B was
> independent work for Requests 21–24. The active R2A-EXPERT-TRACE-CAPTURE
> (`docs/specs/r2a-expert-trace.md`) is the current consumer of Requests 21–24 and likewise consumes
> no `PROPOSED` request; it added new client evidence to Request 23 (a wide `borrow` record) and to
> Request 21 (a second class of read-only input), and it is **not** a client of Request 22: its
> node-name stream is spans into one concatenated `string`, so it holds no `array<string>` and
> avoids the shape that request names. R2A-EXPERT-TRACE-CAPTURE also added Request 25, the missing
> streaming/redirecting child-stdout surface on `std.process`: `command.run()` returns a child's
> entire stdout as one region-bound value and `process.spawn` does no redirection at all, so an
> align-native acquisition verb that invoked `llama-eval-callback` directly could not process its
> multi-hundred-megabyte transcript without materializing the whole thing first. It is
> non-blocking — R2A consumes a transcript file the shell already redirected into and never invokes
> the instrument itself — with all of R2A as independent work. R2A also added Request 26, the
> missing `str`-to-integer conversion in the standard library: Align has no
> `parse_i64`/`parse_int`/`to_i64` surface at this pin at all, so `src/main.align:71`,
> `src/failure_memory.align:176`, and `src/c6f1_request11_adoption.align:6` each route a plain
> decimal integer through a two-line `json.decode` detour, and `src/expert_trace.align:328` — whose
> `     12.0000` expert ids are not JSON numbers and must not travel through a float — writes the
> one genuine private parser instead. It is also non-blocking — the detour and the private parser
> are both in place — with all of R2A as independent work. R2A then added Request 27, string
> *sorting*: `str`/`string` already satisfy `Ord` and already back the four ordering operators and
> `sort_by_key`'s `str`-key comparator (`align_rt_str_cmp`), so the comparison R2A needs is
> shipped; what is missing is a sort that can consume it. Plain `array<T>.sort()` is
> compiler-restricted to numeric elements — an explicitly acknowledged "first cut"
> (`crates/align_sema/src/lib.rs:50612-50618`); `sort_by_key` *does* admit a borrowed `str` key
> (`docs/language-spec.md:252-253`) but cannot reach R2A's columns, because a lambda cannot capture
> the owned `array<i64>` span bounds yet and field access is only supported on a local binding; and
> there is no comparator-based `sort_by` overload, so `src/expert_trace.align` sorts an index
> array with a hand-written bottom-up merge and `src/model_ir.align` packs a 42-bit name hash into
> a sortable integer key instead of sorting or binary-searching by string directly. It is
> non-blocking — both workarounds are in place — with all of R2A as independent work. R2A finally
> added Request 28, a readable append-only accumulator: `builder` and `array_builder` are
> write-only until `build()`, so an interning table that must compare a candidate against text it
> has already accumulated cannot use either and `src/expert_trace.align` accumulates into a
> `buffer` plus pre-sized span columns instead. It is non-blocking — the `buffer` workaround is in
> place — with all of R2A as independent work.
> R4-ALIGNPACK-LAYER-MAJOR (`docs/specs/r4-alignpack-layer-major.md`) merged as align-llm PR #125
> (head `a7e72dc`, merge `991eab1`); it consumed no `PROPOSED` request and added Requests 29, 30,
> and 31. Request 29, an
> incremental digest: `crypto.sha256`/`sha512` are one-shot over exactly one byte view, so align-llm
> cannot digest a file larger than memory; R4 wanted a whole-payload digest so a pack could certify
> itself without re-reading the source and instead ships the bounded header-region digest of its own
> container, reserving the payload digest field. It is non-blocking — the reservation stands in —
> with all of R4 as independent work. Request 30, an exclusive random-access file constructor:
> `fs.create_rw` truncates (`O_TRUNC`) and `fs.create_exclusive` returns a sequential `writer` with no
> positional write, so a packer that must refuse an occupied multi-gigabyte destination and also write
> at planned offsets has no single constructor with both properties and instead documents a
> check-then-create race (`R4_DEST_EXISTS`) between `fs.exists` and `fs.create_rw`. It is
> non-blocking — the documented race is accepted — with all of R4 as independent work. Request 31,
> file durability: the runtime ships no `fsync`/`fdatasync`/`F_FULLFSYNC` at all, so no align-llm
> artifact is guaranteed to survive a power loss; R4 states this as a non-goal because a pack is a
> reproducible derivative of a file that still exists. It is non-blocking, low priority, with all of
> R4 as independent work; the first client that would need it is roadmap R6's persistent KV cache.
> R4-ALIGNPACK-LAYER-MAJOR also added new client evidence to Request 21 — opening a 4.68 GB model it
> never writes needs `O_RDWR` because Align ships no `fs.size`/`stat`, so even *sizing* a read-only
> model needs a writable descriptor, a third input class alongside R0's model and R2A's transcript —
> and to Request 23 — `PackPlan`, another wide columns-plus-stream record read through `borrow`
> accessors, is a fourth client of the same false-positive huge-struct-copy lint, with its concrete
> source line to be cited at implementation.
> R4.5-EXTERNAL-BUFFER-SPIKE (`docs/specs/r4-5-external-buffer.md`) merged as align-llm PR #126
> (`d46fce6` -> `fa567b1`), on `agent/r4-5-external-buffer` rebased onto that merge; it computes a real
> ggml matmul over an Align-owned quantized buffer, it consumes no `PROPOSED` request
> and added Requests 32 and 33. Request 32, FFI v1 by-value struct ABI (AAPCS64 and SysV MEMORY
> class) and `bool` FFI type: `ggml_init`'s 24-byte-by-value `struct ggml_init_params` and
> `ggml_tallocr_new`'s by-value return are unreachable from Align by any route — by-value struct
> passage is rejected at codegen on this target for both 16 and 24 bytes, the diagnostic's own
> by-pointer fallback is unavailable because a `layout(C)` struct cannot hold a `raw` field, and
> `bool` is rejected as an FFI type in either direction — forcing the C shim `scripts/ggml_shim.c`.
> It is non-blocking — the shim is in place — with all of R4.5-EXTERNAL-BUFFER-SPIKE and R5 as
> independent work. Request 33, aligned heap allocation: `ggml_backend_cpu_buffer_from_ptr` aborts
> the process unless its pointer is 32-byte aligned, but neither `buffer(n)` nor `raw.alloc(n)`
> guarantees any alignment — measured: `buffer(4096)` came back off a 16384-byte boundary while
> larger allocations happened to land page-aligned by this platform's `malloc`, not by any Align
> promise — so the design compensates for the allocator's base before every call that could assert,
> rather than relying on allocator luck or refusing what luck did not provide. It is non-blocking —
> the compensation stands in — with all of R4.5-EXTERNAL-BUFFER-SPIKE and R5's DRAM and VRAM tiers as
> independent work. Implementing R4.5-EXTERNAL-BUFFER-SPIKE then strengthened Request 33's evidence
> (the same 192-byte `buffer` measured 32-aligned on one run and 16-aligned on the next, correction
> C9), and its review strengthened it again: correction C14 measured a rule that consults that base
> refusing a legitimate member at interior offset **0** on 20 of 20 runs, so both device-visible
> windows are now over-reserved by 64 bytes and the block is read in behind its pad — the cost of
> the missing language feature, in bytes and in one copy per block. It also added two more requests.
> Request 34, `Result` ok payloads beyond scalars (`raw`, `buffer`, records): a `Result` ok payload
> must be a scalar at this pin, `raw` and `buffer` are both rejected (with two different
> diagnostics), and a plain struct cannot hold a `raw` field either, so `src/ggml_ffi.align`'s
> constructors return a bare `raw` with a null sentinel and
> `src/ggml_spike.align`'s reference reader threads its bytes out through a `borrow mut buffer`
> parameter instead of an owned return. It is non-blocking — the sentinel/out-parameter pattern is in
> place — with all of R4.5-EXTERNAL-BUFFER-SPIKE and R5 as independent work. Request 35, observable
> `buffer` capacity and allocation failure: `buffer(n)` is an advisory reservation that never fails
> (`buffer(2^62)` followed by one `put_u8` still publishes length 1) and has no `.cap()` accessor, so
> `R4_WINDOW_UNAVAILABLE` and R4.5's window-adjacent codes are guards for an observable consequence
> rather than for the reservation itself — the same conclusion R0 and R4 each reached independently.
> It is non-blocking — the observable-consequence guards are in place — with all of R0-GGUF-INSPECT,
> R4-ALIGNPACK-LAYER-MAJOR, and R4.5-EXTERNAL-BUFFER-SPIKE as independent work.
> R5A-DENSE-LAYER-FORWARD (`docs/specs/r5a-dense-layer-forward.md`) merged as align-llm PR #127
> (`0397228` -> `ccbd8ae`), rebased onto that merge; it computes one
> Qwen2 dense layer through ggml over Align-owned weights and checks it against
> `llama-eval-callback`'s own numbers. **Implementation is complete, reviewed, and repaired.** Design set
> out believing no new request was needed — section 5.5 of the plan states this explicitly ("No new
> request. Every gap R5A hit is already recorded") — and implementation confirmed that for every
> design-time gap, but refuted it twice more (section 6, corrections C8 and C9), adding Requests 36
> and 37. R5A added new client evidence to Request 34 — `raw` is refused not only as a struct field
> but as an **array element** (`error: array element must be a scalar (composite payloads are not
> supported yet), got raw`), which is why the thirty-two-node layer graph's `ggml_tensor *` handles
> live in a node-slot store, now citable at `src/layer_qwen2.align:13-16,24-38`, rather than an Align
> array of handles — and to Request 32 — two more `bool`-typed ggml entry points
> (`ggml_gallocr_reserve`, `ggml_gallocr_alloc_graph`) needed shim wrappers, now shipped at
> `src/ggml_ffi.align:744-754` and `scripts/ggml_shim.c:1069-1090`, and the same probe measured the
> request's positive complement: `f32` crosses the FFI by value in both directions and an unsuffixed
> float literal coerces at an `f32` parameter with no cast. It is also a new client, with no change to
> either request's text, of Request 21 (a fourth input class needing a writable descriptor to read a
> read-only model) and Request 35 (`buffer`'s advisory capacity, now paid per weight window), and it
> strengthened Request 33 with a shipped citation: the per-member alignment compensation
> (`src/layer_forward.align:1858`, `:1864`, `:2436-2439`) is paid thirteen times per run, once per
> weight member packed inside one over-reserved window, rather than the two R4.5 pays across its
> separate weight and output windows. Implementing R5A then added two requests of its own. Request 36,
> in-place replacement of owned array record fields and moving out of nested fields: an owned
> `array<i64>` struct field cannot be replaced in place and a nested struct field cannot be moved out
> of its parent, so the document's columns that section 3.7 designed as one `Outcome` every stage
> appends to instead live in eight single-assignment records (`src/layer_forward.align:898-1019`),
> each assigned exactly once, as a whole, by the stage that produces it. It is non-blocking — the
> eight-record shape compiles and ships — with all of R5A-DENSE-LAYER-FORWARD as independent work.
> Request 37, compiler check-time scaling for long function bodies and `match` on `Result` inside
> loops: per-function checking is superlinear in body length (a 400-line body checks in 40 s, a
> 900-line one does not finish in 600 s, measured at the pin) and a `match` on a `Result` with block
> arms inside a loop costs roughly 45 times the same loop written with `?` (90 s against 2 s), so
> `src/layer_forward.align` is split into fourteen functions, none over two hundred lines, with every
> in-loop fallible call routed through `?` and every top-level one through the two-line
> `take`/`take_pack` helpers (`src/layer_forward.align:1218-1234`) purely to keep `make check` in
> seconds rather than minutes. It is non-blocking — the refactor is in place and `check-per-unit
> src/layer_forward.align` is 6 s — with all of R5A-DENSE-LAYER-FORWARD as independent work. None of
> this is blocking: R5A ships entirely on the pinned surface, with all of R5A-DENSE-LAYER-FORWARD as
> independent work. R5B-MODEL-PREFILL-FORWARD (`docs/specs/r5b-model-prefill-forward.md`) merged as
> align-llm PR #128 (`3470646` -> `870bf31`), streaming the whole twenty-eight-layer Qwen2 model
> through one reused Align-owned window and checking it against llama.cpp's own final logits. It
> consumed no `PROPOSED` request. Design believed no new request was needed (section 5.5); as with
> R5A, implementation refuted that belief (section 6, corrections C1-C16) and adds three requests.
> Design-time client evidence for Requests 21, 32, 33, 34, and 36 stands unchanged in kind: the
> read-only pack open (Request 21) gets its fifth client, holding the file across fifty-eight `pread`
> groups and 4.4 GB; `Result` ok payloads beyond scalars (Request 34) is unchanged in kind and larger
> in degree, with 958 handles now passing through the slot store across thirty graphs; aligned heap
> allocation (Request 33) is paid once rather than R5A's thirteen times, on a window over-reserved by
> the same `MAX_TENSOR_ALIGNMENT` pad; FFI by-value structs and `bool` (Request 32) gets two more
> wrapped call sites; and owned `array<i64>` field replacement (Request 36) gets a `schedule[]` built
> the same one-record-per-column-set way correction C9 forced R5A's columns to be built. Request 37
> (per-function check time) shaped the module boundary as planned: `src/model_forward.align` exists
> as its own unit, and `check-per-unit src/model_forward.align` is under the section 5.5 budget.
> Implementation then found three requests section 5.5 did not name. Correction C5 (section 6) — the
> reused 447 MB window cannot be refilled through `buffer`'s append-only, always-full-capacity,
> write-from-index-0 surface, forcing the shim entry point `align_ggml_window_copy` and a 1 MiB
> transient — adds Request 38, positional write/reset and bounded-length `pread` for `buffer`.
> Correction C6 — `alignpack_read.read_exact`'s per-call `buffer(n)` rebind retaining every prior
> allocation for the caller's frame (peak resident set 3.4-4.3 GB against a 447 MB window, against
> 508 MB read through one buffer refilled in place) — adds Request 39, release of rebound `buffer`
> allocations before frame exit; the shipped arm avoids `read_exact` for the per-member read path
> entirely rather than pay that cost at 339 members. Implementation also found a struct-field gap
> section 6 does not separately name: `array_builder<T>`, unlike the plain-text `builder` Request 24
> covers, is admitted as a `borrow mut` parameter type but refused as a struct field
> (`error: struct field type is not supported here, got array_builder<i64>`), forcing
> `plan_layer_members` (`src/model_forward.align:863-908`) to take seven separate
> `borrow mut array_builder<i64>` parameters instead of one grouped record — Request 40. Correction
> C7 (section 6) — the region checker refusing to hold a `PackMember` across a second call taking the
> same `borrow mut Counters` — is *not* a request: it reproduces `docs/language-spec.md`'s documented
> rule that `borrow mut x: T` "ends the previous generation" on each call, so it is expected borrow
> behavior rather than a gap (recorded as an application concern in `HANDOFF.md`). Two further
> candidates considered during implementation did not reach a filed request: a suspected
> `check-per-unit`/whole-program `check` disagreement on `src/model_forward.align` did not reproduce
> against the finished tree (both report zero errors, with or without a cleared codegen cache, on
> `src/model_forward.align` alone and on the `ggml_spike.align` entry that imports it transitively),
> and a suspected move-out-of-an-`if`/`else`-expression restriction — real and sibling-documented,
> `crates/align_sema/src/lib.rs:35095-35098` — did not correspond to any site in the shipped
> `src/model_forward.align`: every conditional expression there selects a Copy scalar or view, never
> an already-bound owned Move local. Both are recorded as investigated-and-not-found in `HANDOFF.md`
> rather than as requests, since neither has align-llm consequence evidence to cite.
> R5C-METAL-PREFILL-ARM (`docs/specs/r5c-metal-prefill.md`) is now the active capability,
> handing R5B's same Align-owned window to Metal through
> `ggml_backend_dev_buffer_from_host_ptr` and checking the whole-model result against
> R5B's byte-identical CPU logits vector. **Implementation, both review repairs, and the
> qualification are complete and committed, the branch is rebased onto the merged R5B at `main`
> `870bf31`, and publication is in progress.** The probe record (section 2) refuted
> six of the plan's own assumptions before section 3 was written: Metal is
> **bit-deterministic** (five consecutive full-model runs byte-identical) rather than
> nondeterministic, needs **no** 16 KB alignment rule (the buffer-type alignment is 32,
> identical to the CPU's), the 447 MB window is **4.7%** of the device's 9,534,832,640 B
> buffer limit rather than needing a split, an oversize wrap **segfaults instead of
> returning null** (forcing a pre-wrap validation step, `R5C_DEVICE_BUFFER_LIMIT`), the
> per-layer residual comparison the plan intended to gate on is **dominated by one
> massive-activation channel** (row 2570) and is recorded but never gated, and the
> no-copy transfer R4.5 recorded as free costs a measured **354.8 ms over thirty wraps**
> (11.8 ms per 447 MB window, roughly 26 microseconds per MB, linear in length) against
> the CPU's 0.075 ms. Against the byte-identical `d2e48620…` vector, Metal's whole-model
> logits reach max `|Δ|` **2,937 ten-thousandths** (0.293651), `argmax` 671, the whole
> top ten identical in order, and zero elements over 0.5 — the measurement section 3.7's
> **6,000 ten-thousandths** tolerance bound is derived from (twice the measured worst
> case, rounded up to the next thousand). GPU compute is 523.3 ms against the CPU's 500.7
> ms — 2.07× faster on the head and 1.58× slower on the narrowed last layer — and end to
> end the GPU arm is a measured **1.20× slower**, a negative result recorded as the cost
> ceiling before implementation and reported as microbenchmark A's honest outcome rather
> than absorbed. R5C discharges required microbenchmark A on unified memory; required
> microbenchmark C (async prefetch of the next layer's window while the current graph
> computes) cannot be written at this pin and is deferred with Request 41 named. R5C's
> design also set out to file "impure/I-O work inside `task_group`" as a candidate
> request and instead measured that it already works — `spawn` accepts `fs` I/O and
> `extern "C"` FFI cleanly, and purity binds `par_map` alone
> (`docs/guide/10-closures-and-parallelism.md`, `docs/language-spec.md`) — so it adds
> Request 41 instead, non-`Copy` capture in `spawn` closures: a prefetch task must own
> (or exclusively borrow) the Align-owned window it fills, and neither capturing it nor
> returning a filled `buffer` from a spawned task compiles at this pin. It is
> non-blocking for R5C itself — the arm ships on microbenchmark A alone — and blocks only
> R5 microbenchmark C, which stays deferred rather than worked around, since the
> compiling `i64`-address alternative is deliberately not proposed (it would put the
> window's bounds outside Align's view). R5C's implementation then met a fourth gap, in
> the region checker rather than in `spawn`: the plan's module split —
> `src/gpu_forward.align` calling `src/model_forward.align`'s `execute` and reading its
> four `borrow mut` column-set out-parameters itself — checked clean and failed only at
> `alignc build`, with `use of invalidated borrow 'schedule': its source 'tokens' was
> moved or reassigned` for the direct read and `cannot return a view that borrows local
> storage` for the alternative of returning the columns bundled in one record (section 6
> correction C5). This adds Request 42, `alignc check` (and `check-per-unit`) not being a
> superset of `alignc build` for region-checker diagnostics — reproduced fresh in a
> minimal two-module probe under the pinned compiler — and Request 43, the specific
> cross-module `borrow mut` record out-parameter gap C5 hit. Neither blocks R5C: the
> shipped shape is `model_forward.render_parts` (`src/model_forward.align:3226-3253`),
> which renders each column set to a `string` inside the module that produces it and
> returns those strings beside `Outcome`, the one shape all three of C5's refusals allow.
> R5C is additionally new client evidence for five
> existing requests, none of them newly blocking: Request 37 (per-function check time)
> shapes the module boundary again, putting the GPU arm in a new `src/gpu_forward.align`;
> Request 34 (`Result` ok payloads beyond scalars) is now also the mechanism behind
> Request 41's second half; Request 33 (aligned heap allocation) is paid once rather than
> R5A's thirteen times; Request 32 (FFI by-value structs and `bool`) gets three more
> wrapped call sites; and Request 21 (a read-only open) gets its sixth client.
> R5C-METAL-PREFILL-ARM then merged as align-llm PR #129 (`c025ee2` -> `39c69a2`), closing no
> request and adding no new client evidence beyond the five requests named above. With R5C merged,
> R0 through R5C are complete on the dense local model, and every remaining roadmap item was
> blocked on a user decision or an Align-side change (`HANDOFF.md`). The user then took the small
> MoE GGUF decision, downloading `OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf` (3.92 GiB, 64 experts,
> top-8 routing), which named two consumers at once: **R2-LOCALITY-GATE** ran the R2 locality
> measurement against that real model and merged as align-llm PR #131 (`fff5806` -> `546b5cc`) with
> the gate met in the prefill direction, and **R1C-OLMOE-MOE-IR**
> (`docs/specs/r1c-olmoe-moe-ir.md`, design ledger commit `83361a9`) implemented a new
> `src/frontend_olmoe.align` and a three-way architecture dispatch and is now in publication.
> Neither consumes a `PROPOSED`
> request; R1C's design section 5.4 records that no new genuine Align gap is expected and that
> `src/frontend_olmoe.align` becomes **the third frontend** at which the already-`PROPOSED`,
> non-blocking Request 23 misfires — not a third client, since this register already carries four
> (`GgufTable`, `BlockPlan`, `TranscriptScan`, `PackPlan`). R1C is now implemented at
> `45e4ced`, and the shipped evidence is under Request 23 below: the warnings land on the
> frontend's three `borrow … : gguf.GgufTable` parameters, not on the `borrow BlockPlan` the
> design ledger predicted, and no new genuine Align gap was encountered. `gpt-oss-20b-mxfp4.gguf` (12.1 GB) is now recorded **infeasible on this host** (disk
> free ~16 GiB after the olmoe download) and remains the next consumer for R1B's real-model
> `model-ir-parity` qualification whenever a host with more free space is available; a source build
> of llama.cpp at `bb4caa754` plus the R2c minimal instrument patch is still the next consumer for
> R6 (Persistent KV) and, through it, R7-R9; and Request 41 itself is still the next consumer for
> R5's deferred required microbenchmark C. None of these decisions changes any request's status;
> Requests 21-43 remain PROPOSED and non-blocking, and none has merged since R0.
> R3-RESIDENCY-SIM (`docs/specs/r3-residency-sim.md`) is now the active capability, on branch
> `agent/r3-residency-sim`, rebased onto the merged MoE prerequisites at `main` `35a0df6` so that
> the corrected `src/expert_trace.align` its qualification depends on now comes from `main` rather
> than from a prerequisite carried on the branch. **Implementation and review are complete;
> publication is the only remaining step.** It simulates ten expert-residency cache policies against a
> real-model activation-trace corpus and discharges the roadmap R3 gate: at the requested 250-per-
> mille budget, `recent_reuse_w32` beats the `lru` baseline by 223 per mille with headroom 574 per
> mille to the offline optimum, a 40-fold leave-one-document-out jackknife minimum gain of 213 per
> mille, `BEATS_BASELINE`. It consumes no `PROPOSED` request. Implementation added two requests and
> strengthened three. Request 45 is a compiler soundness defect, not a missing admission: the region
> checker silently accepts a move of a Move-typed field out of a `json.decode`d record through a
> two-hop field-access chain (`document.run.build_source`) with no diagnostic, and the built program
> aborts at run time — a heap-corruption trap, not a clean `SIGABRT` — when the decoded record's
> recursive `Drop` frees the same string a second time; reproduced fresh in a minimal probe under the
> pinned compiler, with a root cause traced to struct-literal field values never setting the move
> checker's `consuming` flag. It is non-blocking — the shipped fix is one `.clone()`
> (`src/residency_sim.align:624-634`) — with all of R3-RESIDENCY-SIM as independent work. Request 46
> is two related array-shape gaps, distinct from Request 36's whole-field-replacement restriction,
> that together force every helper in the module to return owned columns instead of writing through
> `borrow mut` out-parameters: a local `array<i64>` passed `borrow mut` to a call inside a `loop`
> invalidates the caller's later reads of it (a record or `buffer` in the same position does not),
> and an `array<i64>` field of a record cannot be element-assigned at all. It forces `replay`'s
> eviction-and-insert admission block (`src/residency_sim.align:660-920`) to be written twice rather
> than factored into one helper. It is non-blocking — the duplication is in place and checked against
> an independent oracle — with all of R3-RESIDENCY-SIM as independent work. R3 also strengthens
> Request 21 with a narrower client of the `fs.size`/stat absence specifically (R3 itself needs no
> `fs.open_ro`, since `fs.read_file` does not demand `O_RDWR`), Request 23 with a sixth wide-record
> `borrow`-parameter false positive (`residency_sim$Derived`), and Request 26 with a second private
> `str`-to-integer parser (`parse_budget`) that a `json.decode` detour and the existing `parse_uint`
> both fail to match. None of this changes any request's status; Requests 21-43 and 45-46 remain PROPOSED and
> non-blocking, and none has merged since R0.
> **Request 1 (`std.process` capture) — COMPLETE** across #630/#631/#632 (bar the deferred bytes tier):
> `c := process.command(cmd,args)` + `c.cwd(dir)` + `c.timeout_ns(ns)` + `c.env(name,value)` +
> `c.env_clear()` → `out := c.run()?` with `out.code()/.stdout()/.stderr()`. A timeout kills the child's
> process group and returns `Err(Error.Timeout)` (distinct from a nonzero exit / transport `Error.Code`).
> **align-llm can build its verify/repair loop now** — capture + timeout paths verified end-to-end on
> the shipped compiler (see "align-llm verification" under Request 1). (`out.stdout()/.stderr()` are zero-copy `str` views
> region-bound to `out`; `.clone()` to persist past `out`'s scope. Non-UTF-8 output → `Error.Invalid`;
> the raw-bytes tier is deferred — flag it if you hit non-UTF-8 tool output.)
> **Request 2 (http/net I/O timeouts) — COMPLETE** across #633 (net rail: `tcp.connect` connect-timeout
> substrate + `conn.read_timeout_ns`/`write_timeout_ns`) and #634 (http: `http.client().timeout(ns)`
> default + `http.request(...).timeout(ns)` per-request override). A connect/read/write that overruns →
> `Err(Error.Timeout)`, for both plaintext AND HTTPS/TLS; `ns==0` (the default) preserves the current
> blocking behavior. So an LLM-API call that hangs no longer stalls the loop — set `cl.timeout(ns)`
> (client default) or `r.timeout(ns)` (per request). Specs:
> `../align/docs/impl/std-design/process.md` (R1), `../align/docs/impl/std-design/http.md` + `net.md` (R2).
> **Request 3 (`core.json` scalar-array struct fields) — COMPLETE** (#635). `json.decode` now accepts
> a struct field of type `array<str>` (the C0 eval-task `argv` shape); `array<i64>`/`array<f64>`/
> `array<bool>` fields and `array<str>` encode were already shipped, so all scalar-array struct fields
> now round-trip. A decoded `array<str>` element is a zero-copy `str` view into the input (persist with
> `.clone()`, like the top-level `str`-field rule); a JSON-escaped element decodes to `Err` (the
> pre-existing zero-copy `str` limit). Top-level `array<str> := json.decode` stays deferred (a struct
> field rides the enclosing struct's input-region binding; a top-level array result would carry that
> region itself — a separate slice). Spec: `../align/docs/impl/core-design/json.md`.
>
> **Sequencing (align-llm view, 2026-07-24).** Neither R2 nor R3 blocks align-llm's next work
> (verify/repair loop skeleton + C0 eval), which build on R1 (shipped) alone. When urgency does
> arrive it is **R3 > R2**, the inverse of the Align-side queue order: R3 (json scalar arrays) has
> **no clean workaround** for LLM API bodies (`stop: array<str>`, `embedding: array<f64>`) and becomes
> a hard blocker the moment the provider layer is built; R2 (I/O timeouts) has the `ns == 0`
> no-timeout fallback, so a first provider call works without it. Plan: proceed on the loop/eval now,
> escalate R3 with a concrete failing API-body decode once the provider layer is reached, and let R2
> ride Align's existing DESIGNED queue.

---

## Request 1 — `std.process`: child output capture (+ working directory, environment, timeout)

```text
Status: CLOSED
Priority: critical
Blocking: yes
Blocked gate or slice: provider-independent verification loop
Independent work that may continue: evaluation and architecture work not requiring child capture
Resume condition: capture, cwd, and timeout pass in align-llm with the pinned Align release build
Align commit or pull request: #630 927f6eb, #631 43b6af2, #632 5856c00
align-llm verification: capture and timeout runtime gates PASS; make ci PASS
```

### Motivation

`align-llm`'s central job is to run build/test/lint commands (`git`, `make check`, a test runner)
and **parse their output** to extract structured errors, summarize failures, and generate repair
prompts. Reading a child process's `stdout`/`stderr` as strings is therefore fundamental, not
optional.

### Current state in Align

`std.process` (design: `docs/impl/std-design/process.md`, status "complete in M11") provides:

```text
process.spawn(cmd: str, args: array<str>) -> Result<child, Error>   // fork + execvp
child.wait() -> Result<i64, Error>                                   // reap, return exit code only
child.kill(sig: i64) -> Result<(), Error>
process.exec / exit / abort / cpu_count
```

The runtime (`crates/align_runtime/src/lib.rs`, `align_rt_process_spawn`) does a bare `fork` +
`execvp`: it installs **no pipes and no `dup2`**, so the child inherits the parent's file
descriptors and its output goes straight to the terminal. The `Child` handle is only
`{ pid: i32, reaped: bool }`. Consequently:

- **Capturing `stdout`/`stderr` as strings: not possible.** No `process.output` / `process.run`
  surface exists.
- **Working directory (`cwd`): not possible.** `spawn` has no `cwd` argument; there is no
  `chdir` / `set_cwd` anywhere in `std`.
- **Per-child environment: not possible.** The child inherits the parent environment only.
- **Timeout: not possible.** `wait()` blocks indefinitely; there is no `try_wait` equivalent.

Notably, output capture / `cwd` / timeout are **not present in `process.md`'s design space** — the
only recorded deferrals there are `detach()` and a `Never` type. So this is a genuinely new,
real-workload-motivated requirement, not a planned gap.

### Requested capability

A way to run a child process and collect its captured output, working directory, environment, and a
timeout. A single high-level call fits the workload well; the exact surface is Align's design
decision. A sketch consistent with the existing idioms (Move handles, `Result`, *Nothing hidden*):

```text
// One-shot run with captured output. All non-cmd/argv fields optional.
process.run(cmd: str, args: array<str>, opts?) -> Result<output, Error>
  where output = { code: i64, stdout: string, stderr: string }   // or a merged stream option
        opts   = { cwd?: str, env?: <name,value pairs>, timeout_ns?: i64 }
```

Alternatively, extend the existing `spawn`/`child` model with explicit stream redirection
(pipe + `dup2`), a `cwd`/`env` on spawn, and a `wait_timeout(ns)` — whichever composes better with
Align's stream (`reader`/`writer`) design. Output capture and `cwd` are the two must-haves; `env`
and `timeout` are strongly wanted (a hung test currently freezes the whole loop).

### Design considerations

- *Nothing hidden*: captured output must be an explicit, owned value the caller reads — no hidden
  process-wide buffer. Fits the existing "buffered-writer output is never silently lost" stance.
- UTF-8: build/test output may not be valid UTF-8. Either validate and error (consistent with
  `fs.read_file`), or offer a bytes-returning tier alongside the `string` tier (mirroring
  `read_file` vs `read_bytes_view`). A bytes tier is safer for arbitrary tool output.
- Timeout semantics: on expiry, `SIGKILL` the child and surface a distinct `Error` variant so the
  caller can tell "timed out" from "exited nonzero".

### Acceptance / gate

Spawn a command that writes to both `stdout` and `stderr` and exits nonzero; the caller recovers the
full `stdout` string, the full `stderr` string, and the exit code. Running a command in a specified
`cwd` observes that directory. A command that exceeds `timeout_ns` is killed and reported as a
timeout rather than blocking.

### References

- `crates/align_runtime/src/lib.rs` — `align_rt_process_spawn`, `align_rt_child_wait`,
  `Child` struct.
- `crates/align_sema/src/lib.rs` — `check_process_spawn`, `check_process_op`, child method
  dispatch.
- `docs/impl/std-design/process.md` — the module design spec to extend.
- `crates/align_driver/tests/m11_process.rs` — current tests (exit/abort only).

### Align response (2026-07-24 — ACCEPTED, designed; implementation pending)

Accepted and designed in the Align repo. Full spec: `../align/docs/impl/std-design/process.md` →
the "Extension — captured output + cwd / env / timeout" section.

**Surface.** Align has no optional/named/default arguments, so an `opts?` trailing argument is not
expressible. The chosen form follows Align's one existing optional-configuration idiom — the
`std.http` request builder (a bound-local Move handle mutated by `()`-returning setters, *not* a
fluent chain):

```text
c := process.command(cmd: str, args: array<str>) -> command   // Move handle
c.cwd(dir: str)                    // -> ()
c.env(name: str, value: str)       // -> ()   add/override one variable
c.env_clear()                      // -> ()
c.timeout_ns(ns: i64)              // -> ()   kill + Err(Timeout) past ns
out := c.run() -> Result<run_output, Error>
out.code() -> i64 ;  out.stdout() -> str ;  out.stderr() -> str
```

**On `output = { code, stdout, stderr }`.** A by-value builtin struct owning *two* heap strings is a
capability Align does not have yet (a `Result` `Ok` payload is a single scalar; a value aggregating
multiple owned allocations is the deferred "first-class builtin-struct return" — the same wall
`std.net`'s `datagram { n, peer }` hit). Align's realized idiom for "a returned value that owns heap"
is a single opaque Move handle read through accessors — exactly how `http.response` works
(`resp.status()/.header()/.body()`). So `run_output` is that handle; `.stdout()`/`.stderr()` are
zero-copy `str` views (region-bound to `out`, like `resp.body()`). This is the ideal form within
Align's current design, not a workaround: the by-value-struct spelling would require building the
separate deferred feature first and would then be a second way to do the same thing.

**Must-haves + strongly-wanted, all in.** Output capture, `cwd`, `env`/`env_clear`, and `timeout_ns`
are all designed. The runtime is pipe + `fork` + `dup2` + **both-fd `poll` drain** (two-pipe
deadlock is the #1 correctness point) + deadline `SIGKILL`.

**Timeout is distinguishable.** On overrun the child is `SIGKILL`ed and the run returns the new
`Error.Timeout` variant (a 5th core `Error` variant added by this work and shared with Request 2), so
the caller tells "timed out" apart from "exited nonzero" apart from a transport error.

**UTF-8.** `run()`'s `str` accessors validate UTF-8 and return `Error.Invalid` on invalid bytes
(consistent with `fs.read_file`). A bytes tier `run_bytes()` (`.stdout()/.stderr() -> slice<u8>`,
no validation — mirroring `read_file` vs `read_bytes_view`) is designed and deferred; it ships on
demand if non-UTF-8 tool output proves real for `align-llm`. Flag it if you hit non-UTF-8 output.

**Slices (implementation order).** S4 = both must-haves (`command`/`run_output` + captured output +
`cwd`) — the critical blocker, lands first; S5 `timeout_ns` + the `Error.Timeout` core change; S6
`env`/`env_clear`; S7 (deferred) the bytes tier. `align-llm` can start against S4 (capture + code +
cwd) and layer in `timeout`/`env` as S5/S6 land.

### align-llm verification (2026-07-24 — CONFIRMED against the shipped compiler)

Verified end-to-end against the current `../align` compiler (rebuilt `cargo build --release` to refresh
the runtime staticlib first). The surface is adopted in `src/verify.align::run_captured`, and all four
project units (`project`, `verify`, `eval`, `main`) pass `make check` per-unit and `make build` links.

- **Capture gate — PASS (runtime).** A child writing to stdout and stderr and exiting nonzero recovers
  all three distinctly: `process.command("/bin/sh", […, "printf HELLO; printf OOPS 1>&2; exit 7"])` →
  `out.code()` = `7`, `out.stdout()` = `HELLO`, `out.stderr()` = `OOPS`.
- **Timeout gate — PASS (runtime).** `sleep 10` under `c.timeout_ns(100_000_000)` returns
  `Err(Error.Timeout)` — the `Timeout` match arm fires (distinct from `Ok`/nonzero-exit/`Code`) and the
  process returns in ~0.4 s, not 10 s, so the child is killed at the deadline rather than waited out.
- **`cwd` and `timeout_ns`** are wired through `run_captured`; the `str` views are region-bound to
  `out` and consumed at the call site (printed while the handle is live) as designed. The shipped
  `env` / `env_clear` setters are available for the future provider-command client, but this wrapper
  does not expose them and makes no claim to test them.

No non-UTF-8 tool output encountered yet, so the deferred bytes tier is not needed today; will flag if
that changes. **Request 1 is closed from align-llm's side** — the verify/repair loop can build on it.

### align-llm build finding (2026-07-24 — the provider-independent coding loop, built on R1)

The provider-independent coding loop now exists (`src/repair.align::drive` + `src/verify.align::run`
returning an owned `Captured { status, code, stdout, stderr }`), verified end-to-end: an
already-passing check converges in 1 iteration, a persistent failure with a declining provider ends
`GAVE_UP`, and a provider that actually repairs converges in 2 iterations (verify → repair → verify).

Building it surfaced **exactly the deferred "first-class builtin-struct return" wall the R1 response
named** — now hit for a *user* Move struct: a struct owning heap `string` fields **cannot be a
`Result` Ok payload** (`error: Result ok payload cannot be the Move struct 'Captured' yet (its owned
fields would not be dropped)`). A **bare** Move-struct return (`-> Captured`) and a single owned
`Result<string, Error>` both work. **Not blocking, no new request:** the native idiom is to fold the
run outcome into a `status` enum field and return the struct bare, which is a good fit here (the loop
wants to inspect diagnostics, not `?`-propagate). This is noted only as a data point for that deferred
item — the ergonomic cost is losing `?` on such a value; flag it if a fallible multi-owned-field
return where `?`-propagation is genuinely wanted shows up.

Two smaller Align idioms worth recording (not requests): an owned `string` does **not** auto-borrow to
`str` across an *indirect* (function-value) call — bind it to a `str` local first; and a command
`argv` reused across loop iterations must be a borrowed `slice<str>` (materialized per run with
`.to_array()` for `process.command`), since an owned `array<str>` is moved on the first call.

---

## Request 2 — `std.http` / `std.net`: I/O timeouts

```text
Status: CLOSED
Priority: high
Blocking: no
Blocked gate or slice: none; the C6-MEASURED provider consumer in `src/provider_http.align` consumes the shipped per-operation deadline
Independent work that may continue: all work
Resume condition: complete
Align commit or pull request: #633 98b1712, #634 1b21cdb
align-llm verification: the named focused owner `c6e-request2-adoption` (`scripts/run-http-timeout-adoption-smoke`, `src/c6e_request2_adoption.align`) passes at Align `2f33ac5c33a898a7894af58322852632ce6ffe42`, proving the plaintext read-stall and the TLS handshake-stall both return `Error.Timeout` inside a `timeout_ns` of 250,000,000 (observed 258,576,584 ns and 296,394,625 ns) with a responsive control request at 1,529,083 ns; the target is a `HOSTED_CHECK_TARGETS` member, so it runs in every hosted and capable check graph. At the C6-MEASURED review-repaired head `e14c472b11abcbb2368a93d1fd4c97d3554f11e4` on native Linux `aarch64`, `c6e-request2-adoption` passes together with every other `HOSTED_CHECK_TARGETS` member and with `eval-coding` and `c6-evaluation-adoption`, and the wired `make prompt-gate-check` with all five explicit `C6_GATE_*` values exits 0 (`prompt gate validator: PASS`). **The final supervised `make ci` leg is met.** At head `3768ad8af68bb50ee3129ff392f6ba86ac89e071`, `python3 scripts/run-fresh-worker-qualification --installed-profile-only --require-docker --align-repo <path-to-sibling-align-checkout>` exits 0 with `fresh image profile smoke: PASS` and `fresh worker qualification: PASS (installed profile only)`. That request is the trusted image entrypoint's `make --no-print-directory ci`, so the whole `capable-checks` graph — including this request's `c6e-request2-adoption` — ran inside the authenticated fresh worker. Phases: `docker-daemon` 675 ms, `image-build` 21,883 ms, `image-attestation` 3,822 ms, `profile-lifecycle` 3,188 ms, `profile-self-test` 14,331 ms, `trust-mutations` 13,151 ms, `runtime-replacements` 22,893 ms, `boundary-profile` 270,909 ms, **`worker-aggregate` pass after 354,739 ms**, `cleanup` 1,883 ms; whole installed profile 708,521 ms. The two causes of the earlier failure were the `prompt-verifier-smoke` code-generation cost (removed by demoting that member; see Request 19) and `prompt-measurement-adapter-smoke`'s Git fixture resolving `git` against a hard-coded host PATH instead of the aggregate's tool root (repaired in `3768ad8`); both were pre-existing C6-MEASURED wave gaps rather than review-repair regressions.
```

### Motivation

`align-llm` calls OpenAI-/Anthropic-compatible HTTPS endpoints (`POST /v1/chat/completions`). A
model endpoint can hang or black-hole a connection. Without a timeout, the coding loop can stall
indefinitely on a single request, which is unacceptable for an automated verify/repair loop.

### Current state in Align

`std.http` is otherwise sufficient for the client: `http.client()`, `http.request("POST", url)` with
`r.header(name, value)` and `r.body(...)`, `cl.request(req)`, HTTPS via the system trust store,
response `status()`/`header()`/`body()`. **But there is no timeout on connect, read, or write.** The
runtime records this explicitly:

- `crates/align_runtime/src/lib.rs` — "sets no connect timeout (a hung/black-holed peer blocks
  indefinitely)" and "I/O timeouts stay a net-rail follow-up".

So unlike Request 1, this is **already an acknowledged deferred item in Align**. `align-llm` simply
provides the concrete client demand that justifies pulling it forward.

### Requested capability

Configurable connect/read/write (or overall-deadline) timeouts on the HTTP client and/or the
underlying `std.net` sockets. Surface is Align's choice; a per-client default plus a per-request
override is the common shape. A transport timeout should surface as an `Error` (consistent with
"transport/TLS/malformed-message failures are errors; an HTTP status is data").

### Acceptance / gate

A request to an endpoint that accepts the connection but never responds returns an `Err` (timeout)
within the configured bound instead of blocking indefinitely.

### References

- `crates/align_runtime/src/lib.rs` — HTTP/TLS client path ("Slice 5"), connect/read/write sites,
  and the recorded timeout follow-up comments.
- `crates/align_sema/src/lib.rs` — `check_http_client` and client method dispatch.
- `docs/impl/std-design/http.md`, `docs/impl/std-design/net.md` — module design specs to extend.

### Align response (2026-07-24 — ACCEPTED, designed; implementation pending)

Accepted; this pulls forward the already-acknowledged deferred item (G3-1). Full spec:
`../align/docs/impl/std-design/http.md` → "I/O timeouts", and `../align/docs/impl/std-design/net.md`
→ "I/O timeouts".

**Surface.** One knob, `timeout(ns)`, set as a per-client default and per-request override (the same
`()`-returning bound-local setters as `r.header()`):

```text
cl := http.client() ;  cl.timeout(ns)        // client default (0 = no timeout, unchanged behavior)
r := http.request("POST", url) ;  r.timeout(ns)   // per-request override
```

Not split into connect/read/write — a single `ns` is applied as the deadline for **each** blocking
operation (connect, send, receive), which bounds both "never accepts" and "accepts then never
responds" with the simplest surface. This is a per-operation deadline, not a single wall-clock
deadline across the whole request (deadline arithmetic threaded through every op buys little here).
For raw sockets, `std.net` exposes `c.read_timeout_ns(ns)` / `c.write_timeout_ns(ns)` directly.

**A timeout is `Error.Timeout`** — the new distinct variant (shared with Request 1), separate from
`Error.Code` (transport errno), `Error.Denied` (TLS verification), and an `Ok(response)` carrying a
4xx/5xx status. Meets your gate ("surface as an `Error`").

**Runtime.** Align uses raw libc sockets, so: connect timeout = the net-rail non-blocking
`connect` + `poll(POLLOUT)` substrate (`align_rt_tcp_connect` gains a `timeout_ns` param — its
recorded ideal home); read/write timeout = `SO_RCVTIMEO`/`SO_SNDTIMEO` (bounds the TLS `SSL_read`
path too, same fd). `ns == 0` preserves today's blocking behavior exactly.

**Gate.** A peer that accepts then never responds returns `Err(Timeout)` within the bound; a
black-holed (never-accepting) address returns `Err(Timeout)` within the bound.

### align-llm verification (2026-08-25 — CLOSED)

C6-MEASURED shipped the consuming provider transport, so the original acceptance gate is now
exercised by a real client. `src/provider_http.align` applies the configured `timeout_ns` to every
blocking operation, and `src/c6e_request2_adoption.align` drives it against three loopback
listeners: a plaintext listener that accepts and never answers, a listener that accepts and never
answers the TLS ClientHello, and a responsive control. Both stalls classify as `Error.Timeout`
inside the configured bound, the control exchange is untouched, and the client still works after two
timed-out connections. `scripts/run-http-timeout-adoption-smoke` independently bounds the whole
run's wall clock and rechecks each reported per-row timing.

`c6e-request2-adoption` is now a member of `HOSTED_CHECK_TARGETS`, so it is a permanent part of the
hosted and capable check graphs rather than a target that must be remembered separately. The
shipped surface, ownership, and limits are recorded above; merged publication evidence is named
below.

The C6-MEASURED review repair first ran the supervised publication route named by the review and it
failed inside the fresh worker's `capable-checks` aggregate. The failure was never attributable to
this request's surface — it reproduced unchanged at the pre-repair reviewed head — and it is now
diagnosed and repaired. It had two independent causes, both C6-MEASURED lane additions that the
supervised aggregate had never exercised: the `prompt-verifier-smoke` code-generation cost, and
`prompt-measurement-adapter-smoke` resolving `git` for its patch fixture against a hard-coded
`/usr/bin:/bin` child PATH rather than the aggregate's tool root. With both closed, the supervised
`make ci` request passes at `3768ad8af68bb50ee3129ff392f6ba86ac89e071`, so this request's final
`make ci` leg is met. C6-MEASURED merged as align-llm PR #103
(`c9a510dc6ef4dc123f586eb33f447f02348061fb`), completing the publication evidence and closing this
request.

---

## Request 3 — `core.json`: decode/encode scalar-array struct fields (`array<str>`, `array<i64>`, …)

```text
Status: CLOSED
Priority: medium
Blocking: no
Blocked gate or slice: none at filing; would block the C0 file loader and provider JSON consumer
Independent work that may continue: code-defined C0 tasks and verify/repair loop work
Resume condition: declared task records with argv: array<str> decode and run in align-llm
Align commit or pull request: #635 a32a025
align-llm verification: smoke-v1 decodes, re-encodes, decodes again, executes argv, and passes make ci
```

### Motivation

`align-llm`'s C0 fixed-eval set defines each coding task as data — an id, a validation command, and
its **argv** (`array<str>`) — pinned in a file so the same task reproduces the same score. Loading
that corpus from `eval/tasks/*.json` via `json.decode` into a declared task record is the natural,
provider-independent shape. The same need recurs across every LLM API body `align-llm` must parse or
build: OpenAI/Anthropic chat bodies carry `stop: array<str>`, `tags`, tool-name lists, and embedding
responses carry `data[].embedding: array<f64>` — all scalar arrays as struct fields.

### Current state in Align

`json.decode`/`json.encode` recurse through int/float/bool/str, nested structs, the
decode-eligible scalar/`str` and Copy-struct `Option` forms,
**`array<struct>`**, and enum-unions — but reject a struct field whose type is an **array of
scalars**. Verified against the compiler on 2026-07-24:

```text
// Spec { id: str, cmd: str, argv: array<str>, expected_code: i64 }
r: Spec := json.decode(s)?
// error: 'json.decode' field 'argv' has type array<str>
//        (int/float/bool/str/nested-struct/Option/array<struct>/enum-union only for now)
```

So `array<Struct>` decodes but `array<str>` / `array<i64>` / `array<f64>` do not. The "only for now"
wording marks it as a recognized, not-yet-built extension, not a design exclusion. `array<struct>`
already proves the array-decode machinery exists; this asks to also admit a scalar element type.

### Requested capability

`json.decode` and `json.encode` accept a struct field of type `array<T>` where `T` is a JSON scalar
(`str`, `i64`, `f64`, `bool`) — decoding a JSON array of scalars into the owned `array<T>` and
encoding it back. Element ownership mirrors the existing `str`-field rule: decoded `str` elements are
zero-copy views into the input (persist with `.clone()`), consistent with the top-level caveat in
"Not requested" below.

### Design considerations

- Consistent with Align's declared-record stance — this is **not** a dynamic JSON value type; the
  field's element type stays statically declared. It only widens the admitted element types of an
  already-supported array field from `struct` to also include scalars.
- Encode must round-trip in declaration order, same as every other field.
- Empty array `[]` → an empty owned `array<T>`; a `null` for an `Option<array<T>>` field → `None`
  (matching the existing missing-key/`null` → `None` rule).

### Acceptance / gate

A record with an `array<str>` field (and, ideally, `array<i64>`/`array<f64>`) round-trips:
`json.decode` populates the array from a JSON scalar array, indexing returns the elements, and
`json.encode` renders the same array back in declaration order.

### References

- `../align/crates/align_sema/src/lib.rs:17287` — the `json.decode` field-type gate (lists the
  admitted types; `array<struct>` in, `array<scalar>` out).
- `../align/crates/align_sema/src/lib.rs:17512` — the matching `json.encode` gate.
- `../align/docs/impl/core-design/json.md` — the module design doc to extend.
- `../align/examples/json_nested.align` — nested-struct decode precedent; `array<Choice>` noted there
  as "Slice C" (array-of-struct), the sibling of this request.

### align-llm state at filing

At filing, `align-llm` did **not** work around this. The C0 harness used code-defined tasks while the
JSON `eval/tasks/*.json` loader waited for the capability.

### Align response (2026-07-25 — COMPLETE, shipped #635)

Shipped. `json.decode` now accepts a struct field of type `array<str>`. Note the state had already
moved past this request's 2026-07-24 snapshot: `array<i64>`/`array<f64>`/`array<bool>` struct fields
(and `array<str>` **encode**) were already shipped (the "T1b" JSON-completeness slice), so the only
remaining gap was `array<str>` **decode** — which #635 closes. So the C0 eval-task loader's
`Spec { id: str, argv: array<str>, code: i64 }` round-trips now:

```text
r: Spec := json.decode(task_json)?     // argv:["git","status","--porcelain"] → owned array<str>
r.argv[2]                              // "--porcelain"
json.encode(r)                         // renders the array back in declaration order
```

**The ownership model to know as a client:** a decoded `array<str>` element is a **zero-copy `str` view
into the input JSON buffer** — the same rule as a top-level `str` field. The owned array spine borrows
the input, so the decoded struct is input-region-bound; to persist an element past the input's lifetime,
`.clone()` it (identical to the caveat already noted for `str` fields under "Not requested"). One
inherited limit: a JSON string element containing an **escape** (`\`) decodes to `Err` (zero-copy can't
unescape — the same pre-existing limitation as an escaped `str` field); align-llm's argv / tag / stop
lists are unescaped in practice. Also still deferred (not requested, no consumer): a **top-level**
`array<str> := json.decode("[...]")` (a struct FIELD rides the enclosing struct's input-region binding;
a top-level array result would have to carry that region itself — the scalar top-level array is
deliberately `Static`/returnable, so `array<str>` at top level is a separate region-carrying slice).

Spec: `../align/docs/impl/core-design/json.md` (the "T1b + `array<str>`" section).

### align-llm verification (2026-07-25 — CLOSED)

`src/eval.align` now decodes every file-backed `TaskSpec`, re-encodes it, decodes that result again,
and executes the second record's `argv`. `make ci` runs the smoke-v1 corpus through this path. This
directly exercises the original decode-and-encode round-trip gate before the decoded command can
count as passing.

---

## Request 4 — `std.http`: client-side chunked response de-framing for provider SSE

```text
Status: CLOSED
Priority: high
Blocking: no
Blocked gate or slice: none; C1 streaming provider acceptance is enabled
Independent work that may continue: all provider and C6 work may consume the shipped surface
Resume condition: complete
Align commit or pull request: Align design PR #798, merged as `004b7f02086570b200b238d752a1f7ba67da7d04`; implementation PR #800, merged as `f04672bce6f8689c9b219d0a20e770571e2d638b`
align-llm verification: `.align-revision` pins `5aa5b23ace02109ad5ef9c36ba6d2acaba9ae7ad`; `make provider-smoke` passes chunked OpenAI-compatible and llama.cpp SSE, malformed and truncated framing, exact/cap-plus-one tiny-chunk bodies, bodyless and interim responses, exact/cap-plus-one trailer guards, retained final headers, discarded trailers, reuse after success, and teardown after failure; the native Linux aarch64 installed profile and its fresh `make ci` pass at implementation head `0f9e08eee427b9005d1294c4100f72385a8003b9`
```

### Motivation

OpenAI-compatible streaming APIs normally return server-sent events with HTTP/1.1
`Transfer-Encoding: chunked`. The C1 provider adapters now parse the SSE event body and assemble
delta content, but the shipped `std.http` client is Content-Length-only and rejects chunked response
bodies before the provider can see them. A raw-socket workaround in align-llm would duplicate HTTP
framing and violate the standard-library boundary.

### Requested capability

Extend the existing `std.http` client response path to de-frame a valid chunked response into the
same zero-copy/owned response body exposed by `resp.body()`. Preserve the existing malformed-message
and truncation error behavior, and keep response status and headers byte-for-byte discoverable
through the existing accessors after body compaction. The provider layer does not need a second
streaming transport API; `cl.request` should remain the single HTTP boundary.
As already assigned to this de-framing slice by Align's HTTP plan, select response-body framing from
the request method and response status before reading a body. A final response to `HEAD`, and final
`204` and `304` responses, expose zero body bytes even when a response such as `HEAD` or `304`
legitimately carries `Content-Length` or supported `Transfer-Encoding: chunked` metadata. The latter
remains discoverable as a header but does not enter the chunk decoder.
HTTP method tokens are case-sensitive: only exact uppercase `HEAD` selects HEAD response semantics.
Lowercase or mixed-case tokens such as `head` are extension methods and use ordinary response
framing.

An informational response other than `101` is an interim head, not the response returned to the
caller. Validate it, consume no payload, preserve any following bytes already read from the
connection, and continue until the final response; the final status, headers, and body are the only
response exposed. All interim and final heads share one cumulative `HTTP_MAX_HEADER_BLOCK` wire-byte
allowance, so repeated informational responses cannot accumulate memory or run without a byte bound.
`101 Switching Protocols` is different: the whole-body HTTP client has no upgraded-protocol handle,
so it returns `Error.Invalid`, exposes no response, and closes rather than pools the connection.
For the same reason, `cl.request` rejects the exact `CONNECT` method as `Error.Invalid` before DNS,
connect, or write; a successful CONNECT would switch to a tunnel this API cannot represent.
Lowercase or mixed-case `connect` is not that protocol method and is sent and framed normally.

Successful self-delimited responses preserve the existing R3 reuse-by-default contract. After a
terminal chunk and valid trailers, or after a bodyless final `HEAD`/`204`/`304` head, the connection
returns to the idle pool if the final response is keep-alive eligible, fully parsed, and has no
residual bytes. Read-to-close, `Connection: close`, `101`, malformed/truncated framing, and any
partially consumed response remain ineligible and close.

The trailer section, from the first byte after the terminal zero-chunk line through the empty line
that terminates trailers, has a named fixed `HTTP_MAX_TRAILER_BLOCK` cumulative wire-byte guard in
Align's HTTP design. Its current value is `HTTP_MAX_HEADER_BLOCK`; it is a separate parser counter
but does not add another allocation allowance. Trailer fields are framing metadata in this
whole-body surface: validate them incrementally in the reused read scratch, but do not retain their
raw bytes or offsets, merge them into the response headers, or expose them through the existing
header accessor. Final response headers remain retained and byte-for-byte discoverable. Trailer
field count consumes the unused portion of the same `HTTP_MAX_HEADERS` budget as the final headers,
using only a scalar counter. A complete, syntactically valid trailer block whose terminating CRLF
ends exactly at the guard is accepted. If the terminator is not recognizable within the guard, or
recognizing it would require one byte beyond the guard, return `Error.Invalid`, perform no later
transport read, expose no response, and close rather than pool the connection. Guard excess is
decided before parsing syntax or field-count state that depends on bytes beyond the guard. For a
complete block within the guard, validate trailer syntax and the shared field-count budget normally.
A read after the terminal chunk requests at most the trailer guard's remaining wire bytes; trailer
discovery has no over-guard probe or co-read exception. Trailer bytes already co-read into the reused
scratch while parsing the terminal chunk count against the guard before any later read. A
decoded-body cap excess recognized before the terminal chunk retains the limit-specific outcome and
does not read trailers; after the terminal chunk, trailer guard, syntax, count, or truncation
failures are malformed framing and return `Error.Invalid`.

### Acceptance / gate

An HTTP fixture sends two SSE chunks and a terminating zero chunk. `provider.stream` returns their
concatenated content for both the OpenAI-compatible and llama.cpp adapters. A missing terminator,
invalid chunk size, or truncated chunk returns `Error.Invalid` and does not produce a partial success.
A direct `cl.request` fixture returns `206` with a distinctive response header and a chunked body;
after de-framing, `status()` is exactly `206`, the header lookup returns its exact value, and
`body()` returns only decoded payload bytes.
`HEAD` and `304` fixtures with a syntactically valid nonzero `Content-Length`, or with supported
`Transfer-Encoding: chunked` alone, return an empty body without waiting for payload, a chunk
terminator, or trailers; the transfer-encoding header retains its exact value. The runtime-owner
framing matrix also covers `204`. Same-read and split-read fixtures send one or more non-`101`
informational heads, including `100`, `102`, `103`, and `199`, followed by a final response and prove
that the final status/body is returned without losing co-read bytes. Any `Content-Length` or
`Transfer-Encoding` on those informational heads returns `Error.Invalid` before final-response
advancement. A cumulative interim-head span above `HTTP_MAX_HEADER_BLOCK`, and a `101` response,
return `Error.Invalid`, no response handle, and close the connection. A `CONNECT` fixture returns
`Error.Invalid` before the fixture observes any network request. Lowercase `head` and `connect`
counter-fixtures reach the server, return payload-bearing Content-Length responses, expose their
complete bodies, and preserve ordinary keep-alive framing and reuse.

Trailer boundary fixtures accept a syntactically valid block whose terminating empty line ends
exactly at `HTTP_MAX_TRAILER_BLOCK`, and reject a terminator one byte beyond the guard, a
continuously arriving unterminated trailer line, malformed syntax within the guard, and a trailer
count that exceeds the final headers' remaining `HTTP_MAX_HEADERS` budget. A direct fixture gives a
final header and trailer the same name with distinctive values and proves header lookup returns only
the original final-header value. Plaintext and verified-TLS cases prove the
unterminated/over-guard paths stop after the first recognizable excess, retain no response, and
close without another read; runtime-owner instrumentation proves no trailer byte or offset survives
parsing, every post-terminal-chunk read was clamped to the remaining trailer guard, and the separate
wire counter adds no byte-storage allowance.

Plaintext and verified-TLS sequential fixtures return a complete chunked response and then a second
small response over the same connection. The bodyless matrix does the same for `HEAD`, `204`, and
`304`, including `Content-Length` metadata and `Transfer-Encoding: chunked`-only metadata where
permitted. Each fixture proves that a successful self-delimited first response is pooled only after
its complete framing is consumed; the transfer-encoding-only cases prove no chunk terminator is
consumed before reuse. `Connection: close`, residual bytes, malformed framing, and `101`
counter-cases use a new connection or fail as specified. A separate successful close-delimited
fixture returns its first response at EOF and proves that a later request through the same client
opens a new connection rather than pooling the read-to-close exchange.

The combined de-framing/bounded-receive gate is owned by whichever of Request 4 and Request 5 reaches
`ALIGN_MERGED` second. If Request 5 is already available when this request ships, Request 4 may not
advance to `ALIGN_LLM_VERIFIED` until the exact-cap, cap-plus-one, many-tiny-chunks, aggregate-storage,
trailer-guard, interim-to-final, and bodyless-response-above-cap cases in Request 5 pass against both shipped
commits. If Request 4 ships first, Request 5 owns that same combined gate. The request that landed
first need not be reopened; the second request's lifecycle record must name both Align commits and
the combined align-llm verification. If both capabilities ship in one Align commit or pull request,
or both register entries advance to `ALIGN_MERGED` together, Request 5's bounded-response adoption
checkpoint owns the combined gate; neither request may reach `ALIGN_LLM_VERIFIED` until that
checkpoint names the joint delivery and records the combined verification.

### Current align-llm evidence

`src/provider_openai.align` and `src/provider_llama.align` implement the adapter-level SSE parser and
pass `make provider-smoke` with Content-Length-framed fixtures. The provider-consumer prerequisite
wave must pin the shipped capability and switch the same fixture to chunked framing before the
streaming acceptance slice resumes; non-streaming provider work remains valid meanwhile.

---

## Request 5 — `std.http`: bounded client response bodies

```text
Status: CLOSED
Priority: high
Blocking: no
Blocked gate or slice: none; the C6 provider-proposal cell may consume the shipped bound
Independent work that may continue: all provider and C6 work may consume the shipped surface
Resume condition: complete
Align commit or pull request: Align design PR #810, merged as `6c753de84012e178a99e4de0edebf3b395c71dbd`; implementation PR #812, merged as `5aa5b23ace02109ad5ef9c36ba6d2acaba9ae7ad`
align-llm verification: `.align-revision` pins `5aa5b23ace02109ad5ef9c36ba6d2acaba9ae7ad`; `provider_http.post_json` applies the 262,144-byte transport cap; `make provider-smoke` distinguishes `Error.Code(-1)` with no body from HTTP 413, proves clean connection teardown and later client reuse, and passes the combined Request 4/5 focused gate named above; the native Linux aarch64 installed profile and its fresh `make ci` pass at implementation head `0f9e08eee427b9005d1294c4100f72385a8003b9`
```

### Motivation

C6 asks a model provider for a declared prompt/context proposal and must reject a response larger
than 262,144 bytes before decoding it. A check after the current provider call returns is too late:
the whole response has already been allocated. A misconfigured or hostile endpoint can therefore
consume memory far beyond the C6 contract before align-llm can reject it.

This is a transport-boundary concern, not an application parser feature. align-llm must not build a
second HTTP client or run the existing whole-body call and describe a post-allocation length check
as bounded receiving.

### Current-state evidence

Verified at sibling Align commit `891eb3e37b61526fd096c25d95107f1f69060a45` on
2026-07-28:

- `src/provider_http.align::post_json` calls `client.request(request)` and then
  `response.body()`, which exposes the already-buffered complete body.
- `../align/crates/align_runtime/src/lib.rs` sets `HTTP_MAX_BODY` to `1 << 30`.
- The current `std.http` client has no request/client response-body cap and no client-side bounded
  response reader. Its streaming surface is server-response output, not client-response input.

Timeouts bound elapsed blocking but do not bound bytes or allocation. The existing one-GiB runtime
ceiling is much larger than a provider operation's declared response contract.

### Requested capability

Add idiom-consistent client-default and request-level controls that limit response-body bytes while
the body is being received. Both scopes are required so one client can carry a safe default while
selected operations narrow it. The exact method spelling remains Align's design decision; the
existing timeout builder suggests:

```text
request.max_response_body_bytes(limit: i64)
client.max_response_body_bytes(limit: i64)
```

Required semantics:

- a positive configured cap must be in `1..=HTTP_MAX_BODY`. A larger positive value, a negative
  value, or a value not representable as target `usize` is a programmer error that aborts before
  builder state changes. The configured cap can only narrow the existing global ceiling;
- an unset or zero client cap has effective value `HTTP_MAX_BODY`. An unset or zero request cap
  inherits that client effective value. A positive request cap has effective value
  `min(client effective cap, request cap)`, so one request can narrow but never widen its client's
  receive bound;
- the client default applies to `get`, `post`, `request`, and every `get_many` worker. `get_many`
  snapshots the client cap once before launching workers, and every exchange in that invocation uses
  the same effective cap. A batch keeps its existing deterministic lowest-index error rule regardless
  of worker completion order or error kind; a limit failure produces no response array and frees
  every successful sibling response handle;
- a positive client or request cap is explicit even when its value is exactly `HTTP_MAX_BODY`; zero
  and unset are not explicit. Thus, whenever either scope has a positive cap, a payload-bearing
  response above the effective cap returns the limit-specific outcome, including when the only
  positive cap is exactly `HTTP_MAX_BODY`. When neither scope has a positive cap, target overflow or
  `HTTP_MAX_BODY` excess retains the existing `Error.Invalid`;
- validate `Content-Length` syntax and framing conflicts before cap comparison for every response
  head the available framing surface accepts. A non-decimal value, conflicting duplicate lengths,
  or a `Transfer-Encoding` conflict remains malformed `Error.Invalid`. For a payload-bearing final
  response with a syntactically valid decimal magnitude, an explicit-cap excess returns the
  limit-specific outcome even when the magnitude also exceeds target `usize` or `HTTP_MAX_BODY`.
  Compare decimal magnitudes after ignoring leading zeroes, without converting the untrusted value
  to target `usize`; digit count or raw lexical order is not a magnitude comparison. Duplicate
  Content-Length fields are equal when their normalized numeric magnitudes are equal, even if their
  leading-zero spelling differs;
- compose the cap with Request 4's shipped method/status-aware framing as follows:
  - after a head's syntax and framing conflicts are validated, select body framing from the request
    method and response status. A final response to `HEAD`, and final `204` and `304` responses, have
    zero received payload; a syntactically valid `Content-Length` that is permitted as metadata
    (on `HEAD` and `304`) is validated as an arbitrary-precision decimal string without conversion
    to target `usize`, is not compared with either the selected cap or `HTTP_MAX_BODY`, causes no
    body allocation, and causes no body read. A syntactically valid, supported
    `Transfer-Encoding: chunked` field without `Content-Length` is also permitted metadata on
    `HEAD` and `304`: preserve its exact header value, but do not enter the chunk decoder, compare a
    cap, allocate a body, read payload, or consume a chunk terminator/trailer. A `Content-Length` or
    `Transfer-Encoding` field on `204`, or on any non-`101` informational status in `100..=199`, is
    forbidden and returns `Error.Invalid`. Malformed decimal or transfer-coding syntax, conflicting
    duplicate lengths, unsupported transfer codings, and a simultaneous
    `Content-Length`/`Transfer-Encoding` combination return `Error.Invalid` on `HEAD` and `304`
    before body suppression. Match request methods case-sensitively: only exact uppercase `HEAD`
    selects HEAD response semantics, while `head` and other case variants use ordinary
    payload-bearing response framing;
  - a non-`101` informational head has zero payload but is not returned. Preserve co-read bytes,
    continue through subsequent informational heads to the final response, and apply the selected
    cap only to that final response's payload. Count the complete wire span of all interim and final
    heads against one cumulative `HTTP_MAX_HEADER_BLOCK` allowance even when parsed interim storage
    is discarded;
  - reject `101 Switching Protocols` as `Error.Invalid`, with no response handle and no pooled
    connection. Request 4 rejects `CONNECT` before a network side effect, so tunneled bytes never
    enter the bounded whole-body path;
  - give the complete chunk-size line, including extensions and terminating CRLF, a named fixed
    `HTTP_MAX_CHUNK_LINE` byte guard in Align's HTTP design. Missing termination within the guard or
    any byte beyond the guard returns `Error.Invalid` before syntax, magnitude, or cap comparison.
    For a complete line within the guard, validate size and extension syntax before comparing size.
    Malformed syntax returns `Error.Invalid` first. For a syntactically valid hexadecimal magnitude,
    compare checked cumulative decoded bytes with the effective cap before converting to target
    `usize`, allocating payload storage, or requesting another transport read. If either scope has a
    positive cap, an excess returns the limit-specific outcome even when the magnitude also exceeds
    target `usize` or `HTTP_MAX_BODY`; without a positive cap, target/global excess remains
    `Error.Invalid`. A valid size within the cap whose payload, delimiter, terminal chunk, or trailers
    are truncated remains `Error.Invalid`;
  - after a terminal zero-chunk line, count every trailer-section wire byte through the terminating
    empty line against a named fixed `HTTP_MAX_TRAILER_BLOCK`, whose current value is
    `HTTP_MAX_HEADER_BLOCK`. This is a separate scalar parser counter and does not add a storage
    allowance. Validate trailer fields incrementally in the reused read scratch, but retain no raw
    trailer bytes or offsets, do not merge them into the final response headers, and do not expose
    them through existing header lookup. Trailer field count consumes the unused portion of the
    final headers' `HTTP_MAX_HEADERS` budget. Accept a complete, valid block ending exactly at the
    guard. If its terminator is not recognizable within the guard or needs one byte beyond it,
    return `Error.Invalid` without another read, response handle, or pooled connection. Guard excess
    is decided before syntax or count state that requires an over-guard byte; a complete block
    within the guard then undergoes normal trailer syntax and shared field-count validation. A
    post-terminal-chunk transport read requests at most the remaining trailer guard; there is no
    over-guard probe or trailer-discovery co-read exception. Trailer bytes already co-read into the
    reused scratch while parsing the terminal chunk count before any later read. A decoded-body
    excess recognized before the terminal chunk keeps the limit-specific outcome and performs no
    trailer read; after that chunk, trailer guard, syntax, count, and truncation failures are
    `Error.Invalid`;
- a fixed-size transport read used to discover a response-head terminator or a chunk-size-line
  terminator may already contain payload bytes past the boundary that makes an excess recognizable.
  This is the only co-read exception: all such bytes remain in the single
  `HTTP_CLIENT_READ_CHUNK` scratch allowance, are never copied into retained decoded payload after
  the excess is known, and cause no subsequent transport read. The same rule applies to
  Content-Length, close-delimited, and chunked framing;
- for a payload-bearing response, reject a `Content-Length` above the selected cap without reserving
  from that untrusted declared length or performing another transport read after the excess becomes
  recognizable;
- for a close-delimited body, first consume any payload already present in the bounded
  framing-discovery scratch. If that proves excess, fail without another read. Otherwise request at
  most the remaining payload allowance plus one probe byte. A de-framed chunked response uses the
  guarded, validated size-line rule above and does not request a payload probe after a declared
  cumulative excess;
- return a machine-distinguishable limit-exceeded outcome whose stable public discriminant is not
  shared with malformed framing, truncation, another I/O failure, or an HTTP status. A dedicated
  `Error` variant is viable. If Align uses `Error.Code`, it must reserve and document a stable code
  outside `100..=599` and outside every raw OS error code on all supported targets; the final
  taxonomy and exact reserved value remain Align's design decision;
- on every limit-specific failure, return no response handle or body, free the response
  accumulator, exclude the partially consumed TCP/TLS connection from the idle pool, and close it
  through the existing transport teardown. The client remains usable for a later request on a new
  clean connection;
- apply the cap selection, limit outcome, cleanup, post-decision no-read rule, and Align-owned
  byte-storage ceiling identically to HTTP and HTTPS;
- preserve the current default behavior only when neither scope has a positive cap. A positive
  `HTTP_MAX_BODY` value remains explicit and uses the limit-specific outcome on excess;
- keep the response Move ownership and zero-copy body view unchanged for successful bounded
  responses;
- follow the existing HTTP timeout-setter convention for zero: a request-level zero clears the
  override and inherits its client, while a client-level zero restores the existing default;
- use checked integer conversion at every native boundary.

The receive buffer must not grow from the declared `Content-Length`. At every point in an exchange,
the peak aggregate live Align HTTP-runtime-owned response-byte storage must be no more than:

```text
selected body cap + HTTP_MAX_HEADER_BLOCK + HTTP_CLIENT_READ_CHUNK
```

The current named constants are 262,144 and 32,768 bytes. Therefore the 262,144-byte consumer cap
has a numeric ceiling of 557,056 bytes. Aggregate response-byte storage is the sum of the capacities
of every simultaneously live byte buffer that the Align HTTP runtime directly owns for raw
head/framing/trailer bytes, retained decoded payload, co-read/probe bytes, or fixed raw-read scratch.
This ceiling excludes allocator metadata, the response handle's fixed fields, structurally bounded
offset/decoder records, kernel socket buffers, and opaque TLS-library record buffers behind `SSL*`.
Those transport-owned buffers are outside Align's response allocator and runtime-owner
instrumentation; they may not be sized from the peer-declared `Content-Length`, chunk magnitude,
selected cap, or accumulated response length. Any plaintext or TLS staging buffer added or owned by
the Align HTTP runtime is inside the formula. An implementation may reuse or combine byte regions,
but may not give separate Align-owned byte accumulators independent copies of any allowance.

Structural metadata is bounded independently. Only the final response's header offset records
survive parsing. Interim offset records are discarded before parsing the next head, and at most one
interim or final table is live during framing. Trailer fields have no offsets or retained raw bytes;
a scalar count consumes the unused portion of the final headers' existing `HTTP_MAX_HEADERS` budget.
Chunk decoder state is constant size and may not grow with body length, declared `Content-Length`,
chunk count, chunk-size magnitude, or trailer bytes. Any implementation that needs another
structural table must give it a named fixed count/byte cap in Align's HTTP design and include it in
the runtime-owner structural-metadata test; it is not permitted to hide response bytes in the
structural exclusion.

With Request 4's chunk de-framing shipped, the formula remains a combined receive-buffer ceiling, not
one allowance per parser component. `selected body cap` covers only retained decoded payload;
`HTTP_MAX_HEADER_BLOCK` is the single cumulative wire-byte allowance for every interim and final
response head and the single byte-storage allowance shared with retained raw chunk metadata; one
reused `HTTP_CLIENT_READ_CHUNK` scratch buffer covers raw framing, transient trailer bytes, and
payload input.
The named `HTTP_MAX_CHUNK_LINE` guard applies before chunk syntax and cap comparison and consumes
space only inside the shared framing/scratch allowances. The named `HTTP_MAX_TRAILER_BLOCK` counter
separately bounds trailer wire progress at the same fixed value as `HTTP_MAX_HEADER_BLOCK`; trailer
bytes are validated and discarded incrementally in the reused scratch and never consume retained
header/framing storage. Discovery co-read and the one close-delimited probe byte are observations in
the reused scratch buffer and do not enlarge retained payload.

This request does not require a general async or client-streaming API. A bounded whole-body response
is sufficient for the first real consumer and composes with Request 4's shipped chunk de-framing.

### Acceptance / gate

An Align client configured with a 262,144-byte cap:

1. runs a client-default dispatch matrix through `get`, `post`, and `request`: every entry point
   accepts an exact-cap Content-Length response and exposes the complete body;
2. the same `get`/`post`/`request` matrix rejects a payload-bearing Content-Length response of
   262,145 with the limit-specific outcome after parsing and selecting body framing, without a
   declared-length reservation or a subsequent body read. It also repeats a declared
   `HTTP_MAX_BODY + 1` with the client cap explicitly set to positive `HTTP_MAX_BODY`, client zero,
   and client unset, proving each entry point returns respectively the limit-specific outcome,
   `Error.Invalid`, and `Error.Invalid`. Plaintext and verified-TLS sequential fixtures separately
   use an exact-cap Content-Length response under a positive client-level cap and under a narrower
   positive request-level cap; each proves the successful response is returned to the idle pool and
   the next request through the same client reuses that exact connection. The dispatch matrix also
   accepts leading-zero exact-cap values such as `000262144`, treats duplicate `262144` and
   `000262144` fields as numerically equal, and returns the limit-specific outcome for leading-zero
   cap-plus-one `000262145`;
3. returns the limit-specific outcome for a payload-bearing response with a syntactically valid
   decimal `Content-Length` magnitude above the selected cap even when it is above target `usize` or
   `HTTP_MAX_BODY`, while malformed or conflicting framing returns `Error.Invalid` first. The same
   oversized magnitude on an unconfigured client retains the existing `Error.Invalid`. A valid
   within-cap Content-Length whose body is truncated returns `Error.Invalid`, and a distinct
   transport failure retains its existing discriminant rather than becoming the limit outcome.
   Arbitrary-precision cases add many leading zeroes to within-cap, cap-plus-one, and above-target
   magnitudes and prove normalization occurs before digit-count/magnitude comparison without
   changing malformed or overflow precedence;
4. using Request 4's method/status-aware framing, accepts `HEAD` and `304` responses that
   advertise a syntactically valid decimal `Content-Length` above target `usize` and
   `HTTP_MAX_BODY` but transfer no body, exposes an empty body, and neither returns the limit
   outcome, performs a magnitude-sized allocation, nor consumes bytes belonging to a following
   response. Same-read, split-read, plaintext, and verified-TLS cases also accept supported
   `Transfer-Encoding: chunked` alone on `HEAD`/`304`, preserve its exact header value, expose an
   empty body, consume no chunk terminator/trailer, and remain R3 pool-eligible. Malformed decimal or
   transfer-coding syntax, conflicting duplicate lengths, unsupported transfer codings, and
   simultaneous `Content-Length`/`Transfer-Encoding` on `HEAD` and `304` return `Error.Invalid`.
   Runtime-owner cases prove a final `204` selects zero received payload with no framing fields,
   while any `Content-Length` or `Transfer-Encoding` on `204` returns `Error.Invalid` before body
   suppression. An exact uppercase `HEAD` fixture returns no payload as above; a lowercase `head`
   counter-fixture with an exact-cap Content-Length body uses ordinary framing, returns the complete
   body, and remains pool-eligible. A lowercase `connect` counter-fixture likewise reaches the
   server and uses ordinary response framing, while exact uppercase `CONNECT` remains pre-network
   `Error.Invalid`;
5. using Request 4, same-read and split-read fixtures send one or more non-`101`
   informational heads, including `100`, `102`, `103`, and `199`, followed by a final response. They
   prove only the final status/body is returned, no co-read final bytes are lost, an exact-cap final
   body succeeds, a cap-plus-one final body returns the limit outcome, aggregate live
   response-byte storage remains within 557,056 bytes, and only one bounded header-offset table is
   live. Any `Content-Length` or `Transfer-Encoding` on a non-`101` informational head returns
   `Error.Invalid` before advancing to the final response. A cumulative interim/final head span
   above `HTTP_MAX_HEADER_BLOCK`, and `101 Switching Protocols`, return `Error.Invalid`, no response
   handle, and a closed rather than pooled connection;
6. accepts an exact-cap close-delimited response, and rejects a 262,145-byte close-delimited
   response with the same limit-specific outcome. Same-read and split-read cases separately prove
   that framing-discovery co-read stays in the one scratch buffer, no co-read excess becomes retained
   payload, no transport read follows a recognizable excess, and otherwise at most one requested
   probe byte crosses the cap;
7. enforces the same cap, outcome, cleanup, post-decision-read, and Align-owned storage behavior over
   HTTPS. The verified-TLS runtime case proves that its Align-owned application read/staging buffers
   are counted by the same instrumentation, while opaque libssl and kernel transport buffers are
   excluded and receive no capacity derived from response framing or length;
8. uses runtime-owner instrumentation to prove that peak aggregate live Align HTTP-runtime-owned
   response-byte storage—the sum of every simultaneously live Align-owned response-byte-buffer
   capacity plus fixed raw-read scratch capacity—is at most 557,056 bytes, and that no byte
   allocation request or capacity is derived from the oversized declared length. A separate
   assertion proves only final-header offsets survive, trailer fields consume the remaining
   `HTTP_MAX_HEADERS` count without offsets or retained bytes, only one interim/final offset table is
   live, decoder structural state is constant-size, and no structural capacity depends on body
   length, declared length, chunk count, chunk-size magnitude, or trailer bytes;
9. proves an unconfigured or client-zero effective cap remains exactly `HTTP_MAX_BODY` in a
   runtime-owner unit test, accepts a 262,145-byte response without a smaller cap, and returns the
   existing `Error.Invalid` for a syntactically valid Content-Length above `HTTP_MAX_BODY`;
10. proves request zero inherits the client, a positive request cap narrows a larger client cap, and
    a larger positive request cap cannot widen a smaller client cap. Runtime-owner tests at the
    validation/store boundary accept exactly `HTTP_MAX_BODY`, and prove `HTTP_MAX_BODY + 1`, a
    negative limit, and, on a target where it exists, a positive `i64` not representable as `usize`
    abort before a previously valid builder value can change. Process-level fixtures separately
    prove both public setters abort and issue no network request. Client-level and request-level
    positive `HTTP_MAX_BODY` fixtures each return the limit-specific outcome for a syntactically
    valid Content-Length of `HTTP_MAX_BODY + 1`, while zero/unset fixtures retain `Error.Invalid`;
11. configures only the client-level 262,144-byte cap and calls `get_many` at concurrency greater
    than one with successful small siblings and one 262,145-byte response. The batch returns the
    limit-specific outcome, produces no response array, frees every successful sibling response
    handle, and closes the failed exchange. Two additional multi-error batches invert completion
    order: a lower-index delayed malformed-framing error beats a higher-index early limit error, and
    a lower-index delayed limit error beats a higher-index early malformed-framing error. Both
    produce no array, finish and free successful siblings, and tear down each failed exchange. An
    exact-cap batch succeeds. Declared `HTTP_MAX_BODY + 1` batches under an explicitly positive
    client `HTTP_MAX_BODY`, client zero, and client unset respectively return the limit-specific
    outcome, `Error.Invalid`, and `Error.Invalid`, proving the batch snapshot retains the
    explicit-versus-default distinction. Runtime-owner instrumentation proves every worker used the
    one cap snapshot and each exchange observed the byte/structural bounds independently;
12. proves a limit failure returns no response handle, frees its accumulator, and closes rather than
    pools the partial connection. Plaintext and verified-TLS sequential fixtures send an oversized
    response and then a valid small request through the same client, and prove the second request
    uses a new clean connection;
13. accepts an exact-cap Request 4 de-framed chunked response, including its terminating
    chunk and trailers, and rejects a 262,145-byte decoded payload with the same limit-specific
    outcome immediately after its complete, within-guard valid size line, before another transport
    read or payload allocation. Any payload already co-read with that line remains only in scratch
    and is not retained. A syntactically valid oversized hexadecimal magnitude above target
    `usize`/`HTTP_MAX_BODY` but within `HTTP_MAX_CHUNK_LINE` has the same explicit-cap outcome; a
    malformed size/extension, a missing line terminator at the guard, a terminated line one byte over
    the guard, and a truncated within-cap chunk return `Error.Invalid`. Boundary fixtures prove a
    complete valid line at the guard is parsed before cap comparison, while guard excess wins even
    when a numeric prefix would exceed the cap. A many-tiny-chunks fixture proves decoded payload,
    raw framing/metadata/trailer byte buffers, and scratch do not exceed the combined 557,056-byte
    Align-owned ceiling, while structural state stays constant and independent of chunk count.
    Trailer fixtures accept a valid block whose terminating empty line ends exactly at
    `HTTP_MAX_TRAILER_BLOCK`, and reject a terminator one byte beyond the guard, a continuously
    arriving unterminated trailer line, malformed syntax within the guard, and exhaustion of the
    final headers' remaining `HTTP_MAX_HEADERS` budget. A same-name final-header/trailer fixture
    proves header lookup returns only the original final-header value. Plaintext and verified-TLS
    over-guard cases prove `Error.Invalid`, no response, no pooling, no read after the recognizable
    excess, every post-terminal-chunk read is clamped to the remaining trailer guard, and no byte
    allocation exceeds the combined ceiling. Runtime-owner instrumentation proves no trailer raw
    bytes or offsets survive incremental validation. A combined boundary case retains a final head
    ending exactly at `HTTP_MAX_HEADER_BLOCK`, an exact-cap decoded body, and an exact-guard trailer
    streamed through the reused scratch, and proves peak storage does not exceed the combined
    ceiling or gain a trailer-wire-volume term. A decoded-body limit recognized before the terminal
    chunk remains the limit-specific outcome and does not read any trailer byte.
    Plaintext and verified-TLS sequential fixtures prove an exact-cap terminal chunk/trailer response
    remains pool-eligible and the next request reuses the connection.
    The request that reaches `ALIGN_MERGED` second owns these cases and items 4–5 before it may advance
    to `ALIGN_LLM_VERIFIED`; its lifecycle record names both shipped commits and the combined
    verification. The earlier request need not be reopened. For a joint Align delivery, Request 5's
    bounded-response adoption owns the combined cases, names the joint commit or pull request, and
    must pass before either request reaches `ALIGN_LLM_VERIFIED`;
14. proves the limit outcome remains distinguishable through `provider_http` from a real HTTP 413
    and another non-2xx response. The limit fixture returns the shipped limit discriminant and no
    body; the status fixtures retain `Error.Code(413)` and their exact HTTP status codes.

After Align marks this request `ALIGN_MERGED`, align-llm starts a separate bounded-response adoption
slice. That enabling slice—not the blocked C6 provider-proposal slice—rebuilds the sibling release
compiler/runtime, updates `.align-revision`, makes `provider_http` apply the cap, and runs a
transport fixture proving an oversized response propagates the exact shipped limit discriminant,
returns no body, and leaves the client able to use a new clean connection. It does not decode a
proposal, create a C6 proposal artifact, or introduce a C6 persisted error label. The request
advances to `ALIGN_LLM_VERIFIED` only when that real-client fixture and `make ci` pass. The later
reviewed C6 provider-proposal slice owns conversion from the shipped transport discriminant to its
persisted proposal error label, and resumes only after this adoption gate.

### References

- `src/provider_http.align` — current whole-body provider transport consumer.
- `../align/crates/align_runtime/src/lib.rs` — `HTTP_MAX_BODY` and client response accumulation.
- `../align/docs/impl/std-design/http.md` — authoritative HTTP design to extend.
- `docs/specs/roadmap.md` and `docs/specs/align-llm.md` — committed C6 delivery order and system
  architecture. The detailed C6 design remains an intentional uncommitted draft on its separate
  design branch until this enabling request is registered.

---

## Request 6 — `core.json`: require recursively Copy `json.scan` rows

```text
Status: CLOSED
Priority: high
Blocking: yes
Blocked gate or slice: none; Request 7's other separately registered prerequisites remain independent blockers
Independent work that may continue: N/A; this request is shipped, adopted, verified, and closed
Resume condition: N/A; reopen only for a newly demonstrated regression in the shipped scanner-row ownership contract
Align commit or pull request: Align PR #703 (design) merged at 0ab7a30d6e7bfda56d4c8145b4672306634b9fea; Align PR #704 (implementation) merged at e65448b744c04e3868d079eef8b45ce0d43ac8ee
align-llm verification: CLOSED by align-llm PR #84, merged as c0fc3046bff05d33ad0753f9c273da8bb48d2fa1 with Align pinned at 25b1201b3a4181f6a90921227596bdcb76ab715e
```

The first scheduled dependent slice is Request 7 implementation: its strict-string grammar matrix
uses only rows admitted by this recursively Copy boundary. Request 6 no longer blocks that slice;
Request 7's separately registered prerequisites still do. The first align-llm real-client consumer
was the concrete adoption target specified below. It ran the positive Copy-row aggregate plus the
exact fail-closed Move-row negatives against the pinned shipped compiler before this request closed.
A consumer that actually needs a Move row belongs exclusively to a separate per-row ownership
request and is not a consumer of this rejection capability.

### Motivation

`json.scan` promises bounded streaming: its `json.scanner<Row>` handle only borrows the input, and
each fused terminal decodes one row into a reusable stack slot. The pinned compiler nevertheless
accepts row schemas containing owned scalar arrays and record arrays. A successful row can
therefore allocate a Move field that is neither transferred to an owner nor dropped before the
runtime zeroes the same slot for the next row.

This is an ownership gap, not an escaped-string feature. It was demonstrated while closing the C6
JSON public-path matrix and must have its own Align design and delivery boundary. C6 does not need
owned scanner rows, so the smallest safe surface is to reject them at compile time and preserve
the scanner's shipped no-arena, borrowed-row model.

### Current-state evidence

Verified at the pinned Align commit `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e` on
2026-07-30:

- `../align/docs/impl/core-design/json.md` defines `json.scanner<Row>` as a Copy `{ptr,len}` input
  view, says one row decodes into a per-step stack slot without an arena, and describes `str`
  fields as borrowed input views.
- `check_json_scan` in `../align/crates/align_sema/src/lib.rs` reuses
  `json_struct_fields_ok(..., JsonDir::Decode)`. That general decode predicate admits
  `array<int>`, `array<float>`, `array<bool>`, `array<str>`, and `array<Struct>` fields, including
  arrays reachable through nested structs and shape-directed union payloads.
- `lower_json_scan_reduce` in `../align/crates/align_mir/src/lib.rs` allocates one
  `Ty::StructArray(Row, 1)` slot. Its loop calls `JsonScanNext` repeatedly and contains no
  successful-row `DropValue` before the back edge, exhaustion, malformed-input exit, or terminal
  return.
- `align_rt_json_scan_next` in `../align/crates/align_runtime/src/lib.rs` zeroes the complete row
  slot before each `parse_object`. Typed array decoding allocates an owned spine. Zeroing a
  successfully decoded prior row therefore loses the only pointer to that allocation.
- The fused pipeline checker prevents Move values from being passed to `map` or `where`, and
  scanner terminals return scalar accumulators, but those rules do not help: the runtime decodes
  every declared field before projection or filtering, so an unprojected owned field is still
  allocated and overwritten.

### Requested capability

Give `json.scan` a scanner-specific row eligibility check using Align's canonical recursive
ownership classification (`struct_is_move` / the complete `DropPlan`), not an ad hoc array list.
`Row` must be recursively non-owning: its complete reachable definition graph must be Copy and
must require no `Drop`.
The following remain supported:

- integers, floats, booleans, and borrowed `str` views;
- nested structs whose complete reachable field graphs meet the same rule;
- existing JSON-decode-eligible Copy options: scalar or borrowed-`str` payloads and
  `Option<CopyStruct>` whose complete reachable field graph meets the same rule; and
- shape-directed unions where every variant payload graph meets the same rule.

Reject any direct or transitively reachable owned field, including every `array<T>` and
`array<Struct>`, an array inside a nested or optional struct, and an owned array or owning struct
reachable through any union variant. The separately demonstrated general
`Option<enum>` remains rejected by the existing JSON Decode schema predicate before this ownership
gate and is outside this request. The pinned implementation currently admits
`Option<Move record>`: direct decode/encode succeeds, and ordinary scope `Drop` checks the option
tag and frees the nested owner. The current authoritative JSON design and
`m5.rs::json_option_move_struct_payload_remains_admitted` preserve that positive surface. After
decoding a `Some(MoveStruct)`, any subsequent enclosing-object decode failure leaves the optional
payload unfreed because the separate error-cleanup helper `drop_decoded_owned` skips optional
descriptors. Missing or type-invalid siblings, duplicate declared keys, and malformed later object
content are all instances of that root-cause class.
Additional decoded-owner gaps exist outside error exits. Indexed top-level AoS speculation can
write an owner, then fall back and overwrite it on either a successful or failed fallback.
Top-level `array<MoveStruct>` decode also fails to clean the current or completed staged rows after
malformed later elements or trailing garbage, unlike the nested field-array path's explicit partial
cleanup.
Top-level single-record trailing-garbage rejection separately leaves required or currently
admitted optional decoded owners live. These are known examples, not an exhaustive cleanup
inventory, and are outside this scanner-only request. Request 15 must audit every
transition after any decoded owner
becomes live: construction, speculative write, replacement/source nulling, fallback success and
failure, staging, return, and cleanup. It must either own every affected public path or assign each
class to an explicitly named separate request. SoA decoded-owner cleanup is N/A: well-typed
`json.decode` into `soa<T>` admits only primitive or borrowed-`str` columns, and sema rejects an
owned column before runtime. Defensive behavior for a raw runtime call with an invalid owning SoA
descriptor would require a separate invalid-descriptor ABI contract. While the current recursive
scanner schema walk admits the optional shape, the scanner-specific ownership gate must still
reject its reachable owner: each successful scan row would otherwise be overwritten without Drop.
Request 15 preserves ordinary Decode admission, so this scanner-specific Copy error remains the
first ownership rejection for that otherwise valid schema. The exact diagnostic template
substitutes a public source-level spelling for
`<row-type-source-spelling>`:

```text
`json.scan` row type '<row-type-source-spelling>' must be Copy; Move rows need per-row Drop before the scanner can reuse its row slot
```

That spelling is `Row` for a local non-generic declaration, `Wrap<array<i64>>` for a concrete local
generic monomorph, `scan_schema.ImportedRow` for an imported declaration, and
`scan_schema.Wrap<array<i64>>` for an imported concrete generic monomorph in the exact fixtures
below. Diagnostics must never expose internal `$`-mangled or monomorph-interner names.

A rejected `json.scan` expression must fail during semantic checking before MIR or runtime
descriptor construction. The row declarations remain valid Align types and are not rejected
outside this scanner use. Validation order is deterministic:

1. required `core.json` capability import;
2. argument arity;
3. expected `json.scanner<Row>` annotation and row inference;
4. existing JSON Decode schema eligibility;
5. the canonical recursive Copy/Move classification; and
6. input `str` typing and region checks.

This preserves the existing unsupported-JSON-field diagnostic when a declaration is not a valid
typed-decode schema at all, and makes the scanner ownership error precede an invalid input
expression once the row is otherwise JSON-decodable.

This request deliberately chooses rejection over per-row cleanup:

- it matches the already documented no-arena, borrowed-row contract;
- the scanner decodes all fields before pipeline projection, so lazy construction cannot make an
  unused owner harmless;
- whole-row `map`, `where`, `any`, `all`, and `reduce` calls introduce move-in/move-out and
  source-nulling questions that do not exist for a recursively Copy row; and
- retaining Move rows would require a separate public ownership contract for replacement,
  filtered rows, reducer calls, early exits, malformed partial rows, exhaustion, and unwind. No
  current align-llm consumer justifies that expansion.

The general `json.decode` eligibility surface is unchanged. This request changes no source syntax,
scanner handle representation, runtime ABI, row framing, terminal result type, error discriminant,
or top-level-array/NDJSON behavior. Existing programs that use an owning row at a `json.scan`
expression cease to compile; the row declaration and ordinary non-scanner uses remain valid. That
scanner-specific compatibility break is intentional because the current scan execution can leak.

Persisted identity, schema version, byte order, numeric widths, string encoding, embedded-NUL
handling, JSON validation/error precedence, CLI/build inputs, process-global state, and concurrent
scanner execution are N/A to the change because sema rejects the program before construction and
accepted programs retain their existing HIR, MIR, wire parser, runtime call, and cache identity
rules. The cache-specific compiler-build and schema edit behavior is still gated explicitly below.

### Ownership closure

For an accepted recursively Copy row:

- construction: `json.scan(view)` still produces only the input-borrowing Copy scanner handle;
- success: `align_rt_json_scan_next` may overwrite the reusable row slot because the preceding row
  contains no owner and requires no `Drop`;
- projection and filtering: every declared field is decoded, but ignored and rejected rows retain
  no allocation;
- whole-row calls: passing a Copy row to `map`, `where`, `any`, `all`, or `reduce` cannot transfer
  or duplicate ownership;
- malformed input, exhaustion, and terminal return: the row slot has no cleanup obligation, while
  the existing scalar accumulator and scanner-input lifetime rules remain authoritative;
- early exit: current `any` and `all` are full folds, so N/A for short-circuit cleanup. If Align
  later adds a short-circuiting scanner terminal, the recursively Copy row rule keeps the row slot
  cleanup-free; the new terminal still owns its accumulator cleanup;
- replacement/source nulling: N/A because accepted rows are Copy and no field is moved out; and
- `Drop`: N/A for the row by construction. The borrowed input owner remains live for the scanner's
  existing region and is dropped by its existing owner after the fused terminal.

For a rejected owning row, no scanner, descriptor, row slot, allocation, or side effect is
constructed.

The implementation closure matrix is:

| Case | Intended owner | Exact regression |
| --- | --- | --- |
| Type formation and scanner construction with a recursively Copy schema | `align_sema::check_json_scan` retains the existing concrete `json.scanner<Row>` type and input region | `m5::json_scan_copy_row_terminal_matrix` |
| Direct or transitive owning schema | `align_sema::check_json_scan` using canonical `struct_is_move`; rejection precedes HIR/MIR | `m5::json_scan_rejects_owned_row_fields` and `m5::json_scan_rejects_transitive_owned_row_fields` |
| Successful row replacement and filtered row | N/A for cleanup because sema proves the complete row Copy; existing MIR/runtime loop remains owner | `align_runtime::tests::json_scan_copy_row_no_owned_alloc` plus the filtered case in `m5::json_scan_copy_row_terminal_matrix` |
| Whole-row stage or reducer call | existing pipeline Move-argument checks plus the scanner schema predicate | `m5::json_scan_copy_row_terminal_matrix` |
| Malformed first/later row | existing runtime partial-decode cleanup; no successful Copy row needs Drop | `m5::json_scan_copy_row_error_matrix` |
| Exhaustion, empty input, `Result` return/`?`, and future early exit | existing fused-terminal MIR; row cleanup and source nulling are N/A by the Copy invariant | `m5::json_scan_copy_row_terminal_matrix` |
| Input ownership and scanner return/escape | existing scanner region follows the borrowed input; the request adds no owner or returnable row | existing `m5::json_scan_cannot_escape_its_input` |
| Whole-program check and run | `align_sema` plus existing driver pipeline | the named `m5` positive/negative matrix |
| Per-unit and imported-interface check | the scanner consumer applies the same canonical Move predicate to the imported concrete row definition and its complete interface hash | `modules::json_scan_imported_row_ownership` |
| Concrete generic monomorph construction | `align_sema::check_json_scan` applies the canonical DropPlan to each resolved local or imported monomorph and formats its public source-level type spelling | `m5::json_scan_generic_row_ownership` accepts `Wrap<i64>` and rejects `Wrap<array<i64>>`; `modules::json_scan_imported_row_ownership` does the same for `scan_schema.Wrap<T>` |
| Cache cold/hit/edit/revert | structural program fingerprint, imported interface hash, and sema-before-codegen boundary in `align_driver` | `cache_codegen::json_scan_row_schema_rejection` |
| Runtime ABI and hot loop | N/A: no production runtime/codegen or ABI change is permitted; the feature-gated owner regression may add only test code in the runtime source file | existing `m5` scanner corpus, `align_runtime::tests::json_scan_copy_row_no_owned_alloc`, and an accepted-schema MIR/LLVM comparison |
| Concurrent scanners and process-global state | N/A: the check is compile-time and accepted scanners retain their independent Copy handles, row slots, immutable descriptors, and existing runtime state | two accepted scanner terminals in one program plus the existing nested-scanner rejection |

### Acceptance / gate

Align compiler/runtime tests must:

1. reject direct fields of `array<i64>`, `array<f64>`, `array<bool>`, `array<str>`, and
   `array<Item>`, each with the exact `json.scan` Copy-row diagnostic above. Fixtures named `Row`
   and `BatchRecord` must respectively report `'Row'` and `'BatchRecord'`, proving the source-name
   substitution is not a literal placeholder;
2. reject an owned array reached through a nested struct, a direct object union payload, a nested
   object union payload, and an `array<Struct>` union payload; prove that the diagnostic traverses
   every variant rather than accepting a union because the selected input happens to use a Copy
   variant. For `Option<nested Move struct>`, the shipped Request 6 implementation base admits
   ordinary declared-record decode and therefore requires the scanner-specific Copy-row diagnostic;
   the scanner check must not infer a different oracle from the compiler's later behavior. A generic fixture
   declares `Wrap<T> { value: T }`: scanning the concrete `Wrap<i64>` monomorph must check and run,
   while `Wrap<array<i64>>` must fail with the exact row spelling `'Wrap<array<i64>>'`, proving
   ownership is classified after monomorphization;
3. accept recursively Copy rows containing every scalar width supported by JSON decode, borrowed
   `str`, nested structs, scalar/`str` options in `Some`, missing, and `null` states,
   `Option<CopyStruct>` in `Some`, missing, and `null` states, and shape-directed unions whose
   complete payload graph is Copy;
4. run the exact terminal matrix below once over the top-level-array bytes
   `[{"active":true,"score":2},{"active":false,"score":3},{"active":true,"score":4}]` and once
   over the same three objects separated by single LF bytes with no array delimiters. Each case
   uses a fresh scanner. Required results are:

   | Pipeline | Result |
   | --- | --- |
   | `.score.sum()` | `9` |
   | `.count()` | `3` |
   | `.score.reduce(1, mul)` | `24` |
   | `.score.any(gt_three)` | `true` |
   | `.score.all(positive)` | `true` |
   | `.score.min()` / `.score.max()` | `2` / `4` |
   | `.where(.active).score.sum()` | `6` |
   | `.where(is_active).score.count()` | `2` |
   | `.map(double_score).sum()` | `18` |
   | `.reduce(0, add_row_score)` | `9` |
   | `.any(row_gt_three)` / `.all(row_positive)` | `true` / `true` |

   `mul`, `gt_three`, and `positive` consume projected `i64`; `is_active`, `double_score`,
   `add_row_score`, `row_gt_three`, and `row_positive` consume the complete Copy `Row`. A second
   exact schema fixture declares
   `Leaf { name: str, note: Option<str> }`,
   `Choice { Text(str), Number(i64), Object(Leaf) }`, and
   `RichRow { id: u64, leaf: Leaf, maybe_leaf: Option<Leaf>, choice: Choice }`. For both framings,
   three rows with IDs `1`, `2`, and `3` select the string, number, and object variants respectively,
   exercise `note` as present, missing, and `null`, and exercise `maybe_leaf` as
   `Some(Leaf { name: "xy", note: None })`, missing, and `null`. A fresh scan for each assertion
   must produce `.count() == 3`; filtering by each ID and mapping a whole-row
   `maybe_leaf_name_len` function, which returns the present leaf's name length or `-1` for `None`,
   must produce `2`, `-1`, and `-1` respectively. These per-ID assertions observe the `Some`
   payload and independently distinguish it from the missing and explicit-`null` `None` rows;
   an aggregate count alone is insufficient. Separate compile-only cases cover the remaining
   integer and float widths and `Option` scalar types without multiplying them across every
   terminal. The existing JSON-schema rejection for `Option<enum>` remains covered by the general
   decode corpus and must precede the scanner ownership predicate;
5. prove all-clean rows, a filtered-out row, malformed input before the first row, malformed input
   after at least one successful row, exhaustion, and empty input retain their existing values,
   `Error.Code(1)` classification, and no row allocation;
6. add the feature-gated runtime owner test
   `align_runtime::tests::json_scan_copy_row_no_owned_alloc`. It snapshots
   `align_rt_alloc_count()` and `align_rt_free_count()` around direct
   `align_rt_json_scan_next` calls for clean, malformed, and exhausted Copy rows and requires zero
   delta. The test must acquire the existing process-global `ALLOC_COUNT_LOCK` as its first
   executable statement and hold the guard for the complete test body, including input/descriptor
   setup, both counter snapshots, every scanner call, and assertions. Run it with
   `cargo test -p align_runtime --features alloc-count json_scan_copy_row_no_owned_alloc`.
   Allocation by the Rust duplicate-field `SeenSet`, unrelated test harness, or input setup is
   outside the Align-owned counters;
7. prove deterministic validation order: a call without `import core.json` retains the existing
   capability-import diagnostic even when its arity is also invalid; with the capability imported,
   an unsupported typed-decode field retains its existing schema diagnostic; a valid Move row plus
   an invalid non-string input reports the Copy-row diagnostic; and an otherwise identical valid
   Copy row reports the input-type diagnostic;
8. prove semantic rejection occurs before MIR/codegen for every scanner-owned fixture in items 1–2:
   `alignc check` and `alignc emit-mir` must both report the scanner-specific semantic diagnostic,
   including the shipped `Option<nested Move struct>` case, and `emit-mir` must produce no MIR on
   stdout. The distinct multi-invalid fixtures in item 7 retain their earlier capability, schema,
   or input-type diagnostics and are not ownership fixtures for this assertion. No descriptor table,
   object file, executable, or runtime call may be produced for an owning-row rejection;
9. prove the scanner-only boundary by retaining the row declarations as valid types and by
   decoding, encoding, and dropping through ordinary JSON each supported direct, nested, and union
   Move schema that `json.scan` rejects. The optional fixture is admitted by ordinary decode at
   the shipped Align commit:
   `Inner { items: array<i64> }` and
   `Row { inner: Option<Inner>, score: i64 }`; decoding
   `{"inner":{"items":[1,2]},"score":3}` and immediately encoding the owner must produce those
   exact bytes before the value leaves scope successfully. The distinct decoded-owner transition
   gaps described above remain deferred to Request 15.
   Request 15 must audit every transition after an owner becomes live and include
   allocation-count regressions for successful and failed top-level AoS fallback after a
   speculative owner write, plus malformed-later-element and trailing-garbage cleanup for top-level
   `array<MoveStruct>`. SoA is N/A for these owner regressions because sema excludes owned columns;
10. prove whole-program and per-unit checking produce the same acceptance and exact diagnostic
    when `Row` is local and when its complete definition is imported. The imported fixture's module
    is exactly `scan_schema`; it declares `pub ImportedRow` and
    `pub Wrap<T> { value: T }`. Consumers annotate
    `json.scanner<scan_schema.ImportedRow>` and
    `json.scanner<scan_schema.Wrap<array<i64>>>`. Both checking modes must report the source-level
    public spellings `'scan_schema.ImportedRow'` and
    `'scan_schema.Wrap<array<i64>>'` respectively; neither a bare declaration name nor an internal
    spelling containing `$` is permitted. `scan_schema.Wrap<i64>` must check and run in both modes.
    `align_sema::check_json_scan` therefore owns a user-facing declared-type display rather than
    inserting `StructDef.source_name` directly.
    A reachable imported schema edit must change its interface hash and make the unchanged consumer
    reject on its next `check-per-unit`;
11. use an isolated cold cache for a three-codegen-unit fixture: a scanner consumer, its
    row-schema/helper module, and an unrelated control, each with at least one emitted function.
    The first accepted build misses all three and an identical second build must hit all three.
    Editing the reachable schema from `score: i64` to
    `scores: array<i64>` must reject before codegen and leave the complete cache path set and every
    cache file's bytes unchanged. Restoring the original schema bytes must hit all three original
    entries. A compiler build-identity change makes all prior entries ineligible;
12. update `draft.md`, `docs/language-spec.md`, `docs/design-notes.md`,
    `docs/open-questions.md`, and the English authoritative JSON design first, then synchronize
    the design's maintained Japanese translation. The design, condensed language specification,
    semantic diagnostic, and compiler tests must all describe the same recursively Copy row
    boundary; and
13. run the existing `json.scan` test corpus. From the Align repository root, run the baseline and
    candidate release compilers over the same checked-in
    `tests/fixtures/json-scan-copy-row.align` path. `ALIGN_SCAN_BASELINEC` is the release compiler
    built from `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`;
    `ALIGN_SCAN_CANDIDATEC` is the release compiler built from the proposed Align head; and
    `ALIGN_SCAN_COMPARE_DIR` is a newly created, validated empty temporary directory. Run:

    ```text
    "$ALIGN_SCAN_BASELINEC" emit-mir tests/fixtures/json-scan-copy-row.align >"$ALIGN_SCAN_COMPARE_DIR/base.mir" 2>"$ALIGN_SCAN_COMPARE_DIR/base.mir.err"
    "$ALIGN_SCAN_CANDIDATEC" emit-mir tests/fixtures/json-scan-copy-row.align >"$ALIGN_SCAN_COMPARE_DIR/candidate.mir" 2>"$ALIGN_SCAN_COMPARE_DIR/candidate.mir.err"
    "$ALIGN_SCAN_BASELINEC" emit-llvm tests/fixtures/json-scan-copy-row.align --stage raw >"$ALIGN_SCAN_COMPARE_DIR/base.ll" 2>"$ALIGN_SCAN_COMPARE_DIR/base.ll.err"
    "$ALIGN_SCAN_CANDIDATEC" emit-llvm tests/fixtures/json-scan-copy-row.align --stage raw >"$ALIGN_SCAN_COMPARE_DIR/candidate.ll" 2>"$ALIGN_SCAN_COMPARE_DIR/candidate.ll.err"
    ```

    Each command must exit zero and every `.err` file must be empty. `cmp -s` must report equality
    for `base.mir`/`candidate.mir` and `base.ll`/`candidate.ll`, without normalization. The
    implementation diff must contain no production MIR, codegen, or runtime
    source change; the feature-gated runtime owner test required by item 6 is the only runtime-file
    exception. The identical raw LLVM must retain the exact `align_rt_json_scan_next` declaration
    and call signature. Runtime performance measurement is N/A because accepted HIR/MIR/codegen
    and the runtime entrypoint are unchanged; this request makes no performance claim.

No new runtime entrypoint is expected. If implementation instead changes
`align_rt_json_scan_next` or the compiler/runtime ABI, Align must update its design first, name the
exact signature and identity coupling, and reopen this request's ABI, cleanup, and performance
closure before implementation.

Items 2, 8, and 9 record the optional-schema outcome of the Request 6 implementation at the
shipped Align commit `e65448b744c04e3868d079eef8b45ce0d43ac8ee`. That commit admits
`Option<Move-struct>` for ordinary declared-record decode and rejects a reachable Move row for
`json.scan`; the adoption oracle is therefore fixed, not inferred from whichever compiler happens
to run. Request 15 must preserve all three checked-in Request 6 regressions: scanner checking keeps
the Copy-row diagnostic and no-MIR assertion, while ordinary optional decode keeps its positive
admission test. Request 15 adds cleanup evidence without becoming a second owner for scanner
eligibility.

### align-llm adoption gate

Before the full installed `FRESH-IMAGE-REQUEST6` profile, align-llm may merge one enabling
`FRESH-IMAGE-REQUEST6-BOUNDARY` checkpoint. This checkpoint is deliberately non-evidence and does
not advance this request's lifecycle. It installs only the image-owned
`/usr/local/libexec/align-llm/request6-adoption-boundary-entrypoint` and the exact
`fresh-supervise --mode ordinary-adoption-boundary` selector. The boundary verifies the image and
schema-2 manifest tuple, retains the absolute Align root as FD 18, dispatches the retained
dispatcher through FD 14 with the strict reduced argv/env/fd contract, and rejects both an absent
worker and any present or malformed worker as `json-scan adoption: ERROR revision\n` before source
snapshot, signing, helper, namespace, Make, or compiler work. It creates no nonce, supervisor
channel, capsule, worker memfd, proof, bwrap child, or namespace helper. Direct boundary-dispatcher
paths are permitted only as untrusted diagnostics that can reach the same revision rejection; they
have no supervisor-origin proof and can never produce ordinary evidence. Malformed boundary vectors
and the full `ordinary-adoption` vector are rejected. The boundary smoke may prove only those
installed checks; it must not be recorded as ordinary adoption or as evidence for the full Request 6
transport.

After `ALIGN_MERGED`, align-llm owns a consumer adoption checkpoint, but it must not update
`.align-revision`, run a pin-changing verification, or advance this request to
`ALIGN_LLM_VERIFIED` until the merged Section 9 contract's FRESH-IMAGE, FRESH-WORKER, and separately
verified FRESH-IMAGE-REQUEST6 profile extension have all merged. They must make canonical `make ci`
build and use the pinned compiler through the
reviewed fresh-build, identity, process, timeout, cache, and cleanup contract; this request must
consume that shipped path rather than recreate it. The
adoption may share one pin update with the other merged prerequisites needed by the same consumer.
It release-builds and pins the shipped Align revision and adds the focused
`json-scan-row-ownership-adoption` target without adding that qualification to routine aggregates.
The target runs
`scripts/run-json-scan-row-ownership-adoption-smoke` over
`eval/fixtures/json-scan-row-ownership-adoption/`.

Because the target is intentionally outside the routine hosted/capable aggregate lists, the
Section 9 fresh-capable profile uses the image-owned focused request
`make --no-print-directory json-scan-row-ownership-adoption`. The trusted supervisor accepts that
exact vector as the authenticated `adoption` mode, and the worker runs the target in the same
private source, runtime, cache, process, temporary-filesystem, and cleanup boundary as the capable
aggregate with `ALIGNC_CACHE=off` and `/tools/fresh-alignc`. A direct host invocation that merely
sets `ALIGNC=/tools/fresh-alignc` is not fresh evidence. The focused target remains absent from
`HOSTED_CHECK_TARGETS`, `CAPABLE_ONLY_CHECK_TARGETS`, and `SERIAL_CHECK_AGGREGATES`; the final
fresh `make --no-print-directory ci` is a separate required gate.

The ordinary profile's evidence-bearing public request enters through the already trusted image-owned
`/usr/local/libexec/align-llm/fresh-supervise`. The corrected implementation keeps this native ELF as
the direct parent of the ordinary dispatcher until the dispatcher exits. It does not exec a Python
carrier before dispatch, and a Python interpreter digest or reconstructed command line is not a
supervisor identity. A short-lived embedded C preflight child in the same native ELF may run before
the ordinary channel exists. It receives only the sealed image-attestation, manifest, and retained
dispatcher descriptors, validates only image-owned inputs (including `/proc/self/exe`), emits no
bytes, and must not open either repository, create a nonce or channel, sign a capsule, or launch a
worker. The native parent reaps the preflight and direct dispatcher only; the dispatcher, worker, and
namespace helper own their respective inner reaps. After preflight succeeds, the native parent creates
the ordinary descriptors and channel, owns the bounded public transport pipes, and forwards exactly
the dispatcher-produced result once after reaping that direct child. Legacy `ci`, `build`, and
`self-test` retain their existing carrier path because they have no ordinary parent-authentication
contract.

FRESH-IMAGE-REQUEST6 adds the exact
`--mode ordinary-adoption` request to that supervisor. Before dispatch, `fresh-supervise` authenticates
the runner-image envelope and fixed schema-2 manifest, opens the Request 6 dispatcher
`/usr/local/libexec/align-llm/request6-adoption-entrypoint` through a retained no-follow descriptor,
checks its manifest digest and complete interpreter/loader closure, and creates a
`SOCK_SEQPACKET|SOCK_CLOEXEC` supervisor channel. It validates the absolute `ALIGN_REPO` walk and
retains the final descriptor as FD `18` before creating the channel. It forks exactly one dispatcher
child; the fresh-supervise parent keeps one channel endpoint, and the child receives the other as FD
`16` plus the retained Align-root descriptor as FD `18`.
Only the child then invokes the retained dispatcher descriptor with
`execveat(AT_EMPTY_PATH)` at fixed FD `14`. The parent first sends one fresh 32-byte dispatch
ticket `T` and remains alive with the channel open. The dispatcher accepts that channel only when
`SO_PEERCRED` identifies its current parent, the peer PID's `/proc/<pid>/stat` start-time remains
unchanged through the complete admission, `/proc/<pid>/stat` and `/proc/<pid>/cmdline` are opened
with no-follow flags, and the one explicitly permitted procfs magic-link operation opens
`/proc/<pid>/exe` with `O_RDONLY|O_CLOEXEC` and hashes the retained executable bytes to the
image-attested supervisor digest. The dispatcher fstats that descriptor, rechecks the peer start-time
and executable device/inode after hashing, and rejects an exec transition, short read, replacement,
or digest mismatch. This controlled `/proc/<pid>/exe` exception is the only symlink-like path
operation in the peer predicate; ordinary paths retain the no-follow rule. The bounded
`/proc/<pid>/cmdline` bytes are exactly
`fresh-supervise\0--mode\0ordinary-adoption\0`, and the first message is exactly `T`. A direct
dispatcher invocation cannot satisfy the parent-PID, executable, command-line, and one-time-channel
conjunction.
Its fixed child argv,
including the required `argv[0]`, is:

```text
["request6-adoption-entrypoint", "--mode", "ordinary-adoption", "--project-root-fd", "4",
 "--image-attestation-fd", "6", "--manifest-fd", "8", "--align-repo-root-fd", "18",
 "--align-repo-absolute",
 "<normalized-absolute>", "--align-repo-relative", "<canonical-relative>",
 "--invocation-nonce-fd", "15", "--supervisor-channel-fd", "16"]
```

After the retained dispatcher descriptor is consumed, the child clears `FD_CLOEXEC` on FDs `4`, `6`,
`8`, `15`, `16`, and `18`, closes every other inherited data descriptor, and invokes `execveat(AT_EMPTY_PATH)`
on FD `14`; FD `14` is the only executable authority and is not a data descriptor. FD `15` is a fresh
supervisor-created sealed 32-byte nonce; it is
never caller-selected. The two
path values are supervisor-validated named inputs, not positional arguments or ambient environment;
the dispatcher independently recomputes the relative value from the retained project-root identity
and rejects a mismatch. A
repository checkout cannot replace the first executable
or the retained dispatcher bytes; invoking the dispatcher pathname directly is an untrusted developer
check and cannot claim ordinary evidence: it lacks the inherited supervisor channel and its
authenticated peer. A caller-created socket, ticket, nonce, or descriptor set is not accepted. The
dispatcher accepts no positional arguments. The repository
`scripts/run-json-scan-row-ownership-adoption` file is source data, not a public executable: the
authenticated dispatcher opens it descriptor-relatively, authenticates its bounded bytes and the current
project HEAD/index/raw snapshot, and seals a worker snapshot only after those identities are bound into
the signed `ordinary-adoption/v2` capsule. The capsule binds the
request/API, fresh invocation nonce, supervisor dispatch-ticket digest, project HEAD and object format,
project index, raw-tree, and complete source-exception digests, canonical `ALIGN_REPO` relative path and Align identity, worker
relative path and SHA-256, image digest, image-attestation digest, manifest digest, and entrypoint
digest. The dispatcher verifies the supervisor channel before signing, so it is the only producer
allowed to create this capsule on the evidence-bearing path. The worker verifies the capsule and
worker snapshot before staging the private source. After signing, the dispatcher computes
`C = SHA-256(complete DSSE envelope bytes)` and sends the raw 32-byte `C` to the still-live
supervisor parent. The parent replies on FD `16` with exactly one raw 32-byte worker-admission proof
`P = SHA-256("align-llm/ordinary-adoption/worker-admission/v2\0" ||
dispatch_ticket_sha256_bytes || invocation_nonce_bytes || C)`, where the three binary operands
`dispatch_ticket_sha256_bytes`, `invocation_nonce_bytes`, and `C` are each exactly 32 bytes and the
domain prefix is the literal UTF-8 string including its trailing NUL. The proof remains queued on the
channel; the dispatcher does not consume it. The worker
peeks and verifies `P` without consuming it, and the namespace helper consumes and verifies the same
single proof before any Make child. The parent keeps FD `16` open until the dispatcher/worker/helper
exits; a channel hangup, peer identity change, extra message, missing proof, or proof mismatch fails
closed. A replayed capsule, worker, or nonce therefore cannot pass with a new admission channel
because the new parent proof binds the current capsule envelope digest and ticket digest. The Make target remains an internal worker
target for the authenticated fresh vector. The implementation also adds the private Make target
`align-build-only`: it has no prerequisites, has the same authenticated `$(CARGO)` build recipe as
`align-build`, and is invocable by the ordinary wrapper's fixed second vector only. The existing
`align-build: align-revision` prerequisite remains the developer-facing Make contract; the wrapper does
not invoke that target after its separate revision child. The authenticated dispatcher validates its
arguments and inherited Make-control variables before it starts the namespace launcher; a non-empty
`MAKEFLAGS`, `GNUMAKEFLAGS`, or `MAKEOVERRIDES`, an alternate goal, an alternate makefile, or any other
argument is rejected in the input phase, not consumed by GNU Make. Its success stdout is exactly
`json-scan adoption: PASS\n`, stderr is empty, and failures suppress child streams and emit exactly one
bounded `json-scan adoption: ERROR <phase>\n` line where `phase` is one of `input`, `toolchain`,
`revision`, `build`, `fixture`, or `cleanup`. The worker exit-status table is fixed: status `0` means
success; statuses `1` through `6` mean, respectively, `input`, `toolchain`, `revision`, `build`,
`fixture`, and `cleanup`, and the worker returns the first failed phase even when reverse cleanup also
runs. The dispatcher is the worker's direct parent and sole semantic result producer. The native
`fresh-supervise` parent is the public-stream transport owner: it drains both dispatcher pipes with
an 8,192-byte read size, retains at most 65,536 bytes per stream, validates the complete result after
reaping the dispatcher, and forwards those bytes exactly once. It never synthesizes or duplicates a
phase result. If the worker exits by signal or with an exit status outside that table before returning
a final phase result, the dispatcher emits the special terminal `UNOBSERVED_EXIT` result
`json-scan adoption: ERROR unobserved\n`;
`unobserved` is not a phase and is the only ordinary outcome outside the six-phase set. The dispatcher
produces this semantic result even when the worker is uncatchably killed. A dispatcher signal,
unknown status, partial/extra result, pipe overflow, or native transport cleanup failure is instead a
native `fresh compiler: ERROR TRUST supervisor\n` with child bytes suppressed. Validation order is fixed: (1) argv,
Make-control
variables, cwd, and allowed `HANDOFF.md` exception; (2) project HEAD, index, clean-tree, and raw
snapshot; (3) fixed entrypoint, attestation, capsule, and manifest bytes; (4) worker snapshot and Align
Git view, config, helper, alternate-object, and linked-worktree metadata; (5) tool/runtime/cache identity;
(6) private-root staging and final pre-child snapshots; (7) the three child vectors; and (8) reverse
cleanup. The phase mapping is exact. `input` covers the dispatcher parent/channel peer admission,
the one-time ticket length/order/digest, named-option and environment grammar, cwd, the absolute and
relative path pair, nonce descriptor shape/value/freshness, and Make-control-variable rejection.
`revision` covers project, Align, worker, and source-exception identity or source-content failures at any step,
including a mutation detected during staging or a final pre-child snapshot, an `ALIGN_REPO` mismatch
after FD 14 dispatch, and a capsule field whose retained project/Align/worker identity differs from
the independently observed source. `toolchain` covers fixed image attestation, manifest, entrypoint
closure, capsule signer/DSSE construction or key policy, authority memfd predicates and descriptor
handoffs, lock/cgroup admission, bwrap and namespace setup, runtime/tool/cache identity, private-root
mount/quota, and every other staging-infrastructure failure; a malformed capsule wire from an
otherwise trusted signer is also `toolchain`, while a capsule/source identity mismatch is `revision`.
`.align-revision` mismatch and every `align-revision` launch, timeout, output-overflow, nonzero, or
cancellation outcome are `revision`. A failed `execveat(AT_EMPTY_PATH)` of FD 14 before the dispatcher
starts is `fresh compiler: ERROR TRUST supervisor\n`; after FD 14 has started, dispatcher and worker
validation failures use the ordinary phase set. Before the first child, a supervisor-channel hangup
is `toolchain`; while a child row is active it is that row's phase (`revision` for the revision row,
`build` for the build row, or `fixture` for the focused row); during reverse cleanup it is `cleanup`.
The build-only child, compiler/archive/launcher source copy, and post-build namespace bundle/handoff
setup are `build`; the focused child and fixture/compiler result are `fixture`; and cleanup is
`cleanup` only when every earlier phase and child succeeded. The first failed phase wins. After an
earlier failure, cleanup still runs but cannot overwrite the primary phase. A worker signal death or
unknown exit status is `UNOBSERVED_EXIT` because no phase can be proved; it is emitted only when no
final phase result was observed. No later validation or cleanup side effect changes that precedence.

The ordinary wrapper's only caller-selected source input is `ALIGN_REPO`, the absolute clean Align
worktree. Toolchain and dependency inputs come from the fixed installed-profile manifest at
`/usr/local/share/align-llm/fresh-toolchain.json`; the wrapper accepts no caller-selected manifest
path, manifest digest, tool path, cache path, or per-tool override. That manifest is the
image-owned schema-2 object authenticated by the Section 9 runner-image attestation and contains
the ordered tool records, runtime bindings, complete Rust prefix, LLVM/native inputs, and Cargo
cache manifest. Ordinary host evidence is valid only on that declared installed profile; an
arbitrary local machine may run the smoke as an untrusted developer check but may not claim the
ordinary adoption result until the fixed manifest and attestation are present.

The trusted supervisor opens the current project root from its actual cwd and the caller-selected
absolute `ALIGN_REPO` before it creates the supervisor channel. It opens `/` as temporary root FD
`17`, lexically validates the absolute path, walks every component from that root with
`openat(O_PATH|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC)`, records and rechecks each ancestor device/inode,
and retains the final descriptor as FD `18`; it closes FD `17` before channel creation. A missing,
symlinked, replaced, non-directory, or identity-changing component is a pre-FD-14
`fresh compiler: ERROR TRUST supervisor\n` failure.
The dispatcher receives FD `18`, verifies its retained identity against the signed canonical relative
path, and uses that descriptor for every later Git and copy operation; it never reopens the absolute
pathname. Before it starts bwrap or the namespace supervisor, it proves the project HEAD, index,
raw-tree digest, clean-tree exception, and Align identity, then opens
`scripts/run-json-scan-row-ownership-adoption` as a bounded single-link
regular source file. It reads and hashes that file through the retained descriptor, rechecks its
device, inode, type, link count, mode, and size, and seals the exact bytes into a read-only memfd.
The authenticated dispatcher signs the `ordinary-adoption/v2` capsule only after all those checks,
after verifying the supervisor channel and one-time dispatch ticket, and binds the capsule and worker
snapshot to the fixed manifest, image-attestation, supervisor, fresh nonce, and complete
source-exception digests. It passes the
sealed capsule on FD `12`, the sealed worker bytes on FD `13`, the sealed nonce challenge on FD
`15`, the retained Align-root descriptor on FD `18`, and the supervisor channel on FD `16` to the
fixed repository-worker vector
`/usr/bin/python3 -I -B /proc/self/fd/13 --project-root-fd 4 --align-root-fd 18 --capsule-fd 12
--invocation-nonce-fd 15 --supervisor-channel-fd 16`. Before this exec it clears `FD_CLOEXEC` on FDs
`4`, `12`, `13`, `15`, `16`, and `18` and uses
`close_fds=True, pass_fds=(4, 12, 13, 15, 16, 18)`; the memfd creator's
`MFD_CLOEXEC` trace remains recorded even though the required inheritance edge clears the descriptor
flag.
The dispatcher leaves the supervisor channel open and passes it to the worker. The worker verifies
the inherited peer while it remains in the outer PID namespace, then closes FD `18` after its final
source identity check. It executes only from that sealed descriptor, owns the bwrap/cgroup/staging
setup, and supplies the three sealed FDs to bwrap as
`--ro-bind-data 12 /authority/capsule`, `--ro-bind-data 13 /authority/worker`, and
`--ro-bind-data 15 /authority/nonce`; it also passes FD `16` as the fixed supervisor channel. The
pinned bwrap consumes the three sealed authority source descriptors by copying their bytes into
read-only bind paths. The
exact vector includes `--as-pid-1 --sync-fd 16`: on the pinned bwrap this makes FD `16` part of the
PID-1 helper's inherited descriptor set; `--sync-fd` without `--as-pid-1` is not an accepted vector
and its non-forwarding behavior is a negative platform test. Bwrap does not forward arbitrary FDs. The
namespace supervisor opens only those fixed bind paths, re-verifies their bounded bytes against the
capsule, consumes and verifies the one queued worker-admission proof on FD `16`, rehydrates local
fixed-name sealed memfds for its own observable predicate checks, and never executes the worker a
second time. The dispatcher and worker perform all peer PID, start-time, executable, and command-line
authentication before entering the PID namespace. The namespace helper does not attempt to resolve an
outer PID through its private `/proc`; it checks the already-authenticated channel for `POLLHUP`, EOF,
or protocol violation before setup, before every Make row, and while any row is active. A supervisor
hangup terminates owned children and reports the owning phase.
A worker replacement, same-size edit, dirty-tree swap, replayed capsule, or later pathname restore
therefore fails or executes only the already-authenticated bytes; the host repository script never
runs before this boundary.

The `ordinary-adoption/v2` capsule reuses the Section 9 DSSE envelope and pinned image-deployment
key policy with predicate type `https://align-llm.dev/attestations/ordinary-adoption/v2`. Its canonical
payload field order is `api`, `request`, `invocation_nonce`, `dispatch_ticket_sha256`, `project_head`,
`project_object_format`, `project_index_sha256`, `project_raw_tree_sha256`, `source_exception_sha256`, `align_head`,
`align_object_format`, `align_repo_relative`, `worker_relative`, `worker_size`, `worker_sha256`,
`image_digest`, `image_attestation_sha256`, `manifest_sha256`, and `entrypoint_sha256`; all digest values are lowercase SHA-256 or the fixed
SHA-1 head grammar, and no unknown, duplicate, NUL-bearing, or out-of-order field is accepted. The
capsule signer is the installed profile's invoking-UID seed and its verifier/key policy are image-owned
deployment inputs; callers cannot provide a capsule, signer, digest, or alternate predicate through the
environment or command line.

The capsule predicate uses the Section 9 canonical JSON rules: UTF-8, the listed field order, two-space
indentation, one final LF, no duplicate or unknown fields, and the complete JSON escape table. `api` is
exactly `ordinary-adoption/v2`; `request` is exactly `json-scan-row-ownership-adoption`;
`project_object_format` and `align_object_format` are exactly `sha1`; both heads are exactly 40 lowercase
hexadecimal bytes; `invocation_nonce` is exactly 43 unpadded base64url characters encoding the fresh
32-byte supervisor challenge; `dispatch_ticket_sha256`, `project_index_sha256`,
`project_raw_tree_sha256`, `source_exception_sha256`, `worker_sha256`, `image_attestation_sha256`, `manifest_sha256`, and
`entrypoint_sha256` are exactly 64 lowercase hexadecimal bytes; `image_digest` is `sha256:` followed
by 64 lowercase hexadecimal bytes; `worker_size` is an unsigned
64-bit integer no larger than `fresh_worker_max_bytes = 4194304`; `align_repo_relative` is a non-empty
relative path with no NUL, empty component, or absolute prefix; and `worker_relative` is exactly
`scripts/run-json-scan-row-ownership-adoption`. Strings reject non-UTF-8, NUL, control characters,
overlong values, and unpaired surrogates. The DSSE envelope uses the exact Section 9 `payloadType`,
unpadded base64url, PAE, key-id, and signature grammar.

The supervisor obtains the nonce from `getrandom`, seals the exact 32 bytes in FD `15`, and never
accepts a caller-supplied nonce. The dispatcher copies no nonce from a path or environment: it checks
FD `15`, places its unpadded base64url value in the signed capsule, and passes the same sealed FD to
the worker and bwrap as the fixed `/authority/nonce` source. The worker verifies that FD `15` equals
the capsule field before bwrap consumes it; the namespace helper verifies the bound bytes and its
local rehydrated memfd before any Make child. A new nonce is generated for every supervisor admission,
so replaying an old capsule, worker, or nonce against a new invocation fails before staging even when
every stable project, image, and worker digest is unchanged.

The authority descriptors have one exact wire and lifetime contract. FD `12` (the DSSE capsule) and
FD `13` (the repository-worker snapshot) are created with
`memfd_create(<fixed-name>, MFD_ALLOW_SEALING|MFD_CLOEXEC)`; FD `15` (the nonce) is created with the
same flags. The names are respectively
`align-llm-ordinary-adoption-capsule`, `align-llm-ordinary-adoption-worker`, and
`align-llm-ordinary-adoption-nonce`; they are image-owned constants, not caller input. Linux does not
expose a post-hoc `MFD_ALLOW_SEALING` origin bit, so the contract does not pretend that creation flags
can be recovered from `fstat`. The creator's construction trace must record that exact syscall and
the receiver accepts only the following complete, observable memfd predicate: `fstat` reports
`S_IFREG` and `st_nlink == 0`, `fstatfs` reports `TMPFS_MAGIC == 0x01021994`, `F_GET_SEALS` succeeds
with exactly `F_SEAL_WRITE|F_SEAL_GROW|F_SEAL_SHRINK|F_SEAL_SEAL`, and
`readlink(/proc/self/fd/<fd>)` is exactly `/memfd:<fixed-name> (deleted)`. The fixed name and proc
link check reject an unlinked ordinary or tmpfs file even if a future kernel permits seals on that
file; the filesystem/type, zero-link, and exact-seal checks reject every other regular-file shape.
Each object is written once from offset zero, sealed, and rewound to offset zero before its first
handoff. `MFD_CLOEXEC` is a construction invariant recorded by the creator; Linux exposes no
post-hoc origin bit, and the required inheritance edges intentionally clear `FD_CLOEXEC` only on
the listed descriptors. The receiver therefore does not claim that an omitted creation flag is
observable after a later `fcntl` or exec boundary. FD `12` has an exact size in
`1..ordinary_capsule_max_bytes` where
`ordinary_capsule_max_bytes` is `1048576`; FD `13` has an exact size in
`1..fresh_worker_max_bytes` (`4194304`); FD `15` has exactly `32` bytes. There are no trailing bytes.
The dispatcher and worker check the complete original memfd predicate, current offset, size, and
complete seal set before bwrap consumes the sources. The namespace helper checks each fixed read-only
bind path byte-for-byte, then creates and checks local fixed-name sealed memfds before using the bytes.
A caller-provided regular file, tmpfs file, wrong memfd name, missing `MFD_ALLOW_SEALING` or
`MFD_CLOEXEC` construction trace, extra or missing seal, nonzero offset, short read, or appended byte
is a `toolchain` failure after FD 14 dispatch and before a Make child; only the corresponding
pre-dispatch supervisor failure uses `TRUST`. The acceptance matrix
must include ordinary regular files, unlinked tmpfs files, a correctly sealed memfd with each fixed
name, wrong-name memfds, every missing/extra seal, and a creator that did not use the required flags;
the last case is rejected by the creator trace. The test must not claim that the receiver can recover
the omitted flag from the resulting descriptor.

The authority offset ledger is normative for byte-bearing descriptors only. FD `12`, FD `13`, and
FD `15`, plus every local sealed memfd rehydrated from them, use `pread` where available and never
rely on an inherited offset; after every verifier or interpreter read, the owner executes
`lseek(fd, 0, SEEK_SET)` and requires a zero result. O_PATH identity descriptors, directory bind
sources, the supervisor socket, and executable authorities have no byte-offset contract: they are
validated through `fstat`/identity checks or their declared exec/bind operation and are never passed
to `lseek` or `pread`. Immediately before each data-bearing edge below, the sender repeats the seek
and records offset zero; the receiver repeats it before verification and again before the next edge:

| Edge | Sender action at offset zero | Receiver action before use |
| --- | --- | --- |
| supervisor -> FD-14 dispatcher | Rewind FD `15`; pass FD `15`, the named project/image/manifest descriptors, retained Align-root FD `18`, and the connected supervisor-channel FD `16`; FD `14` is an executable descriptor and has no data offset contract | Dispatcher validates the channel peer/ticket and retained FD `18`, rewinds and verifies FD `15` before nonce read |
| dispatcher -> sealed worker Python | Rewind FD `12`, `13`, and `15` after capsule construction; revalidate identity-only FD `18` without an offset operation; clear `FD_CLOEXEC` on `4`, `12`, `13`, `15`, `16`, and `18`; invoke `/usr/bin/python3 -I -B /proc/self/fd/13` with `close_fds=True, pass_fds=(4,12,13,15,16,18)` | Worker rewinds the three authority fds after Python has opened the `/proc/self/fd/13` source, verifies them, revalidates FD `18` by identity without `lseek`/`pread`, peeks the queued proof on FD `16`, then closes FD `18` after the final source check |
| worker -> bwrap | Rewind FD `12`, `13`, and `15` after worker verification; revalidate the identity-only descriptors in `B` without offset operations; clear `FD_CLOEXEC` on every descriptor in `B`; FD `18` is closed before this edge; FD `27` remains `FD_CLOEXEC` and is retained only by the forked bwrap launcher child for direct `execveat(AT_EMPTY_PATH)`, not by a Python `pass_fds` member | Pinned bwrap consumes FD `12`, `13`, and `15` through fixed `--ro-bind-data` operations, consumes FD `20..26`, `40..(40+N-1)`, and `400..(400+T-1)` through fixed `--ro-bind-fd` operations, retains FD `16` because the exact vector includes `--as-pid-1 --sync-fd 16`, closes every consumed source descriptor after binding, and performs no arbitrary-FD forwarding |
| bwrap -> namespace helper | The PID-1 helper receives only fixed path arguments plus the inherited supervisor channel FD `16`; FD `27` was closed by the successful bwrap exec | Helper opens the three fixed read-only bind paths with no-follow flags, consumes and verifies the one queued proof on FD `16`, and uses `pread`; it then rehydrates and rewinds local sealed memfds before verification |
| namespace helper verification | Use `pread` and require offset zero after each read; no authority descriptor, proof channel, or bind-path fd is passed to a Make child; peer PID/procfs checks are N/A inside the private PID namespace and are completed by dispatcher/worker before bwrap | Close all local authority memfds, FD `16`, and bind-path descriptors only after the final row and reverse cleanup; every Make child sees exactly `{0,1,2}` |

Any failed seek on a byte-bearing descriptor, changed data offset, unexpected short read, identity
failure, or authority descriptor present after the close boundary is a `toolchain` failure after FD
14 dispatch. FD `14` and FD `27` are executable authorities, and FD `18` is an O_PATH identity
authority: each contract is retained identity, closure, and its declared `execveat(AT_EMPTY_PATH)` or
descriptor-relative operation. An attempt to read any of them through an undeclared path is a
`toolchain` failure rather than an offset exception once FD 14 has started.

The checked-in `ordinary-adoption-v2-wire-golden` predicate uses deterministic zero-filled digests,
project head `1111111111111111111111111111111111111111`, and Align head
`2222222222222222222222222222222222222222`. Its canonical predicate SHA-256 is
`2c1cc89bfdc4f48c97a44e7cbf6ec1e9d34daff710ce40972fe37e1f6741f1fd`; the 55-byte predicate type
DSSE pre-authentication encoding is 1,385 bytes and has SHA-256
`92ef881cc93e610563883f54cf06311985caedc9925736a4fca90067c6687f64`. The golden predicate bytes are:

```json
{
  "api": "ordinary-adoption/v2",
  "request": "json-scan-row-ownership-adoption",
  "invocation_nonce": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
  "dispatch_ticket_sha256": "0000000000000000000000000000000000000000000000000000000000000008",
  "project_head": "1111111111111111111111111111111111111111",
  "project_object_format": "sha1",
  "project_index_sha256": "0000000000000000000000000000000000000000000000000000000000000001",
  "project_raw_tree_sha256": "0000000000000000000000000000000000000000000000000000000000000002",
  "source_exception_sha256": "0c685027b378e6ef448e8efd807532eb8f056de04f550e884d56a5ef0834ead0",
  "align_head": "2222222222222222222222222222222222222222",
  "align_object_format": "sha1",
  "align_repo_relative": "../align",
  "worker_relative": "scripts/run-json-scan-row-ownership-adoption",
  "worker_size": 123,
  "worker_sha256": "0000000000000000000000000000000000000000000000000000000000000003",
  "image_digest": "sha256:0000000000000000000000000000000000000000000000000000000000000004",
  "image_attestation_sha256": "0000000000000000000000000000000000000000000000000000000000000007",
  "manifest_sha256": "0000000000000000000000000000000000000000000000000000000000000005",
  "entrypoint_sha256": "0000000000000000000000000000000000000000000000000000000000000006"
}
```

The installed manifest's runtime-binding list has three additional fixed ordinary-adoption records: the
image-owned executable at target `/usr/local/libexec/align-llm/request6-adoption-entrypoint`, the
executable file at target `/usr/bin/adoption-namespace`, and the root-owned mode-`0444` raw public key
at target `/usr/local/share/align-llm/run-verifier.pub`. The executable files have complete
interpreter and library closures. All three are fixed runtime bindings rather than PATH-discovered
tool records; the key binding makes the installed run-verification key available inside the outer
tmpfs-rooted bwrap namespace at the same authenticated path used by the namespace helper. Every ordered `tools` record, including
`make`, `git`, `tr`, `bash`, and the other core utilities, is separately retained and copied into the
namespace-owned `/tools` inventory described below. A missing record, incomplete closure, digest
mismatch, or replacement is a `toolchain` failure before the first child.

The wrapper opens and authenticates the fixed manifest, every named tool, required native file, and
cache descriptor with no-follow checks, records the attested digest, and rejects rustup shims,
symlink aliases, version mismatches, and mutable replacement before the first Make child. The
manifest's Rust runtime binding is the complete Rust 1.96.0 prefix, preserving `bin`, `lib`, and
`lib/rustlib` layout including `librustc_driver` and target libraries; staging only `cargo` or
`rustc` is forbidden. It copies the accepted cache into a unique private Cargo home and sets
`CARGO_NET_OFFLINE=true`; no registry, Git, proxy, credential, or network fallback is allowed. It
derives the exact `CARGO`, `RUSTC`, `LLVM_CONFIG`, `LLVM_SYS_221_PREFIX`, `CC`, `CXX`, `AR`,
`RANLIB`, linker, and runtime search paths from the attested manifest; it clears `RUSTUP_HOME`,
`RUSTC_WRAPPER`, Cargo configuration/proxy/credential channels, and all unrelated inherited build
variables. `PATH` is exactly
`/private-native/bin:/private-rust/bin:/private-llvm/bin:/tools:/usr/bin:/bin`; the native aliases
precede the manifest tool inventory, and `/usr/bin` and `/bin` contain only the explicit runtime
bindings. The wrapper creates unique mode-`0700`
`CARGO_HOME`, `CARGO_TARGET_DIR`, compiler-cache, and output paths and records their identities.
The fixed manifest also authenticates the ordinary namespace launcher at the exact image-owned path
`/usr/bin/bwrap`,
the Request 6 dispatcher and `/usr/bin/adoption-namespace` runtime bindings, the ordinary run-verifier
key binding, their complete interpreter/loader closures where applicable, and the staged runtime files
containing `/usr/bin/env`, `/bin/sh`, and the required loader/library roots.
The wrapper never invokes an ambient host `bwrap`, `make`, `git`, or shell. A missing user/mount
namespace capability or any incomplete launcher/runtime closure is a `toolchain` failure.
The adoption implementation changes the build recipe to invoke `$(CARGO)` with the Makefile default
`CARGO ?= cargo`; both `align-build` and the private `align-build-only` target use that recipe. The
wrapper always supplies the authenticated absolute Cargo path, so the ordinary build never falls
back to a bare or rustup-selected executable. Before the first child, the namespace supervisor
copies every ordered manifest tool record from retained descriptors into the setup-only
`/private-tool-inventory`, verifies each copy against its record, unmounts the setup view, creates a
read-only `/tools` bind clone, and unmounts the original `/private-tool-inventory` tmpfs before a
child starts. It proves that `/private-tool-inventory` is only the empty underlying directory and
that no writable mount or alias of the inventory remains; `/tools` is the only resolution source for
bare `git`, `tr`, `bash`, `python3`, and other tool names; the complete manifest tool inventory is
therefore in scope even when a particular vector does not use every record. The compiler/archive
handoff remains separate in `/private-tool-bin` and is not mixed with the inventory mount.
The executable-resolution ledger is closed: `/usr/local/libexec/align-llm/fresh-supervise`,
`/usr/local/libexec/align-llm/request6-adoption-entrypoint`, `/usr/bin/python3`,
`/usr/bin/adoption-namespace`, `/usr/bin/bwrap`, `/usr/bin/env`, and `/bin/sh` are the named direct
runtime bindings. `/usr/bin/bwrap` is opened by the worker from the image-attested runtime-binding
table through a retained no-follow descriptor, checked against the fixed owner/mode/link-count/ELF
closure, and retained as the worker-owned FD `27`; it is not inherited from the dispatcher or an
authority bind. The worker invokes that descriptor with `execveat(AT_EMPTY_PATH)` before the namespace
exists; its complete ELF interpreter and library closure is part of the fixed runtime binding, and successful exec closes FD
`27` through its construction `FD_CLOEXEC` flag before the helper starts. Every bare tool name resolves to `/tools/<name>`; the fixed absolute `/private-rust`, `/private-llvm`,
`/private-native`, and `/private-tool-bin` paths are the other executable roots. Repository scripts
are never executable roots: `align-revision` invokes the script data as the exact vector
`/tools/bash /private-project/scripts/check-align-revision`, the focused target invokes the exact vector
`/tools/python3 /private-project/scripts/run-json-scan-row-ownership-adoption-smoke`, and the
authenticated dispatcher invokes the sealed worker bytes as the exact vector
`/usr/bin/python3 -I -B /proc/self/fd/13 --project-root-fd 4 --align-root-fd 18 --capsule-fd 12 --invocation-nonce-fd 15 --supervisor-channel-fd 16`. In each case the
`/private-project/scripts/...` value is an argument to an authenticated interpreter, is copied from
the reviewed source snapshot, and has no `execve` or shebang resolution of its own. A source/argv scan
and child-exec smoke must reject every executable outside these classes before a Make child starts.

Before any child starts, the wrapper creates descriptor-relative, no-follow, mode-`0555` snapshots
of the invocation project and `ALIGN_REPO`, including a private Git view for the Align snapshot so
`check-align-revision` never reopens the caller's worktree. For an ordinary clone, the private view
copies `.git` objects, refs, index, and metadata into the snapshot. For a linked worktree, it
resolves the root `.git` file and its `gitdir`/`commondir` entries through retained descriptors,
copies both the worktree metadata and common object/ref directory into private siblings, rewrites
the private `commondir` to a canonical relative private path, and sets the matching private Git
environment; no original common directory or absolute Git path crosses the child boundary. Before
copying either view, the wrapper rejects local `include.path`, `core.fsmonitor`, fsmonitor hooks,
alternates, replacement refs, grafts, hooks, config includes, and every other helper/configuration
channel outside the fixed Section 9 Git allowlist; it sets the private `GIT_DIR`, `GIT_COMMON_DIR`,
`GIT_WORK_TREE`, `GIT_CONFIG_NOSYSTEM`, `GIT_ATTR_NOSYSTEM`, `GIT_CONFIG_GLOBAL=/dev/null`,
`GIT_NO_REPLACE_OBJECTS=1`, and `GIT_GRAFT_FILE=/dev/null` values for all children. It also
stages the complete authenticated Rust prefix, LLVM/native runtime trees, and Cargo-cache inputs
into the private root, hashes every accepted regular file, and performs complete pre-copy,
post-copy, and final pre-child tree snapshots. The namespace supervisor copies the accepted cache
into its bounded namespace-owned writable `CARGO_HOME`, `CARGO_TARGET_DIR`, compiler-cache, and
temporary tmpfs paths; no child receives a host-writable output bind. A
source, tool, native, or cache replacement, mutation, extra entry, type, mode, size, link-count, or
digest mismatch fails before the next child and leaves the private root for diagnostic cleanup
rather than reopening the original path. The project snapshot records the current project `HEAD`
and requires `git rev-parse --show-object-format` to return `sha1` for both the project and Align
views; a SHA-256 object-format checkout is rejected in the `revision` phase before private staging.
The ordinary schema therefore uses the fixed 40-hex `project_head` width; the authenticated fresh
profile retains Section 9's separate SHA-1/SHA-256 support. The project snapshot requires the
project index and raw tree to match that commit before and after the copy; the
only permitted working-tree exceptions are the reserved root `.git` control entry, the root
`HANDOFF.md` control file (tracked in the pinned source and allowed to be uncommitted in the project
checkout), the untracked root `target/` output subtree, and the untracked project-root `main` output;
none is copied into the product snapshot. The fixed exception metadata vector records type, mode,
link-count, and a content digest for each present handoff; it records `bytes_consumed=true` only for
that bounded handoff read and `false` for control/output rows. Untracked files and every other tracked
modification reject.
The adoption PR binds the recorded project `HEAD` to the exact reviewed implementation head before
ordinary evidence is accepted.

The ordinary capsule's `project_raw_tree_sha256` has an independent canonical preimage. It is the
SHA-256 of a UTF-8 `raw-tree/v1` JSON document using the Section 9 canonical JSON rules (fixed field
order, two-space indentation, complete JSON escaping, and one final LF). The document fields are
`schema`, `source`, and `entries` in that order; `schema` is exactly `raw-tree/v1` and `source` is
exactly `project-source` for the capsule. The first entry is the project root with an empty
`path_b64`, followed by every accepted root-relative entry outside the fixed exception set in raw-byte
lexicographic path order. Each entry has fields in the exact order `path_b64`, `kind`, `mode`,
`size`, `sha256`, `target_b64`: `path_b64` is unpadded base64url of the raw path bytes, `kind` is
exactly `dir`, `file`, or `symlink`, `mode` is the four-octal permission mode, `size` is the raw
file or symlink-target byte length (zero for a directory), `sha256` is the digest of file bytes or
symlink-target bytes (the digest of zero bytes for a directory), and `target_b64` is empty except
for the unpadded base64url symlink target. Paths contain no NUL, empty, `.`, or `..` component;
directory and file metadata not listed here, including timestamps, owners, device/inode numbers,
and link counts, is not part of the preimage. The root `.git` control entry, root `target/` subtree,
root `main`, and the root `HANDOFF.md` exception for either source are excluded before enumeration; every
other accepted entry is represented, and an untracked or modified entry cannot be silently omitted.
For `align-source`, the same wire uses `source = align-source` and excludes the root `.git`, root
`HANDOFF.md`, and root `target/`; root `main` is rejected rather than an exception. The fixed
source-exception metadata vector is checked separately and is not included in `entries` or this
digest. The dispatcher computes the project digest from the retained descriptor snapshot before
signing, and the worker recomputes the identical bytes and exception vector before source acceptance.

The source-exception/v2 metadata is a separate canonical JSON array with one final LF, fixed row order,
and fields `source`, `label`, `present`, `type`, `mode`, `link_count`, `bytes_consumed`,
`content_sha256`. Its rows are
`project-source/{git,handoff,target,main}` followed by
`align-source/{git,handoff,target,main}`. `git` is always present and is either the retained
directory or linked-worktree regular file; both project and Align `handoff` rows are present root
regular files with mode `0644` or `0755`, and each `target` is absent or an ordinary
owner-rwx/no-other-write/no-special directory. Project `main` is absent or an untracked regular file
with mode `0644` or `0755`; Align `main` is always absent. A present `handoff` row is bounded-read
and hashed into `content_sha256`, so only those rows use `bytes_consumed=true`; all other rows use
`false` and `content_sha256=null`. The present `.git` rows use `link_count=null` by explicit policy
because their identity is carried by the retained Git descriptor set, not by the exception vector.
Absent rows use `type=null`, `mode=null`, `link_count=null`, and `content_sha256=null`. The dispatcher
includes the SHA-256 of this complete vector as `source_exception_sha256` in the signed v2 capsule;
the worker recomputes and compares it before staging and again after every source snapshot. The
exception vector is never silently folded into `entries`.

The `raw-tree-v1-output-exception-golden` semantic vector has project `HANDOFF.md`, `target/`, and
`main` present, Align `HANDOFF.md` present and `target/` absent, and the six displayed source entries unchanged. Its
canonical exception bytes are:

```json
[
  {
    "source": "project-source",
    "label": "git",
    "present": true,
    "type": "directory",
    "mode": "0755",
    "link_count": null,
    "bytes_consumed": false,
    "content_sha256": null
  },
  {
    "source": "project-source",
    "label": "handoff",
    "present": true,
    "type": "regular",
    "mode": "0644",
    "link_count": 1,
    "bytes_consumed": true,
    "content_sha256": "c1d73659b427ed35aa922d857055638e99574128d50e91ad2f0b28b8691865c8"
  },
  {
    "source": "project-source",
    "label": "target",
    "present": true,
    "type": "directory",
    "mode": "0755",
    "link_count": 1,
    "bytes_consumed": false,
    "content_sha256": null
  },
  {
    "source": "project-source",
    "label": "main",
    "present": true,
    "type": "regular",
    "mode": "0755",
    "link_count": 1,
    "bytes_consumed": false,
    "content_sha256": null
  },
  {
    "source": "align-source",
    "label": "git",
    "present": true,
    "type": "directory",
    "mode": "0755",
    "link_count": null,
    "bytes_consumed": false,
    "content_sha256": null
  },
  {
    "source": "align-source",
    "label": "handoff",
    "present": true,
    "type": "regular",
    "mode": "0644",
    "link_count": 1,
    "bytes_consumed": true,
    "content_sha256": "c1d73659b427ed35aa922d857055638e99574128d50e91ad2f0b28b8691865c8"
  },
  {
    "source": "align-source",
    "label": "target",
    "present": false,
    "type": null,
    "mode": null,
    "link_count": null,
    "bytes_consumed": false,
    "content_sha256": null
  },
  {
    "source": "align-source",
    "label": "main",
    "present": false,
    "type": null,
    "mode": null,
    "link_count": null,
    "bytes_consumed": false,
    "content_sha256": null
  }
]
```

The output-exception test proves that adding or changing only those admitted exception objects leaves
the raw-tree bytes and digest unchanged while changing any non-exception entry changes the digest;
tracked output names, symlinked exception roots, wrong modes/types/link counts, a changed handoff
content digest, and any exception mutation that is not reflected in the signed capsule reject before
staging. The exception-array serializer and its semantic-to-byte round trip are independently
golden-checked; its fixture is 1755 bytes with SHA-256
`0c685027b378e6ef448e8efd807532eb8f056de04f550e884d56a5ef0834ead0`.

The independent `raw-tree-v1-golden` fixture below is the semantic-to-byte and byte-to-semantic
oracle. Its root, `.align-revision`, ASCII `a`, non-UTF-8 `a\x80`, `docs`, and `docs/link` entries
are already in raw-byte lexicographic order; the root `.git` control entry and root `HANDOFF.md`
are intentionally absent. Its exact canonical bytes have SHA-256
`8b30014d36e10e32e230fcbbcbe12b6933903da48c8569140cadd62795caad77` (1348 bytes):

```json
{
  "schema": "raw-tree/v1",
  "source": "project-source",
  "entries": [
    {
      "path_b64": "",
      "kind": "dir",
      "mode": "0755",
      "size": 0,
      "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "target_b64": ""
    },
    {
      "path_b64": "LmFsaWduLXJldmlzaW9u",
      "kind": "file",
      "mode": "0644",
      "size": 15,
      "sha256": "24e971fd7fe565b764425e0374b3b15f3c46e6a60cde0067e2863c9c739f0a29",
      "target_b64": ""
    },
    {
      "path_b64": "YQ",
      "kind": "file",
      "mode": "0644",
      "size": 1,
      "sha256": "559aead08264d5795d3909718cdd05abd49572e84fe55590eef31a88a08fdffd",
      "target_b64": ""
    },
    {
      "path_b64": "YYA",
      "kind": "file",
      "mode": "0644",
      "size": 1,
      "sha256": "6e340b9cffb37a989ca544e6bb780a2c78901d3fb33738768511a30617afa01d",
      "target_b64": ""
    },
    {
      "path_b64": "ZG9jcw",
      "kind": "dir",
      "mode": "0755",
      "size": 0,
      "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "target_b64": ""
    },
    {
      "path_b64": "ZG9jcy9saW5r",
      "kind": "symlink",
      "mode": "0777",
      "size": 4,
      "sha256": "61b4c98bfb92bdc9391613020e5b8cbf68460066e4af7ef9708da61728f61156",
      "target_b64": "Li4vYQ"
    }
  ]
}
```

The golden test must parse and re-emit those bytes byte-for-byte, verify the recorded digest, and
exercise semantic negatives for root omission, `.git` or `HANDOFF.md` inclusion, raw-byte order,
duplicate/prefix paths, invalid NUL/dot/dotdot components, non-UTF-8 names, symlink targets, and
wrong kind/mode/size/content digests. A zero-filled capsule field is not a substitute for this
independent source-manifest vector.

The three ordinary Make children run inside a fresh authenticated private mount namespace. The
namespace starts with an empty root, the authenticated runtime bindings at their canonical `/bin`,
`/lib`, `/lib64`, and `/usr` targets, and namespace-owned sealed read-only copies of the project,
Align, Rust, LLVM, native, Cargo-cache, launcher-source, and ordered tool-inventory inputs; it has
the namespace-owned sealed read-only `/tools` inventory plus writable tmpfs mounts for
`/private-cargo-home`, `/private-cargo-target`, `/private-compiler-cache`, `/private-tool-bin`, and
`/tmp`, plus a setup-only `/private-tool-inventory` tmpfs that is unmounted before any child, each
with a fixed byte and inode cap. It has a private `/proc`,
minimal `/dev`, no host root, and no original host pathname.
The focused mode additionally gives the trusted namespace setup helper a namespace-owned tmpfs at
`/private-tool-bin`; the trusted helper copies the compiler, archive, launcher, and final descriptor
into that tmpfs, remounts it read-only before the focused child, and launches each Make child through
a capability-dropping child boundary. The supervisor retains `CAP_SYS_ADMIN` and `CAP_SETPCAP` only for its own
descriptor-relative tmpfs setup/remount operations and never interprets repository code. The final
bundle has no host pathname or same-UID alias. The wrapper uses the attested namespace launcher
with the fixed shape; every read-only source is passed through a retained descriptor, never reopened
from a host pathname:

```text
<bwrap-fd-27> --clearenv --die-with-parent --new-session --as-pid-1 --unshare-user --unshare-pid --unshare-net --unshare-ipc --sync-fd 16 --uid 0 --gid 0 --cap-drop ALL --cap-add CAP_SYS_ADMIN --cap-add CAP_SETPCAP --size 68719476736 --tmpfs / --proc /proc --dev /dev --dir /tmp --dir /authority --dir /input-project --dir /input-align --dir /input-rust --dir /input-llvm --dir /input-native --dir /input-cargo-cache --dir /input-launcher-source --dir /input-tools --dir /private-project --dir /private-align --dir /private-rust --dir /private-llvm --dir /private-native --dir /private-cargo-cache --dir /private-launcher-source --dir /private-tool-bin --dir /private-tool-inventory --dir /private-cargo-home --dir /private-cargo-target --dir /private-compiler-cache --dir /tools --size 268435456 --tmpfs /tmp --size 268435456 --tmpfs /private-tool-bin --size 268435456 --tmpfs /private-tool-inventory --size 25769803776 --tmpfs /private-cargo-home --size 68719476736 --tmpfs /private-cargo-target --size 8589934592 --tmpfs /private-compiler-cache --dir /bin --dir /lib --dir /lib64 --dir /usr --dir /usr/bin --dir /usr/lib <ordered-runtime-fd-bind-argv> <ordered-tool-fd-bind-argv> --ro-bind-data 12 /authority/capsule --ro-bind-data 13 /authority/worker --ro-bind-data 15 /authority/nonce --ro-bind-fd 20 /input-project --ro-bind-fd 21 /input-align --ro-bind-fd 22 /input-rust --ro-bind-fd 23 /input-llvm --ro-bind-fd 24 /input-native --ro-bind-fd 25 /input-cargo-cache --ro-bind-fd 26 /input-launcher-source --chdir /private-project -- /usr/bin/adoption-namespace --capsule-path /authority/capsule --worker-path /authority/worker --nonce-path /authority/nonce --supervisor-channel-fd 16 --mode ordinary-adoption
```

The launcher child invokes this vector with `execveat(AT_EMPTY_PATH)` on FD `27`, with `argv[0]`
exactly `bwrap`; the `<bwrap-fd-27>` token denotes the executable descriptor and is not an
unspecified argument. The helper's `argv[0]` remains exactly `/usr/bin/adoption-namespace` as shown
in its separate fixed vector.

The pinned-bwrap acceptance fixture uses a sealed regular-file memfd for each authority source and
executes the exact `--ro-bind-data <fd> <file-target>` form. It proves the mounted target is a
read-only regular file with the expected size and bytes, that bwrap consumes and closes the source
descriptor, and that the namespace helper opens the mounted file with `O_NOFOLLOW`. A
pathname-reopened source, directory-only support, or a source descriptor still visible to the helper
is a platform failure.

The fixed inherited descriptor map is:

| FD | Retained source owner and identity | Namespace target |
| --- | --- | --- |
| 12 | sealed `ordinary-adoption/v2` capsule | consumed by bwrap `--ro-bind-data 12 /authority/capsule`; no FD 12 reaches the helper |
| 13 | sealed repository worker snapshot | consumed by bwrap `--ro-bind-data 13 /authority/worker`; no FD 13 reaches the helper |
| 15 | sealed per-invocation 32-byte nonce challenge | consumed by bwrap `--ro-bind-data 15 /authority/nonce`; no FD 15 reaches the helper |
| 16 | connected supervisor channel with the queued worker-admission proof | retained by bwrap `--sync-fd 16` and inherited by the PID-1 helper; the helper retains it through every row and reverse cleanup, excludes it from each Make child, and closes it before helper exit |
| 18 | retained absolute `ALIGN_REPO` root descriptor, revalidated by dispatcher and worker | used only through dispatcher/worker source checks, then closed before bwrap; no host Align descriptor reaches the helper |
| 20 | private project snapshot | `/input-project` |
| 21 | private Align Git view | `/input-align` |
| 22 | complete Rust prefix | `/input-rust` |
| 23 | LLVM prefix | `/input-llvm` |
| 24 | native tool/runtime tree | `/input-native` |
| 25 | authenticated Cargo cache snapshot | `/input-cargo-cache` |
| 26 | fixed launcher source | `/input-launcher-source` |
| 27 | image-owned `/usr/bin/bwrap` executable, retained by the worker for `execveat(AT_EMPTY_PATH)` | consumed by the worker's bwrap exec edge; `FD_CLOEXEC` closes it across exec and it never reaches bwrap or the helper |
| 400 onward | ordered schema-2 tool records | `/input-tools/<tool-name>` |

The ordered runtime binding sequence is the fixed Section 9 manifest-derived list at canonical
`/bin`, `/lib`, `/lib64`, `/usr`, `/usr/bin`, `/usr/lib`, and `/usr/local` targets, including the exact
`/usr/bin/adoption-namespace` and `/usr/local/share/align-llm/run-verifier.pub` file bindings. Its sources occupy FD 40 onward in manifest order,
and `<ordered-runtime-fd-bind-argv>` contains only
`--ro-bind-fd <fd> <canonical-target>` triples for those retained no-follow descriptors; it is not a
caller argument, pathname bind, or ambient host bind. The tool sources occupy FD 400 onward in
manifest order, and `<ordered-tool-fd-bind-argv>` contains only
`--ro-bind-fd <fd> /input-tools/<name>` triples for those retained no-follow descriptors. The
wrapper admits the descriptor table before launch, checks every source identity and complete digest.
Define `B = {12,13,15,16} ∪ {20..26} ∪ {40..(40+N-1)} ∪ {400..(400+T-1)}`;
the worker clears `FD_CLOEXEC` on every descriptor in `B`, forks the bwrap launcher child directly,
and uses no Python `close_fds/pass_fds` subprocess boundary for this edge. The child inherits exactly
`B ∪ {27}` and no other data descriptor; FD `27` retains `FD_CLOEXEC` for its immediate
`execveat(AT_EMPTY_PATH)` edge, while every descriptor in `B` remains open until bwrap consumes its
bind source or retains FD `16` through `--as-pid-1 --sync-fd 16`. Here `N` is the ordered
runtime-binding count and `T` is the fixed ordered tool-record count from the authenticated manifest.
`--ro-bind-data 12 /authority/capsule --ro-bind-data 13 /authority/worker --ro-bind-data 15 /authority/nonce --supervisor-channel-fd 16 --mode ordinary-adoption`; it contains no caller or Make vector.
The image-owned namespace helper owns the exact three-row vector table below and runs those rows in
order; no alternate vector encoding or fourth vector exists. The namespace helper remounts each
writable tmpfs with its fixed `nr_inodes` cap before the first child and continuously counts bytes and
entries between children. bwrap consumes the retained source descriptors before executing
`/usr/bin/adoption-namespace`; each source becomes a fixed read-only `/authority/{capsule,worker,nonce}`
bind, and the PID-1 helper inherits only the live channel FD `16` in addition to its fixed path
arguments. No authority FD is inherited by the helper. The helper accepts only those fixed bind paths,
hashes their bytes against the capsule, and creates local sealed memfds for its checks, so a same-UID
rename or replacement of any staging pathname cannot change a mounted source. The runtime bindings are image-owned root-owned immutable inputs and remain direct
FD binds. Before the first Make child, the supervisor re-snapshots each `/input-*` tree against the
wrapper-authenticated source digest, copies it descriptor-relatively into the matching
namespace-owned `/private-*` directory, verifies source and destination pre/post trees, copies the
ordered `/input-tools/<name>` files into the setup-only `/private-tool-inventory`, verifies each
destination against the manifest, unmounts every `/input-*` bind, creates the read-only `/tools` bind
clone, remounts that clone read-only, and then unmounts the original `/private-tool-inventory` tmpfs.
It proves that `/private-tool-inventory` is only the empty underlying directory and that no writable
mount or alias of the inventory remains before a child starts; `/tools` is the sole visible inventory
path. It then bind-mounts/remounts every other copied `/private-*` tree read-only, remounts the root
`/` read-only, and proves that every writable child path is an independent explicitly mounted tmpfs.
It verifies that no input mount, host pathname, or writable root directory remains in the namespace.
A same-UID host mutation after this seal cannot
affect a child. The
supervisor starts with UID/GID 0 and only `CAP_SYS_ADMIN` retained by
the explicit bwrap vector; each Make child drops all capabilities and sets `no_new_privs` before its
`execve`, and the supervisor is the only process allowed to copy the post-build compiler or remount
`/private-tool-bin`. A failed namespace setup before the first child is
`toolchain`, while a failed post-build compiler copy, namespace bundle, descriptor, remount, or
handoff setup is `build`, before the focused child or compiler marker.

The namespace helper is one trusted supervisor for this invocation. It first consumes exactly one
queued worker-admission proof from the live supervisor channel on FD `16`, and verifies that the proof
equals the capsule envelope digest/ticket/nonce tuple. The dispatcher and worker have already completed
all outer peer PID, start-time, executable, and command-line authentication before bwrap; the helper
does not resolve an outer PID or procfs path from its private PID namespace. It checks only channel
`POLLHUP`, EOF, and protocol liveness before setup, before every row, and while a row is active. It
then opens the three fixed read-only bind paths `/authority/capsule`, `/authority/worker`, and
`/authority/nonce` with no-follow flags, reads bounded bytes with `pread`, and proves that the worker
digest and nonce equal the signed capsule. It creates local fixed-name sealed memfds from those bytes
and checks their complete observable predicates, then closes the bind-path descriptors before any
repository-controlled Make child starts; it does not execute or copy the worker a second time. Its
image-owned fixed vector table is exactly the three rows below; it starts
each row as a separate session with its in-namespace bounded runner, and
performs the compiler bundle handoff only after `align-build-only` succeeds and before the focused
vector.
In focused mode the handoff arguments are, in this fixed order, the namespace-owned source paths
`/private-cargo-target/release/alignc`, `/private-cargo-target/release/libalign_runtime.a`, and
`/private-launcher-source/adoption-alignc`, the expected launcher SHA-256 value, the Align revision,
the project HEAD, and then `--` followed by the focused Make vector. No compiler or archive digest is
an input before the build: the supervisor opens and verifies the two newly built files after
`align-build-only`, computes their complete SHA-256 digests, and copies their bytes into
the namespace-owned `/private-tool-bin` tmpfs with create-exclusive files, copies and verifies the
launcher before writing the schema-1 descriptor, stats/hashes every final destination, verifies the
descriptor bytes, remounts the tmpfs read-only, and drops all capabilities in the focused child
before `execve`-ing its Make vector. The first two vectors pass `--no-compiler-handoff` in the same
fixed helper position. No repository Makefile or fixture code runs before this setup sequence
completes, and no fourth vector is accepted.

The helper's complete child-plan contract is fixed below. The first line is the one image-owned helper
argv consumed by bwrap; the three following rows are helper-owned plan arrays, not caller arguments or
additional public entrypoints. In each row the literal `--` separates helper controls from the exact
argv passed to the child `execve`; `--no-compiler-handoff` is a control token in the first two rows at
the same position, and the third row replaces it with the fixed handoff tuple. The helper does not
re-exec itself for a row. It validates the three fixed authority paths, performs setup, then passes
the post-`--` array to one child with the row's environment:

```text
helper_argv = [
  "/usr/bin/adoption-namespace", "--capsule-path", "/authority/capsule",
  "--worker-path", "/authority/worker", "--nonce-path", "/authority/nonce",
  "--supervisor-channel-fd", "16", "--mode", "ordinary-adoption"
]

row_1.argv = [
  "/usr/bin/adoption-namespace", "--child-index", "1", "--no-compiler-handoff", "--",
  "/tools/make", "--no-print-directory", "-C", "/private-project", "-f",
  "/private-project/Makefile", "align-revision"
]
row_2.argv = [
  "/usr/bin/adoption-namespace", "--child-index", "2", "--no-compiler-handoff", "--",
  "/tools/make", "--no-print-directory", "-C", "/private-project", "-f",
  "/private-project/Makefile", "align-build-only"
]
row_3.argv = [
  "/usr/bin/adoption-namespace", "--child-index", "3", "--compiler-handoff",
  "/private-cargo-target/release/alignc", "/private-cargo-target/release/libalign_runtime.a",
  "/private-launcher-source/adoption-alignc", "<launcher-sha256>", "<align-revision>",
  "<project-head>", "--", "/tools/make", "--no-print-directory", "-C", "/private-project",
  "-f", "/private-project/Makefile", "json-scan-row-ownership-adoption"
]
```

The row environment is also fixed. Every row receives exactly the common set
`ALIGN_REPO=/private-align`, `CARGO_NET_OFFLINE=true`, `HOME=/nonexistent`, `LANG=C`, `LC_ALL=C`,
`MAKEFLAGS=`, `GNUMAKEFLAGS=`, `MAKEOVERRIDES=`, `PATH=/private-native/bin:/private-rust/bin:/private-llvm/bin:/tools:/usr/bin:/bin`,
`PYTHONDONTWRITEBYTECODE=1`, and `TMPDIR=/tmp`. Row 2 adds
`CARGO=/private-rust/bin/cargo`, `RUSTC=/private-rust/bin/rustc`, `CARGO_HOME=/private-cargo-home`,
`CARGO_TARGET_DIR=/private-cargo-target`, `LLVM_CONFIG=/private-llvm/bin/llvm-config`,
`LLVM_SYS_221_PREFIX=/private-llvm`, `CC=/private-native/bin/cc`, `CXX=/private-native/bin/cxx`,
`AR=/private-native/bin/ar`, `RANLIB=/private-native/bin/ranlib`, `LD=/private-llvm/bin/ld.lld`,
`LIBRARY_PATH=<authenticated-native-library-path>`, `LD_LIBRARY_PATH=<authenticated-loader-path>`,
and `PKG_CONFIG_PATH=<authenticated-pkg-config-path>`. Row 3 adds the same build variables plus
`ALIGNC=/private-tool-bin/adoption-alignc`, `ALIGNC_DESCRIPTOR=/private-tool-bin/adoption-handoff`,
and `ALIGNC_CACHE=/private-compiler-cache`. On native `aarch64`, rows 2 and 3 additionally receive
`CARGO_BUILD_JOBS=1`; on native `x86_64`, that variable is absent and Cargo uses its native default
parallelism. No other variable or descriptor is inherited, and the
golden child-plan test compares all three arrays and environment sets byte-for-byte before any child.

The authority lifetime is equally fixed: bwrap closes source FD `12`, FD `13`, FD `15`, every setup
descriptor `20..26`, every runtime descriptor `40..(40+N-1)`, and every tool descriptor
`400..(400+T-1)` after creating their fixed read-only binds. The worker parent retains its own copies
until the bwrap launcher child exits and reverse cleanup has recorded their final state; the namespace
helper never owns or closes those source descriptors. `--as-pid-1 --sync-fd 16` leaves only the live
supervisor channel in the helper in addition to its fixed bind-path descriptors. After helper
verification and namespace setup, and before row 1, the helper closes the bind-path descriptors and
every private directory or compiler-bundle descriptor not needed by the selected row. Before each
Make `execve`, it performs `close_fds=True, pass_fds=()`; the child descriptor allowlist is exactly
`{0,1,2}`. The helper retains FD `16` until the final row and reverse cleanup complete, records
`/proc/self/fd` from each Make child, and rejects any authority, identity, setup, bind-path, or worker
descriptor before accepting the row result.

The trusted installed runner starts the public profile with one direct kernel `execve`; no shell,
`/usr/bin/env`, or repository executable runs before the image-owned supervisor. This is the exact
ordinary request (the `execve` block is the contract, not shell syntax):

```text
execve(
  "/usr/local/libexec/align-llm/fresh-supervise",
  ["fresh-supervise", "--mode", "ordinary-adoption"],
  ["PATH=/usr/bin:/bin", "LC_ALL=C", "LANG=C", "HOME=/nonexistent", "TMPDIR=/tmp",
   "ALIGN_REPO=<absolute-clean-align-worktree>"]
)
```

The runner sets the project checkout as the cwd and supplies no other environment entry. The
image-owned `fresh-supervise` is the first profile executable and the only public path that can claim
ordinary adoption evidence; it validates the absolute `ALIGN_REPO`, derives the canonical relative
spelling, and passes both values in the fixed named-option dispatcher vector before dispatching the
Request 6 child by retained FD `14`. Invoking either
`/usr/local/libexec/align-llm/request6-adoption-entrypoint` or
`./scripts/run-json-scan-row-ownership-adoption` directly is an untrusted developer check and cannot
emit ordinary adoption evidence.

For `ordinary-adoption`, `ALIGN_REPO` is required and is an absolute path with exactly one leading
slash, no empty, `.`, or `..` component, and no symlink component. `fresh-supervise` obtains the
absolute physical spelling of the retained project-root descriptor without consulting `PWD`, applies
the same lexical normalization to the Align input, and computes the POSIX relative path from project
root to Align. It rejects an empty or `.` result, an absolute result, or any result with an empty
component; `..` components are permitted only when produced by this conversion (the golden sibling
value is `../align`). It passes both normalized values in the fixed named-option vector. The
supervisor performs the complete `/`-rooted component walk described above before channel creation
and FD 14 dispatch. The dispatcher does not reopen or walk the absolute pathname: it revalidates the
retained FD `18`, recomputes the relative value from the retained project-root identity, and rejects
any descriptor, identity, or canonical-value mismatch before signing or staging. All later Git and
copy operations reuse the retained Align descriptor rather than reopening the absolute spelling, and
the capsule records only the canonical relative value.

The ordinary output boundary has two stages. A failure in `fresh-supervise` before it consumes the
retained dispatcher descriptor (image, manifest, argument, nonce, or dispatcher-closure admission)
returns exit `1`, empty stdout, and exactly `fresh compiler: ERROR TRUST supervisor\n` on stderr. After
FD `14` dispatch, the dispatcher is the sole semantic result producer and the native parent is the
public-stream transport owner. The parent drains both dispatcher pipes concurrently, retains at most
65,536 bytes per stream, waits for and reaps the direct dispatcher child, validates its complete
result/status pair, and forwards the captured bytes exactly once. Success is exit `0`, empty stderr,
and exactly `json-scan adoption: PASS\n`; failure is exit `1`, empty stdout, and exactly one
`json-scan adoption: ERROR <phase>\n` on stderr. A worker signal or unknown exit before a final
phase result is translated by the dispatcher to `json-scan adoption: ERROR unobserved\n` and is
forwarded unchanged. A dispatcher signal/unknown status, partial or extra output, pipe overflow,
native channel violation, or native cleanup failure is `fresh compiler: ERROR TRUST supervisor\n`
with child bytes suppressed. The native parent never synthesizes or duplicates an ordinary result.

Concurrency is explicit. The ordinary wrapper and every Section 9 fresh public mode use the same
installed per-user mode-`0600` lock at `/run/user/<uid>/align-llm-fresh/lock`; the wrapper opens and
identity-checks it with `LOCK_NB` before private-root creation, cgroup admission, or namespace
setup. The lock path and policy are fixed profile inputs, never caller overrides. The supported
entrypoint combinations are:

| Combination | Policy | Failed-second result |
| --- | --- | --- |
| ordinary + ordinary | reject before side effects | `json-scan adoption: ERROR toolchain\n` |
| ordinary + fresh `ci`, `build`, `adoption`, or `self-test` | reject before side effects under the common lock | the existing fresh `PLATFORM concurrency` result for a fresh second, or the ordinary `toolchain` result for an ordinary second |
| fresh + ordinary | the same common-lock rejection in the opposite arrival order | the result for the second entrypoint above |
| recursive ordinary entrypoint in one process tree | reject before a second root or child | `json-scan adoption: ERROR toolchain\n` |

Independent processes do not wait or share roots. On cancellation or normal exit the outer wrapper
releases the lock only after the namespace supervisor has exited, the cgroup leaf is empty and
removed, and the host staging root has passed its final identity proof and cleanup. A wrapper
`SIGKILL` leaves no writable namespace mount; `--die-with-parent` empties the cgroup leaf, the kernel
releases the lock, and the next invocation scans both the bounded host-root quarantine and the
unique cgroup-leaf quarantine. It removes an orphaned leaf only after parent/leaf identity and empty
membership proofs; if either quarantine cannot be proved safe, it rejects before root creation and
leaves the candidate untouched. The
concurrency smoke runs every listed pair, failed-second marker, orphaned-leaf, orphaned-root, and
replacement-before-admission case.

After its preflight, the wrapper starts the one namespace supervisor, which launches these fixed
child vectors inside that namespace with the authenticated toolchain environment and empty
Make-control variables. `/tools/make` in each vector is the retained schema-2 `make` tool record
materialized in the read-only `/tools` inventory; it is never a host pathname reopened after
admission:

```text
/tools/make --no-print-directory -C /private-project -f /private-project/Makefile align-revision
/tools/make --no-print-directory -C /private-project -f /private-project/Makefile align-build-only
/tools/make --no-print-directory -C /private-project -f /private-project/Makefile json-scan-row-ownership-adoption
```

The Makefile implementation uses project scripts only as interpreter data arguments. The
`align-revision` recipe must execute `/tools/bash /private-project/scripts/check-align-revision`, and
the focused target recipe must execute
`/tools/python3 /private-project/scripts/run-json-scan-row-ownership-adoption-smoke`. The public worker
is the sealed FD-13 data argument to the dispatcher vector
`/usr/bin/python3 -I -B /proc/self/fd/13 --project-root-fd 4 --align-root-fd 18 --capsule-fd 12 --invocation-nonce-fd 15 --supervisor-channel-fd 16`; it is not a Make
script path. The source paths are read-only
arguments inside the reviewed `/private-project` snapshot; a shebang, executable mode, PATH lookup, or
direct `execve` of a project-script path is forbidden. The child-argv and exec-source smoke must record
the interpreter and data argument separately and reject any project-script path in an executable slot.

Each child receives `ALIGN_REPO=/private-align` and the same authenticated read-only toolchain,
cache, and empty Make-control environment. The `align-build-only` child additionally receives
`CARGO=/private-rust/bin/cargo`, `RUSTC=/private-rust/bin/rustc`,
`CARGO_HOME=/private-cargo-home`, `CARGO_TARGET_DIR=/private-cargo-target`,
`CARGO_NET_OFFLINE=true`, `LLVM_CONFIG=/private-llvm/bin/llvm-config`,
`LLVM_SYS_221_PREFIX=/private-llvm`, `CC=/private-native/bin/cc`,
`CXX=/private-native/bin/cxx`, and the authenticated native search paths. On native `aarch64` only,
the child additionally receives `CARGO_BUILD_JOBS=1`; native `x86_64` omits the variable and uses
Cargo's native default parallelism. The wrapper materializes `/private-native/bin/cc` and
`/private-native/bin/cxx` as create-exclusive copies of the authenticated
`clang` and `clang++` runtime bytes, with their complete ELF closure; the manifest's `cc` and `cxx`
forwarders are identity records, not executed aliases. These are explicit staged aliases, not an
unlisted `c++` name. Every focused child
receives `PATH=/private-native/bin:/private-rust/bin:/private-llvm/bin:/tools:/usr/bin:/bin`, with
the staged `cc` first and the authenticated tool inventory before the fixed runtime directories; this
is required because the shipped `alignc run` path invokes `cc` by name and must never reach ambient
`/usr/bin/cc`. After `align-build-only`, the namespace supervisor itself opens
the newly built `/private-cargo-target/release/alignc` and adjacent runtime archive with retained
no-follow descriptors, verifies type, mode, link count, revision, version, and complete bytes, and
copies them create-exclusively into the namespace-owned `/private-tool-bin` tmpfs. It copies the
authenticated fixed `scripts/adoption-alignc` source from `/private-launcher-source`, verifies its
expected SHA-256, stats and hashes every final destination, and only then writes the canonical
schema-1, mode-`0444` compiler handoff descriptor containing the exact compiler/archive paths,
device/inode, mode, link-count, size, SHA-256, Align revision, and project HEAD. The outer wrapper
never opens or transfers a compiler from the namespace target and never writes the handoff
descriptor. The descriptor paths are fixed namespace paths `/private-tool-bin/alignc` and
`/private-tool-bin/libalign_runtime.a`, never host staging paths or caller input. The fixed
`scripts/adoption-alignc` launcher is copied into the same final bundle before the descriptor is
published, and the helper exposes that bundle only through the read-only `/private-tool-bin` mount.
The launcher opens exactly
`/private-tool-bin/adoption-handoff`, `/private-tool-bin/alignc`, and
`/private-tool-bin/libalign_runtime.a` with `O_RDONLY|O_NOFOLLOW`, rechecks the mount identity and
all declared tuples plus the launcher SHA-256 against its own fixed
`/private-tool-bin/adoption-alignc` bytes, and executes the already-open compiler with
`execveat(AT_EMPTY_PATH)`. The
read-only namespace tmpfs is the immutability boundary; a focused child cannot chmod, replace, or
restore any handoff or sibling bundle member through its visible path, and no host alias exists.
The focused child receives
`ALIGNC=/private-tool-bin/adoption-alignc`, `ALIGNC_DESCRIPTOR=/private-tool-bin/adoption-handoff`,
and `ALIGNC_CACHE=/private-compiler-cache`, and rejects a missing, relative, symlinked, stale,
replaced, or digest-mismatched handoff before any fixture compiler call. It never searches sibling
release/debug paths or `PATH` for the compiler.
The handoff descriptor is canonical UTF-8 JSON with one final LF, no duplicate or unknown fields,
decimal unsigned integers, and this exact field order and width: `schema_version` (`u64`),
`compiler_path` (the fixed string `/private-tool-bin/alignc`), `compiler_dev` (`u64`),
`compiler_ino` (`u64`),
`compiler_mode` (`u32`), `compiler_nlink` (`u64`), `compiler_size` (`u64`),
`compiler_sha256` (64 lowercase hexadecimal bytes), `archive_path` (the fixed string
`/private-tool-bin/libalign_runtime.a`),
`archive_dev` (`u64`), `archive_ino` (`u64`), `archive_mode` (`u32`), `archive_nlink` (`u64`),
`archive_size` (`u64`), `archive_sha256` (64 lowercase hexadecimal bytes),
`launcher_sha256` (64 lowercase hexadecimal bytes for the fixed
`/private-tool-bin/adoption-alignc` path),
`align_revision` (40 lowercase hexadecimal bytes), and `project_head` (40 lowercase hexadecimal
bytes). The schema version is `1`; paths must remain below the private root and are checked against
the recorded device/inode/type/mode/link-count/size/digest tuple before every `execve`. The
implementation records a checked-in golden descriptor byte vector and rejects a reordered,
whitespace-normalized, truncated, or trailing-byte variant before the first compiler call.
The semantic-to-byte and byte-to-semantic acceptance vector is named
`adoption-compiler-handoff-v1-golden`; its exact UTF-8 bytes, including the final LF, are:

```text
{"schema_version":1,"compiler_path":"/private-tool-bin/alignc","compiler_dev":7,"compiler_ino":11,"compiler_mode":365,"compiler_nlink":1,"compiler_size":123,"compiler_sha256":"0000000000000000000000000000000000000000000000000000000000000000","archive_path":"/private-tool-bin/libalign_runtime.a","archive_dev":7,"archive_ino":13,"archive_mode":292,"archive_nlink":1,"archive_size":456,"archive_sha256":"1111111111111111111111111111111111111111111111111111111111111111","launcher_sha256":"2222222222222222222222222222222222222222222222222222222222222222","align_revision":"3333333333333333333333333333333333333333","project_head":"4444444444444444444444444444444444444444"}
```
The golden test parses those bytes into the declared typed object and serializes that object back to
the identical byte sequence; each individual field mutation has a separately checked rejection.
The ordinary profile records the staged project/Align identities, exact revision, authenticated
toolchain and cache file identities and versions, build-target identity, compiler/archive digest,
compiler selector, cache identity, and all three internal vectors. The authenticated fresh profile
performs the equivalent source and compiler-build checks inside the worker-owned private root and
supplies only its fixed `/tools/fresh-alignc` and `ALIGNC_CACHE=off` vector; it does not run the
ordinary host wrapper or trust its artifacts.

The worker remains the outer wrapper process that owns the single bwrap/namespace-supervisor child,
the cgroup admission, and the host staging root. It opens and authenticates image-owned bwrap as FD
`27`, creates the unique cgroup leaf and start-gate pipe, and forks exactly one bwrap launcher child.
Before opening any tool or source-identity descriptor, it reserves the complete fixed bind-FD set
`{20..27} ∪ {40+i for each runtime binding} ∪ {400+i for each tool}` with non-inheritable
placeholders. Each bind atomically replaces only its placeholder, so constructing the bwrap vector
cannot overwrite a retained tool or Git-view descriptor; unused placeholders remain worker-owned
and are closed during reverse cleanup.
The launcher child closes its parent-side gate FD `11`, blocks on the read end at fixed launcher-child
FD `10`, and performs no bwrap operation while blocked. The worker parent records the child's PID and
start time, attaches that PID to the empty leaf with `pids.max=512`, proves membership, and releases
the child by writing exactly one gate byte through parent FD `11`. The child then closes FD `10` and
every unrelated descriptor, retains exactly the bwrap descriptor set `B ∪ {27}`, and invokes the bwrap image directly with
`execveat(AT_EMPTY_PATH)`; the successful exec closes FD `27` through its construction
`FD_CLOEXEC` flag. The worker parent retains the cgroup and staging ownership, waits for that child,
and owns reverse cleanup. FDs `10` and `11` are closed before bwrap exec and are never included in
any bind tuple. bwrap and every
inner descendant inherit that leaf from their first executable instruction; `/sys/fs/cgroup` is not
mounted into the empty namespace. The outer wrapper does not enumerate or reap Make descendants
across the private PID namespace. The namespace supervisor's owned-child runner sets Linux
child-subreaper mode before its first child, starts each Make child in a new session, enumerates and
adopts descendants through `/proc` using recorded PID start times and process-group identities, and
drains stdout and stderr concurrently with a 65,536-byte cap per stream. The fixed deadlines are 10 seconds for
`align-revision`, 1,800 seconds for `align-build-only`, and 120 seconds for the focused target.
Timeout, cancellation, reader failure, launch failure, nonzero exit, and cleanup use one order:
stop new children, send TERM to the owned process group, wait one second, send KILL to remaining
owned descendants, reap them, close pipes/descriptors, re-snapshot the private tree, and remove only
namespace-owned temporary paths. The outer wrapper then waits for the supervisor, proves the cgroup
leaf empty and unchanged, removes that leaf descriptor-relatively, rescans the host staging root,
and performs its descriptor-relative cleanup/quarantine; it never asks the namespace supervisor to
remove a host pathname. A failure leaves no child and emits the one phase error; a failed cleanup
emits `json-scan adoption: ERROR cleanup\n` and leaves the unprovable path untouched.

The complete ordinary timeout hierarchy is fixed and strictly nested. The worker gives the one
bwrap/namespace child 5,000 seconds, then owns a separately bounded 5-second final cgroup drain. The
dispatcher deadline is 5,020 seconds, the native supervisor deadline is 5,040 seconds, and the
installed-profile owner deadline is 5,100 seconds. The increasing bounds reserve time for the inner
owner to kill, reap, close, and report before an outer owner intervenes. No caller may override a
deadline. A primary phase remains authoritative if its
reverse cleanup also fails; a cleanup failure after otherwise successful work becomes the sole
`cleanup` result, and no PASS bytes are written until all worker-owned cleanup has succeeded.

The ordinary namespace has enforceable resource bounds, not only post-run accounting. The fixed
installed profile provisions the delegated cgroup-v2 parent
`/sys/fs/cgroup/align-llm-fresh/<uid>` already used by Section 9; the outer wrapper creates one
unique leaf, requires empty `cgroup.procs` and `cgroup.threads`, sets `pids.max=512`, attaches the
bwrap launcher through the start gate, and retains the parent/leaf descriptors until every child and
cleanup step has completed. The namespace supervisor never opens the host cgroup path; the outer
wrapper proves membership before releasing bwrap and proves empty membership before descriptor-relative
leaf removal. Memory cgroup enforcement is `N/A`: the installed profile delegates only the pids
controller, so the ordinary contract does not claim a `memory.max` boundary. Before the bwrap boundary
it applies hard and soft
`RLIMIT_NPROC=512`, `RLIMIT_NOFILE=4096`, and `RLIMIT_FSIZE=536870912`; the child-side probe verifies
the exact inherited rlimits before admitting the first vector. The namespace-owned writable
tmpfs bounds are fixed: root `68719476736` bytes, Cargo home `25769803776`, Cargo target
`68719476736`, compiler cache `8589934592`, tool inventory `268435456`, tool bundle `268435456`,
and `/tmp` `268435456`, with
`nr_inodes=2000000` on the root and private build trees, `nr_inodes=400000` on the Cargo home and
compiler cache, and `nr_inodes=65536` on temporary/tool trees. Each of the seven retained setup
trees has an individual 200,000-entry boundary, and the wrapper rejects a sealed-input byte or entry
total above its fixed 48 GiB or 1,500,000-entry aggregate before the next copy. Cargo-cache admission
also computes the fixed upper bound
`sum(round_up(file_size, 4096)) + 4096 * (directory_count + 1) + 2147483648`; it rejects before copy
when that value exceeds `25769803776`, even when the logical schema-2 total is below 20 GiB. The
2 GiB term is reserved for Cargo-created metadata and locks; the page-rounded file and directory
terms make the copy bound independent of source filesystem allocation. At the schema-2 limits of
20 GiB and 200,000 entries, this upper bound fits the 24 GiB Cargo-home tmpfs. The supervisor counts
every admitted entry and byte between vectors and during active children, rejecting cap-plus-one before
the next side effect. Thus all seven individual boundaries fit the root inode limit together. The
helper never binds a host-writable target or cache. A process, descriptor,
file-size, inode, or byte-cap failure is `build` for the build vector or `fixture` for the focused
vector; cgroup admission is `toolchain`, and a failed post-run cgroup or host-root proof is
`cleanup`. The outer wrapper removes the cgroup leaf only after descriptor-relative empty and identity
proofs.

The focused target accepts no positional arguments and its preflight rejects missing, extra, or
unexpected fixture entries before starting the compiler. It opens the project root from the
invocation `cwd`, requires the fixture directory and every expected fixture to be an owned regular
file with no symlink or special-file component, rejects an unexpected entry, and creates all
ordinary-profile cache and output paths below the namespace supervisor's newly created mode-`0700`
temporary root. The temporary root has a checked device/inode/mount identity and is removed only
after the target proves that no compiler child remains; a failed identity or cleanup proof leaves
the host candidate untouched and fails closed.

Every compiler invocation captures bounded stdout and stderr, forwards neither stream on a
negative result except for the one expected diagnostic comparison, rejects a panic/backtrace or
unexpected cache/output byte, and checks the exit status before the next fixed filename. The
ordinary and fresh profiles must produce the same fixture verdicts and exact output bytes; the
profile difference is only the authenticated compiler/materialization boundary.

Because this adoption changes `Makefile`, fixtures, and `.align-revision`, its implementation branch
also performs the Section 2.4 identity-bound baseline sequence after the final source is complete:
one clean source commit, two deterministic reference samples, one oracle-only commit, and one
finalization-only commit. It verifies the exact source/oracle/finalization identities and requires
all three to be ancestors of the tested head and its merge result; squash or rebase integration is
not evidence for this baseline contract. No tracked input, pin, fixture, or recorded command may
change after finalization without repeating the sequence. The adoption PR records the ordinary
focused result, the authenticated fresh focused result, the final fresh `make ci` result, and the
post-merge ancestry check before advancing the request lifecycle.

The fixture directory contains:

- `copy-row.align`, which scans exactly
  `[{"score":1,"name":"a"},{"score":2,"name":"b"}]`, runs `.score.sum()?`, and must exit zero with
  stdout exactly `3\n` and empty stderr; and
- `owned-direct.align`, `owned-nested.align`, `owned-option.align`, and `owned-union.align`, whose
  top-level scanner type is named `OwnedRow` and which respectively expose
  `items: array<i64>`, a nested `items: array<str>`, an optional nested struct that owns
  `items: array<i64>`, and an owning `Parts(array<Item>)` union variant to `json.scan`.
  `owned-option.align` expects the scanner-specific diagnostic and proves the scanner ownership
  predicate is reached after ordinary schema admission; and
- `decode-owned.align`, which decodes the `owned-direct.align` schema through `json.decode`, sums
  the exact input `{"items":[1,2]}`, evaluates
  `print(decoded.items[0] + decoded.items[1])`, and must exit zero with stdout exactly `3\n` and
  empty stderr; and
- `decode-owned-option.align`, which uses
  `Inner { items: array<i64> }` and
  `Row { inner: Option<Inner>, score: i64 }`, decodes
  `{"inner":{"items":[1,2]},"score":3}`. It immediately prints `json.encode(decoded)`, then lets
  the owner leave scope; at the shipped Align commit it must exit zero with stdout exactly
  `{"inner":{"items":[1,2]},"score":3}\n` and empty stderr.

The adoption script has two explicit execution profiles. In the ordinary adoption profile,
`owned-direct.align`, `owned-nested.align`, and `owned-union.align` use
`ALIGNC=/private-tool-bin/adoption-alignc ALIGNC_DESCRIPTOR=/private-tool-bin/adoption-handoff ALIGNC_CACHE=/private-compiler-cache /private-tool-bin/adoption-alignc check <file>` in that fixed filename order inside the ordinary namespace. In the
Section 9 fresh-capable profile, the same calls use the controller-owned fixed vector
`ALIGNC_CACHE=off /tools/fresh-alignc check <file>`; `/tools/fresh-alignc` opens the authenticated
handoff files and cannot be replaced by a caller-selected compiler. Both profiles require a
nonzero status, require empty stdout, and match exactly once:

```text
`json.scan` row type 'OwnedRow' must be Copy; Move rows need per-row Drop before the scanner can reuse its row slot
```

It rejects a panic, backtrace, or any unexpected file under the selected cache. It checks
`owned-option.align` against the fixed scanner diagnostic above, then invokes the same absolute
private launcher with `run copy-row.align` and `run decode-owned.align` in that order with the same
descriptor and named cache in the ordinary profile. In the Section 9 fresh-capable profile, those exact vectors are
`ALIGNC_CACHE=off /tools/fresh-alignc run copy-row.align` and
`ALIGNC_CACHE=off /tools/fresh-alignc run decode-owned.align`; the worker's `ALIGNC_CACHE=off`
setting is fixed and caller cache overrides are rejected. It then invokes
`decode-owned-option.align` with
`ALIGNC=/private-tool-bin/adoption-alignc ALIGNC_DESCRIPTOR=/private-tool-bin/adoption-handoff ALIGNC_CACHE=/private-compiler-cache /private-tool-bin/adoption-alignc run decode-owned-option.align`
in the ordinary profile, or with
`ALIGNC_CACHE=off /tools/fresh-alignc run decode-owned-option.align` in the Section 9 fresh-capable
profile. The selected profile vector is fixed in both profiles; only a future Align cleanup that
changes the shipped contract may update the fixture oracle in a separate pin wave. Thus the
persistent `make ci` target never infers current behavior from an observed compiler.
The script removes the validated temporary directory on every exit. This focused target must pass
before the consumer capability's one final `make ci`; together they may advance Request 6 to
`ALIGN_LLM_VERIFIED`.

### align-llm verification (2026-08-14 — CLOSED)

align-llm PR #84 merged the ordinary and authenticated-fresh Request 6 consumer adoption at
`c0fc3046bff05d33ad0753f9c273da8bb48d2fa1`, with `.align-revision` selecting
`25b1201b3a4181f6a90921227596bdcb76ab715e`. The exact PR head
`031917b5518170f905793af65b9cb347b837d178` passed the positive recursively Copy fixtures and the
exact fail-closed Move-row matrix in both profiles, followed by the installed worker aggregate's
fixed `make --no-print-directory ci` vector. The same head passed required native Linux
`aarch64` and `x86_64` CI; the ARM compiler build used the qualified single-job Cargo policy while
x86_64 retained Cargo's default parallelism. The merged implementation owns native platform
admission, authenticated compiler handoff, source and tool isolation, bounded process teardown,
phase-preserving failure classification, and cleanup. It does not admit Move scanner rows or
provide per-row Drop; those remain outside this request's shipped surface.

### References

- `../align/docs/impl/core-design/json.md` — authoritative shipped scanner ownership model.
- `../align/draft.md`, `../align/docs/language-spec.md`, `../align/docs/design-notes.md`, and
  `../align/docs/open-questions.md` — public and shipped-surface records that must agree with the
  authoritative design.
- `../align/crates/align_sema/src/lib.rs` — `check_json_scan`, general decode eligibility, and
  pipeline Move-argument restrictions.
- `../align/crates/align_mir/src/lib.rs` — reusable row slot and fused-terminal loop.
- `../align/crates/align_runtime/src/lib.rs` — row zeroing, typed owned-array construction, and the
  separately scoped decoded-owner transition gaps in optional cleanup, indexed
  speculation/fallback, top-level struct-array staging, and trailing-garbage rejection.
- `../align/crates/align_driver/tests/m5.rs` — current scanner terminal and framing coverage.
- `docs/specs/roadmap.md` and `docs/specs/align-llm.md` — align-llm consumer sequencing.

## Request 7 — `core.json`: escaped strings in declared-record decoding

```text
Status: CLOSED
Priority: high
Blocking: yes
Blocked gate or slice: align-llm adoption; roadmap C6 Prompt Optimizer canonical declared-artifact encoding remains blocked until every separately registered JSON prerequisite is also adopted
Independent work that may continue: C6 design and implementation that does not consume the unpinned surface, other independently demonstrated Align prerequisite requests, and C7 design that does not pre-commit C6 artifacts
Resume condition: satisfied by the C6-LIFECYCLE pin wave and Align-llm PR #94; the named escape adoption and final capable gate passed, while C7's separately named aarch64 Linux and aarch64 macOS environments remain independent
Align commit or pull request: benchmark-evidence design PR #813 merged as `734ae3ab20164c02cee56101bb3eeb2b452269ed`; benchmark-input prerequisite PR #815 merged as `58dbb21818edb6d1bb0e2c039e6bee066f877456`; evidence manifest foundation PR #816 merged as `7db1af8cb4ae69fb88506e74b4893f92ed609fd8`; canonical JSON primitive codec PR #817 merged as `4ec35dfe9fca5ba7577ceb7c8c36ae73dc6c1929`; typed Report/Body schema PR #818 merged as `41ce4f930a4105584672153f44cbb646d4fcbb49`; SSHSIG framing PR #820 merged as `19fbc786e92bf1e5ed5f4e4cd52a93d54fd56456`; benchmark-input hardening PR #821 merged as `9aef62a8a6c0e26517a042738c74b0689583c1fc`; strict CLI boundary PR #822 merged as `0d85f50ff14a3383355c14e2d654e5bbedbe56b5`; manifest/profile binding PR #823 merged as `5c5f0187ee99a152b07cfd72e201f5e2528172b2`; raw Git object codec PR #825 merged as `3c6cc8404ad9cf56dd648523936491c11ba9cca1`; prepared benchmark boundary PR #827 merged as `6ba1036fef680e2416c342077b6eff4adaf01e57`; Git batch codec PR #828 merged as `6adfa13db29283f5d289f633a93af16589737258`; pinned Git process boundary PR #830 merged as `5a6ae64b1c9d651b749691b6a8877c07a575ecbe`; revision/tree binding PR #831 merged as `956d943d23d569cd2f799b8871e72b4576c36162`; verified source materialization PR #832 merged as `1c9e2e9a3506573bee466eb940c47c5ec03a5360`; host-profile validation PR #833 merged as `f684b245707997bc114d7cc96f9ce8fe56392ebf`; container launch boundary PR #834 merged as `8ce95870bcf5f808f603e28eaf945003b7269dcc`; image/toolchain qualification PR #835 merged as `95c142f32429cde7dfa5dc7f30c23f4bf64319ca`; native host/daemon validation PR #836 merged as `3eaa2176cbac2f8890d6335bc27495a9a7599bc1`; monitor lifecycle core PR #837 merged as `0e39c8b933929e8af30ac142f16212712f5d0e40`; prepared execution owners PR #838 merged as `62acdd892c5d3c40dbe316cf8597fb40c14cbba9`; adversarial process/schedule/cleanup/exclusive-run owners PR #839 merged as `a9999aee0c3b5e8f57d99c074ba0d0768d7fe01a`; merge-race owners PR #840 merged as `04750821b417f426993de2f152dc59d35618e6e5`; controller/verifier execution PR #842 merged as `6812ced53015e50864fa910e9ca6e4b2afc4664b`; native host/daemon qualification PR #843 merged as `15e1fa9d7bfe94ec085630ec51283ff23683e02a`; native image self-inspection PR #844 merged as `88853de1fd96ac8e35c3542d69971f8370992ce2`; cryptographic key-process integration PR #845 merged as `dff1efdd49b8fdc6ea553661fb8a48ff357b242d`; native performance measurement PR #846 merged as `31ad135a0516bc110658391e5a87745661908d0f`; controller/report handoff PR #847 merged as `293f0afadcf5e89b9df56ef30c53874c154defe3`; merge verification PR #848 merged as `a9ba850e4ba40a583c838879868be67922aa4197`; decoded-owner prerequisite PR #849 merged as `69017961c65bec15ca39ef522813683f963fd896`; Request 7 language design and implementation PR #850 merged as `18301b43d6256349f984e4aaf62e975bf4f42aa0`
align-llm verification: PR #94 merged as `ba56ebed5ac1c82ebc5925e6257e7bd5dba8a9b9`; `.align-revision` pins `a440970ac81118ed2169f600b2b3c06fcb9cde7`; ordered `c6-json-escape-adoption` passed, and the final capable `make ci` passed in CI run `32109434515` at head `954258e24d93300dcdb78f8280de8868cf1ced56`; main run `32111007638` reused the exact merge-bound evidence
```

### Align language implementation (2026-08-17 — merged #850)

PR #850 accepts the authoritative Request 7 language design and ships the implementation. Typed
record, nested-record, scalar-string-array, AoS, SoA, and arena-backed union decoding share strict
RFC 8259 string-token validation. Clean selected strings remain zero-copy input views; selected
escaped strings materialize exactly once in the caller's enclosing arena and are region-bound to
both input and arena. Record, AoS, and union runtime entrypoints carry the nullable arena as their
final ABI argument; SoA retains its existing arena argument. `json.scan` has no arena and rejects an
escaped declared string, while `json.doc` materializes escaped accessors in its existing arena.
Ignored escaped keys and values validate without proportional scratch allocation. The shipped
surface does not add top-level `str`/`array<str>` decode, a hidden heap owner, a dynamic JSON tree,
or a second persisted format. The canonical fixture and closure matrix are owned by
`bench/json_escape/fixtures/canonical.json` and `docs/impl/core-design/json.md`.

The Align-side release build completed on merged `main` with exactly
`cargo build --release --workspace`. Align-llm PR #94 then passed Request 7's exact pin/adoption
target and final capable `make ci`; the merged shipped-surface and client evidence close Request 7.

### Align benchmark-evidence implementation progress (2026-08-16)

The merged implementation prerequisites through PR #846 establish the following bounded pieces of
the benchmark-evidence design without accepting or implementing Request 7's JSON language change:

- PRs #815–#818 isolate benchmark inputs under caller-supplied private roots, verify installed-source
  manifests without following links, provide canonical JSON primitives, and validate the complete
  typed `Report`/`Body` schema and its domain-separated body digest. PR #821 hardens the input owner
  with detached-lock freshness, final-symlink alias rejection, and process-group cleanup including
  TERM-ignoring descendants.
- PRs #820, #822, and #823 provide strict SSHSIG v1 framing and signing-preimage bytes, the exact
  producer/verifier/merge-verifier CLI boundary, and profile-bound installed-source verification
  with directory-race closure. They do not provision or consume a host signing key or execute the
  controller/verifier.
- PRs #825, #828, #830, and #831 provide canonical raw Git object identity, exact
  `git cat-file --batch` response parsing, the pinned Git process/configuration boundary, and
  bounded revision/tree traversal. Protocol failures terminate the owned reader so a rejected
  response cannot desynchronize a later read.
- PR #832 materializes a verified raw tree into a newly created private root, preserves tracked
  modes and reviewed in-tree symlinks, and re-verifies bytes, modes, link targets, inode uniqueness,
  and root identity through retained descriptors with fail-closed cleanup.
- PRs #833–#836 validate the canonical x86_64 host profile, fixed container launch vector,
  image/toolchain inspection record, and native host/daemon observation record. These are pure
  validation and construction boundaries over supplied observations; they do not inspect the host,
  invoke Docker, build an image, provision a key, or run the benchmark.
- PRs #827, #837, and #838 establish two-phase prepared benchmarks with sealed digest-bound
  artifacts, the pure monitor lifecycle ledger, and deterministic prepared-tree/execution boundary
  owners. PR #839 adds the fixed process, exact schedule, ordered cleanup/publication, and
  exclusive-run owner set, including its consolidated review repairs. PR #840 adds the disposable
  merge-race, response-binding, signed-artifact, and final-refetch owner. PR #842 adds the
  fixture-owned trusted controller/verifier phase ordering, report-only producer handoff,
  lock-held durable staging, and fail-closed restart boundary. It does not inspect a real host,
  invoke Docker, run the performance workload, manage keys, query GitHub, or advance lifecycle.
- PR #843 adds the privileged native host/daemon acquisition boundary: fixed Linux source reads,
  trusted Docker executable/configuration validation, bounded process-group cleanup, phase snapshots,
  profile-bound cgroup driver/parent propagation, and selected-CPU identity validation. It does not
  execute the image, run the workload, manage keys, measure performance, verify a merge, or advance
  Request 7's language lifecycle.
- PR #844 adds the native image self-inspection boundary: profile-pinned host image identity,
  immutable local-image selection, a fixed `--entrypoint` self-inspector with no network or host
  mounts, strict toolchain/cache/config parsing, and fail-closed Docker process/container cleanup.
  It does not manage keys, run the performance workload, verify a merge, or advance Request 7's
  language lifecycle.
- PR #845 adds the first real host-side cryptographic operation: profile-pinned `/usr/bin/ssh-keygen`
  sign/verify processes, no-follow descriptor-only private-key access, complete-message handoff, and
  fail-closed temporary-file and process cleanup. It does not provision the administrator secret,
  run the performance workload, measure performance, verify a provider merge, or advance Request 7's
  language lifecycle.
- PR #846 adds the first executable performance-measurement rail: one pinned Docker client launch
  per fixed prepared child, bounded stdout/stderr capture, prepare-time artifact binding, and exact
  native-output parsing into checked integer microseconds. It does not select `BASE`, assemble or
  sign the report, verify a provider merge, or advance Request 7's language lifecycle.
- PR #847 adds the immutable native session, exact fixed-schedule execution transcript, and report
  assembler that consumes child facts into fixed benchmark/report fragments with manifest,
  sample-order, integer-arithmetic, and threshold checks. It does not sign or publish the report,
  verify a provider merge, or advance Request 7's language lifecycle.
- PR #848 adds the signed merge-verification core. It reconstructs and rehashes the raw merge
  object, verifies first-parent reachability and exact baseline/candidate/tree bindings, and binds
  the result to the already verified report/signature. It does not implement JSON language semantics
  or advance Request 7's language lifecycle.

The evidence implementation boundary, Request 6, decoded-owner Request 15, and the authoritative
Request 7 language contract and implementation are now merged at distinct named commits. PR #850
was based on those prerequisites and closes the canonical-fixture/hash, exact arena ABI, and owner
matrix conditions below. Only align-llm pinning and adoption remain.

Benchmark-evidence design PR #813 defined the evidence boundary only and did not by itself accept
the JSON language change. The separate language acceptance and implementation subsequently merged
in PR #850 after every named acceptance-infrastructure prerequisite was present.
Request 6 supplies the recursively
Copy scanner-row boundary on which this request's scanner grammar matrix depends. Strict rejection
of a malformed ignored string and outside-arena rejection of an escaped retained view both add
failure edges after an earlier field may have made an owner live. The cleanup prerequisite must
close those edges for every affected `parse_object` caller and indexed AoS staging path. Joint
delivery is forbidden: the Request 7 implementation branch may be created only from an Align base
that already contains both named merged prerequisite commits, the benchmark-input slice, and the
separately designed and implemented benchmark-evidence boundary below. That reviewed boundary owns
immutable baseline selection, candidate binding, integration topology, and stale-evidence handling;
Request 7 does not invent those mechanisms in this register. All acceptance-infrastructure
prerequisites must merge and select the baseline before the implementation branch starts.

### Motivation

C6 persists human prompts, model proposals, diagnostics, failure-memory JSONL, paths, and error
detail in declared JSON records. These are ordinary UTF-8 strings and can contain newlines, quotes,
backslashes, tabs, carriage returns, NUL, and Unicode characters. `json.encode` correctly escapes
them, but the same record cannot be decoded again when a declared `str` field contains a JSON
escape. The minimum C6 adoption vector therefore uses `text: "x\n"`; an escape-free fixture would
weaken the persisted-format contract rather than test it.

The dynamic `json.doc` surface can unescape into an arena, but it is not a substitute: C6 requires
declared-record decoding, deterministic field validation, nested arrays/options, and canonical
re-encoding. Base64-wrapping every application string would be a second wire convention created
only to route around a missing typed-JSON capability.

### Current-state evidence

Verified at the pinned Align commit `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e` on
2026-07-30:

- `../align/docs/impl/core-design/json.md` says a typed `str` field and an `array<str>` element are
  zero-copy views into the input and that a JSON escape makes typed decode return `Err`.
- `../align/crates/align_runtime/src/lib.rs` rejects an escape when the typed decoder asks for a
  borrowed string span; it cannot return the escaped source bytes as the semantic value.
- `json.doc` already establishes the idiom for escape materialization: inside an explicit arena,
  `as_str()` unescapes into arena-owned storage and returns a region-bound view.
- The same authoritative JSON design records a shared strictness gap: typed decode and `json.doc`
  currently accept unescaped C0 bytes, and strict RFC 8259 string parsing must change both paths
  together. Typed unknown-value skipping can also bypass semantic string decoding.
- `json.decode` to SoA already receives an explicit arena; before PR #850, top-level/field union
  decode had no arena parameter. The merged implementation adds the nullable arena operand to the
  record, AoS, and union entrypoints; `json.scan` still reuses typed row parsing through an input
  view with no retained storage. Request 6 exclusively owns the scanner row-eligibility defect and
  proposes a recursively Copy boundary. Request 7 neither widens nor duplicates that ownership
  contract.
- The pinned surface admits `Option<Move record>`. Sema recursively admits the shape, the
  authoritative JSON design records it, and
  `m5.rs::json_option_move_struct_payload_remains_admitted` successfully produces
  `{"id":1,"meta":{"xs":[2,3]}}`, and ordinary MIR/LLVM `Drop` checks the option tag and frees the
  nested array owner. Decode-error cleanup in `drop_decoded_owned` still skips optional
  descriptors. Request 15 must repair failure, replacement, and cleanup ownership while preserving
  the admitted success surface before Request 7 implementation.
- Request 3 deliberately excluded escapes because its argv/tag consumer did not need them. C6 is
  the first fixed consumer that does.

### Requested capability

Extend declared-record `json.decode` so `str`, nested `str`, `Option<str>`, and `array<str>` fields,
including those reachable through `array<Struct>`, accept every RFC 8259 string escape, including
every escape emitted by the pinned `json.encode`. Preserve the existing zero-copy path for strings
without escapes. When an escape requires materialization, allocation must be explicit through an
enclosing `arena`; the decoded view is region-bound to that arena and the input. Align may refine
the exact compiler diagnostic and lowering shape, but it must not introduce a hidden heap owner or
return still-escaped bytes.

The intended source idiom is the existing typed API in an explicit region. This complete example
syntax-checks at the pinned compiler; Request 7 changes the runtime result for an escaped `text`
value, not the call syntax:

```align
import core.json

PromptArtifact { text: str }

fn decode_artifact(document: str) -> Result<(), Error> {
  arena {
    artifact: PromptArtifact := json.decode(document)?
    canonical := json.encode(artifact)
    print(canonical)
  }
  return Ok(())
}
```

Public-path closure is explicit:

| Public path | Valid escaped returned string | String syntax |
| --- | --- | --- |
| `json.decode` to a record or top-level/field `array<Struct>` | Inside an arena, materialize declared `str`, nested, option, scalar-string-array, and record-array values as specified below; outside, a returned value needing unescape is the existing JSON parse error `Error.Code(1)` | Strict for every key/value, including ignored values, on slow and speculative paths |
| `json.decode` to `soa<Struct>` | Supported because SoA already requires an arena; clean column elements borrow the input and escaped elements materialize once in that arena | Same strict grammar and errors as record decode |
| `json.doc` | Existing behavior retained: clean views borrow input; an escaped `as_str()` or `key(i)` result materializes once in the doc arena | Same strict grammar as typed decode |
| Top-level or field shape-directed union with a direct or transitively reachable `str` payload | Inside an enclosing arena, clean selected views borrow the input and escaped selected fields materialize once in that arena; outside an arena, a selected escaped view returns `Error.Code(1)`. The same rule applies through object/array payload records and a union nested in an arena-backed record | Strict grammar still applies to the complete union input and ignored object members |
| `json.scan` | Row ownership and eligibility are N/A to Request 7 and remain exclusively owned by Request 6. For a row admitted by Request 6's recursively Copy boundary, materialization is also N/A: the scanner owns no arena or stable scratch beyond one row. Any escaped declared view makes the fused terminal return `Error.Code(1)`, including an unprojected, nested, optional, or union-reachable non-owning field | Request 7 applies strict grammar to every key/value in each admitted Copy row under both top-level-array and NDJSON framing |
| Top-level `str` or `array<str>` decode | N/A: both targets remain rejected by the current semantic surface and this request does not add them | No runtime path exists until a separate consumer requests those target types |

Non-string scalar arrays retain their current value semantics, but ignored string keys/values within
their containing document follow the same strict grammar. Encoding already accepts semantic `str`
values and is unchanged.

Required semantics:

- outside an arena, the current zero-copy clean-string path remains valid; a declared returned
  `str` value that needs retained unescaping returns `Error.Code(1)`. Decoded-owner Request 15 must
  already guarantee that any owner made live by an earlier field is released and
  no partially initialized value is returned;
- on the materializing record/AoS/SoA/union paths inside an arena, clean strings remain zero-copy
  input views and escaped strings materialize only their decoded UTF-8 bytes in the arena. The
  scanner path remains `Error.Code(1)` for a recursively reachable escaped declared view; a
  union path follows the same arena-versus-no-arena rule even when nested in an arena-backed outer
  record;
- a materialized decoded field's region is the meet of every storage region it may view, so the
  enclosing record, nested record, option, array spine, and `array<str>` elements cannot escape
  either the input owner or arena;
- `\"`, `\\`, `\/`, `\b`, `\f`, `\n`, `\r`, `\t`, and valid `\uXXXX` sequences decode to their
  semantic bytes. Valid surrogate pairs produce one Unicode scalar; lone, reversed, or malformed
  surrogates and malformed/truncated escapes return `Error.Code(1)`;
- an escaped `\u0000` produces one embedded NUL byte in the semantic `str`. Application validators
  remain responsible for rejecting NUL in paths, environment names, or other native boundaries;
- every JSON string token is grammar-checked before use or skipping: an unescaped C0 byte is
  `Error.Code(1)`, and malformed escapes in declared values, undeclared values, declared keys, or
  undeclared keys cannot be accepted merely because a field is ignored or a speculative path does
  not project it. Apply the same string grammar to `json.doc` so the two public parsers do not
  disagree. This requirement creates no unsound owner-live failure edge because Request 7 cannot
  enter implementation until decoded-owner Request 15 is shipped;
- typed key lookup compares semantic unescaped bytes: a valid escaped spelling of a declared key
  matches that field, a valid escaped unknown key remains ignored, and two raw spellings that
  decode to the same declared key are a duplicate-key error. `json.doc.key(i)` returns the same
  semantic key bytes. Outside an arena, typed key validation and lookup use one incremental
  decoder with fixed-size local state: it validates each escape and UTF-8 sequence, compares
  decoded bytes directly with the declared ASCII identifiers, and discards an unknown key without
  constructing its semantic text. The existing declared-field seen state detects a duplicate only
  after that streaming comparison identifies the field. Ignored string values use the same
  fixed-state grammar validation and discard their decoded bytes. These paths allocate no heap or
  arena scratch proportional to the token or input. Only `json.doc.key(i)`, whose document already
  owns an explicit arena, materializes a returned semantic key;
- duplicate declared keys, missing required fields, unknown-field ignore, field-order freedom,
  number/type validation, and valid unknown-value skipping retain their current behavior;
- slow and speculative typed-decode paths produce identical semantic values, canonical encodings,
  errors, successful materialized-string allocation counts, and storage/region classifications.
  Before any typed path materializes a returned string, one fixed-state validation pass checks UTF-8
  and the complete input's string-token grammar, including ignored keys and values. Thus invalid
  UTF-8, a raw C0 byte, or a malformed escape anywhere fails with zero retained-string
  materializations on slow, speculative, and fallback rails. The speculative path additionally
  validates every projected key and value span that can cause fallback before it materializes an
  escaped string, so abandoning speculation contributes zero materializations. Every successful
  path makes exactly one retained arena allocation per escaped returned value or escaped
  `json.doc` key accessor result. A later duplicate, type, range, missing-field, or trailing-input
  semantic failure may leave already materialized typed bytes unreachable in the caller's arena;
  the hand-authored precedence matrix records the exact per-rail count for an escaped selected
  field before each such fault and proves fallback never double-materializes it. Request 7 adds no
  runtime-owned variable-size scratch allocation. Existing decoded-owner transition gaps remain
  outside this equivalence claim, and Request 7 must not add a new owner-live transition;
- `json.encode` of the decoded record emits the existing canonical escape spelling and declaration
  field order. Decode/encode symmetry does not require retaining the input's alternate escape
  spelling;
- scanner framing is N/A to this request. Scanner fixtures use only well-formed top-level-array and
  NDJSON frames admitted by the shipped parser; Request 7 changes string-token grammar inside a
  Request 6-admitted Copy row only. Missing delimiters, ambiguous EOF, frame selection, row
  boundaries, and other framing behavior retain their shipped semantics. No C6 consumer uses
  `json.scan`; a concrete future consumer must register a separate request before requiring
  framing repair;
- on already-correct nested field-array cleanup paths, partial decode failure still drops every
  owned array spine and nested owned field already constructed; arena allocations follow normal
  arena cleanup and are not individually freed. The prerequisite must extend exact cleanup to the
  separately demonstrated optional-owner, indexed top-level AoS fallback, top-level
  `array<MoveStruct>` staging, and trailing-garbage gaps before Request 7 is implemented;
- JSON number-grammar strictness is N/A to this request because it does not share string
  materialization or storage ownership; C6 records any required numeric strictness separately;
- the feature does not add a dynamic JSON value type. Request 7 neither changes the admitted
  `Option<Move record>` surface nor closes the separately demonstrated decoded-owner transition
  gaps: an optional owner followed by a later enclosing-object failure on that shipped
  implementation path; an owner overwritten across indexed top-level AoS speculation and
  successful or failed fallback; current or completed top-level `array<MoveStruct>` staging
  followed by later failure or trailing garbage; and required or currently admitted optional
  owners live when a top-level record rejects trailing garbage. Request 15 must preserve
  `Option<Move record>` support and audit every admitted
  construction, speculative write, replacement and source nulling, fallback, staging, return, and
  cleanup transition and assign it to an explicit owner module and allocation-count regression.
  That follow-up is an implementation prerequisite, not merely an excluded future improvement.

Validation order is deterministic and preserves the existing parser's observable precedence:

1. validate whole-input UTF-8 before returning any borrowed view;
2. validate each string token's raw C0 and escape grammar when that token is encountered, before
   semantic key comparison, declared-value decoding, or unknown-value skipping;
3. report a duplicate declared key when its second semantic spelling is encountered;
4. report type, numeric-range, and retained-escape-without-arena errors while decoding that value;
5. check missing required fields after the closing object; and
6. reject trailing non-whitespace after the complete top-level value.

An earlier malformed ignored key or value therefore wins over a later missing-field error.
Speculation may return to fallback before choosing an outcome, but it must not materialize an
escaped returned string first; fallback remains the source of truth for the same earliest
observable error.

The differential result oracle separates string grammar from each path's materialization and
semantic policy. Each row below is a complete otherwise-valid fixture for that path:

| Input class | Arena-backed record / AoS / SoA | No-arena record / AoS | Union / Request 6-admitted scanner row | `json.doc` |
| --- | --- | --- | --- | --- |
| Clean selected declared string | success, borrowed semantic bytes | success, borrowed semantic bytes | success, borrowed semantic bytes | success, borrowed semantic bytes |
| Valid escaped selected declared string | success, arena-backed semantic bytes | `Error.Code(1)` | `Error.Code(1)` | success, arena-backed semantic bytes |
| Valid escaped declared key with a clean selected value | success and semantic key match | success and semantic key match | success and semantic key match | success and semantic key bytes |
| Valid escaped ignored key or value with clean selected values | success | success | success | success |
| Malformed escape or raw C0 in any declared or ignored key/value | `Error.Code(1)` | `Error.Code(1)` | `Error.Code(1)` | parse `Err` |
| Literal and escaped spellings of the same declared key | `Error.Code(1)` duplicate | `Error.Code(1)` duplicate | `Error.Code(1)` duplicate | success under the shipped document duplicate policy; lookup remains first-match |
| Missing required declared field or declared type mismatch | `Error.Code(1)` | `Error.Code(1)` | `Error.Code(1)` | success as a schema-unknown document |
| Non-whitespace trailing bytes after a complete non-scanner top-level value | `Error.Code(1)` | `Error.Code(1)` | `Error.Code(1)` for the applicable union; scanner framing is N/A and unchanged | parse `Err` |

The hand-authored multi-invalid precedence corpus fixes the following typed-decode outcomes on slow,
speculative-success, and fallback rails; the same applicable outcome is required for AoS, SoA,
union payload records, and scanner rows:

| Ordered faults in one fixture | Required first failure |
| --- | --- |
| Any semantic fault plus invalid UTF-8 anywhere | whole-input UTF-8 validation |
| Earlier malformed ignored string, later duplicate/type/missing/trailing fault | string grammar at the malformed token |
| Earlier duplicate declared key, later malformed ignored string | duplicate at the second semantic key |
| Earlier declared type/range error, later malformed ignored string | type/range error at the declared value |
| Earlier valid fields, malformed ignored string, then missing required field at `}` | string grammar at the malformed token |
| Missing required field at `}`, then trailing non-whitespace | missing-field failure |
| Complete valid top-level value, then trailing non-whitespace | trailing-input failure |

For `json.doc`, duplicate, missing, and declared-type conditions are intentionally not semantic
errors; its applicable precedence cases are UTF-8, malformed string grammar, and trailing input.
The scanner runs both top-level-array and NDJSON variants, but only with valid outer framing; its
applicable precedence cases combine UTF-8, string grammar, and row-semantic failures, not trailing
or framing faults. Every precedence regression asserts the internal failure kind and byte offset
described below in addition to the public `Error.Code(1)` or parse `Err`, so identical public error
discriminants cannot hide rail drift.

The typed retained-string allocation oracle is also exact. Any UTF-8 or string-grammar failure
anywhere is found by the fixed-state prevalidation pass and records zero materializations. For a
later semantic fault, a fixture with zero, one, and two earlier escaped selected fields records
respectively zero, one, and two materializations on the slow rail and on the committed fallback
rail. The speculative prefix must record zero before it abandons to fallback, so the complete
speculative/fallback attempt has the same total and never materializes one field twice. Reversing
the order so the semantic fault precedes every escaped selected field records zero. All retained
bytes remain arena-owned and unreachable after failure; no partial value is returned.

The implementation closure ledger for the future Align design is:

| Transition | Required owner module / entrypoint | Exact regression owned by the Align design |
| --- | --- | --- |
| Type inference, arena availability, region meet, and construction | `align_sema::check_json_decode`, region/storage-root analysis, and the corresponding `align_mir` JSON decode lowering | `m5::json_escape_typed_region_matrix` |
| Record and nested-record success, outside-arena failure, later sibling failure, return, and cleanup | `align_rt_json_decode`, `parse_object`, shared value writing, and shipped decoded-owner Request 15 | `json_escape_record_lifecycle` and `json_escape_record_owner_transition_integration` |
| Top-level and field AoS success plus slow/speculative/fallback string equivalence | `align_rt_json_decode_struct_array`, `json_speculate`, `json_fallback`, `write_field_indexed`, and shipped decoded-owner Request 15 | `json_escape_aos_path_equivalence` and `json_escape_aos_owner_transition_integration` |
| SoA count, allocation, fill success/failure, and arena cleanup | `align_rt_json_decode_soa` and the shared indexed writers | `json_escape_soa_path_equivalence` |
| Union and scanner non-materialization, including ignored and malformed string tokens inside valid scanner frames | `align_rt_json_decode_union` and `align_rt_json_scan_next`; Request 6 separately owns scanner row eligibility and scanner framing is unchanged | `json_escape_nonmaterializing_paths` |
| `json.doc` parse, lookup, `as_str`, `key`, malformed input, and arena cleanup | `align_rt_json_doc_parse`, `json_unescape_into`, `align_rt_json_doc_as_str`, and `align_rt_json_doc_key` | `json_doc_strict_string_matrix` |
| Cold/cache-hit whole-program and per-unit compilation plus any internal ABI update | semantic and MIR fingerprints, codegen descriptors, compiler build identity, and every changed JSON runtime declaration | `m5::json_escape_cache_and_abi` |
| Root plus detached benchmark dependency resolution, controller trust, immutable baseline and candidate identity, raw worktree materialization, Git object/config isolation, every Cargo configuration search directory, protected inputs, warm-up, paired samples, parsing, threshold failure, evidence, and integration | Evidence-boundary design PR #813 and its dependent enabling implementation are merged; the C6-LIFECYCLE pin/adoption wave owns the remaining exact compiler, source, and real-client qualification | the merged prerequisite plan names exact unit, fault-injection, workload, report, review, and integration regressions for every closure class in item 12, and the merged implementation plus its adoption owners must pass them before the C6 wave's final `make ci` |
| Minimum Git behavior, not only version parsing | topology-ledger-owned immutable Git 2.45.0 image plus required `git-2.45-compat` job | the complete production adoption gate and all repository/Git negatives under actual `/usr/bin/git` 2.45.0 |
| Canonical revision-file bytes and exact filter-independent tracked/untracked filesystem state before lookup or release build | binary-safe shared revision reader, raw tree/index/worktree enumerator and comparator, `scripts/check-align-revision`, `align-build` prerequisite order, and topology-ledger self-test | exact valid record plus embedded-NUL and other encoding, Git-marker, attribute/filter-hidden modification, assume-unchanged, skip-worktree, ignored and case-fold-hidden build inputs, target-output allowlist, dirty/untracked, and unchanged-index/build-output negatives |
| Fresh compiler construction, input trust and identity, process ownership, use, and cleanup | The reviewed Section 9 contract in `docs/specs/check-gate-topology.md` and its wire/source-identity foundations are merged. FRESH-IMAGE owns installation and attestation of the image trust root; FRESH-WORKER owns the repository worker, Make integration, identity-bound baseline refresh, and cleanup. Request 6 additionally requires the separately reviewed FRESH-IMAGE-REQUEST6 installed-profile extension before its ordinary or fresh adoption. Every other pin-changing adoption remains blocked until its applicable image and worker capabilities merge. | Run every Section 9 named owner qualification, the installed-image end-to-end unchanged-pin aggregate, the Request 6 profile-extension smoke where applicable, baseline ancestry checks, and cleanup evidence before worker merge or later adoption. Aarch64 Linux/macOS consumers additionally require their named platform profiles. |

Clean returned views remain owned by the input; materialized returned bytes are owned by the
explicit arena; array spines retain their existing heap or arena owner; key, skipped-string, and
whole-input grammar validation retain only fixed-size local decoder state; and unescaped returned
bytes are written directly to their explicit arena destination. A semantic slow-path failure after
grammar validation and materialization may leave unreachable bytes in the caller's arena until
that arena's normal bulk cleanup, but returns no view and may retain at most one allocation per
escaped returned field encountered before the error. A string-grammar or UTF-8 failure retains
zero. No parser state or decoded view becomes process-global.

Exact logical allocation and precedence observation use a caller-owned, `cfg(test)`-only
`JsonDecodeTestProbe` threaded through internal parser helpers. Production `extern "C"` entrypoints
pass no probe, so this adds no production ABI or ambient state. The probe records the first
validation failure kind and input byte offset, retained-string materialization count and bytes,
temporary string heap-allocation count and peak bytes, speculation attempts, and fallbacks. The
arena helper increments the logical materialization fields exactly where it reserves bytes for one
returned escaped string; fallback tests require those fields to remain zero until fallback
validation succeeds, and key/skip tests require both temporary-allocation fields to remain zero.
Each runtime unit test creates its own probe, so concurrent tests have no shared counter, reset
order, lock, or cross-test contamination. Existing heap-allocation instrumentation remains
separate and continues to observe array-spine ownership. Every regression that reads those
process-global heap allocation counters must acquire the existing `ALLOC_COUNT_LOCK` as its first
executable statement, before fixture or descriptor setup and before any allocation. It must hold
the guard through baseline snapshots, decode success or failure, cleanup or `Drop`, final
snapshots, and assertions. Such a regression must not acquire the lock recursively. A test using
only its caller-owned probe needs no lock; if it also reads a heap counter, the whole-body lock
rule applies.

The shipped internal arena-passing ABI names every changed MIR operand and runtime signature:
record, AoS, and union decode carry a nullable final arena argument, while SoA keeps its existing
arena argument and `json.scan` carries none. No hidden ambient arena exists. CLI inputs,
environment variables, process-global state, connection-global state, and overlap exclusion are
N/A because this parser capability adds none; concurrent invocations retain only distinct
fixed-size per-call parser state and follow the existing caller-owned arena rules.
Persisted scalar widths, field order, schema version, and tags are unchanged; the existing encoder
and the exact adoption vector below remain the semantic-to-byte and byte-to-semantic sources of
truth.

### Acceptance / gate

Align compiler/runtime tests must:

1. round-trip one declared record containing clean text and every supported short escape through
   `decode -> encode -> decode`, and compare the semantic bytes after both decodes;
2. cover a nested record, `Option<str>` in both `Some` and missing/`null` states, and an
   `array<str>` containing clean, escaped, empty, embedded-NUL, and multibyte values;
3. decode `\u0041`, `\u20ac`, `\u00E9`, and the valid pairs `\ud83d\ude00` and
   `\uD83D\uDE00`; reject lone `\ud83d`, lone
   `\ude00`, reversed `\ude00\ud83d`, truncated `\u123`, non-hex `\u12x4`, and a high surrogate
   followed by a non-low-surrogate escape;
4. prove the clean path still points into the input while escaped values point into the explicit
   arena, and prove neither view can escape its owner;
5. reject a typed decode whose returned declared `str` field needs unescaping outside an arena with
   `Error.Code(1)`; with the decoded-owner prerequisite in place, prove no earlier required owner
   leaks and no partially live record is returned. If that prerequisite retains
   `Option<Move record>`, prove the same for an earlier optional owner. Separately accept escaped
   declared keys and valid escaped ignored values outside an arena because neither retains a
   decoded view. With the whole-body allocation-counter lock, compare clean, escaped-declared-key,
   escaped-unknown-key, and escaped-ignored-value cases and prove that key/skip validation adds no
   heap or arena allocation;
6. decode `Root { rows: array<Row> }` where clean and escaped fields appear in Copy and Move element
   records, nested record arrays, options, and scalar-string arrays; on this already-correct nested
   field-array path, inject a malformed escape after initialized Move elements and prove exact deep
   cleanup;
7. run slow, speculative-success, and speculative-fallback paths over the same corpus and require
   identical semantic records, encoded bytes, errors, exact retained materialized-string arena
   allocation counts, string-view ownership, and arena cleanup; force fallback after an escaped
   projected value and prove that it abandoned zero arena allocations. Run the owner-live
   integration regressions only against the named shipped cleanup prerequisite;
8. reject raw C0 bytes and malformed escapes in declared and ignored string values and keys through
   both typed decode and `json.doc`; accept an escaped spelling of a declared key, ignore a valid
   escaped unknown key, and reject duplicate semantic declared keys spelled once literally and once
   with escapes on typed paths, while `json.doc` retains its shipped duplicate-member and
   first-match lookup policy. Retain typed missing-field rejection and field-order independence;
9. cover the public-path matrix directly: a top-level `array<Struct>` distinct from a field array;
   `soa<Struct>` with clean and escaped column elements; direct and nested/object/array union
   payloads plus a union field in an arena-backed record, where clean text borrows the input and
   escaped selected text materializes in the enclosing arena, while the corresponding no-arena
   cases return `Error.Code(1)`; top-level-array and NDJSON
   `json.scan` rows admitted by the merged Request 6 recursively Copy boundary, always inside
   well-formed outer frames, that accept all-clean text but reject an escaped declared view even
   when it is unprojected, nested, optional, or union-reachable; malformed ignored text rejection
   on both paths; and compile-time rejection of top-level `str` and `array<str>` decode targets.
   Request 6, not Request 7, owns compile-time rejection and diagnostic coverage for scanner rows
   containing an owned scalar or record array. Scanner framing behavior is N/A and receives no
   changed production code or repair assertion.
10. compile cold and cache-hit whole-program and per-unit users. A compiler update invalidates old
    objects through the compiler build identity; within one compiler build, unchanged schemas may
    hit while a reachable schema edit misses through the structural MIR fingerprint, and all four
    executions produce identical values/errors. If lowering adds an arena parameter to a runtime
    entrypoint, the Align plan must name that internal ABI signature and keep compiler/runtime
    identity lockstep; unrelated public JSON source syntax and runtime entrypoints remain unchanged.
11. consume an exact checked-in 4,096-line JSONL corpus at
    `crates/align_driver/tests/fixtures/json_escape_differential.jsonl`. The fixture bytes, not a
    generator or seed, are the test source of truth. Each compact-JSON line uses this canonical key
    order:
    `schema_version`, `ordinal`, `validity_class`, `wrapper_shape`, `nesting_depth`,
    `boundary_class`, `anchor_token_offset`, `raw_token_hex`, `grammar_valid`, and
    `semantic_bytes_hex`; the last field is lowercase hex for a valid token and `null` for an
    invalid token. `schema_version` is the JSON integer `1`; `ordinal`, `nesting_depth`, and
    `anchor_token_offset` are nonnegative JSON integers; the three enumerated class/shape fields are
    JSON strings; `raw_token_hex` and every non-null `semantic_bytes_hex` are even-length lowercase
    hex strings; and `grammar_valid` is a JSON boolean. Files use UTF-8, LF endings, no blank lines,
    and ordinals `0..4095`.
    Coverage is the complete Cartesian product of eight validity classes (`clean_ascii`,
    `clean_utf8`, `short_escape`, `unicode_escape`, `surrogate_pair`, `malformed_escape`,
    `malformed_surrogate`, and `raw_c0`), four document-wrapper shapes (`minimal`, `prefix_pad`,
    `suffix_pad`, and `both_pad`), unknown-value nesting depths `0..3`, four boundary classes
    (`interior`, `end_16`, `end_32`, and `end_64`), and variants `0..7`, ordered lexicographically
    by those dimensions. The variant is encoded by `ordinal % 8`; it is not a separate field.
    The following table is the exact variant oracle. Each comma-separated entry is the lowercase
    hex for the bytes between the token's opening and closing `22` quote bytes, in variant order
    `0..7`; the second list is the corresponding `semantic_bytes_hex`. The complete
    `raw_token_hex` is therefore `22 + body + 22`. `null` is literal JSON null. No generator may
    substitute another spelling or duplicate an entry:

    | `validity_class` | body hex for variants `0..7` | semantic hex for variants `0..7` |
    | --- | --- | --- |
    | `clean_ascii` | `61`, `5a`, `30`, `20`, `7e`, `2f`, `2d`, `7f` | `61`, `5a`, `30`, `20`, `7e`, `2f`, `2d`, `7f` |
    | `clean_utf8` | `c2a2`, `c3a9`, `e282ac`, `e6b0b4`, `f09f9880`, `f09090b7`, `c3b1`, `d096` | `c2a2`, `c3a9`, `e282ac`, `e6b0b4`, `f09f9880`, `f09090b7`, `c3b1`, `d096` |
    | `short_escape` | `5c22`, `5c5c`, `5c2f`, `5c62`, `5c66`, `5c6e`, `5c72`, `5c74` | `22`, `5c`, `2f`, `08`, `0c`, `0a`, `0d`, `09` |
    | `unicode_escape` | `5c7530303431`, `5c7530304539`, `5c7532304143`, `5c7536433334`, `5c7530303030`, `5c7530303166`, `5c7530303766`, `5c7546464644` | `41`, `c3a9`, `e282ac`, `e6b0b4`, `00`, `1f`, `7f`, `efbfbd` |
    | `surrogate_pair` | `5c75443833445c7544453030`, `5c75643833645c7564653033`, `5c75643833645c7564653830`, `5c75643833345c7564643165`, `5c75643830305c7564633030`, `5c75646266665c7564666666`, `5c75643833635c7564663064`, `5c75643833655c7564646431` | `f09f9880`, `f09f9883`, `f09f9a80`, `f09d849e`, `f0908080`, `f48fbfbf`, `f09f8c8d`, `f09fa791` |
    | `malformed_escape` | `5c78`, `5c61`, `5c75`, `5c7531`, `5c753132`, `5c75313233`, `5c7531327834`, `5c752b313233` | `null`, `null`, `null`, `null`, `null`, `null`, `null`, `null` |
    | `malformed_surrogate` | `5c7564383030`, `5c7564633030`, `5c75646330305c7564383030`, `5c75643830305c7530303431`, `5c75643830305c6e`, `5c75643830305c7564383030`, `5c75646266665c7564376666`, `5c75643830305c7564633078` | `null`, `null`, `null`, `null`, `null`, `null`, `null`, `null` |
    | `raw_c0` | `00`, `01`, `08`, `09`, `0a`, `0d`, `1e`, `1f` | `null`, `null`, `null`, `null`, `null`, `null`, `null`, `null` |

    The fixture verifier recomputes this table from every row's class and `ordinal % 8` and rejects
    any byte, semantic value, ordering, or duplicate drift before invoking a parser.
    `grammar_valid` is `true` exactly for the first five named validity classes and `false` for
    `malformed_escape`, `malformed_surrogate`, and `raw_c0`; a true row's
    `semantic_bytes_hex` is exactly the semantic UTF-8 byte sequence obtained from `T`.
    `raw_token_hex` is lowercase hex for the complete source token from its opening double quote
    through its closing double quote. Even an invalid token is quote-terminated; truncated
    whole-token structure is outside this grammar corpus. `anchor_token_offset` is the zero-based
    byte offset of the class anchor within those decoded `raw_token_hex` bytes, not an offset in any
    containing document.
    Every token has exactly one class anchor: the first content byte for non-empty `clean_ascii`;
    the first byte of the first multibyte scalar for `clean_utf8`; the backslash beginning the
    class-defining escape for `short_escape`, `unicode_escape`, or `surrogate_pair`; the backslash
    beginning the first malformed escape or ill-formed surrogate sequence for
    `malformed_escape` or `malformed_surrogate`; and the first raw C0 byte for `raw_c0`. A variant
    may contain other bytes of the same class, but none before its anchor.

    Every public-path instance is reconstructed byte-for-byte from the manifest. Let `T` be the
    bytes decoded from `raw_token_hex`; let `V0 = T`; and let
    `Vd = {"next":Vd-1}` for nesting depths `d = 1..3`, with exactly those ASCII bytes and no
    whitespace. For `wrapper_shape`, let `(L,R)` be `("","")` for `minimal`, `(" ","")` for
    `prefix_pad`, `(""," ")` for `suffix_pad`, and `(" "," ")` for `both_pad`, where each nonempty
    value is one ASCII space immediately before or after the complete `Vd`. For a nonnegative
    integer `p`, let `P` be exactly `p` lowercase ASCII `a` bytes and construct the inner object:

    ```text
    O(p) = {"__pad":"P","required":1,"probe":L Vd R}
    ```

    The notation separates substitutions only: the constructed bytes contain no spaces other than
    `L` and `R`, use exactly the shown member order and punctuation, and encode `P` inside the
    `__pad` string. The path adapters are exactly:

    ```text
    object  = O(p)
    array   = [O(p)]
    ndjson  = O(p)\n
    ```

    The `object` adapter is consumed by record, object-union, and `json.doc`; `array` is consumed by
    top-level AoS, flat SoA, and top-level-array `json.scan`; and `ndjson` is consumed only by
    NDJSON `json.scan`. The typed schemas declare `required: i64`; `__pad`, `probe`, and every
    nested `next` member are undeclared and ignored. Thus every typed input contains all required
    fields. The array delimiters and NDJSON line ending therefore remain valid framing bytes even
    when `T` deliberately makes the contained JSON value invalid.

    Each adapter independently chooses the smallest `p >= 0` whose final-document absolute anchor
    offset `a`—computed from that adapter's first byte through `anchor_token_offset` within `T`—
    satisfies the selected boundary class. `end_16`, `end_32`, and `end_64` respectively require
    `(a + 1) % 16 == 0`, `% 32 == 0`, or `% 64 == 0`. `interior` requires
    `4 <= a % N <= N - 5` for every `N` in `{16, 32, 64}`. The adapter test reconstructs the exact
    bytes, proves its chosen `p` satisfies the equation, proves every smaller nonnegative `p` fails
    it, and locates the class anchor at that adapter-specific `a`. An invalid row additionally
    asserts the parser's internal failure offset equals `a`; a valid row asserts successful ignore
    and has no failure offset.

    The authoritative Align design must check in this exact fixture and record its lowercase
    SHA-256 before Request 7 may advance to `ACCEPTED`; the test first verifies the byte hash, line
    count, ordinal sequence, field schema, raw-token quoting and lowercase hex, wrapper-shape
    mapping, class-anchor rule and `anchor_token_offset`, Cartesian coverage, and then every
    adapter's exact template, minimal padding, absolute anchor, and boundary equation. This large
    corpus owns string grammar only. Each row is instantiated for record/AoS/flat
    SoA/object-union typed decode, `json.doc`, and both valid-frame forms of a Request 6-admitted
    Copy `json.scan`; a valid row succeeds with the undeclared value ignored, and an invalid row
    produces that path's malformed-string result at the computed adapter-specific anchor.
    This is executable for flat SoA because the nested token is always in an undeclared value, not
    a column. Declared-key semantic matching, declared returned-value materialization,
    `json.doc.key`, duplicate, missing, declared-type, trailing-input, and scanner-framing behavior
    are deliberately excluded from the large Cartesian corpus and remain owned by the exact
    hand-authored public-path and precedence matrices in items 1–9. In particular, the corpus never
    claims that arbitrary UTF-8 or surrogate-pair semantic bytes can name an Align field; declared
    field names remain ASCII identifiers. The test asserts this grammar-specific oracle rather
    than unconditional cross-path agreement.
12. first merge a separately reviewed benchmark-input enabling slice that removes the detached
    `bench/json_decode/Cargo.lock` and `bench/json_soa/Cargo.lock` ignores, checks in both generated
    lockfiles, and makes every Cargo command in both benchmark scripts use `--locked --offline`:
    both root-workspace `cargo build` commands and the detached-workspace `cargo run`. The enabling
    slice's tests prove that the root and each detached workspace reject a missing or
    manifest-inconsistent lockfile and that an incomplete offline cache fails without network
    access, registry update, lockfile write, or build output. Tool selection and invocation belong
    to the benchmark-evidence design rather than this slice.

    Align PR #813 merged the separate evidence-boundary design at
    `docs/impl/core-design/json-escape-benchmark-evidence.md`. That document explicitly did not
    accept the JSON language change; the separate language design and implementation later
    satisfied the fixture/hash and exact-ABI conditions in PR #850 after the evidence
    implementation had merged.
    The prerequisite owns the controller source and delivery,
    exact public invocation, immutable pre-work baseline selection, candidate binding, trust roots,
    executable and source identities, raw-object and checkout isolation, environment and descriptor mapping,
    credential handling if any provider API is used, concurrency boundary, report schema, exact-SHA
    review and integration evidence, failure cleanup, and every adversarial regression. It must
    prevent implementation-controlled measurement code from selecting or attesting itself and must make every
    accepted baseline, candidate, executable, and report identity independently reproducible.

    The design must explicitly close construction, success, failure, cleanup, early exit, malformed
    input, executable swap, descriptor collision and inheritance, stale or forged report, base
    drift, and integration races. It must either bind execution to already-open verified objects or
    state and test an equivalent non-conflicting privilege boundary. If it uses a hosting API, it
    must bind endpoint, authenticated principal, repository, ref, expected-old and new OIDs, client,
    request bytes, response semantics, and secret non-exposure. Request 7 deliberately does not name
    a hypothetical controller, launcher, token channel, merge mechanism, or provider helper before
    that independent design review. The dependent enabling implementation and its full acceptance
    matrix must merge before the immutable baseline is selected or a Request 7 implementation
    branch is created.

    The separately reviewed evidence design may refine orchestration, but it must preserve the
    benchmark workload and acceptance outcome below: one pre-work baseline containing the
    benchmark-input slice plus both language prerequisites and serving as the exact Request 7
    implementation branch point, the proposed final Request 7 candidate with no unrelated delta,
    byte- and mode-identical protected benchmark inputs, one identical verified effective toolchain,
    one otherwise-idle named host, ten
    order-balanced sample pairs, and all five candidate/baseline median ratios at or below `1.05`.
    The pull request must carry the controller-produced complete report and immutable identities.
    Request 7 supplies only these consumer acceptance requirements to that separate design:

    - the baseline is the exact parent of the first Request 7 implementation commit; candidate is
      its reviewed final descendant, and every intervening commit and changed path belongs to the
      accepted Request 7 implementation closure. An unrelated commit or path, or target-branch
      movement before branch creation, requires a new baseline and evidence rather than measuring a
      mixed delta;
    - baseline and candidate use byte- and mode-identical `.cargo/`, root `Cargo.toml`,
      `Cargo.lock`, optional root `rust-toolchain` and `rust-toolchain.toml`, optional
      `bench/.cargo/`, and complete `bench/json_decode/` and `bench/json_soa/` trees; any
      missing/present mismatch or content, dependency, configuration, workload, generator, timing,
      or lockfile drift fails before measurement;
    - baseline and candidate dependency resolution for the root, `bench/json_decode`, and
      `bench/json_soa` workspaces is `--locked --offline`, semantically identical per corresponding
      workspace, and neither writes a lockfile, updates a registry, or accesses the network;
    - both revisions use the same verified Cargo and Rust compiler binaries, versions, effective
      target/configuration, environment semantics, and dependency cache contents; any difference
      that can affect generated code or timing rejects the comparison before measurement;
    - both revisions run the protected `bench/json_decode/run.sh native` and
      `bench/json_soa/run.sh native` workloads on the same otherwise-idle named host with native CPU
      mode and the row whose first column is exactly decimal `1000000`; no baseline/candidate run
      overlaps another;
    - one discarded warm-up per revision and benchmark precedes ten measured pairs; odd pairs run
      baseline then candidate and even pairs candidate then baseline;
    - the five measured fields are exactly `A-full`, `A-proj`, `soa ms`, `aos ms`, and `proj ms`;
      each sample is the script's numeric millisecond value for the named million-row field, and
      missing, duplicate, non-finite, wrong-row, or otherwise unparsable output fails;
    - for each field and revision, sort the ten values without additional rounding and define the
      median as the arithmetic mean of samples five and six; every
      `candidate_median / baseline_median` ratio must be at most `1.05`; and
    - any identity, isolation, protected-input, dependency, execution, parsing, timeout, cleanup,
      or evidence failure produces no accepted benchmark result. The Request 7 pull request records
      the controller-produced immutable baseline/candidate identities, all parsed samples, medians,
      ratios, host/toolchain observations required by the evidence design, and its accepted report;
      a failed threshold or missing evidence remains blocking.

13. after the cleanup prerequisite ships, place a required owner before a malformed ignored string
    and before an outside-arena escaped returned field in record and union-payload fixtures; if the
    prerequisite retains `Option<Move record>`, repeat with an optional owner. Place owners in the
    current and completed rows before the same failures on slow, speculative, and fallback
    top-level AoS rails. The request's caller-owned probes and existing heap-allocation
    instrumentation must prove deterministic failure position, zero leaked owners, no returned
    partial value, and full cleanup on every ordering. Each regression reading the existing
    process-global heap counters must acquire `ALLOC_COUNT_LOCK` as its first executable statement
    and hold it through all setup, snapshots, decode, cleanup or `Drop`, and assertions;
    caller-owned-probe-only regressions remain lock-free.

### align-llm adoption gate

After Request 7 reaches `ALIGN_MERGED` on top of its two named shipped prerequisites, align-llm owns
one immutable observable adoption checkpoint inside C6-LIFECYCLE. It may release-build and pin the
final Request 7 Align commit together with other merged prerequisites needed by that consumer; the
Request 6 and cleanup lifecycle entries retain their distinct commits. The existing C6 contract
already owns `c6-json-escape-adoption`, so no separate align-llm design pull request is required.
The implementation adds the focused target without placing the full qualification in
`HOSTED_CHECK_TARGETS`; it runs on pin changes and when this boundary changes, followed by the
capability's one final `make ci`. The same capability also checks in
`scripts/check-git-lazy-fetch-version` as the single version-parser
owner used by the hosted history preparation and the focused target, plus
`eval/fixtures/c6-json-escape-adoption/scanner-align-revision` and
`eval/fixtures/c6-json-escape-adoption/cleanup-align-revision`, each containing exactly its
lowercase 40-hex prerequisite commit plus one newline. Direct local and hosted qualification runs
execute the same adoption script. The gate requires each prerequisite lifecycle entry to equal its fixture file
while Request 7's lifecycle entry equals `.align-revision`.

Any hosted qualification checkout must make the prerequisite history available without moving the exact
detached Request 7 checkout. Before its first scripted inspection of that checkout, the
qualification workflow runs the checked-in `scripts/check-git-lazy-fetch-version` preflight
described below. The workflow's initial `git init`, remote configuration, exact validated-revision
fetch and detach, later unshallow fetch, and every HEAD/comparator operation all use one checked-in
wrapper around fixed `/usr/bin/git` under `env -i`, an empty `HOME`, the same system/global/XDG,
replacement, graft, lazy-fetch, optional-lock, hook, fsmonitor, and commit-graph exclusions as the
target, and `GIT_TERMINAL_PROMPT=0`. It rejects common-object-directory alternate files before and
after each object operation. No inline ambient `git` command is permitted. After `git init` and
remote configuration but before the initial fetch, the wrapper performs the effective
config-with-includes promisor query and requires no match. Every later object-capable wrapper call,
including the initial fetch, detach, HEAD resolution, comparator, and unshallow fetch, repeats both
the promisor and alternate-store guards before the command and after it; command output, status,
or side effects are not accepted after a failed postcheck. A persistent configuration race
therefore fails before the next object result is consumed. Concurrent set-and-remove mutation is
outside the controlled hosted-checkout contract.

Only after the initial fetch succeeds under those guards may the wrapper detach the validated
revision, again with a fresh precheck. After the version preflight, the workflow invokes the
comparator in an explicit
shallow-checkout mode that does not inspect parents. The comparator first performs the effective
promisor query, then resolves and includes `HEAD` in its canonical path, mode, type, object-ID, and
raw-worktree digest report. Only after that report succeeds does the wrapper run
`git fetch --no-tags --unshallow origin`. The workflow reruns the comparator and requires its
complete report, including `HEAD`, to be byte-identical. Neither observation uses porcelain status
or a Git content filter, and no HEAD object is resolved before the promisor and alternate-store
guards. If the repository is already complete, it performs no history-changing fetch. A
reference-transaction hook, repository-local alternate, and promisor fixture cover the initial
fetch, detach, both comparator calls, and unshallow fetch. The promisor fixture is installed after
remote configuration and must prove that no fetch, detach, HEAD, comparator-object, or remote
marker ran; every helper marker remains absent.

Before any target-side repository inspection, the adoption target runs the same version preflight.
That script's only ordinary-mode Git command is
`env -i PATH=/usr/bin:/bin LC_ALL=C git --version`. It requires exactly one output line matching
`git version MAJOR.MINOR.PATCH` with an optional dot-or-hyphen-prefixed ASCII alphanumeric vendor
suffix, parses all three decimal components without lexical comparison, and requires
`MAJOR > 2` or `MAJOR == 2 && MINOR >= 45`. Git 2.45 is the minimum because it introduced
`GIT_NO_LAZY_FETCH`; an older binary must fail before any `git -C`, worktree-status, config, or
object command. The hosted job prints the accepted version record before the history preparation.
Parser self-tests reject Git `2.44.4`, missing or non-decimal components, an extra line, and
unexpected text; they accept `2.45.0`, a permitted vendor suffix, and `3.0.0`. Its `--self-test`
mode also substitutes a `2.44.4` fixture executor with a repository-access marker and proves that
the marker remains absent. Neither production call accepts a caller-selected Git binary or version
text.

Synthetic version records test only the parser. Before any pin-changing adoption implementation
may start, the topology-ledger design must also name an immutable OCI image digest whose
`/usr/bin/git` is exactly Git `2.45.0` and whose remaining build toolchain satisfies the declared
hosted gate; a mutable tag or later `2.45.x` is not acceptance evidence. The Request 7 adoption
pull request adds a required
`git-2.45-compat` job that runs in that image, first requires the production preflight to print
exactly `git version 2.45.0`, and then executes the complete topology self-test, exact-checkout
revision check, `c6-json-escape-adoption` target, and every shallow, included/worktree promisor,
lazy-fetch, replacement, graft-race, raw-object, equality, and unrelated-ancestry negative through
the production scripts. It must not substitute version text or a different Git binary. The
ordinary Ubuntu job remains required separately. The immutable image digest and its build
provenance are sources of truth in the topology design. Its dependent implementation must make
the common topology tests pass in that image before any later adoption changes the pin; Request 7
then adds its feature-specific compatibility job.

```sh
export LC_ALL=C
git_version_capture="$(
  env -i PATH=/usr/bin:/bin LC_ALL=C git --version &&
    printf '%s' '__GIT_VERSION_END__'
)" || exit 1
case "$git_version_capture" in
  *'
__GIT_VERSION_END__') ;;
  *) exit 1 ;;
esac
git_version_record="${git_version_capture%
__GIT_VERSION_END__}"
if [[ "$git_version_record" =~ ^git\ version\ ([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})(((\.)|-)[[:alnum:].-]{1,64})?$ ]]; then
  git_major=$((10#${BASH_REMATCH[1]}))
  git_minor=$((10#${BASH_REMATCH[2]}))
  git_patch=$((10#${BASH_REMATCH[3]}))
else
  exit 1
fi
(( git_major > 2 || (git_major == 2 && git_minor >= 45) )) || exit 1
printf '%s\n' "$git_version_record"
```

The fixed non-newline sentinel preserves the command's output terminator before command
substitution can remove it. The suffix removal requires exactly one LF immediately before the
sentinel; the anchored C-locale regex then rejects any earlier or remaining LF, so missing,
additional, or blank output lines cannot normalize to an accepted record.

The topology-ledger update must also add one checked-in, binary-safe revision reader shared by the
canonical `.align-revision` path and the adoption fixture revisions. The reader accepts exactly one
explicit file path, reads the complete file as bytes without shell command substitution or text
decoding, requires exactly `[0-9a-f]{40}\n`, and only after that complete match writes the validated
40-byte lowercase ASCII revision. It never writes input-derived stdout on failure.
The hosted workflow also invokes the reader before its initial Align `git init` or fetch and uses
only that validated result; it no longer reads `.align-revision` with `tr`.
`scripts/check-align-revision`, which is already the first prerequisite of `align-build`, invokes
the reader again for `.align-revision`; a successful capture is safe because the helper can emit
only the already validated 40 ASCII bytes. Before resolving `ALIGN_REPO` or executing any Git or
Cargo command, the script independently requires the captured result to match
`[0-9a-f]{40}` and uses it as the expected revision. It no longer uses `tr -d '[:space:]'` or a
shell sentinel to validate persisted bytes. The helper's checked-in self-test supplies exact valid
bytes plus a NUL at every byte position, the especially dangerous
`<40-lower-hex><NUL><LF>` record, uppercase, short, missing-LF, extra-LF, space-, tab-, CR-, and
trailing-text variants through the production byte reader, with Git-access and build-output
markers; every invalid case must leave stdout and both markers absent. `make align-build` with
each class of temporary noncanonical revision fixture in an isolated repository copy must fail
before the release target directory changes. The scanner and cleanup fixture revisions remain
target-owned and do not select the compiler build, but the adoption target reads them through the
same helper before its first Git command.

After that version gate, the adoption target runs the exact-checkout revision script in an
empty environment that preserves only the validated absolute `ALIGN_REPO`, fixed `PATH` and
`LC_ALL`, disables system/global/XDG Git configuration, replacement objects, lazy fetch, and
optional locks, and supplies command-scope `core.fsmonitor=false` and
`core.hooksPath=/dev/null` and `core.commitGraph=false` overrides so hostile local configuration
cannot execute a helper or substitute derived ancestry:

```sh
env -i \
  PATH=/usr/bin:/bin \
  LC_ALL=C \
  ALIGN_REPO="$ALIGN_REPO" \
  GIT_CONFIG_NOSYSTEM=1 \
  GIT_ATTR_NOSYSTEM=1 \
  GIT_CONFIG_GLOBAL=/dev/null \
  GIT_NO_REPLACE_OBJECTS=1 \
  GIT_GRAFT_FILE=/dev/null \
  GIT_NO_LAZY_FETCH=1 \
  GIT_OPTIONAL_LOCKS=0 \
  GIT_CONFIG_COUNT=3 \
  GIT_CONFIG_KEY_0=core.fsmonitor \
  GIT_CONFIG_VALUE_0=false \
  GIT_CONFIG_KEY_1=core.hooksPath \
  GIT_CONFIG_VALUE_1=/dev/null \
  GIT_CONFIG_KEY_2=core.commitGraph \
  GIT_CONFIG_VALUE_2=false \
  XDG_CONFIG_HOME=/dev/null \
  scripts/check-align-revision
```

Within that boundary, the script treats the validated absolute `ALIGN_REPO` argument as the only
worktree root: it opens that exact directory with no-follow semantics before Git inspection and
never substitutes `rev-parse --show-toplevel`, `core.worktree`, or another Git-derived worktree
path for its retained root descriptor. After locating the exact root `.git` administrative entry
but before `rev-parse HEAD`, `cat-file`, status, tree, index-to-tree comparison, or any other object
inspection, `scripts/check-align-revision` first runs effective `git config --includes` queries
over repository and worktree configuration. It requires no promisor match and no `core.worktree`
value; a match rejects rather than being overridden. Its isolated environment excludes system,
global, XDG, replacement, alternate-object, and caller-selected Git state. Under the same boundary
it then requires `git rev-parse --is-inside-work-tree` to be exactly `true` and binary-safely
captures `git rev-parse --path-format=absolute --show-toplevel`; the complete path bytes must equal
the already validated absolute `ALIGN_REPO`. Missing, additional, or malformed output rejects.
Thus an explicit bare setting, linked-worktree-local redirect, included `core.worktree`, or other
Git/config disagreement cannot select a different filesystem root.

The script resolves the common object directory without reading a commit and rejects existing or
symlinked `objects/info/alternates` and `objects/info/http-alternates` before and after every
subsequent object operation; command output or status is consumed only after the postcheck. It then
fails closed when `git rev-parse --is-shallow-repository` is not exactly `false`; it never fetches
or changes the external repository.

The script does not use `git status`, `git diff`, checkout conversion, or any other operation that
may invoke clean/smudge/text-conversion filters. A checked-in binary-safe comparator first parses
the exact NUL-delimited outputs of `git ls-tree -r -z --full-tree HEAD` and
`git ls-files --stage -z`. It requires an exact path, mode, and object-ID match with only
stage-zero index entries. Tree mode `100644` or `100755` must name a `blob` and maps to a regular
index/worktree entry, `120000` must name a `blob` and maps to a symlink, and `160000` must name a
`commit` but is rejected because the pinned Align repository has no gitlinks; every other
mode/type pairing rejects.
Its ordinary and workflow shallow-checkout entry points both run the effective promisor query
before `ls-tree` or any other object read.
Before filesystem access the adoption comparator builds its own complete tree/index path trie:
relative nonempty paths, no empty, `.`, `..`, or ASCII-case-folded `.git` components, unique
entries, and no file/symlink prefix collision. It opens the worktree root once and enumerates the
entire filesystem beneath it with byte-path, dirfd-relative, no-follow operations. It never asks
Git which paths are untracked or ignored. Every filesystem directory other than the exact root
`.git` administrative entry and the allowed root `target/` output subtree must be an interior node
of the trie, and every other enumerated entry must map one-to-one to the corresponding tracked trie
leaf. The exact `.git` entry is excluded only after the script has resolved and validated the Git
and common directories; any other spelling whose ASCII fold is `.git`, any extra empty directory,
and any filesystem path absent from the trie rejects. The tree/index trie must contain no root
`target` component; otherwise the gate rejects rather than applying the output exception. Only
after that proof may the filesystem's root `target/` entry be absent or an ordinary non-symlinked
directory that this source comparator does not traverse.

Enumeration, descent, `lstat`, regular-file reads, and symlink-target reads all stay relative to
the already opened parent descriptors and use no-follow semantics. A disappearing entry, a type
change between enumeration and open, a rename-and-replace observation, an unsupported filesystem
type, or any inability to prove the one-to-one mapping rejects. Thus a raw malicious tree,
case-fold collision, or concurrent ancestor replacement cannot hide an input or redirect a read
outside the checkout. The same absolute, dot/dotdot/dotgit, duplicate, prefix-collision,
case-fold-collision, extra-directory, and symlink-ancestor raw-object and filesystem fixtures run
through the comparator and must reject without an outside-root read. Its tree-only symlink-chain
resolver rejects absolute, dangling, cyclic, root-escaping, or untracked targets before any later
Cargo or compiler command can follow them; fixtures cover both current valid Align symlinks and
every rejected class.

For every tracked leaf the comparator requires the indexed filesystem type and executable-bit
class, computes the repository's declared SHA-1 or SHA-256 Git blob ID directly over the raw bytes
without invoking Git filters, and matches that ID to the index object. Missing, additional,
unsupported, type-mismatched, mode-mismatched, or byte-mismatched entries fail. The comparator
never executes repository content or Git-configured helpers.

This comparator establishes one raw-filesystem observation; its retained root descriptor alone
does not bind separate `git -C "$ALIGN_REPO"` processes or a later Cargo build to that observation.
The adoption implementation must therefore use only the already installed common fresh-compiler
topology path. That prerequisite design and implementation must put every repository
config/object/index operation, raw enumeration, source materialization, and compiler build inside
one non-conflicting source-identity and mutation boundary. It must bind the exact root, Git
directory, common directory, and source bytes across their complete use; an ordinary pathname
re-resolution or matching pre/post `stat` observation is insufficient because ancestor, root, or
administrative paths can be replaced and restored between observations. Request 7 fixes the safety
outcome, not the mechanism. The common topology closure matrix must include an ancestor/root
rename-and-replace ABA fixture in which another repository has the same HEAD, tree, and index but
an additional recursively consumed Rust input; neither its Git state nor its source may be
accepted or built. A standalone successful comparator invocation cannot satisfy the adoption gate.

Before the raw comparison, `scripts/check-align-revision` also parses
`git ls-files -v -z` bytewise and rejects every lowercase tag (an `assume-unchanged` entry) and
every uppercase `S` tag (a `skip-worktree` entry); it does not clear either flag or refresh the
index. The raw filesystem enumeration above, not either form of
`git ls-files --others`, owns additional-path rejection. Thus repository `.gitignore`,
`.git/info/exclude`, repository-local `core.excludesFile`, and local `core.ignoreCase` cannot hide
a Cargo configuration, default `build.rs`, module source, case-fold-colliding Rust file, empty
directory, or other build input, while `.gitattributes`, `.git/info/attributes`, and local
`filter.*` configuration cannot normalize a tracked-byte comparison or execute a filter helper. A
regression creates
a depth-one detached checkout of the final commit,
proves that the gate fails before history expansion, expands its history, then proves the same
detached `HEAD` and clean worktree pass. Another regression supplies hostile system, global, XDG,
and local status/fsmonitor configuration plus an untracked file; a dedicated hostile local
`core.ignoreCase=true` case adds `crates/align_runtime/src/LIB.rs` beside tracked `lib.rs` and proves
that the raw enumeration rejects it even though both Git untracked queries omit it. Separate cases
set `core.worktree` directly and through linked-worktree configuration to an outside directory
containing a build-input marker, and set `core.bare=true`; each must reject before object lookup,
external-root enumeration, or marker execution. A raw-tree fixture with a tracked root `target`
component must reject rather than hiding that subtree behind the output exception. Separate cases
mark a tracked file `assume-unchanged` and `skip-worktree` and then change its bytes. Every case
must reject before build without invoking the helper, normalizing an index flag, or changing
index/object bytes or metadata. Additional cases hide an executable default `build.rs` and
`.cargo/config.toml` through `info/exclude` and a repository-local excludes file, add an untracked
empty directory, reject a symlinked root `target`, and accept only an ordinary `target/` output
sentinel. Separate cases use tracked `.gitattributes` and untracked `.git/info/attributes` plus
local clean filters that would make `git status` hide different working bytes; the raw comparator
must reject both without executing either filter marker. Index/tree mode, path, object-ID, stage,
regular-file, directory, symlink, executable-bit, raw-byte, unsupported-gitlink, SHA-1, and SHA-256
cases exercise every comparator decision. The rejected files and helpers must never execute. This
replaces
the current hosted workflow's depth-one-only behavior only in the future adoption capability.

An allowed ordinary root `target/` is treated only as unrelated prior output; no acceptance command
may execute or link an artifact from it. The reviewed Section 9 update to
`docs/specs/check-gate-topology.md` is merged. Before the next Linux x86_64 adoption or verification
that changes `.align-revision`, FRESH-WORKER must make canonical `make ci` consume that path and
refresh its identity-bound baseline, while FRESH-IMAGE must install and attest the host profile.
This is a repository-wide pin-transition prerequisite, not a Request 7-only helper: Request 6,
decoded-owner Request 15, Request 7, and any other request that would advance the x86_64 pin or claim
`ALIGN_LLM_VERIFIED` against a new compiler must wait for both capabilities; Request 6 must also
wait for FRESH-IMAGE-REQUEST6 before its focused adoption. A request with an aarch64 or macOS
acceptance environment must additionally wait for its named platform profile.
The plan, rather than this request register, owns the exact public inputs, bootstrap, commands,
statuses, timeout constants, process topology, cleanup algorithm, implementation modules, and
regression names for building and using a fresh pinned compiler outside `ALIGN_REPO`.

The topology plan must close all of these classes before code is written: creation and cleanup
authority for a private empty Cargo target; explicit trust and mutation semantics for every
bootstrap, executable, source, compiler, and cache input before its first possible side effect;
fully no-follow cache and output containment; offline dependency use; identity enforcement at the
actual granularity of every compiler execution, including invocations below Make; ownership,
termination, escalation, and reap of probe, build, aggregate, and escaped descendant processes;
PID and process-group reuse; signal arrival during every construction and active-process window;
bounded monotonic shutdown; one source-identity boundary spanning Git, raw enumeration,
materialization, and build despite ancestor/root/Git-directory/common-directory
rename-and-replace or ABA races; deterministic error precedence; and fail-closed cleanup that
cannot delete an unowned path or race a surviving writer. Its closure matrix must cover success,
every phase failure, timeout, exhaustion, and cleanup failure under both local `make ci` and the
hosted serialized aggregate, and must name exact negative and integration tests for each cell.

The fresh-compiler successor redesign is merged as Section 9 of
`docs/specs/check-gate-topology.md`. The re-scoped design separates the image-owned supervisor and
bootstrap plane from the per-reviewed-head repository worker: the fixed image manifest authenticates
only image tools/runtime, while a signed run capsule binds the checked-out head and current worker
digest. It adds the exact DSSE wire contract and golden hashes, env-scrubbed fd-4/5/6 pre-bootstrap
boundary with sealed worker/manifest/run snapshots at fd-7/8/9, worker enforcement of the signed
project HEAD/object-format identity, descriptor-relative one-root admission lock outside `/tmp`,
bounded source-fd window, fail-closed orphan policy, executable-`/tmp` requirement,
process/fd/inode/Git-object/root bounds, complete Make-option rejection, explicit output-exception
metadata, and phase-5 Cargo-config ownership while retaining the earlier source, cache, runtime,
output, and read-only bundle decisions. Its reviewed wire and source-identity foundations are also
merged. FRESH-WORKER and FRESH-IMAGE must now complete their respective repository and host-profile
capabilities before pin-changing verification consumes the contract. Request 7 must consume the
merged contract exactly; its separate Git 2.45.0
image and C7 non-x86 platform profiles remain independent prerequisites.

The target validates all three revision files' exact encoding, disables replacement objects and
ambient Git configuration, requires raw commit objects rather than peelable tags, and then proves
external-repository reachability with:

```sh
clean_git() {
  env -i \
    PATH=/usr/bin:/bin \
    LC_ALL=C \
    GIT_CONFIG_NOSYSTEM=1 \
    GIT_ATTR_NOSYSTEM=1 \
    GIT_CONFIG_GLOBAL=/dev/null \
    GIT_NO_REPLACE_OBJECTS=1 \
    GIT_GRAFT_FILE=/dev/null \
    GIT_NO_LAZY_FETCH=1 \
    GIT_OPTIONAL_LOCKS=0 \
    XDG_CONFIG_HOME=/dev/null \
    git \
      -c core.fsmonitor=false \
      -c core.hooksPath=/dev/null \
      -c core.commitGraph=false \
      "$@"
}

align_scanner_revision="$(
  scripts/read-exact-revision \
    eval/fixtures/c6-json-escape-adoption/scanner-align-revision
)"
align_cleanup_revision="$(
  scripts/read-exact-revision \
    eval/fixtures/c6-json-escape-adoption/cleanup-align-revision
)"
align_request7_revision="$(scripts/read-exact-revision .align-revision)"
[[ "$align_scanner_revision" =~ ^[0-9a-f]{40}$ ]]
[[ "$align_cleanup_revision" =~ ^[0-9a-f]{40}$ ]]
[[ "$align_request7_revision" =~ ^[0-9a-f]{40}$ ]]

partial_clone_status=0
clean_git -C "$ALIGN_REPO" config --includes --name-only --get-regexp \
  '^(extensions\.partialclone|remote\..*\.(promisor|partialclonefilter))$' \
  >/dev/null 2>&1 || partial_clone_status=$?
test "$partial_clone_status" = 1
test "$(clean_git -C "$ALIGN_REPO" rev-parse --is-shallow-repository)" = false
align_common_record="$(
  clean_git -C "$ALIGN_REPO" rev-parse --path-format=absolute --git-common-dir &&
    printf '%s' '__ALIGN_COMMON_DIR_END__'
)" || exit 1
case "$align_common_record" in
  *'
__ALIGN_COMMON_DIR_END__') ;;
  *) exit 1 ;;
esac
align_common_dir="${align_common_record%
__ALIGN_COMMON_DIR_END__}"
case "$align_common_dir" in
  /?*) ;;
  *) exit 1 ;;
esac
case "$align_common_dir" in
  *[[:cntrl:]]*) exit 1 ;;
esac
test ! -e "$align_common_dir/info/grafts"
test ! -L "$align_common_dir/info/grafts"

reject_alternates() {
  if [[ -e "$align_common_dir/objects/info/alternates" ||
        -L "$align_common_dir/objects/info/alternates" ||
        -e "$align_common_dir/objects/info/http-alternates" ||
        -L "$align_common_dir/objects/info/http-alternates" ]]; then
    return 1
  fi
  return 0
}

clean_object_git() {
  reject_alternates || return 1
  object_status=0
  clean_git "$@" || object_status=$?
  reject_alternates || return 1
  return "$object_status"
}

scanner_type="$(
  clean_object_git -C "$ALIGN_REPO" cat-file -t "$align_scanner_revision"
)" || exit 1
cleanup_type="$(
  clean_object_git -C "$ALIGN_REPO" cat-file -t "$align_cleanup_revision"
)" || exit 1
request7_type="$(
  clean_object_git -C "$ALIGN_REPO" cat-file -t "$align_request7_revision"
)" || exit 1
test "$scanner_type" = commit
test "$cleanup_type" = commit
test "$request7_type" = commit
test "$align_scanner_revision" != "$align_cleanup_revision"
test "$align_scanner_revision" != "$align_request7_revision"
test "$align_cleanup_revision" != "$align_request7_revision"
clean_object_git -C "$ALIGN_REPO" merge-base --is-ancestor \
  "$align_scanner_revision" \
  "$align_request7_revision"
clean_object_git -C "$ALIGN_REPO" merge-base --is-ancestor \
  "$align_cleanup_revision" \
  "$align_request7_revision"
```

Before these commands, `scripts/read-exact-revision` performs the same complete binary-safe match
for each file and emits only a validated revision; shell capture is extraction after validation,
not persisted-byte validation. Its embedded-NUL matrix is exercised for all three call sites.
The earlier exact-checkout script performs the displayed effective config-only promisor query
before its own first object inspection. The adoption target repeats it here immediately before
the ancestry object's shallow, type, and parent reads, so a configuration change between the
checkout check and ancestry gate still fails closed. Both query placements are object-free.
Every command must return zero before any adoption fixture executes. The adoption smoke includes
isolated negative copies of this gate
proving rejection of a shallow repository, a symbolic or annotated-tag object, a replacement
object that would forge ancestry, a Git-common-dir `info/grafts` entry that would forge ancestry, a
graft-race case that creates or replaces that file after the path-absence checks but before the
ancestry calls, ordinary and symlinked `objects/info/alternates` and `http-alternates`, a persistent
alternate-file race between each precheck and object command, a standard partial clone with a
missing prerequisite object, equal prerequisite/final revisions, equal prerequisite revisions,
and valid but unrelated commit objects. The graft-race case proves every `clean_git` command uses
the empty `/dev/null` graft
source and therefore ignores the raced repository file; the forged ancestry must still fail
without a fetch, object write, or index change. Each alternate race may make the isolated object
command run, but the postcheck must reject before consuming its result, executing a fixture, or
claiming success. Concurrent create-and-remove mutation is outside the otherwise-idle external
checkout contract. The partial-clone case sets a
local access marker as its promisor remote, snapshots the object database and index bytes, and must
reject the actual `remote.<name>.promisor` / `remote.<name>.partialclonefilter` configuration before
`cat-file` or `merge-base`, without contacting the remote, creating an object, or changing the
index. Separate negatives cover the legacy extension key and mixed-case remote subsections. A
repository-local `include.path` negative places the promisor keys only in the included file and
proves that included configuration is still rejected. A linked-worktree negative enables
`extensions.worktreeConfig` and places the promisor keys only in that worktree's
`config.worktree`; it must also reject before object access. Thus the query covers all effective
repository-local and worktree configuration after the empty environment has excluded system,
global, XDG, and command-scope inputs. A separate clean-checkout regression makes the index stat
cache eligible for refresh and proves the exact revision check plus every ancestry command leaves
its index bytes and metadata unchanged under `GIT_OPTIONAL_LOCKS=0`. The common-dir capture
appends a fixed non-newline sentinel before shell command
substitution can discard Git's output terminator, requires exactly one LF immediately before that
sentinel, removes only that exact suffix with shell parameter expansion, and then requires a
non-root absolute path containing no control byte. The negative matrix includes a valid separate
Git common directory whose basename ends in LF and whose `info/grafts` would forge the requested
ancestry; it must be rejected before either ancestry command. Thus command substitution cannot
normalize a malicious path into a different graft-check location. Any existing or symlinked graft
path is also rejected before either ancestry command. Those path checks are fail-fast
defense-in-depth; `GIT_GRAFT_FILE=/dev/null` is the race-free ancestry boundary and remains set for
every `cat-file` and `merge-base` invocation. The negative repositories and Git configuration must
not affect the caller's repository. A cherry-pick, squash, or joint commit that
merely reproduces either prerequisite's content without preserving both named commits as strict
ancestors is rejected. The target then runs
`scripts/run-c6-json-escape-adoption-smoke` against checked-in
`eval/fixtures/c6-json-escape-adoption/`.
That directory owns `main.align`, `escape-heavy.input.json`, and
`escape-heavy.expected.json`. The script creates its malformed and outside-arena cases bytewise in
its validated temporary directory so a host JSON parser cannot normalize the test input first.

The fixture declares:

```align
EscapeLeaf { text: str, note: Option<str>, parts: array<str> }
EscapeRow { id: str, leaf: EscapeLeaf }
EscapeEnvelope { schema_version: i64, artifact_kind: str, rows: array<EscapeRow> }
```

Its escape-heavy input bytes are exactly:

```json
{"schema_version":1,"artifact_kind":"C6_JSON_ESCAPE_GATE","r\u006fws":[{"id":"row-1","leaf":{"text":"quote:\" slash:\/ backslash:\\ controls:\b\f\n\r\t","note":"\u20ac","parts":["","nul:\u0000","emoji:\ud83d\ude00"]}}]}
```

Inside an arena, decode must produce the semantic quote, slash, backslash, five control characters,
euro sign, embedded NUL, and grinning-face UTF-8 bytes. Re-encoding must produce exactly these bytes
followed by the newline written by `print`:

```json
{"schema_version":1,"artifact_kind":"C6_JSON_ESCAPE_GATE","rows":[{"id":"row-1","leaf":{"text":"quote:\" slash:/ backslash:\\ controls:\b\f\n\r\t","note":"€","parts":["","nul:\u0000","emoji:😀"]}}]}
```

The same target also proves: a clean record round-trips unchanged; a returned escaped declared field
outside an arena is `Error.Code(1)`; an escaped declared key and valid escaped ignored value work
outside an arena; literal/escaped duplicate semantic keys, raw C0, malformed short escapes,
malformed surrogates, and a mid-nested-Move-record-array failure are rejected; missing and `null`
note both decode as `None`; and a subsequent clean decode succeeds. Pointer provenance and exact
deep cleanup remain compiler/runtime-instrumented Align acceptance items 4 and 6 rather than claims
made by this public-client fixture. Only this named target plus `make ci` may advance Request 7 to
`ALIGN_LLM_VERIFIED`. Broader C6 artifact vectors belong to the later committed C6 design. The
product slice starts only after every other separately registered JSON prerequisite is also
`ALIGN_LLM_VERIFIED`.

### References

- `../align/docs/impl/core-design/json.md` — authoritative declared JSON design and current escape
  limitation.
- `../align/crates/align_runtime/src/lib.rs` — typed string decode and `json.doc` unescape paths.
- `../align/crates/align_driver/tests/m5.rs` — declared-record JSON and differential regressions.
- `../align/bench/json_decode` and `../align/bench/json_soa` — clean-input parser regression
  tripwires.
- `docs/specs/roadmap.md` and `docs/specs/align-llm.md` — committed C6 consumer and architecture;
  the merged detailed C6 design owns the prerequisite and consumer checkpoints.

---

## Request 8 — `core.array_builder`: runtime construction of declared-record arrays

```text
Status: CLOSED
Priority: high
Blocking: yes
Blocked gate or slice: C6f2 deterministic paired evaluator and C6c2 decoded evaluation verifier; Request 8 supplies the recursively Copy, owned-record base needed by Request 10's evaluator extension, and C6c2 cannot consume its runtime-sized declared-record result arrays until the named real-client adoption and shared consumer pin wave pass
Independent work that may continue: C6c2 design and other application designs, pure codecs, renderers, scorers, activation slices, Request 5, Request 6, Request 7, and any implementation that does not construct a runtime-sized declared-record array
Resume condition: satisfied by the C6-LIFECYCLE pin wave and Align-llm PR #94; the later C6c2 verifier still owns its separate `c6f2-array-builder-adoption` consumer evidence
Align commit or pull request: Align design PR #799, merged as `60622c60a4fc21b8586e1f6a907c32c025aa1658`; implementation PR #801, merged as `029e27465d79e24cd36d374aae41dca0ec7e6979`
align-llm verification: PR #94 merged as `ba56ebed5ac1c82ebc5925e6257e7bd5dba8a9b9`; ordered `c6c2-request8-adoption` passed against `.align-revision` `a440970ac81118ed2169f600b2b3c06fcb9cde7`, and final capable `make ci` passed in CI run `32109434515` at head `954258e24d93300dcdb78f8280de8868cf1ced56`; merge run `32111007638` reused the exact evidence
```

The shipped contract is the individually owned heap-record builder design in Align
`docs/impl/17-library-boundary-prerequisites.md` §7.5 and its checked-HIR rows in
`docs/impl/19-hir-validation-ledger.md`, merged by Align PR #799 and implemented by PR #801.
`ALIGN_MERGED` records the producer capability only; align-llm does not consume the surface until
the named real-client adoption target passes on the consumer capability branch.

### Motivation

A future data-oriented evaluator may discover result cardinalities while it reads a fixed corpus and
runs paired samples. It must construct arrays of declared records, possibly with nested declared
records, and those arrays must remain ordinary Align values with explicit ownership. They cannot be
replaced by a dynamic JSON value tree or by a private application vector. The first concrete
consumer must name its exact record shapes in its authoritative design before it consumes the
surface or this request reaches `ALIGN_LLM_VERIFIED`; that design may be reviewed with the consumer
implementation.

This request targets the existing individually owned heap-builder form. Any record inserted into
that form must use owned `string` for persistent text and must not carry a `str`, `slice`,
`resource_ref`, or other borrowed view, directly or through a nested field or array. A consumer must
materialize such text before pushing it. Borrowed fields are owned by the separate explicit-region
`array_builder(out)` / `RegionPlain` design in Align §7 and are not silently folded into this heap
request.

Request 8 deliberately does not admit a dynamic-array field inside a builder element. The pinned
`DropPlan` and builder storage treat dynamic arrays as opaque element payloads, so accepting one
without a separately reviewed recursive layout would be a shallow-copy hole. A future request may
define a dynamic-array field, but it must specify its element predicate and deep cleanup before a
consumer names it as a prerequisite. Request 8 does not ship a JSON codec, a wire DTO, or an
implicit conversion between `array<string>` and `array<str>`.

The existing pipeline terminal `.to_array()` is a compiler-defined collect lowering for a
pipeline-supported element shape, including some whole Copy-record shapes: it allocates from the
source's upper bound and fills survivors in a fused loop. It is not a general mutable append
operation for records assembled by arbitrary evaluator control flow, and the pinned pipeline
surface still restricts broader Move-element and nested/owned whole-record collection shapes. A
fixed array literal has the same limitation for runtime cardinality. A consumer must not build a
second hidden collection abstraction or serialize JSON fragments and parse them back as a
compatibility workaround.

### Current-state evidence at the pinned Align revision

The align-llm pin is `25b1201b3a4181f6a90921227596bdcb76ab715e` (#786), verified in the sibling
Align checkout on 2026-08-14:

- `core.array_builder` is represented as `Ty::ArrayBuilder(Scalar)`. The `resolve_type` branch for
  the `"array_builder"` type restricts its element to Copy primitive scalars or owned `string`;
  `check_array_builder_new` only validates the no-argument constructor and expected-type inference.
  A declared record, `array<Struct>`, `Option<Struct>`, or a nested dynamic array is rejected before
  construction.
- `push` and `append` lower through scalar/string-specific MIR operations. The runtime builder
  stores a raw byte buffer and knows how to move a top-level `string` element, but it has no
  producer-owned element `DropPlan` for recursively dropping a declared record after a partial
  push, builder abandonment, or array destruction.
- `build()` freezes the scalar/string buffer into an owned array. The existing JSON surface can
  decode `array<Struct>` and deep-drop Move elements, but that decode path does not expose an
  appendable builder for records discovered by a loop.
- Struct formation admits some dynamic-array fields but the pinned pass-0b-2 declaration check
  rejects `array<string>` because its per-element deep free is not shipped. `is_field_ok` and the
  current `DropPlan` therefore cannot form arbitrary owned text-array fields. A future consumer must
  register that JSON/type capability separately; Request 8 must not claim it is already available or
  silently replace it with a shallow array.
- `array_builder(out)` and the recursive `RegionPlain` contract are shipped at the pinned revision.
  That explicit-region form accepts view-bearing plain records, grows in caller-owned region chunks,
  and compacts once at `build`; it deliberately excludes independently owned `string` fields and
  dynamic owned arrays. Request 8 therefore owns only the missing individually owned heap-builder
  capability for view-free records containing free-standing `string`, and does not revise the
  shipped region form.

This was a language/compiler/runtime ownership gap, not an align-llm application concern. The
capability is shipped in Align, but the current align-llm pin predates it; align-llm must not write
consumer code against the constructor or element type before the named adoption checkpoint.

### Requested capability

Extend the existing heap `core.array_builder` contract without adding expression-position type
arguments or a second collection API:

```text
array_builder<T>()       // signature notation; T is inferred from the annotated binding
b.push(value: T)         // mut receiver; consumes a Move value when T is Move
b.append(xs: slice<T>)   // available only when T is an existing Copy scalar
b.build() -> array<T>    // consumes the builder
```

The first line is contract notation, not a request for expression-position type arguments. The
actual Align expression remains `array_builder()` and the element type is supplied by the
annotated binding, as in the existing scalar/string form.

The source idiom remains the existing expected-type form:

```align
ScalarRecord { id: i64, active: bool }

fn collect(n: i64) -> array<ScalarRecord> {
  mut b: array_builder<ScalarRecord> := array_builder()
  mut i := 0
  loop {
    if i >= n { break }
    b.push(ScalarRecord { id: i, active: true })
    i = i + 1
  }
  return b.build()
}
```

This example is deliberately a Copy record with scalar-only fields. The separate Move acceptance
case uses `OwnedRecord { id: i64, name: string }` and proves owned-string source nulling,
reallocation, and recursive cleanup; it is not counted as a Copy-record case.

The implementation may choose its internal storage representation, but the public ownership
predicate and existing nominal builder/interface identity described in item 8 are fixed:

1. The accepted heap element predicate is closed and recursive. Define `HeapRecord(S)` as true only
   when `S` is a non-empty, acyclic declared record and every field is one of the current Copy scalar
   types (`Int`, `Float`, `Bool`, or `Char`), `string`, or another record `R` for which
   `HeapRecord(R)` is true. A field graph is finite, every accepted record has its compiler-computed
   natural alignment at most 8 bytes, and no accepted record or reachable field type has an explicit
   `align(N)` or `layout(C)` attribute; either attribute is rejected even when its alignment would be
   at most 8. The new record builder accepts `T = S` exactly when `HeapRecord(S)` is true. The
   existing scalar and `string` builder forms remain unchanged. Dynamic arrays, `Option`, sums/enums,
   empty records, and every other aggregate are rejected as fields before construction; a future
   request must define each such recursive shape and its deep cleanup separately. This predicate is
   the complete `DropPlan` boundary for Request 8, not a promise to accept any type whose opaque
   `DropPlan` happens to exist.
   A top-level or nested `str`, `slice`, `resource_ref`, resource, raw value, function value, another
   builder, or an over-aligned record is rejected before the builder is constructed.
   Region and borrow-generation handling for view-bearing `RegionPlain` elements is N/A here: those
   elements belong to the explicit-region `array_builder(out)` form and are not accepted by this
   heap form.
2. `push` borrows the builder's mutable handle and consumes the complete element value when it is
   Move. The source is nulled at the move boundary. Copy elements retain Copy semantics. There is
   no implicit clone, per-element hidden arena, or JSON-specific insertion path.
3. The heap builder payload and the built `array<T>` are free-standing allocations. For a Move
   record, `FreeStanding(e)` is true only when every reachable `string` owner in the pushed value
   has no arena/region provenance and the compiler can prove that fact at the push expression;
   Copy fields contribute no allocation mode. An arena-owned, mixed-mode, or unknown/path-dependent
   nested owner is rejected before the push side effect. The ownership carrier records this mode
   alongside the structural `DropPlan`, so `build` cannot turn an arena child into a free-standing
   child by merely relocating bytes.
4. Reallocation may relocate the raw element bytes, but it must not run `Drop` on a transient byte
   copy or lose ownership of a live nested pointer. The builder retains the producer-owned
   structural element descriptor, allocation-mode decision, and initialized-element count needed
   for cleanup.
5. Dropping an unbuilt builder drops every initialized element with the canonical recursive
   `DropPlan` and then frees the builder storage. `build()` consumes the builder and transfers the
   initialized storage to `array<T>` without a second element allocation; the resulting free-standing
   array's normal deep `Drop` owns every element exactly once.
6. Partial element construction, early `return`, `?`, `map_err`, branch joins, loop back-edges,
   malformed-input exits, replacement/reassignment, and construction of an enclosing record that
   contains the resulting array must retain or release each already-live element exactly once. A
   failed or abandoned operation must not return a partially initialized array as a successful
   value.
7. `append` remains a bulk-copy operation only for Copy scalar elements. It must not silently
   shallow-copy a Move record or a view-bearing element. A record-element builder uses the same
   one-owner transfer rules as the existing scalar and owned-`string` builders: passing or returning
   it by value moves the sole builder owner and its boxed header, while `borrow mut` permits only a
   checked, non-consuming helper use and `build` consumes the owner. Replacing a builder drops the
   old storage before installing the new owner. A builder still cannot be stored in an aggregate,
   captured, sent to a task, or put in `Option`/`Result`, and an append of record elements remains
   rejected. Request 8 adds no record-only placement state or exception to the existing builder
   contract. The exact forwarding, return, mutable-borrow, and boxed-header behavior must be
   consistent for scalar, owned-`string`, and record element types.
8. The builder retains Align's existing nominal producer-item identity. A record specialization is
   represented by the existing `array_builder<Struct>` type/interface graph and maps to the ordinary
   owned `array<Struct>` result; Request 8 does not add a standalone record-builder descriptor,
   second wire identity, runtime reflection table, or type dictionary. The complete reachable
   substituted record definition graph, including declaration-order fields, layout, allocation
   mode, and recursive `DropPlan` facts, must already participate in the versioned producer
   interface, monomorphization identity, and codegen cache key. Local and imported/per-unit builds
   must resolve the same nominal graph. An element-definition edit, field reorder, field name/type/
   layout/drop-plan change invalidates the identity and codegen cache, while reverting the edit
   restores it. Malformed, unresolved, cyclic, stale, or producer/consumer-incompatible interface
   references reject through the existing interface validation before HIR or codegen. No
   builder-specific byte schema is part of this request.
9. The shipped explicit-region builder remains separate. Request 8 does not make heap allocation
   implicit, revise `array_builder(out)`, or broaden `RegionPlain` or package generic syntax as an
   incidental implementation shortcut.

The exact acceptance diagnostics may follow Align's naming conventions, but validation order is
deterministic and no builder allocation or push-side effect occurs before it completes:

| Order | Validation |
| --- | --- |
| 1 | Existing parser/import/arity diagnostics and expected-type inference for `array_builder()` |
| 2 | Canonical recursive type formation: unresolved/cyclic definitions, over-alignment, reachable views, unsupported resources/raw/functions/builders, and missing `DropPlan` |
| 3 | Existing builder ownership and receiver mode: by-value parameter/return moves the sole owner, `borrow mut` is non-consuming, and aggregate/`Option`/`Result`/capture/task placement remains rejected |
| 4 | At `push`, source move state and exact element-type compatibility, followed by recursive allocation-mode validation; an arena, mixed, or path-dependent owned child is rejected before growth |
| 5 | `build` transfer and ordinary array escape/cleanup validation; scalar/string compatibility paths retain their existing boxed-header behavior |

The same order and first-diagnostic rule applies to whole-program, imported/per-unit, and cache
replay checking. A valid view-free declared record must not be rejected merely because it is a
record rather than a primitive scalar; a view-bearing or over-aligned record must be rejected as a
heap-builder element before construction.

### Ownership closure matrix

Align's reviewed design keeps the canonical implementation closure matrix in
`../align/docs/impl/17-library-boundary-prerequisites.md` §7.5. This register is the align-llm
acceptance summary: it records the required coverage, owner symbols, and regression names so
adoption can verify the shipped capability, but it does not replace the sibling repository's plan
or claim authority over Align implementation order. The Align implementation must map its final
diff and evidence to that canonical matrix; if a boundary changes, the Align design and this request
entry must be updated together.

| Case | Exact owner | Exact regression |
| --- | --- | --- |
| `array_builder<T>` formation and expected-type inference | `../align/crates/align_sema/src/lib.rs` `resolve_type`/`check_array_builder_new` and the new recursive heap-element eligibility check | `m12_array_builder.rs::record_builder_type_formation_and_inference`, `record_builder_field_predicate_rejects_closed_shapes`, and `record_builder_view_and_layout_rejected_before_construction` cover valid Copy/Move records, generic substitution, missing expected type, and every closed field/view/cycle/empty/layout/alignment exclusion before construction |
| Heap-form view exclusion and region-builder boundary | `../align/crates/align_sema/src/lib.rs` `resolve_type`/`check_array_builder_new`; the related explicit-region owner is Align §7 | `m12_array_builder.rs::record_builder_view_and_layout_rejected_before_construction` rejects direct and nested views and explicit/over-aligned layout, while `align_attr.rs::an_aligned_struct_as_a_field_or_dynamic_array_element_is_rejected` remains the aligned dynamic-array baseline |
| Copy record push/build | `../align/crates/align_mir/src/lib.rs`, `../align/crates/align_codegen_llvm/src/lib.rs`, and `../align/crates/align_runtime/src/lib.rs` | `m12_array_builder.rs::copy_record_push_build_zero_one_many_and_realloc` checks a scalar-only Copy record's exact fields and the run result |
| Move record push/source nulling | `../align/crates/align_sema/src/lib.rs` MoveCheck and `../align/crates/align_mir/src/lib.rs` push lowering | `m12_array_builder.rs::record_builder_move_source_matrix` parameterizes bound locals, fresh literals, function results, transparent block tails, value-carrying `if`/`match`/`else`, and successful `?`/`map_err(...)?`, plus every rejected borrowed, projected, divergent, consumed, arena, mixed, or non-fallthrough twin |
| Recursive nested-record `DropPlan` and closed field predicate | `../align/crates/align_sema/src/lib.rs` structural type walk, source-cycle check, natural-layout/representation check, and DropPlan plus `../align/crates/align_codegen_llvm/src/lib.rs` recursive drop lowering | `owned_structs.rs::record_builder_nested_move_drop_plan` observes nested-owner frees on success and partial construction; `m12_array_builder.rs::record_builder_field_predicate_rejects_closed_shapes` proves every excluded aggregate is rejected before construction, while the view/layout formation test closes the non-tree layout boundary |
| Nested owner allocation mode | `../align/crates/align_sema/src/lib.rs` `EscapeCheck::drop_is_individual`/`drop_may_be_individual`, `MoveCheck::expr`, and `../align/crates/align_mir/src/lib.rs` ownership carrier | `owned_structs.rs::record_builder_rejects_arena_or_mixed_nested_owners` rejects arena-owned, mixed-mode, and path-dependent nested owners before push side effects |
| Partial element construction | `../align/crates/align_mir/src/lib.rs` aggregate cleanup edges | `m12_array_builder.rs::record_builder_partial_element_failure_drops_fields` checks a failed element after an earlier push |
| Builder abandonment before `build` | `../align/crates/align_mir/src/lib.rs` cleanup insertion and `../align/crates/align_runtime/src/lib.rs` builder drop | `m12_array_builder.rs::record_builder_abandonment_all_exit_kinds` is parameterized over stack-local and boxed headers and covers normal exit, early return, `?`, `map_err`, branch/match/else joins, loop back-edge/break, malformed input, and leak/double-free counters |
| Reallocation of live nested owners | `../align/crates/align_runtime/src/lib.rs` builder growth and relocation | `m12_array_builder.rs::record_builder_realloc_preserves_nested_owners` checks values and exactly-once frees |
| `build` transfer and returned array cleanup | `../align/crates/align_mir/src/lib.rs` move-out plus ordinary array `Drop` | `m12_array_builder.rs::record_builder_build_transfer_and_array_drop` is parameterized over stack-local and boxed headers and covers return, consume, unused, exact buffer transfer, applicable header disposal, and no duplicate builder cleanup |
| Builder replacement/reassignment and builder-state reset | `../align/crates/align_sema/src/lib.rs` assignment/drop classification and `../align/crates/align_mir/src/lib.rs` `drop_old` | `m12_array_builder.rs::record_builder_reassignment_drops_old_storage` extends the existing `reassignment_frees_old_string_builder` guard and proves the replacement has fresh ownership/placement state; borrow roots are N/A because heap elements reject reachable views |
| Enclosing record construction failure | `../align/crates/align_mir/src/lib.rs` aggregate/source cleanup | `owned_structs.rs::record_builder_enclosing_record_failure` checks a built nested array followed by a failing sibling and branch join |
| `if`/`match`/`else`/`?`/`map_err` joins and loop back-edges | `../align/crates/align_sema/src/lib.rs` Move/Drop analysis and `../align/crates/align_mir/src/lib.rs` cleanup CFG | `region_flow.rs::record_builder_join_cleanup_matrix` covers built and abandoned paths |
| Record-builder transfer, capture exclusion, and `borrow mut` | `../align/crates/align_sema/src/lib.rs` move/placement/capture checks and the existing borrow checker contract; `../align/crates/align_codegen_llvm/src/lib.rs` boxed-header boundary | `m12_array_builder.rs::record_builder_by_value_parameter_return_and_borrow_mut` proves one-owner forwarding, return, and non-consuming mutable borrow; `record_builder_invalid_storage_and_capture` rejects aggregate/`Option`/`Result`/capture/task placement and consuming a borrowed builder; scalar/string compatibility remains covered by `capture_into_spawn_rejected`, `capture_into_par_map_rejected`, `escaping_array_builder_keeps_boxed_header`, and `array_builder_crossing_user_call_stays_boxed` |
| Deterministic validation precedence | `../align/crates/align_sema/src/lib.rs` `resolve_type`, `check_array_builder_new`, `check_array_builder_push`, `MoveCheck::expr`, and `EscapeCheck::walk_array_builder` | `m12_array_builder.rs::record_builder_validation_precedence_local_and_imported`, `per_unit.rs::record_builder_validation_precedence_parity`, and `cache_codegen.rs::record_builder_validation_precedence_cache_replay` cover multi-invalid local/imported/per-unit/cache diagnostics and first-error parity |
| Generic monomorphization and imported interface | `../align/crates/align_sema/src/lib.rs` type substitution, `../align/crates/align_mir/src/lib.rs` graph collection, and `../align/crates/align_driver/src/lib.rs` interface emission | `generics.rs::record_builder_generic_instantiation` plus `per_unit.rs::record_builder_imported_interface_graph` checks local/imported parity |
| Nominal identity and codegen cache | `../align/crates/align_driver/src/lib.rs` existing nominal interface graph and cache identity | `cache_codegen.rs::record_builder_nominal_identity_and_definition_edit_revert` proves two same-shape records with different declaration identities remain distinct, then checks the existing versioned interface identity, cold hit, definition edit miss, revert identity, and malformed/stale/unresolved graph-reference rejection without a builder-specific descriptor |
| Interface ABI and recursive cleanup completeness | `../align/crates/align_driver/src/lib.rs` existing interface serialization and `../align/crates/align_codegen_llvm/src/lib.rs` nominal struct layout/DropPlan resolution | `interface_param_modes.rs::record_builder_interface_drop_plan` rejects a producer/consumer record-layout or recursive cleanup-contract mismatch before HIR/codegen |
| Checked-HIR formation, push, and build | `../align/crates/align_mir/src/validate_hir.rs` using the same canonical heap-record classifier as Sema | `align_mir::validate_hir_tests::heap_record_array_builder_rows_match_the_producer` parameterizes valid and malformed `ArrayBuilderNew`, `ArrayBuilderPush`, and `ArrayBuilderBuild` rows, including record-id/predicate/move-bit/AoS-result mutations before MIR allocation or transfer |
| Allocation and byte ownership | `../align/crates/align_runtime/src/lib.rs` allocation/growth/build plus codegen ownership flags | `m12_array_builder.rs::record_builder_allocation_transfer_instrumentation` checks allocation counts, sanitized execution, and no duplicate element buffer |
| Builder concurrency and overlap exclusion | `../align/crates/align_sema/src/lib.rs` local placement/capture checks and `../align/crates/align_runtime/src/lib.rs` instance-local state | `m12_array_builder.rs::record_builder_same_instance_alias_rejected` proves a second operation on the same builder cannot be represented or start; `record_builder_two_instances` proves two distinct builders and aggregate-plus-aggregate/aggregate-plus-focused calls are independent; `cache_parallel.rs::record_builder_two_processes` covers independent processes |
| Capacity overflow | `../align/crates/align_runtime/src/lib.rs` checked capacity arithmetic | `m12_array_builder.rs::record_builder_capacity_overflow_terminal_child` verifies the existing terminal overflow policy and no successful partial array |
| Allocator failure | `../align/crates/align_runtime/src/lib.rs` allocator boundary and the Align test-only child-process failpoint | `m12_array_builder.rs::record_builder_allocator_failure_terminal_child` injects failure at header and growth allocation, proves non-zero terminal exit and no successful partial result, and makes no post-abort cleanup claim |
| Existing scalar/string and JSON regressions | `../align/crates/align_runtime/src/lib.rs` compatibility paths and `../align/crates/align_driver/tests/m12_array_builder.rs`/`m5.rs` | `m12_array_builder.rs::i64_push_build_then_pipeline_sum`, `string_push_build_len_and_deep_drop_cycles`, and `reassignment_frees_old_string_builder`, plus `m5.rs::json_decode_struct_array_len` and `json_decode_struct_array_malformed_errors`, remain green |

The matrix distinguishes capacity overflow from allocator failure. Both are terminal under the
pinned runtime policy: neither returns a recoverable error or a successful partially initialized
array, and no cleanup-after-abort behavior is promised. The allocator-failure regression uses a
test-only child-process failpoint; it is not a public runtime API. Embedded NUL and UTF-8 behavior
belongs to the contained `str`/`string` types and must not introduce a second encoding. Persisted
wire identity is N/A to the builder itself; a future consumer owns any artifact schema.

### Align acceptance gate

Before Align marks Request 8 `ALIGN_MERGED`, its focused tests must prove all of the following:

1. Type formation applies the closed `HeapRecord(S)` predicate before constructor allocation:
   view-free Copy records, owned-string records, nested records, and generic substitutions that
   reduce to those shapes infer from the annotated binding; dynamic-array fields, `Option`,
   sums/enums, cycles, empty records, `layout(C)`, reachable views, and explicit or natural
   over-alignment reject. The exact gates are
   `m12_array_builder.rs::record_builder_type_formation_and_inference`,
   `m12_array_builder.rs::record_builder_field_predicate_rejects_closed_shapes` and
   `m12_array_builder.rs::record_builder_view_and_layout_rejected_before_construction`.
2. The heap form does not admit `RegionPlain` view-bearing elements; the shipped explicit-region
   `array_builder(out)` contract remains a separate Align §7 surface and is not revised by Request 8.
   The exact compatibility gate is
   `align_attr.rs::an_aligned_struct_as_a_field_or_dynamic_array_element_is_rejected` together
   with `m12_array_builder.rs::record_builder_view_and_layout_rejected_before_construction`.
3. A declared scalar-only Copy record can be pushed zero, one, many, and reallocating counts and
   then built into `array<ScalarRecord>` with exact field values. The exact gate is
   `m12_array_builder.rs::copy_record_push_build_zero_one_many_and_realloc`.
4. A declared Move record containing an owned `string` or a nested Move record can be pushed only
   when every reachable owned value satisfies the exact `FreeStanding(e)` predicate; arena-owned,
   mixed-mode, and path-dependent nested owners are rejected before the push side effect. Dynamic
   arrays, `Option`, and sums are not hidden parts of this gate and require separate requests that
   define their recursive cleanup. A valid value can be rebuilt across capacity growth, consumed
   into an array, and deep-dropped without a leak or double free. The test must observe ownership, not only length
   or exit status; the exact gates are `m12_array_builder.rs::record_builder_move_source_matrix`,
   `owned_structs.rs::record_builder_nested_move_drop_plan`,
   `owned_structs.rs::record_builder_rejects_arena_or_mixed_nested_owners`, and
   `m12_array_builder.rs::record_builder_realloc_preserves_nested_owners`.
5. An abandoned builder after every supported control path drops all initialized elements, a
   builder whose element construction fails after an earlier element was pushed leaves no live
   owner, and an enclosing record that fails after receiving the built array cleans both the array
   and the failing sibling exactly once. The exact gates are
   `m12_array_builder.rs::record_builder_partial_element_failure_drops_fields`,
   `m12_array_builder.rs::record_builder_abandonment_all_exit_kinds`, and
   `owned_structs.rs::record_builder_enclosing_record_failure`, covering `if`, `match`, `else`,
   `?`, `map_err`, loop joins, early return, malformed input, and exact-once cleanup for both
   stack-local and boxed builder headers.
6. `build` consumes the builder and transfers storage exactly once; normal array cleanup owns the
   result, replacement drops the old builder, and use-after-build/source-use-after-push are
   rejected. The exact gates are `m12_array_builder.rs::record_builder_build_transfer_and_array_drop`
   and `m12_array_builder.rs::record_builder_reassignment_drops_old_storage`; the build owner is
   parameterized over stack-local and boxed headers and proves exact buffer/header disposition.
7. `append` of a Move record, bare `str`, dynamic array, resource, function, raw value, or builder is rejected
   before side effects. Passing or returning a record-element builder by value transfers the sole
   boxed-header owner exactly as for scalar/string builders. An existing `borrow mut` helper uses it
   non-consumingly, cannot create an escaping alias, and cannot consume it with `build`; the caller
   may build after the borrow ends. Aggregate/`Option`/`Result` placement, capture, and task transfer
   remain rejected. The exact gates are
   `m12_array_builder.rs::record_builder_by_value_parameter_return_and_borrow_mut`,
   `m12_array_builder.rs::record_builder_invalid_storage_and_capture`, and the existing
   `capture_into_spawn_rejected`, `capture_into_par_map_rejected`,
   `escaping_array_builder_keeps_boxed_header`, and
   `array_builder_crossing_user_call_stays_boxed` tests.
8. The deterministic validation order is preserved for multi-invalid local, imported, per-unit,
   and cache-replay checks: parser/import/arity and inference, the closed recursive eligibility
   predicate (including view/aggregate/cycle/alignment rejection), placement, source/type state,
   allocation mode, then build/escape. The
   exact gates are `m12_array_builder.rs::record_builder_validation_precedence_local_and_imported`,
   `per_unit.rs::record_builder_validation_precedence_parity`, and
   `cache_codegen.rs::record_builder_validation_precedence_cache_replay`.
9. Local and imported records, including a concrete generic record instantiation admitted by the
   pinned Align baseline, preserve their nominal declaration identities and produce identical
   decisions in whole-program and per-unit compilation through the existing versioned nominal
   interface graph. Two distinct declarations with identical fields and layout remain distinct
   builder specializations and result-array types. That graph
   carries the complete reachable declaration-order fields, layout, allocation mode, and recursive
   `DropPlan` facts. Malformed, stale, unresolved, cyclic, or producer/consumer-incompatible graph
   references reject before HIR/codegen. A record-definition edit invalidates the codegen cache,
   reverting it restores the original identity, and no builder-specific descriptor is introduced. The exact
   gates are `generics.rs::record_builder_generic_instantiation`,
   `per_unit.rs::record_builder_imported_interface_graph`,
   `cache_codegen.rs::record_builder_nominal_identity_and_definition_edit_revert`, and
   `interface_param_modes.rs::record_builder_interface_drop_plan`.
10. Checked-HIR validation reuses the producer's canonical heap-record predicate:
    `ArrayBuilderNew` accepts exactly the admitted heap records, `ArrayBuilderPush.moves_value`
    agrees with Copy versus recursive Move ownership, and `ArrayBuilderBuild` preserves the same
    nominal struct id and AoS result. Valid and one-field-malformed rows reject before MIR allocation
    or transfer through
    `align_mir::validate_hir_tests::heap_record_array_builder_rows_match_the_producer`.
11. A second operation cannot concurrently alias one record builder: by-value transfer moves the
    sole owner, while `borrow mut` is a checked non-consuming borrow with no escaping alias and
    aggregate/capture/task placement remains rejected. Two distinct builders in one process, an
    aggregate plus a focused builder call, and two independent processes have no shared mutable
    state. Capacity overflow and test-injected allocator failure both terminate without a
    recoverable result or successful partial array. The exact gates are
    `m12_array_builder.rs::record_builder_same_instance_alias_rejected`,
    `m12_array_builder.rs::record_builder_two_instances`,
    `cache_parallel.rs::record_builder_two_processes`,
    `m12_array_builder.rs::record_builder_capacity_overflow_terminal_child`,
    and `m12_array_builder.rs::record_builder_allocator_failure_terminal_child`.
12. The existing scalar/string builder behavior and JSON `array<Struct>` decode/drop behavior remain
    green, and allocation instrumentation proves that a built array owns transferred storage while
    an abandoned builder frees every live element. The exact gates are the existing
    `m12_array_builder.rs::i64_push_build_then_pipeline_sum`,
    `string_push_build_len_and_deep_drop_cycles`, `reassignment_frees_old_string_builder`,
    `m5.rs::json_decode_struct_array_len`, `json_decode_struct_array_malformed_errors`, and
    `m12_array_builder.rs::record_builder_allocation_transfer_instrumentation` tests.

13. A future consumer adoption test is not part of the current Align implementation gate. Before a
    concrete consumer may mark this request `ALIGN_LLM_VERIFIED`, that consumer must name its exact
    record shapes, wire boundary, adoption fixture, and output checks in its own reviewed design;
    it must not assume a JSON DTO, a borrowed-view conversion, or a private collection abstraction.
    Request 8 itself does not absorb any consumer's wire or persistence boundary. For the currently
    named C6c2 consumer, `c6c2-request8-adoption` is the enabling fixture and must pass before the
    verifier consumes the surface on the same capability branch.

Align implementation remains in the sibling repository. After `ALIGN_MERGED`, each named consumer
adoption checkpoint uses the capability branch's shared release build and pin update and adds its
consumer-specific target and fixture. The targets must use the reviewed fresh-compiler topology and exact shipped pin, verify the
declared record values and cleanup boundary, and reject panic, stale source use, and unexpected
artifacts. `c6c2-request8-adoption` is the first C6c2 enabling target and covers only the Request 8
base graph; it must pass before C6c2's verifier implementation consumes the surface, but does not
need a separate merge. The later `c6f2-array-builder-adoption` covers the paired evaluator consumer.
Each target remains separately traceable; one final `make ci` closes the capability wave rather than
running after every checkpoint. Adoption does not silently inherit another consumer's fixture.

### References

- `docs/specs/roadmap.md` and `docs/specs/align-llm.md` — the committed roadmap and architecture;
  a concrete consumer must refine its own record shapes and adoption gate before using this request.
- `../align/docs/impl/17-library-boundary-prerequisites.md` §7 — the separate shipped
  `RegionPlain` region-builder contract and its ownership/compaction model; §7.5 is the shipped
  heap-record extension awaiting align-llm adoption.
- `../align/docs/impl/08-memory-model-v2.md` §8 — materializing-terminal bounds and allocation
  behavior; §11 — shipped and restricted dynamic struct-array shapes and whole-Copy-record limits.
- `../align/docs/impl/core-design/json.md` §§3–4 — current declared-record JSON ownership and
  `str`/`array<str>` view behavior; this request does not alter that codec or introduce a private
  wire format.
- `../align/draft.md` §§5, 9, and 18 — ownership, arrays, explicit allocation, and core library
  boundaries.
- `../align/crates/align_sema/src/lib.rs` — current `Ty::ArrayBuilder(Scalar)` formation, the
  `resolve_type` `"array_builder"` branch, constructor inference, region analysis, and DropPlan.
- `../align/crates/align_mir/src/lib.rs` — current scalar/string-specific builder MIR operations
  and move/cleanup lowering.
- `../align/crates/align_codegen_llvm/src/lib.rs` — current aggregate/drop lowering and ABI
  descriptor paths.
- `../align/crates/align_driver/src/lib.rs` — current interface, per-unit, and codegen-cache
  identity paths.
- `../align/crates/align_runtime/src/lib.rs` — current raw builder storage, growth, scalar/string
  push, build transfer, and string deep-free paths.
- `../align/crates/align_driver/tests/m12_array_builder.rs` — shipped scalar/string builder and
  reassignment/capture regressions that must remain green.
- `../align/crates/align_driver/tests/owned_structs.rs` and
  `../align/crates/align_driver/tests/owned_structs_arrays.rs` — recursive aggregate ownership and
  array cleanup regressions.
- `../align/crates/align_driver/tests/align_attr.rs` — over-aligned dynamic-array rejection
  regression retained by the heap-builder element gate.
- `../align/crates/align_driver/tests/cache_codegen.rs`,
  `../align/crates/align_driver/tests/generics.rs`,
  `../align/crates/align_driver/tests/per_unit.rs`, and
  `../align/crates/align_driver/tests/interface_param_modes.rs` — nominal identity and
  interface/cache regressions.
- `../align/crates/align_driver/tests/m5.rs` and `../align/crates/align_driver/tests/mmv2.rs` —
  declared JSON array and materializing-terminal compatibility regressions.
- `../align/crates/align_driver/tests/cache_parallel.rs` — independent-process cache/concurrency
  regression harness.

---

## Request 9 — `core.json`: owned text fields and runtime-sized text arrays

```text
Status: CLOSED
Priority: high
Blocking: no
Blocked gate or slice: none; the `C7-PERSISTED-RESULT` consumer in `src/persisted_result.align` and `src/main.align` consumes the shipped owned-JSON surface
Independent work that may continue: all work
Resume condition: complete
Align commit or pull request: accepted Align plan `../align/docs/impl/24-owned-json-plan.md`; design PR #851 merged as `7f435ae9b228fc9a4ce047e9d64d5b99feeea60c`; implementation PR #852 merged as `2bb93a93a2f30da1daabd5b65d83863dab617560`
align-llm verification: the named C7 adoption target `c7-owned-record-source-expiry-adoption` (`scripts/run-c7-owned-record-source-expiry-adoption`, `src/c7_owned_record_source_expiry_adoption.align`) passes at the unchanged pin `2f33ac5c33a898a7894af58322852632ce6ffe42` — 3 parsed fixtures, 12 example rows, 45 adoption rows — covering section 6.1 source expiry for every retained direct field, the three optional-note states, the section 6.3 Move-carrier transfer set, the normative owned-path golden byte pair, bounded canonical encode at exact fit and both rejection rows, and direct `array<string>` cleanup through replacement, move-out, and a mid-array recoverable failure. The consumer that first uses the shipped surface is `src/persisted_result.align` with `src/main.align`, and the C7 lifetime/artifact qualification `make persisted-result-qualification` passes at the same pin: 11 boundary rows, 256 generated PASS and 32 generated FAIL differential cases with 0 unexpected divergences, 38 malformed inputs, 29 artifact mutations, 10 golden rows, the intentional source mutation detected with 5 divergent and 38 agreeing cases, 749 bounded children. **The final supervised `make ci` leg is met.** At head `36c8568897802afe6744edf6177dbb089d887b5a`, `python3 scripts/run-fresh-worker-qualification --installed-profile-only --require-docker` exits 0 with `fresh image profile smoke: PASS` and `fresh worker qualification: PASS (installed profile only)`. That request is the trusted image entrypoint's `make --no-print-directory ci`, so the whole `capable-checks` graph — including this capability's `persisted-result-smoke` member — ran inside the authenticated fresh worker. Phases: `docker-daemon` 913 ms, `image-build` 16,526 ms, `image-attestation` 3,342 ms, `profile-lifecycle` 2,594 ms, `profile-self-test` 14,713 ms, `trust-mutations` 12,892 ms, `runtime-replacements` 27,036 ms, `boundary-profile` 412,666 ms, **`worker-aggregate` pass after 365,567 ms**, `cleanup` 1,380 ms; whole installed profile 858,251 ms. The first supervised run of the newly admitted lane member failed the post-aggregate workspace-overlay check and was repaired in `36c8568`; the pull request's GitHub `Installed Ubuntu 24.04 fresh-image profile (x86_64)` and `(aarch64)` checks are the publication CI evidence for the merge head, following the Request 2 precedent recorded for PR #103. Platform caveat: C7 ACCEPTANCE evidence (the §11 environment matrix) still requires the x86_64 baseline environment and reviewed C7-P profiles for the aarch64 targets — Request 9's register advancement is about the owned-JSON surface adoption, which is complete; no C7 platform acceptance is claimed from these aarch64 runs.
```

### Align implementation (2026-08-17 — merged #852)

PR #852 ships direct declared-record decode, canonical encode, and bounded canonical encode for
the closed owned graph accepted by PR #851: signed and unsigned integer fields of widths 8, 16,
32, and 64, `bool`, `string`, `Option<string>`, and `array<string>`, with at least one owned-text
leaf selecting the route. Decode returns a free-standing `Static` record whose strings and array
spines neither borrow the input nor become arena-owned, including when called inside `arena {}`.
Move, replacement, return, branch joins, `?`, `match`, `else`, `map_err`, recoverable parse failure,
and Drop use the ordinary recursive Move carrier and clean each live owner exactly once.

The shipped descriptor is a target-bound structural `OwnedJsonDescV1` carried through checked HIR,
MIR, interface serialization, per-unit cache identity, LLVM layout verification, and runtime
allocation/cleanup. Encoding preserves declaration order, integer width and signedness, embedded
NUL and Request 7 escape semantics; bounded encoding produces identical bytes on success and keeps
Request 12's inclusive limit errors. The existing borrowed record, scalar-array, AoS, SoA, union,
scanner, and fixed-array routes remain separate. Nested records, record arrays, enums, floats,
`str`, `array<str>`, nested option/array graphs, and `layout(C)`/`align(N)` records remain outside
this owned route; Request 13 owns any later recursive C6 graph widening.

The Align-side release build completed on merged `main` with exactly
`cargo build --release --workspace`. The shipped surface is contained in the current pin
`2f33ac5c33a898a7894af58322852632ce6ffe42`, adopted by align-llm in `f344ea9`; the earlier pin
`19c3db144c462bf7d6784f88d64cc124229b7ec2` already contained it and no pin bump was required for
this request. The `C7-PERSISTED-RESULT` adoption fixture, consumer lifetime/artifact qualification,
and final `make ci` are complete and are recorded above. C7-PERSISTED-RESULT merged as align-llm PR
#104 (`a52b9ac69cdd3a47574a5a4dc426e7edc8294dbf`), completing the shipped-surface record and closing
Request 9.

### Motivation

`C7 Algorithm Verification`'s named `C7-PersistedResult` slice now requires retaining a declared record after its input document and
borrowed `str` views have expired. The pinned `core.json` decoder accepts `str` and `array<str>` fields whose
elements borrow the input, but it rejects the direct `string`/`array<string>` field shape required
for an explicitly owned record. An application-side JSON value tree, private encoder, or reparse
would violate Align's declared-record and explicit-ownership design.

This request extends the existing declared-record JSON operations with one explicitly owned text
domain. It does not add a dynamic JSON value type, reflection, a second encoder, implicit cloning
of arbitrary values, or support for nested owned aggregate graphs that are not listed below.

### Current-state evidence at the pinned Align revision

Verified against `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e` on 2026-08-01:

- `json_struct_fields_ok_rec` in `../align/crates/align_sema/src/lib.rs` admits `str`, scalar
  fields, nested records, `array<Struct>`, and `array<str>` for the shipped descriptor path, but
  rejects `string` and `array<string>` in the JSON direction.
- `check_json_decode` has a separate existing top-level scalar-array path for `array<i64>`,
  `array<f64>`, and `array<bool>` (and the corresponding declared scalar primitive types); this
  path copies elements into an owned dynamic array and must remain separate from the new direct
  owned-record selector.
- Struct formation's pass 0b-2 check rejects an `array<string>` field because the current recursive
  field cleanup is not implemented, even though a top-level `array<string>` payload exists for
  narrower library producers such as `fs.read_dir`.
- `../align/docs/impl/core-design/json.md` defines `array<str>` as an owned spine of borrowed
  elements and explicitly leaves `array<string>` fields deferred. The decoded record is input-region
  bound, so cloning each element is the current way to persist text.
- The existing builder can push individual owned `string` values, but no shipped declared-record
  codec or recursive field `DropPlan` constructs and cleans an owned text array inside a record.
- The current runtime's decoded-owner failure path does not yet recursively clean every optional
  descriptor after a `Some` value becomes live. Request 15 owns repair of that shipped borrowed
  declared-record route. Request 9 owns only the additional direct-owned route's success, failure,
  replacement, move-out, and branch-join tests; it does not claim the pinned cleanup path already
  passes.
- The pinned memory model allocates owned `array`/`string` values inside `arena {}` in the arena and
  forbids moving them out. Request 9 therefore requires a reviewed update to
  `../align/draft.md`, `../align/docs/language-spec.md`,
  `../align/docs/impl/08-memory-model-v2.md`, and `../align/docs/impl/core-design/json.md` that
  defines this JSON materializing terminal's explicit free-standing allocation mode inside an arena,
  plus source-drop, move-out, and failure-cleanup ownership tests. Until that Align design/update is
  merged, the arena persistence case is a future acceptance gate rather than an available capability.
- `../align/docs/impl/07-roadmap.md` marks L1b Move sum/Option/Result payload completion complete,
  and `../align/crates/align_driver/tests/owned_tagged_payloads.rs::retained_result_with_recursive_move_payload_is_supported`
  compiles retained raw results, including `Result<array<Message>, Error>` produced by
  `json.decode`. Per `../align/CLAUDE.md`, the checked-out compiler and its tests are the
  implemented surface when design prose disagrees; that implementation/test evidence is the
  current positive evidence for the recursive Move carrier.
- `../align/docs/impl/core-design/option-result.md` and
  `../align/docs/impl/core-design/json.md` §3 still contain pre-L1b statements that owned
  Move-result values are rejected or must be consumed directly with `?`. Those documents are
  stale design material at this pin, not positive evidence for the raw-`Result` contract. The Align
  implementation PR must reconcile both documents at a named commit before Request 9 can reach
  `ALIGN_MERGED`; Request 9 adopts the compiler/test-proven carrier and does not invent a new result
  mechanism.
- The positive regression
  `../align/crates/align_driver/tests/m5.rs::json_option_move_struct_payload_remains_admitted`
  preserves the existing borrowed route for a record with `Option<MoveStruct>`. Request 15 owns its
  recoverable-failure cleanup. Request 9 rejects unsupported optional owners only after its direct
  owned-text selector has been chosen and must not narrow or reinterpret that existing route.

This is a genuine Align type/standard-library boundary, not an align-llm compatibility concern.
Request 9 must be designed and implemented in Align before any consumer targets it.

### Requested capability

Keep the existing context-inferred declared-record operations and expand their accepted field graph:

```text
json.decode(input: str) -> Result<T, Error>   // T is inferred from the annotated declared-record binding
json.encode(value: T) -> str                  // returns the existing canonical output view
json.encode_bounded(value: T, max_bytes: i64) -> Result<string, Error>
```

The exact source idiom remains the current declared-record form; no expression-position type
arguments are introduced. The declaration and the positional call are shown separately so the
future syntax fixture does not imply a type-argument call form:

```align
import core.json

OwnedTask {
  id: string
  priority: i64
  attempts: u16
  limit: u64
  enabled: bool
  argv: array<string>
  note: Option<string>
}
```

```align
fn use_task(input: str) -> Result<(), Error> {
  task: OwnedTask := json.decode(input)?
  print(json.encode(task))
  return Ok(())
}
```

The owned field walk is an operation-specific extension, not a replacement for the existing shared
JSON schema predicate. The target routing is fixed before any descriptor or runtime allocation is
introduced:

| Entry point and expected target | Request 9 behavior | Required boundary regression |
| --- | --- | --- |
| Direct `json.decode` with `Result<Struct, Error>` | Select the new owned direct-record predicate when the record has an owned text leaf; otherwise retain the existing all-borrowed predicate | `m5_owned_json.rs::owned_json_direct_record_target_selects_owned_path` |
| `json.encode` with a direct `Struct` source | Use the owned descriptor only for the same accepted flat direct-record grammar; existing encode targets retain their existing routes | `m5_owned_json.rs::owned_json_direct_record_encode_route` |
| `json.encode_bounded` with a direct `Struct` source | Use the same owned graph and exact ordered plan as unbounded encode; the inclusive `i64` limit and owned `Result<string, Error>` retain Request 12 semantics | `m5_owned_json.rs::owned_json_direct_record_bounded_encode_route` and `owned_json_bounded_parity` |
| `json.decode` with `Result<array<scalar>, Error>` | Retain the existing top-level scalar-array decoder for `array<i64>`, `array<f64>`, `array<bool>`, and the corresponding supported scalar primitive forms; it copies elements into its existing owned dynamic-array representation and never selects `OwnedJsonDescV1` | Existing `m5.rs::json_decode_scalar_array` and `m5.rs::json_decode_float_array`; the Align implementation PR adds the currently missing `m5.rs::json_decode_bool_array` regression for the already-supported top-level bool path |
| `json.decode` with `Result<array<Struct>, Error>` | Retain the existing AoS predicate and descriptor, including already-shipped Move element graphs such as a union carrying `array<Part>`. The new direct owned-text selector is never entered; an element containing `string`, `Option<string>`, or `array<string>` is rejected before `OwnedJsonDescV1` construction and allocation | `m5_owned_json.rs::owned_json_record_array_preserves_shipped_move_aos` and `m5_owned_json.rs::owned_json_record_array_owned_text_rejected_before_owned_descriptor` |
| `json.scan` with `json.scanner<Struct>` | Retain Request 6's recursively Copy scanner-row predicate. An owned record is rejected before scanner construction, descriptor construction, or row-slot allocation | `m5_owned_json.rs::owned_json_scanner_target_rejected_before_allocation` |
| `json.decode` with `Result<soa<Struct>, Error>`, a union, or a scalar | Unchanged existing target-specific validation; none can select the owned direct-record path | `m5_owned_json.rs::owned_json_non_record_targets_unchanged` |
| `json.encode` with a fixed `StructArray` source | Retain the existing fixed-array template/unrolled route; `OwnedJsonDescV1` is never selected, and existing borrowed or shipped Move element behavior is unchanged | `m5_owned_json.rs::owned_json_fixed_struct_array_encode_route_unchanged` |
| `json.encode_bounded` with a fixed `StructArray` source | Retain the existing bounded fixed-array route; the owned direct-record selector is never entered | `m5_owned_json.rs::owned_json_fixed_struct_array_bounded_route_unchanged` |
| `json.encode` with a direct union/`Enum` source | Retain the existing shape-directed union route; `OwnedJsonDescV1` is never selected, including for shipped Move union payloads | `m5_owned_json.rs::owned_json_union_encode_route_unchanged` |
| `json.encode_bounded` with a direct union/`Enum` source | Retain the existing bounded union route and limit semantics; `OwnedJsonDescV1` is never selected | `m5_owned_json.rs::owned_json_union_bounded_route_unchanged` |

The implementation must keep the existing all-borrowed `json_struct_fields_ok_rec`, the existing AoS
descriptor route, the existing top-level scalar-array decoder, and the Request 6 scanner ownership
predicate separate from the new direct-record selector. A shared helper may classify a field graph, but a caller must pass an explicit
operation/target mode. The scanner mode must reject every non-Copy graph; the record-array mode must
reject only the new Request 9 direct `string`/`Option<string>`/`array<string>` graph before
`OwnedJsonDescV1`, while continuing to accept the already-shipped Move AoS/union graph that its
existing descriptor can deep-drop. Fixed struct-array and union encode modes likewise retain their
existing routes and must not be widened by a direct-record descriptor walk.

The Move boundary is deliberately explicit and follows the shipped recursive Move `Result` carrier.
The `json.decode(input)?` expression above consumes the temporary result and binds the owned record
as the local `task`. A raw `Result<OwnedTask, Error>` is also a normal Move value: it may be bound
with an explicit type, passed to or returned from a function with the same result type, reassigned,
stored in a supported local, or moved through a branch. Every transfer nulls the source slot and
leaves exactly one live owner. These are positive ownership fixtures:

```align
fn retain(input: str) -> Result<OwnedTask, Error> {
  return json.decode(input)
}

fn pass_raw(result: Result<OwnedTask, Error>) -> Result<OwnedTask, Error> {
  return result
}

fn store_raw(input: str) -> Result<OwnedTask, Error> {
  raw: Result<OwnedTask, Error> := json.decode(input)
  return raw
}
```

The supported error-conversion form is:

```align
fn to_error(value: Error) -> Error {
  return value
}

fn use_mapped(input: str) -> Result<OwnedTask, Error> {
  raw: Result<OwnedTask, Error> := json.decode(input)
  mapped: Result<OwnedTask, Error> := raw.map_err(to_error)
  task: OwnedTask := mapped?
  return Ok(task)
}
```

The complete raw-`Result` and explicit typed `map_err` examples above are included in
`docs/examples/request9-owned-json-syntax.align` and are parser-checked together; their runtime
ownership behavior remains an Align implementation acceptance gate. The explicit `raw` and `mapped`
bindings keep the decode target and mapped result type inferable, and `mapped?` yields `OwnedTask`,
which is returned through `Ok(task)`. `map_err` consumes the source `Result`, moves the selected `Ok`
record or converted error into its rebuilt result, and then `?` consumes that result. A mapper may not
retain the consumed source after the call. A result source is dropped on `Err`, moved on `Ok`, and the
old owner is dropped before reassignment. `Result` fields are not part of the flat JSON descriptor
grammar, and unsupported optional owners are rejected by this JSON descriptor before decode
allocation only after the direct owned-text selector is chosen; records with no owned text leaf retain
the existing JSON route. Neither rule changes the language-wide recursive Move `Result` support.

The public contract is:

1. The owned JSON path is selected only when the declared record has at least one direct owned text
   leaf: `string`, direct `Option<string>`, or direct `array<string>`. Once selected, its grammar is
   closed and flat: every other field is one of the Copy JSON scalars `int` or `bool`. Copy integer
   fields retain their declared 8/16/32/64-bit width and signedness, and decode rejects a JSON number
   outside that exact range as a recoverable decode error; a width-64 unsigned field accepts the full
   `0..=u64::MAX` range and encode writes its canonical decimal digits through a full-range unsigned
   writer, never through a signed `i64` intermediate. If an earlier owner is already live, the error
   follows item 4's cleanup contract rather than a preallocation guarantee. Boolean fields
   accept and emit only JSON `true` or `false`. `float` is
   intentionally outside the owned v1 domain: this path never accepts a non-finite value that the
   existing writer would render as invalid JSON; the existing all-borrowed codec retains its own
   float behavior unchanged. The
   record has no `str`/`array<str>` field, nested record, `array<Struct>` field, enum/sum field,
   `Option<array<string>>`, or other aggregate owner. Records with no owned text leaf continue
   through the existing borrowed/all-borrowed JSON codec unchanged, including its current nested,
   `array<Struct>`, `str`, and `array<str>` forms. Missing and JSON `null` both decode to `None`;
   `Some(empty)` is distinct from `None`, and `json.encode` omits `None` fields as in the existing
   direct `Option<T>` contract. Required fields reject both missing and `null`, and `null` is not a
   valid `array<string>` element. Any generic substitution is accepted by the owned descriptor
   only when it reduces to this exact direct grammar; the language itself may form
   `Option<MoveStruct>`, but the selected owned descriptor rejects `Option<MoveStruct>`, `Option<OwnedRecord>`,
   `Option<array<string>>`, `Option<array<Struct>>`, `Option<enum>`, `Option<Result<...>>`, nested
   `Option<Option<string>>`, move-enum payloads, and every other unsupported optional owner within
   the selected owned descriptor at JSON descriptor formation before construction. A record with no
   direct owned text leaf remains on the existing all-borrowed route and is not newly rejected by
   this item solely because it contains an existing-route Move option.
2. A record with an owned text leaf enters the owned JSON domain only when every reachable field is
   in item 1's direct grammar; a `str` or `array<str>` anywhere in that otherwise-owned graph is a
   mixed graph and is rejected before allocation. A record without an owned text leaf is not a
   mixed graph and remains with the existing codec. There is no `Owned*` marker type and no
   implicit `clone_in(out)`. The requested JSON terminal explicitly selects free-standing allocation
   outside and inside `arena {}`; inside an arena this is a new allocation mode, not the pinned
   language default, and Align must first update the memory-model/spec sources and ownership tests
   named above to authorize it. Once that prerequisite is merged, a successful owned result can move
   out of the decoding scope and outlive its input. The owned-path record declaration must use natural layout: explicit `layout(C)`
   and `align(N)` attributes on the record are rejected before descriptor construction, even when
   their effective alignment would otherwise be representable.
3. `json.decode` allocates an independently owned `string` for each owned text field and an owned
   dynamic spine plus one owned `string` per `array<string>` element. The result is the current
   `Result<T, Error>` expression shape. A Move `T` may be consumed by `?`, direct same-scope
   `match`, or the explicit typed `raw`/`mapped` bindings with `mapped?` shown above; the raw
   `Result<T, Error>` may also be bound, passed, returned, reassigned, and moved through supported
   control-flow joins under the ordinary recursive Move rules. `map_err` transfers the selected `Ok`
   owner and converted error exactly once. A successful owned result has no lifetime dependency on
   the input. The Align implementation
   PR must first reconcile the stale `option-result.md`/`json.md` Move-result prose at a named
   commit; the pinned compiler/test behavior is the implementation evidence, and this request adds
   no alternate raw-result mechanism.
4. Every recoverable decode failure after any direct owned field or array element becomes live drops
   every initialized field, array spine, and string buffer exactly once. Recoverable failures include
   malformed or incomplete input, wrong shapes, duplicate declared keys, out-of-range integers, and
   non-whitespace trailing bytes after an otherwise valid object. Capacity overflow and allocator
   failure are terminal process-abort conditions rather than recoverable `Error` results; they are
   covered by separate rows below and carry no cleanup-after-abort guarantee. The supported `Option`
   cleanup is only the direct `Some(string)` payload; all unsupported optional owners reject before
   allocation.
   Cleanup order is deterministic and independent of JSON key order: direct record fields are
   visited in source declaration order; within a live direct `array<string>` field, initialized
   elements are released in ascending element-index order and then the array spine is released.
   An optional string payload is released while its field is visited, and an uninitialized field or
   element is skipped. The same order applies to ordinary record `Drop` and to the top-level
   trailing-byte failure path. Replacement drops the previous direct owner before installing the
   new one; move-out nulls the source; `?`, `else`, `map_err`, branch joins, loop back-edges, and
   early return preserve the same live-field state. No new Request 9 nested aggregate or top-level
   AoS staging path is part of this request, so those existing paths and their separate cleanup
   prerequisites are not widened or implied. Malformed, incomplete, or non-whitespace-
   trailing input never returns a partially initialized successful record; the top-level post-parse
   trailing-byte error path invokes the same direct-owner cleanup before returning `Err`. Terminal
   capacity or allocator aborts are outside this recoverable-failure cleanup guarantee.
5. `json.encode` accepts the same flat owned field grammar, borrows owned strings only for the
   duration of encoding, and returns the existing canonical `str`. Inside an `arena {}` the result is
   arena-backed through `builder_finish_stack` and cannot escape that arena. Outside an arena it uses
   `builder_into_string_stack`; the compiler retains the corresponding hidden free-standing owner
   for the returned view under the existing template-owner rules. It never consumes, clones, or
   mutates the source record. The caller must keep the source and returned view live for the call and
   must explicitly call `canonical.clone()` to obtain a free-standing `string` before crossing an
   arena boundary or persisting the bytes. Field declaration order, scalar formatting, string
   escaping, embedded NUL, and text-array order use the owned-path grammar defined below.
   `json.encode_bounded` accepts the identical graph and ordered plan, then an exact `i64`
   inclusive byte limit. A negative limit or first byte beyond it returns `Error.Invalid` with no
   partial value; success owns one free-standing `string` whose bytes are identical to unbounded
   encode. It borrows and never mutates or consumes the source.
6. JSON field/type validation is compile-time and unbounded encode is non-fallible after a valid
   descriptor is compiled; bounded encode has only the Request 12 limit errors above. Neither
   operation performs consumer artifact validation or file commit. A future
   consumer owns its separate validation, output clone, and persisted-artifact boundary. Runtime
   decode returns the existing `Error` for malformed input and follows the deterministic cleanup
   order below.
7. The accepted field graph participates in type formation, interface serialization,
   monomorphization, structural identity, codegen cache keys, and ABI validation. Its canonical
   internal descriptor is the self-versioned byte sequence `OwnedJsonDescV1`:

   ```text
   descriptor := u8 schema_version (= 0x01)
                u8 layout_mode (= 0x00, natural layout only)
                u8 layout_algorithm (= 0x01, descending alignment with stable declaration-index ties)
                u32 field_count (little-endian, non-zero)
                field[field_count]
   field := u32 name_len (little-endian)
            byte[name_len] name_utf8
            u8 type_tag
            type_payload
            u32 physical_payload_offset (little-endian)
            u32 optional_tag_offset (little-endian, = 0xffffffff for a required field)
            u32 layout_size (little-endian)
            u32 layout_align (little-endian)
            u8 allocation_mode (= 0x00 Copy, 0x01 free-standing owner)
            u8 drop_tag
   type_payload for 0x01 copy-integer := u8 bit_width, u8 signedness (= 0 signed, = 1 unsigned)
   type_payload for 0x03 copy-bool    := empty
   type_payload for 0x10 owned-string := empty
   type_payload for 0x11 optional-owned-string := empty
   type_payload for 0x12 owned-string-array := u8 element_tag (= 0x10),
                                                u8 drop_plan_version (= 0x01)
   ```

   The only accepted type tags are `0x01`, `0x03`, `0x10`, `0x11`, and `0x12`; `0x02` is reserved
   and rejected by v1. Integer widths are exactly `8`, `16`, `32`, or `64`, and `signedness` is
   exactly `0` for signed or `1` for unsigned. `name_utf8` must be a non-empty ASCII identifier using the current
   declared-field grammar, and field names must be unique and appear in source declaration order.
   The drop tags are exactly `0x00` for Copy fields, `0x01` for an owned string, `0x02` for an
   optional owned string, and `0x03` for a direct owned string array; the tag must agree with the
   type tag. Copy type tags must carry allocation mode `0x00`; owned type tags must carry `0x01`.
   `layout_algorithm = 0x01` means that physical fields are ordered by descending natural ABI
   alignment, with ties resolved by the stable source declaration index, matching Align's pinned
   `logical_to_physical` rule. Fields remain serialized in source declaration order. Every serialized
   physical offset is an absolute byte offset from the decoded record's base address; no descriptor
   offset is relative to a logical field base. For a required field, `physical_payload_offset` is
   its target-local field offset and `optional_tag_offset` is the required-field sentinel. For the
   `0x11` optional-owned-string field, let `field_base` be the target-local offset of the logical
   field and let the target ABI provide the `Option` tag and payload offsets within that field.
   `physical_payload_offset` is `field_base + option_payload_offset`, and `optional_tag_offset` is
   `field_base + option_tag_offset`; both record-base-relative offsets are serialized, target-local,
   and independently validated. This explicit addition is required even when the `Option` tag is
   currently at offset zero, so a nonzero-position field such as `OwnedTask.note` cannot be read from
   the wrong origin. Equivalently, the two optional offsets follow the
   `field_base + option_{payload,tag}_offset` rule. Neither offset is an inferred host pointer or a
   runtime scan. The serialized
   `layout_align` is that field's target-local `field_abi_align`, and
   `layout_size` is its target-local ABI size. A descriptor is rejected before interface or codegen use when its
   schema version, natural
   `layout_mode`, or `layout_algorithm` is wrong, field count is zero, a length/count overflows the
   remaining byte sequence, a name is invalid or duplicated, a type payload or drop tag is invalid,
   a physical payload offset, optional tag offset, layout width, or alignment is not the compiler's
   descriptor for the field, an
   allocation mode is not the mode required by the type tag, an array element/drop-plan pair is not
   exactly `(0x10, 0x01)`, fields are not in declaration order, or any trailing byte remains. The
   owned path rejects explicit `layout(C)` and `align(N)` before this descriptor exists. A different
   physical layout mismatch—whether in the algorithm, payload offset, optional tag offset, size, or
   alignment—therefore rejects or
   cache-misses before field access, cleanup, or code generation rather than being treated as the
   same ABI. No pointer, local struct ID, source position, or declaration hash is part of this
   identity. A field reorder, field-name change, scalar-width change, ownership tag, natural layout
   value, allocation mode, physical layout, or drop-plan change therefore changes structural
   identity; an edit/revert restores the original identity. Whole-program and imported/per-unit
   compilation must make the same decisions, and stale interface descriptors reject or cache-miss
   before code generation. A golden byte fixture covers the complete header including the
   natural-layout mode and algorithm, field order, signed and unsigned integer payload mappings,
   payload widths, physical payload/tag offsets, layout values, allocation tags, drop tags, and
   rejection of each malformed, mismatched, or trailing boundary.
   The target-local descriptor is never serialized naked. Interface format 7 adds the sorted
   accepted non-generic exported-record descriptor list after structs and before enums and carries
   each descriptor in `OwnedJsonInterfaceEnvelopeV1`. That envelope binds the canonical LLVM target
   triple, object format, 64-bit little-endian pointer/string/array/`Option<string>` ABI cells, their
   existing `Hash128`, and the exact descriptor length before any offset is trusted. Format 6 rejects
   as `UnknownVersion(6)` before list parsing. Concrete consumer monomorphs and private/current-unit
   records construct the same target envelope into structural MIR/implementation identity instead
   of the public interface hash. The independent x86_64 golden is a 36-byte ABI prefix, 16-byte hash,
   4-byte descriptor length, and the 214-byte inner descriptor: 270 envelope bytes total.
   Full-range unsigned encode adds exactly one keyed runtime record,
   `BuilderWriteUint -> align_rt_builder_write_uint(*mut Builder, u64)`, reusing LLVM ABI A66
   `void @SYM(ptr, i64)` with unsigned Rust interpretation. The implementation changes the native
   inventory from 293 to 294 keyed records, 306 to 307 base records, and 314 to 315 maximum probe
   exports; registry, declaration, Rust export, selection, and parity owners land atomically.
8. Allocation remains explicit at the decode/encode boundary: no hidden global arena, JSON value
   object, private application encoder, automatic conversion between `array<string>` and `array<str>`,
   new Request 9 top-level owned-text record-array decoder, or nested owned aggregate codec is added.
   Existing AoS/union routes, including shipped Move element graphs, remain under their existing
   descriptors and are not reclassified by this request. A separate wire DTO remains out of scope
   until a consumer records its own lifecycle contract.

9. Same-process concurrency is supported for the complete Request 9 entrypoint matrix. Define the
   operation classes as follows:

   | ID | Entry point class |
   | --- | --- |
   | `OD` | direct owned-record `json.decode` |
   | `OE` | direct owned-record `json.encode` |
   | `OEB` | direct owned-record `json.encode_bounded` |
   | `BD` | existing direct borrowed-record `json.decode` |
   | `SD` | existing bare scalar `json.decode` (`int`, `float`, or `bool`) |
   | `AD` | existing top-level scalar-array `json.decode` (`array<i64>`, `array<f64>`, or `array<bool>`) |
   | `BE` | existing borrowed direct-record `json.encode` |
   | `BEB` | existing borrowed direct-record `json.encode_bounded` |
   | `FE` | existing fixed `StructArray` `json.encode` |
   | `FEB` | existing fixed `StructArray` `json.encode_bounded` |
   | `UD` | existing direct union/`Enum` `json.decode` |
   | `UE` | existing direct union/`Enum` `json.encode` |
   | `UEB` | existing direct union/`Enum` `json.encode_bounded` |
   | `DOC` | existing `json.doc` |
   | `SCAN` | existing `json.scan` |
   | `AOS` | existing `array<Struct>` `json.decode` |
   | `SOA` | existing `soa<Struct>` `json.decode` |

   Let `J = {OD, OE, OEB, BD, SD, AD, BE, BEB, FE, FEB, UD, UE, UEB, DOC, SCAN, AOS, SOA}`.
   The required policy is the full unordered Cartesian product `J × J`, including the diagonal:
   all 153 operation-variant pairs are
   supported concurrently, neither serialized nor rejected before side effects. Each class's
   listed target variants is exercised, so the matrix explicitly includes existing-only pairs such
   as `BD + AD`, `DOC + SCAN`, and `FE + UE`, as well as aggregate-plus-aggregate and
   aggregate-plus-focused pairs. Every encode target includes unbounded/unbounded,
   unbounded/bounded, and bounded/bounded overlap. Direct owned decode and both owned encode
   variants keep parser,
   destination, temporary-owner, and output-builder state in caller-local storage; immutable
   descriptor tables may be shared, but no mutable codec or allocator state is process-global. Every
   pair retains its own input/output ownership and result semantics; existing entrypoints keep
   their existing arena, Copy-row, and region restrictions. Independent processes have the same
   no-shared-state policy. A future connection-global or process-global codec cache would require a
   separately reviewed contract and cannot be introduced under this request.

10. Capacity overflow is distinct from allocator failure. The owned `array<string>` decoder checks
   element-count, element-width, byte-count, and temporary/output-copy arithmetic before every
   resize or allocation; the owned encoder checks builder length-plus-additional arithmetic before
   every growth. A reachable overflow is terminal under the pinned runtime policy, is not a
   recoverable `Error`, and returns no successful partial record/string. It may occur after an earlier
   owner became live, but item 4's recoverable-failure cleanup guarantee does not apply after this
   terminal abort. This is separate from an allocator failure, which is also terminal and has no
   promised cleanup-after-abort behavior. Exact child regressions cover decode growth and encode
   growth independently.

11. Metric / benchmark: N/A as a performance acceptance claim. Request 9 is a correctness and
    ownership prerequisite and introduces no optimization threshold or speed promise. Allocation
    parity between whole-program and per-unit compilation remains a required correctness measurement
    in `m5_owned_json.rs::owned_json_whole_program_per_unit_allocation_parity`; any later codec
   optimization must add its own reproducible baseline, workload, and threshold in a separate
   design.

12. Minimum compiler/platform baseline: the target-local ABI is part of this request's contract
    because `layout_algorithm`, `physical_payload_offset`, `optional_tag_offset`, `layout_size`, and
    `layout_align` are serialized
    and validated. The required baseline is
    `x86_64-unknown-linux-gnu` on Ubuntu 24.04 with Rust 1.96 and LLVM 22, using the compiler and
    runtime at the exact pinned Align revision above. Align's supported release targets
    `aarch64-unknown-linux-gnu` on Ubuntu 24.04-arm and `aarch64-apple-darwin` on macOS 15 are also
    required acceptance environments because natural size and alignment are target-dependent; they
    are not optional evidence. No 32-bit or other target is supported by this request. The descriptor
    is target-local: interface exchange must match the target triple before descriptor validation,
    and a target/ABI mismatch rejects before code generation. Newer hosts are supplementary, not a
    substitute for the named baseline environments.

13. Configuration boundaries: CLI/build inputs are N/A because Request 9 adds no flag, build
    setting, profile, or artifact-selection input; source declarations and explicit function
    arguments are its complete inputs. Option/environment isolation is N/A because Request 9 adds
    no option state, environment variable, process-global codec setting, or persistent boundary
    across which accepted or rejected state could cross. The implementation must not read ambient
    configuration to change descriptor formation, allocation, parsing, encoding, or cleanup; the
    exact pinned compiler/runtime revision is a development prerequisite, not a Request 9 runtime
    option.

Request 9 consumes Request 7's already-authoritative JSON string grammar and canonical escape vector;
Request 7 remains the source of truth for lexical acceptance and semantic duplicate-key handling.
Request 9 does not revise that grammar, make Request 7 depend on this later request, or claim Request
7's arena/borrowed-view materialization. The owned path applies the same `\"`, `\\`, `\/`, `\b`,
`\f`, `\n`, `\r`, `\t`, and valid `\uXXXX` sequence rules, including valid surrogate pairs; it
rejects the same lone/reversed/malformed surrogates, truncated or non-hex escapes, raw C0 bytes,
duplicate declared keys, and malformed text in ignored keys or values. Unknown keys retain the
existing ignore behavior, including repeated unknown keys. `\u0000` becomes one embedded
NUL byte. The `OwnedTask` pair below is a separate owned-materialization golden fixture derived from
that earlier grammar, not a second lexical source of truth. The comparison is over JSON bytes before
any CLI newline. Request 7 may return an outside-arena error for an escaped borrowed view; Request 9
instead returns an owned value, so the shared grammar does not imply shared materialization behavior.

The normative owned-path golden pair is bytewise and independent of any future adoption file. It
includes one signed integer and one boolean so the owned route has a semantic-to-byte and
byte-to-semantic vector for its accepted Copy field domain:

```text
OwnedTask {
  id: string
  priority: i64
  attempts: u16
  limit: u64
  enabled: bool
  argv: array<string>
  note: Option<string>
}

input UTF-8 bytes:
{"id":"task-1","priority":-7,"attempts":3,"limit":18446744073709551615,"enabled":true,"argv":["","quote:\" slash:\/ backslash:\\ controls:\b\f\n\r\t","nul:\u0000","emoji:\ud83d\ude00"],"note":"\u20ac"}

canonical output UTF-8 bytes:
{"id":"task-1","priority":-7,"attempts":3,"limit":18446744073709551615,"enabled":true,"argv":["","quote:\" slash:/ backslash:\\ controls:\b\f\n\r\t","nul:\u0000","emoji:😀"],"note":"€"}
```

The output pair is compared before a CLI newline. The `limit` field is the `u64::MAX` boundary
vector: its decimal bytes must survive decode/encode without signed conversion. The null and omitted-note cases are separate
vectors: both decode to None, while Some(empty) is encoded as an explicit empty JSON string.
The exact optional-note vectors are:

```text
omitted-note input UTF-8 bytes:
{"id":"task-1","priority":-7,"attempts":3,"limit":18446744073709551615,"enabled":true,"argv":[]}

omitted-note canonical output UTF-8 bytes:
{"id":"task-1","priority":-7,"attempts":3,"limit":18446744073709551615,"enabled":true,"argv":[]}

null-note input UTF-8 bytes:
{"id":"task-1","priority":-7,"attempts":3,"limit":18446744073709551615,"enabled":true,"argv":[],"note":null}

null-note canonical output UTF-8 bytes:
{"id":"task-1","priority":-7,"attempts":3,"limit":18446744073709551615,"enabled":true,"argv":[]}

some-empty-note input UTF-8 bytes:
{"id":"task-1","priority":-7,"attempts":3,"limit":18446744073709551615,"enabled":true,"argv":[],"note":""}

some-empty-note canonical output UTF-8 bytes:
{"id":"task-1","priority":-7,"attempts":3,"limit":18446744073709551615,"enabled":true,"argv":[],"note":""}
```

`m5_owned_json.rs::owned_json_optional_note_byte_vectors` compares each input/output pair bytewise
before any CLI newline and separately checks the decoded `None`/`Some(empty)` states.
Deterministic validation and failure order is:

| Order | Validation |
| --- | --- |
| 1 | Compile-time parser/import/capability/arity and expected-record inference |
| 2 | Select the owned route only from a direct owned-text leaf; once selected, reject `layout(C)`, then `align(N)` |
| 3 | Validate fields in source order; within one field resolve the type, outer constructor, then exact integer width/sign or `string` payload. The first field failure is the sole graph diagnostic |
| 4 | Validate natural layout, recursive `DropPlan`, free-standing allocation mode, target-bound interface identity, and decode input type in that order |
| 5 | Recoverable runtime decode UTF-8/string grammar, then object syntax/duplicate/shape/range/array-element failures in input order, missing fields, trailing bytes, cleanup, and successful Move publication |
| 6 | Encode validates source place/target, then the same selector/attribute/source-field/layout/Drop/allocation/interface sequence, then canonical parts; bounded encode checks/evaluates its exact-`i64` limit only afterward |
| 7 | Consumer-only output clone, artifact validation, and file commit after encode; these are not Request 9 runtime errors |

### Ownership closure matrix

The matrix below is the reopened design gate. Before implementation, it must close the finite owned
numeric domain and its canonical
signedness tags, preserve the existing top-level scalar-array entrypoints, cleanup after a valid
object followed by non-whitespace trailing bytes, recoverable integer-range failure cleanup versus
terminal abort timing, the exact declared-key duplicate scope, deterministic cleanup order, the named
first expected consumer, operation-specific entrypoint routing including existing Move AoS/union
compatibility, same-process concurrency, separate capacity-overflow and allocator-failure policy, the
metric decision, optional-state byte vectors, target ABI baseline, configuration-boundary N/A decisions,
the selected-owned-path scope for unsupported optional owners while preserving the existing no-owned-
leaf route, the explicit free-standing JSON allocation mode inside an arena versus the existing arena
default, the required memory-model/spec source updates, and reproducible process-level regression names.
Align's reviewed design must keep the canonical implementation matrix in the authoritative JSON and
memory design, while this register records the adoption-visible coverage. A change to the ownership,
entrypoint, wire, capacity, metric, or concurrency boundary updates both documents before
implementation.

| Case | Exact owner | Exact regression |
| --- | --- | --- |
| Owned-path selection and field formation | `../align/crates/align_sema/src/lib.rs` owned-path selector beside `json_struct_fields_ok_rec`/`is_field_ok`, plus direct JSON descriptor validation | `m5_owned_json.rs::owned_text_field_formation_and_inference` covers the unchanged all-borrowed route, one-owned-leaf selection, Copy `int`/`bool`, `string`, direct `Option<string>`, direct `array<string>`, owned-path `float` rejection, missing expected type, mixed `str`/`array<str>`, nested-record, enum, and unsupported-option rejection before allocation; `m5_owned_json.rs::owned_json_copy_scalar_width_sign_range_and_bool` covers every accepted integer width/sign with `0 = signed` and `1 = unsigned`, including the full `u64` range and `u64::MAX` encode vector, range rejection, and boolean decode/encode; the same formation test rejects owned-path `layout(C)` and `align(N)` before allocation |
| Operation-specific target routing | `../align/crates/align_sema/src/lib.rs` direct-record selector plus unchanged `check_json_decode`, `check_json_scan`, fixed-`StructArray` encode, union, and all bounded target gates | `m5_owned_json.rs::owned_json_direct_record_target_selects_owned_path`, `owned_json_direct_record_encode_route`, `owned_json_direct_record_bounded_encode_route`, `owned_json_bounded_parity`, `owned_json_record_array_preserves_shipped_move_aos`, `owned_json_record_array_owned_text_rejected_before_owned_descriptor`, `owned_json_scanner_target_rejected_before_allocation`, `owned_json_non_record_targets_unchanged`, fixed-array unbounded/bounded route owners, and union unbounded/bounded route owners prove the new direct owned-text graph cannot widen scanner, new AoS, SoA, union, scalar, fixed-array, or existing Move-union routes |
| Top-level scalar-array target routing | `../align/crates/align_sema/src/lib.rs` `check_json_decode` `Ty::DynArray` branch and its existing `JsonDecodeArray` lowering; no `OwnedJsonDescV1` construction | Existing `m5.rs::json_decode_scalar_array` and `m5.rs::json_decode_float_array`, plus the new Align implementation regression `m5.rs::json_decode_bool_array` required because the pinned suite has only field-level bool-array coverage, cover the existing `array<i64>`, `array<f64>`, and `array<bool>` targets; `m5_owned_json.rs::owned_json_same_process_entrypoint_matrix` includes scalar-array decode as an independent concurrent entrypoint column |
| Direct `array<string>` type and `DropPlan` | `../align/crates/align_sema/src/lib.rs` pass 0b-2, `struct_is_move`/`drop_plan`; `../align/crates/align_codegen_llvm/src/lib.rs` field/drop lowering | `m5_owned_json.rs::owned_text_array_field_drop_plan` proves the direct array spine/owned-string element descriptor and rejects `Option<array<string>>`, nested arrays, and unsupported elements |
| Owned scalar text decode and free-standing allocation | `../align/crates/align_mir/src/lib.rs` JSON decode lowering, `../align/crates/align_runtime/src/lib.rs` owned string allocation, `../align/crates/align_sema/src/lib.rs` region/move checks, and the required allocation-mode update in `../align/docs/impl/08-memory-model-v2.md` / `../align/docs/impl/core-design/json.md` | `m5_owned_json.rs::decode_owned_string_field_detaches_from_input` drops the input before reading the result and returns/moves the free-standing owner; `m5_owned_json.rs::owned_decode_inside_arena_free_standing_result`, `owned_decode_inside_arena_source_drop_and_move_out`, and `owned_decode_inside_arena_failure_cleanup` are the required ownership tests for the newly authorized free-standing JSON terminal inside an arena; `m5_owned_json.rs::owned_encode_output_region_and_clone_boundary` separately rejects an arena-backed encoded view escaping |
| Arena allocation-mode source of truth | `../align/draft.md`, `../align/docs/language-spec.md`, `../align/docs/impl/08-memory-model-v2.md`, and `../align/docs/impl/core-design/json.md` must explicitly define and reconcile the JSON terminal's free-standing allocation inside an arena before implementation | The same `owned_decode_inside_arena_free_standing_result`, `owned_decode_inside_arena_source_drop_and_move_out`, and `owned_decode_inside_arena_failure_cleanup` tests must cover source drop, move-out, ordinary success cleanup, and recoverable failure cleanup; the implementation PR cannot reach `ALIGN_MERGED` while this source update or its tests is missing |
| Owned text-array spine, elements, and reallocation | `../align/crates/align_runtime/src/lib.rs` array spine/element allocation and typed decode | `m5_owned_json.rs::decode_owned_string_array_empty_many_and_nul` covers zero, one, many, reallocation, embedded NUL, and multibyte values; `m5_owned_json.rs::owned_text_array_move_out_and_drop` proves source nulling and exactly-once deep drop |
| Unsupported nested/mixed graph rejection | `../align/crates/align_sema/src/lib.rs` direct field walk and region/move checks | `m5_owned_json.rs::owned_json_rejects_nested_array_record_enum_and_mixed_view_graphs` proves rejection before any decode allocation |
| Optional owned text and null semantics | `../align/crates/align_runtime/src/lib.rs` missing/null/Some field paths and optional cleanup | `m5_owned_json.rs::decode_owned_option_string_states` covers missing/null → `None`, `Some(empty)`, and non-empty values; `m5_owned_json.rs::owned_json_optional_note_byte_vectors` provides exact omitted/null/empty input-output bytes; `m5_owned_json.rs::owned_option_replacement_drop` proves replacement cleanup; `m5_owned_json.rs::reject_unsupported_owned_options_before_allocation` rejects `Option<MoveStruct>`, `Option<OwnedRecord>`, `Option<array<string>>`, and move-enum payloads only after the owned direct-record selector is chosen, while the existing no-owned-leaf route remains unchanged |
| Decode recoverable failures and partial cleanup | `../align/crates/align_runtime/src/lib.rs` parse and semantic error edges, numeric range checks, top-level post-parse trailing-byte check, `drop_decoded_owned`, and direct-field cleanup; `../align/crates/align_mir/src/lib.rs` failure CFG | `m5_owned_json.rs::owned_decode_partial_failure_cleans_every_live_owner` covers recoverable malformed escapes, wrong shapes, truncation, duplicate declared keys, out-of-range integers, live `Some(string)`, array-spine publication/reallocation, `?`, `else`, `map_err`, and branch joins without nested/AoS claims; `m5_owned_json.rs::owned_decode_trailing_garbage_cleans_every_live_owner` covers a valid object followed by non-whitespace bytes and proves the top-level error path frees every direct owner; terminal capacity/allocator aborts are covered separately and are excluded from this cleanup guarantee |
| Deterministic owned-value cleanup order | `../align/crates/align_codegen_llvm/src/lib.rs` canonical `DropPlan`/record cleanup and `../align/crates/align_runtime/src/lib.rs` direct decoded-owner cleanup | `m5_owned_json.rs::owned_json_cleanup_order_is_declaration_and_element_order` uses permuted JSON key order and injected failure/ordinary `Drop` paths to assert source declaration-order field cleanup, ascending initialized `array<string>` element-index cleanup, optional payload cleanup within its field, and array-spine release after its elements; all initialized owners are released exactly once |
| Move-in, move-out, return, and source nulling | `../align/crates/align_sema/src/lib.rs` MoveCheck and `../align/crates/align_mir/src/lib.rs` transfer/null cleanup | `m5_owned_json.rs::owned_json_move_source_null_and_return_cleanup` covers direct `?`, same-scope `match`, raw `Result<OwnedRecord, Error>` bind/parameter/return/reassignment, `map_err`, and exactly-once source nulling/cleanup |
| Reassignment, replacement, and all control-flow joins | `../align/crates/align_sema/src/lib.rs` `MoveCheck`/`BorrowState` assignment state and `../align/crates/align_mir/src/lib.rs` `drop_old`, branch/loop cleanup CFG | `m5_owned_json.rs::owned_option_replacement_drop` and `m5_owned_json.rs::owned_json_all_control_flow_cleanup` cover `if`, `match`, `else`, `?`, `map_err` mapper early exit, value-carrying `break`, loop back-edges, early return, malformed input, and source/owner reset; `continue` is N/A because Align has no such construct |
| Owned encode field order, signedness, limits, and escapes | typed MIR `IntHole`; `BuilderWriteInt` plus new keyed A66 `BuilderWriteUint`; declared encoder descriptor and string/array writers | `template_unsigned_decimal_boundaries`, `m5_owned_json.rs::encode_owned_json_canonical_bytes`, and `owned_json_bounded_parity` prove every integer width/sign including `u64::MAX`, unbounded/bounded byte parity and exact/rejected limits, declaration order, escapes, embedded NUL, empty arrays, text-array order, and no source mutation |
| Encode output region and explicit persistence clone | `../align/crates/align_sema/src/lib.rs` region escape checks and `../align/crates/align_runtime/src/lib.rs` output builder | `m5_owned_json.rs::owned_encode_output_region_and_clone_boundary` proves arena result expiry, outside hidden-owner lifetime, explicit clone before persistence, and rejection of a dangling return |
| Encode/decode semantic and byte round-trip | `../align/crates/align_mir/src/lib.rs` JSON nodes plus runtime codec | `m5_owned_json.rs::owned_json_encode_decode_encode_identity` proves semantic equality and byte identity while source, decoded, and cloned-output owners remain live |
| Input/source lifetime boundary and mixed records | `../align/crates/align_sema/src/lib.rs` region/drop checks | `m5_owned_json.rs::owned_decode_has_no_input_region_dependency` drops input before using every owned field and rejects treating a mixed borrowed `str` record as `Owned*` |
| Generic and imported graph parity | `../align/crates/align_sema/src/lib.rs` substitution; `../align/crates/align_driver/src/lib.rs` format-7 interface emission and target envelope | `generics.rs::owned_json_direct_grammar_substitution` and `per_unit.rs::owned_json_imported_direct_graph_parity` cover only accepted direct shapes, consumer-created concrete monomorph envelopes, non-generic exported descriptor-list entries, and equivalent rejection |
| Structural identity, natural layout, and cache | `../align/crates/align_driver/src/lib.rs` existing structural/interface cache identity plus the new natural-layout-only `OwnedJsonDescV1` descriptor; `../align/crates/align_sema/src/lib.rs` layout validation; `../align/crates/align_codegen_llvm/src/lib.rs` `logical_to_physical`, `field_byte_offset`, and target `Option` payload/tag offsets | `cache_codegen.rs::owned_json_descriptor_golden_and_definition_edit_revert_identity` proves the natural-layout header and algorithm, fixed tags/widths, explicit `0 = signed`/`1 = unsigned` payload mapping, signed/unsigned golden fields including `u64::MAX`, record-base-relative physical payload/tag offsets for a nonzero-position optional field, target-local sizes/alignments, cold hit, definition edit miss, revert identity, explicit `layout(C)`/`align(N)` rejection, and stale descriptor rejection; `interface_param_modes.rs::owned_json_descriptor_physical_layout_mismatch_rejected` rejects an algorithm, payload offset, optional tag offset, or layout mismatch before field access, cleanup, or codegen |
| ABI descriptor, interface version, runtime writer, and allocation parity | format-7 interface codec and `OwnedJsonInterfaceEnvelopeV1`; codegen ABI/drop descriptors; new `BuilderWriteUint` key/export; runtime ownership flags | independent 270-byte envelope/hash and 214-byte descriptor goldens, v6 `UnknownVersion(6)` before list parse, every list/envelope/descriptor mutation, key↔symbol and registry-count parity, `interface_param_modes.rs::owned_json_direct_drop_descriptor_abi`, `m5_owned_json.rs::owned_json_whole_program_per_unit_allocation_parity`, and `owned_json_allocation_transfer` |
| Capacity overflow | `../align/crates/align_runtime/src/lib.rs` checked element-count/byte-count arithmetic for owned array decode and checked builder length/growth arithmetic for owned encode | `m5_owned_json.rs::owned_json_decode_capacity_overflow_terminal_child` and `m5_owned_json.rs::owned_json_encode_capacity_overflow_terminal_child` cover decode growth and encode growth independently; each proves terminal non-zero exit and no successful partial record/string |
| Allocator failure | `../align/crates/align_runtime/src/lib.rs` allocator/cleanup and the Align test-only child-process failpoint | `m5_owned_json.rs::owned_json_allocation_transfer` covers recoverable parse/type failures; `m5_owned_json.rs::owned_json_allocator_failure_terminal_child` records the distinct terminal allocator-abort policy for direct fields, text-array growth, and output-builder growth and explicitly makes no cleanup-after-abort claim |
| Same-process and process concurrency policy | per-call parser, destination, temporary-owner, and output-builder state in `../align/crates/align_runtime/src/lib.rs`; immutable descriptor tables may be shared; no process-global mutable codec state or codec-instance API is added | `m5_owned_json.rs::owned_json_same_process_entrypoint_matrix` runs the full 153-pair unordered `J × J` operation-variant matrix, including diagonals, existing-only pairs (`BD + AD`, `DOC + SCAN`, `FE + UE`), and every unbounded/unbounded, unbounded/bounded, bounded/bounded, and cross-target pair named in item 9; every pair is supported concurrently, not serialized or pre-rejected; `cache_parallel.rs::owned_json_two_processes` confirms independent processes have the same no-shared-state policy |
| Existing borrowed and shipped Move JSON compatibility | `../align/crates/align_sema/src/lib.rs` target-specific predicates plus existing runtime template/descriptor/union paths | `m5.rs::json_decode_struct_array_len`, `json_decode_struct_array_malformed_errors`, existing `owned_tagged_payloads.rs::retained_result_with_recursive_move_payload_is_supported`, `m5_owned_json.rs::owned_json_record_array_preserves_shipped_move_aos`, `owned_json_fixed_struct_array_encode_route_unchanged`, `owned_json_union_encode_route_unchanged`, and Request 7's escaped-view tests remain green; no new `OwnedJsonDescV1` route is used |
| Metric / benchmark decision | Request 9 public contract item 11; allocation instrumentation in `../align/crates/align_runtime/src/lib.rs` and whole-program/per-unit test harness | `m5_owned_json.rs::owned_json_whole_program_per_unit_allocation_parity` is the required correctness measurement; no performance benchmark or threshold is claimed because this is a correctness prerequisite, and a later optimization must register its own workload and baseline |
| First expected consumer and lifecycle | `docs/specs/roadmap.md` named `C7-PersistedResult` slice, `docs/specs/c7-persisted-result.md`, and Request 9 lifecycle metadata | The C7 design names direct `string` and direct `Option<string>` records and reclassifies Request 9 as blocking for C7 implementation/adoption; Request 9 remains independently implementable only in Align, while C7 waits for its named Align commit and real-client gate |
| Target ABI baseline and target-local descriptor exchange | `../align/crates/align_driver/src/lib.rs` target-triple/interface identity and exact envelope, `../align/crates/align_codegen_llvm/src/lib.rs` natural layout, and `../align/docs/impl/11-release-distribution.md` supported release environments | `interface_param_modes.rs::owned_json_target_abi_descriptor_matches_target` runs the required `x86_64-unknown-linux-gnu` baseline and the `aarch64-unknown-linux-gnu`/`aarch64-apple-darwin` release-target acceptance environments; independent envelope golden and `owned_json_target_abi_mismatch_rejected` reject triple/object-format/ABI/hash mismatches before descriptor length or code generation |
| Normative syntax and baseline declaration | `../align/crates/align_fmt` parser/formatter for the proposed source fixture; no product path consumes it | `docs/examples/request9-owned-json-syntax.align` passes the pinned `alignc fmt` parser-only check; declarations and positional calls are shown as separate blocks in this register. The required platform baseline and release-target environments are the target-ABI tests above; parser formatting remains a separate syntax check |
| CLI/build and option/environment boundaries | N/A: Request 9 adds no CLI flag, build setting, profile, artifact-selection input, option state, environment variable, or persistent boundary; only source declarations and explicit function arguments are inputs, and no ambient configuration may affect the route | N/A by design; there is no new accepted/rejected state to isolate or preserve across a configuration boundary, while the pinned compiler/runtime revision remains a development prerequisite rather than a runtime option |

### Align acceptance gate

Before any owned-path implementation starts, Align must update `../align/draft.md`,
`../align/docs/language-spec.md`, `../align/docs/impl/08-memory-model-v2.md`, and
`../align/docs/impl/core-design/json.md` to authorize the JSON materializing terminal's explicit
free-standing allocation inside `arena {}` while preserving the existing arena default for ordinary
owned values. That source update must land with
`m5_owned_json.rs::owned_decode_inside_arena_free_standing_result`,
`owned_decode_inside_arena_source_drop_and_move_out`, and
`owned_decode_inside_arena_failure_cleanup`, which cover source drop, move-out, success cleanup,
recoverable failure cleanup, and the result's ability to outlive the input. Request 9 cannot reach
`ALIGN_MERGED` on the pinned memory-model contradiction alone.

Before Align marks Request 9 `ALIGN_MERGED`, focused tests must prove:

1. A direct record with no owned text leaf continues through the existing borrowed/all-borrowed
   codec, including its shipped `str`/`array<str>`, nested/array-struct, and union forms. Existing
   top-level AoS decode, fixed struct-array encode, and union encode targets—including shipped Move
   element/union graphs—continue through their existing target modes. A flat declared record
   with a direct owned text leaf plus Copy `int`/`bool` fields at every supported integer width and
   signedness, `string`, direct `Option<string>`, and direct `array<string>` fields passes the owned
   descriptor formation correctly; a width-64 unsigned field accepts and re-encodes `u64::MAX`
   through the full-range unsigned writer rather than a signed `i64` writer. JSON integer range
   failures return a recoverable decode error and use item 4's cleanup path when earlier owners are live, while an owned-path `float` field rejects
   at descriptor formation before runtime allocation and boolean true/false values round-trip. Mixed borrowed fields,
   nested records, `array<Struct>`, enum/sum fields, owned-path `layout(C)`/`align(N)`,
   `Option<MoveStruct>`, `Option<OwnedRecord>`, `Option<array<string>>`, unsupported generic
   substitutions, and missing expected types reject at owned descriptor formation before runtime
   allocation. This rejection applies only after the direct owned-text selector is chosen; a direct
   record with no owned text leaf remains on the existing JSON route, including any pre-existing
   `Option<MoveStruct>` behavior, while general language formation of `Option<MoveStruct>` remains
   supported.
2. Existing top-level scalar-array decode remains unchanged for `array<i64>`, `array<f64>`, and
   `array<bool>`, independently of the new direct owned-record selector. Owned scalar and direct
   runtime-sized text-array fields decode for empty, one, many, NUL, and
   multibyte values; the input can be dropped before all owned fields are read. New Request 9 nested
   and top-level owned-text record-array routes are explicitly out of scope, while existing shipped
   Move AoS/union record-array targets remain covered by their compatibility regressions.
3. Missing and `null` both decode to `None`, `Some(empty)` is distinct from `None`, and `None` is
   omitted by encode. The omitted-note, null-note, and Some(empty)-note byte vectors above are
   compared independently by `m5_owned_json.rs::owned_json_optional_note_byte_vectors`. Required
   fields reject both missing and `null`, `null` array elements reject with the existing type error,
   and optional values are cleaned exactly once on success, replacement, move-out, and failure.
4. Malformed syntax, the inline owned-path escape vectors, wrong shapes, truncation, duplicate
   declared keys, out-of-range integer values, non-whitespace trailing bytes after an otherwise valid
   object, and mid-`array<string>` failures return the deterministic recoverable error and free every
   initialized direct owner, including a live `Some(string)`, without a leak, double free, panic, or
   successful partial record. Cleanup is asserted in source declaration order, with initialized
   text-array elements in ascending index order before their spine, and is independent of JSON key
   order. Repeated unknown keys remain ignored after their values pass the shared grammar. Capacity
   overflow and allocator failure remain terminal aborts covered by item 7 and have no cleanup-after-
   abort assertion.
5. Owned records encode with canonical declaration order and exact inline-vector bytes for escapes,
   embedded NUL, the full `u64::MAX` decimal boundary, empty text arrays, multibyte text, and all
   three optional-note states without consuming or mutating the source. A width-64 unsigned field
   must use a full-range unsigned writer and never pass through a signed `i64` intermediate.
   `json.encode_bounded` accepts the same graph, produces byte-identical success at exact fit, and
   returns `Error.Invalid` for a negative or first-byte-over-limit ceiling without a partial value.
6. `decode -> encode -> decode` preserves semantic owned values and `encode` bytes while the source
   and output owners are independently live; the output does not borrow source text.
7. Generic, imported/per-unit, cache-cold/edit/revert, `OwnedJsonDescV1` ABI descriptor including
   the pinned natural-layout algorithm, every logical field's physical payload offset and optional
   tag offset, explicit signed/unsigned descriptor tags, raw-`Result` bind/parameter/return/reassignment and typed
   `map_err` transfer, the complete same-process entrypoint
   matrix including all 153 unordered operation-variant pairs and every unbounded/bounded target
   variant in item 9, existing scalar-array
   target regressions (`m5.rs::json_decode_scalar_array`, `json_decode_float_array`, and the new
   Align implementation regression `json_decode_bool_array`), existing Move AoS/fixed-array/union
   target compatibility, reconciliation of the stale `option-result.md`/`json.md` Move-result
   prose and the arena allocation-mode source update at named Align commits,
   `m5_owned_json.rs::owned_decode_inside_arena_free_standing_result`,
   `owned_decode_inside_arena_source_drop_and_move_out`,
   `owned_decode_inside_arena_failure_cleanup`, `cache_parallel.rs::owned_json_two_processes`,
   `m5_owned_json.rs::owned_json_cleanup_order_is_declaration_and_element_order`,
   `m5_owned_json.rs::owned_json_decode_capacity_overflow_terminal_child`,
   `m5_owned_json.rs::owned_json_encode_capacity_overflow_terminal_child`, and
   `m5_owned_json.rs::owned_json_allocator_failure_terminal_child` have the same validation and
   ownership result. Capacity overflow and allocator failure are distinct terminal policies under
   the pinned runtime; neither returns a recoverable error or successful partial result, and no
   cleanup-after-abort path is promised.
8. Existing `str`/`array<str>` zero-copy behavior and Request 7's separately tracked escaped-view
   behavior remain unchanged. Request 9 does not claim to close Request 7.
9. A future named align-llm adoption checkpoint, implemented on a branch with its concrete consumer,
   must construct the flat owned record, drop the input, encode the inline canonical bytes, decode
   again, and exercise direct text-array cleanup. That named target, the consumer qualification, and
   the capability's one final `make ci` may advance Request 9 to `ALIGN_LLM_VERIFIED`; this proposal
   does not claim that target or its fixture exists.

10. The metric decision is explicit: Request 9 makes no performance claim or threshold. The
    whole-program/per-unit allocation-parity measurement must pass, and any speed/size optimization
    is deferred to a separately designed benchmark slice.

11. The normative syntax fixture `docs/examples/request9-owned-json-syntax.align` passes the pinned
    `alignc fmt` parser-only check and contains the declaration, positional call, raw-`Result` bind/
    parameter/return examples, and explicit typed `map_err`/`?` form shown above. The declaration and
    positional call are separately shown above; no current `alignc check` result is claimed for the
    proposed `string`/`array<string>` field surface. The required target-ABI baseline and release
    target acceptance environments in item 12 are exercised by the named interface regressions.

12. Request 9 introduces no CLI/build input and no option/environment isolation boundary. Its
   source declarations and explicit `json.decode`/`json.encode`/`json.encode_bounded` arguments are the complete input
    surface; no ambient configuration may change route selection, descriptor identity, allocation,
    parsing, encoding, or cleanup. The closure matrix records both dimensions as N/A with these
    reasons, and the pinned compiler/runtime revision is not treated as a runtime option.

The adoption target is separate from Align implementation. For the first named consumer, the C7
slice in `docs/specs/c7-persisted-result.md` rebuilds the sibling release compiler and runtime from
the `ALIGN_MERGED` commit, updates `.align-revision`, creates its exact bytewise fixture, and runs it
through the common fresh-compiler topology. Other consumers must name their own accepted graph and
adoption evidence before they become dependent on this request.

### References

- `../align/docs/impl/core-design/json.md` §§3–4 — current declared JSON field domains, borrowed
  `str`/`array<str>` ownership, and the deferred `array<string>` field.
- `../align/draft.md` and `../align/docs/language-spec.md` — the public ownership and allocation
  rules that must be updated to authorize this explicit JSON terminal mode without changing the
  ordinary arena default.
- `../align/docs/impl/core-design/option-result.md` and `../align/docs/impl/07-roadmap.md` — the
  roadmap's L1b completion status, the stale per-area Move-result design prose, and the source pair
  that the Align implementation PR must reconcile against the pinned compiler/test evidence before
  this request reaches `ALIGN_MERGED`.
- `../align/docs/impl/08-memory-model-v2.md` §§6–8 and 11 — the pinned ordinary arena/free-standing
  ownership rule, materializing-terminal bounds, Move cleanup, and declared dynamic-array field
  boundaries; the Align implementation must add the explicit JSON-terminal allocation exception
  here before this request is implementable.
- `../align/docs/impl/11-release-distribution.md` — supported compiler/runtime release targets and
  required baseline environments for the target-local ABI descriptor.
- `../align/crates/align_sema/src/lib.rs` — `json_struct_fields_ok_rec`, `is_field_ok`, field
  formation, structural `DropPlan`, and current `array<string>` rejection.
- `../align/crates/align_mir/src/lib.rs` and `../align/crates/align_runtime/src/lib.rs` — current
  JSON lowering, descriptor-driven parse/encode, and cleanup paths.
- `../align/crates/align_driver/tests/m5.rs` — shipped declared JSON regressions.
- `../align/crates/align_driver/tests/owned_tagged_payloads.rs` — shipped recursive Move payload and
  Move AoS/union compatibility regressions.
- `docs/examples/request9-owned-json-syntax.align` — parser-only syntax fixture for the proposed
  declaration and positional call; it is not a product example consumed by `make check`.
- `docs/specs/roadmap.md` and `docs/specs/align-llm.md` — the committed roadmap and architecture
  that future consumers must refine before adoption.

---

## Request 10 — `core.array_builder`: recursive evaluator record fields

```text
Status: CLOSED
Priority: high
Blocking: yes
Blocked gate or slice: C6f2 deterministic paired evaluator and C6c2 decoded evaluation verifier; Requests 8 and 10 supply the recursive runtime-sized result arrays, which C6c2 cannot consume until the named real-client adoption and shared consumer pin wave pass
Independent work that may continue: C6c2 design, C6a1 codec work that does not materialize recursive runtime arrays, C6b, C6c, C6d, Request 5, Request 6, Request 7, Request 8, Request 9, and verification work that does not construct the blocked record graph
Resume condition: satisfied by the C6-LIFECYCLE pin wave and Align-llm PR #94; the later C6c2 verifier still owns its separate recursive evaluator record graph
Align commit or pull request: Align design PR #802, merged as `8fdb274eb98f8aba362d0bea6ba5729f4ed22479`; implementation PR #804, merged as `3ec710656c7ce7412da14a5c929529cb3e89caa3`
align-llm verification: PR #94 merged as `ba56ebed5ac1c82ebc5925e6257e7bd5dba8a9b9`; ordered `c6c2-request10-adoption` passed after Request 8, against `.align-revision` `a440970ac81118ed2169f600b2b3c06fcb9cde7`, and final capable `make ci` passed in CI run `32109434515` at head `954258e24d93300dcdb78f8280de8868cf1ced56`; merge run `32111007638` reused the exact evidence
```

### Motivation

C6f2 discovers task, row, aggregate, snapshot, and regression cardinalities while it evaluates a
fixed corpus. The evaluator therefore needs ordinary declared Align records inside runtime-sized
arrays. Request 8 provides the recursively Copy, owned-record base, but its accepted graph
deliberately excludes `Option<T>` and dynamic `array<T>` fields. C6's exact records contain both,
including nested arrays and optional embedded records. Treating Request 8 as sufficient would
silently require a shallow copy or a private collection implementation.

### Current-state evidence at the pinned Align revision

At `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e`, Request 8's `array_builder<T>` element predicate
rejects the C6 record shapes that contain `Option`, nested dynamic arrays, or arrays of records.
The declared JSON array route is a decode path, not a mutable append API for evaluator control flow.
Request 9 owns direct owned JSON text fields and is not a substitute for a record builder. The
request remains a genuine Align ownership and lowering boundary; align-llm must not encode JSON
fragments and parse them back or add a private vector.

### Requested capability

Extend the reviewed Request 8 builder using its expected-type, data-oriented construction idiom.
The exact public spelling is an Align design decision, but it must accept an `EvaluatorRecord<T>`
graph whose leaves are Copy scalars or owned `string`, and whose recursive fields are only:

- another accepted declared record;
- `Option<T>` where `T` is accepted recursively; or
- `array<T>` where `T` is accepted recursively.

`str`, slices, resources, functions, raw pointers, builders, and region-bound values are rejected
in the graph. Every nested array and option is a separately owned value; no shallow byte copy or
arena alias is allowed. The builder must specify source nulling, move-out, replacement, reallocation,
abandonment, and `Drop` behavior for every partial state.

C6 names these first exact consumers: `SnapshotRequest`, `PromptEvaluationTask`, `PromptTaskRow`,
`TaskAggregate`, `CorpusAggregate`, `RegressionReason`, `RunSnapshotAttestation`, `SnapshotResult`,
and `TaskInputSnapshot`, including their top-level result collections. The Align request must not
generalize beyond the recursively accepted graph needed by those records.

### Acceptance criteria

The Align implementation and its align-llm adoption target must prove, with declarations shown
separately from positional calls:

1. recursive type formation rejects every unsupported leaf and admits every named C6 shape;
2. empty and non-empty arrays, `Option.None`, `Option.Some`, nested arrays, and nested records
   have exact ownership and allocation behavior;
3. push, reallocation, build, abandonment, replacement, and partial construction clean every
   live child exactly once, including `?`, `map_err`, branch joins, loop exits, and enclosing-record
   failure;
4. generic monomorphization, per-unit and whole-program compilation, interface serialization, and
   cache identity agree on the structural record graph;
5. allocation parity is measured against the ordinary declared-record representation, and no
   hidden arena or private collection is introduced; and
6. C6f2 constructs and drops the named records through the shipped surface, then passes its focused
   runtime-array, malformed-input, early-exit, and cleanup qualification; the C6c2 consumer runs
   `c6c2-request10-adoption` for the recursive Request 10 subset before verifier implementation
   consumes it on the same C6-LIFECYCLE branch.

The C6c2 adoption is an ordered checkpoint inside the verifier capability, not a separate merge.
Its `c6c2-request10-adoption` target is allowed only after the named Request 8 and Request 10 Align
commits are pinned; it constructs the exact recursive C6 record graph and exercises `Option.None`,
`Option.Some`, nested arrays, reallocation, partial failure, and `Drop`. The verifier implementation
then consumes that proven surface on the same branch, and one final `make ci` runs after integrated
owner checks pass. The later `c6f2-array-builder-adoption` remains the paired-evaluator consumer
evidence.

### References

- `../align/docs/language-spec.md` §§7–8 and `../align/docs/open-questions.md` §array_builder —
  current builder forms, element restrictions, and the unresolved recursive extension.
- `../align/docs/impl/08-memory-model-v2.md` — recursive Move cleanup, region boundaries, and
  allocation ownership.
- `../align/crates/align_sema/src/lib.rs` and `../align/crates/align_mir/src/lib.rs` — type
  formation, lowering, and `DropPlan` owners at the pinned revision.
- `docs/specs/c6-prompt-context-optimizer.md` §4.5 — the exact first consumer record shapes.

---

## Request 11 — `std.process`: bounded child output capture

```text
Status: CLOSED
Priority: high
Blocking: no
Blocked gate or slice: none; the merged C6-EVALUATION contained evaluator consumes the shipped bounded capture
Independent work that may continue: all work
Resume condition: complete
Align commit or pull request: Align design PR #806, merged as `30ff5830ce556e949edf31500a154ca7de4b1b7c`; implementation PR #808, merged as `82da9f580cc005fbb78f67af6847c7b4ce6626c4`
align-llm verification: focused `c6f1-request11-adoption` and the reopened evaluator runtime-containment owner pass at Align `19c3db144c462bf7d6784f88d64cc124229b7ec2`, including exact-cap, cap-plus-one, simultaneous streams, timeout, post-EOF, repeated/concurrent invocation, retained executable identity, and descendant cleanup; the final capable integration gate passed at PR #100 head `049172f5be57002c2426f012fe23038f570f5069` (CI run 32490981785, both installed native profiles) and merged as `282062bf00416f5e0df678b8bd885709084b4e16`
```

### Motivation and current-state evidence

C6 invokes a trusted snapshot helper and task adapter as external processes. Its contract requires
hard stdout/stderr bounds before allocation, but the pinned `std.process.run()` drains both pipes
into unbounded buffers. `../align/docs/impl/std-design/process.md` P12 explicitly records
unbounded v1 capture and defers `max_capture`/the bytes tier. A post-capture length check is not a
memory or process-safety bound and cannot satisfy C6.

### Requested capability

Add an explicit command-local capture limit, for example a reviewed `max_capture_bytes(limit)`
configuration or an equivalent bytes-tier API. The final API must define whether the limit is per
stream or total, reserve no capacity above the declared limit, drain without deadlock, and on
exceeding the limit kill and reap the child or process group before returning a deterministic
limit error. It must define whether partial bytes are retained, and must not report a successful
run after truncation. Existing uncapped callers remain unchanged only if that compatibility is
explicitly tested.

### Acceptance criteria

Align tests and the C6 adoption target must cover stdout-only and stderr-only over-cap output,
simultaneous pipe pressure, exact-limit output, one-byte overflow, timeout-plus-cap precedence,
nonzero exit, invalid UTF-8 in the bytes tier, process-group cleanup, repeated command reuse,
concurrent independent commands, and allocation/cleanup after every error. C6 must use the
shipped cap for its 65,536-byte helper response and 262,144-byte measurement response; it may not
claim a bound using `run()` followed by a length check.

### References

- `../align/docs/impl/std-design/process.md` §§4, 8, and P12 — shipped `run()` behavior and the
  recorded deferred capture-cap boundary.
- `../align/crates/align_runtime/src/lib.rs` and
  `../align/crates/align_driver/tests/m11_process_command.rs` — current pipe draining, timeout,
  kill, reap, and environment implementation.
- `docs/specs/c6-prompt-context-optimizer.md` §§4.5, 9, and 10.1 — C6 process limits and cleanup.

---

## Request 12 — `core.json`: bounded canonical encoding

```text
Status: CLOSED
Priority: high
Blocking: yes
Blocked gate or slice: C6a1/C6a2 canonical artifact persistence and every C6 slice that writes a result with a declared raw-byte cap
Independent work that may continue: pure prompt rendering, scoring, and design work that does not encode a capped persisted artifact
Resume condition: satisfied by the C6-LIFECYCLE pin wave and Align-llm PR #94; later result/evidence publication remains owned by C6f2 and Request 14
Align commit or pull request: Align design PR #805, merged as `95c559ed29c2451c4c09b289f37eefd421194cfb`; implementation PR #807, merged as `c37d79a180612c345551e259091b0b5acf2cb9cd`
align-llm verification: PR #94 merged as `ba56ebed5ac1c82ebc5925e6257e7bd5dba8a9b9`; ordered `c6-json-bounded-encoding-adoption` passed exact-cap, overflow, malformed-input, and cleanup cases against `.align-revision` `a440970ac81118ed2169f600b2b3c06fcb9cde7`, and final capable `make ci` passed in CI run `32109434515` at head `954258e24d93300dcdb78f8280de8868cf1ced56`; merge run `32111007638` reused the exact evidence
```

### Motivation and current-state evidence

C6 promises that a prompt evaluation result is at most 268,435,456 raw bytes and that an oversized
result is rejected without allocating or writing that artifact. The pinned `core.json.encode`
returns a complete owned `str`; it provides no cap-aware writer or preflight size contract. A
post-encode length check therefore allocates the complete result and cannot satisfy the promised
bound.

### Requested capability

Extend the existing canonical declared-record encoder with an explicit bounded operation, such as
`json.encode_bounded(value, max_bytes) -> Result<string, Error>`, or an equivalent bounded writer
chosen by Align. The bounded result must be byte-for-byte identical to `json.encode` when it fits,
reject at the first byte beyond the limit with a deterministic limit error, never expose partial
success, and define allocation and recursive cleanup on every failure. It must preserve the
existing field order, escaping, omitted-`None` behavior, unknown-field behavior, and no dynamic
JSON value type.

### Acceptance criteria

The Align implementation and C6 adoption target must cover exact-limit and limit-plus-one cases,
escape expansion, nested records, options, arrays, empty values, malformed descriptors, checked
size overflow, allocation failure, partial writer cleanup, and semantic-to-byte golden vectors.
C6a1 and C6a2 must use this surface before constructing a capped persisted artifact; they must not
encode unboundedly and then discard an oversized string.

### References

- `../align/docs/impl/core-design/json.md` §§2–4 — canonical field order, escaping, and current
  complete-string encoder.
- `../align/crates/align_runtime/src/lib.rs` and the JSON driver tests — current encoder allocation
  and cleanup behavior.
- `docs/specs/c6-prompt-context-optimizer.md` §§4.1 and 5.2 — C6 identity and result caps.

---

## Request 13 — `core.json`: recursive owned C6 artifact graphs

```text
Status: CLOSED
Priority: high
Blocking: yes
Blocked gate or slice: C6a1/C6a2 canonical artifact declarations and every C6 command that persists a nested result
Independent work that may continue: C6b/C6c pure rendering and scoring, C6d fixture-only state work, Request 5, Request 7, Request 9, Request 11, Request 12, and any work that does not persist the recursive C6 graph
Resume condition: satisfied by Align-llm PR #94; C6a1/C6a2 is now the shipped consumer-complete graph/codec boundary, with later renderer, verifier, evaluator, and activation cells deferred to their named owners
Align commit or pull request: design PR #853, merged as `6160d0540174577edf927b34630df9d309ce4395`; implementation PR #854, merged as `340a3304724fefb56c2b1aa642e6b2b2c169e6d7`
align-llm verification: PR #94 merged as `ba56ebed5ac1c82ebc5925e6257e7bd5dba8a9b9`; the ordered C6a1/C6a2 owners (`c6-json-decoded-owner-adoption`, `c6-json-escape-adoption`, recursive graph, Request 8/10, bounded encoding, and prompt artifact adoption) passed against `.align-revision` `a440970ac81118ed2169f600b2b3c06fcb9cde7`, and final capable `make ci` passed in CI run `32109434515` at head `954258e24d93300dcdb78f8280de8868cf1ced56`; merge run `32111007638` reused the exact evidence
```

### Align implementation (2026-08-18 — merged #854)

PR #854 ships the accepted recursive owned JSON graph for the existing inferred
`json.decode`, `json.encode`, and `json.encode_bounded` surface. It supports the
target-bound C6 graph of signed and unsigned 8/16/32/64-bit integers, `bool`,
owned `string`, records, one `Option` layer, and dynamic arrays of scalar,
string, or record elements. The checked-in fixture covers the exact 50-record,
543-field C6 declaration graph; unsupported borrowed views, nested options,
composite array elements, nested dynamic arrays, fixed arrays, floats, enums,
explicit layouts, and other constructors remain rejected before descriptor
construction or allocation.

Decode materializes a free-standing `Static` result independent of the input
and of `arena {}`. Reachable strings, owning option payloads, array spines, and
owning elements are recursively transferred and cleaned exactly once across
success, failure, moves, replacement, returns, joins, and early exits. The
implementation replaces V1 with target-bound `OwnedJsonGraphDescV2` and
`OwnedJsonInterfaceEnvelopeV2`, advances interface format 7 to 8, uses
structural complete-graph identity for interface/per-unit/cache validation, and
leaves the runtime ABI export counts unchanged. Constructor depth is bounded at
128 (root depth one, with every record, option, and dynamic-array edge counted),
including deeper paths through shared DAG nodes.

The accepted Align design is `../align/docs/impl/25-recursive-owned-json-plan.md` at
`6160d0540174577edf927b34630df9d309ce4395`. It keeps the existing inferred
`json.decode`, `json.encode`, and `json.encode_bounded` surface and selects one
free-standing route for a nonempty natural-layout record whose complete acyclic
graph contains an owned `string`. The closed graph admits signed/unsigned
8/16/32/64-bit integers, `bool`, owned `string`, records, one `Option` layer, and
dynamic arrays of scalar/string/record elements; it rejects borrowed views,
nested options, composite array elements, floats, enums, explicit layouts, and
every other constructor before allocation. Constructor depth is bounded at 128.

The design pins the clean C6 source provenance and an Align-owned exact
50-record/543-field declaration manifest, selecting the seven-field C6b-memory
`ContextPolicy`; sibling source is never a compiler-test input. It atomically
replaces flat `OwnedJsonDescV1` with target-bound `OwnedJsonGraphDescV2` and
`OwnedJsonInterfaceEnvelopeV2`, advances interface format 7 to 8 without a
compatibility decoder, and keeps the runtime ABI at 294 keyed / 307 base / 315
maximum exports. A103 decode and A80 encode remain the runtime calls. The
implementation must land the descriptor, interface/cache, HIR/MIR, allocation,
recursive cleanup, canonical-byte, C6 graph, and concurrency matrix as one
consumer-complete capability; until then Request 9's flat route is the shipped
behavior.

### Motivation and current-state evidence

C6 artifacts are declared records with nested records, `Option<T>`, runtime-sized arrays, and
persistent text. At the pinned Align revision, `json.decode` exposes `str` views into its input and
the shipped encoder does not accept the owned `string`/`array<string>` graph needed after that input
is dropped. Request 9 deliberately handles only flat direct-owned text fields and excludes nested
owned graphs; Request 8/10 handle evaluator construction but do not provide a JSON wire boundary.
The current application cannot safely retain a borrowed view, concatenate JSON fragments, or add a
private dynamic value tree. This is therefore a distinct Align capability, not an align-llm
workaround.

### Requested capability

Extend the declared-record JSON route with one explicitly owned C6 graph selector. The accepted
graph is finite, acyclic, and exactly:

```text
Record  := nonempty natural-layout declared record with Field+ and no cycle
Field   := Value
Value   := Int | Bool | string | Record | Option<Payload> | array<Element>
Payload := Int | Bool | string | Record | array<Element>
Element := Int | Bool | string | Record
Int     := i8 | i16 | i32 | i64 | u8 | u16 | u32 | u64
```

Nested `Option`, arrays whose elements are options or arrays, nested dynamic arrays, and fixed
arrays remain outside the element representation. The accepted Align manifest pins all 50 C6
nominal records and 543 ordered fields, including prompt variants, scope/policy records,
snapshots, evaluation tasks and limits, task rows, aggregates, reasons, environment identity,
evidence, activation, and the canonical gate envelope. `str`, `array<str>`, floats, char, enums,
`Result`, slices, tuples, boxes, resources, raw values, functions, builders, SoA,
`layout(C)`, `align(N)`, and every other constructor reject before descriptor construction or
allocation. The root is at depth one; every record, Option, and dynamic-array edge increments
depth, 128 is accepted, and 129 rejects at compile time.

The public source keeps expected-type inference and existing `json.decode`/`json.encode` names;
there is no type argument syntax, dynamic JSON value, implicit clone, or second wire format. A
borrowed decode view may be used only while its input owner is live. The owned selector explicitly
materializes every text field, including nested and array elements, and the result has no input
region dependency. Encode/decode preserves declaration order, escaped text, omitted `None`, nested
records, array order, and the exact semantic-to-byte vectors. Unknown input fields may be decoded
and ignored, but canonical re-encoding omits them; bytewise stability is required for canonical
declared-record bytes, not for a non-canonical input containing unknown fields. Request 12's bounded
encoder remains the separate cap operation used by C6.

### Acceptance criteria

The Align design and implementation must prove:

1. formation admits every named C6 graph and rejects every unsupported reachable field before any
   decode or encode allocation;
2. empty/non-empty arrays, `Option.None`, `Option.Some`, nested records, embedded NUL, escapes,
   multibyte UTF-8, malformed input, duplicate keys, wrong shapes, and trailing bytes have the
   declared byte and error vectors;
3. decode materializes free-standing owned text, permits the input owner to drop before every
   retained field is read, and cleans partial nested arrays/options exactly once on `?`, `else`,
   `map_err`, replacement, branch joins, loop exits, and malformed input;
4. encode uses the same declared graph and canonical field order without mutating or borrowing the
   source; `decode -> encode -> decode` is semantically stable, and canonical declared-record bytes
   are bytewise stable; an input containing unknown fields may re-encode without those fields;
5. generic monomorphization, whole-program/per-unit interface serialization, structural cache
   identity, target-local layout, reallocation, capacity overflow, allocator failure, and concurrent
   independent calls have explicit owner tests and no hidden collection or arena conversion; and
6. the align-llm C6a1/C6a2 adoption target constructs, encodes, decodes, drops, and revalidates the
   exact named artifacts through the shipped compiler, then passes `make ci` without a private
   compatibility layer.

### References

- `../align/docs/impl/25-recursive-owned-json-plan.md` — accepted exact grammar, C6 manifest,
  descriptor/envelope bytes, and implementation closure matrix.
- `../align/docs/impl/core-design/json.md` — current borrowed JSON ownership and descriptor route.
- `../align/docs/impl/08-memory-model-v2.md` — recursive Move cleanup and region boundaries.
- `../align/crates/align_sema/src/lib.rs`, `align_mir`, `align_codegen_llvm`, and
  `align_runtime` — formation, lowering, descriptor, and cleanup owners.
- Request 8/10 — runtime construction of the same owned evaluator graph.
- Request 9 — the flat direct-owned text prerequisite, whose ownership rules this request reuses.
- Request 12 — bounded canonical encoding, which remains a separate prerequisite.
- `docs/specs/c6-prompt-context-optimizer.md` §§1.2, 4.5, 6, and 10.1 — C6 ownership and vectors.

---

## Request 14 — `std.fs`: exclusive creation and no-replace publication

```text
Status: CLOSED
Priority: high
Blocking: no
Blocked gate or slice: none; the merged C6-EVALUATION pair publication consumes the shipped exclusive operations
Independent work that may continue: all work
Resume condition: complete
Align commit or pull request: design PR #859, merged as `a21eb8416f2088df68026f10c63a38cd0bd65538`; implementation PR #861, merged as `3c2edd2f399c9e2c9551b4227c61b36d6a041e20`
align-llm verification: focused `c6f2-request14-adoption` passes at Align `19c3db144c462bf7d6784f88d64cc124229b7ec2`, including exclusive staging, fixed result-then-evidence no-replace finalization, occupied regular/directory/symlink/FIFO targets, competing creators, reverse cleanup, and exact evaluator-owned orphan reporting; the final capable integration gate passed at PR #100 head `049172f5be57002c2426f012fe23038f570f5069` (CI run 32490981785, both installed native profiles) and merged as `282062bf00416f5e0df678b8bd885709084b4e16`
```

### Align response (2026-08-21 — shipped; verified 2026-08-24)

Align ships `fs.create_exclusive(path: str) -> Result<writer, Error>` and
`fs.rename_no_replace(source: str, destination: str) -> Result<(), Error>`. The implementation
preserves the existing `Error.Code(native errno)` mapping and writer Move/Drop contract, uses
ephemeral bounded NUL-terminated path copies, and selects native exclusive operations without a
check-then-create, replacing rename, delete-before-rename, or filesystem-class emulation path.

The accepted floor is controlled local ext4/tmpfs on Linux and local APFS on macOS. C6f2 still
owns trusted paths, the single-writer precondition, result-then-evidence ordering, reverse cleanup,
and `OUTPUT_WRITE` / `OUTPUT_PAIR_CLEANUP_FAILED` precedence. No durability guarantee,
cross-device fallback, Windows implementation, or remote-filesystem promise was added.

### Motivation and current-state evidence

Before the shipped Align implementation, C6f2 had to write a result and an independently
content-bound evidence sidecar. Its contract requires
two sibling temporary files, exclusive creation, fixed result-then-evidence publication, and a
no-replace finalization failure if another process creates either target between validation and
publication. The pinned Align `std.fs` surface provides whole-file `write_file` and `remove`, plus
the `fs.create` writer; `fs.create` opens with create/truncate semantics and can replace an existing
path. It did not expose an exclusive-create operation or an atomic no-replace rename operation.
The compiler/runtime's Rust cache publisher uses private `std::fs::rename`, but that is not an Align
program API and cannot be used by an align-llm client. A check-then-write or delete-and-rename
workaround would violate the stated race and no-replace contract.

### Requested capability

Extend `std.fs` with one explicit publication pair, or an equivalent reviewed API with the same
semantics:

```text
fs.create_exclusive(path: str) -> Result<writer, Error>
fs.rename_no_replace(source: str, destination: str) -> Result<(), Error>
```

The exact shipped names may follow Align's library naming, but the design must define that
`create_exclusive` opens a new regular file without following a destination symlink and fails when
the path already exists; it must not truncate or replace an existing entry. It must return an owned
`writer`, preserve the existing explicit Move/drop behavior, and close the descriptor on every
success, write failure, `?`, `map_err`, branch join, early return, and `Drop` path. The path is a
bounded NUL-free `str` view consumed only for the call; the returned writer owns the descriptor and
does not retain the view.

`rename_no_replace` must publish a source path to an absent destination atomically on one filesystem,
fail with a deterministic already-exists error when the destination is present, never replace or
delete the destination, and define source/destination validation, cross-device failure, symlink and
special-file behavior, same-directory behavior, and cleanup after every error. It must be a direct
OS operation, not a shell command or a check-then-rename sequence. The API must state whether the
source is consumed on success, and the caller must be able to remove a successfully published first
target before retrying a failed second publication without the library hiding that cleanup.

### Acceptance criteria

The Align design and implementation must prove:

1. ordinary and linked-worktree path handling, NUL/length/type validation, parent-directory errors,
   destination symlink and special-file rejection, and exact error mapping;
2. exclusive creation at an absent target and deterministic failure at an existing target, including
   a competing creator between preflight and create, with no truncation or replacement;
3. atomic no-replace rename at an absent destination and deterministic failure when a competing
   creator wins, with the source and destination states specified for every failure;
4. same-filesystem publication, cross-device failure, source disappearance, destination directory,
   symlink, and special-file cases, with no hidden remove or overwrite;
5. writer ownership, partial writes, `Drop`, `?`, `map_err`, branch/loop joins, allocation failure,
   and cleanup after a failed pair publication, including the already-published-first-target case;
6. repeated and concurrent independent calls, process interruption between staging and publication,
   and the minimum declared filesystem/platform acceptance environment; and
7. the align-llm `c6f2-request14-adoption` target uses the shipped operations for the exact result-then-
   evidence pair contract, exercises the race/cleanup matrix, leaves no temporary artifact on
   successful cleanup, and passes `make ci`. C6f2 must not use `write_file`, delete-before-rename,
   a check-then-create workaround, or an undeclared native helper in place of this capability.

### References

- `../align/docs/guide/13-std-os.md` — current `std.fs` whole-file and writer APIs.
- `../align/crates/align_runtime/src/lib.rs` — current `fs.create` create/truncate implementation
  and owned writer/drop boundary.
- `docs/specs/c6-prompt-context-optimizer.md` §§5.2, 6, 10, and 11 — result/evidence pair
  publication, cleanup, ledger ownership, and C6f2 adoption gate.

---

## Request 15 — `core.json`: complete decoded-owner transitions

```text
Status: CLOSED
Priority: high
Blocking: yes
Blocked gate or slice: C6-LIFECYCLE's `c6-json-decoded-owner-adoption`, plus any later JSON change that adds a recoverable failure edge after a declared-record owner becomes live
Independent work that may continue: C6 work that does not consume an unadopted decoded-owner surface, other Align requests, and align-llm work that does not consume a changed decoded-owner surface
Resume condition: satisfied by Align-llm PR #94; future JSON changes that add a recoverable failure edge still require the same transition-owner audit
Align commit or pull request: decoded-owner cleanup PR #849 merged as `69017961` (merge commit)
align-llm verification: PR #94 merged as `ba56ebed5ac1c82ebc5925e6257e7bd5dba8a9b9`; `c6-json-decoded-owner-adoption` passed before `c6-json-escape-adoption` in the ordered wave against `.align-revision` `a440970ac81118ed2169f600b2b3c06fcb9cde7`, and final capable `make ci` passed in CI run `32109434515` at head `954258e24d93300dcdb78f8280de8868cf1ced56`; merge run `32111007638` reused the exact evidence
```

### Motivation and current-state evidence

Verified against the sibling Align tree merged by PR #821 at
`9aef62a8a6c0e26517a042738c74b0689583c1fc`. The shipped declared-record decoder can make heap
owners live before a later recoverable parse or schema failure, but its cleanup is incomplete on
four transition classes:

- semantic checking, the authoritative JSON design, and
  `m5.rs::json_option_move_struct_payload_remains_admitted` all preserve `Option<MoveRecord>`;
  ordinary generated `Drop` handles a successful `Some`, while `drop_decoded_owned` skips every
  optional descriptor after a later enclosing-object failure;
- indexed top-level AoS speculation can write an owner and then fall back into the same destination,
  overwriting the first owner on fallback success or leaking it again on fallback failure;
- top-level `array<MoveRecord>` staging does not deep-clean the current and completed rows when a
  later row, closing delimiter, or trailing-input check fails; and
- top-level single-record trailing-input rejection occurs after required or optional owners have
  been written, without releasing them before returning `Error.Code(1)`.

Nested field-array partial cleanup already has an explicit deep-free path and is compatibility
evidence, not a reason to leave the top-level paths inconsistent. Well-typed SoA admits only
non-owning columns, so decoded-owner cleanup there is N/A. This is a compiler/runtime ownership gap,
not an align-llm parsing concern or an application workaround.

### Requested capability and authoritative contract

Preserve the existing public `json.decode` source form, declared-record wire behavior, and
`Error.Code(1)` failure result while making every admitted decoded owner transition exact-once. The
already-shipped `Option<MoveRecord>` surface remains admitted when the nested record is otherwise
JSON-decode eligible. Missing and `null` remain `None`; a valid object becomes `Some`; general
`Option<enum>`, top-level option targets, and otherwise unsupported JSON graphs remain rejected
before MIR or allocation.

The runtime must recursively clean a live optional payload after any later object failure and null
its tag/payload so outer cleanup is idempotent. Indexed AoS speculation must either stage writes
transactionally or recursively clean and null every speculative owner before fallback writes the
same destination. Top-level AoS must track exactly which rows and fields are initialized and
deep-clean the current row and all completed rows on malformed later input, missing/duplicate/type
failure, delimiter failure, or trailing non-whitespace. Top-level single-record post-parse rejection
must clean every live required and optional owner before returning. Successful values retain their
existing generated `Drop`, transfer, replacement, and input-region behavior.

Validation and observable error precedence remain unchanged: capability/import, target inference,
schema eligibility, and recursive ownership formation happen before runtime; runtime preserves
whole-input UTF-8, token grammar, duplicate, type/range, missing-field, delimiter, and trailing-input
order. Cleanup cannot replace the first error, allocate a replacement value, expose a partial
result, or make an allocator failure recoverable. No CLI, environment variable, persisted schema,
cache key, wire tag, descriptor layout, or public runtime ABI is added; if implementation proves a
descriptor change unavoidable, Align must revise this proposed contract before coding.

### Ownership closure matrix and acceptance

| Transition | Exact owner | Required regression |
| --- | --- | --- |
| Optional-owner formation and validation order | `align_sema::check_json_decode`, recursive JSON schema eligibility, canonical `DropPlan`, and the shipped JSON/option design | Existing `m5.rs::json_option_move_struct_payload_remains_admitted` remains green; `m5_decoded_owner.rs::option_move_record_surface_and_validation_order` covers missing/null/valid `Some(MoveRecord)` and rejects general `Option<enum>` and unsupported graphs before MIR/allocation |
| Optional construction, later sibling failure, and top-level trailing input | `align_rt_json_decode`, `parse_object`, optional descriptor handling, and `drop_decoded_owned` | `align_runtime::tests::json_decoded_optional_owner_failure_matrix` covers missing, type/range, duplicate, malformed later value, required-field omission, and trailing bytes after a live `Some`; tag, payload, array spine, nested owners, allocation/free counts, and exact first error agree |
| Slow top-level AoS rows | `align_rt_json_decode_struct_array`, fallback writer, row initialization ledger, and recursive cleanup | `align_runtime::tests::json_decoded_owner_aos_slow_failure_matrix` covers zero, one, and many completed Move rows plus one partial row across malformed element, delimiter, EOF, and trailing-input failure |
| Speculation success to fallback success or failure | `json_speculate`, `json_fallback`, `write_field_indexed`, and the AoS destination owner | `align_runtime::tests::json_decoded_owner_speculation_transition_matrix` forces an owner write before structural drift, then proves exact-once cleanup/nulling before both successful and failing fallback without double materialization |
| Nested record, field-array, union, and scalar-array compatibility | `parse_object`, `decode_struct_array_value`, `drop_decoded_union`, and the existing kind-4/5/6/7 descriptor paths | `align_runtime::tests::json_decoded_owner_nested_compatibility` retains successful Drop and existing mid-field-array cleanup while combining nested records, Move unions, record arrays, and scalar-array spines |
| Result construction, move, replacement, return, and all exits | `align_mir` JSON failure CFG, `align_codegen_llvm` recursive `DropPlan`, source nulling, and ordinary generated Drop | `m5_decoded_owner.rs::decoded_owner_success_and_failure_control_flow` covers direct `?`, `match`, `else`, `map_err`, reassignment, replacement, branch/loop joins, early return, and ordinary scope exit with no leak or double free |
| Whole/per-unit, imported/generic definitions, cache, and ABI preservation | semantic substitution, interface serialization, MIR fingerprints, compiler build identity, and unchanged runtime declarations | `per_unit.rs::decoded_owner_imported_generic_parity`, `cache_codegen.rs::decoded_owner_definition_edit_revert`, and `interface_param_modes.rs::decoded_owner_descriptor_abi_unchanged` |
| Same-process and independent-process calls | per-call parser, destination, staging, and cleanup state; immutable descriptors may be shared, with no new process-global mutable state | `m5_decoded_owner.rs::decoded_owner_same_process_pair_matrix` and `cache_parallel.rs::decoded_owner_two_processes` prove supported concurrent entrypoint pairs have independent owners and deterministic results |
| Allocation/failure observation | existing test-only Align allocation counters and the caller-owned transition probe, if one is required; production entrypoints pass no ambient probe | Every allocation-counter regression acquires `ALLOC_COUNT_LOCK` before fixture setup and holds it through cleanup and final assertions; zero/one/many/reallocation cases require successful-allocation and free counter deltas to agree after each recoverable failure |
| SoA, scanner, CLI/configuration, persistence, and performance | N/A: well-typed SoA and Request 6 scanner rows contain no decoded owners; this repair adds no CLI/configuration/persisted format and makes no optimization claim | Existing SoA/scanner owners remain green; no benchmark threshold or routine aggregate is added |

Before implementation, Align must extend the English JSON ownership source of truth with the exact
cleanup contract while preserving its admitted optional surface, then synchronize its Japanese
translation. The design must map every matrix cell
to the final diff and focused passing evidence. The implementation gate runs the named semantic,
runtime allocation-count, whole/per-unit, cache/interface, and concurrency owners plus the existing
nested field-array and Move-union regressions. This request reaches `ALIGN_MERGED` only at that exact
reviewed head; align-llm later reaches `ALIGN_LLM_VERIFIED` through
`c6-json-decoded-owner-adoption` and one final pin-wave `make ci`.

### References

- `../align/docs/impl/core-design/json.md` — shipped declared-record schemas, admitted optional Move
  ownership, and the currently deferred cleanup defect.
- `../align/docs/impl/core-design/option-result.md` and
  `../align/docs/impl/08-memory-model-v2.md` — recursive optional ownership and Drop.
- `../align/crates/align_sema/src/lib.rs` — JSON schema eligibility and ownership formation.
- `../align/crates/align_mir/src/lib.rs` and `../align/crates/align_codegen_llvm/src/lib.rs` — JSON
  failure CFG, transfer/source nulling, and recursive generated Drop.
- `../align/crates/align_runtime/src/lib.rs` — `drop_decoded_owned`, `parse_object`, indexed
  speculation/fallback, and top-level record/AoS decode.
- Requests 6, 7, and 9 — scanner boundary, first blocked escape-grammar consumer, and the later
  direct-owned JSON route that reuses rather than owns this shipped-route repair.

---

## Request 16 — language: borrow-safe inspection of owned sum payloads

```text
Status: CLOSED
Priority: high
Blocking: no
Blocked gate or slice: none; the C6c2 decoded verifier now consumes the shipped surface
Independent work that may continue: all work; Request 17 separately closes the dynamic-array extension used by the same verifier
Resume condition: complete
Align commit or pull request: design PR #856; implementation PR #857, merged as `8557c1525aefd9a4afef02d1ec5c2f88e16db4e4`
align-llm verification: `.align-revision` pins `cdf333dc0707edbc4984dc8b1cb6b52edf7b48d0`; `c6-borrowed-option-adoption`, `c6-borrowed-array-adoption`, and `prompt-verifier-smoke` PASS; the consuming verifier merged in align-llm PR #98 as `e44b3cca9f834266d6f541d7a68eec2b2c3de9ec`
```

### Align response and adoption (2026-08-20 — verified)

Align projects admitted `Option<T>`, `Result<T, E>`, and user-defined sum payloads in place when
the complete scrutinee is a stable shared or exclusive borrowed place. The existing syntax and
runtime layouts are unchanged: the tag and payload are read through the original storage, no
projection-only owner or allocation is created, and the caller retains ownership. Returning,
storing, capturing, sending, or otherwise consuming an admitted non-Copy payload remains a
diagnostic.

The compiler carries the projection and owner through checked HIR, move and escape analysis, MIR,
LLVM lowering, generic rechecking, interfaces, and cache identity. Request 16 deliberately keeps
dynamic arrays and other collection Move shapes outside this finite payload grammar; Request 17
owns that extension. The shared adoption fixture exercises the direct `Option<string>` case and
the real decoded C6 record graph twice, proving that the caller-owned inputs remain usable.

### Motivation and current-state evidence

C6-LIFECYCLE's pure verifier receives caller-owned decoded records through

```align
pub fn verify_result(
  borrow result: PromptEvaluationResult,
  borrow evidence: PromptEvaluationEvidence,
) -> Result<PromptScoreStatus, Error>
```

The declared artifact graph deliberately uses owned `string` fields and owned optional payloads so
records can outlive their JSON input. The verifier must inspect those values without moving them,
allocating copies, mutating the records, or retaining a view. Its first ordinary operation is
therefore a read-only match over fields such as `result.evaluation_id`, followed by matches over
`Option<PromptScope>`, `Option<WorkspacePreflightRequest>`, and `Option<EvaluationProviderControl>`.

The compiler pinned when this request was proposed rejected the smallest real-client form:

```align
Item { note: Option<string>, n: i64 }

fn inspect(borrow item: Item) -> i64 {
  return match item.note {
    None => 0,
    Some(value) => value.len(),
  }
}
```

The diagnostic was `cannot move a field out of borrowed parameter 'item'`. The same rejection was
pinned by Align's `match_cannot_extract_a_move_payload_from_a_borrowed_parameter` owner for
direct `Option<string>`, `Result<string, string>`, and a struct field carrying `Option<string>`.
The failure is not a JSON or application issue: a borrowed `Option<str>` view is supported, but the
recursive owned graph required for persistence has `Option<string>` and `Option<MoveStruct>`.

### Requested capability and authoritative contract

Extend ordinary pattern matching so that a match whose scrutinee is reachable only through a
shared or exclusive borrow performs a non-consuming read-only projection of the active payload.
Preserve the existing syntax and the existing by-value match behavior:

- a borrowed `Option<T>`, `Result<T, E>`, or user sum reads its tag in place and binds each active
  payload as a caller-owned borrow projection;
- a nested struct payload remains a borrow projection recursively, so its Copy fields are readable
  and its owned `string` fields can be passed to `str` consumers without a hidden clone;
- the projection has the exact source owner/generation region, cannot be returned, stored in a
  longer-lived value, sent to a task, or retained after the borrowed source ends, and does not
  receive an independent `Drop` or cleanup bit;
- attempting to consume the borrowed binding or move the matched payload produces the ordinary
  borrowed-parameter/borrowed-field diagnostic; an explicit `.clone()` remains the visible way to
  copy a borrowed text leaf into an owned `string`;
- matching a free-standing or otherwise owning scrutinee keeps its current move-out, source
  nulling, conditional Drop, branch/loop join, `else`, and `?` behavior; and
- no new runtime representation, heap allocation, ABI field, JSON tag, or special application API is
  added. The compiler may use explicit HIR/MIR projection metadata and a backend pointer/load path,
  but must not shallow-copy a Move aggregate merely to inspect it.

The capability applies through a borrowed root and its checked struct-field path. It must preserve
the current no-alias and generation rules for `borrow`/`borrow mut`, imported/per-unit interfaces,
generic monomorphization, cache identity, and malformed checked-HIR rejection. `Option<str>` and
other Copy-payload matches remain green and are not reclassified as owned.

### Closure matrix and acceptance

| Axis | Owner | Required evidence |
| --- | --- | --- |
| Formation and distinction | `align_sema::check_match`, parameter/field borrow classification, HIR metadata | direct `Option<string>`, `Result<string, string>`, `Option<MoveStruct>`, user-sum Move payload, borrowed root, depth-1 field, and nested field positives; owning/by-value twins retain move semantics |
| Payload projection | `align_mir` match lowering and projection operands | tag branch reads the original aggregate, active payload binds as a borrowed place, no shallow aggregate copy, no source nulling, and no binding Drop/cleanup bit |
| Backend lowering | `align_codegen_llvm` borrowed-place/path lowering | exact pointer/load shape for direct and nested struct payloads, with no new runtime helper or ABI field; malformed projection metadata fails closed |
| Ownership and escape | MoveCheck/EscapeCheck/return-borrow summaries | repeated reads preserve the source, explicit leaf `.clone()` is allowed, whole payload move/return/store/task capture is rejected, source reassignment/drop invalidates views, and branch/loop joins do not retain stale payload generations |
| Control flow | `match`, `else`, `?`, `if`, loop, early return, and replacement owners | `None`/`Some`, `Ok`/`Err`, wildcard/or-pattern, divergent arms, nested match, loop back-edge, borrowed field replacement, and early-exit cleanup matrix |
| Aggregate and nested ownership | recursive DropPlan and field/path classifiers | nested `Option<MoveStruct>`, user sums with multiple Move payloads, mixed Copy/Move fields, optional strings, and no double-free/leak at caller exit |
| Interfaces and cache | interface serialization, checked-HIR replay, MIR fingerprint, per-unit and cache owners | imported direct/generic consumer parity, definition edit/revert invalidation, exact function/match identity, and corrupted projection metadata rejection |
| Existing surface parity | current `Option<str>`/Copy match and owning Move matches | all existing match/else/try/borrow suites plus the current negative test changed into positive read-only coverage with explicit consuming negatives |

The implementation must add the capability to the appropriate language/ownership source of truth
and any required language mirror before coding, then map every applicable matrix row to focused owner
tests.
The align-llm adoption target must compile and run the smallest fixture above plus a representative
C6 `PromptEvaluationResult`/`PromptVerifierTrust` read-only verifier fixture, prove the source
records remain usable after verification, and pass the final C6-LIFECYCLE gate. No application-side
sentinel, wrapper record, hidden clone, or alternate verifier signature is an acceptable substitute.

### References

- `../align/draft.md` and `../align/docs/language-spec.md` — ownership, `borrow`, `Option`,
  `Result`, and match semantics.
- `../align/docs/impl/08-memory-model-v2.md` — borrowed fields, regions, recursive Move cleanup,
  and source nulling.
- `../align/docs/impl/17-library-boundary-prerequisites.md` — `Option`/`Result` payload plans,
  borrow provenance, interface identity, and checked-HIR closure rules.
- `../align/crates/align_sema/src/lib.rs` — `check_match`, MoveCheck, EscapeCheck, and the existing
  `match_cannot_extract_a_move_payload_from_a_borrowed_parameter` owner.
- `../align/crates/align_mir/src/lib.rs` and `../align/crates/align_codegen_llvm/src/lib.rs` —
  current match payload lowering and borrowed-place ABI.
- `docs/specs/c6-prompt-context-optimizer.md` §§6, 10, and 11.2 — the C6c2 verifier signature,
  borrow contract, and acceptance matrix.

---

## Request 17 — language: borrow-safe dynamic aggregate projection

```text
Status: CLOSED
Priority: high
Blocking: no
Blocked gate or slice: none; the C6c2 decoded evaluation verifier now consumes the shipped surface
Independent work that may continue: all work
Resume condition: complete
Align commit or pull request: design PR #864, merged as `0d4b8824`; implementation PR #865, merged as `cdf333dc0707edbc4984dc8b1cb6b52edf7b48d0`
align-llm verification: `.align-revision` pins `cdf333dc0707edbc4984dc8b1cb6b52edf7b48d0`; `c6-borrowed-array-adoption` and the complete `prompt-verifier-smoke` owner PASS; the consuming verifier merged in align-llm PR #98 as `e44b3cca9f834266d6f541d7a68eec2b2c3de9ec`
```

### Align response and adoption (2026-08-20 — verified)

Align permits borrowed `Option`, `Result`, and user-sum payload graphs to contain admitted ordinary
dynamic scalar, string, and AoS declared-record arrays. An immediate shared call may inspect an
indexed Move record element without copying its owner. Checked HIR and MIR preserve the exact
projection, generation, and contained-region roots; LLVM forms the element pointer only at the
guarded call action. No projection storage, cleanup bit, allocation, hidden clone, or application
compatibility path is introduced.

The shipped surface rejects stale roots, overlapping ownership termination, malformed descriptors,
mutable element borrows, nested dynamic arrays, SoA, fixed and specialized arrays, buffers,
builders, boxes, resources, and other excluded collection shapes before pointer construction.
Direct, imported, and function-value calls share the same parameter mode and guarded bounds
semantics. Returned views and views retained through an existing `borrow mut` destination remain
rooted in the source array generation and contained regions.

### Motivation and adopted contract

Request 16's finite payload grammar excluded dynamic arrays. C6c2 nevertheless borrows decoded
`PromptEvaluationResult` and `PromptEvaluationEvidence` records containing `array<string>` and
`array<DeclaredRecord>` fields. It must match optional records such as
`PromptEvaluationResult.corpus`, inspect `corpus.task_files`, and pass indexed Move elements from
tasks, rows, snapshots, attestations, aggregates, reasons, and expected inputs to shared helpers.
Without both the payload-array and indexed-element projections, the settled borrowed verifier
signature could not be implemented without hidden copies or a parallel API.

The adopted contract is read-only and caller-owned. Tag, length, Copy/view element reads,
declared-record field reads, and immediate shared-borrow calls are allowed. Moving, replacing,
mutating, or independently dropping the array, an owning element, or its enclosing payload is
rejected. An indexed borrow reserves the complete source root through later argument evaluation
and the call, evaluates the index once, uses MIR-owned bounds behavior, and forms no pointer when
the index or a later argument terminates. Unrelated-root mutation remains allowed.

Admitted arrays are ordinary `array<T>` scalar and AoS declared-record forms. Indexed element
borrowing is shared-only. Fixed arrays, arrays of slices, opaque response arrays, SoA, buffers,
builders, boxes, resources, and other specialized collection or handle shapes remain outside the
request. Reachable record graphs use the same finite, cycle-safe classifier and fail closed for an
unsupported owner.

### Acceptance evidence

Align's owners cover direct, field, nested-field, `borrow mut`, user-sum, and `Result` payloads;
repeated tag/length/element reads; direct, imported, and function-value indexed calls; once-only
index evaluation; same-root move/drop/replacement/transfer/mutable-borrow rejection; terminating
index and later-argument paths; view return and retention provenance; malformed checked-HIR/MIR;
generic whole/per-unit parity; cache invalidation; and guarded LLVM pointer formation without
aggregate extraction.

The align-llm adoption fixture decodes and repeatedly inspects the real result/evidence/trust graph,
including corpus, task, trace, aggregate, reason, and expected-input arrays. The C6c2 owner then
uses that surface throughout the complete decoded verifier and proves both caller-owned inputs
remain live after verification.

---

## Request 18 — `std.fs`: retained-root regular-file access

```text
Status: CLOSED
Priority: high
Blocking: yes
Blocked gate or slice: C6d offline accept/rollback CLI and any later C6 owner that consumes an ordinary artifact through the common physical-path trust boundary
Independent work that may continue: C6 pure rendering/scoring/verifier work, C6f1 source-helper design, C6f2 publication design, provider work, and every Align capability unrelated to trusted filesystem traversal
Resume condition: met by the exact pin, `c6d-request18-adoption`, and the final capable C6d integration gate
Align commit or pull request: design PR #866, merged as `0b9d25e4d2ac34877ec79f28516f5f31c70ea9e0`; implementation PR #867, merged as `19c3db144c462bf7d6784f88d64cc124229b7ec2`
align-llm verification: `.align-revision` pins `19c3db144c462bf7d6784f88d64cc124229b7ec2`; `make c6d-request18-adoption` passes the retained-root input/output matrix; the final native Linux x86_64 capable `make ci` passes on the same C6d integration head; align-llm PR #99 head `78eae459fd1f88bad1c3c3ca7b86921a08ecf168` merged as `df30533fcf62242e00320b55cd745dd2e4e0a860`
```

### Motivation and pinned-state evidence

C6's common command contract rejects every symlink or dangling-link component, physical escape,
non-regular artifact input, and unsafe output parent before consuming bytes or starting later work.
The C6d offline `accept` and `rollback` commands must enforce that boundary without a subprocess,
network call, ambient registry, or application-private native shim.

At pinned Align revision `cdf333dc0707edbc4984dc8b1cb6b52edf7b48d0`, `fs.open(path)` returns a
reader after ordinary OS pathname resolution, so intermediate and final symlinks are followed and
special files are not rejected before open. `fs.exists` is a boolean following check and
`fs.read_dir` is an owned-name enumeration, not file metadata. Request 14's
`fs.create_exclusive(path)` rejects an occupied final entry atomically but deliberately uses
ordinary parent resolution. The language exposes no `lstat`, retained directory handle, safe
beneath-open, or equivalent operation. A sequence of `exists`/`read_dir`/`open`, a Python helper,
shell command, `/proc` path, or app-specific FFI would either remain racy, lose the declared macOS
floor, add hidden work, or bypass Align's reviewed standard-library boundary.

The concrete implementation attempt that exposed this gap already has passing verifier-first
accept and immutable-lineage rollback logic. It cannot become a review candidate while input opens
may follow an escaping link, a FIFO/device may be opened before type rejection, or output
writability is discovered only after request validation. This request closes only that general
filesystem gap; it does not move C6 lifecycle semantics into Align.

### Requested public surface

Add the following operations, or an equivalent reviewed surface with the same retained-root and
error semantics:

```text
fs.open_beneath(root: str, relative: str) -> Result<reader, Error>
fs.create_exclusive_beneath(root: str, relative: str) -> Result<writer, Error>
```

Both arguments are borrowed UTF-8 views retained only for the call. `root` names an existing
directory and may be absolute or relative under the existing current-directory rule; the exact
single component `.` is allowed as the explicit current-directory root and exact `/` as the
filesystem root. Every other root component
must be non-empty and must not be `.` or `..`. `relative` is a non-empty relative path with no
leading or trailing separator and no empty, `.` or `..` component. Interior NUL, invalid ABI UTF-8,
unrepresentable length, and checked path-copy capacity overflow are invalid before filesystem work.
No operation normalizes, truncates, hashes, or silently rewrites an input.

The runtime opens and retains the root directory, then resolves every `relative` component from
retained directory descriptors. No root, parent, or final symlink is followed. Replacing or
renaming a public ancestor after its descriptor is retained cannot redirect the operation to a
different tree. The implementation may use Linux `openat2` where the accepted kernel provides the
exact semantics, but the contract is the descriptor-relative algorithm, not a Linux-only syscall;
macOS uses the equivalent no-follow `openat`/metadata sequence. There is no `realpath`, pathname
prefix comparison, subprocess, process-global root, sandbox, or hidden retry.

`open_beneath` publishes the existing owned `reader` only after the final entry is proven to be a
regular file opened from the retained parent. A directory, symlink, FIFO, socket, device, or other
special entry is `Error.Invalid` and no artifact byte is read. The returned reader owns the opened
descriptor; later caller reads use that descriptor even if the public name changes. The operation
does not promise that an out-of-band writer cannot mutate the regular file after open; C6 retains
its documented immutable-input/single-writer precondition.

`create_exclusive_beneath` retains and validates every root/parent directory, then performs one
native exclusive create of the absent final component relative to the retained final parent. An
occupied final entry of any type produces the same native `EEXIST`-backed `Error.Code` contract as
Request 14 and is untouched. Success returns the existing owned `writer`; Drop closes it and never
removes the entry. This operation does not add rename, pair atomicity, temporary naming, rollback,
durability, or implicit cleanup.

The two operations add no same-final exclusion, wait, or byte snapshot. When open and exclusive
create race on one initially absent entry, open returns `NotFound` if its no-follow observation wins,
or may acquire the newly installed regular inode while the writer remains live. A pre-existing
regular entry makes create return EEXIST while open may succeed; a pre-existing non-regular entry
makes create return EEXIST and open return `Invalid`. C6 rejects input/output overlap under its
immutable-input/single-writer precondition.

### Public-contract ledger

| Surface | Exact result/error and precedence | Ownership, allocation, effects, and identity | First real-client acceptance |
| --- | --- | --- | --- |
| `fs.open_beneath(root, relative)` | Validate the ABI output slot, then validate/copy/parse the complete root before inspecting relative, then validate/copy/parse the complete relative before traversing root components followed by relative parent components in written order. Missing root/component/final is `NotFound`; permission is `Denied`; unsafe grammar, a symlink component, non-directory intermediate, or non-regular final is `Invalid`; other native failures use the fixed errno mapping. No reader or byte is published on failure. Invalid root grammar wins over every relative-view error; the first invalid component in each traversed sequence wins. | Paths are borrowed. Per-call NUL-terminated copies and retained directory descriptors are released on every failure; terminal allocator exhaustion keeps Align's locked abort policy. Success returns the existing Move `reader`, with its existing read/Drop/`?`/`map_err`/branch/loop/return semantics. The operation is Impure, has no mutable global state, adds one explicit HIR/MIR/runtime key, and uses the existing reader nominal identity. Proposed ABI shape A12: `i32(ptr,i64,ptr,i64,ptr)`. | `c6d-request18-adoption` opens exact-cap and short-read JSON files beneath a physical project root; rejects root/intermediate/final symlinks, dangling links, missing input, directory, FIFO, socket/device where available, outside-root attempts, `.`/`..`/empty components, invalid UTF-8 bytes at the ABI owner, and permission/read failures before decoding. After separate lexical validation, it maps `NotFound` to `INPUT_NOT_FOUND`, `Invalid` (including no-follow/type rejection) to `INPUT_TYPE`, and `Denied`/other read failures to `INPUT_READ`. |
| `fs.create_exclusive_beneath(root, relative)` | Apply the same root/relative validation and component order, ending with one exclusive create at the retained parent. Missing/denied/unsafe parents map as above. Every occupied final entry is native EEXIST through `Error.Code`; no existing entry is opened, truncated, replaced, or removed. The output slot remains null on every recoverable failure. | Paths are borrowed and component owners/descriptors are per-call. Success returns the existing Move `writer`; write/flush/Drop and partial-file behavior remain Request 14's contract. The operation is Impure, adds no cleanup thread or lock, has a distinct HIR/MIR/runtime key, and uses the existing writer identity. Proposed ABI shape A12. | C6d decodes its request, derives the CLI result parent/root and final component, obtains the exclusive writer before request-field validation, writes exactly one canonical success or decoded-request failure result, rejects unsafe/existing/unwritable parents without a result artifact, and proves an existing output is unchanged. Request 14's C6f2 pair adoption remains separately owned. |

The operations add no option object, environment variable, wire format, persisted tag, reflection,
cache format, filesystem-class query, or platform-dependent public flag. Relative roots retain the
existing explicit path/current-directory behavior. C6d supplies an absolute `project_root` for
artifact inputs; for its caller-named result it passes the lexical parent and basename as the two
arguments, so output preflight remains independent of request-field validity after decode.

### Implementation closure matrix and acceptance

| Axis | Compiler/runtime owner | Required regression |
| --- | --- | --- |
| Formation and public types | `align_sema` exact import/name/arity/type checks; distinct HIR kinds | direct and imported calls, owned-string arguments borrowed not moved, missing import, wrong arity/type, generic body, Impure classification |
| Lexical validation and multi-invalid order | shared strict path-view/component decoder; generated and foreign ABI calls | null/length/UTF-8/empty/NUL/capacity cases; root before relative; first bad component; exact `.` root exception; no descriptor/native final operation before complete lexical validation |
| Retained root and component traversal | target-specific runtime helper using directory descriptors and no-follow operations | absolute/relative/`.` roots; nested success; root/intermediate/final symlink and dangling-link rejection; rename/replace public ancestors after retention cannot redirect the operation; all intermediate fds close |
| Regular input type and reader publication | final no-follow metadata/open plus existing Reader constructor | regular empty/non-empty files; directory, FIFO, Unix socket, device, and symlink reject before byte read; missing/denied/read error mapping; exactly one reader descriptor transferred and dropped across normal/`?`/`map_err`/branch/loop/return paths |
| Exclusive output and writer publication | retained final-parent descriptor plus one native exclusive create and existing Writer constructor | absent success; occupied regular/directory/symlink/FIFO/device unchanged; two competing creators exactly one winner; write/flush/partial-file/Drop and explicit cleanup preserve Request 14 semantics |
| Mutation and race boundary | descriptor identity from root through final operation | ancestor/root/final rename and replacement schedules before and after each retained descriptor; no pathname restart; immutable-input mutation remains an explicit consumer precondition rather than a false API guarantee |
| HIR, MIR, LLVM, and checked replay | every expression visitor, checked-HIR validator, replay clone, MIR lowering/print/fingerprint, LLVM runtime call | enum-sweep tripwire, forged operand/type/effect/output metadata rejection, exact A12 declarations, whole/per-unit/generic/interface/cache edit-revert parity |
| Allocation and cleanup | path copies, component scratch, root/intermediate/final descriptors, Reader/Writer construction | zero/one/many components; every lexical/native failure point; checked capacity overflow; terminal OOM child; fd/allocation counters balanced; no partially published handle |
| Concurrency/global state | per-call roots, descriptors, path buffers, and native calls | same-process pair matrix including barrier-controlled absent/newly-created/pre-existing-regular/pre-existing-special same-final open/create outcomes, repeated cycles, two independent processes, competing final creates, no process-global cwd mutation or shared retained root |
| Platform and compatibility | Linux x86_64/ARM64 and macOS Apple Silicon runtime owners | local ext4/tmpfs and APFS, linked worktree/path roots, platform syscall disposition, no `/proc` dependency, no Windows or remote-filesystem claim |

No benchmark is required because the request makes a safety/ownership promise, not a throughput or
latency promise. The implementation must first settle one Align-owned public-contract ledger and
propagate it through the English filesystem design, Japanese mirror, language/spec surface,
runtime ABI ledger, roadmap, and handoff. Rust implementation begins only after one fresh
independent adversarial review of that contract and capability boundary. The implementation PR then
uses the `align-self-review` skill, the focused filesystem/runtime/ABI owners, the bounded gate,
Clippy, and one fresh full-diff review.

### References

- `docs/specs/c6-prompt-context-optimizer.md` §§1.2, 4, 5, 6, 10, and 11 — physical trust,
  validation precedence, lifecycle ownership, and C6d acceptance.
- `../align/docs/impl/std-design/fs.md` and
  `../align/docs/impl/27-fs-exclusive-publication-plan.md` — current path resolution, existing
  reader/writer ownership, and Request 14's deliberately final-component-only guarantee.
- `../align/docs/impl/20-runtime-abi-ledger.md` — runtime-key registry and A12 ABI shape.
- `../align/crates/align_runtime/src/lib.rs` — current path marshalling, Reader/Writer constructors,
  errno mapping, and native filesystem operations.
- `../align/crates/align_sema/src/hir.rs`, `../align/crates/align_mir/src/lib.rs`, and
  `../align/crates/align_codegen_llvm/src/lib.rs` — filesystem expression and lowering closure.

### Align response and real-client adoption

Align PR #867 shipped `fs.open_beneath` and `fs.create_exclusive_beneath` through the standard
filesystem HIR/MIR/runtime boundary on Linux and macOS. The returned values are the existing owned
`reader` and `writer`; inputs remain borrowed, traversal state is per call, input success requires a
regular file, output success performs one exclusive final create, and no process-global cwd, retry,
cleanup thread, or application-private FFI is involved.

C6d consumes the surface in `src/prompt_artifact_io.align` and `src/prompt_state.align`. Request and
artifact reads stay bounded and beneath retained roots; accept invokes the shared decoded verifier
before constructing an activation; rollback validates immutable lineage; one pre-acquired writer
publishes a bounded canonical result and explicitly flushes it. The focused owner covers exact-cap
and multi-read JSON, deterministic multi-invalid order and error mapping, root/intermediate/final
and dangling symlinks, missing/denied/special inputs, unsafe/occupied output paths, destination
preservation, and exactly one winner between concurrent creators. The routine `prompt-state-smoke`
retains verifier-first acceptance, immutable rollback, tamper, lineage, and CLI coverage.

---

## Request 19 — compiler: code-generation cost on a graph of large by-value structs

```text
Status: CLOSED
Priority: medium
Blocking: no
Blocked gate or slice: none — the optimized owner is restored to the hosted lane
Independent work that may continue: all of it; every other align-llm capability compiles and runs inside its existing budget at the current pin
Resume condition: none — closed
Align commit or pull request: PR #891, merged as `4b515f8d37de2e9a9ba06170c5842fd12dc1cba2`
align-llm verification: complete — the managed pin materializes, the exact verifier output and current 23-unit graph pass, the hosted topology contains the restored member, the installed fresh-worker profile including its final `make ci` passes at head `cb28310d6a833a1b4430ec994d1393a380e861f3`, and publication PR #108 merged as `75d7cc39b40b287d47b1185306d6bd8e7eb582dc`; Align's merged CI owns the unchanged compiler-platform boundary, while this request changes no target-local align-llm behavior
```

### Motivation and pinned-state evidence

This is a compiler/runtime performance gap, not a missing surface. `align-llm` has one translation
unit, `src/prompt_verifier_smoke.align` (1,573 lines), whose C6c2 verifier fixtures construct many
literals of the C6 artifact records declared in `src/prompt_artifacts.align`. Semantic analysis of
that unit is fast; code generation for the same unit is roughly three orders of magnitude slower and
allocates over a gigabyte.

The filing-time measurement below is historical evidence from Align revision
`2f33ac5c33a898a7894af58322852632ce6ffe42`, not a measurement of the current pin
(`alignc 0.5.0`, release build), native `linux/aarch64`, 8 logical CPUs:

```text
$ alignc check src/prompt_verifier_smoke.align
0.494 s wall, 76,275 bytes of diagnostics, exit 0

$ make prompt-verifier-smoke          # alignc run: code generation, link, then execute
719 s wall, peak resident set 1,525,732 KiB, exit 0
```

Code generation owns effectively all of that: the produced program prints one line and exits.

The native aarch64 sample identifies the real-client regression that motivated this request. It is
not a permanent target-specific acceptance floor: this request makes no per-architecture latency
or memory promise. Admission of the compiler optimization is measured on one named reproducible
host by comparing `check` and `build` for the same fixture. A future claim about a particular
architecture's performance must carry a benchmark on that architecture.

The compiler's own diagnostics point at the shape it is struggling with. The same `check` emits 345
`huge struct copy` warnings over exactly two kinds — by-value parameter passing and by-value return
— across 39 distinct record types, and 100 of the 345 name one 5,056-byte record
(`prompt_artifacts$PromptEvaluationResult`); the remaining sizes above 500 bytes run 504, 632, 736,
744, 864, 960, and 1,120 bytes. Nothing in the unit is recursive, generic, or reflective: it is a
wide, flat graph of large by-value aggregates, and the cost appears to be superlinear in the copy count times the
copied size rather than in the source size.

The concrete client consequence is measured, not hypothetical. The supervised fresh-worker
aggregate (`make ci` inside the Section 9 sandbox) ran `make capable-checks` in roughly 110–180 s
before this unit joined the hosted lane. With it, one reproduction of the exact aggregate
environment took 890 s for the same graph, of which this single smoke accounted for roughly 780 s
under aggregate contention, and the qualification's practical budget was exceeded. `align-llm` therefore demoted `prompt-verifier-smoke`
from `HOSTED_CHECK_TARGETS` to a named focused qualification run on verifier-boundary changes and
before publication (see `docs/specs/check-gate-topology.md` §2 and
`docs/specs/c6-prompt-context-optimizer.md` §11.3). Coverage is unchanged; only its lane membership
is. That is a scheduling decision on the client side, not a fix, and it is exactly the kind of
non-blocking, workaround-shaped gap this register exists to record.

Supported-platform correctness remains the compiler provider's CI responsibility. The consumer
reruns a platform profile only when its own target-local behavior changes or when the request makes
a target-specific performance claim; ordinary compiler pin adoption does not create either claim.

### Requested behavior

No new public surface. On one named reproducible measurement host, `alignc build` should generate
code for a unit of this shape in time and memory proportional to what `alignc check` already proves
is tractable — concretely, within a small constant multiple of the `check` cost and without a peak
resident set that scales with the product of copy sites and struct size. The structural IR reduction
and generated-program behavior are platform-independent; the measured ratio is representative lane
admission evidence, not a promise that every architecture has the same ratio. Diagnostics,
generated-program semantics, and the `huge struct copy` warning text are unchanged by this request;
the warning is useful client advice and should stay.

Align owns the choice of remedy. Plausible directions, listed only as evidence of where the cost
concentrates and not as a required design:

- lower a large by-value aggregate copy to a memory intrinsic or a single move instead of
  materializing per-field code at every call and return site;
- avoid re-expanding an identical aggregate copy sequence once per site when the source and
  destination layouts are identical;
- bound the working set held per function during code generation so peak memory tracks the largest
  single function rather than the whole unit.

### Public-contract ledger

| Surface | Exact result/error and precedence | Ownership, allocation, effects, and identity | First real-client acceptance |
| --- | --- | --- | --- |
| `alignc build <unit>` | Unchanged. Same accepted programs, same rejections, same diagnostic text and order, same generated-program behavior. This request changes only the resources the existing contract consumes. | Unchanged for the generated program. Compiler-internal only: the peak resident set during code generation must not scale with (copy sites x copied struct bytes) across the whole unit. The check/build resource ratio is measured on one named host and is not a target-specific SLA. | Direct `check`/`build` measurement on one named host satisfies the ratio and memory bound; `make prompt-verifier-smoke` at the adopted pin preserves its output and fits the lane budget; the target is restored to `HOSTED_CHECK_TARGETS`, to `scripts/check-gate-topology`'s `EXPECTED` bytes, and to the `docs/specs/check-gate-topology.md` hosted oracle; and `python3 scripts/run-fresh-worker-qualification --installed-profile-only --require-docker` passes on one capable host at that head. |

### Acceptance criteria

1. At the adopted pin, on one named reproducible measurement host, both compiler phases succeed for
   `src/prompt_verifier_smoke.align`: `alignc check` and `alignc build`. The build's wall time is
   within a small constant multiple of the check's, and its peak resident memory stays well under
   the 1,525,732 KiB filing-time observation. This is representative-host admission evidence, not
   an architecture-specific performance guarantee.
2. `make prompt-verifier-smoke` prints exactly
   `prompt verifier smoke: complete, incomplete, compact, and tamper cases PASS`.
3. `make check` reports the current 23 units per-unit (the filing-time graph had 22 before C7 added
   `persisted_result`) and every other align-llm target is unaffected.
4. `prompt-verifier-smoke` is restored to the hosted lane in `Makefile`,
   `scripts/check-gate-topology`, and `docs/specs/check-gate-topology.md` in one change, and
   `python3 scripts/run-fresh-worker-qualification --installed-profile-only --require-docker` passes
   on one capable host at that head with the restored member inside its per-target budget.

### Align response (2026-08-26 — merged)

Align PR #891 ships no public surface or ABI change. LLVM lowering now emits one module-private
`nounwind void(ptr)` iterative destructor for each Move struct reached as a Drop-site root and
reuses it across ordinary, replacement, fixed-array, dynamic-array, and cross-function cleanup
sites. Nested records, tagged values, owned arrays, handles, and resources remain inside the same
compiler-generated iterative CFG; generated helpers never call one another, so nominal type depth
does not become runtime call-stack depth. Allocation, ownership, cleanup order, exactly-once Drop,
diagnostics, MIR, interfaces, and cache formats remain unchanged.

On the submitted Request 19 fixture, raw LLVM IR fell from 1,517,324 lines / 113.6 MB to 109,992
lines / 5.96 MB. A cold three-unit release build fell from 471.074 seconds with observed RSS above
832,704 KiB to 13.555 seconds and 266,400 KiB peak RSS. The final release candidate completed in
13.27 seconds at 264,560 KiB and printed the exact required PASS line. A small unaffected Move-record
control retained one frontend miss, one codegen miss, a 1,240-byte object, one allocation and one
free; seven cleanup executions measured 0.001 seconds before and after. The focused owners cover one
helper across Drop-site shapes, every admitted dynamic aggregate-array leaf, malformed ids, and an
executable 4,096-record graph with one helper frame. All required Align CI rows passed on the merged
candidate. The consumer-owned pin adoption, hosted-lane restoration, and fresh-worker proof are
verified below.

### align-llm verification (2026-08-26 — ALIGN_LLM_VERIFIED)

The managed release compiler/runtime materializes at the adopted merge. The restored
`prompt-verifier-smoke` prints the exact required line in 14.01 seconds on its first local build,
`gate-topology-check` and its self-test accept the restored bytes, and `make check` passes with the
current 23 units per-unit. The exact-head preflight at `cb28310d6a833a1b4430ec994d1393a380e861f3`
then ran the owner again, completed all hosted checks in 41,714 ms with the verifier in its original
position, and passed the focused fresh-worker owners in 24,118 ms.

The adopted release compiler was also measured directly with a fresh disabled cache on the same
three-unit fixture, copied into an isolated directory. One native Linux x86_64 sample on an AMD
Ryzen 9 5950X with 32 logical CPUs used
`ALIGNC_CACHE=off <managed-alignc> check main.align` and
`ALIGNC_CACHE=off <managed-alignc> build main.align`. The compiler was the managed
`4b515f8d37de2e9a9ba06170c5842fd12dc1cba2` binary with SHA-256
`0f48fa532a160d706d00084460e6c42d79ece4a6251fd44c85546b8c5071532e`. Check completed in
2.214 seconds at 126,192 KiB peak RSS; build completed in 12.786 seconds at 259,720 KiB peak RSS,
5.78 times the check wall clock and well below the filing-time 1,525,732 KiB peak. The built program
printed the exact required PASS line. The Align-side comparison used pre-change compiler revision
`f57b986bc9326ba8d75dad5dbe4c6531c0f872b6` and implementation candidate
`4f3372df60d4974c1aa080ab5423454aa769157d`; the review-repaired final compiler is
`b0147301d830d2b2c71254796541b9b9c1156b0d`, contained by the adopted merge above. Its exact
commands and unaffected control are checked in under Align's `bench/large_drop_codegen/`.

The pin and Makefile identity change also regenerated the required deterministic-reference baseline.
Both samples passed in 267,162,603–309,419,016 ns, median 288,290,809 ns, on native Linux x86_64.
Its strict chain is source `d57436315969d73a01782b02bd6c8b8cf9aeadb5`, oracle
`63250e961f10c029ce2f6c093c556b77f44e7f8c`, and finalization
`cb28310d6a833a1b4430ec994d1393a380e861f3`; `check-baseline-chain` and `baseline-check` both pass.

Finally, `python3 scripts/run-fresh-worker-qualification --installed-profile-only --require-docker`
passed through the exact preflight with the managed Align checkout supplied explicitly and ambient
`DOCKER_HOST` removed. Image build took 168,781 ms; image attestation, profile lifecycle,
self-test, trust mutations, runtime replacements, and the native boundary profile all passed; the
supervised worker's complete `make ci`, including the restored member, passed in 370,529 ms; cleanup
passed; and the whole installed profile completed in 763,510 ms. This is the request's final capable
integration evidence at the adopted pin. The aggregate was selected because this adoption restores
one of its members, not because the measurement host was x86_64 or because every pin change selects
the graph. The filing-time aarch64 result motivated the optimization, but it does not turn each later
pin into a rolling aarch64 performance certification. Request 19 changes no C7 algorithm, wire,
digest, validation, persistence, Darwin linker, or Linux isolation boundary and makes no
architecture-specific performance claim. Align's merged CI already owns the compiler's
supported-platform correctness, so rerunning the C7 Linux aarch64 and Darwin profile gates here
would duplicate provider and unrelated consumer evidence. Publication PR #108 merged the exact
adoption and this record as `75d7cc39b40b287d47b1185306d6bd8e7eb582dc`, so the request is
`CLOSED`.

---

## Request 20 — CI: run the owned-JSON boundary regressions on the macOS matrix leg

```text
Status: CLOSED
Priority: medium
Blocking: no
Blocked gate or slice: none — align-llm's own aarch64-apple-darwin profile gate exercises the shipped surface from the client side, and the Linux legs cover the compiler-side regressions
Independent work that may continue: all of it; this asks for detection coverage in Align CI, not for a behavior change
Resume condition: satisfied — Align CI's `macos-15` matrix leg runs the `m5_owned_json` integration target on every platform-required pull request, its required aggregate fails closed, and the job is green at the revision align-llm pins; trusted docs-only pull requests targeting `main` are the explicit non-executable exception
Align commit or pull request: PR #887, merged as `fa3f03f15f0b1d876683343233f440bce6ea27c5`; adopted through Align `main` at `f57b986bc9326ba8d75dad5dbe4c6531c0f872b6`
align-llm verification: complete — the managed compiler/runtime materializes, `c7-owned-record-source-expiry-adoption` passes, the attested Darwin profile including `persisted-result-qualification` passes, the supervised fresh-image capable graph passes at the adopted pin, and publication PR #107 merged as `eb6108693c74ae9933b224db4e6786058b34e9d6`
```

### Align response (2026-08-25 — merged)

Align PR #887 adds the existing `m5_owned_json` owner after the workspace build in the
required `macos-15` PR leg. Running that owner locally on Apple Silicon exposed a pre-existing
storage-generation regression introduced after the align-llm pin: `JsonOwnedDecode` was incorrectly
retaining both its input fact and the enclosing arena's allocation mode even though the checked-HIR,
MIR, runtime, and Request 9 contract make every decoded owner free-standing. The same candidate
restores those two analysis facts to the existing contract. The complete 10-test owner passed
locally and the required macOS Apple Silicon CI leg passed on the merged candidate. The remaining
pin adoption and `make darwin-profile-gate` proof belong to align-llm. Align PR #888 then closed
the upstream handoff without changing the implementation. PR #889 later added a trusted classifier
that skips the complete platform matrix only for non-empty, addition/modification-only Markdown
diffs targeting `main`; unknown paths, deletions, non-`main` bases, pushes, and executable changes
continue to fail closed into the matrix. The adopted latest `main` commit above contains all three
merges.

### align-llm verification (2026-08-26 — ALIGN_LLM_VERIFIED)

The latest Align `main` pin materializes natively on Apple Silicon and the original
`c7-owned-record-source-expiry-adoption` fixture passes all 45 adoption rows. The Section 10 Darwin
profile then passed at clean head `863ab0d333209fbd90bec0dd4e4148ef56f167f7`; section 11.3 of
`docs/specs/c7-persisted-result.md` carries the emitted identity block and its five passing commands.
The profile's `persisted-result-qualification` is the client-side Request 9 proof; it complements,
but does not replace, Align PR #887's own 10-row macOS boundary owner.

The pin moved the identity-bound coding baseline. The accepted replacement was measured as non-root
on native Linux aarch64 with CPython 3.12 and bubblewrap: both deterministic-reference samples
passed in 133,219,500–141,093,417 ns, median 137,156,458 ns. Its strict chain is source
`3714b371e09ca2937981d9098a167c43084bc0f3`, oracle
`7080b61f9a4b5b6542b77524f0f6c7b42786b801`, and finalization
`863ab0d333209fbd90bec0dd4e4148ef56f167f7`. The earlier macOS-produced non-passing chain remains
in history as rejected evidence; the later `dc321412` Linux chain is a valid intermediate pin
checkpoint, but neither is the canonical record for the selected latest pin.

Finally, `python3 scripts/run-fresh-image-profile-smoke --require-docker --align-repo <managed-pin>`
passed at `863ab0d333209fbd90bec0dd4e4148ef56f167f7`: image build, attestation, lifecycle,
self-test, trust mutations, runtime replacements, native aarch64 boundary profile, the complete
worker aggregate (424,471 ms), and cleanup all passed. This is the request's final capable
integration evidence at the adopted pin. The request advanced to `ALIGN_LLM_VERIFIED` on this
evidence. align-llm publication PR #107 then merged the exact pin and this record as
`eb6108693c74ae9933b224db4e6786058b34e9d6`, so the request is `CLOSED`.

### Motivation and current sibling evidence

Request 9's contract is explicitly target-local: `align-llm`'s C7 design records that natural
ownership and layout behavior per target is part of what the owned-JSON surface promises, which is
why `docs/specs/c7-persisted-result.md` section 11 makes `aarch64-apple-darwin` a *required* C7
acceptance environment rather than supplementary evidence. Align's own boundary regressions for that
surface, however, never execute on macOS.

At the pinned revision `2f33ac5c33a898a7894af58322852632ce6ffe42`:

- `.github/workflows/ci.yml` declares one `build-and-test` matrix with three legs — `ubuntu-24.04`
  (`lint: true`), `ubuntu-24.04-arm` (`lint: false`), and `macos-15` (`lint: false`).
- The only step in that job that executes any test binary is `Bounded PR test gate`
  (`run: scripts/test-pr.sh`), and it is guarded by `if: matrix.lint`. The full test gate is
  therefore x86_64-lint-only. The two non-lint legs run `Build compiler and runtime`,
  `Build release compiler`, and `Smoke test packaged command`, which compile `examples/hello.align`
  and exercise the packaged `alignc`/`align-repl` pair. Useful, but not a regression suite.
- `scripts/test-pr.sh` selects its integration targets explicitly: `--test effect_fail_closed`,
  `--test examples`, `--test m0`, and `--test summary`, plus the listed libraries. Request 9's own
  owner, `crates/align_driver/tests/m5_owned_json.rs` (586 lines; named as
  `m5_owned_json::formation_and_target_routing` in the closure table of
  `docs/impl/24-owned-json-plan.md`), is not in that selection.
- `.github/workflows/nightly.yml` is where it does run: `run-suite-binaries.sh` executes every
  workspace test binary, on `runs-on: ubuntu-24.04` only.

So today a macOS-specific regression in owned text fields, runtime-sized text arrays, or their
cleanup transitions would first be observed by a client — concretely by `align-llm`'s
`persisted-result-qualification` on its Darwin profile gate — instead of by Align's own CI. That is
the inverse of the intended order, and it is exactly the class of gap this register exists to
record: non-blocking today, cheap to close, expensive to discover late.

### Requested change

Add one focused test step to the `macos-15` matrix leg of `build-and-test`, running the
`m5_owned_json` integration target against the workspace that leg already builds:

```yaml
- name: Owned-JSON boundary regressions (macOS)
  if: runner.os == 'macOS'
  run: scripts/cargo.sh test -p align_driver --test m5_owned_json --locked
```

The exact step name, guard spelling, and whether the same step also joins `ubuntu-24.04-arm` are
Align's call; the request is that the owned-JSON boundary regressions execute on the macOS leg. No
public surface, no test content, and no other leg's behavior changes. The marginal cost is one
integration binary on a leg that already compiles the workspace and is not the critical path — the
`lint` leg is.

### Public-contract ledger

| Surface | Exact result/error and precedence | Ownership, allocation, effects, and identity | First real-client acceptance |
| --- | --- | --- | --- |
| `m5_owned_json` test target | Unchanged. Same assertions, same pass/fail meaning; this request changes only where they execute | CI-only. No compiler, runtime, or standard-library behavior changes, and no generated-program identity moves | The `macos-15` leg is green with the step present at the revision `align-llm` pins, and `align-llm`'s `make darwin-profile-gate` passes at that same pin |

### Acceptance criteria

1. The `macos-15` leg of `build-and-test` executes `m5_owned_json` on every platform-required pull
   request and reports its result through a required aggregate. A trusted classifier may exempt only
   non-empty, addition/modification-only Markdown diffs targeting `main`; deletions, unknown paths,
   non-`main` bases, pushes, and executable changes fail closed into the platform matrix.
2. The step is green at the revision `align-llm` pins, so the two evidence sources agree.
3. The `ubuntu-24.04` lint leg's critical-path duration is unchanged, and the bounded PR gate's
   selection is untouched unless Align chooses to widen it instead.
4. `align-llm`'s `make darwin-profile-gate` continues to pass at the adopted pin, with its recorded
   identity block, as the independent client-side observation.

---

## Request 21 — `std.fs`: read-only random-access file open (`fs.open_ro`)

```text
Status: PROPOSED
Priority: medium
Blocking: no
Blocked gate or slice: none today — R0-GGUF-INSPECT (merged, PR #121), R1-QWEN-MODEL-IR (merged, PR #122), R1B-GPTOSS-MOE-IR (merged, PR #123), and the active R2A-EXPERT-TRACE-CAPTURE (`docs/specs/r2a-expert-trace.md` section 2.1) all ship on `fs.open_rw`. R2A opens **no** GGUF at all: its input is a `llama-eval-callback` transcript, which is a second class of read-only input — a transcript captured into a root-owned or read-only artifact directory, exactly where a CI-produced trace lives, cannot be opened at all. It becomes blocking for the first align-runtime consumer that must read a model from a read-only mount, a root-owned shared cache, or a container image layer, where `O_RDWR` cannot be obtained at all
Independent work that may continue: all of R0-GGUF-INSPECT, R1-QWEN-MODEL-IR, R1B-GPTOSS-MOE-IR (each opening the model with `fs.open_rw`), and all of R2A-EXPERT-TRACE-CAPTURE (opening its transcript with the same constructor); every one of them documents the writable-path precondition, and every later Track B slice that can copy or own its input file
Resume condition: Align ships a read-only `file` constructor whose handle supports `pread` and `len`; align-llm then adopts it in `src/gguf.align` and `src/expert_trace.align`, and `make gguf-smoke`, `make model-ir-smoke`, `make expert-trace-smoke`, `scripts/run-gguf-reference-parity`, and `scripts/run-model-ir-parity` pass against input files the invoking user cannot write
Align commit or pull request: none
align-llm verification: pending — `make gguf-smoke` extended with a `chmod 444` model fixture case, `make expert-trace-smoke`'s existing `read-only-transcript` case (mode `0444`) flipped from "exits nonzero with no document" to a successful derivation, and `scripts/run-gguf-reference-parity` run once against a model on a read-only mount
```

### Motivation and current sibling evidence

`align-llm` R0 (`docs/specs/r0-gguf-inspection.md`) inspects a GGUF model's header, metadata, and
tensor table. It reads a few megabytes at explicit offsets out of a multi-gigabyte file and never
writes a byte to it. That is precisely a random-access read workload, and at the pinned revision
`4b515f8d37de2e9a9ba06170c5842fd12dc1cba2` Align has no constructor for it.

Verified in the sibling checkout at that exact commit (which is also `../align`'s `main` tip,
`Merge pull request #891 from sanohiro/agent/request19-drop-codegen`):

- `draft.md:2839-2840` lists the only two `file` constructors:

  ```text
  fs.create_rw(path: str) -> Result<file, Error>   // O_RDWR|O_CREAT|O_TRUNC — a fresh random-access file
  fs.open_rw(path: str)   -> Result<file, Error>   // O_RDWR, must exist — in-place update (see std.io `file`)
  ```

- `draft.md:2770-2776` and `docs/language-spec.md:1042-1044` state the rule directly: `file` "is the
  offset-addressed block read+write handle … there is **no cursor and no `seek`** …, and there is
  **no read-only constructor** (pure random reads stay `reader` or the `fs.read_bytes_view` mmap
  view — a third read path would break 'one way')."
- `crates/align_runtime/src/lib.rs:9933` implements `fs.open_rw` as
  `std::fs::OpenOptions::new().read(true).write(true).open(path_str)`, so the request for write
  access is unconditional. `crates/align_driver/tests/m12_file_io.rs:98-133` pins must-exist and
  non-truncating behavior for that constructor.
- `fs.open` (`draft.md:2833`) returns a sequential `reader` with no `pread` and no offset, so it
  cannot serve a container reader that must jump to a tensor-table entry.
- `fs.open_read` does not exist anywhere in the repository, and `fs.open_ro` exists only as prose in
  three deferred-work notes: `docs/impl/07-roadmap.md:1986` records it as "the recorded escape hatch,
  **deferred-with-trigger**", with the trigger stated as "if a VA-constrained consumer ever needs
  non-mmap random reads"; `docs/impl/07-roadmap.md:1981` and `:1997` list "`open_ro`" and "read-only
  opens" under Deferred; `docs/open-questions.md:3707` repeats the settled decision and the same
  deferral.

**This request is that trigger firing.** R0 is exactly the consumer the deferral anticipated. It
cannot use the mmap alternative as its primary strategy: `fs.read_bytes_view`
(`draft.md:2827-2831`) maps the whole file into an arena, which for a 4.68 GB model means committing
the entire address range for a 5 MB read, and `draft.md:2897` records that concurrent truncation of a
mapped file raises `SIGBUS` with no handler installed. R0 reads roughly 0.15 percent of the file
through a bounded window instead.

**R2A-EXPERT-TRACE-CAPTURE is a second, different class of read-only input for the same gap.** It
opens no GGUF: its subject is a `llama-eval-callback` transcript, a text file it scans through the
same bounded window and never writes. `src/expert_trace.align`'s `scan` calls `fs.open_rw(path)`
because both random-access `file` constructors Align ships (`fs.create_rw` and `fs.open_rw`,
`docs/language-spec.md:1063`) demand `O_RDWR`, so a transcript in a root-owned or
read-only artifact directory is refused before a byte is read. Asserted on this host rather than
argued: `make expert-trace-smoke`'s `read-only-transcript` case copies a valid transcript, sets mode
`0444`, and observes `main --expert-trace` exit **3** with no document written and the destination
untouched. The request also charges its own owner test: `make expert-trace-smoke` must copy the
checked-in `eval/fixtures/expert-trace/qwen2-prefill-build10566.txt` into a writable directory
before scanning it, because the fresh trusted worker mounts the checkout read-only and the
in-place scan exits 3 there. That copy is a workaround, not a design: an `fs.open_ro` would let the
owner read its own fixture where it lies. That case is written to flip the day this request ships. A model is normally writable by
its owner; a CI artifact directory normally is not, which makes the transcript the stronger of the
two clients.

The observable consequence today is that `align-llm` must ask the operating system for `O_RDWR` on a
file it never writes. That is recorded here per the `CLAUDE.md` classification rule even though it
does not block R0 — a model in a developer checkout is normally writable by its owner — because the
deployment shapes this repository is building toward are exactly the ones where it fails: a
read-only mount, a root-owned shared model cache, and a container image layer. In every one of those
an inspection that touches no byte of the file is refused with `EACCES`, which Align's fixed errno
table (`draft.md:2717`) surfaces as `Error.Denied`. A workaround exists — copy the model, or relax
its permissions — and it is precisely the kind of application workaround that must not hide a
language-owned requirement.

**R4-ALIGNPACK-LAYER-MAJOR is a third input class, and strengthens the request rather than merely
repeating it.** R4 opens the source model read-only, in the sense that it never writes a byte back
into it, but Align exposes no `fs.size` / `stat` / `metadata` call at all — verified by its absence
from the ABI enumeration at the pinned commit `4b515f8d37de2e9a9ba06170c5842fd12dc1cba2` — so the
*only* way to learn the model's length before planning the pack's layout is to open it and call
`f.len()`. Combined with the absence of a read-only random-access constructor (this request), even
*sizing* a model align-llm will never write to requires an `O_RDWR` descriptor on it, exactly the
same read-only-media failure this request already names for R0's inspection and R2A's transcript
scan, now on a third distinct input.

**R6-KV-PERSIST is this request's strongest client to date** (`docs/specs/r6-kv-persist.md`
section 7). Every client above reads a file this repository did not produce; the `akvp` container is
one it **does** produce, so the natural place to put it — a shared read-only cache, a root-owned
model directory, a container image layer — is exactly the place this arm cannot then read it from.
`src/decode_step.align`'s load path calls `fs.open_rw(KV_LOAD)` on a file it never writes, and
`src/kv_plane.align`'s `read_header` needs `f.len()` on the same handle because there is still no
`fs.size`. **No status change**: a container in a developer's scratch directory is writable by its
owner, and the capability ships without a workaround.

**R3-RESIDENCY-SIM is a second, narrower client of the same `fs.size`/stat absence — but not a new
client of the `fs.open_ro` gap this request asks for.** `src/residency_sim.align:377-378` and
`:518-519` enforce the Model IR and trace document byte caps (`R3_IR_TOO_LARGE`,
`R3_TRACE_TOO_LARGE`) on the materialized document after `fs.read_file` returns, rather than before
the read, because neither `fs.size` nor any metadata-only stat exists at this pin —
`docs/specs/r3-residency-sim.md` section 6 correction 3 records the same absence
`src/alignpack.align:1717` already cites. Unlike every other client above, R3 does **not** need
`fs.open_ro` itself: it reads documents with `fs.read_file`, which does not demand `O_RDWR`, so its
qualification can read a Model IR or trace document from a read-only artifact directory where
R2A's `fs.open_rw`-based scan cannot. This is additional evidence for the `fs.size`/stat sub-issue
this request's motivation already names (from R4's paragraph above), not a seventh client of the
`fs.open_ro` constructor itself.

### Requested capability

One read-only sibling of the existing `file` constructors, following the established `_rw`/`_ro`
suffix convention and the one fixed errno table:

```align
fs.open_ro(path: str) -> Result<file, Error>   // O_RDONLY, must exist — read-only random access
```

Contract, deliberately minimal and matching `fs.open_rw` everywhere it can:

- Opens an existing path `O_RDONLY | O_CLOEXEC`. It never creates, never truncates, and never
  extends. A missing path is `Error.NotFound`; a permission failure is `Error.Denied`; anything else
  goes through the same errno table as every other `std.fs` call.
- Returns the same `file` handle type. `f.pread(b: mut buffer, off: i64)` and `f.len()` behave
  exactly as `draft.md:2758-2762` specifies, including the returned actual count, `0` at EOF, the
  live `fstat`, and the abort on a negative offset. The handle stays Move, owns its fd, closes on
  `Drop`, and remains structurally single-threaded.
- `f.pwrite` on a handle from `fs.open_ro` is the one difference. Rejecting it at compile time is
  preferable, since the constructor is statically known at the binding site in the same way
  `check_fs_create_open_rw` already discriminates its two callers; if that is not natural in the
  existing sema shape, a runtime `Error.Denied` from the kernel's own `EBADF` is acceptable and
  should be documented as such. `align-llm` needs only `pread` and `len`.
- No new handle type, no capability flag on `file`, no cursor, no `seek`, no buffering, and no
  `copy_range`. This asks for one constructor, not a read-only handle family.

The "third read path would break one way" objection is understood and this request does not dispute
it for the *sequential* case. The claim is narrower: `reader` and the arena mmap together do not
cover bounded random reads of a large file without write permission, and that combination is a real
consumer shape rather than a hypothetical one. If Align prefers to close the gap differently — a
mode argument on `fs.open_rw`, or an `fs.open_at_offset`-style reader — `align-llm` will adopt
whatever shape Align settles on; the requirement is the capability, not the spelling.

The two specification sentences that would have to be amended to admit this are the identical "no
read-only constructor" claims at `draft.md:2772` and `docs/language-spec.md:1043`.

### Public-contract ledger

| Surface | Exact result/error and precedence | Ownership, allocation, effects, and identity | First real-client acceptance |
| --- | --- | --- | --- |
| `fs.open_ro(path: str)` | `Result<file, Error>`. `Error.NotFound` for a missing path, `Error.Denied` for `EACCES`/`EPERM`, `Error.Invalid` for `EINVAL`, `Error.Code(errno)` otherwise — the one fixed table, checked before any read | Returns an owned Move `file` that owns its fd and closes on `Drop`; allocates no buffer; the caller supplies every `buffer` window. No process-global state, no signal handler, no mapping, and no generated-program identity change for existing programs | `align-llm`'s `src/gguf.align` opens the model with `fs.open_ro` and `make gguf-smoke` passes, including a `chmod 444` fixture the current `fs.open_rw` path cannot open |
| `f.pread` / `f.len` on an `fs.open_ro` handle | Unchanged from `draft.md:2758-2762`: actual count, `0` at EOF, live `fstat`, abort on negative offset | Unchanged | The R0 `bytes_read` assertions and the section 4.4 reference-parity comparison produce byte-identical documents from an `open_ro` and an `open_rw` handle on the same file |
| `f.pwrite` on an `fs.open_ro` handle | Compile-time rejection preferred; otherwise `Error.Denied` at runtime | Unchanged | A compile-fail test in `m12_file_io.rs`, or the documented runtime error, whichever Align chooses |

### Acceptance criteria

1. `fs.open_ro(path)` compiles, opens an existing readable file with no write permission requested,
   and returns a `file` whose `pread` and `len` behave identically to the `fs.open_rw` handle's on
   the same file. A compiler test in `crates/align_driver/tests/m12_file_io.rs` covers the success
   path, the missing-path `Error.NotFound`, the unreadable-path `Error.Denied`, and byte-equality of
   a windowed read against the `fs.open_rw` result.
2. A file whose mode is `0444`, owned by another user, or on a read-only mount opens successfully
   through `fs.open_ro` and fails through `fs.open_rw` in the same test, which is the whole point of
   the request and must be asserted rather than assumed.
3. `f.pwrite` on an `fs.open_ro` handle is rejected — at compile time with a named diagnostic, or at
   runtime as `Error.Denied` — with a test pinning whichever Align chooses, and the choice recorded
   in `draft.md` and `docs/language-spec.md`.
4. The existing `fs.open_rw` and `fs.create_rw` surfaces, their flags, their tests, and every
   generated-program identity are unchanged. No existing program's behavior moves.
5. `align-llm` verification: `src/gguf.align` switches its one constructor call to `fs.open_ro`,
   `make gguf-smoke` passes with a new `chmod 444` fixture case asserting a successful inspection,
   and `scripts/run-gguf-reference-parity` passes once against a real model on a read-only mount,
   with its size and modification time unchanged. The R0 writable-path precondition is then removed
   from `docs/align-development.md` and from `docs/specs/r0-gguf-inspection.md` section 2.7.

---

## Request 22 — Indexing arrays of Move element types

```text
Status: PROPOSED
Priority: medium
Blocking: no
Blocked gate or slice: none (workaround in place). R1-QWEN-MODEL-IR (`docs/specs/r1-qwen-model-ir.md`
section 1.3 and section 5.2) deliberately excludes the tokenizer and reads only the declared length
of `tokenizer.ggml.tokens`/`tokenizer.ggml.merges` — exactly what R0's decoder already records
without materializing an element — precisely so this request stays non-blocking through R1, and
R1B-GPTOSS-MOE-IR (merged, PR #123; `docs/specs/r1b-gptoss-moe-ir.md` section 2.1) inherited the same
exclusion unchanged: it reads no `array<string>` and builds no tokenizer. R2A-EXPERT-TRACE-CAPTURE
(`docs/specs/r2a-expert-trace.md` section 2.1) added **no** client evidence here, contrary to what
this entry anticipated: it holds no `array<string>` at all. Its distinct node names and operation
names are one concatenated `string` addressed by explicit `[start, end)` spans in parallel
`array<i64>` columns — the third instance of the `GgufTable`/`BlockPlan` shape — so it *avoids* the
Move-array shape rather than exercising it, for the same reason those two did. The active
R1C-OLMOE-MOE-IR (`docs/specs/r1c-olmoe-moe-ir.md` section 1.3 and section 5.4) inherits the same
exclusion again, expected and confirmed at implementation: it materializes no tokenizer and reads
no `array<string>`, so it adds no new client evidence here either. R6-STEP-N
(`docs/specs/r6-step-n.md` sections 4.4, 8, and 11.3) is the **fourth** instance of the avoidance
and the first outside a container reader: `model_forward.StepColumns` would naturally carry
`sha256`, `oracle_verdict`, and `oracle_worst_node` as `array<str>`, and instead carries the digests
as one fixed-width-sliced `string`, the node names as one `string` with a parallel `[start, end)`
column pair, and the verdict as the `i64` code every other verdict on the wire already is. It stays
**non-blocking** and adds no consumer of a hypothetical surface; it does record that the
stream-plus-column shape is now reached by capabilities that have nothing to do with GGUF, so the
migration named below gains a third producer surface. R6-STEP-N also deliberately gates on **token ids** rather
than on decoded text precisely so this request stays non-blocking through the decode loop.
R6-PREFIX-SUFFIX-PREFILL (`docs/specs/r6-prefix-suffix-prefill.md` section 3.5) is the first client
that makes the tokenizer's absence *cheaper* rather than merely tolerable, and it is recorded
because the direction is unusual: a **suffix is not decoded**. It is an operand, obtained by
splitting an id list the instrument printed, so continuing a saved prefix with a different suffix
needs no detokenization at any point — not in the arm, not in the qualification runner, and not in
gate G, whose `llama-debug --save-logits` blob for the whole prompt is reused unchanged because
`TOKENS ++ SUFFIX` is that prompt's id list by construction. It adds **no client** and consumes no
hypothetical surface. The
first consumer that would make it blocking is a
tokenizer/vocabulary-inspection capability, which needs `tokenizer.ggml.tokens` and
`tokenizer.ggml.merges` as addressable data; per `CLAUDE.md`, this request reclassifies as blocking
the moment that capability becomes the active consumer
Independent work that may continue: all of R0, R1-QWEN-MODEL-IR, R1B-GPTOSS-MOE-IR,
R2A-EXPERT-TRACE-CAPTURE, R1C-OLMOE-MOE-IR, and R6-STEP-N, all of which avoid indexing an
`array<string>` or an array of a Move-field record
Resume condition: Align ships borrow indexing for Move arrays. Section 5.2 of
`docs/specs/r1-qwen-model-ir.md` names the resulting producer surface,
`gguf.read_string_array(path, key) -> Result<array<string>, Error>`, owned by the future tokenizer
capability, not by R1
Align commit or pull request: none
align-llm verification: pending — two targets. `src/gguf.align`'s `render_tensors` NUL-separated
`prefixes: str`/parallel-`array<i64>` workaround (`:120`, `:842`, `:1016-1022`) is the first. The
second, named by `docs/specs/r1-qwen-model-ir.md` section 5.4 as a documentation follow-on now that
R1-QWEN-MODEL-IR has merged (PR #122): once this request reaches `ALIGN_MERGED`, `GgufTable`'s
internals can become indexable `array<KvEntry>`/`array<TensorEntry>` records with no change to any
accessor signature in that document's section 2.3.2, since every accessor is already
index-in/owned-value-out and the stream-plus-column representation is entirely behind them.
`docs/specs/r1b-gptoss-moe-ir.md` section 2.3.4 repeats the same stream-plus-column shape in the new
`BlockPlan`, and `model_forward.StepColumns` repeats it again behind `step_digest_at` and
`step_worst_node_at`, so all three producer surfaces migrate together when this request ships.
```

### Motivation and current sibling evidence

While implementing `src/gguf.align` at pin `4b515f8d37de2e9a9ba06170c5842fd12dc1cba2`, indexing an
`array<string>` or an array of a record with a Move field (`arr[i]`) is rejected. Verified in the
sibling checkout at that exact commit:

- `crates/align_sema/src/lib.rs:52988`, inside `check_index`, reports the exact diagnostic:

  ```rust
  format!("indexing an array of the Move type {} is not supported yet (it would copy the element without transferring ownership)", self.ty_display(elem)),
  ```

  guarded by `collection_element_is_unsupported_move(elem)`. The comment immediately above it
  (`crates/align_sema/src/lib.rs:52982-52985`) states the reason: "the load copies the element's
  `{ptr,len}` without transferring ownership, so the array and the copy would both free the same
  buffer (double-free). Such element reads need a borrow / move-out design (a later slice) — reject
  cleanly until then."
- `docs/language-spec.md:207-215` documents a narrower admitted case: "An indexed Move element of an
  admitted ordinary dynamic array may be passed only to an explicit shared-`borrow` parameter
  selected by a direct, imported, or function-value call." That is call-site-only — the indexed Move
  element may flow straight into a `borrow` parameter of a function call — and does not admit `arr[i]`
  as a general expression (e.g. bound to a local, matched, or read back out of a call result).
- `docs/open-questions.md:4605` and `:4876` record `array<string>` / `array<Move-struct>` as elements
  needing "a later slice" for their per-element deep free, consistent with declaration/storage of
  such arrays now being admitted (`docs/open-questions.md:4936`, J3b, "SHIPPED: `array<Move-struct>`
  struct field") while indexed *reads* of those elements remain the open gap this request names.

**Consequence in align-llm:** `src/gguf.align` cannot store tensor `absolute_offset` values as an
indexable `array<Tensor>`/`array<string>` and read them back by index. `TensorRow` at
`src/gguf.align:120` (`TensorRow { json_prefix: string, offset: i64, offset_field: i64 }`) carries
each tensor's rendered JSON body as a `string` field rather than as an element of an indexable
record array. `render_tensors` at `src/gguf.align:842` reconstitutes the per-tensor bodies from a
single NUL-separated `prefixes: str` stream (`b.write(prefixes[cursor..end])`, splitting on `"\0"`)
plus a parallel `borrow offsets: array<i64>`, because a `array<TensorRow>` or `array<string>` of the
same rendered bodies could not be indexed back out during rendering. The accumulation site is
`src/gguf.align:1016-1022`, where each entry's `json_prefix` is appended to a `builder`
(`tensor_body.write(prefix_view); tensor_body.write("\0")`) instead of being pushed onto an indexable
array, with `row.offset` / `row.offset_field` pushed onto separate parallel `array<i64>` accumulators
(`tensor_offsets.push`, `tensor_offset_fields.push`) to keep every field reachable by position.

### Requested capability

Borrow-indexing for a Move-element array: `arr[i]` yields a `borrow` (or `str` view, for
`array<string>`) without consuming or copying the element, following the existing `check_index`
double-free rationale — the fix is to hand back a borrow instead of a bit-copy, not to make the
element Copy. Alternatively, an explicit `arr.at(i)` borrow accessor alongside `arr[i]`, matching the
`.at(i)` naming convention Align already uses for total, Missing-propagating navigation
(`d.get(k).at(i)` on a `json.doc`, `draft.md:1934`, `docs/language-spec.md:609`). Either spelling is
acceptable; the requirement is a non-consuming read of a Move array element usable as an ordinary
expression, not only as a direct call argument to a `borrow` parameter as `docs/language-spec.md:207`
already admits.

Scope: `array<string>` and `array<Struct>` where the struct has a Move field, matching exactly the
element classes `collection_element_is_unsupported_move` rejects today. No change to the existing
narrower call-argument admission of `docs/language-spec.md:207`, no move-out indexing, and no new
Move container type.

### Public-contract ledger

| Surface | Exact result/error and precedence | Ownership, allocation, effects, and identity | First real-client acceptance |
| --- | --- | --- | --- |
| `arr[i]` on `array<string>` / `array<Struct-with-Move-field>` (or `arr.at(i)`) | Yields a non-consuming `borrow` / `str` view of the element; bounds-checked and aborting exactly like today's Copy-element `xs[i]`; a terminating index forms no bounds action or result, matching the existing convention at `docs/language-spec.md:200-204` | No allocation, no copy of the element's owned buffer, no double-free; the returned view's region is tied to the array's root, following the existing borrowed-place region rules | `align-llm`'s `src/gguf.align` indexes an `array<TensorRow>`/`array<string>` of rendered tensor bodies by position instead of a NUL-separated prefix stream, and `make gguf-smoke` passes |

### Acceptance criteria

1. A compiler test indexes an `array<string>` by borrow and reads the borrowed view as an ordinary
   expression (not only as a direct call argument).
2. A compiler test indexes an `array<Struct>` whose struct has a Move field (e.g. an owned `string`
   field) by borrow and reads a field off the borrowed element.
3. `align-llm` verification: `src/gguf.align` replaces the NUL-separated `prefixes: str` /
   parallel-`array<i64>` workaround (`src/gguf.align:120`, `:842`, `:1016-1022`) with a directly
   indexed `array<TensorRow>` (or equivalent), and `make gguf-smoke` passes.

---

## Request 23 — Huge-struct-copy warning fires on borrow parameters

```text
Status: PROPOSED
Priority: low
Blocking: no
Blocked gate or slice: none
Independent work that may continue: all
Resume condition: Align ships the diagnostic fix
Align commit or pull request: none
align-llm verification: pending — `make check` emits no "huge struct copy" warning for a
  `borrow`/`borrow mut` parameter, specifically none for
  `src/expert_trace.align:1622` (`borrow t: TranscriptScan`), the ten
  `borrow t: GgufTable` accessors in `src/gguf.align`, the three
  `borrow … : gguf.GgufTable` parameters in `src/frontend_olmoe.align`, or the fourteen
  `borrow p: PackPlan` sites in `src/alignpack.align` (`:1261:50`, `:1317:56`,
  `:1331:57` and eleven more), while the by-value warnings the lint
  legitimately owns are unchanged
```

### Motivation and current sibling evidence

**Third client: R2A-EXPERT-TRACE-CAPTURE.** `src/expert_trace.align`'s `TranscriptScan` is another
wide read-only stream-plus-columns record — a `names` stream, ten `array<i64>` columns, and
eighteen scalars, 424 bytes — read by the document renderer through a `borrow` parameter. `make
check` at the pinned toolchain emits, verbatim:

```text
src/expert_trace.align:414:31: warning: huge struct copy: returning `expert_trace$Header` (176 bytes) by value copies it out; narrow the struct (split hot/cold fields) or return a handle
src/expert_trace.align:429:31: warning: huge struct copy: returning `expert_trace$Header` (176 bytes) by value copies it out; narrow the struct (split hot/cold fields) or return a handle
src/expert_trace.align:834:78: warning: huge struct copy: returning `expert_trace$TranscriptScan` (424 bytes) by value copies it out; narrow the struct (split hot/cold fields) or return a handle
src/expert_trace.align:1622:24: warning: huge struct copy: `expert_trace$TranscriptScan` (424 bytes) is passed by value — every call copies it; narrow the struct (split hot/cold fields) or pass a `slice`/view
```

Only the last line is this request's defect. `pub fn build(borrow t: TranscriptScan, path: str)`
never copies its 424 bytes, yet the lint says "is passed by value — every call copies it" because
the parameter loop below consults the parameter's struct type and never its `ParamMode`. The three
`returning … by value` lines above it are the lint working exactly as designed on genuine by-value
returns (`expert_trace.Header` is 176 bytes and is returned from `header_error` and `parse_header`),
and they are **not** evidence for this request — they are quoted so the one line that is evidence
can be told apart from the three that are not.

R1-QWEN-MODEL-IR's `GgufTable` producer surface (`src/gguf.align`) is a wide read-only record — every
metadata and tensor column the decoder recorded — passed to its ten accessors as `borrow t: GgufTable`
so no accessor call copies it. `struct_size_align` puts `GgufTable` at 552 bytes, well past the
lint's own 128-byte threshold, and the pinned compiler's "huge struct copy" lint fires on every one of
those ten accessors even though a `borrow` parameter never copies the struct — the lint's purpose,
per its own message ("every call copies it"), does not apply to it at all.

Verified in the sibling checkout at the pinned commit `4b515f8d37de2e9a9ba06170c5842fd12dc1cba2`
(`crates/align_sema/src/lib.rs`, function `check_fn` around the "huge struct copy" lint block):

- `crates/align_sema/src/lib.rs:40525-40529` documents the lint as targeting a struct "passed or
  returned **by value**"; the comment names exactly the case this request says is mishandled.
- `crates/align_sema/src/lib.rs:40544-40553` is the parameter loop that actually emits it:

  ```rust
  for (p, ty) in f.params.iter().zip(&param_tys) {
      if let Ty::Struct(id) = *ty
          && let Some((sz, name)) = huge(self.structs, id, &mut visiting)
      {
          self.diags.push(align_diag::Diagnostic::warning(
              format!("huge struct copy: `{name}` ({sz} bytes) is passed by value — every call copies it; narrow the struct (split hot/cold fields) or pass a `slice`/view"),
              p.ty.span(),
          ));
      }
  }
  ```

  The loop reads only `ty` (the parameter's struct type) and never reads `p`'s mode. `align_ast`
  carries the mode separately — `crates/align_ast/src/lib.rs:184-188` defines
  `pub enum ParamMode { ByValue, Out, Borrow, BorrowMut }`, and the signature's parallel
  `sig.param_modes: Vec<ParamMode>` is already in scope in the same function (consulted a few lines
  above at `crates/align_sema/src/lib.rs:40513` for the unrelated `main`-argv shape check). The lint
  never consults it, so it fires identically for `fn f(x: Big)` and `fn f(borrow x: Big)`.

- Reproduced against `src/gguf.align` by running `gmake check` in the worktree with
  `export LIBRARY_PATH=/opt/homebrew/lib:/opt/homebrew/opt/openssl@3/lib:/opt/homebrew/opt/zstd/lib`.
  All ten `borrow t: GgufTable` accessors (`find_key`, `find_tensor`, `kv_type`, `kv_int`,
  `kv_float_bits`, `kv_string`, `kv_float_text`, `kv_array_length`, `tensor_name`, `tensor_dim`, at
  `src/gguf.align:1361,1373,1388,1394,1401,1408,1418,1426,1435,1441`) each emit the warning. One
  verbatim line:

  ```text
  src/gguf.align:1361:27: warning: huge struct copy: `gguf$GgufTable` (552 bytes) is passed by value — every call copies it; narrow the struct (split hot/cold fields) or pass a `slice`/view
  ```

  The message's own claim — "is passed by value — every call copies it" — is false for this call
  site: `find_key(borrow t: GgufTable, key: str)` takes `t` by `borrow`, and `GgufTable`'s Move fields
  (its `string` and `array<i64>` columns) are never duplicated at the call boundary.

**Additional client evidence, from the R1B-GPTOSS-MOE-IR capability, now implemented.**
`src/model_ir.align:86` declares `BlockPlan`, the architecture-neutral block plan a frontend hands
the neutral builder. It is a second, independent client of the same false positive, and it is
**narrower** than `GgufTable`, not wider: 36 fields and 440 bytes against `GgufTable`'s 41 fields and
552 bytes (`docs/specs/r1b-gptoss-moe-ir.md` section 7, items 3 and 14, which correct that document's
own earlier "wider" and "nineteen-column" claims). That makes the evidence stronger rather than
weaker — the warning tracks the declared struct type and ignores the parameter mode, so a smaller
record trips it just as reliably.

Reproduced the same way, `gmake check` in the worktree with the recorded `LIBRARY_PATH`. Both
`borrow plan: BlockPlan` parameters emit it, and nothing else in the module does:

```text
src/model_ir.align:478:27: warning: huge struct copy: `model_ir$BlockPlan` (440 bytes) is passed by value — every call copies it; narrow the struct (split hot/cold fields) or pass a `slice`/view
src/model_ir.align:635:16: warning: huge struct copy: `model_ir$BlockPlan` (440 bytes) is passed by value — every call copies it; narrow the struct (split hot/cold fields) or pass a `slice`/view
```

Line 478 is `fn span_text(borrow plan: BlockPlan, start: i64, end: i64) -> string`, the plan's one
accessor; line 635 is the `borrow plan: BlockPlan` parameter of `pub fn build`, into which the
frontend moves its plan exactly once per invocation. Neither call site copies the record, and
`BlockPlan`'s Move fields — its three owned `string`s and seventeen `array<i64>` columns — are never
duplicated at either boundary.

**Fourth client, from the planned R4-ALIGNPACK-LAYER-MAJOR capability.**
`docs/specs/r4-alignpack-layer-major.md` section 2.1 records `PackPlan` — the layout planner's
columns-plus-name-stream record, read through `borrow` accessors by the same shape as `GgufTable`,
`BlockPlan`, and `TranscriptScan` before it (`docs/specs/r4-alignpack-layer-major.md`: "`array<i64>`
columns behind `borrow` record accessors; `array_builder<i64>`; concatenated name stream with
explicit `[start, end)` spans — Shipped, three prior instances (`GgufTable`, `BlockPlan`,
`TranscriptScan`) … The layout plan is the same shape, fourth instance").

**`src/alignpack.align` now exists and the warning is reproduced.** `PackPlan` is 480 bytes — one
owned `string` name stream, twenty-two `array<i64>` columns, and twelve scalars — and every function
that reads it takes it as `borrow p: PackPlan`. The three encoders are the clearest case: each one
writes fixed-width fields out of the plan into a buffer and copies nothing. `gmake check` at the
pinned toolchain emits, verbatim:

```text
src/alignpack.align:1261:50: warning: huge struct copy: `alignpack$PackPlan` (480 bytes) is passed by value — every call copies it; narrow the struct (split hot/cold fields) or pass a `slice`/view
src/alignpack.align:1317:56: warning: huge struct copy: `alignpack$PackPlan` (480 bytes) is passed by value — every call copies it; narrow the struct (split hot/cold fields) or pass a `slice`/view
src/alignpack.align:1331:57: warning: huge struct copy: `alignpack$PackPlan` (480 bytes) is passed by value — every call copies it; narrow the struct (split hot/cold fields) or pass a `slice`/view
```

Reproduction:

```sh
export LIBRARY_PATH=/opt/homebrew/lib:/opt/homebrew/opt/openssl@3/lib:/opt/homebrew/opt/zstd/lib
gmake check 2>&1 | grep 'alignpack.align.*huge struct copy'
```

Line 1261 is `fn encode_header(borrow mut b: buffer, borrow p: PackPlan)`, line 1317 is
`fn encode_block_record(borrow mut b: buffer, borrow p: PackPlan, index: i64)`, and line 1331 is
`fn encode_member_record(borrow mut b: buffer, borrow p: PackPlan, index: i64)`. Eleven further
`borrow`-mode sites in the same module report the same warning for `PackPlan`, and the module emits
53 `huge struct copy` warnings in total against 454 for the whole repository — every one of the
`PackPlan` rows is a `borrow` parameter that copies nothing. The by-value branch the lint
legitimately owns is unaffected: `src/alignpack.align:1376:22` (`empty_header` returning a 160-byte `PackHeader`)
and `:498:20` (`empty_plan` returning the 480-byte `PackPlan`) are real owned returns and are
correctly reported.

**Fifth client — and the third *frontend* — from R1C-OLMOE-MOE-IR, now implemented at `45e4ced`.**
`src/frontend_olmoe.align` is the olmoe Model IR frontend. It never declares a wide record of its
own: it *builds* a `model_ir.BlockPlan` and moves it into `model_ir.Prepared`, so the design ledger's
prediction that it would trip the lint on a `borrow BlockPlan` parameter was wrong
(`docs/specs/r1c-olmoe-moe-ir.md` section 6 item 10). It trips it instead on the record it reads —
`gguf.GgufTable`, 552 bytes — at all three of its `borrow` parameters, one private and two public.
`gmake check` at the pinned toolchain emits, verbatim:

```text
src/frontend_olmoe.align:64:32: warning: huge struct copy: `gguf$GgufTable` (552 bytes) is passed by value — every call copies it; narrow the struct (split hot/cold fields) or pass a `slice`/view
src/frontend_olmoe.align:182:37: warning: huge struct copy: `gguf$GgufTable` (552 bytes) is passed by value — every call copies it; narrow the struct (split hot/cold fields) or pass a `slice`/view
src/frontend_olmoe.align:189:30: warning: huge struct copy: `gguf$GgufTable` (552 bytes) is passed by value — every call copies it; narrow the struct (split hot/cold fields) or pass a `slice`/view
```

Reproduction:

```sh
export LIBRARY_PATH=/opt/homebrew/lib:/opt/homebrew/opt/openssl@3/lib:/opt/homebrew/opt/zstd/lib
gmake check 2>&1 | grep 'frontend_olmoe.align.*huge struct copy'
```

Line 64 is `fn kv_text_decodable(borrow t: gguf.GgufTable, key: str) -> bool`, line 182 is
`pub fn build_model_ir(borrow table: gguf.GgufTable, path: str) -> model_ir.ModelIr`, and line 189 is
`pub fn prepare(borrow table: gguf.GgufTable) -> model_ir.Prepared`. None of the three copies the
table: `src/main.align` reads it once per invocation into one local and borrows it into whichever
frontend the architecture selects. The evidence value of this client is that the *same* struct type
now demonstrates the defect from two independent modules — `src/gguf.align`'s own accessors and a
consumer that only borrows it across a module boundary — so the misfire is a property of the lint's
parameter loop and not of one module's style. The by-value branch the lint legitimately owns is
correct in the same file and is quoted here only so it is not mistaken for evidence:
`src/frontend_olmoe.align:182:67` (returning `model_ir$ModelIr`, 176 bytes) and `:189:49` (returning
`model_ir$Prepared`, 568 bytes) are genuine owned returns.

**Sixth client, from the active R3-RESIDENCY-SIM capability.** `residency_sim$Derived` (440 bytes,
`src/residency_sim.align:1158`) is a sixth wide read-only record read through a `borrow` parameter.
`gmake check` at the pinned toolchain (`4b515f8d37de2e9a9ba06170c5842fd12dc1cba2`, `alignc 0.5.0`)
emits, verbatim, all four `huge struct copy` warnings the module produces:

```text
src/residency_sim.align:485:71: warning: huge struct copy: returning `residency_sim$TraceLoad` (184 bytes) by value copies it out; narrow the struct (split hot/cold fields) or return a handle
src/residency_sim.align:511:6: warning: huge struct copy: returning `residency_sim$TraceLoad` (184 bytes) by value copies it out; narrow the struct (split hot/cold fields) or return a handle
src/residency_sim.align:1203:30: warning: huge struct copy: `residency_sim$Derived` (440 bytes) is passed by value — every call copies it; narrow the struct (split hot/cold fields) or pass a `slice`/view
src/residency_sim.align:1387:68: warning: huge struct copy: returning `residency_sim$ResidencySim` (200 bytes) by value copies it out; narrow the struct (split hot/cold fields) or return a handle
```

Only the third line, `:1203:30`, is this request's defect: `render_document(borrow d: Derived) ->
string` (`:1203`) takes `d` by `borrow` and never copies it. The other three lines are the lint
working exactly as designed on genuine by-value returns — `empty_trace_load` (`:485`) and
`trace_load` (`:511`) both return an owned `TraceLoad` by value, and `simulate` (`:1387`) returns an
owned `ResidencySim` by value — and are quoted, as in the `expert_trace.align` evidence above, only
so the one line that is evidence can be told apart from the three that are not. Four sites in the
module in total: one instance of this request's false positive, three correctly-targeted warnings.

The count is now six clients across five wide records (`GgufTable`, `BlockPlan`, `TranscriptScan`,
`PackPlan`, `Derived`) and every architecture frontend in the repository. The status stays `PROPOSED` and
`Blocking: no`; no workaround is written, and none of these sites is restructured to silence a
diagnostic that is wrong about them.

### Requested capability

Suppress the diagnostic for a `Borrow`/`BorrowMut` parameter — no new syntax, no new diagnostic code,
just consulting the mode the sema pass already carries in `sig.param_modes` (or the AST `p.mode`
directly) before pushing the warning at
`crates/align_sema/src/lib.rs:40544-40553`. The by-value branch (a bare `x: Big`) and the return-type
branch (`crates/align_sema/src/lib.rs:40554-40560`, which returns a fresh owned value and is correctly
targeted regardless of mode) are both unaffected.

### Acceptance criteria

1. A compiler test declares a struct at or above `HUGE_STRUCT_BYTES` and a function taking it by
   `borrow` (and one by `borrow mut`): neither emits the huge-struct-copy warning.
2. A negative control in the same test: the identical struct taken by value still emits the warning,
   so the fix narrows the diagnostic rather than disabling it.
3. `align-llm` verification: `make check` on `src/gguf.align` at the adopted pin emits zero
   huge-struct-copy warnings for the ten `borrow t: GgufTable` accessors.

---

## Request 24 — `builder` as a `borrow mut` parameter type

```text
Status: PROPOSED
Priority: medium
Blocking: no
Blocked gate or slice: none (duplication in place)
Independent work that may continue: all
Resume condition: Align ships builder parameters
Align commit or pull request: none
align-llm verification: pending
```

If the active R2A-EXPERT-TRACE-CAPTURE (`docs/specs/r2a-expert-trace.md`) needs its own
decode-and-accumulate walk over a `llama-eval-callback` transcript — expected, given the shape of
that consumer — it becomes a further client of this request's duplicated-walk workaround, the same
way `gguf.inspect`/`gguf.read_table` are today; that would add client evidence without changing this
request's status.

### Motivation and current sibling evidence

`array_builder<T>` is admitted as a `borrow mut` parameter type at the pinned commit
`4b515f8d37de2e9a9ba06170c5842fd12dc1cba2`, but the plain text `builder` (`core.builder`, listed
among the core areas at `docs/language-spec.md:970` in the sibling checkout, with its `borrow mut`
rule stated for the array form at `:1004-1006`) is not admitted in that position at all; it is
rejected as an unknown type name.

Verified in the sibling checkout:

- `crates/align_sema/src/lib.rs:3269-3298` (`BUILTIN_SPELLING_TYS`) is the reserved-type-name table
  consulted when a bare identifier is used as a type. It lists `("buffer", Ty::Buffer)` and
  `("array_builder", Ty::ArrayBuilder(BRIDGE_ELEM))`, but has no `"builder"` entry at all — `Ty::Builder`
  (defined and used elsewhere in the same file, e.g. `crates/align_sema/src/lib.rs:51009`,
  `:59325`) is reachable only from the `builder()`/`builder(cap)` *expression* form
  (`crates/align_sema/src/lib.rs:50987`, `check_builder_new`), never from a type annotation.
  `crates/align_sema/src/lib.rs:4958` is the fallback that fires when a bare name matches neither a
  declared type nor a `BUILTIN_SPELLING_TYS` entry: `diags.error(format!("unknown type: '{bare}'"),
  span)`.
- Reproduced directly against the pinned managed compiler (`alignc check` on a two-line probe module):
  `fn f(borrow mut b: builder) -> i64 { return 0 }` fails with
  `probe.align:3:24: error: unknown type: 'builder'`, while the identical probe with
  `borrow mut b: array_builder<i64>` compiles clean (`ok: checked 1 function(s)`).
- `docs/language-spec.md:1004-1006` (`core.array_builder`, section on the region-backed
  plain-struct builder) already states the intended rule for the array form: "a helper may push
  through a `borrow mut` parameter but cannot store, return, or consume that borrowed builder" — the
  request asks Align to extend the identical rule to the text `builder`, not to invent a new one.
  `docs/impl/17-library-boundary-prerequisites.md:1066-1068` states the same rule a second time for
  `array_builder`'s region-backed form ("A helper may push through a `borrow mut` builder parameter,
  but a builder is not a `RegionPlain` value...").

**Consequence in align-llm:** `src/gguf.align` comments its own workaround at the definition site
(`src/gguf.align:1250-1253`): "`read_table` and `inspect` are two walks over one decoder: they call
the same `decode_header`, `decode_kv`, `decode_tensor`, `resolve_data_offset`, and
`check_tensor_ranges`. They cannot share a single walk function because `builder` is not a parameter
type at this pin (section 2.3.6), so each accumulates its own bodies inline." The two duplicated
walks are `pub fn inspect` at `src/gguf.align:1091` and `pub fn read_table` at `src/gguf.align:1455`;
`docs/specs/r1-qwen-model-ir.md` section 2.3.6 ("One decoder, two walks", committed at that document's
`:373-390`) records the same constraint as design-level debt, and its closure-matrix row 2
(`docs/specs/r1-qwen-model-ir.md:1433`) records the exact probe result this request reproduces above:
"`array_builder<T>` *is* a `borrow mut` parameter type at this pin; `builder` is not. … the two walks
still cannot share a walk function, because what they must accumulate is a `builder`." R0's document
walk (`docs/specs/r0-gguf-inspection.md`) was inlined into `inspect` directly for the same reason
before `GgufTable`/`read_table` existed.

### Requested capability

Admit `borrow mut b: builder` as a parameter type, with the same region/escape rules Align already
enforces for `array_builder<T>` as a `borrow mut` parameter: a helper may `write` through it, but
cannot store it past the call, return it, or otherwise let it escape or be consumed inside the callee
— only the caller's own binding may call `.to_string()`/finish it. No new syntax beyond adding
`("builder", Ty::Builder)` (or the equivalent parameter-position admission) alongside the existing
`array_builder` entry.

### Acceptance criteria

1. A compiler test appends through a `borrow mut b: builder` parameter from inside a helper function
   and finishes (`.to_string()`) the builder in the caller after the call returns, observing every
   appended byte.
2. A compiler test confirms the callee cannot store, return, or consume the borrowed builder (still a
   compile-time rejection, matching the existing `array_builder<T>` `borrow mut` boundary).
3. `align-llm` verification: refactor `src/gguf.align`'s `inspect` (`:1091`) and `read_table`
   (`:1455`) onto one shared decode-and-accumulate walk taking a `borrow mut b: builder` parameter (or
   equivalent), removing the duplicated inline accumulation the section 2.3.6 comment names, and pass
   `make gguf-smoke model-ir-smoke`.

---

## Request 25 — Streaming child stdout (redirect or incremental read) for `std.process`

```text
Status: PROPOSED
Priority: medium
Blocking: no
Blocked gate or slice: none. R2A-EXPERT-TRACE-CAPTURE (`docs/specs/r2a-expert-trace.md`) consumes a
  transcript *file* and never invokes `llama-eval-callback` itself (section 1.3's stated non-goal),
  so `scripts/run-expert-trace-parity`'s shell redirection stands in for this request and the gap is
  designed around rather than hit. It becomes blocking for the first capability that must run an
  unbounded-output child in-process rather than through a shell.
Independent work that may continue: all of R2A, R2b's transcript collection through the shell, and
  every existing verify/repair client whose child output is small enough for the shipped whole-stdout
  capture.
Resume condition: Align ships a streaming or redirecting stdout surface on `std.process` — an
  incremental `reader` on a piped child, or a kernel-level redirect to a file — and align-llm adopts
  it in a future acquisition verb that invokes the instrument directly.
Align commit or pull request: none
align-llm verification: pending — capture the instrument transcript from align-llm itself (rather
  than the shell) and pass `make expert-trace-smoke` plus `scripts/run-expert-trace-parity` against
  that self-captured transcript.
```

### Motivation and current sibling evidence

R2A-EXPERT-TRACE-CAPTURE (`docs/specs/r2a-expert-trace.md` section 2.1) turns `llama-eval-callback`'s
entire stdout transcript into a machine-readable document. The instrument's whole output is a text
stream on stdout, and R2A's own measurement on this host (`docs/specs/r2a-expert-trace.md:1155-1157`,
section 5.5.1) recorded 1,487,718 and 1,101,250 bytes for a 5-token and a 3-token prompt against a
dense 7B model, extrapolating a patched multi-graph MoE decode capture to hundreds of megabytes
(section 2.2, finding 9). R2A itself never invokes the instrument (non-goal, section 1.3): the CLI
consumes a file the shell already redirected into, which is exactly why this request is non-blocking
for R2A. But the same shape — run a child that emits an unbounded text stream, consume it
incrementally, discard it — is the ordinary shape of a compiler, test runner, profiler, or tracer, and
`align-coder`'s own verify/repair loop (Request 1) is already a `std.process` client.

Verified in the sibling checkout at the pinned commit `4b515f8d37de2e9a9ba06170c5842fd12dc1cba2`:

- `docs/language-spec.md:1093-1099` is the complete `std.process` surface at this pin: `spawn` /
  `wait` / `kill` / `exec`, `exit` / `abort`, `cpu_count()`, and the `command` builder —
  `process.command(cmd, args)` plus `cwd`/`env`/`env_clear`/`timeout_ns` setters, the optional
  `max_capture_bytes(limit)` bound, `run() -> Result<run_output, Error>` for UTF-8 text capture, and
  `run_bytes() -> Result<run_bytes, Error>` for arbitrary bytes; `stdout()`/`stderr()` on either
  output handle are "region-bound zero-copy views" — of the *complete* captured stream, materialized
  before `run()`/`run_bytes()` returns. `max_capture_bytes` only bounds the total size Align will hold
  before rejecting with `Error.Invalid`; it does not expose any byte before the child exits.
- `docs/impl/std-design/process.md:216-218` states the alternative directly: "`spawn` does a bare
  `fork` + `execvp` with **no pipes and no `dup2`**: the child inherits the parent's fds and its
  output goes straight to the terminal. The `child` handle is `{ pid, reaped }` only." `process.spawn`
  therefore does no redirection at all and is not an alternative capture path; a caller cannot attach
  a pipe to it.
- `docs/impl/std-design/process.md:280` documents `out.stdout() -> str` as "captured stdout, zero-copy
  view into `out` (region-bound to `out`)" — the view exists only on the `run_output` handle returned
  after the whole child has been drained, never incrementally.
- No chunked, streaming, or reader-based access to a child's stdout appears anywhere in
  `docs/impl/std-design/process.md`; the only per-stream control is the exact-size `max_capture_bytes`
  bound described above (`docs/impl/std-design/process.md:477-481`), which fails closed on overflow
  rather than yielding a prefix.
- align-llm's own register already records this shape for the shipped surface: Request 1's
  "COMPLETE" note (`docs/align-requests.md:96-103`) states `out.stdout()/.stderr()` are "zero-copy
  `str` views region-bound to `out`" with a deferred raw-bytes tier — i.e. the existing capture is a
  whole-value return, not a stream, at every tier Align ships.

**Consequence for align-llm:** an align-native acquisition verb that invoked `llama-eval-callback`
directly would have to materialize the entire transcript as one `str`/`slice<u8>` value before
reading its first line, for a scan that R2A's bounded line reader (section 2.4) needs at most
`MAX_LINE_BYTES` resident to perform. The shipped shell-redirect workaround (`scripts/
run-expert-trace-parity` redirects the instrument's stdout to a file R2A then opens with
`fs.open_rw`) is a good design on its own merits and is not being replaced; the language-owned gap is
recorded because a workaround existing does not make it an application concern.

### Requested capability

Two shapes were weighed, following the existing `process`/`file`/`io` surfaces rather than inventing
a new abstraction:

1. **Preferred — an incremental `reader` on a piped child.** Align already ships exactly one
   incremental-read idiom: `r.read(b: mut buffer) -> Result<i64, Error>` fills `b` up to capacity,
   `0` means EOF (`docs/language-spec.md:1035`; the canonical `pump` loop at
   `docs/guide/13-std-os.md:122-132` drives `io.stdin`/`io.stdout` and `fs.open`'s `reader` with the
   identical pattern). Extending that same `reader` type to a piped child's stdout needs no new type
   and no new read protocol:

   ```align
   c := process.command(cmd, args)
   ch := c.spawn_piped()?        // Result<child, Error> — like process.spawn, but stdout/stderr
                                  // are pipes (not inherited) so they can be taken as readers
   r := ch.take_stdout()         // reader, Move, region-bound to ch, same type fs.open() returns
   loop {
       n := r.read(buf)?         // fills buf to capacity; 0 = EOF, identical to every other reader
       if n == 0 { break }
       // consume buf.bytes()[..n] incrementally, discard, repeat
   }
   code := ch.wait()?
   ```

2. **Rejected as the primary ask — `c.stdout_to(path: str)` kernel-level redirect.** This only moves
   the materialization from memory to disk; the consumer must still reopen and re-read the file to
   get any access to the data, either after the child exits or by racing a still-growing file with no
   defined read-while-write contract — it does not change the shape of the problem this request names
   (process incrementally, discard, bounded memory, no wait for exit). It would also duplicate rather
   than reuse the shipped `fs`/`reader` surface, since the caller ends up hand-rolling the same
   growing-file-poll loop `align-llm` already avoids by using a real pipe conceptually.

Option 1 is proposed because it is the smaller, more Align-consistent change: it reuses the exact
`reader`/`.read(buf)` contract already shipped for every other stream in `std.io`, adds one command
method and one child accessor, and needs no new type, no new read protocol, and no change to the
existing whole-stdout `run()`/`run_bytes()` capture (which stays the right choice for small,
finite-size tool output). The exact spelling (`spawn_piped`/`take_stdout`, or an equivalent naming
Align prefers) is Align's call; the requirement is the capability, not the name.

### Acceptance criteria

1. A compiler test spawns a child that writes more bytes to stdout than the test's read buffer's
   capacity and asserts that `reader.read` returns before the child exits — i.e. that at least one
   partial read is observed while the child process is still alive, proving the surface streams
   rather than buffers the whole output before returning.
2. A compiler test confirms `reader.read` reaches `0` (EOF) exactly when the child closes its stdout
   descriptor, and that `child.wait()` still reports the correct exit code afterward, matching the
   existing `reader`/EOF convention used elsewhere in `std.io`.
3. `align-llm` verification: an acquisition verb built on this surface captures the
   `llama-eval-callback` transcript from within align-llm (rather than through the shell) with
   resident memory bounded by `MAX_LINE_BYTES` (or `WINDOW_BYTES`) rather than by transcript size, on
   a transcript of at least 100 MB, and the resulting document passes `make expert-trace-smoke` and
   `scripts/run-expert-trace-parity` identically to the shell-captured path.

---

## Request 26 — `str`-to-integer parsing in the standard library

```text
Status: PROPOSED
Priority: medium
Blocking: no
Blocked gate or slice: none. Three call sites route a plain decimal integer through a `json.decode`
  detour and R2A writes the one private parser the detour cannot serve.
Independent work that may continue: all of it — this is a duplication and correctness-surface
  concern, not a capability gate.
Resume condition: Align ships a checked text-to-integer conversion (e.g. `str.parse_i64() ->
  Result<i64, Error>`) with a stated overflow/sign/whitespace contract; align-llm then drops the
  three `json.decode` detours and R2A's private parser and adopts the shipped surface.
Align commit or pull request: none
align-llm verification: pending — replace the three `json.decode` detours
  (`src/main.align:71` `parse_i64`, `src/failure_memory.align:176` `parse_integer`,
  `src/c6f1_request11_adoption.align:6` `parse_i64`) and the one private parser
  (`src/expert_trace.align:328` `parse_uint`) with the shipped surface and pass their
  owners: `make check failure-memory-smoke expert-trace-smoke` plus the `c6f1_request11_adoption`
  owner.
```

### Motivation and current sibling evidence

Align at the pinned commit `4b515f8d37de2e9a9ba06170c5842fd12dc1cba2` has no surface anywhere in the
standard library that converts a `str` to a number.

Verified in the sibling checkout:

- `docs/language-spec.md:625-643` is the complete enumerated method list for `str`: `.len()`, `==`/
  `!=`, `.contains(n)`/`.starts_with(p)`/`.ends_with(s)`, `.find(n)`/`.rfind(n)` → `Option<i64>`,
  `.eq_ignore_ascii_case(o)`, and `.trim()`/`.trim_start()`/`.trim_end()`. No `parse`, `parse_i64`,
  `parse_int`, `to_i64`, `as_i64`, or `atoi`-shaped method exists on `str`. A repository-wide search
  for `parse_int|parse_i64|parse_f64|to_i64|atoi` across `docs/language-spec.md` and `docs/guide/*.md`
  returns no `std.process`/core-language hit; the only `.parse` in that search is `std.cli`'s
  argument-vector parser (`c.parse(args)?`, `docs/guide/14-std-encoding-rand-cli.md:93`), an unrelated
  flag-parsing surface, not a text-to-number conversion.
- The two places the runtime *does* parse a number from text are buried, not general: `json.doc`'s
  leaf accessor `as_i64` (`docs/language-spec.md:610`, → `Option`) requires wrapping the input in a
  JSON document inside an `arena {}`, and `std.cli`'s `p.get_i64(name)`
  (`docs/guide/14-std-encoding-rand-cli.md:95`) is reachable only through a registered CLI flag.
  Neither is a general `str`-to-`i64` conversion a caller can invoke on an arbitrary substring.
  `docs/open-questions.md:384` records that the compiler's own numeric-literal *lexer* already does
  the underlying work internally ("the lexer parses the prefix (greedy alphanumeric run) →
  `i128::from_str_radix`"), but that logic is not exposed as a callable stdlib surface.
- `docs/language-spec.md:625-643`'s same enumeration also has no `.split` method on `str` — R2A's own
  ledger already records the sibling fact that `.split` exists only as a `regex` method at this pin
  (`docs/specs/r2a-expert-trace.md`, section 2.1 table row "`s.split(...)`"), which is why R2A's
  header parser composes `.find` + range slicing explicitly rather than splitting.

**Evidence from this repository, which is the point.** Every existing align-llm call site that needs
an integer out of text takes the JSON detour, because there is nothing else to take. Verified by
reading each function in this worktree:

```align
// src/main.align:71                    // src/failure_memory.align:176
fn parse_i64(value: str)                fn parse_integer(value: str)
    -> Result<i64, Error> {                 -> Result<i64, Error> {
  number: i64 := json.decode(value)?      number: i64 := json.decode(value)?
  return Ok(number)                       return Ok(number)
}                                       }

// src/c6f1_request11_adoption.align:6
fn parse_i64(value: str) -> Result<i64, Error> {
  decoded: i64 := json.decode(value)?
  return Ok(decoded)
}
```

Three call sites, three two-line wrappers, all routing a plain decimal integer through a JSON
decoder. That is the gap made visible: `json.decode` is not a text-to-integer conversion, it is a
document decoder being used as one because the standard library offers no other spelling.

**And the fourth consumer cannot even do that**, which is the stronger half of the argument.
`docs/specs/r2a-expert-trace.md` section 2.2 finding 5 records that llama.cpp prints *every* tensor
element through `%12.4f`, so an expert id arrives as `     12.0000`. That is not a JSON integer;
decoding it as a JSON *number* would route an exact array index through an `f64`, which is precisely
what an array index must never do. Tensor dimensions and layer suffixes arrive inside header lines
that are not JSON at all. So `src/expert_trace.align:328` writes the one genuine private parser,
`fn parse_uint`, with its own comment recording the gap directly ("The bounded decimal integer parse
Align has no standard-library form of"), plus `parse_integral_element` on top of it to reject a
sign, a non-zero fraction, `nan`, and `inf` without a float parse.

So the register's claim is not "four hand-rolled parsers" — it is one private parser and three
`json.decode` detours, which is a worse shape: the three call sites silently inherit a JSON
document's number grammar, its overflow behavior, and its whitespace rules for a value that is not
JSON, and nobody reading them would notice. A workaround existing does not make this a purely
application concern — it is exactly the class of duplication `CLAUDE.md`'s request-register rule
exists to surface.

**Second client, from the active R3-RESIDENCY-SIM capability.** `BUDGET_BYTES`, the fourth CLI
operand of `--simulate-residency`, needs the same conversion for a reason specific to *this*
operand: a `json.decode` detour would accept `-0`, `1e3`, and leading whitespace, none of which a
byte budget admits, and `src/expert_trace.align:328`'s existing `parse_uint` is not reusable either
— it trims `%12.4f`-padded whitespace and tolerates a leading `+`, a contract this operand does not
want. `src/residency_sim.align:264-279` (`fn parse_budget`, 16 lines) is therefore a second private
parser, with its own explicit non-wrapping overflow guard (`if total > (I64_MAX - digit) / 10 {
return -1 }`, `:273`) rather than a delegation to either existing workaround — the same pattern this
request's own text already established for `src/expert_trace.align`'s private parser: every call
site that needs an integer out of text and cannot tolerate the JSON detour's grammar writes its own.
It is non-blocking — the private parser is in place — with all of R3-RESIDENCY-SIM as independent
work.

### Requested capability

A checked text-to-integer conversion on `str`, matching Align's existing `Option`/`Result` idioms
(the same pattern `.find`/`.rfind` already establish for a fallible lookup on `str`, and the pattern
`std.fs`/`std.process` already establish for a fallible conversion that should carry a reason rather
than a bare `None`):

```align
s.parse_i64() -> Result<i64, Error>   // or Option<i64>, Align's call — see below
```

with a stated contract for:

- **Sign.** An optional leading `+`/`-`.
- **Whitespace.** Whether leading/trailing ASCII whitespace is trimmed automatically or rejected.
  align-llm's three `json.decode` call sites inherit whatever the JSON decoder does — which none of
  their authors chose — while `src/expert_trace.align`'s `parse_integral_element` trims explicitly
  because a `%12.4f` field is padded. A single settled contract is what would let all four agree on
  purpose rather than by accident.
- **Overflow.** Out-of-range input is a defined error (`Error.Invalid` or equivalent), not a silent
  wrap, consistent with `docs/open-questions.md:249`'s existing zero-UB-by-design numeric conversion
  rule for `as` casts (int→int wraps only under an explicit cast; nothing about `str` parsing should
  wrap implicitly).
- **Empty / non-digit input.** A defined error, not an abort.

`Result<i64, Error>` is proposed over `Option<i64>` because the existing `str` predicate/lookup
methods (`.find`, `.rfind`) return `Option` for a "not present" outcome, while all three of this
repository's existing call sites already return `Result<i64, Error>` for a "malformed" outcome —
closer in kind to a decode failure than a missing-value lookup. Align may prefer `Option` for symmetry with
`json.doc`'s `as_i64`; either satisfies this request, and the acceptance criteria below are phrased to
accept whichever Align settles on.

Whether Align also ships a `str.parse_f64()` is Align's call and this request takes no position:
`docs/specs/r2a-expert-trace.md` section 2.2 finding 5 means R2A itself needs only the integer form,
so no genuine float-parsing consumer is recorded here.

### Acceptance criteria

1. A compiler test converts a well-formed positive and negative decimal `str` (including a leading
   `+`) to the expected `i64`, and a malformed input (empty, non-digit, embedded sign, or
   out-of-range) to the defined error/`None`, pinning whichever return type and contract Align
   chooses.
2. A compiler test pins the settled whitespace and overflow behavior named above, so a future change
   to either is a deliberate, reviewed decision rather than a silent drift.
3. `align-llm` verification: `src/main.align:71`, `src/failure_memory.align:176`, and
   `src/c6f1_request11_adoption.align:6` each drop the `json.decode` detour for the shipped surface,
   and `src/expert_trace.align:328` adopts the shipped surface instead of its private `parse_uint`.
   `make check failure-memory-smoke expert-trace-smoke` and the `c6f1_request11_adoption`
   owner pass unchanged.

---

## Request 27 — String ordering and sorting

```text
Status: PROPOSED
Priority: medium
Blocking: no
Blocked gate or slice: none. `src/expert_trace.align` hand-writes the ordering and the sort it
  needs, and `src/model_ir.align` packs a hash to avoid needing either.
Independent work that may continue: all of it — both hand-written workarounds are in place and nothing
  downstream depends on this request.
Resume condition: Align ships `array<T>.sort()` over `str` (and owned `string`) elements directly, and/or
  the general comparator overload the compiler's own `check_array_sort` already anticipates
  (`crates/align_sema/src/lib.rs:50602-50603`, "a `sort(cmp)` overload is a follow-up"); align-llm then
  deletes the private `span_less`/`sort_spans` pair in `src/expert_trace.align` and reconsiders the
  packed-hash index in `src/model_ir.align`.
Align commit or pull request: none
align-llm verification: pending — replace `span_less`/`sort_spans` in `src/expert_trace.align`
  (`src/expert_trace.align:656-730`) and the packed-42-bit-hash name index in `src/model_ir.align`
  (`src/model_ir.align:261-301`) with the shipped surface, and pass `make expert-trace-smoke
  model-ir-smoke`.
```

### Motivation and current sibling evidence

**Correction before the evidence below: `str`/`string` already satisfy `Ord` at this pin, and
`sort_by_key` already admits a `str` key.** An earlier draft of this request assumed Align ships no
string ordering at all; that assumption does not hold and is recorded here so a future reader does not
duplicate the discovery. Verified in the sibling checkout at the pinned commit
`4b515f8d37de2e9a9ba06170c5842fd12dc1cba2`, and confirmed by compiling and running small programs
against the exact toolchain align-llm materializes for this pin
(`/Users/hiro/.cache/align-llm/align/dev-v1/4b515f8d37de2e9a9ba06170c5842fd12dc1cba2/target/release/alignc`,
`alignc 0.5.0`):

- `docs/language-spec.md:250-260`: "`str`/`string` are `Ord` (byte-lexicographic; locale collation is
  a library concern), so strings sort and compare. A `sort_by_key` key is a **Copy** `Ord` value — a
  number, a `char`, or a borrowed `str`; an owned `string` key type-checks but is then rejected at the
  MIR boundary as an internal error … so project the key to a `str`." and "Comparison operators and
  `Eq`/`Ord` bounds accept both `str` and owned `string`." `docs/language-spec.md:271` restates the
  bound: `Ord` = "numbers, `char`, `str`". `docs/guide/06-pipelines.md:85` independently confirms
  `sort_by_key`'s key "must be an orderable scalar — an int, a float, a `char`, or a `str`."
  `docs/open-questions.md:2926-2941` ("`Ord(str)` … SETTLED (2026-07-09) … **IMPLEMENTED**") is explicit
  that `Bound::Ord.satisfied_by` accepts `str` and a runtime `align_rt_str_cmp` backs "the four ordering
  operators and the `sort`/`sort_by_key` `str`-key comparator" — direct compiler-source confirmation at
  `crates/align_runtime/src/lib.rs:11526` (`align_rt_str_cmp`, "byte-lexicographic order … `Ord(str)`,
  2026-07-09") and `crates/align_codegen_llvm/src/lib.rs:18870-18898` (`gen_str_cmp`, "`str < str` /
  `<=` / `>` / `>=` (`Ord(str)`) via `align_rt_str_cmp`").
- Empirically confirmed against the pinned `alignc 0.5.0` in this session: `"apple" < "banana"` compiles
  and evaluates `true`; `"banana" < "apple"` evaluates `false`. `idx.sort_by_key(fn i { names[i] })` over
  an `array<str>` correctly sorts an index array by string key. `idx.sort_by_key(fn i {
  text[starts[i]..ends[i]] })` — a zero-copy sliced `str` key built from parallel `starts`/`ends`
  arrays, the exact span shape `src/expert_trace.align` uses — also sorts correctly, with no
  materialized intermediate strings.

**The genuine, narrower gap is plain `array<T>.sort()` over `str` elements, and the absence of a
general comparator overload.** Both are confirmed directly in the compiler source, not inferred:
`crates/align_sema/src/lib.rs:50601-50603`, the doc comment on `check_array_sort`: "`source.….sort()` —
materialize the surviving elements into an owned `array<T>` and sort them ascending. **First cut:
numeric scalar elements only** (an ordering exists), **no comparator argument (a `sort(cmp)` overload is
a follow-up)**." `crates/align_sema/src/lib.rs:50612-50618` enforces this: a struct element is rejected
with `'sort' over struct elements is not supported yet`, and any non-numeric element — including `str`,
even though `str` is `Ord` — is rejected with `'sort' needs a numeric element type, got {type}`.
Empirically confirmed: `["banana", "apple", "cherry"].sort()` fails at the pinned compiler with exactly
`error: 'sort' needs a numeric element type, got str`. `docs/guide/06-pipelines.md:83,87` documents the
same restriction in prose ("Both sorts are scalar-only for now"). So a caller who has a plain
`array<str>` (not an index array into a separately held key) and wants it sorted has no direct one-call
path: `sort()` rejects the element type outright, and `sort_by_key` needs something to key *by* — an
identity key function (`fn s { s }`) happens to work around this (untested here, but follows from the
same `str`-key path just confirmed), but there is still no `sort_by(comparator)` for a caller who needs
a multi-field or otherwise non-scalar-keyed order, which is exactly the shape the compiler's own comment
calls out as a deferred follow-up.

**Consequence for align-llm.** `src/expert_trace.align` needs an ordering over spans — byte ranges
`(start, end)` into one shared name-stream buffer, not standalone `str` values — to sort the
rendered name and op lists (`docs/specs/r2a-expert-trace.md` section 2.5.4).

The *comparison* is now the shipped one. `span_less` and `span_same` are one expression each,
`span_text(text, a, b) < span_text(text, c, d)`, and the earlier hand-written byte loop and its
"Align ships no string ordering at this pin" comment are both gone; that assumption is the one
corrected above.

The *sort* is not, and the reason is narrower and more interesting than "no string sort". Three
paths were compiled against the pinned toolchain in this module's own shape, and each is rejected:

```text
# 1. sort the names directly
src/…:  built.sort()
error: 'sort' needs a numeric element type, got str

# 2. materialize the spans as an array<str> first
src/…:  mut b: array_builder<str> := array_builder()
error: heap array_builder<str> requires a Copy scalar, `string`, or a closed heap record;
       use `array_builder(out)` for RegionPlain values

# 3. sort an index array by a sliced-`str` key — the shape that *should* work
src/expert_trace.align:1655: family_index.sort_by_key(fn i { span_text(names_view, family_start[i], family_end[i]) })
src/expert_trace.align:1655:28: error: a lambda cannot capture the owned value 'family_start' yet (capture supports copy values like int/float/bool/char)
src/expert_trace.align:1655:28: error: a lambda cannot capture the owned value 'family_end' yet (capture supports copy values like int/float/bool/char)
src/expert_trace.align:1657: op_index.sort_by_key(fn i { span_text(ops_view, t.op_start[i], t.op_end[i]) })
src/expert_trace.align:1657:51: error: field access is only supported on a local binding
src/expert_trace.align:1657:66: error: field access is only supported on a local binding
```

Path 3 is the correction to an earlier draft of this entry, which claimed the isolated experiment
`idx.sort_by_key(fn i { text[starts[i]..ends[i]] })` showed the hand-rolled merge sort to be
redundant. It does not. That experiment succeeds only because its `text`, `starts`, and `ends` are a
`str` literal and fixed-size array literals — Copy values a lambda may capture. The real call site's
columns are owned `array<i64>`s frozen from an `array_builder<i64>`, and one of them is a field of a
`borrow` parameter, and neither is capturable at this pin. So `sort_spans`
(a bottom-up merge sort over an index array, ordered by the shipped comparison) stays, and its
comment now records all three diagnostics so the next client does not repeat the experiment. `src/model_ir.align:261-301` (`name_hash`, `packed_entry`, `name_index`) packs a
64-bit FNV-1a hash, folded to 42 bits, above an index into one `i64`, so the resulting `array<i64>` is
both plain-`.sort()`-able and binary-searchable with only integer comparisons at every probe
(`indexed_tensor`, `src/model_ir.align:307` onward). That structure is not purely forced by missing
string ordering either — `sort_by_key(name)` would sort the same index by string — but Align ships no
general `sort_by`/`binary_search` over a non-scalar or string-keyed order, so a binary search over
string-keyed rows without the hash trick would need a hand-rolled comparator-driven search that Align's
pipeline surface does not provide; the packed integer key is what lets `name_index` reuse the shipped
`.sort()` and a plain integer binary search unmodified.

### Requested capability

Two additions, matching the shape the compiler's own `check_array_sort` comment already names as a
follow-up, and consistent with Align's existing pipeline/sort idioms (no new type, no new protocol):

1. **`array<T>.sort()` admits `str` (and, by the same non-consuming borrow `Eq`/`Ord` already use for
   owned operands, `string`) elements directly**, since `str` already satisfies the `Ord` bound this
   method requires for every other admitted element type. This removes the special-cased
   `elem.is_numeric()` check in `check_array_sort` (`crates/align_sema/src/lib.rs:50616`) for the one
   other type that already satisfies `Ord`.
2. **`array<T>.sort_by(cmp)` — a general comparator overload**, exactly the follow-up
   `crates/align_sema/src/lib.rs:50603` already names: `cmp: fn(T, T) -> bool` (or an `Ordering`-typed
   three-way form, Align's call) over a Copy element, admitting a struct or tuple-like composite key for
   a multi-field order without an artificial packed-scalar encoding. `check_array_sort`'s existing
   `'sort' takes no arguments yet` diagnostic (`crates/align_sema/src/lib.rs:50606`) is the exact
   deferred spot this would fill.

A `str.cmp(other: str) -> Ordering` (or `-> i64`) method is explicitly **not** the primary ask: the four
ordering operators already provide byte-lexicographic comparison, and `align_rt_str_cmp` already returns
a tri-state -1/0/1 internally, so surfacing it as a named method is a minor convenience at most — Align's
call whether to expose it alongside the two items above.

### Acceptance criteria

1. A compiler test sorts an `array<str>` directly with `.sort()` and asserts ascending byte-lexicographic
   order, with no key function required.
2. A compiler test sorts an index (or a struct array, once struct elements are otherwise admitted) using
   `sort_by` with a comparator over a non-scalar Copy key — the case `sort_by_key` cannot express — and
   asserts the result matches an independently computed expected order.
3. `align-llm` verification: `src/expert_trace.align`'s `sort_spans` and `src/model_ir.align`'s
   packed-hash `name_index` are replaced with the shipped surface (`sort()` on a
   sliced-`str` array, or `sort_by`/`sort_by_key` as appropriate), and `make expert-trace-smoke
   model-ir-smoke` pass unchanged. `span_less`/`span_same` already use the shipped `str` ordering
   and are unaffected.

---

## Request 28 — A readable append-only accumulator

```text
Status: PROPOSED
Priority: low
Blocking: no
Blocked gate or slice: none. `src/expert_trace.align` accumulates into a `buffer`, which is
  readable through `.bytes()` while still growing, and keeps its spans in pre-sized
  mutable `array<i64>` columns.
Independent work that may continue: all of R2A-EXPERT-TRACE-CAPTURE, and every existing
  `builder`/`array_builder` client, none of which needs to read back what it has
  accumulated.
Resume condition: Align ships read access to an unfinished accumulator — a `.len()` plus an
  indexed or byte-view read on `array_builder<T>` and/or `builder`, or a distinct
  append-and-read collection — with a stated aliasing rule for a read that a later `push`
  may reallocate behind.
Align commit or pull request: none
align-llm verification: pending — `src/expert_trace.align` interns node and operation names
  into the shipped accumulator instead of a `buffer` plus pre-sized `array<i64>` span
  columns, and `make expert-trace-smoke` passes unchanged.
```

### Motivation and current sibling evidence

`builder` and `array_builder<T>` are **write-only until `build()`/`to_string()`**. There is no
`.len()`, no index, and no byte view on either while it is still growing. Verified by compiling
against the exact toolchain align-llm materializes for the pinned commit
`4b515f8d37de2e9a9ba06170c5842fd12dc1cba2` (`alignc 0.5.0`); all four errors come from one probe
program:

```text
error: '.len()' is not defined on array_builder<i64>
error: cannot index array_builder<i64> (only array / slice / owned array)
error: '.len()' is not defined on builder
error: '.bytes()' is not a method on builder
```

The specification is consistent with the probe rather than contradicted by it:
`docs/language-spec.md:982-1006` describes `array_builder<T>` entirely in terms of `push`, `append`,
`build()`, and Drop — "a helper may push through a `borrow mut` parameter but cannot store, return,
or consume that borrowed builder" — and names no reader. `docs/guide/18-std-services.md:84` lists
the whole surface as "`array_builder<T>` with `push`, `append`, and consuming `build()` for a result
whose final length is discovered while reading." `builder` is documented the same way, as an
accumulate-then-`to_string()` value.

**Consequence for align-llm.** `src/expert_trace.align` interns every distinct node name and
operation name so a repeated name costs no bytes and a graph boundary can be recognized by identity.
An interning table is exactly an accumulator that must be *read back*: a candidate name is confirmed
against the bytes already accumulated by an exact comparison before the hash-selected slot is
trusted, because a hash collision must cost work and never merge two names. Neither builder can do
that, so the module accumulates node and operation text into a `buffer` — which *is* readable through
`.bytes()` while still growing — and keeps `name_start` / `name_end` / `op_start` / `op_end` in
pre-sized mutable `array<i64>`s rather than in `array_builder<i64>`s, purely because those columns
are indexed during the walk that fills them.

That works, is bounded, and is not a hardship. It is recorded because the shape — accumulate, look
back at what you accumulated, keep accumulating — is the ordinary shape of interning, deduplication,
run-length coding, and any incremental parser that must recognize a repeat, and every one of those
will hit the same wall. The `buffer` workaround also costs the pre-sizing: `NAME_STREAM_BYTES` and
`SLOT_COUNT` are fixed reservations where an accumulator would have grown.

### Requested capability

Read access to an accumulator that is still growing, in whichever of these shapes Align prefers:

```align
b.len() -> i64                       // elements accumulated so far
b[i]                                 // borrow of an already-pushed Copy element
builder.len() -> i64                 // bytes accumulated so far
builder.bytes() -> slice<u8>         // borrowed view of the accumulated prefix
```

The aliasing rule is the substance of the request, not an afterthought: a view taken from an
unfinished accumulator must either be invalidated by the next `push`/`write` — the same borrow rule
`borrow mut` already enforces elsewhere — or the accumulator must document that it never reallocates
behind a live view. `align-llm` needs only the read; the rule is Align's to choose, and stating it is
what makes the surface safe rather than a foot-gun.

This request does **not** ask for removal, mutation of an already-pushed element, iteration, or a
second collection type. It is the minimum that turns a write-only accumulator into one an interning
table can use.

### Acceptance criteria

1. A compiler test pushes into an `array_builder<T>`, reads back an already-pushed element and the
   current length before `build()`, and asserts both; `build()` afterwards still yields the complete
   array.
2. A compiler test accumulates into a `builder`, reads the accumulated byte prefix before
   `to_string()`, and asserts it; `to_string()` afterwards still yields the complete text.
3. A compiler test pins the chosen aliasing rule — either a rejected use of a view across a
   subsequent `push`/`write`, or a passing test demonstrating the documented no-reallocation
   guarantee — so the decision is reviewed rather than incidental.
4. Every existing `builder`/`array_builder` program, its Drop behavior, and its generated-program
   identity are unchanged.
5. `align-llm` verification: `src/expert_trace.align` replaces its `buffer`-plus-pre-sized-column
   interning tables with the shipped accumulator, and `make check` and `make expert-trace-smoke`
   pass unchanged.

---

## Request 29 — Incremental digest (`sha256` init/update/final)

```text
Status: PROPOSED
Priority: medium
Blocking: no
Blocked gate or slice: none. R4-ALIGNPACK-LAYER-MAJOR (`docs/specs/r4-alignpack-layer-major.md`
  section 2.4.6) ships the bounded header-region digest and reserves the whole-payload
  `payload_sha256` field as explicitly zero-valued in v1.
Independent work that may continue: all of R4-ALIGNPACK-LAYER-MAJOR.
Resume condition: an Align release ships an incremental digest handle; align-llm then fills
  `payload_sha256` in `--pack` and checks it in `--pack-verify`.
Align commit or pull request: none
align-llm verification: pending — `alignpack-qualification` computes the reserved
  `payload_sha256` in `--pack`, checks it in `--pack-verify`, and `make alignpack-smoke` passes
  unchanged.
```

### Motivation and current sibling evidence

R4-ALIGNPACK-LAYER-MAJOR rewrites one GGUF file into one alignpack v1 container and must certify the
result without re-reading the multi-gigabyte source. A whole-payload digest computed once while
streaming the copy would let `--pack-verify` (and any later consumer) check the pack's payload
against a recorded value with no second full read of either file, but `crypto.sha256`/`sha512` are
one-shot over exactly **one** byte view.

Verified in the sibling checkout at the pinned commit `4b515f8d37de2e9a9ba06170c5842fd12dc1cba2`:

- `crates/align_sema/src/lib.rs:54374` (`fn check_crypto_hash`) takes exactly one argument, checked
  through the same `check_byte_view` used by `std.compress`, and returns one owned 32- or 64-byte
  `array<u8>` in a single call. There is no `sha256_init`, `update`, `finish`, digest handle, or
  streaming `Hasher` anywhere in the crate.
- `hash64`/`hash128` (wyhash) are incremental in neither sense and are explicitly "not stable across
  builds" (`../align/docs/impl/core-design/hash.md`), so they cannot bind a persisted artifact's
  identity across a compiler upgrade.

**Consequence for the client.** align-llm cannot digest a file larger than memory in one call, and
has no way to fold a digest across the many `pwrite`d chunks of a streaming copy without holding the
whole payload in one byte view — which is exactly the multi-gigabyte residency R4 is designed to
avoid. R4 settled for the bounded header-region digest of section 2.4.6 (5,953,536 bytes on the
reference model, about 2.6 ms at the measured 2.26 GB/s) and reserved the payload digest field.

**R6-KV-PERSIST is the second client, and the bound it forces is recorded rather than hidden**
(`docs/specs/r6-kv-persist.md` sections 2.4 and 2.5). Two consequences follow from the one-shot
digest. First, `MAX_KV_PLANE_BYTES := 536870912` exists: a plane this capability cannot digest is a
plane it **refuses to persist**, because a persisted artifact whose identity cannot be computed is
not an identity and the one thing the digest exists to catch — a torn write — would go undetected.
alignpack's own `MAX_HEADER_REGION_BYTES` of 128 MiB could not simply be inherited, because a plane
at `MAX_ATTENTION_WIDTH` on the reference model is 448 MiB. Second, the container's model identity
is the **pack's** header-region digest rather than the GGUF's, because a 4.68 GB digest would need a
4.68 GB byte view; the limitation that follows — a pack whose weight bytes were corrupted after
packing has the same header-region digest — is stated in that document's section 2.4 rather than
papered over. **No status change.**

### Requested capability

An Align-consistent Move-handle streaming digest, following the existing owned-handle/`Drop` idiom
already used by `file`/`reader`/`writer`:

```text
crypto.sha256_stream() -> digest          // a Move handle, Drop-released
d.update(data: str | string | slice<u8>)  // borrows the view, never consumes
d.finish() -> array<u8>                   // consumes the handle, yields 32 bytes
```

### Acceptance criteria

1. `finish()` over `n` `update` calls equals `crypto.sha256` over the concatenation, for `n` in
   `{0, 1, 2, 1000}` and for chunk boundaries at every offset of a multi-megabyte input.
2. The handle is Move, closes on `Drop`, and cannot be used after `finish()`; an `update` after
   `finish()` is a compile error.
3. The digest of the empty input (zero `update` calls) equals the known SHA-256 of the empty string.
4. `align-llm` verification: `alignpack-qualification` fills `payload_sha256` while streaming the
   copy in `--pack`, re-derives and checks it in `--pack-verify`, and asserts it against an
   independent Python `hashlib.sha256` digest of the same payload bytes.

---

## Request 30 — `fs.create_rw_exclusive`

```text
Status: PROPOSED
Priority: medium
Blocking: no
Blocked gate or slice: none. R4-ALIGNPACK-LAYER-MAJOR ships the documented check-then-create race
  (`R4_DEST_EXISTS`: `fs.exists` then `fs.create_rw`) as its destination guard.
Independent work that may continue: all of R4-ALIGNPACK-LAYER-MAJOR.
Resume condition: an Align release ships an exclusive random-access constructor; align-llm then
  replaces the exists-then-create sequence in `src/alignpack.align` with it.
Align commit or pull request: none
align-llm verification: pending — `alignpack-smoke`'s `dest-exists` case asserts the exclusive
  failure directly, with no `fs.exists` preflight, and no window in which a competing creator can
  win between check and create.
```

### Motivation and current sibling evidence

R4-ALIGNPACK-LAYER-MAJOR writes a multi-gigabyte artifact and must refuse to overwrite an occupied
destination path while still writing at planned offsets (the layout planner places each block at a
computed absolute offset, not appended sequentially).

Verified in the sibling checkout at the pinned commit `4b515f8d37de2e9a9ba06170c5842fd12dc1cba2`:

- `crates/align_runtime/src/lib.rs:9890` (`align_rt_io_file_create`, backing `fs.create_rw`) opens
  `O_RDWR|O_CREAT|O_TRUNC`, mode `0644` — its own doc comment calls it "the fresh-alignpack output
  path" — so it silently destroys an occupied destination; there is no flag or sibling constructor
  that both refuses an existing path and returns a positional-write handle.
- `crates/align_sema/src/lib.rs:53164` (`fn check_fs_create_exclusive`) backs `fs.create_exclusive`,
  which "never truncates, replaces, or removes an existing final entry" but returns
  `Ty::Result(Scalar::Writer, ...)` — a sequential `writer`.
- `crates/align_sema/src/lib.rs:55795` (`fn check_writer_method`) is the complete method set on that
  `writer`: `write` and `flush` only. There is no positional `pwrite` on a `writer`, so a planned
  layout with per-block absolute offsets cannot be realized through it — the two properties (refuse
  an occupied destination; write at a planned offset) exist on two different, incompatible handle
  types.

**Consequence for the client.** align-llm's `R4_DEST_EXISTS` guard (`docs/specs/r4-alignpack-layer-major.md`
section 2.8 step 5) is a check-then-create race: `fs.exists(path)` then `fs.create_rw(path)`, with a
window in which another process could create the path, which is then truncated by `fs.create_rw`.
The artifact at risk is multiple gigabytes.

**R6-KV-PERSIST is the second client** (`docs/specs/r6-kv-persist.md` section 2.6). Its
`R6_KV_EXISTS` guard is the same check-then-create shape for the same reason, verified again at this
pin: `fs.create_rw` is `O_RDWR|O_CREAT|O_TRUNC` and `fs.create_exclusive` returns a sequential
`writer` with no `pwrite`, so a container that must be written at declared offsets has no exclusive
positional constructor to use. The race is documented rather than defended — hiding it behind a
silent overwrite would be worse — and **no workaround is built**. A destination that is a symlink is
followed in both directions, exactly as alignpack's `dest-symlink` case pins. **No status change.**

### Requested capability

Mirroring the shipped `fs.create_rw` / `fs.create_exclusive` pair:

```text
fs.create_rw_exclusive(path: str) -> Result<file, Error>
```

`O_RDWR|O_CREAT|O_EXCL|O_CLOEXEC|O_NOFOLLOW`, mode `0644`, failing deterministically when the path
exists, never truncating, never following a destination symlink, returning the same owned `file`
handle with the same `Drop` contract as `fs.create_rw`.

### Acceptance criteria

1. Creation at an absent target succeeds and yields a working `pwrite`; an existing regular file,
   directory, symlink, or FIFO at the target fails deterministically with the target unmodified; a
   competing creator between preflight and create loses deterministically.
2. The fd is `O_CLOEXEC` and closes on every `?`, `map_err`, branch join, early return, and `Drop`;
   repeated create/free cycles leak no descriptors.
3. `align-llm` verification: `src/alignpack.align` replaces its `fs.exists` + `fs.create_rw` sequence
   with one `fs.create_rw_exclusive` call, and `alignpack-smoke`'s `dest-exists` case passes against
   the new, race-free failure path.

---

## Request 31 — File durability (`fsync`/`fdatasync`)

```text
Status: PROPOSED
Priority: low
Blocking: no
Blocked gate or slice: none. R4-ALIGNPACK-LAYER-MAJOR makes no durability claim (section 1.3 states
  it as a non-goal: a pack is a reproducible derivative of a file that still exists, so the recovery
  from a torn pack is to run `--pack` again, and `--pack-verify` detects a torn pack anyway).
Independent work that may continue: all work.
Resume condition: an Align release ships a sync operation with a stated per-platform guarantee.
Align commit or pull request: none
align-llm verification: R6-KV-PERSIST's `--decode-step KV_SAVE` would call `f.sync()` before
  reporting `kv.destination: "WRITTEN"`, and `gmake layer-forward-smoke` would pass unchanged in
  outcome.
```

### Motivation and current sibling evidence

Verified in the sibling checkout at the pinned commit `4b515f8d37de2e9a9ba06170c5842fd12dc1cba2`:

- `grep -rn "fsync|fdatasync|F_FULLFSYNC" crates/align_runtime/src/lib.rs crates/align_sema/src/lib.rs`
  returns zero hits — the ABI exposes no sync primitive on `file` or `writer` at all.
- `docs/impl/std-design/fs.md:75` states the omission as a deliberate design decision, listing "…
  preflight existence check, cross-device copy, `fsync`, or crash-durability" among what the
  publish/rename operation does not add. `draft.md:2892` likewise lists "rollback, durability, or
  multi-file transaction" among what the constructors add none of.
- A `writer`'s `flush` (`crates/align_sema/src/lib.rs:55795`) pushes buffered bytes to the kernel,
  not to the device; `file` has no flush or sync method of any kind.

**Consequence for the client.** align-llm cannot promise that any artifact — including a multi-
gigabyte alignpack — survives a power loss. For R4 this is genuinely harmless: a pack is a
deterministic derivative of a file (the source GGUF) that still exists, so a torn pack costs a rerun
of `--pack`, and `--pack-verify` detects a torn or truncated pack rather than trusting it. It is
recorded because the next client is a persistent KV cache (roadmap item 29,
`docs/specs/r6-kv-persist.md`).

**That client has now been designed and shipped, and it corrects this paragraph's own prediction.**
The earlier text said the R6 artifact "is not a derivative of anything else and losing it loses the
only copy". It **is** a deterministic derivative — of the pack, the geometry document, the token
ids, and `KV_WIDTH` — so a torn `akvp` container costs exactly one re-prefill, and
`R6_KV_TRUNCATED` or `R6_KV_DIGEST("plane")` detects it rather than loading it
(`docs/specs/r6-kv-persist.md` section 6, risk 6). This request therefore **stays `low` and
non-blocking**; the first client that would raise it is one whose artifact is not reproducible from
inputs that still exist. Correcting the register upward would have been easy and wrong.

### Requested capability

```text
f.sync() -> Result<(), Error>   // on `file`, a real fsync/F_FULLFSYNC
w.sync() -> Result<(), Error>   // on `writer`, the same
```

### Acceptance criteria

Acceptance criteria must state exactly what is and is not promised on each supported filesystem,
because a durability API that over-promises is worse than none: a compiler test asserts that after
`sync()` returns `Ok`, a subsequent read (in-process or via a fresh open) observes the written bytes,
and the platform-specific guarantee (e.g. `F_FULLFSYNC` on APFS vs. plain `fsync` elsewhere) is
documented in `draft.md`/`docs/language-spec.md` rather than left implicit.

---

## Request 32 — FFI v1 by-value struct ABI (AAPCS64 and SysV MEMORY class) and `bool` FFI type

```text
Status: PROPOSED
Priority: medium
Blocking: no
Blocked gate or slice: none. R4.5-EXTERNAL-BUFFER-SPIKE (`docs/specs/r4-5-external-buffer.md`
  section 3.1) ships `scripts/ggml_shim.c`, a C shim, as the application-side answer.
Independent work that may continue: all of R4.5-EXTERNAL-BUFFER-SPIKE and R5.
Resume condition: an Align release admits a `raw` field in a `layout(C)` struct, admits by-value
  `layout(C)` struct passing on a second ABI (AArch64 AAPCS64, or the SysV MEMORY class), or admits
  a `bool`-equivalent FFI scalar.
Align commit or pull request: none
align-llm verification: call `ggml_init` directly from `src/ggml_ffi.align` and delete the shim's
  by-value context-open wrapper; pass `make ggml-spike-smoke` plus `make ggml-spike-qualification`.
```

### Motivation and current sibling evidence

R4.5-EXTERNAL-BUFFER-SPIKE calls ggml — a mature, unmodified C library — from Align to compute a real
quantized matmul over an Align-owned buffer. `ggml_init(struct ggml_init_params)`, ggml's sole entry
point, takes a 24-byte struct **by value**, and `ggml_tallocr_new` returns a struct by value; both are
unreachable from Align at the pinned commit `4b515f8d37de2e9a9ba06170c5842fd12dc1cba2` by any route,
forcing the C shim `scripts/ggml_shim.c`.

Verified in the sibling checkout at that pin:

- `docs/language-spec.md:873` states FFI v1's own deferral list: "MEMORY-class or larger-than-16-byte
  structs by value, and all by-value struct ABIs other than x86-64 SysV (struct-by-pointer covers the
  portable case); `bool`/`char` as FFI types". `docs/guide/15-unsafe-and-ffi.md:84` repeats the
  by-value restriction: "`layout(C)` structs cross by pointer (through `raw`) or **by value** (SysV
  x86-64 ABI, ≤16-byte register-class structs …; larger-by-value is implementation in progress)".
- `crates/align_codegen_llvm/src/lib.rs:2208` is the exact codegen diagnostic fired on this target for
  both a 16-byte and a 24-byte `layout(C)` struct passed by value: "extern '{}' passes or returns a
  struct by value, which is only supported on x86-64 SysV (Linux) — the target is '{}'; pass the
  struct by pointer (`raw`) instead". The spike's target is `arm64-apple-darwin25.5.0` (AAPCS64), not
  SysV, so both sizes are rejected regardless of the 16-byte register-class boundary.
- The diagnostic's own advice does not apply to `ggml_init_params`: `crates/align_sema/src/lib.rs:6627`
  ("struct field type is not supported here, got raw") and `:6636` ("a `layout(C)` struct field must
  be an integer or float (got raw) — other field types are a later FFI slice") reject a `layout(C)`
  struct with a `raw` (pointer) field outright, and
  `struct ggml_init_params { size_t mem_size; void *mem_buffer; bool no_alloc; }` has one. There is no
  by-pointer fallback for any struct with a pointer member.
- `crates/align_sema/src/lib.rs:7502` ("'{}' is not an FFI-safe return type for an extern (use an
  integer, float, `raw`, a `layout(C)` struct, or `()`)") and its parameter-position twin at `:7474`
  reject `bool` as an FFI type in either direction, removing `ggml_backend_dev_supports_op` and every
  other ggml predicate from direct reach.

**Additional client evidence, from the R5A-DENSE-LAYER-FORWARD capability, now shipped.**
`ggml_gallocr_reserve` and `ggml_gallocr_alloc_graph` are two more `bool`-returning ggml entry points
R5A's design had to reach — the graph allocator's own reserve/alloc pair — and both are now wrapped
by a shim function that translates the `bool` to `int32_t`: `src/ggml_ffi.align:741-754`
(`gallocr_reserve`, `gallocr_alloc`) calls `align_ggml_gallocr_reserve`/`align_ggml_gallocr_alloc`,
implemented at `scripts/ggml_shim.c:1069-1090`, each returning `int32_t` from a `bool` ggml call.
Section 2.6 of the design plan also records the **positive** half of this request's surface, which is
worth adding to the register alongside the negative one: `f32` crosses the FFI by value in both
directions, verified with a nine-argument probe mixing `f32`/`f64`/`i32` parameters and an `f32`
return value, and an unsuffixed float literal in an `f32` parameter position coerces with no cast
required at the call site —

```text
$ alignc run f32probe.align
1                 # C saw 1000000.0, 1.0, 0.0, 1.0, 32.0, 1.0 exactly, alongside three i32
3.75              # probe_f64(1.5, 2.25f) — mixed f64/f32 arguments
7.0               # probe_ret_f32(3.5f) — an f32 return value
```

R5A's shipped implementation nonetheless passes no float across the boundary for an unrelated reason
(bit-pattern fidelity to the GGUF source), so this is a measured boundary of the gap, not a
workaround for it. It is non-blocking — both new entry points are wrapped and shipped — with all of
R5A-DENSE-LAYER-FORWARD as independent work.

**Consequence for the client.** `ggml_init` is unreachable from Align at this pin by any route
(by-value rejected; by-pointer impossible because `layout(C)` cannot hold a `raw` field), and every
`bool` predicate needs an integer-translating shim function. `align-llm` therefore ships
`scripts/ggml_shim.c` — one C translation unit that no ggml type ever crosses out of — as the only way
to call ggml from Align at this pin (`docs/specs/r4-5-external-buffer.md` section 3.1).

### Requested capability

Align-consistent, extending mechanisms the language already has:

1. Admit `raw` as a `layout(C)` struct field, so a struct mixing an integer/float with a pointer
   member can at least be declared and assembled with `raw.store`.
2. Admit `layout(C)` struct-by-value passage on a second ABI — AArch64 AAPCS64, and the SysV MEMORY
   class for a struct larger than two eightbytes — under the same "reject rather than silently pass in
   memory" discipline the existing SysV register-class path already uses.
3. Admit a `bool`-equivalent FFI scalar: a distinct `c_bool` type, or a defined lowering of Align's
   `bool` to `u8` with `0`/non-zero semantics, in both parameter and return position.

### Acceptance criteria

1. A `layout(C)` struct with a `raw` field compiles and can be constructed field-by-field.
2. That struct crosses an `extern "C"` boundary by value on `arm64-apple-darwin`, verified by
   compiling and running `probe_byval.align` (or its successor) against a real C library that receives
   it and reads every field back correctly.
3. A `bool`-typed extern parameter and return value compile and round-trip correctly against a real C
   predicate function, verified by compiling and running `probe_bool.align` (or its successor).
4. `align-llm` verification: `ggml_init` is declared and called directly from `src/ggml_ffi.align`;
   the shim's by-value context-open wrapper is deleted; `make ggml-spike-smoke` and
   `make ggml-spike-qualification` both pass unchanged in outcome.

---

## Request 33 — Aligned heap allocation (`buffer` / `raw.alloc` with explicit alignment)

```text
Status: PROPOSED
Priority: medium
Blocking: no
Blocked gate or slice: none. R4.5-EXTERNAL-BUFFER-SPIKE (`docs/specs/r4-5-external-buffer.md`
  section 3.8 step 14, with corrections C9 and C14) **compensates** for the allocator's base rather
  than depending on it: both device-visible windows are over-reserved by `MAX_TENSOR_ALIGNMENT = 64`
  and the ranges handed to ggml start at an aligned interior offset of each.
Independent work that may continue: all of R4.5-EXTERNAL-BUFFER-SPIKE; R5's DRAM and VRAM tiers.
Resume condition: an Align release adds an alignment parameter to `raw.alloc` and/or `buffer`, or
  admits an `align(N)` prefix on a `buffer` binding.
Align commit or pull request: none
align-llm verification: allocate the block and output buffers with the new aligned surface, delete
  the pad-and-copy compensation from `src/ggml_spike.align` (its `weights_pad`, `output_pad`, and
  `alignpack_read.read_append`), and pass `make ggml-spike-qualification`.
```

R6-OLMOE-DECODE adds `src/moe_decode_step.align` and `gmake moe-decode-step-qualification` as
clients. It is the first arm that pays the 64-byte over-reservation **three** times in one
invocation — the dense window, the claim window, and the KV plane — where R5E pays it twice, so the
compensation's cost is now proportional to the number of Align-owned regions an arm holds rather than
to the number of arms. **No status change**, `Blocking: no`.

### Motivation and current sibling evidence

R4.5-EXTERNAL-BUFFER-SPIKE hands ggml's CPU backend a pointer into an Align-owned `buffer` so it can
compute a real Q4_K matmul without copying the weights. `ggml_backend_cpu_buffer_from_ptr` (and the
device-generic path the design actually uses) asserts — `abort()`, not an error return — unless that
pointer is 32-byte aligned (`TENSOR_ALIGNMENT`).

Verified in the sibling checkout at the pinned commit `4b515f8d37de2e9a9ba06170c5842fd12dc1cba2`:

- `crates/align_runtime/src/lib.rs:10090` (`align_rt_buffer_new`, backing `buffer(cap)`) allocates
  through a plain `Vec<u8>` and `try_reserve_exact` — Rust's global (C `malloc`-family) allocator at
  its ordinary byte alignment, not any alignment Align requests or guarantees. There is no alignment
  parameter on this function or on `raw.alloc` anywhere in the crate.
- align-llm's own measurement (`docs/specs/r4-5-external-buffer.md` section 2.4, `probe_align2.align`
  against the pinned compiler) found every observed allocation 32-byte aligned and every allocation at
  or above the page size page-aligned — both properties of this platform's `malloc`, not of Align:
  `buffer(4096)` measured `addr % 16384 == 10496` (not page-aligned) while `buffer(14336)` and larger
  measured `addr % 16384 == 0` by allocator luck alone.
- The shipped implementation's own measurement is stronger than the design-time probe, and is not a
  one-off: correction C9 (`docs/specs/r4-5-external-buffer.md` section 6.1) found the **same 192-byte
  `buffer`**, on the same host, for the same input, come back **32-byte aligned on one run and
  16-byte aligned on the next**. Correction C14 measured the same instability on the block window —
  the arm's own `buffer.weights_pad` varies run to run within `[1, 64]` across runs of one fixture —
  and measured its consequence: a rule that consults the allocator's base rejects a legitimate
  member at interior offset **0** on 20 of 20 runs on this host, and would have accepted it on a
  host whose allocator answered differently. Nondeterministically, not merely occasionally.

- **The shipped arm therefore compensates rather than refusing, and that compensation is this
  request's cost.** Both device-visible windows are over-reserved by `MAX_TENSOR_ALIGNMENT = 64`
  bytes; the output tensor is placed at `buffer.output_pad` inside its window, and the block is
  **read in behind** `buffer.weights_pad` so block byte 0 itself lands on a boundary
  (`alignpack_read.read_append` exists for that and nothing else). The price is 64 bytes of
  over-reservation per device-visible window plus one copy of the block into the compensated window
  — on the real model, 64 bytes on top of a 17,020,928-byte block and one 17 MB copy inside
  `timings.pread_ns` — carried by every consumer that hands memory to a device, in exchange for a
  verdict that no longer depends on the allocator. `R4_5_ALIGNMENT` survives for the one case no
  padding can fix: a **container-chosen** interior offset whose own alignment does not divide
  `tensor_alignment`, which is exactly what `spike-misaligned-member` (section 6.2, `4.5`) exercises
  and is the same verdict on every host. Both the weights-base and output-base misaligned rows are
  consequently `N/A`, not reachable from any input, because the base is the Align allocator's
  accident to compensate for, not the container's to be blamed for.

**Additional client evidence, from the R5A-DENSE-LAYER-FORWARD capability, now shipped.** R5A packs
thirteen weight members into one Align-owned window instead of R4.5's separate weight and output
windows, so the same compensation this request asks the language to make unnecessary is now paid
once per member rather than once per window. `src/layer_forward.align:2436` allocates
`buffer(layout.weight_bytes + MAX_TENSOR_ALIGNMENT)` — one over-reservation for the whole window —
and `:2438-2439` pads it to a `MAX_TENSOR_ALIGNMENT`-aligned interior offset the same way R4.5 does.
That single pad only guarantees the window's first byte is aligned; each of the thirteen members'
own interior placement inside that window still has to be checked individually, because a
`block_align`-packed offset (typically 32 bytes) does not necessarily divide `tensor_alignment` (up
to 64 bytes): `src/layer_forward.align:1858` computes `layout.window_offsets[at] % alignment` for
every member in a loop over all thirteen, and `:1864` tests it against zero to name the first
misaligned one as `R5_ALIGNMENT`. Thirteen separate alignment checks and a per-member `R5_ALIGNMENT`
failure surface exist only because Align's allocator makes no placement guarantee stronger than the
window's own base — the same gap this request asks to close, now paid thirteen times per run instead
of R4.5's two.

**Consequence for the client.** `ggml_backend_cpu_buffer_from_ptr` aborts the process
(`GGML_ASSERT((uintptr_t)ptr % TENSOR_ALIGNMENT == 0 && "buffer pointer must be aligned")`) on a
misaligned pointer, with no unwinding and no document. Because Align makes no alignment promise,
R4.5-EXTERNAL-BUFFER-SPIKE cannot rely on it: it pads to whatever base it is given, re-measures the
exact range it is about to hand across the boundary, and refuses only what padding cannot fix
(`docs/specs/r4-5-external-buffer.md` section 3.8 step 14, corrections C9 and C14). No legitimate
input is rejected for the allocator's reasons any more — but every such client now carries the
over-reservation, the interior offset, and the copy, in a language that could simply hand it an
aligned allocation.

### Requested capability

Extending the existing allocator surface, consistent with the promise `align(N)` already makes for
struct storage:

```text
raw.alloc(size: i64, align: i64) -> raw        // fails rather than silently under-aligning
buffer(cap: i64, align: i64) -> buffer         // same failure discipline
```

or, equivalently, an `align(N)` prefix admitted on a `buffer` binding.

### Acceptance criteria

1. A `buffer` (or `raw.alloc`) of run-time size requested with an explicit alignment (e.g. 16384, for
   the Metal path where page alignment is the practical requirement) returns a pointer satisfying that
   alignment on every call, verified by an address probe over a range of sizes including sub-page and
   multi-page requests.
2. A request the allocator cannot satisfy fails deterministically (`Result`/`Err`) rather than
   returning an under-aligned pointer.
3. `align-llm` verification: the block-read buffer in `src/ggml_spike.align` is allocated with the
   aligned surface instead of relying on platform-allocator luck, `buffer.base_alignment` in the
   `R4_5_EXTERNAL_BUFFER` document is `0 mod 32` on every run by construction rather than by
   observation, and `make ggml-spike-qualification` passes.

---

## Request 34 — `Result` ok payloads beyond scalars (`raw`, `buffer`, records)

```text
Status: PROPOSED
Priority: medium
Blocking: no
Blocked gate or slice: none. `src/ggml_ffi.align`'s constructors return a bare `raw` and report
  failure as a null handle (section 6, correction C3), and `src/ggml_spike.align`'s reference reader
  threads its bytes out through a `borrow mut buffer` parameter instead of an owned return.
Independent work that may continue: all of R4.5-EXTERNAL-BUFFER-SPIKE and R5.
Resume condition: an Align release admits `raw` and/or `buffer` directly as a `Result` ok payload,
  or admits `raw` as an ordinary (non-`layout(C)`) struct field so a fallible constructor can be
  wrapped in a small owning record instead.
Align commit or pull request: none
align-llm verification: return `Result<raw, Fault>` from the ggml constructors in
  `src/ggml_ffi.align` and delete the `.is_null()` sentinel checks in `src/ggml_spike.align`; pass
  `make ggml-spike-smoke` plus `make ggml-spike-qualification` unchanged in outcome.
```

### Motivation and current sibling evidence

R4.5-EXTERNAL-BUFFER-SPIKE's ggml constructors (`device_open`, `backend_open`, `context_open`,
`buffer_from_host`, `new_tensor_2d`, `alloc_remaining`, `mul_mat` — `src/ggml_ffi.align:207-313`)
each return a bare `raw` and signal failure only as a null handle, because a `Result` ok payload
must be a scalar at this pin and neither `raw` nor `buffer` qualifies. `src/ggml_ffi.align:202-206`
states the consequence in-repo: "Every constructor below returns a bare `raw` and reports failure as
a null handle rather than as `Result<raw, Fault>`: at this pin a `Result` ok payload must be a scalar
and `raw` is refused ... `src/ggml_spike.align` tests each handle with `.is_null()` at the one place
that knows which object it asked for."

Verified directly against the pinned compiler (`4b515f8d37de2e9a9ba06170c5842fd12dc1cba2`,
`alignc 0.5.0`, `target/release/alignc`) with three probes:

- `fn make_raw() -> Result<raw, i32> { return Ok(raw.null()) }` reports `error: Result ok payload
  must be a scalar (composite payloads are not supported yet), got raw` — the generic diagnostic
  `payload_scalar` emits (`crates/align_sema/src/lib.rs:44855`, reached from `check_result_ctor`'s
  `Ok`/`Err` check at `:56586`) and the identical text `scalar_arg` emits when resolving the
  `Result<raw, i32>` type annotation itself (`crates/align_sema/src/lib.rs:60836`, reached from the
  Result-type resolver's ok-payload call at `:61809`).
- `fn make_buf() -> Result<buffer, i32> { return Ok(buffer(16)) }` reports the `buffer`-specific
  error `Result ok payload cannot be \`buffer\` — an owned I/O handle/buffer is bound to one local,
  not collected into an array/slice/box (bind it to a local)` — the unconditional `Ty::Buffer`
  exclusion inside `scalar_arg` (`crates/align_sema/src/lib.rs:60819`), hit through the same
  Result-type resolver. (`ty_to_scalar` at `:909` does map `Ty::Buffer => Some(Scalar::Buffer)` for
  the narrower `encoding.*_decode`-style builtin path, but a client-declared `Result<buffer, E>`
  return-type annotation does not reach that path — it is rejected at `scalar_arg`.)
- A record cannot serve as an escape hatch for the `raw` case: `Handle { ptr: raw, size: i64 }`,
  declared as an ordinary (non-`layout(C)`) struct and used as a plain local (no `Result` involved),
  is rejected with `error: struct field type is not supported here, got raw`
  (`is_field_ok`/`crates/align_sema/src/lib.rs:6624,6627`) — the same universal per-field check
  Request 32 already cites for `layout(C)` structs, confirmed here to apply to every struct
  regardless of `layout(C)`. A record holding a `buffer` field instead compiles cleanly (`buffer` is
  an admitted Move-handle field via `is_move_handle`), so the gap is specific to `raw` and to `buffer`
  as a **direct** Result payload, not to records in general.

**Consequence for the client.** A fallible ggml constructor cannot return a handle *and* a reason —
it returns a null sentinel and lets the caller invent the reason from context
(`src/ggml_ffi.align:207-283`; `src/ggml_spike.align`'s call sites test `ggml_ffi.handle_absent` at
the one place that knows which object was requested). A reader that must return owned bytes cannot
return them as a `Result` payload either: `src/ggml_spike.align:401-419`'s `read_reference` returns
`Result<i64, alignpack_read.Fault>` (elapsed nanoseconds) and threads the actual bytes out through a
`borrow mut out: buffer` parameter (line 405) instead of an owned `Result<buffer, Fault>` return.

**Additional client evidence, from the R5A-DENSE-LAYER-FORWARD capability, now shipped.**
R5A (`docs/specs/r5a-dense-layer-forward.md` section 2.6) is this request's first
**architecturally load-bearing** client: not a constructor that would merely prefer to return a
handle and a reason, but a design that needed `raw` to live inside an aggregate and found the pin
refuses both aggregate shapes. A thirty-two-node Qwen2 layer graph needs its `ggml_tensor *`
handles held somewhere the topology loop can index, and the probe found `raw` rejected as a struct
field (as Request 34 already records) **and, newly, as an array element**:

```text
rawagg.align:7:10:  error: struct field type is not supported here, got raw
rawagg.align:11:13: error: array element must be a scalar (composite payloads are not supported
                     yet), got raw
```

That second refusal is why R5A does not hold the graph as an Align array of handles: it holds a
node-slot store instead, a `buffer`-backed byte window that the shim writes `ggml_tensor *` values
into by `i64` index. The shipped topology module names the slots and their bounds at
`src/layer_qwen2.align:13-16` ("this module never sees one [handle]" — every reference is an `i64`
slot index) and `:24-38` (`MAX_NODE_SLOTS`, `SLOT_HEADER_BYTES`, `SLOT_BYTES`, `NODE_COUNT`,
`MEMBER_COUNT`, `ORACLE_COUNT`, `SLOT_TOKENS`, `SLOT_POS`, `SLOT_MASK`, `SLOT_NODE_BASE`); the arm
addresses it exclusively through `i64` indices (for example `layer_qwen2.SLOT_NODE_BASE + oracle.node[row]`
at `src/layer_forward.align:1368`), and no `raw` value appears in any record field or array anywhere
in `src/` (asserted by the owner test, `docs/specs/r5a-dense-layer-forward.md` section 6's closing
paragraph). The register entry should gain the array-element refusal text above and an acceptance
criterion that `array<raw>` compiles; the align-llm verification is then to delete the slot store and
hold the graph's handles directly. It is non-blocking — R5A ships the slot store on the pinned
surface — with all of R5A-DENSE-LAYER-FORWARD as independent work.

### Requested capability

Extending the existing `Result`/`Option` payload surface, consistent with the partial support
`ty_to_scalar` already carries for `Ty::Buffer`:

1. Admit `raw` and `buffer` as `Result` (and `Option`) ok payloads on the same footing as the other
   owned handles `ty_to_scalar` already admits (`reader`, `writer`, `file`, `tcp_conn`, …), reached
   consistently through both the `Ok`/`Err` constructor check and the `Result<T, E>` type-annotation
   resolver.
2. Admit `raw` as an ordinary struct field (`is_field_ok`), so a fallible constructor that needs to
   report more than a null/non-null handle can wrap the pointer in a small owning record.

### Acceptance criteria

1. `fn f() -> Result<raw, Fault>` compiles, and `Ok`/`Err`/`match` round-trip a real `raw` value
   through it.
2. `fn g() -> Result<buffer, Fault>` compiles, and `Ok`/`Err`/`match` round-trip a real `buffer`
   value through it (matching the already-partial `ty_to_scalar` support).
3. A struct with a `raw` field compiles, both as a plain local and as a `Result` ok payload.
4. `align-llm` verification: `src/ggml_ffi.align`'s constructors return `Result<raw, Fault>`; the
   `.is_null()` sentinel checks in `src/ggml_spike.align` are deleted; `make ggml-spike-smoke` and
   `make ggml-spike-qualification` both pass unchanged in outcome.

---

## Request 35 — Observable `buffer` capacity and allocation failure

```text
Status: PROPOSED
Priority: high
Blocking: no
Blocked gate or slice: none. `R4_WINDOW_UNAVAILABLE` (R0) and R4.5's window/allocation-failure code
  are retained as fail-closed guards that are not input-reachable (section 6, correction C8), and
  `scripts/run-alignpack-smoke` documents its own `window-unavailable` case as `N/A` for the same
  reason.
Independent work that may continue: all of R0-GGUF-INSPECT, R4-ALIGNPACK-LAYER-MAJOR, and
  R4.5-EXTERNAL-BUFFER-SPIKE.
Resume condition: an Align release adds a fallible constructor and/or a capacity accessor to
  `buffer`.
Align commit or pull request: none
align-llm verification: replace the observable-consequence guards (a zero-length read at an
  in-range offset) with a direct capacity check before the read; pass `make gguf-smoke`,
  `make alignpack-smoke`, and `make ggml-spike-smoke`.
```

### Motivation and current sibling evidence

`buffer(cap)` is an advisory capacity **hint** that never fails and cannot be interrogated. Verified
in the sibling checkout at the pinned commit `4b515f8d37de2e9a9ba06170c5842fd12dc1cba2`:

- `crates/align_runtime/src/lib.rs:10090` (`align_rt_buffer_new`) requests `data.try_reserve_exact(
  requested)` and, on failure, silently sets `cap = 0` rather than surfacing an error — there is no
  way for the caller to observe that the reservation degraded, because `buffer(cap)` returns a bare
  `buffer`, not a `Result`.
- `crates/align_runtime/src/lib.rs:10156` (`align_rt_buffer_put`, backing `put_<scalar>`) and
  `:10186` (`align_rt_buffer_append`) grow the buffer with `Vec::extend_from_slice` — Rust's ordinary
  infallible, abort-on-OOM growth — entirely independent of the `cap` the constructor reserved (only
  `b.cap = b.cap.max(b.len)` afterward). This is exactly why `docs/specs/r4-5-external-buffer.md`
  section 6.1 correction C8 measured `buffer(4611686018427387904)` (2^62) followed by one `put_u8`
  publishing length `1` with **no failure anywhere**: the oversized reservation degrades to `cap = 0`
  invisibly, and the unrelated one-byte append succeeds on its own, independent growth path.
- There is no `.cap()`/`.capacity()` accessor anywhere in `crates/align_runtime/src/lib.rs`'s buffer
  method set (`bytes`, `len`, `put_<scalar>`, `append` — the same set `docs/language-spec.md:651-660`
  documents for `buffer`), and `grep -n 'cap()' docs/language-spec.md` returns nothing: the only way
  to learn what a read produced is `b.len()`, which reports the **last read's** byte count, not what
  was reserved.
- `docs/specs/r0-gguf-inspection.md:1073` (item 17) reaches the identical conclusion from GGUF
  inspection: "Capacity is not observable at this pin (`b.len()` is the last read's count; there is
  no `b.cap()`), so the observable consequence is tested instead: a zero-length read at a position
  `ensure` has already proved strictly inside the file reports the new `GGUF_WINDOW_UNAVAILABLE`."
  `docs/specs/r0-gguf-inspection.md:658` records `GGUF_WINDOW_UNAVAILABLE` as carrying **no fixture**,
  because "neither cause can be provoked deterministically from a test." R4 reached the same
  conclusion independently: `docs/specs/r4-alignpack-layer-major.md:165` cites the identical
  `try_reserve_exact` degrade-to-zero mechanism (`crates/align_runtime/src/lib.rs:10090-10102`,
  `9971`) behind its own `R4_WINDOW_UNAVAILABLE`, and line 1825 records
  `scripts/run-alignpack-smoke`'s `window-unavailable` case as `N/A` because "truncating the source
  between the plan and the copy needs an injection point the arm does not expose."
- R4.5-EXTERNAL-BUFFER-SPIKE's own correction C8 (`docs/specs/r4-5-external-buffer.md` section 6.1)
  confirms this a third time for the same underlying mechanism: the plan's `spike-window-huge`
  fixture ("a fixture header claiming a `pack_bytes` past any allocation") cannot reach
  `R4_WINDOW_UNAVAILABLE`, because no fixture can make the advisory reservation degrade in a way an
  input controls; the code is retained purely as a fail-closed guard for a file that shrinks
  underneath the reader, and `spike-dimension-bound` was substituted as the input-reachable
  bounded-work guard the design actually needed.

**New evidence, and why the priority is now high — R6-RESIDENT-WEIGHTS is this request's second and
sharpest client.** At R4.5's 447 MB window the degrade-to-zero was an unreachable guard on a host
that would have held the window anyway. `docs/specs/r6-resident-weights.md` reserves one
**4,677,533,696-byte** arena, measured on the reference host at a 4,736,313,856-byte peak memory
footprint, and there the same gap is the difference between a document and a process abort: a host
that cannot hold the arena does not get `R6_RESIDENT_UNAVAILABLE`, it dies inside `Vec` growth with
no code, no document, and no Align line running after it. That capability states the consequence as
a contract row (its section 3.6) rather than hiding it, keeps `RESIDENT=weights` **opt-in** for
exactly this reason, and adds a physical-memory preflight to `scripts/run-decode-step` — which is
why `Blocking: no` still stands. The observable-consequence guard it does ship
(`weights.bytes().len() != pad + resident_bytes` → `R6_RESIDENT_UNAVAILABLE`) is the same shape as
`R4_WINDOW_UNAVAILABLE` and is equally unreachable from any input.

**Consequence for the client.** Three independent capabilities (R0, R4, R4.5) each converged on the
same workaround: define `*_WINDOW_UNAVAILABLE`/`R4_5_ALIGNMENT`-adjacent codes as fail-closed guards
for *the observable consequence* of a degraded reservation (a zero-length read at a
provably-in-range offset) rather than for the reservation failure itself, and each records that code
as carrying no input-reachable fixture. The guard is real, but nothing in the language lets a client
ask "did my `buffer(n)` actually get `n` bytes" before finding out the hard way.

### Requested capability

```text
buffer.try_new(n: i64) -> Option<buffer>   // or Result<buffer, Fault>; fails rather than degrading
b.cap() -> i64                             // the capacity actually reserved, independent of .len()
```

### Acceptance criteria

1. `buffer.try_new(n)` returns `None` (or `Err`) when the requested capacity cannot be reserved,
   verified against a request large enough to exceed available memory, and returns a buffer whose
   `.cap()` is at least `n` otherwise.
2. `b.cap()` reports the buffer's actually-reserved capacity at any point in its lifetime,
   independent of `.len()`, verified against a buffer grown past its original reservation via
   `put_<scalar>`/`append`.
3. `align-llm` verification: `GGUF_WINDOW_UNAVAILABLE` (`src/gguf.align`),
   `R4_WINDOW_UNAVAILABLE` (`src/alignpack.align`, `src/alignpack_read.align`), and the
   corresponding window-availability checks in `src/ggml_spike.align` are replaced with a direct
   `b.cap()` check before the read that needs the window, each guard's fixture status (currently
   `N/A`/no-fixture) is re-evaluated now that the failure is input-reachable, and `make gguf-smoke`,
   `make alignpack-smoke`, and `make ggml-spike-smoke` all pass.

---

## Request 36 — In-place replacement of owned array record fields and moving out of nested fields

```text
Status: PROPOSED
Priority: medium
Blocking: no
Blocked gate or slice: none. R5A-DENSE-LAYER-FORWARD (`docs/specs/r5a-dense-layer-forward.md`
  section 6, correction C9) ships eight single-assignment records instead of the one `Outcome` its
  own section 3.7 designed, each assigned exactly once, as a whole, by the stage that produces it.
Independent work that may continue: all of R5A-DENSE-LAYER-FORWARD.
Resume condition: an Align release admits in-place replacement of an owned `array<T>` struct field
  (assigning a whole new array to an already-initialized field of an owned struct), and/or admits
  moving a whole nested Move-typed struct field out of its parent struct.
Align commit or pull request: none
align-llm verification: collapse `src/layer_forward.align`'s eight column records (`TokenColumns`,
  `MemberColumns`, `Layout`, `ReadColumns`, `AbiColumns`, `PlacementColumns`, `NodeColumns`,
  `OracleStates`) into the one `Outcome` section 3.7 designed, with each stage replacing the fields
  it produces in place; pass `make layer-forward-smoke`.
```

R6-OLMOE-DECODE adds `src/moe_decode_step.align` and `gmake moe-decode-step-qualification` as
clients. Its `steps[]` rows carry a `n_layer x n_expert_used` integer matrix **per step** — the
demand stream this capability exists to publish — and R5A correction C9's shape forces that to be
rendered as it is produced into one string rather than carried as a column set, exactly as R5E's
`schedule[]` is. **No status change**, `Blocking: no`.

### Motivation and current sibling evidence

R5A-DENSE-LAYER-FORWARD's document (`docs/specs/r5a-dense-layer-forward.md` section 3.7) was designed
around one `Outcome` record that every stage function appends a column to as it runs. The
implementation could not build that shape.

Verified in the sibling checkout at the pinned commit `4b515f8d37de2e9a9ba06170c5842fd12dc1cba2`:

- `crates/align_sema/src/lib.rs:40934` is the exact diagnostic hit replacing an already-populated
  `array<i64>` field of an owned struct: "field replacement of {} is not supported yet (owned field
  replacement currently supports only `string` and `Option<string>` leaves; replace the whole
  struct)". Two sema regression tests already pin this exact text for `array<i64>` specifically
  (`crates/align_sema/src/lib.rs:69774`, `:69783`), so the restriction is deliberate and tested, not
  an incidental gap.
- `crates/align_sema/src/lib.rs:35159` and `:38646` both carry the second half, reached from two
  different move-checking paths (a direct field-move expression at `:35159`, and a `let`-bound place
  read of a field at `:38646`): "moving a nested struct field out of a struct is not supported yet —
  clone it, or move the whole struct". A nested Move-typed sub-struct field therefore cannot be
  pulled out of its parent even to reassign it as a whole.

**Consequence for the client.** `src/layer_forward.align:889-894` records the forced shape in-repo:
"The document's columns live in one `Outcome`; its **columns** live in six small records, each
assigned exactly once, as a whole, by the stage that produces it. That shape is forced rather than
chosen: at this pin an owned `array<i64>` field cannot be replaced in place ... and a nested struct
field cannot be moved out of a struct either" (the comment predates the final count; the shipped file
holds eight — `TokenColumns` at `src/layer_forward.align:898`, `MemberColumns` at `:903-915`,
`Layout` at `:940-946`, `ReadColumns` at `:959`, `AbiColumns` at `:966`, `PlacementColumns` at `:974`,
`NodeColumns` at `:982-994`, and `OracleStates` at `:1010`). `Outcome` itself (`:1016` onward) keeps
only scalars and names. Each record is constructed exactly once, as a whole struct literal, by the
one stage function that owns it — for example `stage_members` (`src/layer_forward.align:1626-1745`)
builds `MemberColumns` and `Layout` in one literal at the end of the function rather than field by
field — because a struct built any other way would need either an in-place `array<i64>` field
replacement or a nested-field move, and both are refused. The design's own single-record shape —
simpler to read, and closer to what section 3.7 wrote down — is unavailable at this pin.

### Requested capability

Extending the existing owned-field-replacement surface the checker already carries for
`string`/`Option<string>` leaves:

1. Admit in-place replacement of an owned `array<T>` struct field (assigning a whole new array to an
   already-initialized field of an owned struct), on the same footing as the existing `string`/
   `Option<string>` leaf support.
2. Admit moving a whole nested (Move-typed) struct field out of its parent struct — nulling the
   parent's field the same way a top-level local's move already does — so a record whose fields are
   nested owned structs can be constructed incrementally instead of atomically.

### Acceptance criteria

1. `o.column := new_ids` (or equivalent) compiles and correctly frees the previous `array<i64>` when
   `o` is an owned struct whose `column: array<i64>` field was already initialized.
2. `sub := parent.nested_field` compiles and moves `nested_field` out of `parent`, leaving `parent`'s
   other fields readable and `parent.nested_field` unusable, when `nested_field` is itself a Move
   struct.
3. `align-llm` verification: `src/layer_forward.align`'s eight column records collapse into the one
   `Outcome` `docs/specs/r5a-dense-layer-forward.md` section 3.7 designed; `make layer-forward-smoke`
   passes unchanged in outcome.

---

## Request 37 — Compiler check-time scaling for long function bodies and `match` on `Result` inside loops

```text
Status: PROPOSED
Priority: medium
Blocking: no
Blocked gate or slice: none. R5A-DENSE-LAYER-FORWARD (`docs/specs/r5a-dense-layer-forward.md`
  section 6, correction C8) ships fourteen small functions instead of the wide arm its own design
  was silent on, purely to keep `make check` in seconds rather than minutes.
Independent work that may continue: all of R5A-DENSE-LAYER-FORWARD, and any other capability writing
  a long checked function or a `match` on a `Result` inside a loop.
Resume condition: an Align release bounds per-function check time (near-)linearly in body length,
  and/or removes the disproportionate cost of a `match` on a `Result` with block arms inside a loop
  relative to the same loop written with `?`.
Align commit or pull request: none
align-llm verification: recombine `src/layer_forward.align`'s fourteen `?`-propagating functions (a
  representative merge, not necessarily back into section 3.7's single-`Outcome` shape, since Request
  36 governs that data-shape question separately) and pass `make check` on the merged module in under
  10 s.
```

### Motivation and current sibling evidence

R5A-DENSE-LAYER-FORWARD's design (`docs/specs/r5a-dense-layer-forward.md` sections 3-4, and section
6's own correction row C8) was silent on how the arm should be shaped: nothing there says a stage
must be its own function, and nothing warns against a `match` on a `Result`. The implementation found
both choices carry a real, measured compiler cost:

- Per-function checking is superlinear in body length: a 400-line function body checks in 40 s and a
  900-line one does not finish in 600 s, measured on the section 2.1 host at the pinned commit
  `4b515f8d37de2e9a9ba06170c5842fd12dc1cba2` (`docs/specs/r5a-dense-layer-forward.md` section 6, row
  C8).
- A `match` on a `Result` with block arms costs far more to check than the same control flow written
  with `?`, and the difference compounds inside a loop: one stage function with two in-loop `match`
  expressions took 90 s to check, and the identical function rewritten with `?` took 2 s — roughly a
  45x difference for the same computation (same row).

A grep of the sibling repository's own performance notes (`docs/open-questions.md`,
`docs/impl/21-build-perf-plan.md`, and the rest of `docs/impl/*`) for this specific cost — per-function
check-time scaling, or `match`-in-loop cost relative to `?` — returns nothing: no sibling note found;
reproduced only in align-llm at `src/layer_forward.align`.

**Consequence for the client.** `src/layer_forward.align:1218-1221` records the design forced by this
measurement in-repo: "One `match` in one place. At this pin a `match` on a `Result` with block arms
is markedly more expensive to check than a call — inside a loop the difference is minutes against
seconds — so every one of the arm's fallible calls either propagates with `?` or routes through this
two-line function (section 6, correction C8)." The arm is split across fourteen functions
(`stage_geometry` through `stage_prepare`/`execute`, `src/layer_forward.align:1463-2467`, none over
two hundred lines), every fallible call inside a loop (for example `build_nodes`,
`src/layer_forward.align:1303-1358`, one `?` per graph-node op) propagates with `?`, and every
top-level fallible call outside a loop routes through the two-line `take`/`take_pack` helpers
(`src/layer_forward.align:1222-1234`) instead of a `match`. The result: `check-per-unit
src/layer_forward.align` is 6 s and `make check` is 86 s for 29 units — a shape chosen purely to keep
the compiler fast, not because it reads better than the one-`Outcome`-per-stage design that section
3.7 originally wrote down (see Request 36).

**Largest client to date, from R5D-MOE-LAYER-FORWARD** (`docs/specs/r5d-moe-layer-forward.md`
section 5.5, correction C20). R5D applied the remedy this request's own client evidence prescribes —
the topology tables, the geometry, and the routing decision are a separate module
(`src/layer_olmoe.align`) from the arm (`src/moe_layer_forward.align`) — and the arm's unit is still
the dominant cost. Measured warm on the section 2.1 host of that ledger, at
`4b515f8d37de2e9a9ba06170c5842fd12dc1cba2`:

```text
alignc check-per-unit src/moe_layer_forward.align   (4-unit graph)   17.02 s
alignc check-per-unit src/model_forward.align       (7-unit graph)   17.21 s
alignc check-per-unit src/layer_olmoe.align                           0.67 s
alignc check-per-unit src/ggml_ffi.align                              0.18 s
alignc check-per-unit src/alignpack_read.align                        0.60 s
make check                                          (30 units)       134 s
```

The arm's own unit is therefore roughly **15.6 s** of its graph's 17.0 s, against 0.67 s for the
1,403-line `src/layer_olmoe.align` beside it — a 23x time ratio for a 3.3x line ratio, on a module
written after this request was filed. Splitting the arm again would move the cost, not remove it,
which is why R5D records this as language-owned rather than as an application task, and why
`r5b-model-prefill-forward.md` correction C26 and `r5c-metal-prefill.md` correction C22 **retire**
the under-10 s single-unit acceptance target those ledgers carried instead of restating it a third
time. This request's own `align-llm verification` line above is unchanged: it names
`src/layer_forward.align`, not the R5D arm.
3.7 originally wrote down (see Request 36).

### Requested capability

No specific mechanism is proposed — this is a compiler performance property, not a missing language
surface. The register asks for:

1. A compiler test or benchmark that bounds per-function check time (near-)linearly in body length,
   so a single well-organized function does not force an artificial split purely for check-time
   reasons.
2. Investigation and, if warranted, a fix for the disproportionate cost of a `match` on a `Result`
   with block arms inside a loop relative to the same loop expressed with `?`, so a `match` is not a
   45x check-time tax over an equivalent `?` chain.

### Acceptance criteria

1. A compiler benchmark exists that measures check time against function body length and shows it
   growing (near-)linearly — or documents and bounds any remaining superlinear factor — rather than
   the unbounded-looking growth measured here (400 lines → 40 s, 900 lines → not finished at 600 s).
2. The same benchmark class measures a `match` on a `Result` with block arms inside a loop against
   the equivalent `?`-propagating loop and shows the ratio bounded well below the ~45x measured here,
   or documents why the difference is inherent.
3. `align-llm` verification: `src/layer_forward.align`'s fourteen functions are recombined (a
   representative merge) and `make check` on the re-merged module finishes in under 10 s.

---

## Request 38 — Positional write, reset, and bounded read length for `buffer`

```text
Status: PROPOSED
Priority: medium
Blocking: no
Blocked gate or slice: none. R5B-MODEL-PREFILL-FORWARD (`docs/specs/r5b-model-prefill-forward.md`
  section 6, correction C5) ships a bounded C `memcpy` shim entry point,
  `align_ggml_window_copy`, and a 1 MiB transient buffer instead of positional writes into the
  reused window.
Independent work that may continue: all of R5B-MODEL-PREFILL-FORWARD.
Resume condition: an Align release adds a positional/offset write to `buffer` (or a reset that
  truncates a buffer to a chosen length without reallocating) and a bounded-length `pread` that
  requests fewer bytes than the buffer's capacity.
Align commit or pull request: none
align-llm verification: replace `align_ggml_window_copy`'s bounded `memcpy` and the
  `read_into_window`/`window_put` chunked-copy path (`src/model_forward.align`) with a direct
  positional `buffer` write and/or a bounded `pread` into the reused window; delete the shim
  symbol; pass `make layer-forward-smoke` and `make model-forward-qualification` unchanged in
  outcome.
```

### Motivation and current sibling evidence

R5B-MODEL-PREFILL-FORWARD streams the whole twenty-eight-layer Qwen2 model through one reused
447 MB window rather than reallocating a window per layer (`docs/specs/r5b-model-prefill-forward.md`
section 3.5, "one window, reused thirty times"). That shape needs the window's contents replaced at
each layer's block offsets without changing the window's identity, and Align's `buffer` cannot do
that.

Verified in the sibling checkout at the pinned commit `4b515f8d37de2e9a9ba06170c5842fd12dc1cba2`:

- `crates/align_runtime/src/lib.rs:10078-10085` (`prepare_uninit_window`, the shared entry both
  `pread` and construction use to obtain a write destination) unconditionally calls
  `self.data.clear()` (`:10079`) before returning a pointer into `spare_capacity_mut()` — every
  write starts at index 0. There is no positional/offset write and no truncate-without-reallocate
  reset anywhere in the file's `Buffer` method set (`align_rt_buffer_new`, `_bytes`, `_len`,
  `_free`, `_put`, `_append`, and `align_rt_io_file_pread`/`_pwrite` are the complete set that
  touches a `Buffer`).
- `crates/align_runtime/src/lib.rs:9962-9990` (`align_rt_io_file_pread`) always requests exactly
  `b.cap` bytes from the underlying `pread(2)` (`pread(fd, dst, b.cap, off)` at `:9976`) — there is
  no length parameter narrower than the buffer's full capacity.
- `docs/language-spec.md:651-660` (the `buffer` method table Request 35 also cites) lists only
  `bytes`, `len`, `put_<scalar>`, and `append`; none accepts a destination offset.

**Consequence for the client.** `docs/specs/r5b-model-prefill-forward.md` section 6 correction C5
records the forced design in-repo: "An Align `buffer` is append-only. `put_*` and `append` write at
the logical length; there is no offset write, no truncate, and no reset. `f.pread` is the only
operation that rewrites a buffer's contents, and it overwrites from index 0 and always requests the
buffer's whole capacity." Refilling a reused 447 MB window from a pack file has exactly three
implementations, and the document names two of them wrong (12.5 GB of I/O to re-`pread` the whole
window on every layer, or faulting in 447 MB of fresh pages thirty times while briefly holding two
windows) — so the implementation adds `align_ggml_window_copy(window, window_bytes, offset,
source, source_bytes, n)`, a bounded C `memcpy` between two Align-owned byte ranges, to the shim's
shared region (`scripts/ggml_shim.c:367`, `scripts/ggml_shim_stub.c:360`, wired at
`src/ggml_ffi.align:193,772`) purely so the window can be written at an offset. Correction C6
further forces a 1 MiB transient (`CHUNK_BYTES := 1048576`, `src/model_forward.align:1958`) that
reads each weight member's bytes through `handle.pread(temp, ...)` and then copies them into the
target offset via `window_put`/`align_ggml_window_copy` (`src/model_forward.align:1975-2033`),
because `pread`'s always-full-capacity read would otherwise over-read every member's tail if the
transient were larger than the smallest member.

**R6-KV-PERSIST is `align_ggml_window_copy`'s second consumer, and adds no new shim symbol**
(`docs/specs/r6-kv-persist.md` section 2.7). Its load path must fill a caller-owned
`mut plane: buffer` from a file region, which is the same shape for the same two reasons — the
buffer is append-only, and `f.pread` overwrites from index 0 and always requests the whole capacity
— so the plane is read in `CHUNK_BYTES` rounds through one transient and copied in at an offset
through `model_forward.window_put`. The format's own region order is what makes the tail read safe:
the plane is the container's **last** region and `f.len() == total_bytes` is validated before the
first plane byte is read, so the final short read is short by exactly the remaining bytes rather
than an over-read. **No status change.**

**R6-RESIDENT-WEIGHTS measures the platform boundary this request describes, and is its third
consumer.** `docs/specs/r6-resident-weights.md` section 2.4 ran the probe at the pinned compiler
against the real 4,683,073,536-byte GGUF and found the limit is not a soft cost but a hard refusal:

```text
$ ./r6w_probe MODEL.gguf 2147483647 0        # INT_MAX
mode: single
requested: 2147483647   count: 2147483647   len: 2147483647   ns: 482214208

$ ./r6w_probe MODEL.gguf 2147483648 0        # INT_MAX + 1
mode: single
pread: ERROR
```

The boundary is **exactly `INT_MAX`**: Darwin's `pread(2)` refuses `nbyte >= 2 GiB` with `EINVAL`,
and because `align_rt_io_file_pread` always asks for `b.cap`, **a `buffer` at or above 2 GiB cannot
be filled by one `pread` at this pin on this platform at all**. That is not a preference for chunked
reads; it is the only shape available. The resident arena is filled in 4,669 `CHUNK_BYTES` rounds
through the same `read_into_window` the streamed path uses, at a measured 2.58 s for
4,677,120,000 B. A bounded-length `pread` would let each weight member be read straight to its own
arena offset and would delete the transient and the `window_copy` from the fill entirely.
**No status change**; this is continuing evidence, and the chunked fill is not written against a
hypothetical surface.

### Requested capability

```text
b.pread_into(offset: i64, n: i64) -> i64   // write at most n bytes starting at `offset`, not index 0
```

or equivalent: a positional write on `buffer` (an offset parameter on `pread`, or a `put_at`/
`write_at` that does not move the logical length), and a bounded-length `pread` overload that
requests fewer than `b.cap()` bytes.

### Acceptance criteria

1. A `buffer` can be refilled at a chosen offset without changing its capacity or reallocating,
   verified by writing two non-overlapping regions of one buffer with two positional writes and
   reading both back.
2. `f.pread` (or an equivalent) accepts a length shorter than the destination buffer's capacity and
   reads at most that many bytes, verified against a buffer sized larger than the requested read.
3. `align-llm` verification: `align_ggml_window_copy` (`scripts/ggml_shim.c:367`,
   `scripts/ggml_shim_stub.c:360`, `src/ggml_ffi.align:193,772`) is deleted, `read_into_window`/
   `window_put` (`src/model_forward.align`) read directly into the reused window at each member's
   offset, and `make layer-forward-smoke` / `make model-forward-qualification` pass unchanged in
   outcome.

---

## Request 39 — Release of rebound `buffer` allocations before frame exit

```text
Status: PROPOSED
Priority: medium
Blocking: no
Blocked gate or slice: none. R5B-MODEL-PREFILL-FORWARD reads each weight member through one buffer
  reused across the whole run instead of `alignpack_read.read_exact`'s per-call `buffer(n)` rebind,
  to keep peak resident set at one window's size.
Independent work that may continue: all of R5B-MODEL-PREFILL-FORWARD, R4-ALIGNPACK-LAYER-MAJOR, and
  R4.5-EXTERNAL-BUFFER-SPIKE.
Resume condition: an Align release frees (or makes reclaimable within the same frame) the storage a
  `borrow mut buffer` parameter held before a rebinding assignment (`window = buffer(n)`) replaces
  it, rather than retaining every prior allocation until the caller's frame exits.
Align commit or pull request: none
align-llm verification: `src/model_forward.align`'s `read_into_window`/`fill_members` collapse onto
  `alignpack_read.read_exact` (removing the duplicated per-member read path built solely to avoid
  the rebind-retention cost), and `make layer-forward-smoke` / `make model-forward-qualification`
  pass with resident set unchanged from the reused-buffer baseline (507,969,536 B).
```

### Motivation and current sibling evidence

`alignpack_read.read_exact` (`src/alignpack_read.align:230-238`) takes its window as a
`borrow mut buffer` parameter and rebinds it on every call: `window = buffer(n)` (line 238) discards
whatever the caller's binding pointed at and allocates a fresh buffer. Verified in the sibling
checkout at the pinned commit `4b515f8d37de2e9a9ba06170c5842fd12dc1cba2`: nothing in
`crates/align_runtime/src/lib.rs`'s `Buffer`/`align_rt_buffer_*` set frees the previous allocation
at the point of a rebind — the old `Buffer`'s backing `Vec` is only dropped when the `Buffer` itself
is (`align_rt_buffer_free`, run at the owning frame's cleanup), not when a `borrow mut` binding is
reassigned mid-call. A `borrow mut` rebind therefore leaves the prior allocation live and
unreachable from the caller until the caller's own frame ends.

**Consequence for the client, measured directly.** `docs/specs/r5b-model-prefill-forward.md`
section 6 correction C6: "`alignpack_read.read_exact` rebinds its window to a fresh `buffer(n)` on
every call, and at 339 members those allocations are not returned to the process while the caller's
frame lives: peak resident set measured 3,442,016,256 to 4,262,133,760 B for a 447 MB window.
Reading through one buffer that `f.pread` refills in place brings it to 507,969,536 B." The
implementation therefore does not use `alignpack_read.read_exact` for the per-member read path at
all: `fill_members`/`read_into_window` (`src/model_forward.align:2005-2060`) take a
`borrow mut temp: buffer` and refill it in place via `handle.pread(temp, ...)`, never rebinding it,
to avoid the measured 6.8-8.5x resident-set inflation the rebind-per-call shape produces at this
member count. `read_exact` itself is unchanged and remains R0/R4's shared reader for every caller
that reads fewer times per run.

**R6-KV-PERSIST is a cited client** (`docs/specs/r6-kv-persist.md` section 2.7). Its plane refill
uses one `buffer(model_forward.CHUNK_BYTES)` transient that `f.pread` refills in place and that is
**never rebound**, for exactly the reason measured above; the two small metadata regions still go
through `alignpack_read.read_exact`, which rebinds, because they are read once each at 192 and at
most 128 bytes. **No status change.**

### Requested capability

Free (or make immediately reclaimable within the current frame) the storage backing a `borrow mut`
handle-typed parameter (`buffer`, and any other Move handle in `MOVE_HANDLE_TYPES`) at the point a
rebinding assignment replaces it, rather than deferring that free until the caller's own frame
exits — the same early-free discipline an owned local's move/reassignment already gets, extended to
a value reached only through a `borrow mut` parameter.

### Acceptance criteria

1. A function taking `borrow mut w: buffer` and rebinding it (`w = buffer(n)`) on each of N calls
   from a loop in the caller shows peak resident set bounded near one buffer's size (not N buffers'
   worth), verified for N large enough to make the difference measurable (a few hundred, matching
   R5B's 339 members).
2. `align-llm` verification: `src/alignpack_read.align:230-238`'s `read_exact` (used elsewhere in
   the codebase, e.g. `src/gguf.align`, `src/layer_forward.align`) is unchanged in outcome, its
   rebind-per-call peak resident set drops to the reused-buffer baseline, and
   `src/model_forward.align`'s duplicated per-member read path collapses onto it; `make gguf-smoke`,
   `make alignpack-smoke`, `make layer-forward-smoke`, and `make model-forward-qualification` all
   pass.

---

## Request 40 — `array_builder<T>` as a struct field type

```text
Status: PROPOSED
Priority: medium
Blocking: no
Blocked gate or slice: none. R5B-MODEL-PREFILL-FORWARD's per-layer member-plan builder
  (`plan_layer_members`, `src/model_forward.align:863-908`) takes seven separate
  `borrow mut array_builder<i64>` parameters instead of one `borrow mut` record grouping them.
Independent work that may continue: all of R5B-MODEL-PREFILL-FORWARD.
Resume condition: an Align release admits `array_builder<T>` as an ordinary struct field.
Align commit or pull request: none
align-llm verification: collapse `plan_layer_members`'s seven `array_builder<i64>` parameters
  (`src/model_forward.align:869-875`) and the matching seven locals in `build_plan`
  (`src/model_forward.align:930-936`) into one record parameter with `array_builder<i64>` fields;
  pass `make layer-forward-smoke` and `make model-forward-qualification` unchanged in outcome.
```

### Motivation and current sibling evidence

Request 24 established that the plain-text `builder` is admitted as a `borrow mut` parameter type
but not as a struct field, and that `array_builder<T>` — unlike `builder` — *is* already admitted as
a `borrow mut` parameter type at this pin. R5B's implementation hits the companion gap:
`array_builder<T>` is not admitted as a struct field either, so a helper that must accumulate into
several builders at once cannot group those builders into one record and pass it by `borrow mut` —
it must take one parameter per builder.

Verified directly against the pinned managed compiler (`4b515f8d37de2e9a9ba06170c5842fd12dc1cba2`,
`alignc 0.5.0`) with a two-line probe:

```text
Bag {
  b: array_builder<i64>,
}
```

`alignc check` on that probe (plus a trivial `pub fn main`) reports `error: struct field type is not
supported here, got array_builder<i64>` — the same generic `is_field_ok` rejection Request 34 cites
for `raw` (`crates/align_sema/src/lib.rs:6625-6628`), reached because `array_builder` is neither in
`MOVE_HANDLE_TYPES` (`crates/align_sema/src/lib.rs:62004-62030`, which admits `buffer` at line
`62007` but no builder type) nor any of the other admitted field shapes `is_field_ok`
(`crates/align_sema/src/lib.rs:62044-62122`, catch-all `_ => return false` at `:62121`) enumerates.
The bare `builder` text is rejected even earlier, as an unknown type name
(`error: unknown type: 'builder'`), matching Request 24's own finding.

**Consequence for the client.** `plan_layer_members` (`src/model_forward.align:863-908`) accumulates
seven parallel `i64` columns — member type, `ne0`, `ne1`, `nbytes`, pack offset, source offset,
window offset — one per column, and needs a `borrow mut array_builder<i64>` for each because there
is no way to bundle them into one `borrow mut MemberBuilders` record: `array_builder<i64>` is
refused as a field of `MemberBuilders` by the same diagnostic reproduced above. The signature at
`src/model_forward.align:869-875` carries all seven as separate parameters, and `build_plan`
(`src/model_forward.align:914-936`) declares and threads all seven as separate locals; the same
seven-wide shape recurs for the embedding, head, and per-layer member-table builders elsewhere in
the same file (`src/model_forward.align:1078-1089`, `:1124-1135`, `:1181-1192`).

### Requested capability

Admit `array_builder<T>` as an ordinary struct field, with the field making the enclosing struct
Move (recursive `Drop` frees the builder's backing storage) and reachable through a `borrow mut`
parameter on the same footing `array_builder<T>` already gets as a bare `borrow mut` parameter —
`push` through the field, but no return/store/consume of the field's builder outside the struct's
own owner.

### Acceptance criteria

1. A struct with an `array_builder<i64>` field compiles, and a helper taking that struct by
   `borrow mut` can `push` into the field and observe every pushed element after the helper returns
   (via `.to_array()` on the field, called by the caller).
2. The struct's `Drop` frees the field's builder storage exactly once, verified by exercising both
   the finished (`.to_array()` called) and unfinished (dropped mid-accumulation) paths.
3. `align-llm` verification: `plan_layer_members`'s seven `array_builder<i64>` parameters
   (`src/model_forward.align:869-875`) collapse into one `borrow mut MemberBuilders` record
   parameter; `make layer-forward-smoke` and `make model-forward-qualification` pass unchanged in
   outcome.

---

## Request 41 — Non-`Copy` capture in `spawn` closures (`task_group`)

```text
Status: PROPOSED
Priority: medium
Blocking: no
Blocked gate or slice: R5 microbenchmark C only. R5C-METAL-PREFILL-ARM
  (`docs/specs/r5c-metal-prefill.md` section 1.4) discharges required microbenchmark A on unified
  memory without it; required microbenchmark C (async prefetch of the next layer's window while the
  current graph computes) cannot be written at all at this pin and stays deferred with this gap
  named rather than worked around.
Independent work that may continue: all of R5C-METAL-PREFILL-ARM.
Resume condition: an Align release admits an owned-value (or exclusive-borrow) capture into a
  `spawn` closure, and/or an owned task result, sufficient to hand a prefetch task the Align-owned
  window it must fill.
Align commit or pull request: none
align-llm verification: pending — implement a `--model-forward-gpu --prefetch` arm that overlaps
  layer `L+1`'s read with layer `L`'s compute and pass a new `prefetch-forward-qualification`.
```

### Motivation and current sibling evidence

R5C-METAL-PREFILL-ARM's design set out to file "impure/I-O work inside `task_group`" as a candidate
request and instead measured that it already works. Verified against the sibling checkout at
`/Users/hiro/Projects/align`, pinned at `4b515f8d37de2e9a9ba06170c5842fd12dc1cba2` (`git rev-parse
HEAD` confirms the checkout is exactly this commit):

- **Purity binds `par_map` alone, not `task_group`/`spawn`.**
  `docs/guide/10-closures-and-parallelism.md:47` defines Pure as "no I/O, no rng, no FFI, and no
  mutation of external state it does not own", and its `par_map` example at lines 55-56 shows that
  requirement enforced only there (`error: 'par_map' requires a Pure function`); the
  `task_group`/`spawn` section (heading at line 84, `spawn`/`wait`/`get` described at line 101)
  carries no such restriction. `docs/language-spec.md:521` states the same division directly:
  "Effects restrict optimization legality, while explicit `par_map` still requires Pure callables" —
  naming `par_map` alone. A four-line probe (`task_group { a := spawn(fn { readsome(p) }) ... }`,
  `fs.open_rw` + `f.pread` inside the spawned task, and a second probe with an `unsafe`/`extern "C"`
  call inside a spawned task) both `alignc check`s clean and runs.
- **The blocker is closure capture, not purity.** A spawned task that must write into a caller-owned
  `buffer` fails at check time:

  ```text
  tg2.align:14:20: error: a lambda cannot capture the owned value 'w' yet
                          (capture supports copy values like int/float/bool/char)
  tg2.align:14:33: error: the exclusive borrowed argument to 'fill' must be rooted in mutable storage
  ```

  the generic capture diagnostic (`crates/align_sema/src/lib.rs:48950`, `"a lambda cannot capture
  the owned value '{cname}' yet (capture supports copy values like int/float/bool/char)"`) and the
  companion rooting diagnostic (`crates/align_sema/src/lib.rs:43724`, `"the exclusive borrowed
  argument to '{display}' must be rooted in mutable storage"`).
- **The task cannot return a filled buffer either**, which is Request 34's own gap reached from a
  second direction: `fn make_buf() -> Result<buffer, i32> { return Ok(buffer(16)) }` is rejected by
  the unconditional `Ty::Buffer` exclusion inside `scalar_arg`
  (`crates/align_sema/src/lib.rs:60819`) with `error: Result ok payload cannot be \`buffer\` — an
  owned I/O handle/buffer is bound to one local, not collected into an array/slice/box (bind it to a
  local)`. So both halves of the prefetch shape are closed: the task cannot **capture** the window
  and cannot **return** a filled buffer.

**Consequence for the client.** `docs/specs/r5c-metal-prefill.md` section 2.10 records the forced
conclusion: R5's required microbenchmark C — a task that reads layer `L+1`'s bytes into the
Align-owned window while the device computes layer `L` — cannot be written at this pin, because the
prefetch task must own (or exclusively capture) the window's `buffer` for the duration of the read.
An `i64`-address workaround through the existing `align_ggml_window_copy` FFI symbol would compile —
a `Copy` `i64` captures and runs correctly — but it is **deliberately not proposed**: `CLAUDE.md`
forbids building a compatibility layer around a language-owned gap, and it would put the window's
bounds outside Align's view, precisely what `r5b-model-prefill-forward.md` correction C20 removed
when it replaced a caller-computed `window_bytes` with the borrow's own `slice.len()`.

### Requested capability

Align-consistent and deliberately minimal: allow a `spawn` closure to capture an **exclusive
`borrow mut`** of caller-owned storage that the enclosing `task_group` provably outlives. The
lifetime argument is already the language's own — leaving a `task_group`, including by early return
or error propagation, joins its tasks before captured frame-owned locals or enclosing-arena storage
are released — and exclusivity is already what `borrow mut` proves. Disjointness between two spawned
tasks is the open question; the natural bound is **one exclusive capture per spawn**, rejecting two
spawns that capture the same root.

### Acceptance criteria

1. A `task_group` in which one spawned task fills a caller-owned `buffer` via `f.pread` while the
   main thread computes checks and runs at the pin.
2. Two spawns capturing the same root are rejected at check time.
3. `align-llm` verification: a `--model-forward-gpu --prefetch` arm overlaps layer `L+1`'s read with
   layer `L`'s compute and publishes microbenchmark C against `r5c-metal-prefill.md` section 5.3's
   1,423.8 ms of `pread`; passes a new `prefetch-forward-qualification`.

## Request 42 — `alignc check` as a superset of `alignc build` (region checking parity)

```text
Status: PROPOSED
Priority: high
Blocking: no
Blocked gate or slice: none. R5C-METAL-PREFILL-ARM (`docs/specs/r5c-metal-prefill.md` section 6
  correction C5, section 7.3 item 1) treated a clean `make check` as insufficient evidence of a
  compiling checkpoint and ran `make build` before trusting any candidate module split.
Independent work that may continue: all of R5C-METAL-PREFILL-ARM and every capability that uses
  `make check` (the narrow owner run after a coherent batch) as its compiling-checkpoint signal.
Resume condition: an Align release makes `alignc check` and `alignc check-per-unit` report every
  region-checker (borrow/lifetime) error that `alignc build` reports for the same source, or
  documents an explicit, checkable list of diagnostic classes `check` intentionally defers to
  `build`.
Align commit or pull request: none
align-llm verification: `make check` on `src/gpu_forward.align` plus `src/model_forward.align`
  with a seeded region error (a `borrow mut` out-parameter read by a caller in another module after
  a sibling out-parameter is reassigned, the exact C5 shape) fails with the same diagnostic
  `make build` already reports, instead of passing clean.
```

### Motivation and current sibling evidence

R5C-METAL-PREFILL-ARM's design first split `--model-forward-gpu` into its own module
(`src/gpu_forward.align`) calling `src/model_forward.align`'s `execute` directly. Section 6
correction C5 (`docs/specs/r5c-metal-prefill.md:1296-1319`) records that this module split checked
clean and failed only at `alignc build`, in the region checker, with two distinct diagnostics for
two distinct shapes:

```text
src/gpu_forward.align:556:36: error: use of invalidated borrow 'schedule': its source 'tokens' was
                                    moved or reassigned (or its storage was reallocated)
```

for the direct out-parameter form, and `cannot return a view that borrows local storage` for the
alternative that returns the four column sets bundled inside one record instead. Section 7.3 item 1
(`docs/specs/r5c-metal-prefill.md:1549-1556`) states the general conclusion: "`alignc check` is not
a superset of `alignc build`. Three separate programs in this capability checked clean and failed to
build, all in the region checker. A per-module `check` is therefore not sufficient evidence that a
module compiles, which matters because `make check` is the narrow owner this repository runs after
a coherent batch."

Reproduced fresh against the pinned managed compiler (`4b515f8d37de2e9a9ba06170c5842fd12dc1cba2`,
`alignc 0.5.0`) with a minimal two-module probe in a scratch directory, isolating the same shape as
the first diagnostic above — a callee reassigning one `borrow mut` out-parameter (`tokens`) while a
caller in another module later reads a sibling out-parameter (`schedule`):

```text
// callee.align
module callee

pub Cols { count: i64, ids: array<i64> }

fn inner(borrow mut tokens: Cols) {
  mut b: array_builder<i64> := array_builder()
  b.push(1)
  b.push(2)
  tokens = Cols { count: 2, ids: b.build() }
}

pub fn fill(borrow mut tokens: Cols, borrow mut schedule: Cols) {
  inner(tokens)
  mut c: array_builder<i64> := array_builder()
  c.push(3)
  schedule = Cols { count: 1, ids: c.build() }
}

// main.align
module main
import callee

fn empty_i64_array() -> array<i64> {
  mut b: array_builder<i64> := array_builder()
  return b.build()
}

fn main() -> i32 {
  mut tokens := callee.Cols { count: 0, ids: empty_i64_array() }
  mut schedule := callee.Cols { count: 0, ids: empty_i64_array() }
  callee.fill(tokens, schedule)
  return schedule.ids[0] as i32
}
```

```text
$ alignc check main.align
main.align:13:10: warning: lossy conversion: `i64 as i32` truncates the high bits — this is defined
                            behavior, not an error
ok: checked 4 function(s)

$ alignc build main.align
main.align:13:10: error: use of invalidated borrow 'schedule': its source 'tokens' was moved or
                          reassigned (or its storage was reallocated); create a new view from the
                          current source
main.align:13:10: error: value snapshot was invalidated before the enclosing operation: owner
                          'tokens' was moved, reassigned, or reallocated by a later eager operand
```

`check` reports the probe clean (exit 0, "ok: checked 4 function(s)"); `build` rejects the identical
source (exit 1) with the same diagnostic family C5 recorded from the real module split. The
diagnostic text is generated at `crates/align_sema/src/lib.rs:34422-34427` (the `BorrowEnd::Consumed`
arm of the invalidated-borrow message builder); `cannot return a view that borrows local storage`,
the second C5 diagnostic, is generated at `crates/align_sema/src/lib.rs:18595` and is reachable from
the same region-checking machinery.

One asymmetry the probe also surfaced, worth recording precisely rather than smoothing over:
`alignc check-per-unit` — the command this repository's `make check` actually invokes
(`Makefile:39-41`) — **does** reject this specific minimal probe with the identical diagnostic,
unlike the real C5 module split, which checked clean under the repository's actual `make check`.
`check-per-unit`'s own doc comment (`crates/align_driver/src/main.rs:1301-1303`) states why this is
expected rather than contradictory: it is "an additive capability that proves the separate-compilation
seam; it does not replace the whole-program `check`/`build` path" — its per-unit, interface-summary
walk is a different, narrower analysis than either whole-program `check` or `build`'s full MIR-level
region pass, and the three shapes disagree with each other about which of these two-file programs it
accepts. The minimal probe is offered as fresh, independently reproducible evidence of the same
underlying gap (no diagnostic class is a strict superset of another across `check`,
`check-per-unit`, and `build`), not as a byte-for-byte replay of the real C5 module split, whose
`execute`/`stage_geometry` call chain is larger and checked clean under all of `check` and
`check-per-unit` before failing only at `build`.

**Third client, and the second exact repeat of one diagnostic, from R5D-MOE-LAYER-FORWARD**
(`docs/specs/r5d-moe-layer-forward.md` section 5.5, correction C10). `src/moe_layer_forward.align`
checked clean per unit and the executable then refused to link, in the region checker, with

```text
cannot retain a shorter-lived view through this mutable borrow; copy it into the destination
region first
```

for `alignpack_read.member_at(f, x, block, within, c)` called with a **local** `block` while the same
call crosses a `borrow mut Counters`. `r5b-model-prefill-forward.md` section 6 correction C7 records
the identical sentence for the identical function at the same pin, and `r5c-metal-prefill.md` section
6 correction C5 records two further region diagnostics behind the same `check`/`build` gap. R5D's
mitigation is C10's: the member scan became its own function, `block_carries_role`
(`src/moe_layer_forward.align:1483-1520`), whose block is a parameter rather than a local. Whether
the recurrence is one request or two — the parity gap, and a separate constraint that a `Borrow`
crossing a `borrow mut` must be a parameter of the calling frame rather than a local — is left to
this register; R5D records the evidence and takes no dependency on either surface.

**Fourth client, and the largest measured gap so far, from R6-DECODE-KV-STEP1**
(`docs/specs/r6-decode-kv-step1.md` section 10.6). The first cross-module draft of
`src/decode_step.align` — the module that calls `src/model_forward.align`'s failure sink, plan,
`top_k`, and logits comparison directly — produced this:

```text
$ alignc check src/decode_step.align
ok: checked 413 function(s)

$ alignc build src/ggml_spike.align
… 178 errors, of which 161 are:
src/decode_step.align:524:25: error: cannot retain a shorter-lived view through this mutable
  borrow; copy it into the destination region first
```

`check` reported 413 functions clean; `build` reported 178 errors on the same source, all in the
region checker. This is the same parity gap as the three clients above, at a scale that made it the
capability's dominant implementation cost: the workaround was to move nine callees into the calling
module unchanged, and the *other* half of the finding — that the refusals are cross-module only —
is filed separately as Request 49. Request 42's own acceptance criteria are unchanged by it; it is
recorded here because a request with four clients and a 413-versus-178 measurement is a different
priority from one with three.

### Requested capability

Make `alignc check` (and, if it remains a distinct verb, `alignc check-per-unit`) run the same
region/borrow-checking pass `alignc build` runs, so that a program rejected by `build` for a
region-checker reason is also rejected by `check` — or, if the two verbs are deliberately allowed to
diverge for performance reasons, document the exact diagnostic classes `check` defers to `build` so
a caller can decide whether a clean `check` is sufficient evidence for its purpose.

### Acceptance criteria

1. A compiler test pins a program that `alignc build` rejects with an invalidated-borrow or
   return-provenance region-checker diagnostic and asserts `alignc check` rejects it with an
   equivalent diagnostic (same diagnostic family, not necessarily identical wording).
2. A compiler test pins the same requirement for `alignc check-per-unit`.
3. `align-llm` verification: `make check` on `src/gpu_forward.align` and `src/model_forward.align`
   with a seeded region error matching the C5 shape (a `borrow mut` out-parameter read after a
   sibling is reassigned, across a module boundary) fails identically to `make build`, instead of
   passing clean.

---

## Request 43 — Cross-module `borrow mut` record out-parameters

```text
Status: PROPOSED
Priority: medium
Blocking: no
Blocked gate or slice: none. `model_forward.render_parts` (`src/model_forward.align:3226-3253`)
  ships as the shape all three refusals in section 6 correction C5 allow; R5C's originally planned
  module split, where `src/gpu_forward.align` would call `src/model_forward.align`'s `execute`
  directly and read its four `borrow mut` column-set out-parameters itself, collapsed into
  `render_parts` returning rendered `string`s instead.
Independent work that may continue: all of R5C-METAL-PREFILL-ARM.
Resume condition: an Align release admits a caller in one module to read a `borrow mut` record
  out-parameter filled by a callee in a different module, without the checker merging that
  out-parameter's validity to an unrelated sibling out-parameter's later reassignment.
Align commit or pull request: none
align-llm verification: restore the module split R5C originally planned —
  `src/gpu_forward.align` calling `src/model_forward.align`'s `execute` directly and reading
  `TokenColumns`/`ScheduleColumns`/`GraphColumns`/`TopColumns` itself instead of going through
  `render_parts` — and pass `make layer-forward-smoke`.
```

### Motivation and current sibling evidence

R5C-METAL-PREFILL-ARM's plan put the `--model-forward-gpu` arm in its own module
(`src/gpu_forward.align`) calling `src/model_forward.align`'s existing `execute`, which reports its
work through four `borrow mut` record out-parameters (`TokenColumns`, `ScheduleColumns`,
`GraphColumns`, `TopColumns`; the signature is `src/model_forward.align:2963-2977`). Section 6
correction C5 (`docs/specs/r5c-metal-prefill.md:1296-1330`) records that this does not compile as
written, and names three separately refused forms:

1. **Reading the out-parameters directly**, as the plan wrote it: `alignc build` reports `use of
   invalidated borrow 'schedule': its source 'tokens' was moved or reassigned (or its storage was
   reallocated)` at the caller's read, even though the identical call-then-read sequence inside
   `src/model_forward.align` itself (the same module that owns `execute`) both checks and builds —
   C5's own words: "The identical sequence inside `src/model_forward.align` checks *and builds*,
   which is why R5B never met it." Request 42, filed alongside this one, records that `alignc check`
   also missed this in the real module split (only `build` caught it).
2. **Returning the four owners bundled inside one record instead**, refused for a second, different
   reason: `cannot return a view that borrows local storage` — the checker treats the caller's own
   local (the one the four builders write into inside `stage_geometry`/`schedule_model`) as a view
   over storage local to those functions, and only a `Bundle` carrying `Outcome` alone (no column
   set) builds.
3. **Assembling the return record field by field** instead of in one literal, refused by a third,
   unrelated diagnostic: `field replacement of model_forward$Outcome is not supported yet (owned
   field replacement currently supports only string and Option<string> leaves)` — this is Request
   36's already-registered gap (owned `array<T>` field replacement), re-encountered here from a third
   angle rather than a new one.

**Consequence for the client.** All three obvious shapes for handing four filled-in-a-callee
records back across a module boundary are refused, each for a different reason. The shape that
compiles is the one C5 names as shipped: `model_forward.render_parts`
(`src/model_forward.align:3226-3253`) calls `execute` and renders each column set to a `string`
*inside the module that owns the data*, returning a `Parts` record whose fields are the already-
rendered `head`, `schedule`, `graph`, and `output` strings (plus `outcome` and `token_list`) rather
than the typed column-set records themselves:

```text
pub fn render_parts(
  pack_path: str, geometry_path: str, tokens_text: str, width_text: str, width_declared: bool,
  reference_path: str, transcript_path: str, logits_path: str,
  borrow selection: DeviceSelection, schedule_suffix: str,
) -> Parts {
  mut tokens := empty_tokens()
  mut schedule := empty_schedule()
  mut graphs := empty_graphs()
  mut top := empty_top()
  outcome := execute(
    pack_path, geometry_path, tokens_text, width_text, width_declared, reference_path,
    transcript_path, logits_path, selection, tokens, schedule, graphs, top)
  return Parts {
    outcome: outcome,
    head: render_head(outcome, tokens),
    schedule: render_schedule_with(schedule, schedule_suffix),
    graph: render_graph_object(outcome, graphs),
    output: render_output(outcome, top),
    token_list: render_token_list(tokens),
  }
}
```

`src/gpu_forward.align:501-521` calls `render_parts` and works only with `parts.outcome` (a plain
`Outcome`, unaffected by this gap) and the pre-rendered `string`s, never with the typed column-set
records `execute` produces. The GPU document's three extra per-layer field names travel back into
`model_forward` as a `schedule_suffix: str` parameter instead (`src/gpu_forward.align:94-...`,
`schedule_suffix()`), so the field list the `R5_MODEL_FORWARD_GPU` document needs stays owned by the
module that defines that document, and `--model-forward` is unchanged, still calling `execute`
directly within the same module. This is architecturally load-bearing, not a preference: the planned
module split (a `gpu_forward` that computes nothing and delegates every column set to
`model_forward`, reading the typed records itself to build its own device-specific document) is
unavailable at this pin, and `render_parts` returning strings is the substitute R5C shipped instead.

### Requested capability

Admit a caller in one module to read the fields of a `borrow mut` record out-parameter after the
callee (in the same or a different module) has filled it, without the checker's validity tracking
merging that out-parameter to an unrelated sibling out-parameter of the same call that was
separately reassigned — the cross-module case of the region behavior that already works when caller
and callee share a module. This does not require solving Request 36 (in-place field replacement) or
Request 34 (`Result` payloads beyond scalars); it is specifically about a caller's read access to an
already-filled `borrow mut` out-parameter surviving a call whose *other* out-parameters were
reassigned, once that call crosses a module boundary.

### Acceptance criteria

1. A compiler test declares a callee in module A taking two or more `borrow mut record` parameters,
   reassigning each with a whole-struct literal; a caller in module B invokes it with two owned
   locals and reads every out-parameter's fields after the call returns. The program checks and
   builds.
2. The same test, run with caller and callee merged into one module (the working case today),
   continues to check and build unchanged, confirming the fix is additive to the cross-module case
   and does not change the single-module behavior R5B already relies on.
3. `align-llm` verification: restore the originally planned module split —
   `src/gpu_forward.align` calling `src/model_forward.align`'s `execute` directly and reading
   `TokenColumns`/`ScheduleColumns`/`GraphColumns`/`TopColumns` itself instead of routing through
   `render_parts`'s rendered strings — and pass `make layer-forward-smoke`.

---

## Request 44 — compiler: array-to-slice view retype through a borrowed sum projection

```text
Status: ALIGN_LLM_VERIFIED
Priority: high
Blocking: yes
Blocked gate or slice: C8-OPTIONAL-TARGETED-STAGE verification task/result schema 2
Independent work that may continue: every Track B capability and align-coder work unrelated to the optional verification stage
Resume condition: align-llm adopts an Align revision containing merge 3a34febe912db5096c58c74fede36ff53f223e04 and the complete optional-target owner passes at the managed pin
Align commit or pull request: Align PR #892, merged as 3a34febe912db5096c58c74fede36ff53f223e04
align-llm verification: `.align-revision` selects 3a34febe912db5096c58c74fede36ff53f223e04; the managed compiler verifies at that identity; whole/per-unit compilation and the schema-v2 Some/absent/null, validation, cleanup, repair, and failure-memory owner pass; the 101-pair fixed-task comparison improves 60,515,456 ns to 40,475,113 ns (331,160 ppm) while projecting only schema 1→2 and the passing targeted-stage removal
```

### Reconciliation and shipped response

The request was first filed as Request 21 on the unmerged local branch
`agent/c8-optional-targeted-test`. Current `main` independently assigned Request 21 to
`std.fs.open_ro`, so this register records the shipped compiler prerequisite under the next
non-colliding identifier. Align's plan and PR retain their historical Request 21 wording; Request 44
is the align-llm-side reconciliation identity for the same compiler defect, not a second compiler
request.

C8 makes the verification loop's `targeted_test` command optional while retaining `full_test` as
the complete acceptance owner. The schema decodes an arena-owned `VerificationTask` whose optional
command and required sibling commands contain dynamic argument arrays. A borrowed helper matches
the optional payload and passes those arrays as slices without moving, cloning, or replacing the
decoded owner.

At the pinned Align revision `4b515f8d37de2e9a9ba06170c5842fd12dc1cba2`, `make check` accepted
that source but `make build` rejected `verification_loop` while lowering the borrowed field path:

```text
alignc: codegen failed for unit 'verification_loop': lowering failed: borrowed place type disagrees with its field path
```

Align PR #892 repairs that cross-stage type-identity gap. Path replay first recovers the owning
array type, then admits only the existing layout-identical scalar or AoS array-to-slice view with
canonical element identity. The owner remains live; the view creates no clone, source nulling,
replacement, allocation, or cleanup. The merged Align owner covers scalar and AoS arrays under
`Some`, the `None` arm, sibling fields, repeated use, whole/per-unit execution, source survival, and
a mismatched-element malformed-MIR rejection before pointer construction.

Replaying the align-llm prototype in a temporary worktree with a sibling compiler containing
`3a34febe` makes both `make check` and `make build` pass. The remaining client work is intentionally
not inferred from that compiler proof: `.align-revision` adoption, exact schema-v2 Some/absent/null
task vectors, Some/None/Invalid result vectors, validation and cleanup owners, failure-memory
admission, user documentation, and the paired performance comparison all belong to the active
consumer capability in `docs/specs/c8-optional-targeted-stage.md`.

### Acceptance criteria

1. `.align-revision` selects a shipped Align revision containing `3a34febe`, and the managed
   compiler/runtime materialize and verify at that exact identity.
2. The schema-v2 real client checks, builds, and executes with both present and absent/null
   `targeted_test`; present runs build/target/full and absent/null runs build/full while sibling
   commands and dynamic argv remain reusable from the decoded arena.
3. `make verify-loop-smoke` and `make failure-memory-smoke` pass the complete ledger and closure
   matrix in `docs/specs/c8-optional-targeted-stage.md`.
4. The paired fixed-task comparison proves that the full command executes the targeted assertion,
   preserves every undeclared semantic field, and repeatably exceeds the C8 2,000 ppm shipping
   floor. This measurement owns the performance claim; the pin change alone does not.

---

## Request 45 — Compiler soundness: moving a field out of a decoded record double-frees at run time

```text
Status: PROPOSED
Priority: high
Blocking: no
Blocked gate or slice: none. R3-RESIDENCY-SIM (`docs/specs/r3-residency-sim.md` section 7.5 item 3)
  ships on a one-line `.clone()` through a `str` view rather than the move the region checker
  silently accepted.
Independent work that may continue: all of R3-RESIDENCY-SIM.
Resume condition: an Align release either rejects the move at check time with a named diagnostic
  (the same family Request 36 already gets for a whole nested Move-struct field), or makes codegen
  correctly transfer ownership of the moved-out field so the source record's recursive `Drop` no
  longer frees it a second time.
Align commit or pull request: none
align-llm verification: remove the `.clone()` at `src/residency_sim.align:624-634` (move
  `document.run.build_source` directly into `TraceLoad.build_source`) and pass
  `make residency-sim-smoke` without the process aborting.
```

### Motivation and current sibling evidence

R3-RESIDENCY-SIM's trace decoder needs one owned `string` field, `TraceRunSection.build_source`, out
of a `json.decode`d `TraceDocument`. The straightforward move —
`build_source: document.run.build_source` inside a new record literal — compiles cleanly under both
`alignc check` and `alignc build`, runs, prints the moved string correctly, and then aborts the
process when the decoded document is dropped. `docs/specs/r3-residency-sim.md` section 7.5 item 3
records it directly in-repo: "`build_source: document.run.build_source` compiles cleanly and then
aborts the process at `free` with 'pointer being freed was not allocated' when the decoded
`TraceDocument` is dropped — SIGABRT, no message, and, because stdout is block-buffered, no output at
all, so the failure looks like a hang at whatever the last flushed byte was. The fix is one
`.clone()` through a `str` view. A partial move out of a record is either supported or rejected;
being accepted by the checker and unsound at run time is the part worth recording."
`src/residency_sim.align:624-634` carries the shipped workaround: `source_view: str :=
document.run.build_source` followed by `build_source: source_view.clone()`, with the comment "The
decoded document owns `run.build_source`; moving the field out of it would leave the record's drop
to free a string this result also owns, so the view is cloned."

**Reproduced fresh** against the pinned managed compiler (`4b515f8d37de2e9a9ba06170c5842fd12dc1cba2`,
`alignc 0.5.0`) with a minimal two-hop field-access probe in a scratch directory:

```align
module probe
import core.json

Run { build_source: string }
Doc { run: Run }
Out { build_source: string }

fn load(s: str) -> Result<Doc, Error> {
  d: Doc := json.decode(s)?
  return Ok(d)
}

fn main() -> Result<(), Error> {
  document := load("{\"run\":{\"build_source\":\"abcdefghijklmnopqrstuvwxyz0123456789\"}}")?
  out := Out { build_source: document.run.build_source }
  print(out.build_source)
  return Ok(())
}
```

```text
$ alignc check probe.align
ok: checked 2 function(s)

$ alignc build probe.align -o probe
alignc: built executable: probe

$ ./probe
abcdefghijklmnopqrstuvwxyz0123456789
[1]    68974 trace trap  ./probe
```

Exit status 133 (signal 5, `SIGTRAP`), not the classic `SIGABRT` (134): macOS's `xzone` `libmalloc`
raises the corruption trap through `__builtin_trap`, not `abort()`, for this class of failure. Under
`lldb`, the trap decodes to a genuine heap-corruption assertion, not a benign breakpoint — verbatim:

```text
* thread #1, stop reason = EXC_BREAKPOINT (code=1, subcode=0x184584fd4)
    frame #0: libsystem_malloc.dylib`mfm_free.cold.4 + 36
libsystem_malloc.dylib`mfm_free.cold.4:
->  brk    #0x1
libsystem_malloc.dylib`_xzm_introspect_map_zone_and_main.cold.1:
    "BUG IN LIBMALLOC: malloc assertion "main_address" failed
     (.../libmalloc/src/xzone_malloc/xzone_introspect.c:838)"
```

Restoring the one-line `.clone()` (`view: str := document.run.build_source; out := Out {
build_source: view.clone() }`) on the identical program runs to exit `0` with no crash, confirming
the clone is what the shipped file relies on rather than an unrelated variable.

**Root cause, verified in the sibling checkout at the pinned commit.** The move checker's
`ExprKind::Field` handling (`crates/align_sema/src/lib.rs:38581`) branches on field-access depth.
The single-hop case (`path.len() == 1`, e.g. `document.build_source`) records a move —
`moved.insert(MovedKey::Field(*base, fld))` — for a `string`/`Option`/handle/Move-enum leaf when
`consuming` is true (`:38587-38634`), and separately rejects a whole nested Move-**struct** field
outright with "moving a nested struct field out of a struct is not supported yet — clone it, or move
the whole struct" (`:38638-38642`, Request 36's already-registered gap). The **depth ≥ 2** branch
(`:38645-38669`, own comment: "a borrow is fine; the read is invalid only if the root struct was
moved … Moving a field out through a nested path is deferred") only raises its own diagnostic,
"moving an owned field out through a nested path is not supported yet — clone it", when `consuming &&
self.is_move_ty(e.ty)` (`:38663-38668`) — and, critically, only ever *records* a move at depth 1; no
branch at depth ≥ 2 calls `moved.insert(...)` at all, diagnosed or not.

Whether either the diagnostic or the move-recording branch is even reached depends on `consuming`,
and a struct-literal field value never sets it: `ExprKind::StructLit { fields, .. }`
(`:38770-38773`) dispatches every field through `move_expr_deferred!(self, field, moved)`
unconditionally, and `move_expr_deferred!` (`:28040-28046`) calls `expr_deferred_action`
(`:35192-35194`), which calls `self.expr_with_action_mode(e, moved, /* consuming */ false, false,
true)` — `consuming` is hard-coded `false` for every struct-literal field. So
`Out { build_source: document.run.build_source }` reaches the depth-≥2 `ExprKind::Field` arm with
`consuming = false`: neither the deferred-nested-path diagnostic fires (it is gated on `consuming`)
nor is the field ever marked moved. The checker treats the whole two-hop chain as an inert borrow —
which is why `alignc check` reports it clean — while codegen, elsewhere, still copies the field's
owned string pointer into the new struct literal without nulling the source. `document`'s recursive
`Drop` then frees `run.build_source` a second time. No sema regression test anywhere in the
repository names this shape: `grep -rln "nested struct field out of a struct\|nested path is not
supported"` across the whole sibling checkout returns only `align_sema/src/lib.rs` itself, so not
even the sibling depth-1 restriction has a pinned test, let alone this depth-≥2 soundness gap.

**Distinct from the already-registered Request 36.** Request 36 covers the checker *rejecting* a
move of a whole nested Move-typed **struct** field with a named diagnostic — overly conservative, but
sound. This request covers the opposite defect on a *different* shape: a move through a two-hop
field-access chain whose leaf is a scalar-ish `string` (not itself a struct) is *silently accepted*
by both `check` and `build`, and the generated program is unsound. Fixing Request 36's admission gap
would not touch this path (struct-literal fields never set `consuming`, regardless of the leaf's
type), and fixing this defect would not admit Request 36's shape either. Requests 34, 40, and 43 are
unrelated: no `raw`/`buffer` Result payload, `array_builder` struct field, or cross-module
out-parameter is involved in this probe.

**Exact locations, verified in the sibling checkout at the pinned commit
`4b515f8d37de2e9a9ba06170c5842fd12dc1cba2`.** The depth-≥2 field-read handling that this defect
lives in is `crates/align_sema/src/lib.rs:38650-38670`: it blocks a deep read of a moved root, and
it emits "moving an owned field out through a nested path is not supported yet — clone it" when
`consuming && self.is_move_ty(e.ty)` — the branch a struct-literal field initializer never reaches,
because a struct literal's field values are not checked in a consuming context. The neighbouring
diagnostic at `crates/align_sema/src/lib.rs:38644-38648` — "moving a nested struct field out of a
struct is not supported yet — clone it, or move the whole struct" — is Request 36's, and is the
control this request must leave unchanged.

**Second client, from R5D-MOE-LAYER-FORWARD** (`docs/specs/r5d-moe-layer-forward.md` section 5.5,
correction C22). `layer_olmoe.parse_geometry` (`src/layer_olmoe.align:248-410`) decodes an
`R1_MODEL_IR`-shaped geometry document and reads owned fields out of it, which is the same shape as
the R3 client. R5D's mitigation is R3's and it is in the shipped source:
`g.arch = value.clone()` at `src/layer_olmoe.align:269` clones through the `str` view rather than
moving the decoded field out. R5D was written against this register entry as an *anticipated* client
before PR #135 merged it, so the mitigation was in place from the first commit and no run-time
corruption was ever observed in this client. Non-blocking, with all of R5D as independent work.

**Third client, from R5E-MOE-MODEL-PREFILL** (`docs/specs/r5e-moe-model-prefill.md` section 5.5).
R5E reuses `layer_olmoe.parse_geometry` unchanged for the whole-model geometry and therefore
inherits the same shape and the same `str`-view clone; no new mitigation was needed and no run-time
corruption was observed. Non-blocking, with all of R5E as independent work.
control this request must leave unchanged.

### Requested capability

Make the move checker's `consuming` flag (or an equivalent ownership-transfer signal) reach a
struct-literal field's initializer expression, so a depth-≥2 field-access chain used as a moved
struct-literal value is treated the same as any other consuming context: either it records the move
(nulling the source field, matching depth-1 handling) or it is rejected with the existing "moving an
owned field out through a nested path is not supported yet — clone it" diagnostic — never silently
accepted with neither effect. Whichever Align prefers (admit-and-null, or reject) is acceptable to
align-llm; the defect is the silent, unrecorded acceptance, not a preference between the two.

### Acceptance criteria

1. A compiler test constructs a struct literal whose field value is a depth-≥2 field-access chain
   (`a.b.c`, where `c` is an owned `string`) rooted at a `json.decode`d (or otherwise owned) local,
   and asserts one of: (a) the program is rejected at check time with a named diagnostic, or (b) the
   program compiles, and a runtime test asserts no double free occurs (e.g. under an
   allocator-instrumented build) and the source struct's own `Drop` does not re-free the moved field.
2. A negative/positive control pins the existing depth-1 behavior (`n := u.name`) and the existing
   depth-≥2 whole-nested-struct rejection (Request 36) unchanged.
3. `align-llm` verification: the `.clone()` at `src/residency_sim.align:624-634` is removed in favor
   of the direct move, and `make residency-sim-smoke` passes with the process exiting `0` on every
   case (no `SIGTRAP`/`SIGABRT`).

---

## Request 46 — `borrow mut` array locals inside loops, and no element assignment through an array field

```text
Status: PROPOSED
Priority: medium
Blocking: no
Blocked gate or slice: none. R3-RESIDENCY-SIM (`docs/specs/r3-residency-sim.md` section 7.5 item 1)
  ships every helper returning owned columns inside a record instead of writing through
  `borrow mut` out-parameters, and correction 15 (section 6) writes the eviction-and-insert
  admission block twice inside `replay` rather than once in a shared helper.
Independent work that may continue: all of R3-RESIDENCY-SIM.
Resume condition: an Align release admits a `borrow mut array<T>` local passed to a call inside a
  `loop` without invalidating the caller's later reads, and/or admits element assignment through an
  `array<T>` field of a record (`s.field[i] = v`).
Align commit or pull request: none
align-llm verification: `src/residency_sim.align`'s `replay` function (`:660-920`) collapses its two
  copies of the eviction-and-insert block (`:772-812` and `:856-908`) into one shared `admit` helper
  taking the per-key tables as `borrow mut array<i64>` parameters, called from both call sites inside
  the demand loop; pass `make residency-sim-smoke` with the `policy-oracle` case unchanged in
  outcome.
```

### Motivation and current sibling evidence

R3-RESIDENCY-SIM's per-policy cache simulator (`replay`, `src/residency_sim.align:660-920`) needs a
shared "evict-then-insert" admission step called from two places inside one `loop`-driven demand
walk — once on the ordinary demand path (`:856-908`), once on the `topk` prefetch path (`:772-812`).
Factoring it into one helper needs either a `borrow mut array<i64>` parameter per per-key table
(eight tables: `resident_size`, `resident_pos`, `resident_list`, `last_use`, `freq`, `recent_count`,
`next_of`, `prefetched`) called from inside the loop, or an element-assignable `array<i64>` field on
a record bundling them. Both are refused at this pin, for two independent reasons.

**1. A local `array<i64>` passed as `borrow mut` to a call inside a `loop` invalidates every later
read of it in the caller — a record or `buffer` in the same position does not.** Reproduced fresh
against the pinned managed compiler (`4b515f8d37de2e9a9ba06170c5842fd12dc1cba2`, `alignc 0.5.0`) with
a minimal probe in a scratch directory:

```align
fn filled(n: i64, value: i64) -> array<i64> {
  mut b: array_builder<i64> := array_builder()
  mut at := 0
  loop { if at >= n { break }
    b.push(value)
    at = at + 1
  }
  return b.build()
}

fn touch(borrow mut a: array<i64>, k: i64) {
  a[k] = a[k] + 1
}

fn main() -> i32 {
  mut a := filled(4, 0)
  mut i := 0
  loop {
    if i >= 4 { break }
    if a[i] == 0 { touch(a, i) }
    i = i + 1
  }
  return a[0] as i32
}
```

```text
$ alignc check probe_a.align
probe_a.align:23:8: error: use of invalidated borrow 'a': its source 'a' was moved or reassigned (or
                          its storage was reallocated); create a new view from the current source
probe_a.align:26:10: error: use of invalidated borrow 'a': its source 'a' was moved or reassigned
                            (or its storage was reallocated); create a new view from the current
                            source
```

**The transcript above is abridged**: `alignc` prints each diagnostic on one line, and the two
messages are hard-wrapped here for width. The text, the file positions, and the diagnostic count are
verbatim; the line breaks and the continuation indentation are not.

fires on the loop guard's own next read (`a[i]`, line 23), on the call argument (line 23), and on the
read after the loop (`a[0]`, line 26). The identical `touch(a, 0)` call once, outside any loop,
checks clean ("ok: checked 3 function(s)"). `src/alignpack_read.align:335`'s `Counters` (`borrow mut`
of a **record**) and every `borrow mut buffer` call in this repository both survive the same shape
inside a loop, so the gap is specific to `array<T>`.

Root cause, verified in the sibling checkout at the pinned commit: `indexed_backing_type`
(`crates/align_sema/src/lib.rs:15840-15850`) classifies `array<T>` (with `StructArray`/`DynArray`/
`DynStructArray`/`Slice`/`Soa`/`SoaParam`) as a type whose backing storage a call might reallocate,
but does **not** classify a record (`Ty::Struct`) or `buffer` the same way. A `BorrowMut` call
argument only computes a `borrow_mut_replacement_snapshot` — the machinery that treats the call as
potentially replacing the whole backing storage and ends the local's generation — when
`self.indexed_backing_type(destination.ty)` holds (`crates/align_sema/src/lib.rs:22528-22530`), so
only `array<T>`/slice/SoA arguments take this path. The governing doc comment
(`crates/align_sema/src/lib.rs:34273-34275`, on `invalidate_storage`) states the policy directly:
"End every generation `storage` owns — a reallocating mutation invalidates views of the buffer
whatever names it." Inside a `loop`, this per-call generation-end is not scoped to the call's own
continuation; it invalidates the state merged across the loop's back edge, so the guard's next read,
the call argument, and every read after the loop all see an ended generation. A record's `borrow mut`
never enters `indexed_backing_type`, and `buffer` mutation is gated separately, on actual
reflow-causing operations (`put_u8` and similar) rather than on every call — which is why both
survive the identical shape unchanged. No existing regression pins this either way:
`crates/align_driver/tests/borrowed_params.rs` has loop/array cases (lines 651-761), but none repeats
a `borrow mut array<T>` **call** inside a `loop` with reads before and after — an undiscovered gap,
not a documented restriction.

**2. An `array<T>` field of a record cannot be element-assigned at all, independent of the loop
question above.** Reproduced fresh, same pin:

```align
S { table: array<i64> }

fn set(borrow mut s: S, k: i64, v: i64) {
  s.table[k] = v
}
```

```text
$ alignc check probe_b.align
probe_b.align:17:3: error: invalid assignment target
```

Verified in the sibling checkout: `check_place` (`crates/align_sema/src/lib.rs:41376-41377`, doc
comment "Resolve an assignable place: a `mut` local, or `mut_local.field`") recognizes exactly two
assignment-target shapes rooted at a bare local — `local[index] = v` (an `Index` whose receiver
resolves directly to a local via `self.place_local(recv)`, `:41379-41383`) and `local.f0.f1.… = v`
(a `FieldAccess` chain rooted at a local, `:41600-41613`) — with no case composing the two
(`local.field[index] = v`). The one composed shape it does admit is the mirror of this request and
not this request: `local[index].f0.f1.… = v`, the leaf-field store into a struct-array or SoA
**element** (`peel_index_field_chain`, `:41519-41597`), which requires the spine to bottom at an
`Index` of a local and returns `None` for a pure field path. When
the `Index` arm's receiver is itself a `FieldAccess` (`s.table`), `self.place_local(recv)` returns
`None` and the resolver falls straight to `self.diags.error("invalid assignment target", place.span)`
at `:41381`, regardless of whether `s` is a plain local or a `borrow mut` parameter.

**Distinct from the already-registered Request 36.** Request 36 asks for **whole-field
replacement** — assigning an entirely new `array<i64>` to an already-initialized field
(`o.column := new_ids`) — refused only because owned-field replacement is restricted to
`string`/`Option<string>` leaves. This request is about two different things: **element assignment**
through an array field (`s.table[i] = v`), and, separately, **loop-scoped borrow invalidation** of a
plain `array<T>` local. Neither shape reaches Request 36's field-replacement code path at all —
`s.table[k] = v` never replaces the field's array value or its identity, it writes one element of the
array the field already holds, and the assignment-target resolver rejects it (`:41381`) before any
field-replacement rule is ever consulted. Fixing Request 36 would not admit this shape, and fixing
this request would not need Request 36's owned-field-replacement admission either.

**Consequence for the client.** `src/residency_sim.align`'s `replay` function (`:660-920`) cannot
factor its eviction-and-insert step into a helper taking the eight per-key tables as
`borrow mut array<i64>` parameters (gap 1) or as `borrow mut` fields of one bundling record (gap 2).
The admission block is written out twice inside `replay` instead — once for the `topk` prefetch path
(`:772-812`) and once for the ordinary demand path (`:856-908`) — recorded as correction 15 in
`docs/specs/r3-residency-sim.md` section 6 and closed by the `policy-oracle` case, which checks every
`topk_prefetch` cell against an independent oracle whose own admission is one function. Every other
helper in the module (`ReplayResult`, `BudgetSweep`, `IrLoad`, `TraceLoad`, `Verdict`) returns owned
columns inside a record instead of writing through `borrow mut` out-parameters for the same reason
(`docs/specs/r3-residency-sim.md` section 7.5 item 1).

**Second client, from R5D-MOE-LAYER-FORWARD** (`docs/specs/r5d-moe-layer-forward.md` section 5.5,
correction C22), and it hits **both** gaps. `layer_olmoe.decide`
(`src/layer_olmoe.align:1279-1403`) wants a helper taking the per-token id tables as
`borrow mut array<i64>` and called inside the token loop (gap 1), and wants
`routing.compact_ids[t][s] = v` through a record field (gap 2). Neither compiles at this pin, so the
whole routing decision — the union pass, the pairwise-distinct check, the ascending remap, and the
bijection cover — is written inline in one function over `array_builder` locals, and every helper
around it returns owned columns inside a record. That is the same workaround R3 wrote, reached
independently on a different data shape. Non-blocking, with all of R5D as independent work.

**Third client, from R5E-MOE-MODEL-PREFILL** (`docs/specs/r5e-moe-model-prefill.md` section 5.5).
R5E repeats the same two gaps sixteen times rather than once: each layer's routing decision wants a
helper taking that layer's per-token id tables as `borrow mut array<i64>` inside the token loop, and
wants `schedule[L].compact_ids[t][s] = v` through a record field. Neither compiles at this pin, so
every per-layer decision is written inline over `array_builder` locals and every helper around it
returns owned columns. Non-blocking, with all of R5E as independent work.
columns inside a record instead of writing through `borrow mut` out-parameters for the same reason
(`docs/specs/r3-residency-sim.md` section 7.5 item 1).

### Requested capability

Two independent, narrower asks:

1. Either narrow `indexed_backing_type`'s conservative whole-backing-replacement treatment so a
   `borrow mut array<T>` call that never actually reassigns/reallocates the array does not end the
   local's generation on every call, or scope generation-ending to the call's own continuation rather
   than the state merged across a `loop`'s back edge — on the same footing `buffer`'s reflow-gated
   invalidation already gets.
2. Admit `local.field[index] = v` as an assignment target when `field` is an `array<T>` (or
   `slice<T>`) field of a record reachable through `local` (directly or through a `borrow mut`
   parameter), for the same Copy-scalar element set `local[index] = v` already admits.

### Acceptance criteria

1. A compiler test declares `fn touch(borrow mut a: array<i64>, k: i64)` mutating one element, and a
   caller that calls it repeatedly inside a `loop`, then reads the array after the loop: the program
   checks and builds, and the post-loop read observes every mutation.
2. A compiler test declares a record with an `array<i64>` field and a function taking it `borrow mut`
   that assigns one element through the field (`s.table[k] = v`): the program checks and builds, and
   a caller observes the write.
3. A negative control in the same tests: assigning a whole new array to the field (`s.table :=
   new_ids`) is unaffected by either fix and continues to be governed solely by Request 36.
4. `align-llm` verification: `src/residency_sim.align`'s `replay` function collapses its two copies of
   the eviction-and-insert block into one `admit` helper called from both call sites inside the loop;
   `make residency-sim-smoke` passes with the `policy-oracle` case unchanged in outcome.

---

> **Numbering note, resolved at reconciliation.** These two were drafted on
> `agent/r5e-moe-model-prefill` as **46** and **47** while `agent/r3-residency-sim` still held 44 and
> 45 unmerged. R3's pair merged first (PR #135) and then took 45 and 46 when PR #134 claimed 44, so
> the two below are renumbered to **47** and **48**. Nothing outside this register cited either
> number.

## Request 47 — A `Borrow` argument may be a temporary value

```text
Status: PROPOSED
Priority: medium
Blocking: no
Blocked gate or slice: none. R5E-MOE-MODEL-PREFILL ships with the mitigation below throughout
  `src/moe_model_forward.align`.
Independent work that may continue: all of R5E-MOE-MODEL-PREFILL and its successors.
Resume condition: an Align release accepts a call whose `borrow` argument is a slice expression, a
  builder's `build()` result, or an `if`/`match` expression, materializing the temporary for the
  duration of the call.
Align commit or pull request: none
align-llm verification: rewrite `src/moe_model_forward.align`'s window-region and column-set call
  sites to pass the expression directly instead of binding a named local first, and pass
  `make layer-forward-smoke`.
```

R6-OLMOE-DECODE adds `src/moe_decode_step.align` and `gmake moe-decode-step-qualification` as
clients: the new module inherits R5E's mitigation throughout — every window region, every claim
region, and every `str` view bound to a named local on the preceding line. **No status change**,
`Blocking: no`.

### Motivation and current sibling evidence

Every `borrow` argument must name a stable local or a field. Three ordinary expression forms are
refused, each measured at the compiler `4b515f8d` this request was drafted against, on this host.
The slice form was re-measured unchanged at the adopted pin `3a34febe`:

```text
sink(bytes[0..4])           error: the Borrow argument to 'sink' must be a stable named local or
                                   field, not a temporary value
total(b.build())            error: the Borrow argument to 'total' must be a stable named local or
                                   field, not a temporary value
total(if c { x } else { y })  error: the Borrow argument to 'total' must be a stable named local or
                                   field, not a temporary value
```

The diagnostic is `crates/align_sema/src/lib.rs:43694` at `4b515f8d`, inside
`validate_borrow_argument`; the `root` computation immediately above it
(`crates/align_sema/src/lib.rs:43685-43693`) accepts exactly three expression shapes — a local, a
field chain, and a single-element `BorrowedIndex` in `Borrow` mode — and returns `None` for
everything else, a **range** slice expression over such a local included.

**Consequence for the client.** R5E slices two reused windows constantly — every member placement,
every reference fill, every claim plane is a `window[offset..offset + span]` handed to a function
that borrows it. Each one has to be bound to a named local on its own line first, which turns a
one-line call into two lines and, in the loops that place 195 tensors, adds a local whose only
purpose is to satisfy the rule. The same applies to `array_builder.build()` results, which R5E
produces once per column set per graph.

### Requested capability

Accept a temporary as a `borrow` argument by materializing it into a compiler-introduced slot whose
lifetime spans the call, exactly as a named local would. The requested surface is only the
relaxation; the aliasing analysis, the mutation rules, and the refusal of a `borrow` that outlives
its owner are unchanged.

### Acceptance criteria

1. A compiler test passes a slice expression, an `array_builder.build()` result, and an `if`
   expression to a `borrow` parameter; each checks, builds, and runs with the value the named-local
   spelling produces.
2. A negative test confirms the temporary does not outlive the call: returning the borrow, or
   storing it in an outer local, is still refused.
3. `align-llm` verification: `src/moe_model_forward.align`'s window-region call sites drop their
   one-line binding locals and `make layer-forward-smoke` passes.

### Application-side mitigation in use

Bind the expression to a named local on the preceding line and pass the local. This is what
`src/moe_model_forward.align` does at every window slice and every column-set build.

---

## Request 48 — Same-call argument aliasing between a `borrow mut` owner and its own scalar field

```text
Status: PROPOSED
Priority: medium
Blocking: no
Blocked gate or slice: none. R5E-MOE-MODEL-PREFILL ships with the mitigation below.
Independent work that may continue: all of R5E-MOE-MODEL-PREFILL and its successors.
Resume condition: an Align release accepts a call that passes a `Copy` scalar field of a record
  beside a `borrow mut` of that record, on the grounds that the scalar is copied at the call.
Align commit or pull request: none
align-llm verification: pass `plan.n_layer`-style scalars directly beside their owning record's
  `borrow mut` in `src/moe_model_forward.align` instead of copying each to a local first, and pass
  `make layer-forward-smoke`.
```

R6-OLMOE-DECODE adds `src/moe_decode_step.align` and `gmake moe-decode-step-qualification` as
clients, with the same mitigation: `alignment := o.tensor_alignment` and the block alignment copied
to locals before every call that also takes `borrow mut o`. **No status change**, `Blocking: no`.

### Motivation and current sibling evidence

A `Copy` scalar read out of a record is refused when the same record is also passed `borrow mut` in
the same call, measured at `4b515f8d` and re-measured unchanged at the adopted pin `3a34febe`:

```text
Box { n: i64, total: i64 }
fn fill(borrow mut b: Box, width: i64) { b.total = b.total + width }
fill(box, box.n)
error: borrowed argument 1 to 'fill' aliases argument 2, whose mode may invalidate the same owner
```

The diagnostic is `crates/align_sema/src/lib.rs:30504` at `4b515f8d`. The conflict table above it
(`crates/align_sema/src/lib.rs:30478-30493`) makes `(BorrowMut, _)` conflict unconditionally — every
peer mode, `ByValue` included, with a single carve-out for an `ArenaHandle` — and the overlap test
that follows (`crates/align_sema/src/lib.rs:30497-30501`) compares the borrowed argument's place
against each peer's place *and* against the peers' storage roots, which a field read of the same
local shares. `box.n` is an `i64` and is copied at the call, so the exclusive borrow cannot
invalidate anything the callee will read from it.

**The analysis is not uniform, and the second shape is the same root cause seen from the other
side.** The nested form

```text
fn take(borrow mut b: Box, v: i64) { b.total = b.total + v }
fn peek(borrow b: Box, k: i64) -> i64 { return b.n + k }
take(box, peek(box, 1))
```

**compiles** at both pins: the inner read-only borrow of the same owner passed beside the outer
`borrow mut` is accepted (`ok: checked 3 function(s)` at `3a34febe`), while the direct scalar field
read of that owner is not. One of the two
answers is wrong, and the accepted one is the safe one — which is why this is a language-owned
soundness/precision question and not a style preference.

**Consequence for the client.** R5E's staging functions take an out-parameter record `borrow mut`
plus several geometry scalars, many of which live in a record the same call already borrows. Each
one has to be copied to a local first.

### Requested capability

Treat a `Copy`-typed field read as a value, not as a place aliasing its owner, when deciding whether
a call's arguments conflict — or, if the conservative answer is the intended one, extend it to the
nested read-only-borrow form so the two shapes agree and the rule is at least predictable.

### Acceptance criteria

1. A compiler test passes a record's `i64` field beside a `borrow mut` of that record and both
   checks and builds, producing the value the copy-to-a-local spelling produces.
2. A negative test confirms a non-`Copy` field of the same record passed by value beside the
   `borrow mut` is still refused.
3. A test pins whichever answer is chosen for `take(o, peek(o, 1))` so the two shapes cannot drift
   apart again.
4. `align-llm` verification: the scalar-copy locals disappear from `src/moe_model_forward.align`'s
   staging call sites and `make layer-forward-smoke` passes.

### Application-side mitigation in use

Copy the scalar to a local before the call and pass the local.

---

## Request 49 — A cross-module call with a `borrow mut` argument refuses every shorter-lived operand

```text
Status: PROPOSED
Priority: medium
Blocking: no
Blocked gate or slice: none. R6-DECODE-KV-STEP1 ships with `src/decode_step.align` carrying its own
  copies of `fail`/`fault_into`/`take`/`take_pack`/`account`/`top_k`, a compact re-implementation of
  the prefill logits comparison, and a new borrow-free `model_forward.stage_plan_owned` beside the
  `stage_plan` it could not call. `src/model_forward.align`'s existing `pub` surface is otherwise
  intact and `--model-forward`'s goldens are byte-unchanged.
Independent work that may continue: all of R6-DECODE-KV-STEP1, and the second decode step.
Resume condition: an Align release admits a call into another module that takes the caller's own
  `borrow mut` parameter together with an operand rooted in the caller's frame — a string literal, a
  `Result` produced at the call, or a local record — without reporting "cannot retain a
  shorter-lived view through this mutable borrow"; and stops unioning a foreign call's several
  `borrow mut` arguments into one region, so that a later write to one does not invalidate reads of
  another.
Align commit or pull request: none
align-llm verification: delete `src/decode_step.align`'s local `fail`, `fault_into`,
  `pack_fault_into`, `take`, `take_pack`, `account`, `check_types`, `top_k`, and
  `compare_prefill_logits`, **and `src/moe_decode_step.align`'s local `fail`, `fault_into`,
  `pack_fault_into`, `take`, `take_pack`, `account`, `check_balance`, `check_types`, `top_k`,
  `compare_prefill_logits`, `stage_claims`, `read_block_scatter`, `claim_tensors`,
  `graph_identity`, `graph_alignment`, `free_gallocr`, `free_context`, `free_buffer`,
  `teardown_layer`, `oracle_ten_thousandths`, `compare_transcript_rows`,
  `compare_transcript_elements`, and `compare_transcript_sum`**, call the identical functions in
  `src/model_forward.align` and `src/moe_model_forward.align` instead, replace both
  `stage_plan_owned`s with the pre-existing `stage_plan`s, and pass `gmake layer-forward-smoke` with
  **all seven** goldens byte-unchanged.
```

**R6-OLMOE-DECODE is this request's largest client to date.** `src/moe_decode_step.align` carries a
**third** copy of the failure sink and, beyond it, **thirty-six** functions that exist only because
they take `borrow mut Outcome`, `borrow mut buffer`, or `borrow mut Counters` as a **parameter**
rather than as a local. The list is **regenerated from the source** rather than written by hand — the
criterion is "shares a name with a function in `src/moe_model_forward.align`,
`src/moe_layer_forward.align`, `src/decode_step.align`, `src/layer_olmoe.align` or
`src/model_forward.align` **and** takes a `borrow mut` parameter" — and it is 36 of the module's 91
functions:

```text
  `account`, `capture_plane`, `check_balance`, `check_types`, `claim_tensors`,
  `compare_prefill_logits`, `compare_routing_layer`, `compare_transcript_elements`,
  `compare_transcript_rows`, `compare_transcript_sum`, `decode_loop`, `decode_pass`, `execute`,
  `fail`, `fault_into`, `free_buffer`, `free_context`, `free_gallocr`, `graph_alignment`,
  `graph_identity`, `pack_fault_into`, `prefill_pass`, `prefix_step`, `publish`,
  `read_block_scatter`, `reset_step_oracle`, `schedule_decode`, `stage_claims`, `stage_inputs`,
  `stage_past_k`, `stage_past_v`, `take`, `take_pack`, `teardown_layer`, `top_k`,
  `verify_plane`
```

An earlier draft of this block said twenty-three and named a duplicated `refill` that
`src/moe_decode_step.align` does not contain: KV persistence is out of R6-OLMOE-DECODE's scope, so
its plane is never refilled from a container. A future collapse that followed the short list
verbatim would have left thirteen copies behind, which is why the count is now derived and not
remembered. The measured shape is unchanged and was met twice more here:

* `moe_model_forward.read_block_scatter(pak, temp, claim_window, …, starts, sizes, dests, …)` where
  `temp` is the caller's own `borrow mut buffer` **parameter** and `starts`/`sizes`/`dests` are that
  frame's locals is refused with "cannot retain a shorter-lived view through this mutable borrow" —
  and `alignc check` **accepts** it while `alignc build` refuses it, which is Request 42's divergence
  met once more and is how this instance was found;
* `moe_model_forward.stage_plan(pak, g, table, tokens, plan, ends, win, o, counters)` unions its four
  mutable borrows, so `src/moe_decode_step.align` consumes a new `stage_plan_owned` beside it exactly
  as `src/decode_step.align` does.

The cost is measurable rather than rhetorical: of `src/moe_decode_step.align`'s 4,400 lines, roughly
600 are functions that would be one-line calls if either refusal were lifted. **No status change**,
`Blocking: no`, and no compatibility layer is built.

### Motivation and current sibling evidence

R6-DECODE-KV-STEP1 adds a second arm over the whole-model schedule. `src/model_forward.align`
already owns every part it needs — the failure sink, the container reader, the plan, the member
tables, the window discipline, the digests, and the renderers — and the repository's own rule is
that a later arm **imports** an earlier one rather than copying it (`src/model_forward.align`'s own
header: "the R5A arm is imported rather than copied"). Widening those functions to `pub` is
mechanical and changes no behaviour. Calling them from a second module is what does not compile.

Two distinct refusals appear, both only across a module boundary and both absent from the identical
same-module sequence.

**1. A shorter-lived operand beside a `borrow mut` argument.** The failing form is the most ordinary
line in the arm:

```align
fn run_step_graph(/* … */ borrow mut o: model_forward.Outcome) {
  model_forward.take(o, ggml_ffi.slots_init(slot_view, slot_view.len(), "slots"))
```

```text
$ alignc build src/ggml_spike.align
src/decode_step.align:524:25: error: cannot retain a shorter-lived view through this mutable
  borrow; copy it into the destination region first
```

`src/model_forward.align:1951` is that exact line, with `o` a `borrow mut` parameter of its own
`run_graph` and `take` in the same module, and it builds. Moving the two-line body of `take` into
`src/decode_step.align` — same code, same types, same `Outcome` — makes the diagnostic go away. It
is not about what the callee does: `take` clones through `fail`, and the checker cannot see that
across the boundary, so it assumes the `Fault`'s `string` fields could be retained through `o`. The
same refusal fires for `model_forward.fill_members(pak, m, tokens, window, transient, counters)`
when `tokens` is the caller's own `borrow mut` parameter and `transient` is a local, and for
`model_forward.top_k(logits_view, top_index, top_bits)` when all three are locals of the calling
frame. Measured count: **161 of the 178 errors** in the first cross-module draft of
`src/decode_step.align` were this one diagnostic, and every one of them disappeared by moving the
callee into the calling module unchanged.

**R6-KV-PERSIST is the first client for which this gap shapes a module boundary rather than forcing
a copy** (`docs/specs/r6-kv-persist.md` section 2.7). `src/kv_plane.align` owns the `akvp` format —
its constants, header, identity record, region arithmetic, digests, and writer — and every one of
those is expressible with borrowed views and by-value returns, so they cross the boundary freely.
The plane **refill** does not: it must write into `src/decode_step.align`'s own `mut plane: buffer`
alongside that frame's other locals, which is precisely the refused shape. The byte movement
therefore stays with the buffer's owner, the format's authority stays in one module, and no
compatibility layer is built around the gap. **No status change.**

**R6-PREFIX-SUFFIX-PREFILL is a continuing client, and a *negative* one worth recording**
(`docs/specs/r6-prefix-suffix-prefill.md` section 8). It adds a second writer into the same plane —
a multi-column write-back at `n_past = T_prefix` before any decode step runs — and the gap **shaped
nothing**, because the write goes through `capture_plane`, which is already in `src/decode_step.align`
with the buffer, and the pass's eleven scalars travel in `model_forward.Outcome` fields as
`weights`' nine do. It did shape one small thing and the shape is recorded rather than worked
around: `stage_inputs` could not gain a third `borrow mut` out-parameter for the suffix ids beside
the caller's `tokens` and `o`, so the arm re-parses the operand in `execute` with the same total
`parse_tokens` it already calls twice — which is a re-parse of at most 32 decimal ids, not a
compatibility layer. **No status change, no workaround built, and no hypothetical surface
consumed.**

**2. A foreign call unions its `borrow mut` arguments.** `model_forward.stage_plan` reports through
four of them:

```align
window_bytes := model_forward.stage_plan(pak, g, table, tokens.count, plan, ends, o, counters)
```

```text
src/decode_step.align:2026:65: error: use of invalidated borrow 'plan': its source 'o' was moved or
  reassigned (or its storage was reallocated); create a new view from the current source
src/decode_step.align:2026:24: error: value snapshot was invalidated before the enclosing operation:
  owner 'o' was moved, reassigned, or reallocated by a later eager operand
```

`plan` and `o` are two unrelated locals of the caller. After the call the checker treats them as one
owner, so the next ordinary write to `o` invalidates every later read of `plan` —
`build_layer_members(table, plan, probe)` twenty lines down. `src/model_forward.align:3128` makes the
identical call with the identical four locals and builds. This is the same **merging** the R5C
correction behind Request 43 named, met from the other side: Request 43 is about a caller reading a
`borrow mut` out-parameter *after* the call, and this is about the call invalidating an argument the
callee never touched.

**Why this is not Request 43, 42, or 46.** Request 43 asks for one specific read-after-call to be
admitted and its shipped workaround — return the results in one owned record — is exactly what does
*not* help here: the failing operands are **inputs**, and refusal 1 has no out-parameter in it at
all. Request 42 is about `check` missing what `build` catches, which is how both refusals were found
(`alignc check src/decode_step.align` reported `ok: checked 413 function(s)` against a file with 178
build errors) but is not what they are. Request 46 is about `array<T>` locals in loops and element
assignment through an array field; neither shape appears here.

### Proposed surface

No new syntax. Two checker changes:

1. When a foreign call takes a `borrow mut` argument, judge each other operand against that
   argument's own region rather than against the callee's unknown one — or, minimally, treat a
   literal, a call result, and a caller-frame local as admissible operands of a foreign call whose
   signature does not return a view.
2. Keep a foreign call's several `borrow mut` arguments in **separate** regions unless the callee's
   signature can actually alias them (no returned view, no shared lifetime parameter). Today they are
   unioned unconditionally.

### Acceptance criteria

- `src/decode_step.align` calls `model_forward.fail`, `take`, `take_pack`, `account`, `top_k`,
  `compare_logits`, and `stage_plan` directly, with no local re-implementation of any of them, and
  `alignc build src/ggml_spike.align` succeeds.
- `gmake layer-forward-smoke` passes with all five goldens byte-unchanged, which is what makes the
  removal a refactor rather than a behaviour change.
- `alignc check` and `alignc build` agree on every one of the shapes above (Request 42's own
  criterion, restated here because that is how both were discovered).

---

<!-- The next free request number is **53**. R6-PREFIX-SUFFIX-PREFILL proposes none: every gap it
     met is already recorded above (49 as a continuing client, and 22, 41, 35, 31, 21, 30, 29, 38,
     39, 33 inherited unchanged through paths it does not touch). 52 is expected to be claimed by a
     parallel branch; both numbers must be re-checked when this branch merges `origin/main`. -->

## Request 50 — `std.os`: how much physical and available memory the host has

```text
Status: PROPOSED
Priority: medium
Blocking: no
Blocked gate or slice: none. `R6-RESIDENT-WEIGHTS`'s `RESIDENT=weights` operand is opt-in and
  `scripts/run-decode-step` performs the check in shell before the arm is invoked
  (`docs/specs/r6-resident-weights.md` section 3.6, consequence 2).
Independent work that may continue: all of R6-RESIDENT-WEIGHTS, and any later capability that
  reserves a large buffer behind an opt-in operand with a runner-side preflight.
Resume condition: an Align release exposes the host's physical and available memory to a program.
Align commit or pull request: none
align-llm verification: `src/decode_step.align` refuses `RESIDENT=weights` with a
  document-carrying refusal code when the host cannot hold the arena — **no such code exists
  today**; the name `R6_RESIDENT_HOST` is this request's proposal for it and is not a shipped
  surface. The shell preflight in `scripts/run-decode-step` and its `N/A` line are deleted;
  `gmake layer-forward-smoke` and `gmake decode-step-qualification` pass with a new
  forced-low-limit smoke case reaching the new code.
```

### Motivation and current sibling evidence

An Align program cannot ask the host how much memory it has. `R6-RESIDENT-WEIGHTS` reserves one
4,677,533,696-byte `buffer` for the resident weight arena, and the honest consequence on a host that
cannot hold it is **a process abort, not a refusal**: `buffer(cap)` degrades to `cap = 0` without
telling the caller and `append` grows through Rust's infallible, abort-on-OOM path (Request 35).
The arm therefore cannot decide whether to accept `RESIDENT=weights`; only something outside the
program can.

Searched in the sibling checkout at the pinned commit
`3a34febe912db5096c58c74fede36ff53f223e04`:

- `crates/align_stdlib/` exposes no memory inquiry. `std.os` has no `physical_memory`,
  `available_memory`, `total_memory`, or `page_size`; `std.process` runs children and captures
  output; `std.fs` answers questions about files, and `fs.free_space`-style disk inquiry is the
  nearest neighbour and is about a filesystem, not about RAM.
- `docs/language-spec.md`'s standard-library surface lists no host-resource module.
- The workaround an application would otherwise reach for — spawning `sysctl -n hw.memsize` or
  reading `/proc/meminfo` through `std.process`/`std.fs` — is exactly the "second, untested input
  path" `docs/review-checklist.md` warns about, and it makes a memory-safety decision depend on a
  child process's text output. No such workaround is built.

### Proposed surface

```align
module std.os

// Total physical memory installed on the host, in bytes.
pub fn physical_memory() -> Result<i64, Error>

// Memory the host reports as currently available to a new allocation, in bytes. It is a hint by
// nature — it changes between the call and the allocation — and the contract should say so, in the
// same way `fs` free-space answers are hints.
pub fn available_memory() -> Result<i64, Error>
```

Both return `Err` rather than a sentinel on a platform or configuration that cannot answer, so a
caller that must fail closed can, and `i64` rather than `u64` for the reason every other size in the
language is `i64`.

### Acceptance criteria

1. `physical_memory()` returns the host's installed memory on Linux (`/proc/meminfo` `MemTotal`) and
   on macOS (`hw.memsize`), and `Err` on a platform that cannot answer, with a test on each
   supported target.
2. `available_memory()` returns a value no greater than `physical_memory()` on the same host.
3. Neither call allocates a large buffer, spawns a process, or reads a path the caller supplies.
4. A cgroup-constrained Linux container reports the **container's** limit rather than the host's, or
   the contract states plainly that it does not and why.

### What this capability does instead, today

`scripts/run-decode-step` reads `sysctl -n hw.memsize` / `/proc/meminfo` in shell and prints one
explicit `N/A` line naming physical memory below 12 GiB, exiting 0. That is a correct home for the
check — the runner already refuses to start below a disk-space floor in the same shape — and it is
recorded here rather than treated as sufficient, because the refusal a *caller of the arm* deserves
is a document with a code, and the arm cannot produce one.

## Request 51 — A reserved word used as an identifier should say so

```text
Status: PROPOSED
Priority: low
Blocking: no
Blocked gate or slice: none. Every identifier in `R6-RESIDENT-WEIGHTS` is `resident_*`, `pool`, or
  `layout`; the reserved word is the language's prerogative and the code that avoids it is normal
  code, not a workaround.
Independent work that may continue: all of it. This request is about a diagnostic, not a semantic.
Resume condition: an Align release reports a reserved word used in an identifier position by name.
Align commit or pull request: none
align-llm verification: compile the three repros below with the shipped compiler and observe one
  error that names the reserved word and its position, and no cascading top-level errors on later
  lines; no align-llm source changes and no regression of its own, because the subject is the
  compiler's output rather than this repository's behaviour.
```

### Motivation and current sibling evidence

`arena` is a reserved word — `crates/align_lexer/src/lib.rs:675` maps it to `TokKind::Arena`, and
`docs/language-spec.md:314` lists it in the memory section's reserved list, where `arena name {}`
binds a scope-local `region` capability (`docs/language-spec.md:429`). That is the language's
prerogative and is not what this request is about. What it is about is that using one in an
identifier position produces a diagnostic that names neither the word nor, in the binding case, the
right line — and then cascades into unrelated top-level errors that bury the one real cause.

Reproduced at the pinned compiler `3a34febe912db5096c58c74fede36ff53f223e04`; the reserved-word list
is read from the sibling checkout at `4b515f8d37de2e9a9ba06170c5842fd12dc1cba2`. `grep -rn
'reserved word\|is a keyword\|reserved keyword' crates/align_parser/src crates/align_lexer/src`
returns nothing: the compiler has no such diagnostic to emit.

**Repro 1 — a parameter.** The first error is at the right column and says the wrong thing; the two
that follow are consequences and one of them names a line with nothing wrong on it.

```align
fn total(borrow arena: slice<u8>) -> i64 {
  return arena.len()
}

fn main() {
  data: buffer := buffer(8)
  print(total(data.bytes()))
}
```

```text
repro.align:1:17: error: expected ':'
repro.align:1:17: error: expected identifier
repro.align:3:1: error: expected `fn`, a type declaration, or a constant (`NAME := …`) at top level
repro.align:7:9: error: undefined function: 'total'
```

**Repro 2 — a local binding, and the worse case.** The error is reported at the `:=`, one token
**past** the cause, because `arena name {}` is what the parser was expecting; the two cascading
errors then name lines 3 and 4, neither of which contains a defect.

```align
fn main() {
  arena := 3
  print(arena)
}
```

```text
repro.align:2:9: error: expected '{'
repro.align:2:9: error: expected expression
repro.align:3:3: error: expected `fn`, a type declaration, or a constant (`NAME := …`) at top level
repro.align:4:1: error: expected `fn`, a type declaration, or a constant (`NAME := …`) at top level
```

**Repro 3 — the class, not the word.** `unsafe` behaves identically, so this is a property of
reserved words in identifier positions rather than of `arena`:

```align
fn total(borrow unsafe: i64) -> i64 { return unsafe }
```

```text
repro.align:1:17: error: expected ':'
repro.align:1:17: error: expected identifier
repro.align:5:19: error: undefined function: 'total'
```

By contrast `region`, which is a type name rather than a reserved word, is accepted as a parameter
name at the same pin — so the boundary is exactly the lexer's keyword set.

### Proposed surface

No language surface changes. When the lexer produces a keyword token where the parser requires an
identifier, the diagnostic should name the word and say it is reserved, and the parser should
recover at that token so the rest of the file still type-checks. For example:

```text
repro.align:1:17: error: `arena` is a reserved word and cannot be used as an identifier
  note: it introduces a scope-local region (`arena name { … }`); see the memory section of the
        language specification
```

### Acceptance criteria

1. All three repros above produce **one** error each, naming the reserved word and its own position.
2. No cascading top-level error is emitted for a file whose only defect is a reserved-word
   identifier: the parser recovers at that token.
3. The binding form (repro 2) reports at the identifier, not at the following token.
4. A test per repro shape — parameter, local binding, and one more identifier position — in the
   compiler's own diagnostic suite.

### What this capability does instead, today

Nothing, and nothing is needed. `docs/specs/r6-resident-weights.md` section 5.8 records that every
identifier in that capability is `resident_*`, `pool`, or `layout`, and that "arena" survives only
in prose. The request is filed because the diagnostic cost a bounded but real amount of time to
diagnose — the visible errors were on lines that had nothing wrong with them — and the next
implementer to reach for the most natural word for a large contiguous allocation will pay it again.

---

## Request 52 — `match` on an owned record's `Option` field silently moves the payload out, and a later encode drops it

```text
Status: PROPOSED
Priority: high
Blocking: no
Blocked gate or slice: none. C4-REPAIR-MEASURED ships by reading every `Option` member of an owned
  record through a `borrow` binding, never through a `match` on the owned value.
Independent work that may continue: all of C4-REPAIR-MEASURED.
Resume condition: an Align release either rejects a `match` that partially moves a payload out of an
  owned record still live at the match site, or preserves the field so a subsequent
  `json.encode` of that record re-emits it. Either answer closes this; silence does not.
Align commit or pull request: none
align-llm verification: read `PromptTaskRow.attempts`, `repair_loop_count`, and
  `generation_to_passing_patch_ns` through a direct `match` on the owned row in
  `src/prompt_score.align`, re-encode the row with `json.encode`, and require the encoded bytes to
  equal the decoded input's for the frozen `eval/prompt/gate/prompt-evaluation-improved.json` chain.
```

### Motivation and current sibling evidence

C4-REPAIR-MEASURED moves `PROMPT_TASK_ROW` to `schema_version: 2` by adding `Option` members to the
existing record rather than declaring a parallel `PromptTaskRowV2`. That choice depends on one
property: a decoded document must re-encode byte-identically, because
`src/prompt_evaluate.align` decodes the Python evaluator's output and **re-encodes** it to produce
the persisted artifact, and `make prompt-gate-check` verifies the frozen C6 evidence against those
exact bytes.

While implementing the version-2 verifier, reading an `Option` field with

```text
match owned.field { Some(value) => ..., None => ... }
```

on an **owned** record partially moved the payload out of the record with no diagnostic at all. The
record stayed live and usable; a later `json.encode` of it simply omitted that field. Nothing was
reported at compile time and nothing failed at run time — the artifact was just missing a member,
and its `content_sha256` then disagreed with the producer's.

Reading the same field through a `borrow` binding is safe and is what the shipped code does
throughout. The two spellings look interchangeable at the call site and are not.

This is a "nothing hidden" violation rather than a missing feature: the language's own ownership
rules make the move legitimate, but a partial move out of a still-live record that silently changes
what that record serializes to is exactly the class of failure a compiler should refuse. The blast
radius is any Align program that decodes a document, inspects an `Option` member by `match` on the
owned value, and re-encodes — which is the ordinary shape of every artifact rewriter in this
repository.

Either resolution is acceptable and both are better than the current silence: reject the partial
move while the record is still live, or keep the payload in place for a `match` that only inspects.

---

## Not requested (respecting Align's design)

These were considered and deliberately **not** requested, because they conflict with Align's design
or are already implemented:

- **A dynamic "JSON value" type.** Align deliberately requires declared record types and has no
  expression-position type arguments. `core.json` already decodes nested structs,
  `array<Struct>`, existing decode-eligible scalar/`str` and struct `Option` forms
  (missing key / `null` → `None`), enums (shape-directed unions), and ignores unknown fields —
  verified against `examples/json_nested.align`, which decodes an OpenAI chat-completions shape.
  `Option<enum>` remains an existing decode rejection. `Option<Move record>` is admitted by the
  pinned sema/runtime, authoritative JSON design, and positive regression; Request 15 must preserve
  that surface and repair its cleanup. Known cleanup gaps include currently admitted
  optional owners on later object failure, owners overwritten across indexed top-level AoS
  speculation-to-fallback transitions even when fallback succeeds, staged top-level
  `array<MoveStruct>` rows on later failure, and required or currently admitted optional owners on
  trailing-garbage rejection. Request 15 audits and assigns every transition after a decoded owner
  becomes live. `align-llm` should declare provider response structs, not ask Align
  for a dynamic value
  type. (Caveat handled app-side: decoded
  `str` fields are zero-copy views into the input; use `.clone()` to persist them past the input's
  lifetime.)
- **Working directory via app-side shell.** A `sh -c "cd <dir> && ..."` workaround exists, but it is
  fragile (shell quoting, no native exit/stream semantics); native `cwd` is requested in Request 1
  instead of relying on it.
