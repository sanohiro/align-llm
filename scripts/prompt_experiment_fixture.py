#!/usr/bin/env python3
"""Shared C6e proposal fixtures: content-bound artifacts and a recording provider listener.

The two owner runners (`run-prompt-experiment-smoke` and `run-prompt-credential-lifetime-smoke`)
share this module so both drive the same request/activation/opportunity shapes and the same
connection-recording listener. Nothing here is a product surface; it exists only to give the smokes
a real filesystem, a real process, and a real HTTP peer.
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
FILLER_DIGEST = "a" * 64
RESPONSE_CAP = 262_144
DIAGNOSTIC_CAP = 16_384
CREDENTIAL_VARIABLE = "ALIGN_LLM_PROMPT_EXPERIMENT_SMOKE_KEY"
CREDENTIAL_VALUE = "sk-fixture-.*+?[a-z]$-SECRET"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def bind(value: dict) -> dict:
    value["content_sha256"] = ""
    value["content_sha256"] = hashlib.sha256(canonical(value)).hexdigest()
    return value


def text_artifact(kind: str, artifact_id: str, text: str) -> dict:
    return bind({
        "schema_version": 1,
        "artifact_kind": kind,
        "artifact_id": artifact_id,
        "text": text,
        "content_sha256": "",
    })


def context_policy(**overrides: object) -> dict:
    value = {
        "include_patch_evaluation": False,
        "include_failure_memory": False,
        "include_diagnostics": False,
        "max_patch_evaluation_bytes": 0,
        "max_failure_events": 0,
        "max_failure_context_bytes": 0,
        "max_diagnostic_bytes_per_stream": 0,
    }
    value.update(overrides)
    return value


PARENT_POLICY = context_policy(
    include_patch_evaluation=True,
    max_patch_evaluation_bytes=4_096,
)
CANDIDATE_POLICY = context_policy(
    include_patch_evaluation=True,
    max_patch_evaluation_bytes=4_096,
    include_diagnostics=True,
    max_diagnostic_bytes_per_stream=2_048,
)
BASE_TEXT = "You are align-coder.\nReturn a minimal patch."
REPO_TEXT = "This repository is written in Align."
OPPORTUNITY_TEXT = (
    "Repair loops repeat the same failing test without citing it.\n"
    "diagnostics: 3 of 5 tasks looped twice; stderr truncated at 512 bytes"
)
CANDIDATE_APPEND = "Always name the failing test and quote its assertion."


def activation_result(learned_append: str = "", policy: dict | None = None) -> dict:
    base = text_artifact("BASE_PROMPT", "base-v1", BASE_TEXT)
    repo = text_artifact("REPO_PROMPT", "repo-v1", REPO_TEXT)
    variant = bind({
        "schema_version": 1,
        "artifact_kind": "PROMPT_VARIANT",
        "variant_id": "baseline-v1",
        "base_prompt": base,
        "repo_prompt": repo,
        "learned_prompt_append": learned_append,
        "context_policy": PARENT_POLICY if policy is None else policy,
        "candidate_id": "BASELINE",
        "content_sha256": "",
    })
    scope = bind({
        "schema_version": 1,
        "artifact_kind": "PROMPT_SCOPE",
        "repo_id": "align-llm",
        "repo_profile_revision": "profile-v1",
        "align_revision": FILLER_DIGEST,
        "corpus_id": "prompt-v1",
        "corpus_revision": bind({
            "schema_version": 1,
            "artifact_kind": "CORPUS_REVISION",
            "source_kind": "GIT_COMMIT",
            "source_repository_id": "align-llm",
            "source_sha256": FILLER_DIGEST,
            "content_sha256": "",
        }),
        "evaluation_provider_kind": "LOCAL_OPENAI",
        "evaluation_provider_model": "evaluation-model",
        "generation_policy_sha256": FILLER_DIGEST,
        "acceptance_policy_sha256": FILLER_DIGEST,
        "base_prompt_sha256": base["content_sha256"],
        "repo_prompt_sha256": repo["content_sha256"],
        "content_sha256": "",
    })
    activation = bind({
        "schema_version": 1,
        "artifact_kind": "PROMPT_ACTIVATION",
        "activation_id": "baseline-v1/activation",
        "operation": "BASELINE",
        "scope": scope,
        "parent_activation_id": "",
        "parent_activation_sha256": "",
        "effective_variant": variant,
        "accepted_evaluation_id": "",
        "accepted_evaluation_sha256": "",
        "rollback_target_activation_id": "",
        "rollback_target_activation_sha256": "",
        "decision_reason": "",
        "content_sha256": "",
    })
    return bind({
        "schema_version": 1,
        "artifact_kind": "PROMPT_ACTIVATION_RESULT",
        "decision_id": "baseline-v1",
        "status": "BASELINED",
        "error_code": "NONE",
        "error": "",
        "activation": activation,
        "content_sha256": "",
    })


def experiment_request(root: pathlib.Path, endpoint: str, **overrides: object) -> dict:
    value = {
        "schema_version": 1,
        "artifact_kind": "PROMPT_EXPERIMENT_REQUEST",
        "experiment_id": "experiment-1",
        "project_root": str(root),
        "parent_activation_path": "activation.json",
        "opportunity_path": "opportunity.json",
        "proposal_provider_kind": "LOCAL_OPENAI",
        "proposal_provider_endpoint": endpoint,
        "proposal_provider_endpoint_id": "fixture-endpoint",
        "proposal_provider_model": "fixture-model",
        "timeout_ns": 20_000_000_000,
        "max_prompt_bytes": 262_144,
        "max_tokens": 512,
        "temperature_micros": 250_000,
    }
    value.update(overrides)
    ordered = [
        "schema_version", "artifact_kind", "experiment_id", "project_root",
        "parent_activation_path", "opportunity_path", "proposal_provider_kind",
        "proposal_provider_endpoint", "proposal_provider_endpoint_id",
        "proposal_provider_model", "api_key_env", "tokenize_endpoint", "timeout_ns",
        "max_prompt_bytes", "max_tokens", "temperature_micros",
    ]
    return {key: value[key] for key in ordered if key in value}


def expected_prompt(activation: dict, opportunity: dict) -> str:
    variant = activation["activation"]["effective_variant"]
    policy = variant["context_policy"]
    learned = variant["learned_prompt_append"] or "(none)"

    def flag(name: str) -> str:
        return "true" if policy[name] else "false"

    return (
        "--- parent activation effective hierarchy ---\n"
        "base prompt:\n"
        f"{variant['base_prompt']['text']}\n"
        "\n"
        "repo prompt:\n"
        f"{variant['repo_prompt']['text']}\n"
        "\n"
        "effective learned append:\n"
        f"{learned}\n"
        "\n"
        "--- parent effective context policy ---\n"
        f"include_patch_evaluation: {flag('include_patch_evaluation')}\n"
        f"include_failure_memory: {flag('include_failure_memory')}\n"
        f"include_diagnostics: {flag('include_diagnostics')}\n"
        f"max_patch_evaluation_bytes: {policy['max_patch_evaluation_bytes']}\n"
        f"max_failure_events: {policy['max_failure_events']}\n"
        f"max_failure_context_bytes: {policy['max_failure_context_bytes']}\n"
        f"max_diagnostic_bytes_per_stream: {policy['max_diagnostic_bytes_per_stream']}\n"
        "\n"
        "--- immutable constraints ---\n"
        "The model does not choose identifiers.\n"
        "The model does not choose scope.\n"
        "The model does not choose the parent activation.\n"
        "The model does not choose acceptance thresholds.\n"
        "The model does not choose evaluation tasks.\n"
        "align-coder validates the proposal and computes candidate_id and content_sha256.\n"
        "The rendered learned append and context policy must differ from the parent effective"
        " variant.\n"
        "\n"
        "--- opportunity ---\n"
        "opportunity id:\n"
        f"{opportunity['artifact_id']}\n"
        "\n"
        "opportunity summary and diagnostics:\n"
        f"{opportunity['text']}\n"
        "\n"
        "--- candidate response schema ---\n"
        "Return exactly one JSON object with these fields and no others:\n"
        '{"schema_version":1,"summary":"<English summary, at most 4096 bytes>",'
        '"learned_prompt_append":"<at most 8192 bytes>","context_policy":{'
        '"include_patch_evaluation":<bool>,"include_failure_memory":<bool>,'
        '"include_diagnostics":<bool>,"max_patch_evaluation_bytes":<integer>,'
        '"max_failure_events":<integer>,"max_failure_context_bytes":<integer>,'
        '"max_diagnostic_bytes_per_stream":<integer>}}\n'
    )


def proposal_text(summary: str, learned_append: str, policy: dict) -> str:
    return json.dumps({
        "schema_version": 1,
        "summary": summary,
        "learned_prompt_append": learned_append,
        "context_policy": policy,
    }, ensure_ascii=False, separators=(",", ":"))


def openai_envelope(content: str) -> bytes:
    return canonical({"choices": [{"message": {"role": "assistant", "content": content}}]})


def llama_envelope(content: str) -> bytes:
    return canonical({"content": content})


def straddling_body(credential: str) -> bytes:
    """A >16 KiB diagnostic body whose only credential occurrence crosses the truncation cap."""
    head = "x" * (DIAGNOSTIC_CAP - 4)
    tail = "y" * 4_096
    return f"{head}{credential}{tail}".encode("utf-8")


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
            self.respond(200, openai_envelope(
                proposal_text("Cite the failing test in every repair turn.", CANDIDATE_APPEND, CANDIDATE_POLICY)
            ))
        elif path == "/llama/ok":
            self.respond(200, llama_envelope(
                proposal_text("Cite the failing test in every repair turn.", CANDIDATE_APPEND, CANDIDATE_POLICY)
            ))
        elif path == "/openai/no-change":
            self.respond(200, openai_envelope(
                proposal_text("Only the summary changed.", "", PARENT_POLICY)
            ))
        elif path == "/openai/bad-envelope":
            self.respond(200, canonical({"choices": []}))
        elif path == "/openai/bad-content":
            self.respond(200, openai_envelope("not a candidate proposal"))
        elif path == "/openai/bad-version":
            self.respond(200, openai_envelope(json.dumps({
                "schema_version": 2,
                "summary": "wrong version",
                "learned_prompt_append": CANDIDATE_APPEND,
                "context_policy": CANDIDATE_POLICY,
            }, separators=(",", ":"))))
        elif path == "/openai/bounds-summary":
            self.respond(200, openai_envelope(
                proposal_text("s" * 4_097, CANDIDATE_APPEND, CANDIDATE_POLICY)
            ))
        elif path == "/openai/bounds-empty-summary":
            self.respond(200, openai_envelope(
                proposal_text("", CANDIDATE_APPEND, CANDIDATE_POLICY)
            ))
        elif path == "/openai/bounds-append":
            self.respond(200, openai_envelope(
                proposal_text("too long an append", "a" * 8_193, CANDIDATE_POLICY)
            ))
        elif path == "/openai/bounds-policy":
            self.respond(200, openai_envelope(proposal_text(
                "inconsistent policy",
                CANDIDATE_APPEND,
                context_policy(include_diagnostics=True, max_diagnostic_bytes_per_stream=0),
            )))
        elif path == "/openai/status-404":
            self.respond(404, canonical({"error": "no such model"}))
        elif path == "/openai/status-503":
            self.respond(503, straddling_body(CREDENTIAL_VALUE), content_type="text/plain")
        elif path == "/openai/over-cap":
            self.respond(200, b"x" * (RESPONSE_CAP + 1))
        elif path == "/openai/non-utf8":
            self.respond(200, b"\xff\xfe\x00\x01", content_type="application/octet-stream")
        # The credential-lifetime family: every response deliberately echoes the credential value
        # back at the client, so any persisted or printed byte of it is a leak the runner catches.
        elif path == "/credential/echo-summary":
            self.respond(200, openai_envelope(proposal_text(
                f"the provider echoed {CREDENTIAL_VALUE} back", CANDIDATE_APPEND, CANDIDATE_POLICY,
            )))
        elif path == "/credential/echo-no-change":
            self.respond(200, openai_envelope(proposal_text(
                f"only the summary changed and it echoes {CREDENTIAL_VALUE}", "", PARENT_POLICY,
            )))
        elif path == "/credential/echo-schema":
            self.respond(200, openai_envelope(f"not a proposal: {CREDENTIAL_VALUE}"))
        elif path == "/credential/echo-bounds":
            self.respond(200, openai_envelope(proposal_text(
                f"{CREDENTIAL_VALUE} " * 400, CANDIDATE_APPEND, CANDIDATE_POLICY,
            )))
        elif path == "/credential/echo-status":
            self.respond(503, f"upstream rejected {CREDENTIAL_VALUE}".encode("utf-8"),
                         content_type="text/plain")
        elif path == "/credential/echo-over-cap":
            payload = (CREDENTIAL_VALUE * 64).encode("utf-8")
            self.respond(200, payload * (RESPONSE_CAP // len(payload) + 1))
        elif path == "/credential/stall":
            self.server.stalled.set()
            self.server.release.wait(timeout=30)
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
    """One prepared `prompt experiment` invocation with its own request and result path."""

    def __init__(self, root: pathlib.Path, name: str) -> None:
        self.root = root
        self.name = name
        self.directory = root / name
        self.directory.mkdir(parents=True, exist_ok=True)
        self.request_path = self.directory / "request.json"
        self.result_path = self.directory / "result.json"

    def write_inputs(
        self,
        *,
        activation: dict | None = None,
        opportunity: dict | None = None,
        activation_bytes: bytes | None = None,
        opportunity_bytes: bytes | None = None,
    ) -> None:
        if activation_bytes is None:
            activation_bytes = canonical(activation if activation is not None else activation_result())
        if opportunity_bytes is None:
            opportunity_bytes = canonical(
                opportunity if opportunity is not None
                else text_artifact("OPPORTUNITY", "opportunity-1", OPPORTUNITY_TEXT)
            )
        (self.directory / "activation.json").write_bytes(activation_bytes)
        (self.directory / "opportunity.json").write_bytes(opportunity_bytes)

    def write_request(self, request: dict | bytes) -> None:
        self.request_path.write_bytes(request if isinstance(request, bytes) else canonical(request))

    def run(self, **keywords: object) -> subprocess.CompletedProcess[str]:
        return invoke(
            ["prompt", "experiment", str(self.request_path), str(self.result_path)],
            **keywords,
        )

    def result(self) -> dict:
        require(self.result_path.is_file(), f"{self.name}: no result artifact was published")
        return json.loads(self.result_path.read_text(encoding="utf-8"))


def prepare(
    root: pathlib.Path,
    name: str,
    endpoint: str,
    *,
    activation: dict | None = None,
    opportunity: dict | None = None,
    activation_bytes: bytes | None = None,
    opportunity_bytes: bytes | None = None,
    **request_overrides: object,
) -> Case:
    case = Case(root, name)
    case.write_inputs(
        activation=activation,
        opportunity=opportunity,
        activation_bytes=activation_bytes,
        opportunity_bytes=opportunity_bytes,
    )
    case.write_request(experiment_request(case.directory, endpoint, **request_overrides))
    return case


def assert_status(
    case: Case,
    completed: subprocess.CompletedProcess[str],
    status: str,
    error_code: str,
) -> dict:
    require(
        completed.returncode == (0 if status == "PROPOSED" else 2),
        f"{case.name}: unexpected exit {completed.returncode}: {completed.stderr}",
    )
    require(
        f"\n{status}\n" in completed.stdout,
        f"{case.name}: stdout did not report {status}: {completed.stdout!r}",
    )
    result = case.result()
    require(
        result["status"] == status and result["error_code"] == error_code,
        f"{case.name}: expected {status}/{error_code}, got"
        f" {result['status']}/{result['error_code']} ({result['error']})",
    )
    require(
        result["schema_version"] == 1 and result["artifact_kind"] == "PROMPT_EXPERIMENT_RESULT",
        f"{case.name}: wrong result envelope: {result!r}",
    )
    claimed = result["content_sha256"]
    recomputed = dict(result)
    recomputed["content_sha256"] = ""
    require(
        hashlib.sha256(canonical(recomputed)).hexdigest() == claimed,
        f"{case.name}: result content digest does not bind the record",
    )
    return result
