#!/usr/bin/env python3

import argparse
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


def parse_eval_output(stdout: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        rows = [json.loads(line) for line in stdout.splitlines() if line]
    except json.JSONDecodeError as error:
        raise BaselineError(f"evaluation emitted invalid JSON Lines: {error}") from error
    if len(rows) < 2:
        raise BaselineError("evaluation emitted no task results or summary")
    task_results = rows[:-1]
    summary = rows[-1]
    for task in task_results:
        required = {"task_id", "verdict", "actual_code", "duration_ns"}
        if not isinstance(task, dict) or not required.issubset(task):
            raise BaselineError("evaluation task result does not match the expected schema")
    if not isinstance(summary, dict) or "corpus_id" not in summary:
        raise BaselineError("evaluation summary does not match the expected schema")
    return task_results, summary


def record_run(binary: Path, corpus_path: Path, project_root: Path, sample: int) -> dict[str, Any]:
    result = run([str(binary), "--eval", str(corpus_path)], project_root)
    if result.returncode != 0:
        raise BaselineError(
            f"evaluation sample {sample} failed with exit code {result.returncode}: "
            f"{result.stderr.strip()}"
        )
    tasks, summary = parse_eval_output(result.stdout)
    task_rows = []
    for task in tasks:
        duration = task["duration_ns"]
        if not isinstance(duration, int) or isinstance(duration, bool) or duration <= 0:
            raise BaselineError("evaluation emitted a non-positive task duration")
        task_rows.append(
            {
                "task_id": task["task_id"],
                "verdict": task["verdict"],
                "actual_code": task["actual_code"],
                "duration_ns": duration,
                "time_to_passing_patch_ns": duration if task["verdict"] == "PASS" else None,
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

        corpus_path = (project_root / args.corpus).resolve()
        output_path = (project_root / args.output).resolve()
        binary = (project_root / "main").resolve()
        for path, label in ((corpus_path, "corpus"), (binary, "align-llm binary")):
            if not path.is_file():
                raise BaselineError(f"{label} does not exist: {path}")
        try:
            corpus_path.relative_to(project_root)
            output_path.relative_to(project_root)
        except ValueError as error:
            raise BaselineError("corpus and output must remain inside the project root") from error

        corpus = load_json(corpus_path)
        if corpus.get("schema_version") != 1 or not isinstance(corpus.get("corpus_id"), str):
            raise BaselineError("corpus does not match schema version 1")

        runs = [
            record_run(binary, corpus_path, project_root, sample)
            for sample in range(1, args.samples + 1)
        ]
        passing_times = [
            task["time_to_passing_patch_ns"]
            for run_result in runs
            for task in run_result["task_results"]
            if task["time_to_passing_patch_ns"] is not None
        ]
        if not passing_times:
            raise BaselineError("baseline contains no passing patch")

        baseline = {
            "schema_version": 1,
            "baseline_id": f"{corpus['corpus_id']}-{args.provider}-{args.model}",
            "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "align_llm_commit": checked_output(["git", "rev-parse", "HEAD"], project_root),
            "align_revision": (project_root / ".align-revision")
            .read_text(encoding="utf-8")
            .strip(),
            "corpus": {
                "id": corpus["corpus_id"],
                "schema_version": corpus["schema_version"],
                "path": str(corpus_path.relative_to(project_root)),
            },
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
                "passing_attempt_count": len(passing_times),
                "time_to_passing_patch_ns": {
                    "minimum": min(passing_times),
                    "median": int(statistics.median(passing_times)),
                    "maximum": max(passing_times),
                },
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
