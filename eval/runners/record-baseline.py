#!/usr/bin/env python3

import argparse
import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class BaselineError(Exception):
    pass


def require_integer(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise BaselineError(f"{label} must be an integer")
    return value


def require_non_negative_integer(value: Any, label: str) -> int:
    integer = require_integer(value, label)
    if integer < 0:
        raise BaselineError(f"{label} must be a non-negative integer")
    return integer


def run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            argv,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        raise BaselineError(f"cannot run {argv[0]}: {error}") from error


def checked_output(argv: list[str], cwd: Path) -> str:
    result = run(argv, cwd)
    if result.returncode != 0:
        raise BaselineError(f"{' '.join(argv)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def checked_run(argv: list[str], cwd: Path) -> None:
    result = run(argv, cwd)
    if result.returncode != 0:
        raise BaselineError(
            f"{' '.join(argv)} failed with exit code {result.returncode}: "
            f"{result.stderr.strip()}"
        )
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.stderr:
        print(result.stderr, end="" if result.stderr.endswith("\n") else "\n", file=sys.stderr)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise BaselineError(f"cannot load {path}: {error}") from error
    if not isinstance(value, dict):
        raise BaselineError(f"{path} must contain a JSON object")
    return value


def cpu_model() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


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


def artifact_manifest(
    project_root: Path,
    corpus_path: Path,
    corpus: dict[str, Any],
) -> dict[str, Any]:
    task_files = corpus.get("task_files")
    if not isinstance(task_files, list) or not task_files:
        raise BaselineError("corpus task_files must be a non-empty list")

    files = {
        corpus_path,
        project_root / ".align-revision",
        project_root / ".gitattributes",
        project_root / "eval" / "runners" / "record-baseline.py",
    }
    for task_value in task_files:
        if not isinstance(task_value, str) or not task_value:
            raise BaselineError("corpus task path must be a non-empty string")
        task_path = resolve_inside(project_root, task_value, "task path")
        if not task_path.is_file():
            raise BaselineError(f"task file does not exist: {task_path}")
        files.add(task_path)
        task = load_json(task_path)
        artifact_paths = task.get("artifact_paths")
        if not isinstance(artifact_paths, list) or not artifact_paths:
            raise BaselineError(f"task does not declare artifact_paths: {task_path}")
        for artifact_value in artifact_paths:
            if not isinstance(artifact_value, str) or not artifact_value:
                raise BaselineError("artifact path must be a non-empty string")
            artifact_path = resolve_inside(project_root, artifact_value, "artifact path")
            if artifact_path.is_dir():
                artifact_files = [path for path in artifact_path.rglob("*") if path.is_file()]
                if not artifact_files:
                    raise BaselineError(f"artifact directory is empty: {artifact_path}")
                files.update(path.resolve() for path in artifact_files)
            elif artifact_path.is_file():
                files.add(artifact_path)
            else:
                raise BaselineError(f"artifact does not exist: {artifact_path}")

    rows = []
    for path in sorted(files, key=lambda item: item.relative_to(project_root).as_posix()):
        relative = path.relative_to(project_root).as_posix()
        rows.append({"path": relative, "sha256": hash_file(path)})
    return {"algorithm": "sha256", "files": rows}


def parse_eval_output(
    stdout: str,
    expected_corpus_id: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        rows = [json.loads(line) for line in stdout.splitlines() if line]
    except json.JSONDecodeError as error:
        raise BaselineError(f"evaluation emitted invalid JSON Lines: {error}") from error
    if len(rows) < 2:
        raise BaselineError("evaluation emitted no task results or summary")
    task_results = rows[:-1]
    summary = rows[-1]
    for task in task_results:
        required = {
            "schema_version",
            "task_id",
            "verdict",
            "expected_code",
            "actual_code",
            "duration_ns",
            "stdout",
            "stderr",
        }
        if not isinstance(task, dict) or set(task) != required:
            raise BaselineError("evaluation task result does not match the expected schema")
        if require_integer(task["schema_version"], "task schema_version") != 1:
            raise BaselineError("evaluation task result uses an unsupported schema")
        if not isinstance(task["task_id"], str) or not task["task_id"]:
            raise BaselineError("evaluation task id must be a non-empty string")
        if not isinstance(task["stdout"], str) or not isinstance(task["stderr"], str):
            raise BaselineError("evaluation task output must be strings")
    summary_fields = {
        "schema_version",
        "corpus_id",
        "task_count",
        "pass_count",
        "fail_count",
    }
    if not isinstance(summary, dict) or set(summary) != summary_fields:
        raise BaselineError("evaluation summary does not match the expected schema")
    if require_integer(summary["schema_version"], "summary schema_version") != 1:
        raise BaselineError("evaluation summary uses an unsupported schema")
    if summary["corpus_id"] != expected_corpus_id:
        raise BaselineError("evaluation summary corpus_id differs from the requested corpus")
    for field in ("task_count", "pass_count", "fail_count"):
        require_non_negative_integer(summary[field], f"summary {field}")
    return task_results, summary


def record_run(
    binary: Path,
    corpus_path: Path,
    project_root: Path,
    sample: int,
    expected_corpus_id: str,
) -> dict[str, Any]:
    result = run([str(binary), "--eval", str(corpus_path)], project_root)
    try:
        tasks, summary = parse_eval_output(result.stdout, expected_corpus_id)
    except BaselineError as error:
        raise BaselineError(
            f"evaluation sample {sample} did not produce a complete result: {error}; "
            f"exit code {result.returncode}; stderr: {result.stderr.strip()}"
        ) from error
    if summary["task_count"] != len(tasks):
        raise BaselineError(f"evaluation sample {sample} summary task count is incorrect")
    observed_passes = sum(task["verdict"] == "PASS" for task in tasks)
    if (
        summary["pass_count"] != observed_passes
        or summary["fail_count"] != len(tasks) - observed_passes
    ):
        raise BaselineError(f"evaluation sample {sample} summary verdict counts are incorrect")
    if summary["fail_count"] == 0 and result.returncode != 0:
        raise BaselineError(
            f"passing evaluation sample {sample} exited with code {result.returncode}: "
            f"{result.stderr.strip()}"
        )
    if summary["fail_count"] != 0 and result.returncode == 0:
        raise BaselineError(f"failing evaluation sample {sample} exited successfully")

    task_rows = []
    for task in tasks:
        verdict = task["verdict"]
        expected_code = task["expected_code"]
        actual_code = task["actual_code"]
        if verdict not in {"PASS", "FAIL", "TIMEOUT", "ERROR"}:
            raise BaselineError("evaluation emitted an unknown task verdict")
        if not isinstance(expected_code, int) or isinstance(expected_code, bool):
            raise BaselineError("evaluation emitted a non-integer expected code")
        if not isinstance(actual_code, int) or isinstance(actual_code, bool):
            raise BaselineError("evaluation emitted a non-integer actual code")
        if verdict == "PASS" and actual_code != expected_code:
            raise BaselineError("passing task actual_code differs from expected_code")
        if verdict == "FAIL" and actual_code == expected_code:
            raise BaselineError("failing task actual_code equals expected_code")
        if verdict in {"TIMEOUT", "ERROR"} and actual_code != -1:
            raise BaselineError("non-completed task actual_code must be -1")
        duration = task["duration_ns"]
        if not isinstance(duration, int) or isinstance(duration, bool) or duration <= 0:
            raise BaselineError("evaluation emitted a non-positive task duration")
        task_rows.append(
            {
                "task_id": task["task_id"],
                "verdict": verdict,
                "expected_code": expected_code,
                "actual_code": actual_code,
                "duration_ns": duration,
                "time_to_passing_patch_ns": duration if verdict == "PASS" else None,
            }
        )
    return {
        "sample": sample,
        "task_results": task_rows,
        "summary": {
            "task_count": summary["task_count"],
            "pass_count": summary["pass_count"],
            "fail_count": summary["fail_count"],
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Record a canonical fixed-evaluation baseline.")
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--prompt-version", required=True)
    parser.add_argument("--samples", type=int, default=2)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[2]
    try:
        if args.samples < 2:
            raise BaselineError("canonical baselines require at least two samples")
        status = checked_output(
            ["git", "status", "--porcelain", "--untracked-files=all"], project_root
        )
        if status:
            raise BaselineError("canonical baselines must be recorded from a clean worktree")

        corpus_path = resolve_inside(project_root, args.corpus, "corpus")
        output_path = resolve_inside(project_root, args.output, "output")
        align_repo = Path(
            os.environ.get("ALIGN_REPO", str(project_root.parent / "align"))
        ).resolve()
        pinned_compiler = align_repo / "target" / "release" / "alignc"
        checked_run(["make", "align-build"], project_root)
        checked_run(["make", f"ALIGNC={pinned_compiler}", "build"], project_root)
        binary = (project_root / "main").resolve()
        for path, label in ((corpus_path, "corpus"), (binary, "align-llm binary")):
            if not path.is_file():
                raise BaselineError(f"{label} does not exist: {path}")
        status_after_build = checked_output(
            ["git", "status", "--porcelain", "--untracked-files=all"], project_root
        )
        if status_after_build:
            raise BaselineError("baseline build changed the source worktree")

        corpus = load_json(corpus_path)
        if require_integer(corpus.get("schema_version"), "corpus schema_version") != 1:
            raise BaselineError("corpus does not match schema version 1")
        if not isinstance(corpus.get("corpus_id"), str) or not corpus["corpus_id"]:
            raise BaselineError("corpus id must be a non-empty string")
        source_commit = checked_output(["git", "rev-parse", "HEAD"], project_root)
        artifacts = artifact_manifest(project_root, corpus_path, corpus)

        runs = [
            record_run(
                binary,
                corpus_path,
                project_root,
                sample,
                corpus["corpus_id"],
            )
            for sample in range(1, args.samples + 1)
        ]
        passing_times = [
            task["time_to_passing_patch_ns"]
            for run_result in runs
            for task in run_result["task_results"]
            if task["time_to_passing_patch_ns"] is not None
        ]
        final_commit = checked_output(["git", "rev-parse", "HEAD"], project_root)
        final_status = checked_output(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            project_root,
        )
        if final_commit != source_commit:
            raise BaselineError("evaluation changed the source commit")
        if final_status:
            raise BaselineError("evaluation changed the source worktree")
        baseline = {
            "schema_version": 1,
            "baseline_id": f"{corpus['corpus_id']}-{args.provider}-{args.model}",
            "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "align_llm_commit": source_commit,
            "align_revision": (project_root / ".align-revision")
            .read_text(encoding="utf-8")
            .strip(),
            "corpus": {
                "id": corpus["corpus_id"],
                "schema_version": corpus["schema_version"],
                "path": str(corpus_path.relative_to(project_root)),
            },
            "artifacts": artifacts,
            "provider": {
                "id": args.provider,
                "model": args.model,
                "prompt_version": args.prompt_version,
            },
            "environment": {
                "os": platform.system(),
                "os_release": platform.release(),
                "architecture": platform.machine(),
                "cpu": cpu_model(),
                "logical_cpu_count": os.cpu_count(),
                "python_version": platform.python_version(),
                "gpu": "not used",
            },
            "sample_count": args.samples,
            "runs": runs,
            "aggregate": {
                "task_attempt_count": sum(
                    len(run_result["task_results"]) for run_result in runs
                ),
                "passing_attempt_count": len(passing_times),
                "time_to_passing_patch_ns": (
                    {
                        "minimum": min(passing_times),
                        "median": int(statistics.median(passing_times)),
                        "maximum": max(passing_times),
                    }
                    if passing_times
                    else None
                ),
            },
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")
        print(f"recorded {args.samples} samples in {output_path.relative_to(project_root)}")
    except (BaselineError, OSError) as error:
        print(f"baseline error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
