#!/usr/bin/env python3
"""Shared local and hosted verification-scope classification."""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence


REPOSITORY = Path(__file__).resolve().parent.parent

# This is the installed profile's executable ownership boundary. Keep it here only: the local
# preflight and both hosted jobs consume the classifier instead of copying this inventory. A pin by
# itself is deliberately not in this set: provider platform CI owns compiler portability, while the
# consumer CI retains its ordinary hosted graph and local preflight runs the request owner.
FRESH_IMAGE_PATTERNS = (
    "Makefile",
    ".github/workflows/ci.yml",
    "eval/runners/run-coding-task.py",
    "image/fresh/*",
    "scripts/alignc",
    "scripts/build-fresh-image-control",
    "scripts/ci-align-bundle",
    "scripts/classify-verification",
    "scripts/fresh-align-compiler",
    "scripts/fresh-alignc",
    "scripts/fresh-image-attest",
    "scripts/fresh_attestation.py",
    "scripts/fresh_manifest.py",
    "scripts/generate-fresh-toolchain-manifest",
    "scripts/materialize-fresh-tree",
    "scripts/pre-pr",
    "scripts/prepare-fresh-image-build",
    "scripts/run-baseline-*",
    "scripts/run-coding-task-*",
    "scripts/run-fresh-attestation-wire-smoke",
    "scripts/run-fresh-image-control-smoke",
    "scripts/run-fresh-image-profile-smoke",
    "scripts/run-fresh-worker-*",
    "scripts/run-loop-smoke",
    "scripts/select-ci-reuse",
    "scripts/signal_subprocess.py",
    "scripts/test-development-preflight",
    "scripts/test-ci-align-bundle",
    "scripts/verification_scope.py",
)

LIGHT_STATUSES = frozenset(("A", "M"))
KNOWN_STATUSES = frozenset(("A", "C", "D", "M", "R", "T", "U", "X", "B"))


class ScopeError(RuntimeError):
    """Raised when the requested comparison cannot be classified safely."""


@dataclass(frozen=True)
class Scope:
    scope: str
    base: str
    head: str
    docs_only: bool
    hosted: bool
    fresh_focused: bool
    fresh_installed: bool

    def scalars(self) -> dict[str, str]:
        return {
            "scope": self.scope,
            "base": self.base,
            "head": self.head,
            "docs_only": str(self.docs_only).lower(),
            "hosted": str(self.hosted).lower(),
            "fresh_focused": str(self.fresh_focused).lower(),
            "fresh_installed": str(self.fresh_installed).lower(),
        }


def git(*arguments: str, repository: Path = REPOSITORY) -> bytes:
    result = subprocess.run(
        ("git", *arguments),
        cwd=repository,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        diagnostic = result.stderr.decode("utf-8", "replace").strip()
        raise ScopeError(f"git {' '.join(arguments)} failed: {diagnostic}")
    return result.stdout


def resolve_commit(reference: str, repository: Path = REPOSITORY) -> str:
    if not reference or "\x00" in reference or "\n" in reference or "\r" in reference:
        raise ScopeError("verification reference is empty or not line-safe")
    value = git("rev-parse", "--verify", f"{reference}^{{commit}}", repository=repository)
    decoded = value.decode("ascii", "strict").strip()
    if len(decoded) != 40 or any(character not in "0123456789abcdef" for character in decoded):
        raise ScopeError("verification reference did not resolve to a full commit identity")
    return decoded


def merge_base(base: str, head: str, repository: Path = REPOSITORY) -> str:
    value = git("merge-base", base, head, repository=repository).decode("ascii", "strict").strip()
    if len(value) != 40 or any(character not in "0123456789abcdef" for character in value):
        raise ScopeError("verification merge base is not a full commit identity")
    return value


def parse_name_status(raw: bytes) -> list[tuple[str, str]]:
    if raw and not raw.endswith(b"\x00"):
        raise ScopeError("verification diff has unterminated name-status output")
    fields = raw.split(b"\x00")
    if fields and fields[-1] == b"":
        fields.pop()
    if len(fields) % 2 != 0:
        raise ScopeError("verification diff has malformed name-status output")
    changes: list[tuple[str, str]] = []
    for index in range(0, len(fields), 2):
        try:
            status = fields[index].decode("ascii", "strict")
            path = fields[index + 1].decode("utf-8", "strict")
        except UnicodeError as error:
            raise ScopeError("verification diff contains an undecodable status or path") from error
        if len(status) != 1 or status not in KNOWN_STATUSES:
            raise ScopeError(f"verification diff contains unsupported status: {status!r}")
        if not path or path.startswith("/") or "\x00" in path:
            raise ScopeError("verification diff contains an invalid repository path")
        changes.append((status, path))
    return changes


def diff_changes(base: str, head: str, repository: Path = REPOSITORY) -> list[tuple[str, str]]:
    raw = git(
        "diff",
        "--name-status",
        "-z",
        "--no-renames",
        f"{base}...{head}",
        repository=repository,
    )
    return parse_name_status(raw)


def owns_fresh_image(path: str) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in FRESH_IMAGE_PATTERNS)


def classify_changes(
    changes: Sequence[tuple[str, str]], *, base: str, head: str
) -> Scope:
    if not changes:
        raise ScopeError("verification diff is empty")
    docs_only = all(
        status in LIGHT_STATUSES and path.endswith(".md") for status, path in changes
    )
    if docs_only:
        return Scope("docs", base, head, True, False, False, False)
    pin_only = any(path == ".align-revision" for _, path in changes) and all(
        status in LIGHT_STATUSES and (path == ".align-revision" or path.endswith(".md"))
        for status, path in changes
    )
    if pin_only:
        return Scope("pin", base, head, False, True, False, False)
    fresh = any(
        owns_fresh_image(path) or (path == ".align-revision" and status not in LIGHT_STATUSES)
        for status, path in changes
    )
    return Scope(
        "fresh-image" if fresh else "hosted",
        base,
        head,
        False,
        True,
        fresh,
        fresh,
    )


def classify_refs(base_ref: str, head_ref: str, repository: Path = REPOSITORY) -> Scope:
    base_commit = resolve_commit(base_ref, repository)
    head_commit = resolve_commit(head_ref, repository)
    comparison_base = merge_base(base_commit, head_commit, repository)
    return classify_changes(
        diff_changes(comparison_base, head_commit, repository),
        base=comparison_base,
        head=head_commit,
    )


def all_scope(head_ref: str, repository: Path = REPOSITORY) -> Scope:
    head = resolve_commit(head_ref, repository)
    return Scope("fresh-image", "", head, False, True, True, True)


def write_github_output(path: Path, scope: Scope) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as output:
        for name, value in scope.scalars().items():
            output.write(f"{name}={value}\n")


def parse_arguments(arguments: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base")
    parser.add_argument("--head", required=True)
    parser.add_argument("--all", action="store_true", dest="select_all")
    parser.add_argument("--github-output", type=Path)
    values = parser.parse_args(arguments)
    if values.select_all == (values.base is not None):
        parser.error("pass exactly one of --base REF or --all")
    return values


def main(arguments: Sequence[str] | None = None) -> int:
    values = parse_arguments(sys.argv[1:] if arguments is None else arguments)
    try:
        scope = (
            all_scope(values.head)
            if values.select_all
            else classify_refs(values.base, values.head)
        )
        if values.github_output is not None:
            write_github_output(values.github_output, scope)
        print(json.dumps(asdict(scope), sort_keys=True, separators=(",", ":")))
        return 0
    except (OSError, ScopeError) as error:
        print(f"verification scope error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
