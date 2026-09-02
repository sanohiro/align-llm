"""Shared retained-log capture and terminal reduction for verification commands."""

from __future__ import annotations

import argparse
import collections
import errno
import hashlib
import json
import os
import re
import signal
import stat
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


SCHEMA_VERSION = 1
DEFAULT_PROGRESS_SECONDS = 60
MIN_PROGRESS_SECONDS = 1
MAX_PROGRESS_SECONDS = 3_600
MAX_FAILURE_LINES = 40
MAX_FAILURE_BYTES = 12_288
MAX_DIAGNOSTIC_RECORDS = 24
MAX_DIAGNOSTIC_BYTES = 8_192
MAX_DIAGNOSTIC_TEXT_BYTES = 2_048
MAX_RETAINED_LINE_PREFIX = 4_096
PROCESS_GROUP_CLEANUP_SECONDS = 2.0
SIGNAL_CLEANUP_SECONDS = 5.0
CHILD_POLL_SECONDS = 0.25
OUTPUT_DIRECTORY_VARIABLE = "ALIGN_LLM_OUTPUT_DIRECTORY"
ACTIVE_VARIABLE = "ALIGN_LLM_OUTPUT_SUMMARY_ACTIVE"
PHASE = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}\Z", re.ASCII)
ALIGN_WARNING = re.compile(rb"^.+:[0-9]+:[0-9]+: warning: ([^:\r\n]+)", re.ASCII)
ACTIONABLE = re.compile(
    rb"(?:^|[ :])(?:error|fatal|traceback|exception)(?:[ :]|$)"
    rb"|(?:^| )(?:cannot |not found|no such |denied|failed|failure|mismatch|differs|"
    rb"timed out|timeout|killed|signal |refused)",
    re.IGNORECASE,
)
SIGNALS = tuple(
    selected
    for selected in (
        getattr(signal, "SIGHUP", None),
        signal.SIGINT,
        getattr(signal, "SIGQUIT", None),
        signal.SIGTERM,
        getattr(signal, "SIGPIPE", None),
    )
    if selected is not None
)
ALIGN_CLASSES = {
    b"huge struct copy": "align:huge-struct-copy",
    b"lossy conversion": "align:lossy-conversion",
    b"unused import": "align:unused-import",
    b"unnecessary heap allocation": "align:unnecessary-heap-allocation",
    b"unconstrained element type": "align:unconstrained-element-type",
}


class OutputSummaryError(RuntimeError):
    """Raised when the wrapper cannot establish or finalize its ownership boundary."""


@dataclass(frozen=True)
class RetainedLine:
    data: bytes
    truncated: bool


@dataclass(frozen=True)
class LogAnalysis:
    byte_count: int
    line_count: int
    sha256: str
    warning_counts: Mapping[str, int]
    first_actionable: RetainedLine | None
    useful_tail: tuple[RetainedLine, ...]


def compact_record(event: str, **fields: object) -> bytes:
    record = {"event": event, "version": SCHEMA_VERSION, **fields}
    return (
        json.dumps(record, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def emit_record(descriptor: int, event: str, **fields: object) -> bool:
    return emit_bytes(descriptor, compact_record(event, **fields))


def emit_bytes(descriptor: int, value: bytes) -> bool:
    pending = memoryview(value)
    try:
        while pending:
            written = os.write(descriptor, pending)
            if written <= 0:
                raise OSError(errno.EIO, "summary write made no progress")
            pending = pending[written:]
        return True
    except OSError as error:
        if error.errno in (errno.EPIPE, errno.EBADF):
            return False
        raise


def parse(arguments: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--log-directory")
    parser.add_argument("--progress-seconds", type=int, default=DEFAULT_PROGRESS_SECONDS)
    try:
        separator = arguments.index("--")
    except ValueError:
        parser.error("command must follow --")
    values = parser.parse_args(arguments[:separator])
    values.command = list(arguments[separator + 1 :])
    if PHASE.fullmatch(values.phase) is None:
        parser.error("phase must match [a-z0-9][a-z0-9._-]{0,63}")
    if not values.command:
        parser.error("command must not be empty")
    if not MIN_PROGRESS_SECONDS <= values.progress_seconds <= MAX_PROGRESS_SECONDS:
        parser.error("progress seconds must be in 1..3600")
    if values.log_directory == "":
        parser.error("log directory must not be empty")
    if (
        values.log_directory is None
        and OUTPUT_DIRECTORY_VARIABLE in os.environ
        and not os.environ[OUTPUT_DIRECTORY_VARIABLE]
    ):
        parser.error(f"{OUTPUT_DIRECTORY_VARIABLE} must not be empty")
    return values


def git_common_directory(repository: Path) -> Path:
    try:
        result = subprocess.run(
            ("git", "rev-parse", "--git-common-dir"),
            cwd=repository,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as error:
        raise OutputSummaryError(f"cannot resolve Git common directory: {error}") from error
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise OutputSummaryError(detail or "cannot resolve Git common directory")
    try:
        value = result.stdout.decode("utf-8", "strict").strip()
    except UnicodeError as error:
        raise OutputSummaryError("Git common directory is not UTF-8") from error
    if not value or "\x00" in value or "\n" in value or "\r" in value:
        raise OutputSummaryError("Git returned an invalid common directory")
    selected = Path(value)
    if not selected.is_absolute():
        selected = repository / selected
    try:
        return selected.resolve(strict=True)
    except OSError as error:
        raise OutputSummaryError(f"cannot resolve Git common directory: {error}") from error


def resolve_log_directory(
    explicit: str | os.PathLike[str] | None,
    repository: Path,
    environment: Mapping[str, str],
) -> Path:
    selected: Path
    if explicit is not None:
        if not os.fspath(explicit):
            raise OutputSummaryError("log directory must not be empty")
        selected = Path(explicit)
    elif OUTPUT_DIRECTORY_VARIABLE in environment:
        value = environment[OUTPUT_DIRECTORY_VARIABLE]
        if not value:
            raise OutputSummaryError(f"{OUTPUT_DIRECTORY_VARIABLE} must not be empty")
        selected = Path(value)
    else:
        selected = git_common_directory(repository) / "align-llm-output"
    if not selected.is_absolute():
        selected = repository / selected
    return selected.absolute()


def canonical_phase(label: str) -> str:
    lowered = label.lower()
    normalized = re.sub(r"[^a-z0-9._-]+", "-", lowered, flags=re.ASCII).strip("-._")
    if not normalized:
        normalized = "verification"
    if len(normalized) > 64:
        suffix = hashlib.sha256(label.encode("utf-8")).hexdigest()[:12]
        normalized = normalized[:51].rstrip("-._") + "-" + suffix
    if PHASE.fullmatch(normalized) is None:
        raise OutputSummaryError("cannot canonicalize verification phase")
    return normalized


def admit_log_directory(directory: Path) -> None:
    try:
        metadata = directory.lstat()
    except FileNotFoundError:
        try:
            directory.mkdir(mode=0o700, parents=True)
        except FileExistsError:
            pass
        except OSError as error:
            raise OutputSummaryError(f"cannot create log directory: {error}") from error
        try:
            metadata = directory.lstat()
        except OSError as error:
            raise OutputSummaryError(f"cannot inspect created log directory: {error}") from error
    except OSError as error:
        raise OutputSummaryError(f"cannot inspect log directory: {error}") from error
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise OutputSummaryError("log directory must be a real directory")


def reserve_log(directory: Path, phase: str) -> tuple[int, Path]:
    admit_log_directory(directory)
    try:
        descriptor, name = tempfile.mkstemp(prefix=f"{phase}-", suffix=".log", dir=directory)
    except OSError as error:
        raise OutputSummaryError(f"cannot reserve log: {error}") from error
    return descriptor, Path(name).absolute()


def warning_class(line: bytes) -> str | None:
    stripped = line.rstrip(b"\r\n")
    lowered = stripped.lower()
    matched = ALIGN_WARNING.match(stripped)
    if matched is not None:
        detail = matched.group(1).strip().lower()
        for prefix, selected_class in ALIGN_CLASSES.items():
            if detail == prefix or detail.startswith(prefix + b" "):
                return selected_class
        return "align:other"
    if lowered.startswith(b"warning:"):
        detail = lowered[len(b"warning:") :].strip()
        if b"deprecated" in detail:
            return "tool:deprecated"
        if b"unused" in detail:
            return "tool:unused"
        if b"never used" in detail or b"dead code" in detail:
            return "tool:dead-code"
        if b"pgo" in detail or b"profile" in detail:
            return "tool:pgo"
        return "tool:other"
    if lowered.startswith(b"hint:"):
        return "git:hint"
    if b"warning:" in lowered:
        return "other"
    return None


def retained_prefix(line: bytes) -> RetainedLine:
    stripped = line.rstrip(b"\r\n")
    return RetainedLine(stripped[:MAX_RETAINED_LINE_PREFIX], len(stripped) > MAX_RETAINED_LINE_PREFIX)


def analyze_log(path: Path) -> LogAnalysis:
    digest = hashlib.sha256()
    byte_count = 0
    line_count = 0
    warnings: collections.Counter[str] = collections.Counter()
    first: RetainedLine | None = None
    useful: collections.deque[RetainedLine] = collections.deque(maxlen=MAX_DIAGNOSTIC_RECORDS)
    raw_tail: collections.deque[RetainedLine] = collections.deque(maxlen=MAX_DIAGNOSTIC_RECORDS)
    try:
        with path.open("rb") as source:
            for line in source:
                digest.update(line)
                byte_count += len(line)
                line_count += 1
                retained = retained_prefix(line)
                raw_tail.append(retained)
                selected_class = warning_class(line)
                if selected_class is not None:
                    warnings[selected_class] += 1
                    continue
                if not retained.data:
                    continue
                useful.append(retained)
                if first is None and ACTIONABLE.search(retained.data) is not None:
                    first = retained
    except OSError as error:
        raise OutputSummaryError(f"cannot read retained log: {error}") from error
    tail = tuple(useful if useful else raw_tail)
    return LogAnalysis(
        byte_count=byte_count,
        line_count=line_count,
        sha256=digest.hexdigest(),
        warning_counts=dict(warnings),
        first_actionable=first,
        useful_tail=tail,
    )


def bounded_text(line: RetainedLine, maximum: int = MAX_DIAGNOSTIC_TEXT_BYTES) -> tuple[str, bool]:
    decoded = line.data.decode("utf-8", "replace")
    if len(decoded.encode("utf-8")) <= maximum:
        return decoded, line.truncated
    suffix = "..."
    budget = maximum - len(suffix)
    encoded = decoded.encode("utf-8")[: max(0, budget)]
    while True:
        try:
            prefix = encoded.decode("utf-8", "strict")
            break
        except UnicodeDecodeError as error:
            encoded = encoded[: error.start]
    return prefix + suffix, True


def terminal_records(
    *,
    phase: str,
    elapsed_ms: int,
    returncode: int,
    path: Path,
    analysis: LogAnalysis,
    launch_detail: str | None = None,
    forced_signal: int | None = None,
) -> list[bytes]:
    selected_signal = forced_signal if forced_signal is not None else (-returncode if returncode < 0 else None)
    result = "SIGNAL" if selected_signal is not None else ("PASS" if returncode == 0 else "FAIL")
    status = selected_signal if selected_signal is not None else returncode
    fixed = [
        compact_record(
            "verification-result",
            elapsed_ms=elapsed_ms,
            phase=phase,
            result=result,
            status=status,
        )
    ]
    for selected_class in sorted(analysis.warning_counts):
        fixed.append(
            compact_record(
                "verification-warning",
                **{
                    "class": selected_class,
                    "count": analysis.warning_counts[selected_class],
                    "phase": phase,
                },
            )
        )
    fixed.append(
        compact_record(
            "verification-log",
            **{
                "bytes": analysis.byte_count,
                "lines": analysis.line_count,
                "path": os.fspath(path),
                "phase": phase,
                "sha256": analysis.sha256,
            },
        )
    )
    if result == "PASS":
        return fixed

    first_line = (
        RetainedLine(launch_detail.encode("utf-8", "replace"), False)
        if launch_detail is not None
        else analysis.first_actionable
    )
    first_record: bytes | None = None
    if first_line is not None:
        text, truncated = bounded_text(first_line)
        first_record = compact_record(
            "verification-diagnostic-first",
            phase=phase,
            text=text,
            truncated=truncated,
        )

    tail: list[bytes] = []
    for ordinal, line in enumerate(analysis.useful_tail, 1):
        text, truncated = bounded_text(line)
        tail.append(
            compact_record(
                "verification-diagnostic",
                ordinal=ordinal,
                phase=phase,
                text=text,
                truncated=truncated,
            )
        )
    while tail and sum(map(len, tail)) > MAX_DIAGNOSTIC_BYTES:
        tail.pop(0)
    records = fixed + ([first_record] if first_record is not None else []) + tail
    while tail and (len(records) > MAX_FAILURE_LINES or sum(map(len, records)) > MAX_FAILURE_BYTES):
        tail.pop(0)
        records = fixed + ([first_record] if first_record is not None else []) + tail
    if sum(map(len, records)) > MAX_FAILURE_BYTES and first_record is not None and first_line is not None:
        text, _ = bounded_text(first_line, 256)
        first_record = compact_record(
            "verification-diagnostic-first",
            phase=phase,
            text=text,
            truncated=True,
        )
        records = fixed + [first_record] + tail
    return records


def emit_error(descriptor: int, phase: str, detail: str, status: int = 125) -> bool:
    text, _ = bounded_text(RetainedLine(detail.encode("utf-8", "replace"), False), 1_024)
    return emit_record(
        descriptor,
        "verification-error",
        detail=text,
        phase=phase,
        status=status,
    )


def self_signal(signum: int) -> None:
    signal.signal(signum, signal.SIG_DFL)
    os.kill(os.getpid(), signum)
    os._exit(128 + signum)


def process_group_exists(group: int) -> bool:
    try:
        os.killpg(group, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def stop_remaining_process_group(group: int) -> tuple[bool, bool]:
    """Return whether the direct child left a group behind and whether cleanup completed."""
    if not process_group_exists(group):
        return False, True
    try:
        os.killpg(group, signal.SIGTERM)
    except ProcessLookupError:
        return True, True
    deadline = time.monotonic() + PROCESS_GROUP_CLEANUP_SECONDS
    while time.monotonic() < deadline:
        if not process_group_exists(group):
            return True, True
        time.sleep(0.02)
    try:
        os.killpg(group, signal.SIGKILL)
    except ProcessLookupError:
        return True, True
    deadline = time.monotonic() + PROCESS_GROUP_CLEANUP_SECONDS
    while time.monotonic() < deadline:
        if not process_group_exists(group):
            return True, True
        time.sleep(0.02)
    return True, False


def run_command(
    arguments: Sequence[str],
    *,
    phase: str,
    repository: Path,
    environment: Mapping[str, str] | None = None,
    log_directory: str | os.PathLike[str] | None = None,
    progress_seconds: int = DEFAULT_PROGRESS_SECONDS,
    output_descriptor: int = 2,
) -> int:
    selected_environment = dict(os.environ if environment is None else environment)
    selected_environment["PYTHONDONTWRITEBYTECODE"] = "1"
    selected_environment[ACTIVE_VARIABLE] = "1"
    try:
        directory = resolve_log_directory(log_directory, repository, selected_environment)
        descriptor, path = reserve_log(directory, phase)
    except OutputSummaryError as error:
        if not emit_error(output_descriptor, phase, str(error)):
            self_signal(signal.SIGPIPE)
        return 125

    child: subprocess.Popen[bytes] | None = None
    pending_signal: int | None = None
    termination_deadline_ns: int | None = None
    output_broken = False
    prior_handlers: dict[int, signal.Handlers] = {}

    def handle_signal(signum: int, _frame: object) -> None:
        nonlocal pending_signal, termination_deadline_ns
        if pending_signal is None:
            pending_signal = signum
            termination_deadline_ns = (
                time.monotonic_ns() + int(SIGNAL_CLEANUP_SECONDS * 1_000_000_000)
            )
        if child is not None:
            try:
                os.killpg(child.pid, signum)
            except ProcessLookupError:
                pass

    try:
        for selected_signal in SIGNALS:
            prior_handlers[selected_signal] = signal.getsignal(selected_signal)
            signal.signal(selected_signal, handle_signal)
    except (OSError, ValueError) as error:
        for selected_signal, previous in prior_handlers.items():
            signal.signal(selected_signal, previous)
        os.close(descriptor)
        if not emit_error(output_descriptor, phase, f"cannot install signal ownership: {error}"):
            self_signal(signal.SIGPIPE)
        return 125

    started = time.monotonic_ns()
    launch_detail: str | None = None
    returncode = 125
    finalization_error: OutputSummaryError | None = None
    writer = os.fdopen(descriptor, "wb", buffering=0)
    try:
        try:
            child = subprocess.Popen(
                tuple(arguments),
                cwd=repository,
                env=selected_environment,
                stdin=None,
                stdout=writer,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        except FileNotFoundError as error:
            returncode = 127
            launch_detail = f"launch error: {error}"
        except OSError as error:
            returncode = 126
            launch_detail = f"launch error: {error}"
        else:
            if pending_signal is not None:
                try:
                    os.killpg(child.pid, pending_signal)
                except ProcessLookupError:
                    pass
            interval_ns = progress_seconds * 1_000_000_000
            next_progress = started + interval_ns
            while True:
                now = time.monotonic_ns()
                deadline = min(next_progress, now + int(CHILD_POLL_SECONDS * 1_000_000_000))
                if termination_deadline_ns is not None:
                    deadline = min(deadline, termination_deadline_ns)
                remaining = max(0, deadline - now) / 1_000_000_000
                try:
                    returncode = child.wait(timeout=remaining)
                    break
                except subprocess.TimeoutExpired:
                    now = time.monotonic_ns()
                    if termination_deadline_ns is not None and now >= termination_deadline_ns:
                        try:
                            os.killpg(child.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        termination_deadline_ns = None
                        continue
                    if now >= next_progress and not output_broken:
                        output_broken = not emit_record(
                            output_descriptor,
                            "verification-progress",
                            elapsed_ms=max(0, (now - started) // 1_000_000),
                            phase=phase,
                        )
                        if output_broken:
                            handle_signal(signal.SIGPIPE, None)
                    if now >= next_progress:
                        while next_progress <= now:
                            next_progress += interval_ns
            group_remained, group_cleaned = stop_remaining_process_group(child.pid)
            if group_remained and pending_signal is None and returncode == 0:
                returncode = 125
                launch_detail = (
                    "cleanup error: child process group outlived the direct child"
                    if group_cleaned
                    else "cleanup error: child process group survived SIGTERM and SIGKILL"
                )
        try:
            writer.flush()
            os.fsync(writer.fileno())
        except OSError as error:
            finalization_error = OutputSummaryError(f"cannot finalize retained log: {error}")
    finally:
        try:
            writer.close()
        except OSError as error:
            if finalization_error is None:
                finalization_error = OutputSummaryError(f"cannot close retained log: {error}")

    elapsed_ms = max(0, (time.monotonic_ns() - started) // 1_000_000)
    if finalization_error is None:
        try:
            analysis = analyze_log(path)
        except OutputSummaryError as error:
            finalization_error = error
    if finalization_error is not None:
        if not output_broken:
            emit_error(output_descriptor, phase, str(finalization_error))
        returncode = 125
    elif not output_broken:
        for record in terminal_records(
            phase=phase,
            elapsed_ms=elapsed_ms,
            returncode=returncode,
            path=path,
            analysis=analysis,
            launch_detail=launch_detail,
            forced_signal=pending_signal,
        ):
            output_broken = not emit_bytes(output_descriptor, record)
            if output_broken:
                handle_signal(signal.SIGPIPE, None)
                break

    for selected_signal, previous in prior_handlers.items():
        signal.signal(selected_signal, previous)

    selected_signal = pending_signal
    if selected_signal is None and returncode < 0:
        selected_signal = -returncode
    if selected_signal is not None:
        self_signal(selected_signal)
    return returncode


def main(
    arguments: Sequence[str] | None = None,
    *,
    repository: Path | None = None,
) -> int:
    values = parse(tuple(arguments) if arguments is not None else tuple(os.sys.argv[1:]))
    selected_repository = Path(__file__).resolve().parent.parent if repository is None else repository
    return run_command(
        values.command,
        phase=values.phase,
        repository=selected_repository,
        log_directory=values.log_directory,
        progress_seconds=values.progress_seconds,
    )
