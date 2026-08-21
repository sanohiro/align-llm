#!/usr/bin/env python3
"""Content-bound workspace preflight and input snapshot helper for C6 evaluation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import selectors
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence


REQUEST_LIMIT = 1_048_576
RESULT_LIMIT = 1_048_576
MAX_ARTIFACTS = 4096
GIT_OUTPUT_LIMIT = 262_144
HEX64 = frozenset("0123456789abcdef")


class SnapshotError(ValueError):
    """The snapshot boundary cannot validate its declared input."""


class SnapshotCleanupError(SnapshotError):
    """A snapshot child could not be fully removed."""


def process_group_exists(group: int) -> bool:
    try:
        os.killpg(group, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def cleanup_process_group(process: subprocess.Popen[bytes], maximum_seconds: float = 2.0) -> bool:
    complete = True
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except OSError:
        complete = False
    try:
        process.wait(timeout=maximum_seconds)
    except (OSError, subprocess.TimeoutExpired):
        complete = False
    deadline = time.monotonic() + maximum_seconds
    while process_group_exists(process.pid) and time.monotonic() < deadline:
        time.sleep(0.01)
    return complete and not process_group_exists(process.pid)


def canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def canonical_digest_bytes(value: Any) -> bytes:
    def omit_none(item: Any) -> Any:
        if isinstance(item, dict):
            return {key: omit_none(child) for key, child in item.items() if child is not None}
        if isinstance(item, list):
            return [omit_none(child) for child in item]
        return item

    return canonical_bytes(omit_none(value))


def bind_digest(value: dict[str, Any]) -> None:
    value["content_sha256"] = ""
    value["content_sha256"] = hashlib.sha256(canonical_digest_bytes(value)).hexdigest()


def runtime_identity() -> str:
    return "PYTHON:" + hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def valid_digest(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in HEX64 for character in value)


def canonical_mode(metadata: os.stat_result) -> str:
    return f"{stat.S_IFMT(metadata.st_mode) | stat.S_IMODE(metadata.st_mode):06o}"


def read_bounded(path: Path, maximum: int) -> bytes:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    except OSError as error:
        raise SnapshotError("snapshot input is unavailable") from None
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size < 0 or metadata.st_size > maximum:
            raise SnapshotError("snapshot input type or size is invalid")
        result = bytearray()
        while len(result) <= maximum:
            chunk = os.read(descriptor, min(65_536, maximum + 1 - len(result)))
            if not chunk:
                break
            result.extend(chunk)
        if len(result) > maximum:
            raise SnapshotError("snapshot input exceeds its limit")
        return bytes(result)
    finally:
        os.close(descriptor)


def decode_request(path: Path, kind: str, fields: tuple[str, ...]) -> dict[str, Any]:
    try:
        value = json.loads(read_bounded(path, REQUEST_LIMIT).decode("utf-8", "strict"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise SnapshotError("snapshot request is not valid UTF-8 JSON") from None
    if not isinstance(value, dict) or tuple(value) != fields:
        raise SnapshotError("snapshot request fields are invalid")
    if value["schema_version"] != 1 or value["artifact_kind"] != kind or not valid_digest(value["content_sha256"]):
        raise SnapshotError("snapshot request header is invalid")
    normalized = dict(value)
    normalized["content_sha256"] = ""
    if hashlib.sha256(canonical_digest_bytes(normalized)).hexdigest() != value["content_sha256"]:
        raise SnapshotError("snapshot request digest does not match")
    return value


def physical_directory(path: Path) -> Path:
    if not path.is_absolute():
        raise SnapshotError("snapshot root is not absolute")
    current = Path("/")
    for component in path.parts[1:]:
        current /= component
        try:
            metadata = os.lstat(current)
        except OSError as error:
            raise SnapshotError("snapshot root is unavailable") from None
        if stat.S_ISLNK(metadata.st_mode):
            raise SnapshotError("snapshot root contains a symlink component")
    if not stat.S_ISDIR(os.stat(path, follow_symlinks=False).st_mode):
        raise SnapshotError("snapshot root is not a directory")
    return path.resolve(strict=True)


def relative_path(value: Any) -> bytes:
    if not isinstance(value, str) or not value or "\x00" in value or len(value.encode()) > 4096:
        raise SnapshotError("snapshot relative path is invalid")
    raw = os.fsencode(value)
    if raw.startswith(b"/") or any(part in (b"", b".", b"..") for part in raw.split(b"/")):
        raise SnapshotError("snapshot relative path components are invalid")
    return raw


def open_relative(root: Path, raw: bytes) -> tuple[int, os.stat_result]:
    current = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        parts = raw.split(b"/")
        for component in parts[:-1]:
            next_descriptor = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=current)
            os.close(current)
            current = next_descriptor
        descriptor = os.open(parts[-1], os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=current)
        return descriptor, os.fstat(descriptor)
    except OSError as error:
        raise SnapshotError("snapshot artifact is unavailable or unsafe") from None
    finally:
        os.close(current)


def digest_file(root: Path, raw: bytes) -> dict[str, Any]:
    descriptor, metadata = open_relative(root, raw)
    try:
        if not stat.S_ISREG(metadata.st_mode):
            raise SnapshotError("snapshot artifact is not a regular file")
        digest = hashlib.sha256()
        size = 0
        while True:
            chunk = os.read(descriptor, 1_048_576)
            if not chunk:
                break
            size += len(chunk)
            digest.update(chunk)
        return {
            "path": os.fsdecode(raw),
            "mode": canonical_mode(metadata),
            "byte_count": size,
            "sha256": digest.hexdigest(),
        }
    finally:
        os.close(descriptor)


def walk_tree(root: Path, raw_root: bytes) -> tuple[list[dict[str, Any]], str]:
    base = root / os.fsdecode(raw_root)
    physical_directory(base)
    directories: list[bytes] = [raw_root]
    files_found: list[bytes] = []
    for directory, names, files in os.walk(base, topdown=True, followlinks=False):
        names.sort(key=os.fsencode)
        files.sort(key=os.fsencode)
        relative_directory = os.fsencode(os.path.relpath(directory, root))
        for name in names:
            candidate = Path(directory) / name
            if candidate.is_symlink():
                raise SnapshotError("snapshot tree contains a symlink")
            directories.append(relative_directory + b"/" + os.fsencode(name))
        for name in files:
            candidate = Path(directory) / name
            if candidate.is_symlink() or not candidate.is_file():
                raise SnapshotError("snapshot tree contains a non-regular entry")
            files_found.append(relative_directory + b"/" + os.fsencode(name))
    directories = sorted(set(directories))
    files_found.sort()
    if len(directories) + len(files_found) > MAX_ARTIFACTS:
        raise SnapshotError("snapshot tree has too many files")
    file_digests = {os.fsencode(value["path"]): value for value in (digest_file(root, entry) for entry in files_found)}
    manifest = bytearray()
    for entry in sorted((*directories, *files_found)):
        metadata = os.stat(root / os.fsdecode(entry), follow_symlinks=False)
        mode = canonical_mode(metadata).encode("ascii")
        if entry in file_digests:
            manifest.extend(mode + b" " + entry + b"\0F " + file_digests[entry]["sha256"].encode("ascii") + b"\n")
        else:
            manifest.extend(mode + b" " + entry + b"\0D\n")
    tree_sha256 = hashlib.sha256(manifest).hexdigest()
    values: list[dict[str, Any]] = []
    for entry in sorted((*directories, *files_found)):
        if entry in file_digests:
            values.append(file_digests[entry])
        else:
            metadata = os.stat(root / os.fsdecode(entry), follow_symlinks=False)
            values.append({
                "path": os.fsdecode(entry),
                "mode": canonical_mode(metadata),
                "byte_count": 0,
                "sha256": tree_sha256,
            })
    return values, tree_sha256


def environment_probe() -> dict[str, Any]:
    logical = os.cpu_count()
    value = {
        "schema_version": 1,
        "artifact_kind": "ENVIRONMENT_PROBE",
        "producer": "SNAPSHOT_HELPER",
        "os": platform.system().lower(),
        "os_release": platform.release(),
        "architecture": platform.machine().lower(),
        "cpu": platform.processor() or platform.machine().lower(),
        "logical_cpu_count": logical if logical and logical > 0 else None,
        "gpu": "none",
        "runtime_identity": runtime_identity(),
        "content_sha256": "",
    }
    bind_digest(value)
    return value


def safe_workspace(project: Path, workspace: Path, *, require_empty: bool) -> tuple[Path, Path]:
    project_root = physical_directory(project)
    workspace_root = physical_directory(workspace)
    try:
        workspace_root.relative_to(project_root)
    except ValueError as error:
        raise SnapshotError("workspace escapes the project root") from None
    if workspace_root == project_root:
        raise SnapshotError("workspace aliases the project root")
    if require_empty and any(os.scandir(workspace_root)):
        raise SnapshotError("workspace is not empty")
    return project_root, workspace_root


def workspace_preflight(value: dict[str, Any]) -> dict[str, Any]:
    result = {
        "schema_version": 1,
        "artifact_kind": "WORKSPACE_PREFLIGHT_RESULT",
        "evaluation_id": value["evaluation_id"],
        "status": "UNSAFE",
        "error_code": "NOT_EMPTY",
        "error": "workspace preflight failed",
        "physical_project_root": "",
        "physical_workspace_path": "",
        "environment_probe": None,
        "content_sha256": "",
    }
    try:
        project, workspace = safe_workspace(Path(value["project_root"]), Path(value["workspace_path"]), require_empty=True)
        result.update(
            status="SAFE",
            error_code="NONE",
            error="",
            physical_project_root=str(project),
            physical_workspace_path=str(workspace),
            environment_probe=environment_probe(),
        )
    except (OSError, SnapshotError):
        pass
    bind_digest(result)
    return result


def git_identity(
    repository: Path, expected: str, require_clean: bool, git: Path = Path("/usr/bin/git")
) -> None:
    if not require_clean:
        return
    environment = {
        "LANG": "C",
        "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_GRAFT_FILE": "/dev/null",
    }
    def fixed_git(*arguments: str) -> bytes:
        try:
            process = subprocess.Popen(
                [str(git), "--no-pager", "-C", str(repository), *arguments],
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                start_new_session=True,
            )
        except OSError:
            raise SnapshotError("task repository Git command is unavailable") from None
        output = bytearray()
        selector = selectors.DefaultSelector()
        deadline = time.monotonic() + 10
        try:
            assert process.stdout is not None
            os.set_blocking(process.stdout.fileno(), False)
            selector.register(process.stdout, selectors.EVENT_READ)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise SnapshotError("task repository Git command timed out")
                events = selector.select(remaining)
                if not events:
                    raise SnapshotError("task repository Git command timed out")
                for key, _ in events:
                    try:
                        chunk = os.read(key.fileobj.fileno(), min(65_536, GIT_OUTPUT_LIMIT + 1 - len(output)))
                    except BlockingIOError:
                        continue
                    if not chunk:
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                        continue
                    output.extend(chunk)
                    if len(output) > GIT_OUTPUT_LIMIT:
                        raise SnapshotError("task repository Git output exceeded its cap")
            process.wait(timeout=max(0.001, deadline - time.monotonic()))
            if process_group_exists(process.pid):
                if not cleanup_process_group(process):
                    raise SnapshotCleanupError("task repository Git command cleanup failed")
                raise SnapshotError("task repository Git command left a descendant")
        except (OSError, subprocess.TimeoutExpired, SnapshotError) as failure:
            if not cleanup_process_group(process):
                raise SnapshotCleanupError("task repository Git command cleanup failed") from None
            if isinstance(failure, SnapshotCleanupError):
                raise failure
            raise SnapshotError("task repository Git command failed") from None
        finally:
            selector.close()
            if process.stdout is not None and not process.stdout.closed:
                process.stdout.close()
        if process.returncode != 0:
            raise SnapshotError("task repository Git command failed")
        return bytes(output)

    head = fixed_git("rev-parse", "--verify", "HEAD")
    status = fixed_git("status", "--porcelain=v1", "-z", "--untracked-files=all")
    if head.decode("ascii", "strict").strip() != expected or status:
        raise SnapshotError("task repository identity does not match")


def snapshot(value: dict[str, Any]) -> dict[str, Any]:
    try:
        initial_probe = environment_probe()
        initial_code = "INTERNAL"
    except (OSError, SnapshotError):
        initial_probe = None
        initial_code = "ENVIRONMENT"
    result = {
        "schema_version": 1,
        "artifact_kind": "SNAPSHOT_RESULT",
        "task_id": value["task_id"],
        "status": "ERROR",
        "error_code": initial_code,
        "error": "snapshot validation failed",
        "environment_probe": initial_probe,
        "artifact_digests": [],
        "content_sha256": "",
    }
    try:
        project = physical_directory(Path(value["project_root"]))
        repository_path = Path(value["repo_path"])
        if not repository_path.is_absolute():
            repository_path = project / repository_path
        repository = physical_directory(repository_path)
        _, workspace = safe_workspace(project, Path(value["workspace_path"]), require_empty=False)
        git_identity(repository, value["repo_revision"], value["require_clean_repo"])
        allowed = {os.fsdecode(relative_path(item)) for item in value["allowed_workspace_entries"]}
        actual = {entry.name for entry in os.scandir(workspace)}
        if not actual.issubset(allowed):
            raise SnapshotError("workspace contains an undeclared entry")
        digests: list[dict[str, Any]] = []
        for expectation in value["static_expectations"]:
            raw = relative_path(expectation["path"])
            if expectation["kind"] == "FILE":
                values = [digest_file(project, raw)]
                observed_sha256 = values[0]["sha256"]
            elif expectation["kind"] == "TREE":
                values, observed_sha256 = walk_tree(project, raw)
            else:
                raise SnapshotError("snapshot expectation kind is invalid")
            if not values or observed_sha256 != expectation["expected_sha256"]:
                raise SnapshotError("snapshot expectation digest does not match")
            digests.extend(values)
        for item in value["additional_files"]:
            digests.append(digest_file(project, relative_path(item)))
        if len(digests) > MAX_ARTIFACTS:
            raise SnapshotError("snapshot has too many artifact digests")
        result.update(
            status="MATCH",
            error_code="NONE",
            error="",
            environment_probe=environment_probe(),
            artifact_digests=digests,
        )
    except SnapshotCleanupError:
        result["error_code"] = "CLEANUP"
    except (OSError, SnapshotError, subprocess.SubprocessError, UnicodeError):
        pass
    bind_digest(result)
    return result


def write_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    raw = canonical_bytes(value)
    if len(raw) > RESULT_LIMIT:
        raise SnapshotError("snapshot result exceeds its bound")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
    try:
        offset = 0
        while offset < len(raw):
            offset += os.write(descriptor, raw[offset:])
    finally:
        os.close(descriptor)


PREFLIGHT_FIELDS = (
    "schema_version", "artifact_kind", "evaluation_id", "project_root", "workspace_path", "content_sha256",
)
SNAPSHOT_FIELDS = (
    "schema_version", "artifact_kind", "task_id", "project_root", "repo_path", "repo_revision",
    "require_clean_repo", "static_expectations", "additional_files", "workspace_path",
    "allowed_workspace_entries", "content_sha256",
)


def parse_arguments(arguments: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--workspace-preflight-request", type=Path)
    group.add_argument("--snapshot-request", type=Path)
    parser.add_argument("--result", type=Path)
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    values = parse_arguments(sys.argv[1:] if arguments is None else arguments)
    try:
        if values.workspace_preflight_request is not None:
            if values.result is not None:
                raise SnapshotError("workspace preflight does not accept a result path")
            request = decode_request(values.workspace_preflight_request, "WORKSPACE_PREFLIGHT_REQUEST", PREFLIGHT_FIELDS)
            raw = canonical_bytes(workspace_preflight(request))
            if len(raw) > 65_536:
                raise SnapshotError("workspace preflight result exceeds its bound")
            os.write(sys.stdout.fileno(), raw)
        else:
            if values.result is None:
                raise SnapshotError("snapshot mode requires a result path")
            request = decode_request(values.snapshot_request, "SNAPSHOT_REQUEST", SNAPSHOT_FIELDS)
            write_exclusive(values.result, snapshot(request))
        return 0
    except (OSError, SnapshotError):
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
