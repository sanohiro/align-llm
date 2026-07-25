#!/usr/bin/env python3

import hashlib
import json
import os
import statistics
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


class BaselineError(Exception):
    pass


def git_environment() -> dict[str, str]:
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    environment["GIT_CONFIG_GLOBAL"] = os.devnull
    environment["GIT_NO_REPLACE_OBJECTS"] = "1"
    environment["LC_ALL"] = "C"
    return environment


def load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise BaselineError(f"cannot load {path}: {error}") from error
    if not isinstance(value, dict):
        raise BaselineError(f"{path} must contain a JSON object")
    return value


def require_fields(value: dict[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise BaselineError(f"{label} fields do not match baseline schema version 1")


def require_non_empty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise BaselineError(f"{label} must be a non-empty string")
    return value


def require_integer(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise BaselineError(f"{label} must be an integer")
    return value


def require_positive_integer(value: Any, label: str) -> int:
    integer = require_integer(value, label)
    if integer <= 0:
        raise BaselineError(f"{label} must be a positive integer")
    return integer


def require_non_negative_integer(value: Any, label: str) -> int:
    integer = require_integer(value, label)
    if integer < 0:
        raise BaselineError(f"{label} must be a non-negative integer")
    return integer


def resolve_inside(project_root: Path, relative: str, label: str) -> Path:
    candidate = (project_root / relative).resolve()
    try:
        candidate.relative_to(project_root)
    except ValueError as error:
        raise BaselineError(f"{label} escapes the project root") from error
    return candidate


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as error:
        raise BaselineError(f"cannot hash {path}: {error}") from error
    return digest.hexdigest()


def verify_commit(project_root: Path, revision: str) -> None:
    exists = subprocess.run(
        ["git", "cat-file", "-e", f"{revision}^{{commit}}"],
        cwd=project_root,
        check=False,
        capture_output=True,
        text=True,
        env=git_environment(),
    )
    if exists.returncode != 0:
        raise BaselineError("align_llm_commit is not available in the repository")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", revision, "HEAD"],
        cwd=project_root,
        check=False,
        capture_output=True,
        text=True,
        env=git_environment(),
    )
    if ancestor.returncode != 0:
        raise BaselineError("align_llm_commit is not an ancestor of HEAD")


def corpus_tasks(
    project_root: Path,
    corpus: dict[str, Any],
) -> tuple[list[str], list[int], set[Path], str]:
    require_fields(corpus, {"id", "schema_version", "path"}, "corpus metadata")
    if require_integer(corpus["schema_version"], "corpus metadata schema_version") != 1:
        raise BaselineError("unsupported corpus schema")
    corpus_id = require_non_empty_string(corpus["id"], "corpus id")
    relative_path = require_non_empty_string(corpus["path"], "corpus path")
    corpus_path = resolve_inside(project_root, relative_path, "corpus path")
    manifest = load_object(corpus_path)
    require_fields(manifest, {"schema_version", "corpus_id", "task_files"}, "corpus")
    if (
        require_integer(manifest["schema_version"], "corpus schema_version") != 1
        or manifest["corpus_id"] != corpus_id
    ):
        raise BaselineError("baseline corpus metadata differs from the corpus manifest")
    task_files = manifest["task_files"]
    if not isinstance(task_files, list) or not task_files:
        raise BaselineError("corpus task_files must be a non-empty list")

    task_ids = []
    artifact_files = {
        corpus_path,
        project_root / ".align-revision",
        project_root / ".gitattributes",
        project_root / "eval" / "runners" / "record-baseline.py",
        project_root / "eval" / "runners" / "verify-baseline.py",
        project_root / "scripts" / "check-align-revision",
    }
    expected_codes = []
    task_commands = []
    for relative_task_path in task_files:
        task_path_value = require_non_empty_string(relative_task_path, "task path")
        task_path = resolve_inside(project_root, task_path_value, "task path")
        task = load_object(task_path)
        artifact_files.add(task_path)
        task_ids.append(require_non_empty_string(task.get("id"), "task id"))
        expected_code = task.get("expected_code")
        expected_codes.append(require_integer(expected_code, "task expected_code"))
        task_commands.append(require_non_empty_string(task.get("cmd"), "task command"))
        artifact_paths = task.get("artifact_paths")
        if not isinstance(artifact_paths, list) or not artifact_paths:
            raise BaselineError(f"task does not declare artifact_paths: {task_path}")
        for artifact_value in artifact_paths:
            artifact_relative = require_non_empty_string(artifact_value, "artifact path")
            artifact_path = resolve_inside(project_root, artifact_relative, "artifact path")
            if artifact_path.is_dir():
                files = [path.resolve() for path in artifact_path.rglob("*") if path.is_file()]
                if not files:
                    raise BaselineError(f"artifact directory is empty: {artifact_path}")
                artifact_files.update(files)
            elif artifact_path.is_file():
                artifact_files.add(artifact_path)
            else:
                raise BaselineError(f"artifact does not exist: {artifact_path}")
    if len(set(task_ids)) != len(task_ids):
        raise BaselineError("corpus contains duplicate task ids")
    if len(set(task_commands)) != 1:
        raise BaselineError(
            "baseline schema version 1 requires one Python command for all corpus tasks"
        )
    return task_ids, expected_codes, artifact_files, task_commands[0]


def verify_artifacts(
    artifacts: Any,
    artifact_files: set[Path],
    project_root: Path,
    align_llm_commit: str,
) -> None:
    if not isinstance(artifacts, dict):
        raise BaselineError("artifacts must be an object")
    require_fields(artifacts, {"algorithm", "files"}, "artifacts")
    if artifacts["algorithm"] != "sha256":
        raise BaselineError("unsupported artifact digest algorithm")
    rows = artifacts["files"]
    if not isinstance(rows, list) or not rows:
        raise BaselineError("artifact files must be a non-empty list")

    expected_rows = []
    for path in sorted(
        artifact_files,
        key=lambda item: item.relative_to(project_root).as_posix(),
    ):
        expected_rows.append(
            {
                "path": path.relative_to(project_root).as_posix(),
                "sha256": hash_file(path),
            }
        )
    if rows != expected_rows:
        raise BaselineError("current evaluation artifacts differ from the recorded baseline")

    for row in rows:
        if not isinstance(row, dict):
            raise BaselineError("artifact file entry must be an object")
        require_fields(row, {"path", "sha256"}, "artifact file entry")
        relative = require_non_empty_string(row["path"], "artifact file path")
        digest = require_non_empty_string(row["sha256"], "artifact file sha256")
        if len(digest) != 64:
            raise BaselineError("artifact sha256 must be a full digest")
        source = subprocess.run(
            ["git", "show", f"{align_llm_commit}:{relative}"],
            cwd=project_root,
            check=False,
            capture_output=True,
            env=git_environment(),
        )
        if source.returncode != 0:
            raise BaselineError(
                f"artifact is absent from the baseline source commit: {relative}"
            )
        if hashlib.sha256(source.stdout).hexdigest() != digest:
            raise BaselineError(
                f"artifact differs from the baseline source commit: {relative}"
            )


def verify_provider(provider: Any) -> None:
    if not isinstance(provider, dict):
        raise BaselineError("provider metadata must be an object")
    require_fields(provider, {"id", "model", "prompt_version"}, "provider metadata")
    for field in ("id", "model", "prompt_version"):
        require_non_empty_string(provider[field], f"provider {field}")


def verify_environment(environment: Any, task_command: str) -> None:
    if not isinstance(environment, dict):
        raise BaselineError("environment metadata must be an object")
    required = {
        "os",
        "os_release",
        "architecture",
        "cpu",
        "logical_cpu_count",
        "task_python_executable",
        "task_python_resolved_executable",
        "task_python_version",
        "gpu",
    }
    require_fields(environment, required, "environment metadata")
    for field in required - {"logical_cpu_count"}:
        require_non_empty_string(environment[field], f"environment {field}")
    require_positive_integer(environment["logical_cpu_count"], "environment logical_cpu_count")
    if environment["task_python_executable"] != task_command:
        raise BaselineError("recorded Python executable differs from the corpus task command")
    for field in ("task_python_executable", "task_python_resolved_executable"):
        if not Path(environment[field]).is_absolute():
            raise BaselineError(f"environment {field} must be an absolute path")


def verify_runs(
    runs: Any,
    sample_count: int,
    expected_task_ids: list[str],
    expected_codes: list[int],
) -> list[int]:
    if not isinstance(runs, list) or len(runs) != sample_count:
        raise BaselineError("runs length differs from sample_count")

    passing_times = []
    for expected_sample, run in enumerate(runs, start=1):
        if not isinstance(run, dict):
            raise BaselineError("run must be an object")
        require_fields(run, {"sample", "task_results", "summary"}, "run")
        sample = require_positive_integer(run["sample"], "run sample")
        if sample != expected_sample:
            raise BaselineError("run sample numbers are not contiguous")
        task_results = run["task_results"]
        if not isinstance(task_results, list):
            raise BaselineError("task_results must be a list")
        if len(task_results) != len(expected_task_ids) or not all(
            isinstance(task, dict) for task in task_results
        ):
            raise BaselineError("baseline task result count or shape differs from the corpus")
        actual_task_ids = [task.get("task_id") for task in task_results]
        if actual_task_ids != expected_task_ids:
            raise BaselineError("baseline task ids or order differ from the corpus")

        pass_count = 0
        for task in task_results:
            require_fields(
                task,
                {
                    "task_id",
                    "verdict",
                    "expected_code",
                    "actual_code",
                    "duration_ns",
                    "time_to_passing_patch_ns",
                },
                "task result",
            )
            verdict = task["verdict"]
            if not isinstance(verdict, str) or verdict not in {
                "PASS",
                "FAIL",
                "TIMEOUT",
                "ERROR",
            }:
                raise BaselineError("task result contains an unknown verdict")
            require_integer(task["actual_code"], "task actual_code")
            require_integer(task["expected_code"], "task expected_code")
            task_index = expected_task_ids.index(task["task_id"])
            if task["expected_code"] != expected_codes[task_index]:
                raise BaselineError("task expected_code differs from the corpus")
            duration = require_positive_integer(task["duration_ns"], "task duration_ns")
            passing_time = task["time_to_passing_patch_ns"]
            if verdict == "PASS":
                if task["actual_code"] != task["expected_code"]:
                    raise BaselineError("passing task actual_code differs from expected_code")
                pass_count += 1
                require_positive_integer(
                    passing_time,
                    "task time_to_passing_patch_ns",
                )
                if passing_time != duration:
                    raise BaselineError("passing task time differs from its duration")
                passing_times.append(duration)
            else:
                if passing_time is not None:
                    raise BaselineError("non-passing task has a time_to_passing_patch")
                if verdict == "FAIL" and task["actual_code"] == task["expected_code"]:
                    raise BaselineError("failing task actual_code equals expected_code")
                if verdict in {"TIMEOUT", "ERROR"} and task["actual_code"] != -1:
                    raise BaselineError("non-completed task actual_code must be -1")

        summary = run["summary"]
        if not isinstance(summary, dict):
            raise BaselineError("run summary must be an object")
        require_fields(summary, {"task_count", "pass_count", "fail_count"}, "run summary")
        for field in ("task_count", "pass_count", "fail_count"):
            require_non_negative_integer(summary[field], f"run summary {field}")
        expected_summary = {
            "task_count": len(task_results),
            "pass_count": pass_count,
            "fail_count": len(task_results) - pass_count,
        }
        if summary != expected_summary:
            raise BaselineError("run summary does not match task results")
    return passing_times


def verify_aggregate(
    aggregate: Any,
    passing_times: list[int],
    expected_task_attempt_count: int,
) -> None:
    if not isinstance(aggregate, dict):
        raise BaselineError("aggregate must be an object")
    require_fields(
        aggregate,
        {"task_attempt_count", "passing_attempt_count", "time_to_passing_patch_ns"},
        "aggregate",
    )
    task_attempt_count = require_positive_integer(
        aggregate["task_attempt_count"], "aggregate task_attempt_count"
    )
    if task_attempt_count != expected_task_attempt_count:
        raise BaselineError("aggregate task_attempt_count is incorrect")
    if task_attempt_count < len(passing_times):
        raise BaselineError("aggregate task_attempt_count is smaller than pass count")
    passing_attempt_count = require_non_negative_integer(
        aggregate["passing_attempt_count"],
        "aggregate passing_attempt_count",
    )
    if passing_attempt_count != len(passing_times):
        raise BaselineError("aggregate passing_attempt_count is incorrect")
    timing = aggregate["time_to_passing_patch_ns"]
    if not passing_times:
        if timing is not None:
            raise BaselineError("aggregate timing must be null without a passing attempt")
        return
    if not isinstance(timing, dict):
        raise BaselineError("aggregate timing must be an object when a task passes")
    require_fields(timing, {"minimum", "median", "maximum"}, "aggregate timing")
    for field in ("minimum", "median", "maximum"):
        require_positive_integer(timing[field], f"aggregate timing {field}")
    expected = {
        "minimum": min(passing_times),
        "median": int(statistics.median(passing_times)),
        "maximum": max(passing_times),
    }
    if timing != expected:
        raise BaselineError("aggregate timing does not match task results")


def verify_baseline(path: Path, project_root: Path) -> None:
    baseline = load_object(path)
    require_fields(
        baseline,
        {
            "schema_version",
            "baseline_id",
            "recorded_at",
            "align_llm_commit",
            "align_revision",
            "corpus",
            "artifacts",
            "provider",
            "environment",
            "sample_count",
            "runs",
            "aggregate",
        },
        "baseline",
    )
    if require_integer(baseline["schema_version"], "baseline schema_version") != 1:
        raise BaselineError("unsupported baseline schema")
    require_non_empty_string(baseline["baseline_id"], "baseline_id")
    recorded_at = require_non_empty_string(baseline["recorded_at"], "recorded_at")
    try:
        timestamp = datetime.fromisoformat(recorded_at)
    except ValueError as error:
        raise BaselineError("recorded_at must be an ISO-8601 timestamp") from error
    if timestamp.tzinfo is None:
        raise BaselineError("recorded_at must include a timezone")

    align_llm_commit = require_non_empty_string(
        baseline["align_llm_commit"], "align_llm_commit"
    )
    if len(align_llm_commit) != 40:
        raise BaselineError("align_llm_commit must be a full Git commit ID")
    verify_commit(project_root, align_llm_commit)
    expected_align_revision = (
        (project_root / ".align-revision").read_text(encoding="utf-8").strip()
    )
    if baseline["align_revision"] != expected_align_revision:
        raise BaselineError("baseline Align revision differs from .align-revision")

    verify_provider(baseline["provider"])
    expected_task_ids, expected_codes, artifact_files, task_command = corpus_tasks(
        project_root,
        baseline["corpus"],
    )
    verify_environment(baseline["environment"], task_command)
    verify_artifacts(
        baseline["artifacts"],
        artifact_files,
        project_root,
        align_llm_commit,
    )
    sample_count = require_positive_integer(baseline["sample_count"], "sample_count")
    if sample_count < 2:
        raise BaselineError("canonical baseline must contain at least two samples")
    passing_times = verify_runs(
        baseline["runs"],
        sample_count,
        expected_task_ids,
        expected_codes,
    )
    task_attempt_count = sum(len(run["task_results"]) for run in baseline["runs"])
    verify_aggregate(baseline["aggregate"], passing_times, task_attempt_count)


def main() -> int:
    project_root = Path(__file__).resolve().parents[2]
    paths = sys.argv[1:] or ["eval/baselines/coding-v1-reference.json"]
    try:
        for raw_path in paths:
            path = (project_root / raw_path).resolve()
            try:
                path.relative_to(project_root)
            except ValueError as error:
                raise BaselineError("baseline path escapes the project root") from error
            verify_baseline(path, project_root)
            print(f"baseline valid: {path.relative_to(project_root)}")
    except (BaselineError, OSError) as error:
        print(f"baseline error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
