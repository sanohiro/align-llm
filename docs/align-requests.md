# Align language/stdlib requests from align-llm

This document records capabilities that the **Align language and standard library** need,
discovered by building `align-llm` (a local LLM coding system) as a real client. It is the
register that `AGENTS.md` requires ("If this project needs missing Align functionality, document
the dependency clearly").

**How to use this document.** `align-llm` is a *driver*: its purpose is to surface genuine Align
needs, not to force-build around them. Each request below is meant to be implemented **in the
Align repository** (`../align`), in Align's own design discipline (author a design spec under
`docs/impl/std-design/`, then implement + test), and can be handed directly to Align's own tooling.
`align-llm` does not work around these; it waits for the Align capability and then exercises it as a
real client.

Verified against the `../align` compiler on 2026-07-24. File paths are stable references; line
numbers are approximate and may drift — locate by function name.

## Request protocol

Every new or reopened request must begin with this metadata:

```text
Status: PROPOSED | ACCEPTED | IMPLEMENTING | ALIGN_MERGED | ALIGN_LLM_VERIFIED | CLOSED
Priority: critical | high | medium | low
Blocking: yes | no
Blocked gate or slice: <roadmap gate/slice, or "none">
Independent work that may continue: <work that does not assume the requested surface>
Resume condition: <observable Align and align-llm gate>
Align commit or pull request: <named commit/PR, or "pending">
align-llm verification: <command/result, or "pending">
```

The lifecycle is:

```text
PROPOSED -> ACCEPTED -> IMPLEMENTING -> ALIGN_MERGED -> ALIGN_LLM_VERIFIED -> CLOSED
```

A blocking request pauses only its dependent gate or slice. Record that pause and its resume
condition in `HANDOFF.md`; continue independent work when it remains valid. Do not implement a
workaround or write code against a proposed surface. A non-blocking request must name its first
expected consumer and becomes blocking if that consumer is reached before `ALIGN_MERGED`.

After Align merges the capability, rebuild its release compiler and runtime, update
`.align-revision`, and run the original acceptance gate through `make ci`. Close the request only
after this file records both Align's response and align-llm's real-client verification.

> **Status (2026-07-28): Requests 1 and 3 are CLOSED; Request 2 is ALIGN_MERGED; Requests 4 and 5 are PROPOSED.**
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
Status: ALIGN_MERGED
Priority: high
Blocking: no
Blocked gate or slice: provider HTTP client acceptance gate (not reached yet)
Independent work that may continue: C0 evaluation and provider-independent loop work
Resume condition: plaintext and TLS timeout gates pass in align-llm
Align commit or pull request: #633 98b1712, #634 1b21cdb
align-llm verification: pending plaintext and TLS timeout fixtures in the provider HTTP client
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

### align-llm verification status

The Align capability is merged and pinned, but align-llm does not yet have the provider HTTP client
that consumes it. Therefore this request remains `ALIGN_MERGED`, is non-blocking for the current C0
and provider-independent loop work, and must not advance to `ALIGN_LLM_VERIFIED` or `CLOSED` until
`make ci` runs both the plaintext and TLS timeout fixtures named in the original acceptance gate.

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
Status: PROPOSED
Priority: high
Blocking: yes
Blocked gate or slice: C1 streaming provider acceptance
Independent work that may continue: non-streaming provider calls, token counting, common result persistence, C2 preparation
Resume condition: after ALIGN_MERGED, a pinned Align compiler decodes valid chunked SSE and rejects truncated or malformed framing, and align-llm's provider stream smoke passes; if Request 5 reached ALIGN_MERGED first, the Request 4 adoption slice must pass the combined bodyless/chunk-cap/trailer-guard/aggregate-storage gate; if both capabilities ship together, Request 5's bounded-response adoption owns that gate; this request cannot reach ALIGN_LLM_VERIFIED until the applicable gate passes
Align commit or pull request: pending
align-llm verification: pending
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
slice owns the combined gate; neither request may reach `ALIGN_LLM_VERIFIED` until that slice names
the joint delivery and records the combined verification.

### Current align-llm evidence

`src/provider_openai.align` and `src/provider_llama.align` implement the adapter-level SSE parser and
pass `make provider-smoke` with Content-Length-framed fixtures. The same fixture must be switched to
chunked framing after Align ships this capability; until then, only the streaming acceptance slice
is paused and the non-streaming provider work remains valid.

---

## Request 5 — `std.http`: bounded client response bodies

```text
Status: PROPOSED
Priority: high
Blocking: yes
Blocked gate or slice: C6 provider-proposal slice and real-provider prompt-optimizer gate
Independent work that may continue: C6 artifacts, renderer, pure scorer, activation lifecycle, and deterministic A/B evaluator
Resume condition: after ALIGN_MERGED, a separate bounded-response adoption slice pins the shipped Align release, integrates the cap at provider_http, and proves the exact shipped limit discriminant, no returned body, clean connection teardown, and make ci; if Request 4 reached ALIGN_MERGED first or both capabilities ship together, that slice also owns and must pass the combined bodyless/chunk-cap/trailer-guard/aggregate-storage gate before Request 5 reaches ALIGN_LLM_VERIFIED, and for a joint delivery neither request may reach ALIGN_LLM_VERIFIED first; only then does the C6 provider-proposal slice resume
Align commit or pull request: pending
align-llm verification: pending
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
- once Request 4's method/status-aware framing is available, compose it with the cap as follows:
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

When Request 4 adds chunk de-framing, the formula remains a combined receive-buffer ceiling, not
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
is sufficient for the first real consumer and composes with Request 4's future chunk de-framing.

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
4. once Request 4's method/status-aware framing exists, accepts `HEAD` and `304` responses that
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
5. once Request 4 exists, same-read and split-read fixtures send one or more non-`101`
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
13. after Request 4 ships, accepts an exact-cap de-framed chunked response, including its terminating
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
Status: PROPOSED
Priority: high
Blocking: no
Blocked gate or slice: N/A; current align-llm product code and planned C6 artifacts do not consume json.scan
Independent work that may continue: all current C6 design, prerequisite, and implementation work that explicitly excludes json.scan
Resume condition: N/A for current work; the named adoption consumer starts only after ALIGN_MERGED, pins the release, and closes the request; if a product consumer is scheduled before ALIGN_MERGED, reclassify this request as blocking for that consumer
Align commit or pull request: pending
align-llm verification: pending
```

The first expected consumer is the concrete align-llm adoption target specified below. It starts
only after this request is `ALIGN_MERGED`, runs the positive Copy-row aggregate plus the exact
fail-closed Move-row negatives, and pins the shipped compiler before closing the request. No
align-llm product consumer is currently planned. If the roadmap later schedules one before
`ALIGN_MERGED`, reclassify this request as blocking for that consumer; a consumer that actually
needs a Move row belongs exclusively to a separate per-row ownership request and is not a consumer
of this rejection capability.

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
gate and is outside this request. An otherwise decode-eligible `Option<Move record>` is already
supported by ordinary `json.decode`/`json.encode`, including successful construction and owner
drop. One demonstrated error-path defect remains: after decoding a `Some(MoveStruct)`, any
subsequent enclosing-object decode failure leaves the optional payload unfreed because
`drop_decoded_owned` skips optional descriptors. Missing or type-invalid siblings, duplicate
declared keys, and malformed later object content are all instances of that root-cause class.
Additional decoded-owner gaps exist outside error exits. Indexed top-level AoS speculation can
write an owner, then fall back and overwrite it on either a successful or failed fallback.
Top-level `array<MoveStruct>` decode also fails to clean the current or completed staged rows after
malformed later elements or trailing garbage, unlike the nested field-array path's explicit partial
cleanup.
Top-level single-record trailing-garbage rejection separately leaves required or optional decoded
owners live. These are known examples, not an exhaustive cleanup inventory, and are outside this
scanner-only request. Their follow-up design must audit every transition after any decoded owner
becomes live: construction, speculative write, replacement/source nulling, fallback success and
failure, staging, return, and cleanup. It must either own every affected public path or assign each
class to an explicitly named separate request. SoA decoded-owner cleanup is N/A: well-typed
`json.decode` into `soa<T>` admits only primitive or borrowed-`str` columns, and sema rejects an
owned column before runtime. Defensive behavior for a raw runtime call with an invalid owning SoA
descriptor would require a separate invalid-descriptor ABI contract. The current recursive scanner
schema walk admits the optional shape, so the scanner-specific ownership gate must still reject its
reachable owner: each successful scan row would otherwise be overwritten without Drop. The exact
diagnostic template substitutes a public source-level spelling for
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
2. reject an owned array reached through a nested struct, `Option<nested struct>`, a direct object
   union payload, a nested object union payload, and an `array<Struct>` union payload; prove that
   the diagnostic traverses every variant rather than accepting a union because the selected input
   happens to use a Copy variant. A generic fixture declares `Wrap<T> { value: T }`: scanning the
   concrete `Wrap<i64>` monomorph must check and run, while `Wrap<array<i64>>` must fail with the
   exact row spelling `'Wrap<array<i64>>'`, proving ownership is classified after
   monomorphization;
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
8. prove semantic rejection occurs before MIR/codegen for every owning-row fixture in items 1–2:
   `alignc check` and `alignc emit-mir` must both report the scanner-specific semantic diagnostic,
   and `emit-mir` must produce no MIR on stdout. The distinct multi-invalid fixtures in item 7
   retain their earlier capability, schema, or input-type diagnostics and are not ownership
   fixtures for this assertion. No descriptor table, object file, executable, or runtime call may
   be produced for an owning-row rejection;
9. prove the scanner-only boundary by retaining the row declarations as valid types and by
   decoding, encoding, and dropping through ordinary JSON each supported direct, nested, optional,
   and union Move schema that `json.scan` rejects. The optional fixture is exactly
   `Inner { items: array<i64> }` and
   `Row { inner: Option<Inner>, score: i64 }`; decoding
   `{"inner":{"items":[1,2]},"score":3}` and immediately encoding the owner must produce those
   exact bytes before the value leaves scope successfully. This success case is shipped behavior,
   not the subject of a new descriptor request. The distinct decoded-owner transition gaps
   described above remain deferred. Their follow-up must audit every transition after an owner
   becomes live and include allocation-count regressions for successful and failed top-level AoS
   fallback after a speculative owner write, plus malformed-later-element and trailing-garbage
   cleanup for top-level `array<MoveStruct>`. SoA is N/A for these owner regressions because sema
   excludes owned columns;
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

### align-llm adoption gate

After `ALIGN_MERGED`, align-llm owns a separate adoption slice. It release-builds and pins the
shipped Align revision, adds `json-scan-row-ownership-adoption` to the `Makefile`, and includes that
target in `make ci`. The target runs
`scripts/run-json-scan-row-ownership-adoption-smoke` over
`eval/fixtures/json-scan-row-ownership-adoption/`.

The fixture directory contains:

- `copy-row.align`, which scans exactly
  `[{"score":1,"name":"a"},{"score":2,"name":"b"}]`, runs `.score.sum()?`, and must exit zero with
  stdout exactly `3\n` and empty stderr; and
- `owned-direct.align`, `owned-nested.align`, `owned-option.align`, and `owned-union.align`, whose
  top-level scanner type is named `OwnedRow` and which respectively expose
  `items: array<i64>`, a nested `items: array<str>`, an optional nested struct that owns
  `items: array<i64>`, and an owning `Parts(array<Item>)` union variant to `json.scan`; and
- `decode-owned.align`, which decodes the `owned-direct.align` schema through `json.decode`, sums
  the exact input `{"items":[1,2]}`, evaluates
  `print(decoded.items[0] + decoded.items[1])`, and must exit zero with stdout exactly `3\n` and
  empty stderr; and
- `decode-owned-option.align`, which uses
  `Inner { items: array<i64> }` and
  `Row { inner: Option<Inner>, score: i64 }`, decodes
  `{"inner":{"items":[1,2]},"score":3}`, immediately prints `json.encode(decoded)`, then lets the
  owner leave scope. It must exit zero with stdout exactly
  `{"inner":{"items":[1,2]},"score":3}\n` and empty stderr.

For each negative file, the script invokes
`ALIGNC_CACHE=<fresh-cache> <pinned-alignc> check <file>` in that fixed filename order, requires a
nonzero status, requires empty stdout, and matches exactly once:

```text
`json.scan` row type 'OwnedRow' must be Copy; Move rows need per-row Drop before the scanner can reuse its row slot
```

It rejects a panic, backtrace, or any unexpected file under the fresh cache. It then invokes
`<pinned-alignc> run copy-row.align`, `<pinned-alignc> run decode-owned.align`, and
`<pinned-alignc> run decode-owned-option.align` in that order with the same fresh cache and
requires all positive results above. The script removes the validated temporary directory on every
exit. Only this target plus `make ci` may advance Request 6 to `ALIGN_LLM_VERIFIED`.

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
Status: PROPOSED
Priority: high
Blocking: yes
Blocked gate or slice: roadmap C6 Prompt Optimizer canonical declared-artifact encoding; that product slice remains blocked until every separately registered JSON prerequisite is also adopted
Independent work that may continue: C6 design review, Request 5 bounded-response work, other independently demonstrated Align prerequisite requests, and C7 design that does not pre-commit C6 artifacts
Resume condition: after ALIGN_MERGED, a separate JSON-escape adoption slice pins the shipped Align release and passes the exact `make c6-json-escape-adoption` gate defined below plus `make ci`; this closes only the escape prerequisite
Align commit or pull request: pending
align-llm verification: pending
```

Request 7 may be registered and reviewed independently, but it must not advance from `PROPOSED` to
`IMPLEMENTING` until both Request 6 and a separately registered decoded-owner transition cleanup
request reach `ALIGN_MERGED` at distinct named Align commits. Request 6 supplies the recursively
Copy scanner-row boundary on which this request's scanner grammar matrix depends. Strict rejection
of a malformed ignored string and outside-arena rejection of an escaped retained view both add
failure edges after an earlier field may have made an owner live. The cleanup prerequisite must
close those edges for every affected `parse_object` caller and indexed AoS staging path. Joint
delivery is forbidden: the Request 7 implementation branch may be created only from an Align base
that already contains both named merged prerequisite commits. Merge, rebase, or squash integration
is permitted only when the final Request 7 commit retains both prerequisite commits as strict
ancestors.

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
- `json.decode` to SoA already receives an explicit arena; top-level/field union decode has no arena
  parameter; and `json.scan` reuses typed row parsing through an input view with no retained
  storage. Request 6 exclusively owns the scanner row-eligibility defect and proposes a recursively
  Copy boundary. Request 7 neither widens nor duplicates that ownership contract.
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
| Top-level or field shape-directed union with a direct or transitively reachable `str` payload | N/A for materialization: no C6 consumer requires it and the current no-arena union ABI remains; a selected escaped view returns `Error.Code(1)`, including through object/array payload records or a union nested in an arena-backed record | Strict grammar still applies to the complete union input and ignored object members |
| `json.scan` | Row ownership and eligibility are N/A to Request 7 and remain exclusively owned by Request 6. For a row admitted by Request 6's recursively Copy boundary, materialization is also N/A: the scanner owns no arena or stable scratch beyond one row. Any escaped declared view makes the fused terminal return `Error.Code(1)`, including an unprojected, nested, optional, or union-reachable non-owning field | Request 7 applies strict grammar to every key/value in each admitted Copy row under both top-level-array and NDJSON framing |
| Top-level `str` or `array<str>` decode | N/A: both targets remain rejected by the current semantic surface and this request does not add them | No runtime path exists until a separate consumer requests those target types |

Non-string scalar arrays retain their current value semantics, but ignored string keys/values within
their containing document follow the same strict grammar. Encoding already accepts semantic `str`
values and is unchanged.

Required semantics:

- outside an arena, the current zero-copy clean-string path remains valid; a declared returned
  `str` value that needs retained unescaping returns `Error.Code(1)`. The decoded-owner cleanup
  prerequisite must already guarantee that any owner made live by an earlier field is released and
  no partially initialized value is returned;
- on the materializing record/AoS/SoA paths inside an arena, clean strings remain zero-copy input
  views and escaped strings materialize only their decoded UTF-8 bytes in the arena. The matrix's
  union and scanner paths remain `Error.Code(1)` for a recursively reachable escaped declared view
  even when a union is nested in an arena-backed outer record;
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
  enter implementation until its decoded-owner cleanup prerequisite is shipped;
- typed key lookup compares semantic unescaped bytes: a valid escaped spelling of a declared key
  matches that field, a valid escaped unknown key remains ignored, and two raw spellings that
  decode to the same declared key are a duplicate-key error. `json.doc.key(i)` returns the same
  semantic key bytes. Typed key validation/comparison and skipped-value validation share one
  reusable scratch buffer per decode invocation; its logical length is at most the current raw
  string-token length and its capacity is at most the largest raw string token seen, hence no more
  than the already bounded input length. They retain no decoded view, so valid escapes in those
  positions do not require an arena;
- duplicate declared keys, missing required fields, unknown-field ignore, field-order freedom,
  number/type validation, and valid unknown-value skipping retain their current behavior;
- slow and speculative typed-decode paths produce identical semantic values, canonical encodings,
  errors, materialized-string allocation counts, and storage/region classifications. The
  speculative path validates every projected key and value span that can cause fallback before it
  materializes an escaped string. Consequently fallback abandons zero materialized-string arena
  allocations, and every successful path makes exactly one retained arena allocation per escaped
  returned value or escaped `json.doc` key accessor result; temporary scratch growth is not a
  retained allocation. Existing decoded-owner transition gaps remain outside this equivalence
  claim, and Request 7 must not add a new owner-live transition;
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
- the feature does not add a dynamic JSON value type. Ordinary decode, encode, and owner drop for
  an eligible `Option<Move record>` success path are already shipped. Request 7 neither reopens that
  surface nor closes the separately demonstrated decoded-owner transition gaps: an optional owner
  followed by a later enclosing-object failure; an owner overwritten across indexed top-level AoS
  speculation and successful or failed fallback; current or completed top-level
  `array<MoveStruct>` staging followed by later failure or trailing garbage; and required or
  optional owners live when a top-level record rejects trailing garbage. Their follow-up design
  must audit construction, speculative write, replacement and source nulling, fallback, staging,
  return, and cleanup, and must assign every owner-live transition to an explicit owner module and
  allocation-count regression. That follow-up is an implementation prerequisite, not merely an
  excluded future improvement.

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

The implementation closure ledger for the future Align design is:

| Transition | Required owner module / entrypoint | Exact regression owned by the Align design |
| --- | --- | --- |
| Type inference, arena availability, region meet, and construction | `align_sema::check_json_decode`, region/storage-root analysis, and the corresponding `align_mir` JSON decode lowering | `m5::json_escape_typed_region_matrix` |
| Record and nested-record success, outside-arena failure, later sibling failure, return, and cleanup | `align_rt_json_decode`, `parse_object`, shared value writing, and the shipped decoded-owner cleanup prerequisite | `json_escape_record_lifecycle` and `json_escape_record_owner_transition_integration` |
| Top-level and field AoS success plus slow/speculative/fallback string equivalence | `align_rt_json_decode_struct_array`, `json_speculate`, `json_fallback`, `write_field_indexed`, and the shipped decoded-owner cleanup prerequisite | `json_escape_aos_path_equivalence` and `json_escape_aos_owner_transition_integration` |
| SoA count, allocation, fill success/failure, and arena cleanup | `align_rt_json_decode_soa` and the shared indexed writers | `json_escape_soa_path_equivalence` |
| Union and scanner non-materialization, including ignored and malformed string tokens inside valid scanner frames | `align_rt_json_decode_union` and `align_rt_json_scan_next`; Request 6 separately owns scanner row eligibility and scanner framing is unchanged | `json_escape_nonmaterializing_paths` |
| `json.doc` parse, lookup, `as_str`, `key`, malformed input, and arena cleanup | `align_rt_json_doc_parse`, `json_unescape_into`, `align_rt_json_doc_as_str`, and `align_rt_json_doc_key` | `json_doc_strict_string_matrix` |
| Cold/cache-hit whole-program and per-unit compilation plus any internal ABI update | semantic and MIR fingerprints, codegen descriptors, compiler build identity, and every changed JSON runtime declaration | `m5::json_escape_cache_and_abi` |

Clean returned views remain owned by the input; materialized returned bytes are owned by the
explicit arena; array spines retain their existing heap or arena owner; and per-invocation key,
skip, and unescape scratch is temporary runtime-owned storage freed on return. A slow-path failure
after materialization may leave unreachable bytes in the caller's arena until that arena's normal
bulk cleanup, but returns no view and may retain at most one allocation per escaped returned field
encountered before the error. No scratch or decoded view becomes process-global.

Exact logical allocation and precedence observation use a caller-owned, `cfg(test)`-only
`JsonDecodeTestProbe` threaded through internal parser helpers. Production `extern "C"` entrypoints
pass no probe, so this adds no production ABI or ambient state. The probe records the first
validation failure kind and input byte offset, retained-string materialization count and bytes,
peak temporary scratch capacity, speculation attempts, and fallbacks. The arena helper increments
the logical materialization fields exactly where it reserves bytes for one returned escaped
string; fallback tests require those fields to remain zero until fallback validation succeeds.
Each runtime unit test creates its own probe, so concurrent tests have no shared counter, reset
order, lock, or cross-test contamination. Existing heap-allocation instrumentation remains
separate and continues to observe array-spine ownership. Every regression that reads those
process-global heap allocation counters must acquire the existing `ALLOC_COUNT_LOCK` as its first
executable statement, before fixture or descriptor setup and before any allocation. It must hold
the guard through baseline snapshots, decode success or failure, cleanup or `Drop`, final
snapshots, and assertions. Such a regression must not acquire the lock recursively. A test using
only its caller-owned probe needs no lock; if it also reads a heap counter, the whole-body lock
rule applies.

An exact internal arena-passing ABI is N/A while this request is `PROPOSED`: align-llm must not code
against a hypothetical lowering. Before the request can become `ACCEPTED`, Align's authoritative
design must name every changed MIR operand and runtime signature for record, AoS, and SoA
materialization, or explicitly prove why an entrypoint needs no change. A hidden ambient arena is
forbidden. CLI inputs, environment variables, process-global state, connection-global state, and
overlap exclusion are N/A because this parser capability adds none; concurrent invocations retain
only distinct per-call scratch and follow the existing caller-owned arena rules. Persisted scalar
widths, field order, schema version, and tags are unchanged; the existing encoder and the exact
adoption vector below remain the semantic-to-byte and byte-to-semantic sources of truth.

### Acceptance / gate

Align compiler/runtime tests must:

1. round-trip one declared record containing clean text and every supported short escape through
   `decode -> encode -> decode`, and compare the semantic bytes after both decodes;
2. cover a nested record, `Option<str>` in both `Some` and missing/`null` states, and an
   `array<str>` containing clean, escaped, empty, embedded-NUL, and multibyte values;
3. decode `\u0041`, `\u20ac`, and the valid pair `\ud83d\ude00`; reject lone `\ud83d`, lone
   `\ude00`, reversed `\ude00\ud83d`, truncated `\u123`, non-hex `\u12x4`, and a high surrogate
   followed by a non-low-surrogate escape;
4. prove the clean path still points into the input while escaped values point into the explicit
   arena, and prove neither view can escape its owner;
5. reject a typed decode whose returned declared `str` field needs unescaping outside an arena with
   `Error.Code(1)`; with the decoded-owner prerequisite in place, prove no earlier required or
   optional owner leaks and no partially live record is returned. Separately accept escaped
   declared keys and valid escaped ignored values outside an arena because neither retains a
   decoded view;
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
   payloads plus a union field in an arena-backed record, all of which accept clean text but reject
   any selected transitively reachable escaped view as `Error.Code(1)`; top-level-array and NDJSON
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
12. run the existing `bench/json_decode` and `bench/json_soa` escape-free fixtures on the same named
    host with at least 10 alternating baseline/candidate samples, report both medians, and treat a
    candidate slowdown greater than 5% as a failed gate until the design or implementation removes
    it;
13. after the cleanup prerequisite ships, place a required and optional owner before a malformed
    ignored string and before an outside-arena escaped returned field in record and union-payload
    fixtures; place owners in the current and completed rows before the same failures on slow,
    speculative, and fallback top-level AoS rails. The request's caller-owned probes and existing
    heap-allocation instrumentation must prove deterministic failure position, zero leaked owners,
    no returned partial value, and full cleanup on every ordering. Each regression reading the
    existing process-global heap counters must acquire `ALLOC_COUNT_LOCK` as its first executable
    statement and hold it through all setup, snapshots, decode, cleanup or `Drop`, and assertions;
    caller-owned-probe-only regressions remain lock-free.

### align-llm adoption gate

After Request 7 reaches `ALIGN_MERGED` on top of its two named shipped prerequisites, align-llm owns
a separate adoption slice with one immutable observable gate. It release-builds and writes only the
final Request 7 Align commit to the single `.align-revision`; the Request 6 and cleanup lifecycle
entries retain their distinct commits. The adoption slice also checks in
`eval/fixtures/c6-json-escape-adoption/scanner-align-revision` and
`eval/fixtures/c6-json-escape-adoption/cleanup-align-revision`, each containing exactly its
lowercase 40-hex prerequisite commit plus one newline. It adds `c6-json-escape-adoption` to the
`Makefile`, includes that target in `make ci`, and adds it explicitly to the hosted workflow's
fixed supported-target invocation, which does not call `make ci`. Both local and hosted gates must
execute the same adoption script. The gate requires each prerequisite lifecycle entry to equal its
fixture file while Request 7's lifecycle entry equals `.align-revision`.

The hosted CI checkout must make the prerequisite history available without moving the exact
detached Request 7 checkout. Its adoption-slice workflow records `HEAD` and the porcelain worktree
status immediately after the existing pinned checkout, expands a shallow repository with
`git fetch --no-tags --unshallow origin`, and proves that both observations are byte-identical
afterward. If the repository is already complete, it performs no history-changing fetch. The gate
itself runs the existing exact-checkout revision check and then fails closed when
`git rev-parse --is-shallow-repository` is not exactly `false`; it never fetches or changes the
external repository. A regression creates a depth-one detached checkout of the final commit,
proves that the gate fails before history expansion, expands its history, then proves the same
detached `HEAD` and clean worktree pass. This replaces the current hosted workflow's depth-one-only
behavior only in the future adoption slice.

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
    XDG_CONFIG_HOME=/dev/null \
    git "$@"
}

align_scanner_revision="$(tr -d '\n' < eval/fixtures/c6-json-escape-adoption/scanner-align-revision)"
align_cleanup_revision="$(tr -d '\n' < eval/fixtures/c6-json-escape-adoption/cleanup-align-revision)"
align_request7_revision="$(tr -d '\n' < .align-revision)"

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
test "$(clean_git -C "$ALIGN_REPO" cat-file -t "$align_scanner_revision")" = commit
test "$(clean_git -C "$ALIGN_REPO" cat-file -t "$align_cleanup_revision")" = commit
test "$(clean_git -C "$ALIGN_REPO" cat-file -t "$align_request7_revision")" = commit
test "$align_scanner_revision" != "$align_cleanup_revision"
test "$align_scanner_revision" != "$align_request7_revision"
test "$align_cleanup_revision" != "$align_request7_revision"
clean_git -C "$ALIGN_REPO" merge-base --is-ancestor \
  "$align_scanner_revision" \
  "$align_request7_revision"
clean_git -C "$ALIGN_REPO" merge-base --is-ancestor \
  "$align_cleanup_revision" \
  "$align_request7_revision"
```

Before these commands, a bytewise validator requires each file to match
`[0-9a-f]{40}\n` exactly; `tr` is extraction, not validation. Every command must return zero before
any adoption fixture executes. The adoption smoke includes isolated negative copies of this gate
proving rejection of a shallow repository, a symbolic or annotated-tag object, a replacement
object that would forge ancestry, a Git-common-dir `info/grafts` entry that would forge ancestry,
equal prerequisite/final revisions, equal prerequisite revisions, and valid but unrelated commit
objects. The common-dir capture appends a fixed non-newline sentinel before shell command
substitution can discard Git's output terminator, requires exactly one LF immediately before that
sentinel, removes only that exact suffix with shell parameter expansion, and then requires a
non-root absolute path containing no control byte. The negative matrix includes a valid separate
Git common directory whose basename ends in LF and whose `info/grafts` would forge the requested
ancestry; it must be rejected before either ancestry command. Thus command substitution cannot
normalize a malicious path into a different graft-check location. Any existing or symlinked graft
path is also rejected before either ancestry command. The negative repositories and Git
configuration must not affect the caller's repository. A cherry-pick, squash, or joint commit that
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
  the detailed C6 design remains on its separate design branch until its prerequisite register is
  complete.

## Not requested (respecting Align's design)

These were considered and deliberately **not** requested, because they conflict with Align's design
or are already implemented:

- **A dynamic "JSON value" type.** Align deliberately requires declared record types and has no
  expression-position type arguments. `core.json` already decodes nested structs,
  `array<Struct>`, existing decode-eligible scalar/`str` and struct `Option` forms
  (missing key / `null` → `None`), enums (shape-directed unions), and ignores unknown fields —
  verified against `examples/json_nested.align`, which decodes an OpenAI chat-completions shape.
  `Option<enum>` remains an existing decode rejection. Eligible `Option<Move record>` success is
  shipped. Known cleanup gaps include optional owners on later object failure, owners overwritten
  across indexed top-level AoS speculation-to-fallback transitions even when fallback succeeds,
  staged top-level `array<MoveStruct>` rows on later failure, and required or optional owners on
  trailing-garbage rejection. A follow-up design must audit and assign every transition after a
  decoded owner becomes
  live. `align-llm` should declare provider response structs, not ask Align for a dynamic value
  type. (Caveat handled app-side: decoded
  `str` fields are zero-copy views into the input; use `.clone()` to persist them past the input's
  lifetime.)
- **Working directory via app-side shell.** A `sh -c "cd <dir> && ..."` workaround exists, but it is
  fragile (shell quoting, no native exit/stream semantics); native `cwd` is requested in Request 1
  instead of relying on it.
