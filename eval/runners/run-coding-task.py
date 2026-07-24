#!/usr/bin/env python3

import json
import os
import shutil
import subprocess
import sys
import tempfile
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


class TaskError(Exception):
    pass


def load_task(path: Path) -> dict[str, Any]:
    try:
        task = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise TaskError(f"cannot load task descriptor: {error}") from error

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
    if task["schema_version"] != 1:
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
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            argv,
            cwd=cwd,
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise TaskError(f"command failed to run: {argv[0]}: {error}") from error


def git_output(checkout: Path, *args: str) -> str:
    result = run(["git", *args], checkout, 10)
    if result.returncode != 0:
        raise TaskError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def create_pinned_checkout(source: Path, checkout: Path, expected_revision: str) -> None:
    shutil.copytree(source, checkout)
    init = run(
        ["git", "init", "-q", "--initial-branch=main", "--object-format=sha1"],
        checkout,
        10,
    )
    if init.returncode != 0:
        raise TaskError(f"git init failed: {init.stderr.strip()}")

    fixture_env = os.environ.copy()
    fixture_env.update(FIXTURE_GIT_ENV)
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

    actual_revision = git_output(checkout, "rev-parse", "HEAD")
    if actual_revision != expected_revision:
        raise TaskError(
            f"fixture revision mismatch: expected {expected_revision}, got {actual_revision}"
        )
    if git_output(checkout, "status", "--porcelain"):
        raise TaskError("new fixture checkout is dirty")


def print_command_output(label: str, result: subprocess.CompletedProcess[str]) -> None:
    print(f"{label} exit code: {result.returncode}")
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.stderr:
        print(result.stderr, end="" if result.stderr.endswith("\n") else "\n", file=sys.stderr)


def validate_candidate(
    checkout: Path,
    patch: Path,
    allowed_edits: list[str],
    validation_argv: list[str],
    validation_timeout_seconds: int,
) -> None:
    validation_env = os.environ.copy()
    validation_env["PYTHONDONTWRITEBYTECODE"] = "1"
    before = run(
        validation_argv,
        checkout,
        validation_timeout_seconds,
        env=validation_env,
    )
    print_command_output("pre-repair validation", before)
    if before.returncode == 0:
        raise TaskError("pinned fixture unexpectedly passes before repair")
    if git_output(checkout, "status", "--porcelain"):
        raise TaskError("validation changed the pinned fixture before repair")

    check = run(["git", "apply", "--check", str(patch)], checkout, 10)
    if check.returncode != 0:
        raise TaskError(f"candidate patch does not apply: {check.stderr.strip()}")
    apply = run(["git", "apply", str(patch)], checkout, 10)
    if apply.returncode != 0:
        raise TaskError(f"candidate patch failed to apply: {apply.stderr.strip()}")

    changed = git_output(checkout, "diff", "--name-only", "--no-renames").splitlines()
    untracked = git_output(checkout, "ls-files", "--others", "--exclude-standard").splitlines()
    if untracked:
        raise TaskError(f"candidate created untracked files: {', '.join(untracked)}")
    if not changed:
        raise TaskError("candidate patch made no tracked changes")
    disallowed = sorted(set(changed) - set(allowed_edits))
    if disallowed:
        raise TaskError(f"candidate changed disallowed files: {', '.join(disallowed)}")

    after = run(
        validation_argv,
        checkout,
        validation_timeout_seconds,
        env=validation_env,
    )
    print_command_output("post-repair validation", after)
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
            )
    except TaskError as error:
        print(f"task error: {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
