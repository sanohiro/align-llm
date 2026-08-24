#!/usr/bin/env python3
"""Shared C6-MEASURED generation-child fixtures: content-bound artifacts and a recording listener.

`run-prompt-generate-smoke` and `run-prompt-measurement-adapter-smoke` share this module so both
drive the same `PromptGenerationRequest` shapes and the same connection-recording HTTP peer. Nothing
here is a product surface; it exists only to give the smokes a real filesystem, a real process, and
a real provider peer whose received bytes can be read back and re-digested.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import signal
import socket
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REPOSITORY = pathlib.Path(__file__).resolve().parent.parent
RESPONSE_CAP = 262_144
DIAGNOSTIC_CAP = 16_384
CREDENTIAL_VARIABLE = "ALIGN_LLM_PROMPT_GENERATE_SMOKE_KEY"
CREDENTIAL_VALUE = "sk-generate-.*+?[a-z]$-SECRET"
GENERATION_REQUEST_FIELDS = (
    "schema_version", "artifact_kind", "request_id", "provider_kind", "endpoint",
    "provider_model", "api_key_env", "rendered_prompt_path", "rendered_prompt_sha256",
    "max_tokens", "temperature_micros", "paired_seed", "timeout_ns", "max_response_bytes",
    "content_sha256",
)
GENERATION_RESPONSE_FIELDS = (
    "schema_version", "artifact_kind", "request_id", "status", "error_code", "error",
    "provider_kind", "provider_model", "provider_request_sha256", "seed_result", "applied_seed",
    "http_status", "content", "dispatch_start_ns", "dispatch_end_ns", "content_sha256",
)
PATCH_TEXT = (
    "--- a/src/duration.py\n"
    "+++ b/src/duration.py\n"
    "@@\n"
    "-    return round(seconds / 60)\n"
    "+    return int(seconds / 60 + (0.5 if seconds >= 0 else -0.5))\n"
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def digest_bytes(value: object) -> bytes:
    """The canonical digest preimage: `None` members are omitted exactly as Align's encoder omits them."""

    def omit_none(item: object) -> object:
        if isinstance(item, dict):
            return {key: omit_none(child) for key, child in item.items() if child is not None}
        if isinstance(item, list):
            return [omit_none(child) for child in item]
        return item

    return canonical(omit_none(value))


def bind(value: dict) -> dict:
    value["content_sha256"] = ""
    value["content_sha256"] = hashlib.sha256(digest_bytes(value)).hexdigest()
    return value


def rendered_prompt(
    text: str, *, task_id: str = "duration-half-away-from-zero", variant_id: str = "baseline-v1",
) -> dict:
    return bind({
        "schema_version": 1,
        "artifact_kind": "RENDERED_PROMPT",
        "task_id": task_id,
        "variant_id": variant_id,
        "variant_sha256": "1" * 64,
        "task_prompt_sha256": "2" * 64,
        "context_sources_sha256": "3" * 64,
        "text": text,
        "content_sha256": "",
    })


def generation_request(
    *,
    rendered_path: pathlib.Path,
    rendered_sha256: str,
    endpoint: str,
    provider_kind: str = "LOCAL_OPENAI",
    provider_model: str = "fixture-model",
    api_key_env: str | None = None,
    request_id: str = "generation-1",
    max_tokens: int = 512,
    temperature_micros: int = 250_000,
    paired_seed: int = 4_242,
    timeout_ns: int = 20_000_000_000,
    max_response_bytes: int = RESPONSE_CAP,
    **overrides: object,
) -> dict:
    value = {
        "schema_version": 1,
        "artifact_kind": "PROMPT_GENERATION_REQUEST",
        "request_id": request_id,
        "provider_kind": provider_kind,
        "endpoint": endpoint,
        "provider_model": provider_model,
        "api_key_env": api_key_env,
        "rendered_prompt_path": str(rendered_path),
        "rendered_prompt_sha256": rendered_sha256,
        "max_tokens": max_tokens,
        "temperature_micros": temperature_micros,
        "paired_seed": paired_seed,
        "timeout_ns": timeout_ns,
        "max_response_bytes": max_response_bytes,
        "content_sha256": "",
    }
    value.update(overrides)
    ordered = {key: value[key] for key in GENERATION_REQUEST_FIELDS if key in value}
    for key in value:
        require(key in GENERATION_REQUEST_FIELDS, f"unknown generation request field {key}")
    bind(ordered)
    return {key: ordered[key] for key in GENERATION_REQUEST_FIELDS if ordered.get(key) is not None}


def openai_envelope(content: str) -> bytes:
    return canonical({"choices": [{"message": {"role": "assistant", "content": content}}]})


def llama_envelope(content: str) -> bytes:
    return canonical({"content": content})


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else b""
        self.server.requests.append({
            "path": self.path,
            "authorization": self.headers.get("Authorization"),
            "body": body,
        })
        try:
            self.dispatch(body)
        except (BrokenPipeError, ConnectionResetError):
            # Over-cap and stalled rows deliberately abandon the connection.
            pass

    def respond(self, status: int, payload: bytes, content_type: str = "application/json") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if payload:
            self.wfile.write(payload)

    def dispatch(self, body: bytes) -> None:
        path = self.path
        if path == "/openai/ok":
            self.respond(200, openai_envelope(PATCH_TEXT))
        elif path == "/llama/ok":
            self.respond(200, llama_envelope(PATCH_TEXT))
        elif path == "/openai/seed-in-content":
            # A 2xx completion whose text mentions the word `seed`: this accepted the request and
            # must never be read as a refusal.
            self.respond(200, openai_envelope("the seed value is fine; here is the patch\n"))
        elif path == "/openai/seed-rejected":
            # A genuinely received status whose body refuses the paired seed control.
            self.respond(400, canonical({"error": "this deployment does not accept the seed field"}))
        elif path == "/openai/status-404":
            self.respond(404, canonical({"error": "no such model"}))
        elif path == "/openai/bad-envelope":
            self.respond(200, canonical({"choices": []}))
        elif path == "/openai/empty-content":
            # A well-formed 2xx envelope whose completion text is empty: the child must classify it
            # exactly like a malformed envelope instead of publishing an empty `GENERATED` content.
            self.respond(200, openai_envelope(""))
        elif path == "/openai/bad-content":
            self.respond(200, b"not a provider envelope at all")
        elif path == "/openai/over-cap":
            self.respond(200, b"x" * (RESPONSE_CAP + 1))
        elif path == "/openai/non-utf8":
            self.respond(200, b"\xff\xfe\x00\x01", content_type="application/octet-stream")
        elif path == "/credential/echo-content":
            self.respond(200, openai_envelope(f"the provider echoed {CREDENTIAL_VALUE} back"))
        elif path == "/credential/echo-status":
            self.respond(503, f"upstream rejected {CREDENTIAL_VALUE}".encode("utf-8"),
                         content_type="text/plain")
        elif path == "/credential/echo-straddling":
            # The only credential occurrence crosses the 16 KiB diagnostic bound, so it survives
            # only if redaction runs before truncation.
            head = "x" * (DIAGNOSTIC_CAP - 4)
            tail = "y" * 4_096
            self.respond(500, f"{head}{CREDENTIAL_VALUE}{tail}".encode("utf-8"),
                         content_type="text/plain")
        elif path == "/credential/echo-schema":
            self.respond(200, f"not an envelope: {CREDENTIAL_VALUE}".encode("utf-8"),
                         content_type="text/plain")
        elif path == "/openai/stall":
            # Accept the request and never write a response: the client's timeout must fire.
            self.server.stalled.set()
            self.server.release.wait(timeout=30)
        else:
            self.respond(404, canonical({"error": "unknown fixture path"}))

    def log_message(self, *_arguments: object) -> None:
        return


class FixtureServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), Handler)
        self.connections = 0
        self.requests: list[dict] = []
        self.stalled = threading.Event()
        self.release = threading.Event()

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(30)
        self.connections += 1
        return connection, address

    def handle_error(self, *_arguments: object) -> None:
        return

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.server_port}"


def start_server() -> tuple[FixtureServer, threading.Thread]:
    server = FixtureServer()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def stop_server(server: FixtureServer, thread: threading.Thread) -> None:
    server.release.set()
    server.shutdown()
    server.server_close()
    thread.join(timeout=10)


def closed_port() -> int:
    """A port with no listener: connecting to it is a transport errno, never an HTTP status."""
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    return port


def binary_path() -> pathlib.Path:
    return pathlib.Path(os.environ.get("ALIGN_LLM_BIN", str(REPOSITORY / "main")))


def zero_file_limit() -> None:
    import resource

    signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))


def invoke(
    arguments: list[str],
    *,
    environment: dict[str, str] | None = None,
    limit_file_size: bool = False,
    timeout: int = 60,
) -> subprocess.CompletedProcess[str]:
    process_environment = dict(os.environ)
    process_environment.pop(CREDENTIAL_VARIABLE, None)
    if environment:
        process_environment.update(environment)
    return subprocess.run(
        [str(binary_path()), *arguments],
        cwd=REPOSITORY,
        env=process_environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=timeout,
        preexec_fn=zero_file_limit if limit_file_size else None,
    )


class Case:
    """One prepared `prompt generate` invocation with its own request and response path."""

    def __init__(self, root: pathlib.Path, name: str) -> None:
        self.root = root
        self.name = name
        self.directory = root / name
        self.directory.mkdir(parents=True, exist_ok=True)
        self.request_path = self.directory / "request.json"
        self.response_path = self.directory / "response.json"
        self.rendered_path = self.directory / "rendered.json"

    def write_rendered(self, text: str, **keywords: object) -> dict:
        value = rendered_prompt(text, **keywords)
        self.rendered_path.write_bytes(canonical(value))
        return value

    def write_request(self, request: dict | bytes) -> None:
        self.request_path.write_bytes(request if isinstance(request, bytes) else canonical(request))

    def run(self, **keywords: object) -> subprocess.CompletedProcess[str]:
        return invoke(
            ["prompt", "generate", str(self.request_path), str(self.response_path)],
            **keywords,
        )

    def response(self) -> dict:
        require(self.response_path.is_file(), f"{self.name}: no response artifact was published")
        return json.loads(self.response_path.read_text(encoding="utf-8"))


def prepare(
    root: pathlib.Path,
    name: str,
    endpoint: str,
    *,
    prompt_text: str = "Repair round_to_minutes so an exact half minute rounds away from zero.",
    rendered_sha256: str | None = None,
    **request_overrides: object,
) -> Case:
    case = Case(root, name)
    rendered = case.write_rendered(prompt_text)
    case.write_request(generation_request(
        rendered_path=case.rendered_path,
        rendered_sha256=rendered["content_sha256"] if rendered_sha256 is None else rendered_sha256,
        endpoint=request_overrides.pop("endpoint", endpoint),
        **request_overrides,
    ))
    return case


def assert_response(
    case: Case,
    completed: subprocess.CompletedProcess[str],
    status: str,
    error_code: str,
) -> dict:
    require(
        completed.returncode == (0 if status == "GENERATED" else 2),
        f"{case.name}: unexpected exit {completed.returncode}: {completed.stderr}",
    )
    require(
        f"\n{status}\n" in completed.stdout,
        f"{case.name}: stdout did not report {status}: {completed.stdout!r}",
    )
    response = case.response()
    require(
        tuple(response) == tuple(
            name for name in GENERATION_RESPONSE_FIELDS if name in response
        ),
        f"{case.name}: response field order changed: {tuple(response)!r}",
    )
    require(
        response["status"] == status and response["error_code"] == error_code,
        f"{case.name}: expected {status}/{error_code}, got"
        f" {response['status']}/{response['error_code']} ({response['error']!r})",
    )
    require(
        response["schema_version"] == 1
        and response["artifact_kind"] == "PROMPT_GENERATION_RESPONSE",
        f"{case.name}: wrong response envelope: {response!r}",
    )
    claimed = response["content_sha256"]
    recomputed = dict(response)
    recomputed["content_sha256"] = ""
    require(
        hashlib.sha256(digest_bytes(recomputed)).hexdigest() == claimed,
        f"{case.name}: response content digest does not bind the record",
    )
    return response
