#!/usr/bin/env python3
"""Closed-environment process owner for the G1 GPU qualifier."""

from __future__ import annotations

import dataclasses
import hashlib
import os
import pathlib
import selectors
import signal
import stat
import subprocess
import time
from collections.abc import Mapping, Sequence

from gpu_backend_recipe import MAX_BUNDLE_ARTIFACT_BYTES, RecipeError
from gpu_qualification_records import validate_command


LOG_LIMIT = 4 * 1024 * 1024
READ_CHUNK = 64 * 1024
POLL_SECONDS = 0.05
KILL_GRACE_SECONDS = 1.0


@dataclasses.dataclass(frozen=True)
class CapturedLog:
    retained: bytes
    original_bytes: int
    original_sha256: str

    @property
    def truncated(self) -> bool:
        return self.original_bytes > len(self.retained)


@dataclasses.dataclass(frozen=True)
class OwnedCommandResult:
    command: dict[str, object]
    terminal: str
    exit_code: int | None
    signal: int | None
    stdout: CapturedLog
    stderr: CapturedLog
    descendants_before: int
    descendants_after: int
    elapsed_ns: int


def retained_file_row(role: str, path: str, captured: CapturedLog) -> dict[str, object]:
    """Describe a retained bounded log with its complete-stream identity."""
    return {
        "role": role,
        "path": path,
        "bytes": len(captured.retained),
        "sha256": hashlib.sha256(captured.retained).hexdigest(),
        "original_bytes": captured.original_bytes,
        "original_sha256": captured.original_sha256,
        "truncated": captured.truncated,
    }


class _LogSink:
    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.retained = bytearray()
        self.original_bytes = 0
        self.digest = hashlib.sha256()

    def add(self, data: bytes) -> None:
        self.original_bytes += len(data)
        self.digest.update(data)
        remaining = self.limit - len(self.retained)
        if remaining > 0:
            self.retained.extend(data[:remaining])

    def finish(self) -> CapturedLog:
        return CapturedLog(
            retained=bytes(self.retained),
            original_bytes=self.original_bytes,
            original_sha256=self.digest.hexdigest(),
        )


def _private_directory(path: pathlib.Path, label: str) -> pathlib.Path:
    if not path.is_absolute():
        raise RecipeError(f"{label} is not absolute")
    try:
        metadata = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise RecipeError(f"{label} cannot be inspected") from exc
    if not stat.S_ISDIR(metadata.st_mode) or metadata.st_mode & 0o077:
        raise RecipeError(f"{label} is not a private directory")
    return path.resolve(strict=True)


def _single_link_sha256(path: pathlib.Path, label: str) -> str:
    if not path.is_absolute():
        raise RecipeError(f"{label} is not absolute")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 \
                or before.st_size > MAX_BUNDLE_ARTIFACT_BYTES:
            raise RecipeError(f"{label} is not a single-link regular file")
        digest = hashlib.sha256()
        total = 0
        while True:
            chunk = os.read(descriptor, READ_CHUNK)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_BUNDLE_ARTIFACT_BYTES:
                raise RecipeError(f"{label} exceeds its byte bound")
            digest.update(chunk)
        after = os.fstat(descriptor)
    except OSError as exc:
        raise RecipeError(f"{label} cannot be read") from exc
    finally:
        if "descriptor" in locals():
            os.close(descriptor)
    identity = ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")
    if total != before.st_size or any(
        getattr(before, field) != getattr(after, field) for field in identity
    ):
        raise RecipeError(f"{label} changed while it was verified")
    return digest.hexdigest()


def _is_beneath(path: pathlib.Path, roots: tuple[pathlib.Path, ...]) -> bool:
    try:
        resolved = path.resolve(strict=True)
    except OSError:
        return False
    return any(resolved == root or root in resolved.parents for root in roots)


def _verify_argv(
    physical_argv: Sequence[str], logical_argv: Sequence[str], mappings: Mapping[str, pathlib.Path],
    owned_roots: tuple[pathlib.Path, ...],
) -> None:
    if len(physical_argv) != len(logical_argv) or not physical_argv:
        raise RecipeError("physical and logical argv do not match")
    for ordinal, (physical, logical) in enumerate(zip(physical_argv, logical_argv, strict=True)):
        if logical.startswith("<"):
            if logical not in mappings:
                raise RecipeError(f"logical argv[{ordinal}] has no physical mapping")
            mapped = mappings[logical]
            if str(mapped) != physical:
                raise RecipeError(f"logical argv[{ordinal}] mapping changed")
            if ":sha256:" in logical:
                expected = logical.rsplit(":sha256:", 1)[1]
                if _single_link_sha256(mapped, f"argv[{ordinal}]") != expected:
                    raise RecipeError(f"logical argv[{ordinal}] digest does not match")
            elif not _is_beneath(mapped, owned_roots):
                raise RecipeError(f"logical argv[{ordinal}] is outside owned roots")
        elif physical != logical:
            raise RecipeError(f"literal argv[{ordinal}] changed")
    extra = set(mappings) - {item for item in logical_argv if item.startswith("<")}
    if extra:
        raise RecipeError("unused logical path mapping")


def _group_member_count(group: int) -> int:
    ps = pathlib.Path("/bin/ps")
    if not ps.is_file():
        ps = pathlib.Path("/usr/bin/ps")
    if not ps.is_file():
        raise RecipeError("process-group inspection is unavailable")
    try:
        completed = subprocess.run(
            (str(ps), "-axo", "pid=,pgid="),
            env={"LC_ALL": "C"},
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RecipeError("process-group inspection failed") from exc
    if len(completed.stdout) > 8 * 1024 * 1024:
        raise RecipeError("process-group inspection exceeded its bound")
    count = 0
    for line in completed.stdout.splitlines():
        fields = line.split()
        if len(fields) == 2:
            try:
                member_group = int(fields[1])
            except ValueError:
                continue
            if member_group == group:
                count += 1
    return count


def _terminate_group(process: subprocess.Popen[bytes], grace_seconds: float) -> None:
    group = process.pid
    try:
        os.killpg(group, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        pass
    deadline = time.monotonic() + grace_seconds
    while _group_member_count(group) and time.monotonic() < deadline:
        time.sleep(POLL_SECONDS)
    if _group_member_count(group):
        try:
            os.killpg(group, signal.SIGKILL)
        except ProcessLookupError:
            return
        except PermissionError:
            pass
        deadline = time.monotonic() + grace_seconds
        while _group_member_count(group) and time.monotonic() < deadline:
            time.sleep(POLL_SECONDS)
        if _group_member_count(group):
            raise RecipeError("command process group could not be killed")


def _drain(
    selector: selectors.BaseSelector, sinks: Mapping[int, _LogSink], maximum_wait: float,
) -> None:
    deadline = time.monotonic() + maximum_wait
    while selector.get_map() and time.monotonic() < deadline:
        for key, _ in selector.select(POLL_SECONDS):
            try:
                chunk = os.read(key.fd, READ_CHUNK)
            except BlockingIOError:
                continue
            if chunk:
                sinks[key.fd].add(chunk)
            else:
                selector.unregister(key.fd)


def run_owned_command(
    *,
    kind: str,
    physical_argv: Sequence[str],
    logical_argv: Sequence[str],
    mappings: Mapping[str, pathlib.Path],
    cwd: pathlib.Path,
    home: pathlib.Path,
    temporary: pathlib.Path,
    timeout_seconds: float,
    log_limit: int = LOG_LIMIT,
    spawn: object = subprocess.Popen,
) -> OwnedCommandResult:
    """Run one verified command in a new group and return bounded complete-log identities."""
    if not 0 < timeout_seconds <= 60 * 60 or not 0 <= log_limit <= LOG_LIMIT:
        raise RecipeError("command timeout or log bound is invalid")
    home_root = _private_directory(home, "command HOME")
    temporary_root = _private_directory(temporary, "command TMPDIR")
    cwd_root = _private_directory(cwd, "command cwd")
    logical_environment = ["HOME=<home>:owned", "LC_ALL=C", "TMPDIR=<tmp>:owned", "TZ=UTC"]
    command = {
        "kind": kind,
        "argv": list(logical_argv),
        "environment": logical_environment,
        "sha256": "0" * 64,
    }
    from gpu_qualification_records import command_digest
    command["sha256"] = command_digest(kind, command["argv"], logical_environment)
    validate_command(command, allow_sentinel=False, expected_kind=kind)
    _verify_argv(physical_argv, logical_argv, mappings, (home_root, temporary_root, cwd_root))
    executable = pathlib.Path(physical_argv[0])
    _single_link_sha256(executable, "command executable")

    actual_environment = {
        "HOME": str(home_root),
        "LC_ALL": "C",
        "TMPDIR": str(temporary_root),
        "TZ": "UTC",
    }
    started_ns = time.monotonic_ns()
    process = spawn(
        tuple(physical_argv), cwd=cwd_root, env=actual_environment, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True, close_fds=True,
    )
    if process.stdout is None or process.stderr is None:
        raise RecipeError("command log pipes were not created")
    selector = selectors.DefaultSelector()
    sinks: dict[int, _LogSink] = {}
    for pipe in (process.stdout, process.stderr):
        os.set_blocking(pipe.fileno(), False)
        selector.register(pipe.fileno(), selectors.EVENT_READ)
        sinks[pipe.fileno()] = _LogSink(log_limit)

    timed_out = False
    deadline = time.monotonic() + timeout_seconds
    while process.poll() is None and time.monotonic() < deadline:
        _drain(selector, sinks, POLL_SECONDS)
    if process.poll() is None:
        timed_out = True
        descendants_before = _group_member_count(process.pid)
        _terminate_group(process, KILL_GRACE_SECONDS)
    else:
        descendants_before = _group_member_count(process.pid)
        if descendants_before:
            _terminate_group(process, KILL_GRACE_SECONDS)
    try:
        process.wait(timeout=KILL_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        _terminate_group(process, 0)
        process.wait(timeout=KILL_GRACE_SECONDS)
    _drain(selector, sinks, KILL_GRACE_SECONDS)
    for fd in list(selector.get_map()):
        selector.unregister(fd)
    selector.close()
    process.stdout.close()
    process.stderr.close()
    descendants_after = _group_member_count(process.pid)

    returncode = process.returncode
    if timed_out:
        terminal, exit_code, signal_number = "TIMEOUT", None, None
    elif returncode is not None and returncode < 0:
        terminal, exit_code, signal_number = "SIGNAL", None, -returncode
    elif returncode == 0:
        terminal, exit_code, signal_number = "PASS", 0, None
    else:
        terminal, exit_code, signal_number = "FAIL", returncode, None
    sink_values = list(sinks.values())
    return OwnedCommandResult(
        command=command,
        terminal=terminal,
        exit_code=exit_code,
        signal=signal_number,
        stdout=sink_values[0].finish(),
        stderr=sink_values[1].finish(),
        descendants_before=descendants_before,
        descendants_after=descendants_after,
        elapsed_ns=max(1, time.monotonic_ns() - started_ns),
    )
