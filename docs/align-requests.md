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

The next transition away from the currently pinned Align commit
`d9fb5da2b73f6ea649bf17ed9237069ca4baf06e` has one repository-wide prerequisite. A reviewed
`docs/specs/check-gate-topology.md` fresh-compiler design update and its dependent implementation
must both merge before any request changes `.align-revision`, runs verification against a new
compiler, or advances to `ALIGN_LLM_VERIFIED`. This augments every lifecycle entry below, including
older requests whose local resume condition only names their feature-specific adoption gate.

A blocking request pauses only its dependent gate or slice. Record that pause and its resume
condition in `HANDOFF.md`; continue independent work when it remains valid. Do not implement a
workaround or write code against a proposed surface. A non-blocking request must name its first
expected consumer and becomes blocking if that consumer is reached before `ALIGN_MERGED`.

After Align merges the capability, rebuild its release compiler and runtime, update
`.align-revision`, and run the original acceptance gate through `make ci`. Close the request only
after this file records both Align's response and align-llm's real-client verification.

> **Status (2026-08-01): Requests 1 and 3 are CLOSED; Request 2 is ALIGN_MERGED; Requests 4, 5, 6, 7, 8, and 9 are PROPOSED.**
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
Blocking: yes
Blocked gate or slice: Request 7 implementation, whose strict-string grammar matrix exercises Request 6-admitted Copy scanner rows; Request 6 align-llm adoption and every other pin-changing adoption are blocked on the common fresh-compiler topology design and implementation; roadmap C6 remains indirectly blocked behind Request 7
Independent work that may continue: the common check-topology design and implementation, Request 7 registration and review, its separately registered decoded-owner cleanup prerequisite, C6 design, and other work that neither implements Request 7 nor consumes json.scan
Resume condition: Request 7 implementation may start only after Request 6 reaches ALIGN_MERGED at a named commit; after the common check-topology design and implementation merge, the Request 6 adoption consumer may pin that release and must pass before Request 6 closes
Align commit or pull request: pending
align-llm verification: pending
```

The first scheduled dependent slice is Request 7 implementation: its strict-string grammar matrix
uses only rows admitted by this recursively Copy boundary, so Request 6 is now blocking even though
no align-llm product path directly consumes `json.scan`. The first align-llm real-client consumer
remains the concrete adoption target specified below. It starts only after this request is
`ALIGN_MERGED`, runs the positive Copy-row aggregate plus the exact fail-closed Move-row negatives,
and pins the shipped compiler before closing the request. A consumer that actually needs a Move row
belongs exclusively to a separate per-row ownership request and is not a consumer of this
rejection capability.

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
tag and frees the nested owner. That behavior contradicts the authoritative JSON design and its
stale rejection regression, so the decoded-owner prerequisite must either restore rejection before
construction or specify and repair the admitted surface. On the currently admitted path, after
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
inventory, and are outside this scanner-only request. Their follow-up design must audit every
transition after any decoded owner
becomes live: construction, speculative write, replacement/source nulling, fallback success and
failure, staging, return, and cleanup. It must either own every affected public path or assign each
class to an explicitly named separate request. SoA decoded-owner cleanup is N/A: well-typed
`json.decode` into `soa<T>` admits only primitive or borrowed-`str` columns, and sema rejects an
owned column before runtime. Defensive behavior for a raw runtime call with an invalid owning SoA
descriptor would require a separate invalid-descriptor ABI contract. While the current recursive
scanner schema walk admits the optional shape, the scanner-specific ownership gate must still
reject its reachable owner: each successful scan row would otherwise be overwritten without Drop.
If the cleanup prerequisite instead restores general Decode rejection, that earlier schema error
wins and this gate is not reached. The exact diagnostic template substitutes a public source-level
spelling for
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
   variant. For `Option<nested Move struct>`, the Request 6 implementation base freezes one of two
   outcomes: if general Decode still admits it, require this scanner-specific Copy-row diagnostic;
   if an already-merged cleanup prerequisite restored rejection, require that earlier canonical
   schema diagnostic and prove the scanner ownership predicate is not reached. A generic fixture
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
   and `emit-mir` must produce no MIR on stdout. If `Option<nested Move struct>` is already rejected
   by the general schema, apply the same no-MIR assertion to that earlier diagnostic instead. The
   distinct multi-invalid fixtures in item 7 retain their earlier capability, schema, or input-type
   diagnostics and are not ownership fixtures for this assertion. No descriptor table, object
   file, executable, or runtime call may be produced for an owning-row rejection;
9. prove the scanner-only boundary by retaining the row declarations as valid types and by
   decoding, encoding, and dropping through ordinary JSON each supported direct, nested, and union
   Move schema that `json.scan` rejects. If the Request 6 implementation base still admits
   `Option<Move record>`, include the exact optional fixture
   `Inner { items: array<i64> }` and
   `Row { inner: Option<Inner>, score: i64 }`; decoding
   `{"inner":{"items":[1,2]},"score":3}` and immediately encoding the owner must produce those
   exact bytes before the value leaves scope successfully. If an already-merged cleanup
   prerequisite restored rejection, instead prove the same declaration remains a valid Align type
   while ordinary JSON decode receives that prerequisite's canonical schema diagnostic before
   the scanner ownership predicate. The distinct decoded-owner transition gaps described above
   remain deferred.
   Their follow-up must audit every transition after an owner becomes live and include
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

Items 2, 8, and 9 record the optional-schema outcome of the Request 6 implementation candidate.
If a later decoded-owner cleanup changes that outcome, its Align change must update all three
checked-in Request 6 regressions in the same pull request before the cleanup merges: scanner
checking must then expect the cleanup request's canonical schema diagnostic, the no-MIR assertion
must bind to that earlier rejection, and ordinary optional decode must change from success to the
same rejection. If cleanup instead preserves and repairs the admitted schema, those Request 6
expectations remain unchanged. This is test-oracle maintenance for the active compiler, not a
second owner for scanner eligibility.

### align-llm adoption gate

After `ALIGN_MERGED`, align-llm owns a separate adoption slice, but it must not update
`.align-revision`, run a pin-changing verification, or advance this request to
`ALIGN_LLM_VERIFIED` until the common fresh-compiler check-topology design and its dependent
implementation have both merged. That implementation must make canonical `make ci` build and use
the pinned compiler through the reviewed fresh-build, identity, process, timeout, cache, and
cleanup contract; this request must consume that shipped path rather than recreate it. The
adoption then release-builds and pins the shipped Align revision, adds
`json-scan-row-ownership-adoption` to the `Makefile`, and includes that target in `make ci`. The
target runs
`scripts/run-json-scan-row-ownership-adoption-smoke` over
`eval/fixtures/json-scan-row-ownership-adoption/`.

The fixture directory contains:

- `copy-row.align`, which scans exactly
  `[{"score":1,"name":"a"},{"score":2,"name":"b"}]`, runs `.score.sum()?`, and must exit zero with
  stdout exactly `3\n` and empty stderr; and
- `owned-direct.align`, `owned-nested.align`, `owned-option.align`, and `owned-union.align`, whose
  top-level scanner type is named `OwnedRow` and which respectively expose
  `items: array<i64>`, a nested `items: array<str>`, an optional nested struct that owns
  `items: array<i64>`, and an owning `Parts(array<Item>)` union variant to `json.scan`.
  `owned-option.align` expects the scanner-specific diagnostic only when the active pinned compiler
  admits that general Decode schema; otherwise it expects the decoded-owner cleanup request's exact
  canonical schema diagnostic and proves the scanner ownership predicate was not reached; and
- `decode-owned.align`, which decodes the `owned-direct.align` schema through `json.decode`, sums
  the exact input `{"items":[1,2]}`, evaluates
  `print(decoded.items[0] + decoded.items[1])`, and must exit zero with stdout exactly `3\n` and
  empty stderr; and
- `decode-owned-option.align`, which uses
  `Inner { items: array<i64> }` and
  `Row { inner: Option<Inner>, score: i64 }`, decodes
  `{"inner":{"items":[1,2]},"score":3}`. When the active pinned compiler admits that schema, it
  immediately prints `json.encode(decoded)`, then lets the owner leave scope; it must exit zero
  with stdout exactly `{"inner":{"items":[1,2]},"score":3}\n` and empty stderr. When the active
  pinned compiler rejects that schema, the fixture instead expects the decoded-owner cleanup
  request's exact canonical schema diagnostic with empty stdout.

For `owned-direct.align`, `owned-nested.align`, and `owned-union.align`, the script invokes
`ALIGNC_CACHE=<fresh-cache> <pinned-alignc> check <file>` in that fixed filename order, requires a
nonzero status, requires empty stdout, and matches exactly once:

```text
`json.scan` row type 'OwnedRow' must be Copy; Move rows need per-row Drop before the scanner can reuse its row slot
```

It rejects a panic, backtrace, or any unexpected file under the fresh cache. It checks
`owned-option.align` against the outcome selected by the adoption slice that installed the active
`.align-revision`, then invokes `<pinned-alignc> run copy-row.align` and
`<pinned-alignc> run decode-owned.align` in that order with the same fresh cache. It runs
`decode-owned-option.align` only for the admitted outcome; for the rejected outcome it checks the
fixture and exact decoded-owner cleanup diagnostic instead. The initial Request 6 adoption records
the outcome of its active compiler. If a later decoded-owner cleanup changes that outcome, the
align-llm adoption slice that first pins the changed compiler must update both optional-fixture
expectations and this script in the same pull request before `.align-revision` advances. Thus the
persistent `make ci` target never infers current behavior from the immutable Request 6 commit.
The script removes the validated temporary directory on every exit. Only this target plus
`make ci` may advance Request 6 to `ALIGN_LLM_VERIFIED`.

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
Blocked gate or slice: Request 7 acceptance, implementation, and align-llm adoption; roadmap C6 Prompt Optimizer canonical declared-artifact encoding remains blocked until every separately registered JSON prerequisite is also adopted
Independent work that may continue: the separate benchmark-evidence design and implementation, C6 design review, Request 5 bounded-response work, other independently demonstrated Align prerequisite requests, and C7 design that does not pre-commit C6 artifacts
Resume condition: Request 7 may enter ACCEPTED only after the separate benchmark-evidence design is reviewed and merged; it may enter IMPLEMENTING only after Request 6, decoded-owner cleanup, the benchmark-input slice, and that design's dependent enabling implementation reach their named merged states below and a reviewed immutable pre-work baseline is selected under that evidence design; after Request 7 reaches ALIGN_MERGED, the common fresh-compiler check-topology design plus its dependent implementation both merge, and the separate Request 7 topology update adding `c6-json-escape-adoption` merges, align-llm adoption pins the shipped Align release and passes that exact target plus `make ci`; this closes only the escape prerequisite
Align commit or pull request: pending
align-llm verification: pending
```

Request 7 may be registered and reviewed independently, but it remains `PROPOSED` until the
benchmark-evidence design below merges and must not advance to `IMPLEMENTING` until both Request 6
and a separately registered decoded-owner transition cleanup request reach `ALIGN_MERGED` at
distinct named Align commits and the other acceptance-infrastructure conditions below are met.
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
- `json.decode` to SoA already receives an explicit arena; top-level/field union decode has no arena
  parameter; and `json.scan` reuses typed row parsing through an input view with no retained
  storage. Request 6 exclusively owns the scanner row-eligibility defect and proposes a recursively
  Copy boundary. Request 7 neither widens nor duplicates that ownership contract.
- The pinned surface is internally inconsistent for `Option<Move record>`. Sema recursively admits
  the shape, a direct decode/encode fixture successfully produces
  `{"id":1,"meta":{"xs":[2,3]}}`, and ordinary MIR/LLVM `Drop` checks the option tag and frees the
  nested array owner. In contrast, decode-error cleanup in `drop_decoded_owned` skips optional
  descriptors, while `docs/impl/core-design/json.md` and
  `json_option_move_struct_payload_still_rejected` say the shape is rejected; running that exact
  test fails because `check_errs(...)` is false. The decoded-owner prerequisite must reconcile this
  surface before Request 7 implementation: either reject it before construction or specify and
  repair success, failure, replacement, and cleanup ownership. Request 7 does not choose between
  those outcomes.
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
- the feature does not add a dynamic JSON value type. Request 7 neither resolves the contradictory
  `Option<Move record>` surface nor closes the separately demonstrated decoded-owner transition
  gaps: an optional owner followed by a later enclosing-object failure on the currently admitted
  implementation path; an owner overwritten across indexed top-level AoS speculation and
  successful or failed fallback; current or completed top-level `array<MoveStruct>` staging
  followed by later failure or trailing garbage; and required or currently admitted optional
  owners live when a top-level record rejects trailing garbage. The cleanup prerequisite must first
  decide whether `Option<Move record>` is rejected or supported. It must then audit every admitted
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
| Record and nested-record success, outside-arena failure, later sibling failure, return, and cleanup | `align_rt_json_decode`, `parse_object`, shared value writing, and the shipped decoded-owner cleanup prerequisite | `json_escape_record_lifecycle` and `json_escape_record_owner_transition_integration` |
| Top-level and field AoS success plus slow/speculative/fallback string equivalence | `align_rt_json_decode_struct_array`, `json_speculate`, `json_fallback`, `write_field_indexed`, and the shipped decoded-owner cleanup prerequisite | `json_escape_aos_path_equivalence` and `json_escape_aos_owner_transition_integration` |
| SoA count, allocation, fill success/failure, and arena cleanup | `align_rt_json_decode_soa` and the shared indexed writers | `json_escape_soa_path_equivalence` |
| Union and scanner non-materialization, including ignored and malformed string tokens inside valid scanner frames | `align_rt_json_decode_union` and `align_rt_json_scan_next`; Request 6 separately owns scanner row eligibility and scanner framing is unchanged | `json_escape_nonmaterializing_paths` |
| `json.doc` parse, lookup, `as_str`, `key`, malformed input, and arena cleanup | `align_rt_json_doc_parse`, `json_unescape_into`, `align_rt_json_doc_as_str`, and `align_rt_json_doc_key` | `json_doc_strict_string_matrix` |
| Cold/cache-hit whole-program and per-unit compilation plus any internal ABI update | semantic and MIR fingerprints, codegen descriptors, compiler build identity, and every changed JSON runtime declaration | `m5::json_escape_cache_and_abi` |
| Root plus detached benchmark dependency resolution, controller trust, immutable baseline and candidate identity, raw worktree materialization, Git object/config isolation, every Cargo configuration search directory, protected inputs, warm-up, paired samples, parsing, threshold failure, evidence, and integration | DEFERRED to a separately reviewed and merged Align benchmark-evidence design plus its dependent enabling implementation; Request 7 cannot advance to `ACCEPTED` while that contract is undesigned or to `IMPLEMENTING` while its controller and evidence path are uninstalled | that prerequisite plan must name exact unit, fault-injection, workload, report, review, and integration regressions for every closure class in item 12 and its implementation must pass them before baseline selection or Request 7 implementation |
| Minimum Git behavior, not only version parsing | topology-ledger-owned immutable Git 2.45.0 image plus required `git-2.45-compat` job | the complete production adoption gate and all repository/Git negatives under actual `/usr/bin/git` 2.45.0 |
| Canonical revision-file bytes and exact filter-independent tracked/untracked filesystem state before lookup or release build | binary-safe shared revision reader, raw tree/index/worktree enumerator and comparator, `scripts/check-align-revision`, `align-build` prerequisite order, and topology-ledger self-test | exact valid record plus embedded-NUL and other encoding, Git-marker, attribute/filter-hidden modification, assume-unchanged, skip-worktree, ignored and case-fold-hidden build inputs, target-output allowlist, dirty/untracked, and unchanged-index/build-output negatives |
| Fresh compiler construction, input trust and identity, process ownership, use, and cleanup | DEFERRED to a separately reviewed and merged `docs/specs/check-gate-topology.md` design update plus a dependent implementation slice; every pin-changing adoption is blocked because the bootstrap, cache, compiler-exec interposition, process, timeout, and cleanup surfaces are not yet designed or installed | that prerequisite plan must name exact unit, fault-injection, and local/hosted integration regressions for every closure class listed in the adoption gate, and its implementation must pass them before a later adoption changes the pin |

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

An exact internal arena-passing ABI is N/A while this request is `PROPOSED`: align-llm must not code
against a hypothetical lowering. Before the request can become `ACCEPTED`, Align's authoritative
design must name every changed MIR operand and runtime signature for record, AoS, and SoA
materialization, or explicitly prove why an entrypoint needs no change. A hidden ambient arena is
forbidden. CLI inputs, environment variables, process-global state, connection-global state, and
overlap exclusion are N/A because this parser capability adds none; concurrent invocations retain
only distinct fixed-size per-call parser state and follow the existing caller-owned arena rules.
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

    Request 7 must remain `PROPOSED` until a separate Align design slice at
    `docs/impl/core-design/json-escape-benchmark-evidence.md` defines and merges the
    benchmark-evidence boundary. It must remain below `IMPLEMENTING` until that design's own reviewed
    enabling implementation also merges. The prerequisite owns the controller source and delivery,
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
a separate adoption slice with one immutable observable gate. It release-builds and writes only the
final Request 7 Align commit to the single `.align-revision`; the Request 6 and cleanup lifecycle
entries retain their distinct commits. Before implementation, a separate reviewed update to
`docs/specs/check-gate-topology.md` adds `c6-json-escape-adoption` as the final
`HOSTED_CHECK_TARGETS` entry and names its external-history preparation; that design update merges
first. The adoption implementation then updates the `Makefile` list, the
`scripts/check-gate-topology` embedded oracle and self-test, and the hosted workflow through its
canonical `make -j8 hosted-checks` aggregate. It must not append an out-of-band workflow command.
Because `capable-checks` consumes the complete hosted list, `make ci` runs the same target. The
adoption slice also checks in `scripts/check-git-lazy-fetch-version` as the single version-parser
owner used by the hosted history preparation and the focused target, plus
`eval/fixtures/c6-json-escape-adoption/scanner-align-revision` and
`eval/fixtures/c6-json-escape-adoption/cleanup-align-revision`, each containing exactly its
lowercase 40-hex prerequisite commit plus one newline. Both local and hosted aggregates execute the
same adoption script. The gate requires each prerequisite lifecycle entry to equal its fixture file
while Request 7's lifecycle entry equals `.align-revision`.

The hosted CI checkout must make the prerequisite history available without moving the exact
detached Request 7 checkout. Before its first scripted inspection of that checkout, the
adoption-slice workflow runs the checked-in `scripts/check-git-lazy-fetch-version` preflight
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
the current hosted workflow's depth-one-only behavior only in the future adoption slice.

An allowed ordinary root `target/` is treated only as unrelated prior output; no acceptance command
may execute or link an artifact from it. Before the next adoption or verification that changes
`.align-revision`, a separate reviewed design slice must update
`docs/specs/check-gate-topology.md` and merge, followed by a dependent implementation slice that
makes canonical `make ci` consume the reviewed fresh-compiler path and passes its complete local
and hosted acceptance matrix. This is a repository-wide pin-transition prerequisite, not a
Request 7-only helper: Request 6, decoded-owner cleanup, Request 7, and any other request that would
advance the pin or claim `ALIGN_LLM_VERIFIED` against a new compiler must wait for both slices.
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

Four design choices are intentionally unresolved here and block that enabling slice: how a
bootstrap is trusted before it can validate itself; whether additional bootstrap or tool-identity
version probes exist beyond the required Git preflight above and, if so, how their own processes
are owned; how an offline Cargo cache is materialized without nested symlink or rename escape; and
how compiler identity is enforced inside aggregate-internal invocations. Request 7 does not name a
controller, wrapper, environment variable, path, timeout, or PID mechanism ahead of that review.
The topology implementation and every later adoption must consume the merged topology contract
exactly and may not code against a proposed interface.

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
  the detailed C6 design remains on its separate design branch until its prerequisite register is
  complete.

---

## Request 8 — `core.array_builder`: runtime construction of declared-record arrays

```text
Status: PROPOSED
Priority: high
Blocking: yes
Blocked gate or slice: C6f2 deterministic paired evaluator and C6c2 decoded evaluation verifier; Request 8 supplies the recursively Copy, owned-record base needed by Request 10's evaluator extension, and C6c2 cannot adopt its runtime-sized declared-record result arrays until the capability is merged
Independent work that may continue: C6c2 design and other application designs, pure codecs, renderers, scorers, activation slices, Request 5, Request 6, Request 7, and any implementation that does not construct a runtime-sized declared-record array
Resume condition: Request 8 must reach ALIGN_MERGED at a named Align commit before its recursive extension can start; after ALIGN_MERGED at a named Align commit, rebuild both the sibling release compiler and runtime and update `.align-revision` to that exact commit after the common check-topology design and implementation are already merged. The C6f2 consumer runs its named `c6f2-array-builder-adoption` target and `make ci`; the C6c2 enabling consumer independently runs the Request 8 subset of `c6c2-request8-adoption` and `make ci`, which may advance this request for C6c2 without requiring the later C6c2 verifier implementation or Request 10. C6c2 remains blocked on Request 10 until its separate adoption gate passes.
Align commit or pull request: pending
align-llm verification: pending
```

### Motivation

A future data-oriented evaluator may discover result cardinalities while it reads a fixed corpus and
runs paired samples. It must construct arrays of declared records, possibly with nested declared
records, and those arrays must remain ordinary Align values with explicit ownership. They cannot be
replaced by a dynamic JSON value tree or by a private application vector. The first concrete
consumer must name its exact record shapes in a separate design before this request is adopted.

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

The align-llm pin is `d9fb5da2b73f6ea649bf17ed9237069ca4baf06e` (#672), verified in the sibling
Align checkout on 2026-08-01:

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
- `../align/docs/impl/17-library-boundary-prerequisites.md` §7 specifies a future
  `array_builder(out)` for recursively `RegionPlain` records. That planned region form is
  not the current public surface at #672: the pinned compiler's builder constructor accepts no
  argument. It also deliberately excludes dynamic owned arrays, which remain a separate future
  prerequisite when a concrete consumer requires them. Request 8 therefore owns only the missing
  heap-builder record capability for view-free records and must not claim that the planned region
  form has shipped.

This is a language/compiler/runtime ownership gap, not an align-llm application concern. The
requested change must be designed and implemented in Align first; align-llm must not write code
against a proposed constructor or element type.

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
predicate and the canonical `RecordBuilderDescV1` identity described in item 8 are fixed:

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
   shallow-copy a Move record or a view-bearing element. The new record-element builder remains one
   mutable local: it cannot be stored in an aggregate, transferred by-value across a user-function
   boundary, returned, captured, or put in `Option`/`Result`; replacing it drops the old builder
   and resets its builder-local ownership state before installing the new one. It follows Align's
   existing builder contract for `borrow mut`: once Align L2e is available, a helper may borrow the
   bound builder for non-consuming `push`/`append` use and return while the caller retains the same
   owner; `build` remains a consuming operation. The pinned compiler lacks L2e, so direct local
   record-builder use is independent of that upstream prerequisite, while the positive helper
   regression is deferred until L2e ships. This restriction is scoped to the newly admitted
   record/nested shapes and does not revise the upstream borrow contract.
   Existing scalar and owned-`string` builders retain their current boxed return and user-function
   forwarding behavior, including `escaping_array_builder_keeps_boxed_header` and
   `array_builder_crossing_user_call_stays_boxed`.
8. The complete substituted element definition graph participates in interface serialization,
   monomorphization, structural compiler identity, and codegen cache keys through the self-versioned
   `RecordBuilderDescV1` byte sequence:

   ```text
   descriptor := u8 schema_version (= 0x01)
                u8 root_tag (= 0x20, declared record)
                u32 root_size (little-endian, non-zero)
                u32 root_align (little-endian)
                u8 root_allocation_mode (= 0x01, free-standing)
                u8 root_drop_plan_version (= 0x01)
                record_body
   record_body := u32 field_count (little-endian, non-zero), field[field_count]
   field := u32 name_len (little-endian)
            byte[name_len] name_utf8
            u8 type_tag
            type_payload
            u32 layout_size (little-endian)
            u32 layout_align (little-endian)
            u8 allocation_mode
            u8 drop_tag
   type_payload for 0x01 Copy integer := u8 bit_width, u8 signedness (0 or 1)
   type_payload for 0x02 Copy float   := u8 bit_width
   type_payload for 0x03 Copy bool    := empty
   type_payload for 0x04 Copy char    := empty
   type_payload for 0x10 owned string := empty
   type_payload for 0x20 nested record := record_body
   ```

   The only field tags are `0x01` through `0x04`, `0x10`, and `0x20`; integer widths are exactly
   `8`, `16`, `32`, or `64`, float widths are exactly `32` or `64`, and `signedness` is exactly `0`
   or `1`. Names are non-empty ASCII identifiers in source declaration order and are unique. A
   field's `allocation_mode` is `0x00` for Copy scalar fields and `0x01` for `string` or nested
   record fields; its `drop_tag` is `0x00` for Copy scalar fields, `0x01` for `string`, and `0x02`
   for nested records. The root and every nested record must have natural alignment at most 8, no
   explicit `align(N)` or `layout(C)` attribute, and at least one field. The parser rejects a wrong
   schema/root tag, zero root size or field count, count or length overflow, invalid name, duplicate
   or out-of-order field, unknown tag, invalid scalar payload, mismatched layout/allocation/drop tag,
   truncated nested body, or trailing byte before interface or codegen use. Cycles are rejected
   during source type formation; this finite inline descriptor has no graph-reference encoding and
   therefore has no wire-level cycle case. No pointer, local struct ID, source position, or
   declaration hash is part of the identity. A definition edit, field reorder, name/type/layout/
   drop-plan change changes the descriptor; an edit/revert restores it. Whole-program and
   imported/per-unit compilation must make the same decisions, and stale descriptors reject or
   cache-miss before code generation. A golden-byte test covers the complete nested descriptor and
   every malformed boundary, including zero-size/zero-field rejection. No runtime reflection or
   type dictionary is added.
9. The existing future region-builder design remains separate. Request 8 does not make heap
   allocation implicit, does not add `array_builder(out)` prematurely, and does not broaden
   `RegionPlain` or package generic syntax as an incidental implementation shortcut.

The exact acceptance diagnostics may follow Align's naming conventions, but validation order is
deterministic and no builder allocation or push-side effect occurs before it completes:

| Order | Validation |
| --- | --- |
| 1 | Existing parser/import/arity diagnostics and expected-type inference for `array_builder()` |
| 2 | Canonical recursive type formation: unresolved/cyclic definitions, over-alignment, reachable views, unsupported resources/raw/functions/builders, and missing `DropPlan` |
| 3 | Record-builder placement and receiver mode: standalone mutable local, non-capturing/non-aggregate/non-`Option`/non-`Result`; once Align L2e is available, an existing `borrow mut` helper may use the builder non-consumingly |
| 4 | At `push`, source move state and exact element-type compatibility, followed by recursive allocation-mode validation; an arena, mixed, or path-dependent owned child is rejected before growth |
| 5 | `build` transfer and ordinary array escape/cleanup validation; scalar/string compatibility paths retain their existing boxed-header behavior |

The same order and first-diagnostic rule applies to whole-program, imported/per-unit, and cache
replay checking. A valid view-free declared record must not be rejected merely because it is a
record rather than a primitive scalar; a view-bearing or over-aligned record must be rejected as a
heap-builder element before construction.

### Ownership closure matrix

Align's own reviewed design must keep the canonical implementation closure matrix in its
authoritative Align design (the current related owner is
`../align/docs/impl/17-library-boundary-prerequisites.md` §7, or a directly linked successor chosen
before implementation). This register is the align-llm acceptance summary: it records the required
coverage, owner symbols, and regression names so adoption can verify the shipped capability, but it
does not replace the sibling repository's plan or claim authority over Align implementation order.
The Align implementation PR must copy/refine this coverage in that canonical design before coding;
if a boundary changes, the Align design and this request entry must be updated together.

| Case | Exact owner | Exact regression |
| --- | --- | --- |
| `array_builder<T>` formation and expected-type inference | `../align/crates/align_sema/src/lib.rs` `resolve_type`/`check_array_builder_new` and the new recursive heap-element eligibility check | `m12_array_builder.rs::record_builder_type_formation_and_inference` covers a view-free Copy record, a supported generic record instantiation, missing expected type, and rejected resource/function/raw/view/dynamic-array/option/sum/cyclic/empty/`layout(C)`/over-aligned types; `m12_array_builder.rs::record_builder_over_aligned_type_rejected_before_allocation` and `m12_array_builder.rs::record_builder_empty_or_c_layout_rejected_before_allocation` pin the boundary |
| Heap-form view exclusion and region-builder boundary | `../align/crates/align_sema/src/lib.rs` `resolve_type`/`check_array_builder_new`; the related explicit-region owner is Align §7 | `m12_array_builder.rs::record_builder_view_element_rejected_before_construction` rejects direct and nested views, while `align_attr.rs::an_aligned_struct_as_a_field_or_dynamic_array_element_is_rejected` remains the aligned dynamic-array baseline |
| Copy record push/build | `../align/crates/align_mir/src/lib.rs`, `../align/crates/align_codegen_llvm/src/lib.rs`, and `../align/crates/align_runtime/src/lib.rs` | `m12_array_builder.rs::copy_record_push_build_zero_one_many_and_realloc` checks a scalar-only Copy record's exact fields and the run result |
| Move record push/source nulling | `../align/crates/align_sema/src/lib.rs` MoveCheck and `../align/crates/align_mir/src/lib.rs` push lowering | `m12_array_builder.rs::move_record_push_nulls_source` checks an owned-string/nested Move record's source-use-after-push and moved-field provenance |
| Recursive nested-record `DropPlan` and closed field predicate | `../align/crates/align_sema/src/lib.rs` structural type walk, source-cycle check, natural-layout/representation check, and DropPlan plus `../align/crates/align_codegen_llvm/src/lib.rs` recursive drop lowering | `owned_structs.rs::record_builder_nested_move_drop_plan` observes nested-owner frees on success and partial construction; `m12_array_builder.rs::record_builder_field_predicate_rejects_dynamic_array_option_sum_and_cycle` proves every excluded aggregate is rejected before construction, while the empty/`layout(C)` formation test closes the non-tree layout boundary |
| Nested owner allocation mode | `../align/crates/align_sema/src/lib.rs` `EscapeCheck::drop_is_individual`/`drop_may_be_individual`, `MoveCheck::expr`, and `../align/crates/align_mir/src/lib.rs` ownership carrier | `owned_structs.rs::record_builder_rejects_arena_or_mixed_nested_owners` rejects arena-owned, mixed-mode, and path-dependent nested owners before push side effects |
| Partial element construction | `../align/crates/align_mir/src/lib.rs` aggregate cleanup edges | `m12_array_builder.rs::record_builder_partial_element_failure_drops_fields` checks a failed element after an earlier push |
| Builder abandonment before `build` | `../align/crates/align_mir/src/lib.rs` cleanup insertion and `../align/crates/align_runtime/src/lib.rs` builder drop | `m12_array_builder.rs::record_builder_abandonment_all_exit_kinds` covers early return, `?`, `map_err`, loop break, malformed input, and leak/double-free counters |
| Reallocation of live nested owners | `../align/crates/align_runtime/src/lib.rs` builder growth and relocation | `m12_array_builder.rs::record_builder_realloc_preserves_nested_owners` checks values and exactly-once frees |
| `build` transfer and returned array cleanup | `../align/crates/align_mir/src/lib.rs` move-out plus ordinary array `Drop` | `m12_array_builder.rs::record_builder_build_transfer_and_array_drop` covers return, consume, unused, and no duplicate builder cleanup |
| Builder replacement/reassignment and builder-state reset | `../align/crates/align_sema/src/lib.rs` assignment/drop classification and `../align/crates/align_mir/src/lib.rs` `drop_old` | `m12_array_builder.rs::record_builder_reassignment_drops_old_storage` extends the existing `reassignment_frees_old_string_builder` guard and proves the replacement has fresh ownership/placement state; borrow roots are N/A because heap elements reject reachable views |
| Enclosing record construction failure | `../align/crates/align_mir/src/lib.rs` aggregate/source cleanup | `owned_structs.rs::record_builder_enclosing_record_failure` checks a built nested array followed by a failing sibling and branch join |
| `if`/`match`/`else`/`?`/`map_err` joins and loop back-edges | `../align/crates/align_sema/src/lib.rs` Move/Drop analysis and `../align/crates/align_mir/src/lib.rs` cleanup CFG | `region_flow.rs::record_builder_all_supported_join_shapes` and `m12_array_builder.rs::record_builder_join_cleanup_matrix` cover built and abandoned paths |
| Record-builder storage, by-value boundary, capture, `Option`, `Result`, and `borrow mut` | `../align/crates/align_sema/src/lib.rs` placement/capture checks and the existing Align L2e borrow checker contract; `../align/crates/align_codegen_llvm/src/lib.rs` boxed-header boundary | `m12_array_builder.rs::record_builder_invalid_storage_and_capture` rejects aggregate/by-value forwarding/return/capture/`Option`/`Result` placement before allocation; `m12_array_builder.rs::record_builder_borrow_mut_helper_non_consuming` covers the existing non-consuming helper contract once L2e is available; scalar/string compatibility remains covered by `capture_into_spawn_rejected`, `capture_into_par_map_rejected`, `escaping_array_builder_keeps_boxed_header`, and `array_builder_crossing_user_call_stays_boxed` |
| Deterministic validation precedence | `../align/crates/align_sema/src/lib.rs` `resolve_type`, `check_array_builder_new`, `check_array_builder_push`, `MoveCheck::expr`, and `EscapeCheck::walk_array_builder` | `m12_array_builder.rs::record_builder_validation_precedence_local_and_imported`, `per_unit.rs::record_builder_validation_precedence_parity`, and `cache_codegen.rs::record_builder_validation_precedence_cache_replay` cover multi-invalid local/imported/per-unit/cache diagnostics and first-error parity |
| Generic monomorphization and imported interface | `../align/crates/align_sema/src/lib.rs` type substitution, `../align/crates/align_mir/src/lib.rs` graph collection, and `../align/crates/align_driver/src/lib.rs` interface emission | `generics.rs::record_builder_generic_instantiation` plus `per_unit.rs::record_builder_imported_interface_graph` checks local/imported parity |
| Structural identity and codegen cache | `../align/crates/align_driver/src/lib.rs` interface/cache identity plus canonical `RecordBuilderDescV1` serialization | `cache_codegen.rs::record_builder_descriptor_golden_and_definition_edit_revert_identity` checks exact versioned bytes, cold hit, definition edit miss, revert identity, and malformed/zero-field/trailing descriptor rejection |
| Interface ABI and descriptor completeness | `../align/crates/align_driver/src/lib.rs` interface serialization and `../align/crates/align_codegen_llvm/src/lib.rs` ABI descriptor | `interface_param_modes.rs::record_builder_interface_drop_descriptor` rejects a producer/consumer cleanup-contract mismatch and layout/allocation/drop-tag disagreement |
| Allocation and byte ownership | `../align/crates/align_runtime/src/lib.rs` allocation/growth/build plus codegen ownership flags | `m12_array_builder.rs::record_builder_allocation_transfer_instrumentation` checks allocation counts, sanitized execution, and no duplicate element buffer |
| Builder concurrency and overlap exclusion | `../align/crates/align_sema/src/lib.rs` local placement/capture checks and `../align/crates/align_runtime/src/lib.rs` instance-local state | `m12_array_builder.rs::record_builder_same_instance_alias_rejected` proves a second operation on the same builder cannot be represented or start; `record_builder_two_instances` proves two distinct builders and aggregate-plus-aggregate/aggregate-plus-focused calls are independent; `cache_parallel.rs::record_builder_two_processes` covers independent processes |
| Capacity overflow | `../align/crates/align_runtime/src/lib.rs` checked capacity arithmetic | `m12_array_builder.rs::record_builder_capacity_overflow_terminal_never_returns_partial_success` verifies the existing terminal overflow policy and no successful partial array |
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
   `m12_array_builder.rs::record_builder_view_element_rejected_before_construction`, and
   `m12_array_builder.rs::record_builder_over_aligned_type_rejected_before_allocation`, together
   with `m12_array_builder.rs::record_builder_empty_or_c_layout_rejected_before_allocation`.
2. The heap form does not admit `RegionPlain` view-bearing elements; the explicit-region
   `array_builder(out)` design remains a separate Align §7 gate and is not claimed by Request 8.
   The exact compatibility gate is
   `align_attr.rs::an_aligned_struct_as_a_field_or_dynamic_array_element_is_rejected` together
   with the view-rejection test in item 1.
3. A declared scalar-only Copy record can be pushed zero, one, many, and reallocating counts and
   then built into `array<ScalarRecord>` with exact field values. The exact gate is
   `m12_array_builder.rs::copy_record_push_build_zero_one_many_and_realloc`.
4. A declared Move record containing an owned `string` or a nested Move record can be pushed only
   when every reachable owned value satisfies the exact `FreeStanding(e)` predicate; arena-owned,
   mixed-mode, and path-dependent nested owners are rejected before the push side effect. Dynamic
   arrays, `Option`, and sums are not hidden parts of this gate and require separate requests that
   define their recursive cleanup. A valid value can be rebuilt across capacity growth, consumed
   into an array, and deep-dropped without a leak or double free. The test must observe ownership, not only length
   or exit status; the exact gates are `m12_array_builder.rs::move_record_push_nulls_source`,
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
   `?`, `map_err`, loop joins, early return, malformed input, and exact-once cleanup.
6. `build` consumes the builder and transfers storage exactly once; normal array cleanup owns the
   result, replacement drops the old builder, and use-after-build/source-use-after-push are
   rejected. The exact gates are `m12_array_builder.rs::record_builder_build_transfer_and_array_drop`
   and `m12_array_builder.rs::record_builder_reassignment_drops_old_storage`.
7. `append` of a Move record, bare `str`, dynamic array, resource, function, raw value, or builder is rejected
   before side effects. A record-element builder cannot be stored in an aggregate, transferred
   by-value across a user-function boundary, returned, captured, or put in `Option`/`Result`.
   Once Align L2e is shipped, an existing `borrow mut` helper may use the builder non-consumingly;
   the helper cannot create an alias that escapes the borrow, and `build` remains consuming. The
   pinned compiler does not yet run that positive helper gate, but Request 8 does not contradict or
   redefine it. Existing scalar/string builders retain their current boxed return and forwarding
   behavior. The exact gates are
   `m12_array_builder.rs::record_builder_invalid_storage_and_capture` and the existing
   `m12_array_builder.rs::record_builder_borrow_mut_helper_non_consuming`,
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
   pinned Align baseline, produce identical structural identities and decisions in whole-program
   and per-unit compilation. The exact `RecordBuilderDescV1` golden bytes include the schema/root
   tags, declaration-order names, scalar widths, nested bodies, layout values, allocation modes,
   and drop tags; malformed, truncated, zero-field, and trailing-byte descriptors reject before use.
   Source type formation rejects cycles before a finite descriptor is emitted. A record-definition edit invalidates the codegen cache, reverting it restores the original
   identity, and an incompatible cleanup descriptor is rejected. The exact
   gates are `generics.rs::record_builder_generic_instantiation`,
   `per_unit.rs::record_builder_imported_interface_graph`,
   `cache_codegen.rs::record_builder_definition_edit_and_revert_identity`, and
   `interface_param_modes.rs::record_builder_interface_drop_descriptor`.
10. A second operation cannot concurrently alias one record builder: standalone mutable-local
    placement rejects capture and by-value transfer, while an Align L2e `borrow mut` helper is a
    checked non-consuming borrow with no escaping alias. Two distinct builders in one process, an
    aggregate plus a focused builder call, and two independent processes have no shared mutable
    state. Capacity overflow and test-injected allocator failure both terminate without a
    recoverable result or successful partial array. The exact gates are
    `m12_array_builder.rs::record_builder_same_instance_alias_rejected`,
    `m12_array_builder.rs::record_builder_two_instances`,
    `cache_parallel.rs::record_builder_two_processes`,
    `m12_array_builder.rs::record_builder_capacity_overflow_terminal_never_returns_partial_success`,
    and `m12_array_builder.rs::record_builder_allocator_failure_terminal_child`.
11. The existing scalar/string builder behavior and JSON `array<Struct>` decode/drop behavior remain
    green, and allocation instrumentation proves that a built array owns transferred storage while
    an abandoned builder frees every live element. The exact gates are the existing
    `m12_array_builder.rs::i64_push_build_then_pipeline_sum`,
    `string_push_build_len_and_deep_drop_cycles`, `reassignment_frees_old_string_builder`,
    `m5.rs::json_decode_struct_array_len`, `json_decode_struct_array_malformed_errors`, and
    `m12_array_builder.rs::record_builder_allocation_transfer_instrumentation` tests.

12. A future consumer adoption test is not part of the current Align implementation gate. Before a
    concrete consumer may mark this request `ALIGN_LLM_VERIFIED`, that consumer must name its exact
    record shapes, wire boundary, adoption fixture, and output checks in its own reviewed design;
    it must not assume a JSON DTO, a borrowed-view conversion, or a private collection abstraction.
    Request 8 itself does not absorb any consumer's wire or persistence boundary. For the currently
    named C6c2 consumer, `c6c2-request8-adoption` is that separate enabling fixture and is allowed
    to verify this Request 8 base before the C6c2 verifier or Request 10 exists.

The align-llm adoption slice is separate from the Align implementation. After `ALIGN_MERGED`, each
named consumer adoption slice must rebuild the sibling release compiler and runtime from the named
Align commit, update `.align-revision` to that exact commit, and add its consumer-specific target and
fixture. The targets must use the reviewed fresh-compiler topology and exact shipped pin, verify the
declared record values and cleanup boundary, and reject panic, stale source use, and unexpected
artifacts. `c6c2-request8-adoption` is the first C6c2 enabling target and covers only the Request 8
base graph; it may advance Request 8 to `ALIGN_LLM_VERIFIED` before C6c2's verifier implementation
or Request 10 is available. The later `c6f2-array-builder-adoption` covers the paired evaluator
consumer. Each target plus `make ci` is required for the consumer that names it; adoption does not
silently inherit another consumer's fixture.

### References

- `docs/specs/roadmap.md` and `docs/specs/align-llm.md` — the committed roadmap and architecture;
  a concrete consumer must refine its own record shapes and adoption gate before using this request.
- `../align/docs/impl/17-library-boundary-prerequisites.md` §7 — the separate planned
  `RegionPlain` region-builder contract and its ownership/compaction model.
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
  `../align/crates/align_driver/tests/interface_param_modes.rs` — structural identity and
  interface/cache regressions.
- `../align/crates/align_driver/tests/m5.rs` and `../align/crates/align_driver/tests/mmv2.rs` —
  declared JSON array and materializing-terminal compatibility regressions.
- `../align/crates/align_driver/tests/cache_parallel.rs` — independent-process cache/concurrency
  regression harness.

---

## Request 9 — `core.json`: owned text fields and runtime-sized text arrays

```text
Status: PROPOSED
Priority: high
Blocking: no
Blocked gate or slice: C7's named `C7-PersistedResult` persisted verification-result slice (the first expected consumer; its detailed contract is not yet designed); the first Align implementation of this request is also gated on Request 7's named `ALIGN_MERGED` escape-grammar commit and a reviewed Align memory-model/spec update that defines explicit free-standing JSON materialization inside an arena, and C6 remains independent
Independent work that may continue: Request 5, Request 6, Request 7, application designs, and any consumer that does not require this direct owned JSON shape
Resume condition: Request 9 remains non-blocking until the named `C7-PersistedResult` design names this capability as its prerequisite; then reclassify it as blocking for that named slice. Request 9's Align implementation may start only after Request 7 reaches `ALIGN_MERGED` at a named Align commit that supplies the authoritative escape grammar/vector and the reviewed Align memory-model/spec update authorizes this JSON terminal's explicit free-standing allocation inside an arena; Request 9 reuses that grammar but owns its separate free-standing materialization contract. After Request 9 reaches ALIGN_MERGED at a named Align commit, a separately reviewed consumer adoption slice must rebuild the sibling release compiler and runtime, update `.align-revision` to that exact commit after the common check-topology design and implementation are already merged, run its named adoption target and `make ci`, and resume only that named consumer
Align commit or pull request: pending
align-llm verification: pending
```

### Motivation

`C7 Algorithm Verification`'s named `C7-PersistedResult` slice may need to retain a declared record after its input document and
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
  descriptor after a `Some` value becomes live. Request 9 explicitly owns that transition audit and
  its success, failure, replacement, move-out, and branch-join tests; it does not claim the pinned
  cleanup path already passes.
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
- The pinned negative regression
  `../align/crates/align_driver/tests/m5.rs::json_option_move_struct_payload_still_rejected` currently
  fails because a record with only `Option<MoveStruct>` is admitted by the existing JSON route. That
  is a pre-existing route inconsistency, not evidence that the new owned descriptor is available:
  Request 9 rejects unsupported optional owners only after its direct owned-text selector has been
  chosen, while preserving the existing route for records with no owned text leaf. Align may decide
  and repair the existing-route behavior separately if it wants to change it.

This is a genuine Align type/standard-library boundary, not an align-llm compatibility concern.
Request 9 must be designed and implemented in Align before any consumer targets it.

### Requested capability

Keep the existing context-inferred declared-record operations and expand their accepted field graph:

```text
json.decode(input: str) -> Result<T, Error>   // T is inferred from the annotated declared-record binding
json.encode(value: T) -> str                  // returns the existing canonical output view
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
| `json.decode` with `Result<array<scalar>, Error>` | Retain the existing top-level scalar-array decoder for `array<i64>`, `array<f64>`, `array<bool>`, and the corresponding supported scalar primitive forms; it copies elements into its existing owned dynamic-array representation and never selects `OwnedJsonDescV1` | Existing `m5.rs::json_decode_scalar_array` and `m5.rs::json_decode_float_array`; the Align implementation PR adds the currently missing `m5.rs::json_decode_bool_array` regression for the already-supported top-level bool path |
| `json.decode` with `Result<array<Struct>, Error>` | Retain the existing AoS predicate and descriptor, including already-shipped Move element graphs such as a union carrying `array<Part>`. The new direct owned-text selector is never entered; an element containing `string`, `Option<string>`, or `array<string>` is rejected before `OwnedJsonDescV1` construction and allocation | `m5_owned_json.rs::owned_json_record_array_preserves_shipped_move_aos` and `m5_owned_json.rs::owned_json_record_array_owned_text_rejected_before_owned_descriptor` |
| `json.scan` with `json.scanner<Struct>` | Retain Request 6's recursively Copy scanner-row predicate. An owned record is rejected before scanner construction, descriptor construction, or row-slot allocation | `m5_owned_json.rs::owned_json_scanner_target_rejected_before_allocation` |
| `json.decode` with `Result<soa<Struct>, Error>`, a union, or a scalar | Unchanged existing target-specific validation; none can select the owned direct-record path | `m5_owned_json.rs::owned_json_non_record_targets_unchanged` |
| `json.encode` with a fixed `StructArray` source | Retain the existing fixed-array template/unrolled route; `OwnedJsonDescV1` is never selected, and existing borrowed or shipped Move element behavior is unchanged | `m5_owned_json.rs::owned_json_fixed_struct_array_encode_route_unchanged` |
| `json.encode` with a direct union/`Enum` source | Retain the existing shape-directed union route; `OwnedJsonDescV1` is never selected, including for shipped Move union payloads | `m5_owned_json.rs::owned_json_union_encode_route_unchanged` |

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
6. JSON field/type validation is compile-time and the encode operation is non-fallible after a valid
   descriptor is compiled; it does not perform consumer artifact validation or file commit. A future
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
   | `BD` | existing direct borrowed-record `json.decode` |
   | `SD` | existing bare scalar `json.decode` (`int`, `float`, or `bool`) |
   | `AD` | existing top-level scalar-array `json.decode` (`array<i64>`, `array<f64>`, or `array<bool>`) |
   | `BE` | existing borrowed direct-record `json.encode` |
   | `FE` | existing fixed `StructArray` `json.encode` |
   | `UD` | existing direct union/`Enum` `json.decode` |
   | `UE` | existing direct union/`Enum` `json.encode` |
   | `DOC` | existing `json.doc` |
   | `SCAN` | existing `json.scan` |
   | `AOS` | existing `array<Struct>` `json.decode` |
   | `SOA` | existing `soa<Struct>` `json.decode` |

   Let `J = {OD, OE, BD, SD, AD, BE, FE, UD, UE, DOC, SCAN, AOS, SOA}`. The required policy is
   the full unordered Cartesian product `J × J`, including the diagonal: all 91 class pairs are
   supported concurrently, neither serialized nor rejected before side effects. Each class's
   listed target variants is exercised, so the matrix explicitly includes existing-only pairs such
   as `BD + AD`, `DOC + SCAN`, and `FE + UE`, as well as aggregate-plus-aggregate and
   aggregate-plus-focused pairs. Direct owned decode and direct owned encode keep parser,
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
| 1 | Compile-time parser/import/arity and expected-record inference |
| 2 | Compile-time direct declared field grammar, ownership classification, `DropPlan`, allocation mode, and interface identity; mixed or unsupported aggregate graphs reject before allocation |
| 3 | Recoverable runtime decode syntax/duplicate/schema/range validation in the existing parser order; on recoverable failure, direct-field cleanup of already-live owners; capacity overflow and allocator failure take the separate terminal-abort policy |
| 4 | Successful decode result construction and Move transfer; raw `Result<OwnedRecord, Error>` bind, parameter, return, reassignment, branch-join, and `map_err` paths use the pinned recursive Move carrier and are checked as ordinary ownership transfers |
| 5 | Compile-time encode descriptor validation, then non-fallible canonical field-order emission into the existing output region |
| 6 | Consumer-only output clone, artifact validation, and file commit after `json.encode`; these are not Request 9 runtime errors |

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
| Operation-specific target routing | `../align/crates/align_sema/src/lib.rs` direct-record selector plus unchanged `check_json_decode`, `check_json_scan`, fixed-`StructArray` encode, and union target gates | `m5_owned_json.rs::owned_json_direct_record_target_selects_owned_path`, `owned_json_direct_record_encode_route`, `owned_json_record_array_preserves_shipped_move_aos`, `owned_json_record_array_owned_text_rejected_before_owned_descriptor`, `owned_json_scanner_target_rejected_before_allocation`, `owned_json_non_record_targets_unchanged`, `owned_json_fixed_struct_array_encode_route_unchanged`, and `owned_json_union_encode_route_unchanged` prove the new direct owned-text graph cannot widen scanner, new AoS, SoA, union, scalar, fixed-array, or existing Move-union routes |
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
| Owned encode field order and escapes | `../align/crates/align_runtime/src/lib.rs` declared encoder descriptor and string writer | `m5_owned_json.rs::encode_owned_json_canonical_bytes` proves declaration order, the inline owned-path grammar vectors, escapes, embedded NUL, empty arrays, text-array order, and no source mutation |
| Encode output region and explicit persistence clone | `../align/crates/align_sema/src/lib.rs` region escape checks and `../align/crates/align_runtime/src/lib.rs` output builder | `m5_owned_json.rs::owned_encode_output_region_and_clone_boundary` proves arena result expiry, outside hidden-owner lifetime, explicit clone before persistence, and rejection of a dangling return |
| Encode/decode semantic and byte round-trip | `../align/crates/align_mir/src/lib.rs` JSON nodes plus runtime codec | `m5_owned_json.rs::owned_json_encode_decode_encode_identity` proves semantic equality and byte identity while source, decoded, and cloned-output owners remain live |
| Input/source lifetime boundary and mixed records | `../align/crates/align_sema/src/lib.rs` region/drop checks | `m5_owned_json.rs::owned_decode_has_no_input_region_dependency` drops input before using every owned field and rejects treating a mixed borrowed `str` record as `Owned*` |
| Generic and imported graph parity | `../align/crates/align_sema/src/lib.rs` substitution; `../align/crates/align_driver/src/lib.rs` interface emission | `generics.rs::owned_json_direct_grammar_substitution` and `per_unit.rs::owned_json_imported_direct_graph_parity` cover only accepted direct shapes and equivalent rejection |
| Structural identity, natural layout, and cache | `../align/crates/align_driver/src/lib.rs` existing structural/interface cache identity plus the new natural-layout-only `OwnedJsonDescV1` descriptor; `../align/crates/align_sema/src/lib.rs` layout validation; `../align/crates/align_codegen_llvm/src/lib.rs` `logical_to_physical`, `field_byte_offset`, and target `Option` payload/tag offsets | `cache_codegen.rs::owned_json_descriptor_golden_and_definition_edit_revert_identity` proves the natural-layout header and algorithm, fixed tags/widths, explicit `0 = signed`/`1 = unsigned` payload mapping, signed/unsigned golden fields including `u64::MAX`, record-base-relative physical payload/tag offsets for a nonzero-position optional field, target-local sizes/alignments, cold hit, definition edit miss, revert identity, explicit `layout(C)`/`align(N)` rejection, and stale descriptor rejection; `interface_param_modes.rs::owned_json_descriptor_physical_layout_mismatch_rejected` rejects an algorithm, payload offset, optional tag offset, or layout mismatch before field access, cleanup, or codegen |
| ABI descriptor and allocation parity | `../align/crates/align_driver/src/lib.rs` interface serialization, `../align/crates/align_codegen_llvm/src/lib.rs` ABI/drop descriptors, and `../align/crates/align_runtime/src/lib.rs` ownership flags | `interface_param_modes.rs::owned_json_direct_drop_descriptor_abi`, `m5_owned_json.rs::owned_json_whole_program_per_unit_allocation_parity`, and `m5_owned_json.rs::owned_json_allocation_transfer` |
| Capacity overflow | `../align/crates/align_runtime/src/lib.rs` checked element-count/byte-count arithmetic for owned array decode and checked builder length/growth arithmetic for owned encode | `m5_owned_json.rs::owned_json_decode_capacity_overflow_terminal_child` and `m5_owned_json.rs::owned_json_encode_capacity_overflow_terminal_child` cover decode growth and encode growth independently; each proves terminal non-zero exit and no successful partial record/string |
| Allocator failure | `../align/crates/align_runtime/src/lib.rs` allocator/cleanup and the Align test-only child-process failpoint | `m5_owned_json.rs::owned_json_allocation_transfer` covers recoverable parse/type failures; `m5_owned_json.rs::owned_json_allocator_failure_terminal_child` records the distinct terminal allocator-abort policy for direct fields, text-array growth, and output-builder growth and explicitly makes no cleanup-after-abort claim |
| Same-process and process concurrency policy | per-call parser, destination, temporary-owner, and output-builder state in `../align/crates/align_runtime/src/lib.rs`; immutable descriptor tables may be shared; no process-global mutable codec state or codec-instance API is added | `m5_owned_json.rs::owned_json_same_process_entrypoint_matrix` runs the full 91-pair unordered `J × J` matrix, including diagonal and existing-only pairs (`BD + AD`, `DOC + SCAN`, `FE + UE`) and every target variant named in item 9; every pair is supported concurrently, not serialized or pre-rejected; `cache_parallel.rs::owned_json_two_processes` confirms independent processes have the same no-shared-state policy |
| Existing borrowed and shipped Move JSON compatibility | `../align/crates/align_sema/src/lib.rs` target-specific predicates plus existing runtime template/descriptor/union paths | `m5.rs::json_decode_struct_array_len`, `json_decode_struct_array_malformed_errors`, existing `owned_tagged_payloads.rs::retained_result_with_recursive_move_payload_is_supported`, `m5_owned_json.rs::owned_json_record_array_preserves_shipped_move_aos`, `owned_json_fixed_struct_array_encode_route_unchanged`, `owned_json_union_encode_route_unchanged`, and Request 7's escaped-view tests remain green; no new `OwnedJsonDescV1` route is used |
| Metric / benchmark decision | Request 9 public contract item 11; allocation instrumentation in `../align/crates/align_runtime/src/lib.rs` and whole-program/per-unit test harness | `m5_owned_json.rs::owned_json_whole_program_per_unit_allocation_parity` is the required correctness measurement; no performance benchmark or threshold is claimed because this is a correctness prerequisite, and a later optimization must register its own workload and baseline |
| First expected consumer and lifecycle | `docs/specs/roadmap.md` named `C7-PersistedResult` slice and Request 9 lifecycle metadata | N/A until the `C7-PersistedResult` detailed consumer design names the accepted record shapes; the named roadmap slice is the first consumer, Request 9 remains non-blocking until that design gate, and the consumer must reclassify this request before implementation/adoption |
| Target ABI baseline and target-local descriptor exchange | `../align/crates/align_driver/src/lib.rs` target-triple/interface identity, `../align/crates/align_codegen_llvm/src/lib.rs` natural layout, and `../align/docs/impl/11-release-distribution.md` supported release environments | `interface_param_modes.rs::owned_json_target_abi_descriptor_matches_target` runs the required `x86_64-unknown-linux-gnu` baseline and the `aarch64-unknown-linux-gnu`/`aarch64-apple-darwin` release-target acceptance environments; `interface_param_modes.rs::owned_json_target_abi_mismatch_rejected` rejects a target/ABI mismatch before code generation |
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
6. `decode -> encode -> decode` preserves semantic owned values and `encode` bytes while the source
   and output owners are independently live; the output does not borrow source text.
7. Generic, imported/per-unit, cache-cold/edit/revert, `OwnedJsonDescV1` ABI descriptor including
   the pinned natural-layout algorithm, every logical field's physical payload offset and optional
   tag offset, explicit signed/unsigned descriptor tags, raw-`Result` bind/parameter/return/reassignment and typed
   `map_err` transfer, the complete same-process entrypoint
   matrix including all 91 unordered pairs and every target variant in item 9, existing scalar-array
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
9. A future named align-llm adoption slice, created only after a concrete consumer design exists,
   must construct the flat owned record, drop the input, encode the inline canonical bytes, decode
   again, and exercise direct text-array cleanup. Only that named target plus `make ci` may advance
   Request 9 to `ALIGN_LLM_VERIFIED`; this proposal does not claim that target or its fixture exists.

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
    source declarations and explicit `json.decode`/`json.encode` arguments are the complete input
    surface; no ambient configuration may change route selection, descriptor identity, allocation,
    parsing, encoding, or cleanup. The closure matrix records both dimensions as N/A with these
    reasons, and the pinned compiler/runtime revision is not treated as a runtime option.

The adoption target is separate from Align implementation. After `ALIGN_MERGED`, the named consumer
slice rebuilds the sibling release compiler and runtime from the named commit, updates
`.align-revision`, creates its exact bytewise fixture, and runs it through the common fresh-compiler
topology. No later consumer dependency is asserted until that consumer's design is durable and
updated to name this merged request.

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
Status: PROPOSED
Priority: high
Blocking: yes
Blocked gate or slice: C6f2 deterministic paired evaluator and C6c2 decoded evaluation verifier; Request 8 supplies the recursively Copy, owned-record base needed by this evaluator extension, and C6c2 cannot adopt its recursive runtime-sized result arrays until both requests are merged
Independent work that may continue: C6c2 design, C6a1 codec work that does not materialize recursive runtime arrays, C6b, C6c, C6d, Request 5, Request 6, Request 7, Request 8, Request 9, and verification work that does not construct the blocked record graph
Resume condition: Request 8 first reaches ALIGN_MERGED at a named Align commit; then Align merges this request at a named commit, the sibling release compiler and runtime are rebuilt, and `.align-revision` is updated after the common check-topology design and implementation are already merged. The C6f2 path runs `c6f2-array-builder-adoption` and `make ci`; the C6c2 path runs the Request 10 recursive subset of `c6c2-request10-adoption` and `make ci`, then the original recursive-construction acceptance matrix. The C6c2 target is a separate enabling adoption slice and does not require the later verifier implementation; only after both Request 8 and Request 10 adoption gates pass may C6c2 implementation resume.
Align commit or pull request: pending
align-llm verification: pending
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
6. C6f2 constructs and drops the named records through the shipped surface, then passes its
   runtime-array, malformed-input, early-exit, and cleanup regressions through `make ci`; the
   C6c2 enabling consumer separately runs `c6c2-request10-adoption` for the recursive Request 10
   subset before C6c2 implementation starts, without making Request 10 depend on the later verifier.

The C6c2 enabling adoption is intentionally split from the verifier implementation. Its
`c6c2-request10-adoption` target is allowed only after the named Request 8 and Request 10 Align
commits are pinned; it constructs the exact recursive C6 record graph, exercises `Option.None`,
`Option.Some`, nested arrays, reallocation, partial failure, and `Drop`, then runs `make ci`. This
target supplies the C6c2-specific adoption evidence required by this request; the later
`c6f2-array-builder-adoption` remains the paired-evaluator consumer evidence.

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
Status: PROPOSED
Priority: high
Blocking: yes
Blocked gate or slice: C6f1 trusted snapshot/workspace boundary, C6f2 paired evaluator, and C6g1 real-consumer process boundaries
Independent work that may continue: C6a1 through C6d2 pure codecs, rendering, scoring, activation, and any work without an external child process
Resume condition: Align merges a cap-aware process capture surface at a named commit; the sibling release compiler and runtime are rebuilt, `.align-revision` is updated, and C6's helper/adapter over-cap, timeout, environment, kill/reap, and cleanup tests pass through `make ci`
Align commit or pull request: pending
align-llm verification: pending
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
Status: PROPOSED
Priority: high
Blocking: yes
Blocked gate or slice: C6a1/C6a2 canonical artifact persistence and every C6 slice that writes a result with a declared raw-byte cap
Independent work that may continue: pure prompt rendering, scoring, and design work that does not encode a capped persisted artifact
Resume condition: Align merges a bounded canonical encoder at a named commit; the sibling release compiler and runtime are rebuilt, `.align-revision` is updated, and C6's exact-cap, overflow, malformed-record, and cleanup adoption target plus `make ci` pass
Align commit or pull request: pending
align-llm verification: pending
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
Status: PROPOSED
Priority: high
Blocking: yes
Blocked gate or slice: C6a1/C6a2 canonical artifact declarations and every C6 command that persists a nested result
Independent work that may continue: C6b/C6c pure rendering and scoring, C6d fixture-only state work, Request 5, Request 7, Request 9, Request 11, Request 12, and any work that does not persist the recursive C6 graph
Resume condition: Align reviews and merges the exact recursive owned graph below at a named commit; the sibling release compiler/runtime are rebuilt, `.align-revision` is updated, and the C6a1/C6a2 owned-graph adoption target plus `make ci` pass
Align commit or pull request: pending
align-llm verification: pending
```

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
graph is finite, acyclic, and consists only of Copy scalar leaves, owned `string`, declared records,
`Option<T>` of an accepted graph, and `array<T>` of an accepted graph. It must cover the exact C6
records named in `docs/specs/c6-prompt-context-optimizer.md` §4.5, including prompt variants,
scope/policy records, snapshots, task rows, aggregates, reasons, environment identity, and the
canonical gate envelope. `str`, slices, resources, region-bound values, functions, raw values,
builders, enums, and unsupported floating or composite forms are rejected before allocation unless
the C6 ledger explicitly names them as a Copy scalar.

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
Status: PROPOSED
Priority: high
Blocking: yes
Blocked gate or slice: C6f2 deterministic paired evaluator result/evidence publication and any later C6 command that promises no-replace artifact finalization
Independent work that may continue: C6c1p and C6c2 pure verification, prompt rendering, scoring, design work, and any implementation that does not publish a pair with exclusive creation and no-replace rename
Resume condition: Align accepts and merges the reviewed exclusive-create and no-replace-publication design at a named commit; the sibling release compiler and runtime are rebuilt, `.align-revision` is updated, `c6f2-request14-adoption` passes the exact publication race/cleanup matrix, and `make ci` passes
Align commit or pull request: pending
align-llm verification: pending
```

### Motivation and current-state evidence

C6f2 writes a result and an independently content-bound evidence sidecar. Its contract requires
two sibling temporary files, exclusive creation, fixed result-then-evidence publication, and a
no-replace finalization failure if another process creates either target between validation and
publication. The pinned Align `std.fs` surface provides whole-file `write_file` and `remove`, plus
the `fs.create` writer; `fs.create` opens with create/truncate semantics and can replace an existing
path. It does not expose an exclusive-create operation or an atomic no-replace rename operation.
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

## Not requested (respecting Align's design)

These were considered and deliberately **not** requested, because they conflict with Align's design
or are already implemented:

- **A dynamic "JSON value" type.** Align deliberately requires declared record types and has no
  expression-position type arguments. `core.json` already decodes nested structs,
  `array<Struct>`, existing decode-eligible scalar/`str` and struct `Option` forms
  (missing key / `null` → `None`), enums (shape-directed unions), and ignores unknown fields —
  verified against `examples/json_nested.align`, which decodes an OpenAI chat-completions shape.
  `Option<enum>` remains an existing decode rejection. `Option<Move record>` is admitted by the
  pinned sema/runtime despite a contrary design statement and stale negative test; the cleanup
  prerequisite must decide and repair that surface. Known cleanup gaps include currently admitted
  optional owners on later object failure, owners overwritten across indexed top-level AoS
  speculation-to-fallback transitions even when fallback succeeds, staged top-level
  `array<MoveStruct>` rows on later failure, and required or currently admitted optional owners on
  trailing-garbage rejection. A follow-up design must audit and assign every transition after a
  decoded owner becomes live. `align-llm` should declare provider response structs, not ask Align
  for a dynamic value
  type. (Caveat handled app-side: decoded
  `str` fields are zero-copy views into the input; use `.clone()` to persist them past the input's
  lifetime.)
- **Working directory via app-side shell.** A `sh -c "cd <dir> && ..."` workaround exists, but it is
  fragile (shell quoting, no native exit/stream semantics); native `cwd` is requested in Request 1
  instead of relying on it.
