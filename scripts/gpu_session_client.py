"""Caller-owned serial client for the G1R runtime worker."""
from __future__ import annotations

import json
import os
import selectors
import signal
import struct
import subprocess
import tempfile
import time


class SessionError(RuntimeError):
    pass


class InvalidRequest(SessionError):
    pass


class Session:
    def __init__(self, command: list[str], timeout: float = 300):
        if not command or timeout <= 0:
            raise ValueError("a worker command and positive timeout are required")
        self.timeout = timeout
        self.process = None
        self.log = tempfile.TemporaryFile()
        try:
            self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                            stderr=self.log, start_new_session=True)
            os.set_blocking(self.process.stdin.fileno(), False)
            os.set_blocking(self.process.stdout.fileno(), False)
            ready = self._read(time.monotonic() + timeout)
            if not isinstance(ready, dict) or type(ready.get("schema_version")) is not int or ready != {"schema_version": 1, "status": "ready"}:
                raise SessionError("worker did not acknowledge session construction")
        except BaseException as error:
            self.log.seek(0, os.SEEK_END)
            self.log.seek(max(0, self.log.tell() - 4096))
            diagnostic = self.log.read().decode("utf-8", "replace")
            self.close()
            if isinstance(error, Exception):
                raise SessionError(f"{error}; worker diagnostic: {diagnostic}") from error
            raise

    def _wait(self, fd: int, event: int, deadline: float):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise SessionError("worker request deadline exceeded")
        with selectors.DefaultSelector() as selector:
            selector.register(fd, event)
            if not selector.select(remaining):
                raise SessionError("worker request deadline exceeded")

    def _receive(self, count: int, deadline: float) -> bytes:
        fd = self.process.stdout.fileno()
        result = bytearray()
        while len(result) < count:
            self._wait(fd, selectors.EVENT_READ, deadline)
            try:
                chunk = os.read(fd, min(count - len(result), 65536))
            except BlockingIOError:
                continue
            if not chunk:
                raise SessionError("worker closed its output before completing a frame")
            result.extend(chunk)
        return bytes(result)

    def _read(self, deadline: float):
        count = struct.unpack("<I", self._receive(4, deadline))[0]
        if not 1 <= count <= 2097152:
            raise SessionError("worker response exceeds its frame bound")
        raw = self._receive(count, deadline)
        def fields(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise SessionError("duplicate worker response field")
                result[key] = value
            return result
        def invalid_constant(value):
            raise SessionError(f"nonfinite worker response scalar: {value}")
        try:
            return json.loads(raw.decode("utf-8"), object_pairs_hook=fields,
                              parse_constant=invalid_constant)
        except (UnicodeError, ValueError) as error:
            raise SessionError("invalid worker response JSON") from error

    def generate(self, request: dict) -> dict:
        raw = json.dumps(request, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
        if not 1 <= len(raw) <= 1048576:
            raise InvalidRequest("request exceeds its frame bound")
        if self.process is None or self.process.poll() is not None:
            raise SessionError("worker session is closed")
        deadline = time.monotonic() + self.timeout
        try:
            pending = memoryview(struct.pack("<I", len(raw)) + raw)
            fd = self.process.stdin.fileno()
            while pending:
                self._wait(fd, selectors.EVENT_WRITE, deadline)
                try:
                    count = os.write(fd, pending)
                except BlockingIOError:
                    continue
                if count <= 0:
                    raise SessionError("worker request write made no progress")
                pending = pending[count:]
            response = self._read(deadline)
            if isinstance(response, dict) and type(response.get("schema_version")) is int and response == {"schema_version": 1, "status": "invalid"}:
                raise InvalidRequest("worker rejected request syntax or model limits")
            if not isinstance(response, dict) or set(response) != {"schema_version", "status", "result"}:
                raise SessionError("worker generation failed or returned an invalid envelope")
            if type(response["schema_version"]) is not int or response["schema_version"] != 1 or response["status"] != "ok":
                raise SessionError("invalid worker generation envelope")
            result = response["result"]
            required = {"schema_version", "operation", "provider", "model", "endpoint", "status", "output",
                        "prompt_tokens", "completion_tokens", "total_tokens", "token_count_exact",
                        "elapsed_ns", "error", "error_code"}
            if not isinstance(result, dict) or set(result) != required:
                raise SessionError("invalid provider result fields")
            if type(result["schema_version"]) is not int or result["schema_version"] != 2 or result["operation"] != "generate" or result["provider"] != "align-runtime" or result["status"] != "ok":
                raise SessionError("invalid provider result identity")
            if not isinstance(result["model"], str) or result["endpoint"] != "" or result["error"] != "" or type(result["error_code"]) is not int or result["error_code"] != -1:
                raise SessionError("invalid provider result metadata")
            if not isinstance(result["output"], str) or len(result["output"].encode()) > 262144:
                raise SessionError("invalid provider output")
            for key in ("prompt_tokens", "completion_tokens", "total_tokens", "elapsed_ns"):
                if type(result[key]) is not int or result[key] < 0:
                    raise SessionError("invalid provider result count")
            if result["total_tokens"] != result["prompt_tokens"] + result["completion_tokens"] or result["token_count_exact"] is not True:
                raise SessionError("inconsistent provider token counts")
            return result
        except InvalidRequest:
            raise
        except BaseException as error:
            self.log.seek(0, os.SEEK_END)
            self.log.seek(max(0, self.log.tell() - 4096))
            diagnostic = self.log.read().decode("utf-8", "replace")
            self.close()
            if isinstance(error, Exception):
                raise SessionError(f"{error}; worker diagnostic: {diagnostic}") from error
            raise

    def close(self):
        process, self.process = self.process, None
        if process is not None:
            if process.stdin is not None:
                process.stdin.close()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait(timeout=5)
            # A worker that exits early may leave a child holding the process group/pipes.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            if process.stdout is not None:
                process.stdout.close()
        self.log.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
