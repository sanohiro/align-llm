#!/usr/bin/env python3

import ctypes
import dis
import hashlib
import json
import os
import selectors
import signal
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable


FIXTURE_GIT_ENV = {
    "GIT_AUTHOR_NAME": "align-llm fixture",
    "GIT_AUTHOR_EMAIL": "fixture@align-llm.invalid",
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z",
    "GIT_COMMITTER_NAME": "align-llm fixture",
    "GIT_COMMITTER_EMAIL": "fixture@align-llm.invalid",
    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z",
}
PR_SET_CHILD_SUBREAPER = 36
BWRAP_EXECUTABLE = Path(os.environ.get("ALIGN_LLM_BWRAP", "/usr/bin/bwrap"))
PRLIMIT_EXECUTABLE = Path("/usr/bin/prlimit")
MAX_COMMAND_OUTPUT_BYTES = 64 * 1024
COMMAND_OUTPUT_TRUNCATION_MARKER = b"\n[output truncated]"
MAX_VALIDATION_TMPFS_BYTES = 64 * 1024 * 1024
MAX_VALIDATION_WORKTREE_BYTES = 64 * 1024 * 1024
MAX_VALIDATION_WORKTREE_FILES = 8192
MAX_VALIDATION_ADDRESS_SPACE_BYTES = 512 * 1024 * 1024
MAX_VALIDATION_RESIDENT_BYTES = 512 * 1024 * 1024
MAX_VALIDATION_FILE_BYTES = 64 * 1024 * 1024
MAX_VALIDATION_PROCESSES = 256
MAX_VALIDATION_OPEN_FILES = 512
RESOURCE_POLL_INTERVAL_SECONDS = 0.25
BWRAP_PROBE_TIMEOUT_SECONDS = 2
MAX_RESOURCE_SCAN_SECONDS = 0.1
MAX_PROCESS_TREE_SCAN_SECONDS = 0.5


def enable_child_subreaper() -> bool:
    if not sys.platform.startswith("linux"):
        return False
    try:
        return ctypes.CDLL(None, use_errno=True).prctl(
            PR_SET_CHILD_SUBREAPER,
            1,
            0,
            0,
            0,
        ) == 0
    except (AttributeError, OSError):
        return False


CHILD_SUBREAPER_ENABLED = enable_child_subreaper()


class TaskError(Exception):
    pass


class CommandTimedOut(TaskError):
    pass


class BoundedOutput:
    def __init__(self) -> None:
        self.data = bytearray()
        self.truncated = False

    def append(self, chunk: bytes) -> None:
        if self.truncated:
            return
        remaining = MAX_COMMAND_OUTPUT_BYTES - len(self.data)
        if len(chunk) > remaining:
            self.data.extend(chunk[:remaining])
            self.truncated = True
        else:
            self.data.extend(chunk)

    def bytes(self) -> bytes:
        if not self.truncated:
            return bytes(self.data)
        prefix_limit = max(
            0,
            MAX_COMMAND_OUTPUT_BYTES - len(COMMAND_OUTPUT_TRUNCATION_MARKER),
        )
        return bytes(self.data[:prefix_limit]) + COMMAND_OUTPUT_TRUNCATION_MARKER

    def text(self) -> str:
        return self.bytes().decode("utf-8", errors="replace")


class OutputTimeout(subprocess.TimeoutExpired):
    def __init__(self, command: list[str], timeout: int, captures: dict[str, BoundedOutput]):
        super().__init__(command, timeout)
        self.captures = captures


def require_process_containment() -> None:
    if not CHILD_SUBREAPER_ENABLED:
        raise TaskError("process containment requires Linux child-subreaper support")


def descendant_process_ids(
    root_pids: set[int], deadline: float | None = None
) -> set[int]:
    parents: dict[int, list[int]] = {}
    if not sys.platform.startswith("linux"):
        return set()
    for status_path in Path("/proc").glob("[0-9]*/status"):
        if deadline is not None and time.monotonic() >= deadline:
            raise TaskError("validation resource scan exceeded its time limit")
        try:
            pid = int(status_path.parent.name)
            lines = status_path.read_text(encoding="utf-8").splitlines()
            parent_line = next(line for line in lines if line.startswith("PPid:"))
            parent = int(parent_line.split()[1])
        except (OSError, StopIteration, ValueError):
            continue
        parents.setdefault(parent, []).append(pid)

    descendants = set()
    pending = list(root_pids)
    while pending:
        parent = pending.pop()
        for child in parents.get(parent, []):
            if child not in descendants:
                descendants.add(child)
                pending.append(child)
    return descendants


def kill_process_ids(process_ids: set[int]) -> None:
    for pid in process_ids:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def kill_owned_processes(process: subprocess.Popen[bytes]) -> set[int]:
    roots = {process.pid}
    if CHILD_SUBREAPER_ENABLED:
        roots.add(os.getpid())
    descendants = descendant_process_ids(roots)
    descendants.discard(os.getpid())
    descendants.discard(process.pid)
    kill_process_ids(descendants)
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    return descendants


def kill_adopted_descendants() -> set[int]:
    if not CHILD_SUBREAPER_ENABLED:
        return set()
    descendants = descendant_process_ids({os.getpid()})
    descendants.discard(os.getpid())
    kill_process_ids(descendants)
    return descendants


def reap_owned_processes(process_ids: set[int], timeout_seconds: float = 1.0) -> None:
    if not CHILD_SUBREAPER_ENABLED:
        return
    pending = set(process_ids)
    deadline = time.monotonic() + timeout_seconds
    while pending:
        for pid in tuple(pending):
            try:
                waited, _ = os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                if not Path(f"/proc/{pid}").exists():
                    pending.remove(pid)
                continue
            if waited == pid:
                pending.remove(pid)
        if not pending or time.monotonic() >= deadline:
            return
        time.sleep(0.01)


def decode_output(output: bytes | None) -> str:
    return (output or b"").decode("utf-8", errors="replace")


ResourceCheck = Callable[[subprocess.Popen[bytes], float], None]


def invoke_resource_check(
    process: subprocess.Popen[bytes],
    deadline: float,
    resource_check: ResourceCheck,
    *,
    monotonic: Callable[[], float] = time.monotonic,
) -> None:
    if monotonic() >= deadline:
        raise subprocess.TimeoutExpired(process.args, 0)
    try:
        resource_check(process, deadline)
    except TaskError as error:
        if monotonic() >= deadline:
            raise subprocess.TimeoutExpired(process.args, 0) from error
        raise
    if monotonic() >= deadline:
        raise subprocess.TimeoutExpired(process.args, 0)


def wait_for_process(
    process: subprocess.Popen[bytes],
    deadline: float,
    resource_check: ResourceCheck | None,
) -> None:
    while process.poll() is None:
        if resource_check is not None:
            invoke_resource_check(process, deadline, resource_check)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(process.args, 0)
        try:
            process.wait(timeout=min(remaining, RESOURCE_POLL_INTERVAL_SECONDS))
        except subprocess.TimeoutExpired:
            continue


def read_process_output(
    process: subprocess.Popen[bytes],
    captures: dict[str, BoundedOutput],
    timeout_seconds: float,
    resource_check: ResourceCheck | None = None,
) -> None:
    streams = {
        "stdout": process.stdout,
        "stderr": process.stderr,
    }
    selector = selectors.DefaultSelector()
    try:
        for name, stream in streams.items():
            if stream is None or stream.closed:
                continue
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, name)

        deadline = time.monotonic() + timeout_seconds

        def check_resources() -> None:
            if resource_check is None:
                return
            try:
                invoke_resource_check(process, deadline, resource_check)
            except subprocess.TimeoutExpired as error:
                raise OutputTimeout(
                    process.args,
                    int(timeout_seconds),
                    captures,
                ) from error

        while selector.get_map():
            check_resources()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise OutputTimeout(process.args, int(timeout_seconds), captures)
            events = selector.select(
                min(remaining, RESOURCE_POLL_INTERVAL_SECONDS)
                if resource_check is not None
                else remaining
            )
            if not events:
                if resource_check is not None:
                    check_resources()
                    continue
                raise OutputTimeout(process.args, int(timeout_seconds), captures)
            for key, _ in events:
                stream = key.fileobj
                try:
                    chunk = os.read(stream.fileno(), 65536)
                except BlockingIOError:
                    continue
                if chunk:
                    captures[key.data].append(chunk)
                    continue
                selector.unregister(stream)
                stream.close()

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise OutputTimeout(process.args, int(timeout_seconds), captures)
        try:
            wait_for_process(process, deadline, resource_check)
            if resource_check is not None:
                check_resources()
        except subprocess.TimeoutExpired as error:
            raise OutputTimeout(process.args, int(timeout_seconds), captures) from error
    finally:
        for key in tuple(selector.get_map().values()):
            stream = key.fileobj
            try:
                selector.unregister(stream)
            except KeyError:
                pass
        selector.close()


def close_process_streams(process: subprocess.Popen[bytes]) -> None:
    for stream in (process.stdout, process.stderr):
        if stream is not None:
            stream.close()


def communicate_after_kill(
    process: subprocess.Popen[bytes],
    timeout_error: subprocess.TimeoutExpired,
) -> tuple[str, str]:
    owned_processes = kill_owned_processes(process)
    captures = getattr(timeout_error, "captures", None)
    if captures is None:
        captures = {
            "stdout": BoundedOutput(),
            "stderr": BoundedOutput(),
        }
        captures["stdout"].append(timeout_error.output or b"")
        captures["stderr"].append(timeout_error.stderr or b"")
    try:
        read_process_output(process, captures, 1)
    except subprocess.TimeoutExpired:
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            owned_processes.update(kill_owned_processes(process))
    finally:
        close_process_streams(process)
    if process.poll() is None:
        owned_processes.update(kill_owned_processes(process))
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            close_process_streams(process)
    owned_processes.update(kill_adopted_descendants())
    reap_owned_processes(owned_processes)
    return captures["stdout"].text(), captures["stderr"].text()


def load_task(path: Path) -> dict[str, Any]:
    try:
        task = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise TaskError(f"cannot load task descriptor: {error}") from error

    if not isinstance(task, dict):
        raise TaskError("task descriptor must be a JSON object")
    required = {
        "schema_version",
        "id",
        "source_dir",
        "source_revision",
        "allowed_edits",
        "validation_argv",
        "validation_timeout_seconds",
    }
    if set(task) != required:
        raise TaskError("task descriptor fields do not match schema version 1")
    if (
        not isinstance(task["schema_version"], int)
        or isinstance(task["schema_version"], bool)
        or task["schema_version"] != 1
    ):
        raise TaskError("unsupported task descriptor schema")
    if not isinstance(task["id"], str) or not task["id"]:
        raise TaskError("task id must be a non-empty string")
    if not isinstance(task["source_dir"], str) or not task["source_dir"]:
        raise TaskError("source_dir must be a non-empty string")
    if not isinstance(task["source_revision"], str) or len(task["source_revision"]) != 40:
        raise TaskError("source_revision must be a full Git commit ID")
    if not is_string_list(task["allowed_edits"]) or not task["allowed_edits"]:
        raise TaskError("allowed_edits must be a non-empty string list")
    if not is_string_list(task["validation_argv"]) or not task["validation_argv"]:
        raise TaskError("validation_argv must be a non-empty string list")
    timeout = task["validation_timeout_seconds"]
    if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout <= 0:
        raise TaskError("validation_timeout_seconds must be a positive integer")
    return task


def is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and item for item in value)


def resolve_inside(root: Path, relative: str, label: str) -> Path:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise TaskError(f"{label} escapes the project root") from error
    return candidate


def run(
    argv: list[str],
    cwd: Path,
    timeout_seconds: int,
    *,
    env: dict[str, str] | None = None,
    command_name: str | None = None,
    resource_check: ResourceCheck | None = None,
) -> subprocess.CompletedProcess[str]:
    display_name = command_name or argv[0]
    require_process_containment()
    try:
        process = subprocess.Popen(
            argv,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
    except OSError as error:
        raise TaskError(f"command failed to run: {display_name}: {error}") from error
    captures = {
        "stdout": BoundedOutput(),
        "stderr": BoundedOutput(),
    }
    try:
        read_process_output(process, captures, timeout_seconds, resource_check)
    except subprocess.TimeoutExpired as error:
        stdout, stderr = communicate_after_kill(process, error)
        details = [f"command timed out after {timeout_seconds} seconds: {display_name}"]
        if stdout:
            details.append(f"stdout:\n{stdout.rstrip()}")
        if stderr:
            details.append(f"stderr:\n{stderr.rstrip()}")
        raise CommandTimedOut("\n".join(details))
    except BaseException:
        owned_processes = kill_owned_processes(process)
        try:
            read_process_output(process, captures, 1)
        except subprocess.TimeoutExpired:
            close_process_streams(process)
        owned_processes.update(kill_adopted_descendants())
        reap_owned_processes(owned_processes)
        raise
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    owned_processes = kill_adopted_descendants()
    reap_owned_processes(owned_processes)
    stdout = captures["stdout"].text()
    stderr = captures["stderr"].text()
    return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)


def fixture_environment() -> dict[str, str]:
    environment = {
        "HOME": "/tmp/home",
        "PATH": "/usr/bin:/bin",
        "TMPDIR": "/tmp",
    }
    environment.update(FIXTURE_GIT_ENV)
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    environment["GIT_ATTR_NOSYSTEM"] = "1"
    environment["GIT_CONFIG_GLOBAL"] = os.devnull
    environment["GIT_NO_REPLACE_OBJECTS"] = "1"
    environment["LC_ALL"] = "C"
    return environment


def validation_environment() -> dict[str, str]:
    environment = fixture_environment()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONNOUSERSITE"] = "1"
    return environment


def validation_command(argv: list[str]) -> list[str]:
    if argv[0] == "python3":
        return [str(Path(sys.executable).resolve()), *argv[1:]]
    return argv


def sandbox_probe_command() -> list[str]:
    return [
        str(BWRAP_EXECUTABLE),
        "--die-with-parent",
        "--new-session",
        "--unshare-all",
        "--uid",
        str(os.getuid()),
        "--gid",
        str(os.getgid()),
        "--cap-drop",
        "ALL",
        "--ro-bind",
        "/usr",
        "/usr",
        "--symlink",
        "usr/bin",
        "/bin",
        "--symlink",
        "usr/lib",
        "/lib",
        "--symlink",
        "usr/lib64",
        "/lib64",
        "--symlink",
        "usr/sbin",
        "/sbin",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--size",
        str(MAX_VALIDATION_TMPFS_BYTES),
        "--tmpfs",
        "/tmp",
        "--size",
        str(MAX_VALIDATION_TMPFS_BYTES),
        "--tmpfs",
        "/dev/shm",
        "--dir",
        "/tmp/home",
        "--",
        "/usr/bin/python3",
        "-c",
        "pass",
    ]


def require_sandbox_capability() -> None:
    try:
        probe = subprocess.run(
            sandbox_probe_command(),
            check=False,
            capture_output=True,
            timeout=BWRAP_PROBE_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise TaskError(
            "validation sandbox is unavailable: required bubblewrap namespaces "
            "could not be created"
        ) from error
    if probe.returncode != 0:
        diagnostic = (probe.stderr or probe.stdout).decode(
            "utf-8", errors="replace"
        ).strip()
        suffix = f": {diagnostic}" if diagnostic else ""
        raise TaskError(
            "validation sandbox is unavailable: required bubblewrap namespaces "
            f"could not be created{suffix}"
        )


def validation_resource_limits(timeout_seconds: int) -> list[str]:
    return [
        str(PRLIMIT_EXECUTABLE),
        f"--as={MAX_VALIDATION_ADDRESS_SPACE_BYTES}",
        f"--fsize={MAX_VALIDATION_FILE_BYTES}",
        f"--nproc={MAX_VALIDATION_PROCESSES}",
        f"--nofile={MAX_VALIDATION_OPEN_FILES}",
        f"--cpu={max(1, timeout_seconds + 1)}",
        "--",
    ]


def create_sandbox_parent_argv(path: Path, existing_roots: tuple[Path, ...]) -> list[str]:
    arguments = []
    parents = list(path.parents)
    parents.reverse()
    for parent in parents:
        if parent == Path("/"):
            continue
        if any(parent == root or parent.is_relative_to(root) for root in existing_roots):
            continue
        arguments.extend(["--dir", str(parent)])
    return arguments


def validation_sandbox_command(
    argv: list[str], checkout: Path, timeout_seconds: int
) -> list[str]:
    if not BWRAP_EXECUTABLE.is_file() or not os.access(BWRAP_EXECUTABLE, os.X_OK):
        raise TaskError(
            f"validation sandbox is unavailable: {BWRAP_EXECUTABLE} is required"
        )
    if not PRLIMIT_EXECUTABLE.is_file() or not os.access(PRLIMIT_EXECUTABLE, os.X_OK):
        raise TaskError(
            f"validation sandbox is unavailable: {PRLIMIT_EXECUTABLE} is required"
        )
    require_sandbox_capability()

    resolved = validation_command(argv)
    executable = Path(resolved[0]).resolve()
    system_root = Path("/usr")
    python_root = Path(sys.base_prefix).resolve()
    readonly_roots = [system_root]
    sandbox = [
        str(BWRAP_EXECUTABLE),
        "--die-with-parent",
        "--new-session",
        "--unshare-all",
        "--uid",
        str(os.getuid()),
        "--gid",
        str(os.getgid()),
        "--cap-drop",
        "ALL",
        "--ro-bind",
        str(system_root),
        str(system_root),
        "--symlink",
        "usr/bin",
        "/bin",
        "--symlink",
        "usr/lib",
        "/lib",
        "--symlink",
        "usr/lib64",
        "/lib64",
        "--symlink",
        "usr/sbin",
        "/sbin",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--size",
        str(MAX_VALIDATION_TMPFS_BYTES),
        "--tmpfs",
        "/tmp",
        "--size",
        str(MAX_VALIDATION_TMPFS_BYTES),
        "--tmpfs",
        "/dev/shm",
        "--dir",
        "/tmp/home",
    ]
    if python_root != system_root and not python_root.is_relative_to(system_root):
        sandbox.extend(
            create_sandbox_parent_argv(
                python_root,
                tuple(readonly_roots),
            )
        )
        sandbox.extend(["--ro-bind", str(python_root), str(python_root)])
        readonly_roots.append(python_root)
    if not any(
        executable == root or executable.is_relative_to(root) for root in readonly_roots
    ):
        raise TaskError(
            f"validation executable is outside the sandbox runtime: {executable}"
        )

    sandbox.extend(
        create_sandbox_parent_argv(
            checkout,
            tuple(readonly_roots),
        )
    )
    sandbox.extend(
        [
            "--bind",
            str(checkout),
            str(checkout),
            "--ro-bind",
            str(checkout / ".git"),
            str(checkout / ".git"),
            "--chdir",
            str(checkout),
            "--",
            *validation_resource_limits(timeout_seconds),
            *resolved,
        ]
    )
    return sandbox


def git_output(checkout: Path, *args: str, nul_terminated: bool = False) -> str:
    result = run(["git", *args], checkout, 10, env=fixture_environment())
    if result.returncode != 0:
        raise TaskError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.rstrip("\0") if nul_terminated else result.stdout.strip()


def create_pinned_checkout(source: Path, checkout: Path, expected_revision: str) -> None:
    shutil.copytree(source, checkout, symlinks=True)
    init = run(
        ["git", "init", "-q", "--initial-branch=main", "--object-format=sha1"],
        checkout,
        10,
        env=fixture_environment(),
    )
    if init.returncode != 0:
        raise TaskError(f"git init failed: {init.stderr.strip()}")

    fixture_env = fixture_environment()
    for argv in (
        ["git", "config", "core.autocrlf", "false"],
        ["git", "config", "core.filemode", "true"],
        ["git", "add", "--all"],
        [
            "git",
            "-c",
            "commit.gpgSign=false",
            "-c",
            "core.hooksPath=/dev/null",
            "commit",
            "-q",
            "-m",
            "Create deterministic evaluation fixture",
        ],
    ):
        result = run(argv, checkout, 10, env=fixture_env)
        if result.returncode != 0:
            raise TaskError(f"{' '.join(argv)} failed: {result.stderr.strip()}")

    if git_output(checkout, "status", "--porcelain", "--ignored", "--untracked-files=all"):
        raise TaskError("new fixture checkout contains uncommitted or ignored files")
    actual_revision = git_output(checkout, "rev-parse", "HEAD")
    if actual_revision != expected_revision:
        raise TaskError(
            f"fixture revision mismatch: expected {expected_revision}, got {actual_revision}"
        )


def print_command_output(label: str, result: subprocess.CompletedProcess[str]) -> None:
    print(f"{label} exit code: {result.returncode}")
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.stderr:
        print(result.stderr, end="" if result.stderr.endswith("\n") else "\n", file=sys.stderr)


def source_tree(checkout: Path, source_revision: str) -> dict[str, tuple[str, str]]:
    records = git_output(
        checkout,
        "ls-tree",
        "-r",
        "-z",
        "--full-tree",
        source_revision,
        nul_terminated=True,
    ).split("\0")
    entries = {}
    for record in records:
        if not record:
            continue
        try:
            metadata, relative = record.split("\t", 1)
            mode, object_type, object_id = metadata.split()
        except ValueError as error:
            raise TaskError("pinned fixture tree contains an invalid entry") from error
        if object_type != "blob" or mode not in {"100644", "100755", "120000"}:
            raise TaskError(f"unsupported pinned fixture tree entry: {relative}")
        entries[relative] = (mode, object_id)
    return entries


def worktree_paths(checkout: Path) -> set[str]:
    paths = set()
    for directory, child_directories, filenames in os.walk(checkout, followlinks=False):
        current = Path(directory)
        if current == checkout:
            child_directories[:] = [
                name for name in child_directories if name != ".git"
            ]
        for name in tuple(child_directories):
            path = current / name
            if path.is_symlink():
                paths.add(path.relative_to(checkout).as_posix())
                child_directories.remove(name)
        for name in filenames:
            paths.add((current / name).relative_to(checkout).as_posix())
    return paths


def worktree_snapshot(checkout: Path) -> dict[str, tuple[Any, ...]]:
    snapshot: dict[str, tuple[Any, ...]] = {}
    for relative in worktree_paths(checkout):
        path = checkout / relative
        try:
            metadata = path.lstat()
            mode = metadata.st_mode & 0o7777
            if stat.S_ISLNK(metadata.st_mode):
                snapshot[relative] = ("symlink", mode, os.readlink(path))
            elif stat.S_ISREG(metadata.st_mode):
                content = path.read_bytes()
                snapshot[relative] = (
                    "file",
                    mode,
                    len(content),
                    hashlib.sha256(content).hexdigest(),
                )
            else:
                snapshot[relative] = ("other", mode)
        except OSError as error:
            raise TaskError(f"cannot snapshot candidate worktree path {relative}: {error}") from error
    return snapshot


def index_snapshot(checkout: Path) -> str:
    return git_output(checkout, "ls-files", "--stage", "-z", nul_terminated=True)


def has_symlink_parent(checkout: Path, relative: str) -> bool:
    current = checkout
    for part in Path(relative).parts[:-1]:
        current /= part
        if current.is_symlink():
            return True
    return False


def git_blob_id(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode()
    return hashlib.sha1(header + data).hexdigest()


def actual_worktree_changes(checkout: Path, source_revision: str) -> list[str]:
    expected = source_tree(checkout, source_revision)
    observed_paths = worktree_paths(checkout)
    changed = observed_paths - set(expected)
    for relative, (mode, object_id) in expected.items():
        path = checkout / relative
        if relative not in observed_paths or has_symlink_parent(checkout, relative):
            changed.add(relative)
            continue
        try:
            metadata = path.lstat()
            if mode == "120000":
                if not stat.S_ISLNK(metadata.st_mode):
                    changed.add(relative)
                    continue
                content = os.fsencode(os.readlink(path))
            else:
                if not stat.S_ISREG(metadata.st_mode):
                    changed.add(relative)
                    continue
                expected_mode = 0o755 if mode == "100755" else 0o644
                if (metadata.st_mode & 0o7777) != expected_mode:
                    changed.add(relative)
                    continue
                content = path.read_bytes()
        except OSError as error:
            raise TaskError(f"cannot inspect candidate worktree path {relative}: {error}") from error
        if git_blob_id(content) != object_id:
            changed.add(relative)
    return sorted(changed)


def check_allowed_changes(
    checkout: Path,
    allowed_edits: list[str],
    source_revision: str,
    expected_directory_modes: dict[str, int],
) -> None:
    if git_output(checkout, "rev-parse", "HEAD") != source_revision:
        raise TaskError("candidate changed the pinned fixture HEAD")
    index_records = git_output(
        checkout,
        "ls-files",
        "-v",
        "-z",
        nul_terminated=True,
    ).split("\0")
    flagged_paths = sorted(
        record[2:] for record in index_records if record and not record.startswith("H ")
    )
    if flagged_paths:
        raise TaskError(f"candidate changed Git index flags: {', '.join(flagged_paths)}")
    check_directory_modes(checkout, expected_directory_modes)
    changed = set(actual_worktree_changes(checkout, source_revision))
    changed.update(
        path
        for path in git_output(
            checkout,
            "diff",
            "--cached",
            "--name-only",
            "-z",
            "--no-renames",
            "--no-ext-diff",
            source_revision,
            nul_terminated=True,
        ).split("\0")
        if path
    )
    untracked = [
        path
        for path in git_output(
            checkout,
            "ls-files",
            "--others",
            "-z",
            "--exclude-standard",
            nul_terminated=True,
        ).split("\0")
        if path
    ]
    ignored = [
        path
        for path in git_output(
            checkout,
            "ls-files",
            "--others",
            "--ignored",
            "-z",
            "--exclude-standard",
            nul_terminated=True,
        ).split("\0")
        if path
    ]
    if untracked:
        raise TaskError(f"candidate created untracked files: {', '.join(untracked)}")
    if ignored:
        raise TaskError(f"candidate created ignored files: {', '.join(ignored)}")
    if not changed:
        raise TaskError("candidate patch made no tracked changes")
    disallowed = sorted(set(changed) - set(allowed_edits))
    if disallowed:
        raise TaskError(f"candidate changed disallowed files: {', '.join(disallowed)}")


def directory_modes(checkout: Path) -> dict[str, int]:
    modes: dict[str, int] = {"": checkout.lstat().st_mode & 0o7777}
    deadline = time.monotonic() + MAX_RESOURCE_SCAN_SECONDS
    pending = [checkout]
    while pending:
        current = pending.pop()
        try:
            entries = os.scandir(current)
        except OSError as error:
            raise TaskError(
                f"cannot inspect validation directory {current.relative_to(checkout)}: "
                f"{error}"
            ) from error
        with entries:
            for entry in entries:
                if current == checkout and entry.name == ".git":
                    continue
                if time.monotonic() >= deadline:
                    raise TaskError("validation resource scan exceeded its time limit")
                path = Path(entry.path)
                try:
                    metadata = entry.stat(follow_symlinks=False)
                except OSError as error:
                    raise TaskError(
                        f"cannot inspect validation directory {path.relative_to(checkout)}: "
                        f"{error}"
                    ) from error
                if stat.S_ISLNK(metadata.st_mode):
                    continue
                if not stat.S_ISDIR(metadata.st_mode):
                    continue
                relative = path.relative_to(checkout).as_posix()
                modes[relative] = metadata.st_mode & 0o7777
                pending.append(path)
    return modes


def check_directory_modes(
    checkout: Path, expected_directory_modes: dict[str, int]
) -> None:
    observed = directory_modes(checkout)
    if observed != expected_directory_modes:
        changed = sorted(
            set(observed) | set(expected_directory_modes),
            key=lambda path: path or ".",
        )
        changed = [
            path or "."
            for path in changed
            if observed.get(path) != expected_directory_modes.get(path)
        ]
        raise TaskError(
            "validation changed directory modes: " + ", ".join(changed)
        )


def check_pristine_checkout(
    checkout: Path,
    source_revision: str,
    expected_directory_modes: dict[str, int],
) -> None:
    if git_output(checkout, "rev-parse", "HEAD") != source_revision:
        raise TaskError("validation changed the pinned fixture HEAD")
    index_records = git_output(
        checkout,
        "ls-files",
        "-v",
        "-z",
        nul_terminated=True,
    ).split("\0")
    flagged_paths = sorted(
        record[2:] for record in index_records if record and not record.startswith("H ")
    )
    if flagged_paths:
        raise TaskError(f"validation changed Git index flags: {', '.join(flagged_paths)}")
    check_directory_modes(checkout, expected_directory_modes)
    if actual_worktree_changes(checkout, source_revision):
        raise TaskError("validation changed the pinned fixture worktree")
    untracked = [
        path
        for path in git_output(
            checkout,
            "ls-files",
            "--others",
            "-z",
            "--exclude-standard",
            nul_terminated=True,
        ).split("\0")
        if path
    ]
    if untracked:
        raise TaskError(
            f"validation created untracked files: {', '.join(sorted(untracked))}"
        )
    ignored = [
        path
        for path in git_output(
            checkout,
            "ls-files",
            "--others",
            "--ignored",
            "-z",
            "--exclude-standard",
            nul_terminated=True,
        ).split("\0")
        if path
    ]
    if ignored:
        raise TaskError(
            f"validation created ignored files: {', '.join(sorted(ignored))}"
        )
    if git_output(
        checkout,
        "diff",
        "--cached",
        "--name-only",
        "-z",
        "--no-renames",
        "--no-ext-diff",
        source_revision,
        nul_terminated=True,
    ):
        raise TaskError("validation changed the pinned fixture index")


def validation_worktree_usage(
    checkout: Path,
    *,
    scan: Callable[[Path], Any] = os.scandir,
    monotonic: Callable[[], float] = time.monotonic,
    command_deadline: float | None = None,
) -> tuple[int, int, set[tuple[int, int]]]:
    total_bytes = 0
    file_count = 0
    visible_inodes: set[tuple[int, int]] = set()
    deadline = monotonic() + MAX_RESOURCE_SCAN_SECONDS
    if command_deadline is not None:
        deadline = min(deadline, command_deadline)
    pending = [checkout]

    def require_scan_deadline() -> None:
        if monotonic() >= deadline:
            raise TaskError("validation resource scan exceeded its time limit")

    def directory_error(current: Path, error: BaseException) -> TaskError:
        return TaskError(
            f"cannot inspect validation directory {current.relative_to(checkout)}: "
            f"{error}"
        )

    while pending:
        current = pending.pop()
        require_scan_deadline()
        entered = False
        body_error: tuple[type[BaseException], BaseException, Any] | None = None
        close_error: BaseException | None = None
        try:
            with scan(current) as entries:
                entered = True
                try:
                    require_scan_deadline()
                    while True:
                        try:
                            entry = next(entries)
                        except StopIteration:
                            require_scan_deadline()
                            break
                        except OSError as error:
                            require_scan_deadline()
                            raise directory_error(current, error) from error

                        require_scan_deadline()
                        if current == checkout and entry.name == ".git":
                            continue
                        path = Path(entry.path)
                        try:
                            metadata = entry.stat(follow_symlinks=False)
                        except FileNotFoundError:
                            require_scan_deadline()
                            continue
                        except OSError as error:
                            require_scan_deadline()
                            raise TaskError(
                                "cannot inspect validation worktree path "
                                f"{path.relative_to(checkout)}: {error}"
                            ) from error
                        require_scan_deadline()
                        file_count += 1
                        if file_count > MAX_VALIDATION_WORKTREE_FILES:
                            raise TaskError(
                                "validation exceeded the writable worktree file limit "
                                f"({MAX_VALIDATION_WORKTREE_FILES} files)"
                            )
                        if stat.S_ISDIR(metadata.st_mode):
                            pending.append(path)
                            continue
                        if not stat.S_ISREG(metadata.st_mode):
                            continue
                        total_bytes += metadata.st_size
                        visible_inodes.add((metadata.st_dev, metadata.st_ino))
                        if total_bytes > MAX_VALIDATION_WORKTREE_BYTES:
                            raise TaskError(
                                "validation exceeded the writable worktree size limit "
                                f"({MAX_VALIDATION_WORKTREE_BYTES} bytes)"
                            )
                except BaseException:
                    body_error = sys.exc_info()
        except BaseException as error:
            interrupted_error = None
            interrupted_traceback = None
            cleanup_replaced_body = False
            candidate_error: BaseException | None = error
            current_frame = sys._getframe()
            seen_contexts: set[int] = set()
            outer_error = True
            scan_construction_error = False
            while (
                candidate_error is not None
                and id(candidate_error) not in seen_contexts
            ):
                seen_contexts.add(id(candidate_error))
                candidate_traceback = candidate_error.__traceback__
                while (
                    candidate_traceback is not None
                    and candidate_traceback.tb_frame is not current_frame
                ):
                    candidate_traceback = candidate_traceback.tb_next
                if candidate_traceback is not None:
                    if (
                        outer_error
                        and candidate_traceback.tb_lasti
                        in VALIDATION_WORKTREE_SCAN_CALL_OFFSETS
                    ):
                        scan_construction_error = True
                    if not outer_error:
                        cleanup_replaced_body = True
                    if not isinstance(candidate_error, Exception):
                        interrupted_error = candidate_error
                        interrupted_traceback = candidate_traceback
                        break
                outer_error = False
                candidate_error = candidate_error.__context__

            if interrupted_error is not None and interrupted_traceback is not None:
                body_error = (
                    type(interrupted_error),
                    interrupted_error,
                    interrupted_error.__traceback__,
                )
                if interrupted_error is not error:
                    close_error = error
            elif not entered and not cleanup_replaced_body:
                if not isinstance(error, OSError):
                    raise
                require_scan_deadline()
                if (
                    isinstance(error, FileNotFoundError)
                    and current != checkout
                    and scan_construction_error
                ):
                    continue
                raise directory_error(current, error) from error
            else:
                close_error = error

        require_scan_deadline()
        if body_error is not None:
            _, error, traceback = body_error
            raise error.with_traceback(traceback)
        if close_error is not None:
            if isinstance(close_error, OSError):
                raise directory_error(current, close_error) from close_error
            raise close_error
    return total_bytes, file_count, visible_inodes


CALL_OPNAMES = frozenset(("CALL", "CALL_FUNCTION", "CALL_METHOD"))


def loaded_name_call_offsets_from_instructions(
    instructions: tuple[Any, ...], name: str
) -> frozenset[int]:
    offsets = []
    for index, instruction in enumerate(instructions):
        if not instruction.opname.startswith("LOAD_") or instruction.argval != name:
            continue
        for candidate in instructions[index + 1 :]:
            if candidate.opname in CALL_OPNAMES:
                offsets.append(candidate.offset)
                break
    return frozenset(offsets)


def loaded_name_call_offsets(function: Callable[..., Any], name: str) -> frozenset[int]:
    return loaded_name_call_offsets_from_instructions(
        tuple(dis.get_instructions(function)),
        name,
    )


VALIDATION_WORKTREE_SCAN_CALL_OFFSETS = loaded_name_call_offsets(
    validation_worktree_usage, "scan"
)
if len(VALIDATION_WORKTREE_SCAN_CALL_OFFSETS) != 1:
    raise RuntimeError("cannot identify the validation worktree scan call")


def validation_process_usage(
    process: subprocess.Popen[bytes], command_deadline: float
) -> set[int]:
    roots = {process.pid}
    if CHILD_SUBREAPER_ENABLED:
        roots.add(os.getpid())
    deadline = min(
        time.monotonic() + MAX_PROCESS_TREE_SCAN_SECONDS,
        command_deadline,
    )
    process_ids = {process.pid} | descendant_process_ids(roots, deadline)
    if time.monotonic() >= command_deadline:
        raise subprocess.TimeoutExpired(process.args, 0)
    process_ids.discard(os.getpid())
    if len(process_ids) > MAX_VALIDATION_PROCESSES:
        raise TaskError(
            "validation exceeded the process limit "
            f"({MAX_VALIDATION_PROCESSES} processes)"
        )
    resident_bytes = 0
    deadline = min(
        time.monotonic() + MAX_RESOURCE_SCAN_SECONDS,
        command_deadline,
    )
    for pid in process_ids:
        if time.monotonic() >= deadline:
            raise TaskError("validation resource scan exceeded its time limit")
        try:
            status = (Path("/proc") / str(pid) / "status").read_text(
                encoding="ascii", errors="replace"
            )
        except OSError:
            continue
        for line in status.splitlines():
            if not line.startswith("VmRSS:"):
                continue
            fields = line.split()
            if len(fields) >= 2 and fields[1].isdigit():
                resident_bytes += int(fields[1]) * 1024
            break
        if resident_bytes > MAX_VALIDATION_RESIDENT_BYTES:
            raise TaskError(
                "validation exceeded the aggregate resident-memory limit "
                f"({MAX_VALIDATION_RESIDENT_BYTES} bytes)"
            )
    return process_ids


def deleted_open_file_usage(
    process_ids: set[int],
    visible_inodes: set[tuple[int, int]],
    command_deadline: float | None = None,
) -> tuple[int, int]:
    total_bytes = 0
    file_count = 0
    seen_inodes = set(visible_inodes)
    deadline = time.monotonic() + MAX_RESOURCE_SCAN_SECONDS
    if command_deadline is not None:
        deadline = min(deadline, command_deadline)
    for pid in process_ids:
        if time.monotonic() >= deadline:
            raise TaskError("validation resource scan exceeded its time limit")
        try:
            descriptors = (Path("/proc") / str(pid) / "fd").iterdir()
        except OSError:
            continue
        try:
            for descriptor in descriptors:
                if time.monotonic() >= deadline:
                    raise TaskError("validation resource scan exceeded its time limit")
                try:
                    target = os.readlink(descriptor)
                    if not target.endswith(" (deleted)"):
                        continue
                    metadata = descriptor.stat()
                except OSError:
                    continue
                if not stat.S_ISREG(metadata.st_mode):
                    continue
                inode = (metadata.st_dev, metadata.st_ino)
                if inode in seen_inodes:
                    continue
                seen_inodes.add(inode)
                file_count += 1
                if file_count > MAX_VALIDATION_WORKTREE_FILES:
                    raise TaskError(
                        "validation exceeded the writable worktree file limit "
                        f"({MAX_VALIDATION_WORKTREE_FILES} files)"
                    )
                total_bytes += metadata.st_size
                if total_bytes > MAX_VALIDATION_WORKTREE_BYTES:
                    raise TaskError(
                        "validation exceeded the writable worktree size limit "
                        f"({MAX_VALIDATION_WORKTREE_BYTES} bytes)"
                    )
        except OSError:
            continue
    return total_bytes, file_count


def check_validation_resources(
    checkout: Path,
    process: subprocess.Popen[bytes],
    command_deadline: float,
) -> None:
    process_ids = validation_process_usage(process, command_deadline)
    if time.monotonic() >= command_deadline:
        raise subprocess.TimeoutExpired(process.args, 0)
    total_bytes, file_count, visible_inodes = validation_worktree_usage(
        checkout,
        command_deadline=command_deadline,
    )
    if time.monotonic() >= command_deadline:
        raise subprocess.TimeoutExpired(process.args, 0)
    deleted_bytes, deleted_file_count = deleted_open_file_usage(
        process_ids,
        visible_inodes,
        command_deadline,
    )
    if time.monotonic() >= command_deadline:
        raise subprocess.TimeoutExpired(process.args, 0)
    if file_count + deleted_file_count > MAX_VALIDATION_WORKTREE_FILES:
        raise TaskError(
            "validation exceeded the writable worktree file limit "
            f"({MAX_VALIDATION_WORKTREE_FILES} files)"
        )
    total_bytes += deleted_bytes
    if total_bytes > MAX_VALIDATION_WORKTREE_BYTES:
        raise TaskError(
            "validation exceeded the writable worktree size limit "
            f"({MAX_VALIDATION_WORKTREE_BYTES} bytes)"
        )


def validate_candidate(
    checkout: Path,
    patch: Path,
    allowed_edits: list[str],
    validation_argv: list[str],
    validation_timeout_seconds: int,
    source_revision: str,
) -> None:
    resolved_validation_argv = validation_sandbox_command(
        validation_argv, checkout, validation_timeout_seconds
    )
    validation_env = validation_environment()
    resource_check = lambda process, deadline: check_validation_resources(
        checkout,
        process,
        deadline,
    )
    expected_directory_modes = directory_modes(checkout)
    before = run(
        resolved_validation_argv,
        checkout,
        validation_timeout_seconds,
        env=validation_env,
        command_name=validation_argv[0],
        resource_check=resource_check,
    )
    print_command_output("pre-repair validation", before)
    if before.returncode == 0:
        raise TaskError("pinned fixture unexpectedly passes before repair")
    try:
        check_pristine_checkout(
            checkout, source_revision, expected_directory_modes
        )
    except TaskError as error:
        raise TaskError(
            f"validation changed the pinned fixture before repair: {error}"
        ) from error

    fixture_env = fixture_environment()
    check = run(
        ["git", "apply", "--check", str(patch)],
        checkout,
        10,
        env=fixture_env,
    )
    if check.returncode != 0:
        raise TaskError(f"candidate patch does not apply: {check.stderr.strip()}")
    apply = run(["git", "apply", str(patch)], checkout, 10, env=fixture_env)
    if apply.returncode != 0:
        raise TaskError(f"candidate patch failed to apply: {apply.stderr.strip()}")

    check_allowed_changes(
        checkout, allowed_edits, source_revision, expected_directory_modes
    )
    candidate_worktree = worktree_snapshot(checkout)
    candidate_index = index_snapshot(checkout)

    after = run(
        resolved_validation_argv,
        checkout,
        validation_timeout_seconds,
        env=validation_env,
        command_name=validation_argv[0],
        resource_check=resource_check,
    )
    print_command_output("post-repair validation", after)
    check_allowed_changes(
        checkout, allowed_edits, source_revision, expected_directory_modes
    )
    observed_worktree = worktree_snapshot(checkout)
    if observed_worktree != candidate_worktree:
        changed = sorted(
            set(candidate_worktree) | set(observed_worktree)
        )
        changed = [
            path
            for path in changed
            if candidate_worktree.get(path) != observed_worktree.get(path)
        ]
        raise TaskError(
            "validation changed the candidate worktree after repair: "
            + ", ".join(changed)
        )
    if index_snapshot(checkout) != candidate_index:
        raise TaskError("validation changed the candidate Git index after repair")
    if after.returncode != 0:
        raise TaskError("candidate patch did not pass validation")


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: run-coding-task.py TASK_JSON CANDIDATE_PATCH", file=sys.stderr)
        return 2

    project_root = Path(__file__).resolve().parents[2]
    try:
        task_path = resolve_inside(project_root, sys.argv[1], "task descriptor")
        patch_path = resolve_inside(project_root, sys.argv[2], "candidate patch")
        task = load_task(task_path)
        source = resolve_inside(project_root, task["source_dir"], "fixture source")
        if not source.is_dir():
            raise TaskError(f"fixture source is not a directory: {source}")
        if not patch_path.is_file():
            raise TaskError(f"candidate patch is not a file: {patch_path}")

        # Keep descriptor-controlled text out of the filesystem prefix. Task IDs are labels,
        # not path components, and may contain separators or be unusually long.
        with tempfile.TemporaryDirectory(prefix="align-llm-coding-task-") as temporary:
            checkout = Path(temporary) / "repository"
            create_pinned_checkout(source, checkout, task["source_revision"])
            print(f"fixture revision: {task['source_revision']}")
            validate_candidate(
                checkout,
                patch_path,
                task["allowed_edits"],
                task["validation_argv"],
                task["validation_timeout_seconds"],
                task["source_revision"],
            )
    except TaskError as error:
        print(f"task error: {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
