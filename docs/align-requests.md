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

> **Status (2026-07-25): Requests 1 and 3 are CLOSED; Request 2 is ALIGN_MERGED; Request 4 is PROPOSED.**
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

`json.decode`/`json.encode` recurse through int/float/bool/str, nested structs, `Option<T>`,
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
Resume condition: a pinned Align compiler decodes a valid chunked SSE response and rejects truncated or malformed chunk framing; align-llm's provider stream smoke passes against that wire format
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
and truncation error behavior, and keep response status and headers unchanged. The provider layer
does not need a second streaming transport API; `cl.request` should remain the single HTTP boundary.

### Acceptance / gate

An HTTP fixture sends two SSE chunks and a terminating zero chunk. `provider.stream` returns their
concatenated content for both the OpenAI-compatible and llama.cpp adapters. A missing terminator,
invalid chunk size, or truncated chunk returns `Error.Invalid` and does not produce a partial success.

### Current align-llm evidence

`src/provider_openai.align` and `src/provider_llama.align` implement the adapter-level SSE parser and
pass `make provider-smoke` with Content-Length-framed fixtures. The same fixture must be switched to
chunked framing after Align ships this capability; until then, only the streaming acceptance slice
is paused and the non-streaming provider work remains valid.

## Not requested (respecting Align's design)

These were considered and deliberately **not** requested, because they conflict with Align's design
or are already implemented:

- **A dynamic "JSON value" type.** Align deliberately requires declared record types and has no
  expression-position type arguments. `std.json` already decodes nested structs, `array<Struct>`,
  `Option<T>` (missing key / `null` → `None`), enums (shape-directed unions), and ignores unknown
  fields — verified against `examples/json_nested.align`, which decodes an OpenAI chat-completions
  shape. `align-llm` should declare provider response structs, not ask Align for a dynamic value
  type. (Caveat handled app-side: decoded `str` fields are zero-copy views into the input; use
  `.clone()` to persist them past the input's lifetime.)
- **Working directory via app-side shell.** A `sh -c "cd <dir> && ..."` workaround exists, but it is
  fragile (shell quoting, no native exit/stream semantics); native `cwd` is requested in Request 1
  instead of relying on it.
