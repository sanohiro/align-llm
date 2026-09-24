# Local OpenAI-compatible serving

Status: planned after the Qwen3.5-0.8B native correctness and optimization gate in
`roadmap.md`. This is the inbound local server contract. `provider_openai` is an outbound
client and does not implement it.

## First usable consumer and prerequisites

An OpenAI-compatible client configured with `base_url = http://127.0.0.1:8080/v1` and the
configured model id can complete a text chat, including a second turn that carries prior
messages. The server owns one validated native Qwen3.5 session at a time and reuses loaded
weights across requests; request state begins empty and ends isolated. The same native owner
must first pass pinned llama.cpp prefill and multistep decode parity. The text prompt owner
must extend its qualified one-system/one-user template to ordered system, user, and assistant
history before multi-turn HTTP acceptance. The measured native optimization gate precedes
this capability; serving performance is measured separately and cannot inherit a CLI result.

The fixed Align revision `5c7af9e5` ships `std.http` `serve`, `accept`, `respond`, and
`respond_stream` with an owned request context and response/stream builders. Those are the
server's network primitives. No new Align surface is assumed. The HTTP server lives in Align;
the existing C ggml shim remains a backend ABI. The
[OpenAI Chat Completions API reference](https://developers.openai.com/api/reference/resources/chat)
owns the external JSON names and response shape; this file defines the supported local subset.

## Public contract ledger

| Dimension | Initial local serving contract |
| --- | --- |
| Surface and defaults | `main --serve-openai GGUF PACK MODEL_IR OPTIONS CACHE_BYTES MODEL_ID [PORT]`. `PORT` defaults to 8080 and must be in 1–65535. Bind only `127.0.0.1`. The command runs until interrupted; startup failure returns nonzero before listening. No public remote bind or TLS option in this boundary. |
| Routes | `POST /v1/chat/completions` and `GET /v1/models`. Other paths return 404; other methods on a known path return 405. `/v1/models` lists exactly the configured model id. |
| Request | UTF-8 `application/json` body ≤ 1 MiB; exact configured `model`; 1–128 ordered text messages with at most one leading `system`, alternating `user`/`assistant`, and final `user`; optional `stream` default false; optional `temperature` default 0 and required to remain 0; optional `max_tokens` default 256, range 1–4096 and bounded again by remaining context. Reject tools, images, audio, unknown role/content variants, nonzero temperature, and unsupported generation fields explicitly before tokenization or native allocation. |
| Response | `stream:false`: HTTP 200 JSON `chat.completion` with id, created timestamp, model id, one assistant choice with `finish_reason`, and exact prompt/completion/total token `usage`. `stream:true`: HTTP 200 `text/event-stream`, ordered `chat.completion.chunk` deltas, a final finish chunk, then `data: [DONE]`. No fabricated usage on an incomplete stream. |
| Errors | Before response headers, malformed JSON/schema/body → 400, wrong model → 404, unsupported but well-formed option → 400, native resource exhaustion → 503, internal generation failure → 500. Error bodies use `{ "error": { "message", "type", "code" } }` with stable machine-readable code. After SSE headers, send an error event when transport permits, then close without `[DONE]`. No partial result is recorded as success. |
| Ownership and concurrency | One Align process owns the listener, one loaded model, native device, and a single active generation session. Requests are serialized in the first capability. Each request owns parsed JSON, prompt ids, per-request KV/recurrent state, response buffers, and a stream if selected; cleanup runs on success, EOG, malformed input, disconnect, and compute failure. Loaded immutable weights survive between requests. |
| Identity/version | `MODEL_ID` is the exact external id and must match every request. Pack and Model IR bind to the source GGUF as the existing provider requires. The HTTP JSON has the Chat Completions object names; it introduces no persisted schema. Existing result and model formats keep their versions. |
| Validation order | Validate CLI and source/pack/geometry, load and verify native model, then bind. For each request: method/path, content type/body bound, JSON syntax and unique keys, model and message/option subset, prompt/context length, native admission, generation, response serialization. Invalid requests do not alter session state. |
| Acceptance and metric | A real OpenAI-compatible client sends non-stream and streaming two-turn requests to Qwen3.5-0.8B; response text, IDs, usage, `finish_reason`, SSE termination, and state isolation agree with the qualified native oracle. Record startup, time to first token, and completion latency against the native CLI on the same host. A serving speed claim needs its own measured baseline and floor. |

The first endpoint is loopback only. A remote bind, authentication, concurrent sessions,
tools, vision, and the Responses API are later contracts. This scope supports ordinary local
text chat without implying full OpenAI API coverage. The server documents the supported
subset and supplies a curl example only after the endpoint passes its owner test.

## Closure matrix

| Phase | Implementation and exact regression |
| --- | --- |
| Construction | `main` parses the serving command; `provider_runtime` verifies source/pack/geometry and creates a native Qwen3.5 session before `std.http.serve`. `scripts/run-openai-serving-smoke` tests real 0.8B startup and bad pack/options refusal with no listener left behind. |
| Success | An Align HTTP module decodes ordered messages, invokes the same qualified native session, and encodes JSON/SSE. The owner sends non-stream and stream two-turn requests through an OpenAI-compatible client and compares text/tokens to the pinned native oracle. |
| Malformed and unsupported input | The HTTP module bounds and validates method, path, content type, duplicate keys, model, roles, options, and context. The owner asserts exact 400/404/405 error envelopes and no native call for each malformed class. |
| Early exit and failure | The HTTP module observes disconnect/EOG/compute error; the native session retains only committed state until response success. The owner injects a compute failure and disconnect, then checks the next request against a fresh session. |
| Cleanup | Dropping request context, stream, graph and request state releases owned resources; shutdown drops listener and model. The owner runs repeated requests and a shutdown/restart cycle without state or descriptor growth. |
| Reused modules | `tokenizer_qwen2` owns Qwen3.5 chat rendering; `runtime_generation` owns inference and state; `std.http` owns framing. Existing tokenizer, generation, and runtime provider owners pass unchanged. |

The implementation map is open until the native consumer and prompt-history owner pass. Before
publication, map every applicable ledger and matrix cell to the final diff and exact passing
evidence or an explicit deferral here. A separate design-only pull request is not planned.
