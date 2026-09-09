"""Bound and reap an owned preparation/build command group."""
import os
from contextlib import ExitStack
from pathlib import Path
import signal
import subprocess
import time


def run_logged(command, log_path: Path, timeout: float, *, env=None, cwd=None, stdout_path=None):
    if timeout<=0: raise TimeoutError('final validation deadline exhausted')
    started=time.monotonic_ns()
    with ExitStack() as stack:
        log=stack.enter_context(log_path.open('wb'))
        output=stack.enter_context(stdout_path.open('wb')) if stdout_path is not None else log
        process=subprocess.Popen([str(value) for value in command],stdin=subprocess.DEVNULL,
            stdout=output,stderr=log,env=env,cwd=cwd,start_new_session=True)
        try:
            code=process.wait(timeout=timeout)
        except BaseException:
            # Python qualification owners unwind KeyboardInterrupt through their
            # existing finally blocks, including workers in separate sessions.
            try: os.killpg(process.pid,signal.SIGINT)
            except ProcessLookupError: pass
            try: process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                try: os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError: pass
                process.wait(timeout=5)
            raise
        finally:
            try: os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError: pass
    if code: raise subprocess.CalledProcessError(code,command)
    return time.monotonic_ns()-started
