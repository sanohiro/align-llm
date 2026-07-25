#!/usr/bin/env python3

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


CANONICAL_BASELINE = Path("eval/baselines/coding-v1-reference.json")
CANONICAL_DIGEST = Path("eval/expected/coding-v1-reference.sha256")
CANONICAL_ORACLE = Path("eval/expected/coding-v1-reference-oracle.json")


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


def resolve_inside(project_root: Path, value: str, label: str) -> Path:
    candidate = (project_root / value).resolve()
    try:
        candidate.relative_to(project_root)
    except ValueError as error:
        raise BaselineError(f"{label} escapes the project root") from error
    return candidate


def load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BaselineError(f"cannot load {path}: {error}") from error
    if not isinstance(value, dict):
        raise BaselineError(f"{path} must contain a JSON object")
    return value


def require_oracle(project_root: Path, commit: str) -> None:
    if len(commit) != 40:
        raise BaselineError("oracle commit must be a full Git commit ID")
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{commit}:{CANONICAL_ORACLE.as_posix()}"],
        cwd=project_root,
        check=False,
        capture_output=True,
        env=git_environment(),
    )
    if result.returncode != 0:
        raise BaselineError("oracle commit does not contain the canonical oracle")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Finalize a recorded baseline with its committed immutable oracle."
    )
    parser.add_argument("--input", required=True, help="pending recorder output")
    parser.add_argument("--oracle-commit", required=True)
    return parser.parse_args()


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    args = parse_args()
    try:
        input_path = resolve_inside(project_root, args.input, "input baseline")
        output_path = project_root / CANONICAL_BASELINE
        if not input_path.is_file():
            raise BaselineError(f"input baseline does not exist: {input_path}")
        require_oracle(project_root, args.oracle_commit)
        baseline = load_object(input_path)
        baseline["canonical_oracle_commit"] = args.oracle_commit
        output_path.write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")
        digest = hashlib.sha256(output_path.read_bytes()).hexdigest()
        (project_root / CANONICAL_DIGEST).write_text(
            f"{digest}  {CANONICAL_BASELINE.as_posix()}\n",
            encoding="ascii",
        )
        print(f"finalized {CANONICAL_BASELINE} with oracle {args.oracle_commit}")
    except (BaselineError, OSError) as error:
        print(f"baseline error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
