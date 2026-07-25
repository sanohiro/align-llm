#!/usr/bin/env python3

import ctypes
import json
import os
import signal
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


FIXTURE_GIT_ENV = {
    "GIT_AUTHOR_NAME": "align-llm fixture",
    "GIT_AUTHOR_EMAIL": "fixture@align-llm.invalid",
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z",
    "GIT_COMMITTER_NAME": "align-llm fixture",
    "GIT_COMMITTER_EMAIL": "fixture@align-llm.invalid",
    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z",
}
PR_SET_CHILD_SUBREAPER = 36


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


def descendant_process_ids(root_pids: set[int]) -> set[int]:
    parents: dict[int, list[int]] = {}
    if not sys.platform.startswith("linux"):
        return set()
    for status_path in Path("/proc").glob("[0-9]*/status"):
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


def communicate_after_kill(
    process: subprocess.Popen[bytes],
    timeout_error: subprocess.TimeoutExpired,
) -> tuple[str, str]:
    owned_processes = kill_owned_processes(process)
    try:
        stdout, stderr = process.communicate(timeout=1)
    except subprocess.TimeoutExpired as cleanup_error:
        stdout = cleanup_error.output or timeout_error.output
        stderr = cleanup_error.stderr or timeout_error.stderr
        if process.stdout is not None:
            process.stdout.close()
        if process.stderr is not None:
            process.stderr.close()
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            owned_processes.update(kill_owned_processes(process))
    owned_processes.update(kill_adopted_descendants())
    reap_owned_processes(owned_processes)
    return decode_output(stdout), decode_output(stderr)


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
) -> subprocess.CompletedProcess[str]:
    display_name = command_name or argv[0]
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
    try:
        raw_stdout, raw_stderr = process.communicate(timeout=timeout_seconds)
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
            process.communicate(timeout=1)
        except subprocess.TimeoutExpired:
            if process.stdout is not None:
                process.stdout.close()
            if process.stderr is not None:
                process.stderr.close()
        owned_processes.update(kill_adopted_descendants())
        reap_owned_processes(owned_processes)
        raise
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    owned_processes = kill_adopted_descendants()
    reap_owned_processes(owned_processes)
    stdout = decode_output(raw_stdout)
    stderr = decode_output(raw_stderr)
    return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)


def fixture_environment() -> dict[str, str]:
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }
    environment.update(FIXTURE_GIT_ENV)
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    environment["GIT_CONFIG_GLOBAL"] = os.devnull
    environment["LC_ALL"] = "C"
    return environment


def validation_environment() -> dict[str, str]:
    environment = fixture_environment()
    for key in tuple(environment):
        if key.startswith("PYTHON"):
            environment.pop(key)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONNOUSERSITE"] = "1"
    return environment


def validation_command(argv: list[str]) -> list[str]:
    if argv[0] == "python3":
        return [str(Path(sys.executable).resolve()), *argv[1:]]
    return argv


def git_output(checkout: Path, *args: str) -> str:
    result = run(["git", *args], checkout, 10, env=fixture_environment())
    if result.returncode != 0:
        raise TaskError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def create_pinned_checkout(source: Path, checkout: Path, expected_revision: str) -> None:
    shutil.copytree(source, checkout)
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


def check_allowed_changes(
    checkout: Path,
    allowed_edits: list[str],
    source_revision: str,
) -> None:
    if git_output(checkout, "rev-parse", "HEAD") != source_revision:
        raise TaskError("candidate changed the pinned fixture HEAD")
    index_records = git_output(checkout, "ls-files", "-v", "-z").split("\0")
    flagged_paths = sorted(
        record[2:] for record in index_records if record and not record.startswith("H ")
    )
    if flagged_paths:
        raise TaskError(f"candidate changed Git index flags: {', '.join(flagged_paths)}")
    changed = git_output(
        checkout,
        "diff",
        "--name-only",
        "--no-renames",
        source_revision,
    ).splitlines()
    untracked = git_output(
        checkout,
        "ls-files",
        "--others",
        "--exclude-standard",
    ).splitlines()
    ignored = git_output(
        checkout,
        "ls-files",
        "--others",
        "--ignored",
        "--exclude-standard",
    ).splitlines()
    if untracked:
        raise TaskError(f"candidate created untracked files: {', '.join(untracked)}")
    if ignored:
        raise TaskError(f"candidate created ignored files: {', '.join(ignored)}")
    if not changed:
        raise TaskError("candidate patch made no tracked changes")
    disallowed = sorted(set(changed) - set(allowed_edits))
    if disallowed:
        raise TaskError(f"candidate changed disallowed files: {', '.join(disallowed)}")


def validate_candidate(
    checkout: Path,
    patch: Path,
    allowed_edits: list[str],
    validation_argv: list[str],
    validation_timeout_seconds: int,
    source_revision: str,
) -> None:
    resolved_validation_argv = validation_command(validation_argv)
    validation_env = validation_environment()
    before = run(
        resolved_validation_argv,
        checkout,
        validation_timeout_seconds,
        env=validation_env,
        command_name=validation_argv[0],
    )
    print_command_output("pre-repair validation", before)
    if before.returncode == 0:
        raise TaskError("pinned fixture unexpectedly passes before repair")
    if git_output(
        checkout,
        "status",
        "--porcelain",
        "--ignored",
        "--untracked-files=all",
    ):
        raise TaskError("validation changed the pinned fixture before repair")

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

    check_allowed_changes(checkout, allowed_edits, source_revision)

    after = run(
        resolved_validation_argv,
        checkout,
        validation_timeout_seconds,
        env=validation_env,
        command_name=validation_argv[0],
    )
    print_command_output("post-repair validation", after)
    if after.returncode != 0:
        raise TaskError("candidate patch did not pass validation")
    check_allowed_changes(checkout, allowed_edits, source_revision)


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

        with tempfile.TemporaryDirectory(prefix=f"align-llm-{task['id']}-") as temporary:
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
