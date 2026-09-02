"""Catch signals, relay them to one active child group, and preserve cleanup before exit."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager


POLL_SECONDS = 0.25


class SignalSubprocessOwner:
    """Own one synchronous child group while a surrounding finalizer remains authoritative."""

    def __init__(self, cleanup_seconds: float) -> None:
        self.cleanup_seconds = cleanup_seconds
        self.pending_signal: int | None = None
        self.cleanup_started = False
        self.launching = False
        self.child: subprocess.Popen[bytes] | None = None
        self.signal_deadline: float | None = None

    def begin_cleanup(self) -> None:
        self.cleanup_started = True

    @staticmethod
    def signal_group(process: subprocess.Popen[bytes], signum: int) -> None:
        try:
            os.killpg(process.pid, signum)
        except ProcessLookupError:
            pass

    def handle_signal(self, signum: int, _frame: object) -> None:
        if self.pending_signal is None:
            self.pending_signal = signum
        if self.child is not None:
            self.signal_group(self.child, signum)
            if self.signal_deadline is None:
                self.signal_deadline = time.monotonic() + self.cleanup_seconds
            return
        if not self.launching and not self.cleanup_started:
            raise SystemExit(128 + signum)

    def run(
        self,
        arguments: Sequence[str],
        *,
        cwd: str | os.PathLike[str],
        env: Mapping[str, str],
        check: bool = False,
        stdin: int | None = None,
        stdout: int | None = None,
        stderr: int | None = None,
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[bytes]:
        started = time.monotonic()
        pending_before_launch = self.pending_signal
        self.launching = True
        try:
            process = subprocess.Popen(
                tuple(arguments),
                cwd=cwd,
                env=env,
                stdin=stdin,
                stdout=stdout,
                stderr=stderr,
                start_new_session=True,
            )
            self.child = process
        finally:
            self.launching = False
        if (
            pending_before_launch is None
            and self.pending_signal is not None
            and process.poll() is None
        ):
            self.signal_group(process, self.pending_signal)
            self.signal_deadline = time.monotonic() + self.cleanup_seconds

        output: bytes | None
        errors: bytes | None
        while True:
            try:
                output, errors = process.communicate(timeout=POLL_SECONDS)
                break
            except subprocess.TimeoutExpired:
                now = time.monotonic()
                if self.signal_deadline is not None and now >= self.signal_deadline:
                    self.signal_group(process, signal.SIGKILL)
                    self.signal_deadline = None
                    continue
                if timeout is not None and now - started >= timeout:
                    self.signal_group(process, signal.SIGKILL)
                    output, errors = process.communicate()
                    self.child = None
                    raise subprocess.TimeoutExpired(
                        tuple(arguments), timeout, output=output, stderr=errors
                    )
        self.child = None
        self.signal_deadline = None
        if self.pending_signal is not None and not self.cleanup_started:
            raise SystemExit(128 + self.pending_signal)
        result = subprocess.CompletedProcess(tuple(arguments), process.returncode, output, errors)
        if check:
            result.check_returncode()
        return result


@contextmanager
def signal_subprocess_owner(
    signals: Sequence[int], cleanup_seconds: float
) -> Iterator[SignalSubprocessOwner]:
    owner = SignalSubprocessOwner(cleanup_seconds)
    previous_handlers: dict[int, signal.Handlers] = {}
    caught: BaseException | None = None
    try:
        for selected_signal in signals:
            previous_handlers[selected_signal] = signal.getsignal(selected_signal)
            signal.signal(selected_signal, owner.handle_signal)
        try:
            yield owner
        except BaseException as error:
            caught = error
    finally:
        for selected_signal, previous in previous_handlers.items():
            signal.signal(selected_signal, previous)
    if owner.pending_signal is not None:
        raise SystemExit(128 + owner.pending_signal)
    if caught is not None:
        raise caught
