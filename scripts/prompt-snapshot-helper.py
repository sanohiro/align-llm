#!/usr/bin/env python3
"""Content-bound workspace preflight and input snapshot helper for C6 evaluation."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import platform
import re
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
MAX_EXPANDED_ARTIFACTS = 128
MAX_STATIC_EXPECTATIONS = 64
MAX_ADDITIONAL_FILES = 32
MAX_ARTIFACT_BYTES = 1_073_741_824
GIT_OUTPUT_LIMIT = 262_144
HEX64 = frozenset("0123456789abcdef")
PR_SET_CHILD_SUBREAPER = 36
ALLOWED_LOCAL_KEYS = (
    re.compile(r"^remote\.[^.]+\.(url|pushurl|fetch)$"),
    re.compile(r"^branch\.[^.]+\.(remote|merge)$"),
)
REJECTED_EXACT_KEYS = frozenset({
    "core.alternaterefscommand", "core.askpass", "core.attributesfile", "core.editor",
    "core.excludesfile", "core.fsmonitor", "core.fsmonitorhookversion", "core.gitproxy",
    "core.hookspath", "core.pager", "core.sshcommand", "core.worktree", "credential.helper",
    "diff.external", "gpg.program", "sequence.editor", "uploadpack.packobjectshook",
})
REJECTED_KEY_PATTERNS = (
    re.compile(r"^alias\."), re.compile(r"^browser\..*\.(cmd|path)$"),
    re.compile(r"^credential\."), re.compile(r"^diff\..*\.(command|textconv)$"),
    re.compile(r"^difftool\..*\.(cmd|path)$"), re.compile(r"^filter\..*\.(clean|smudge|process)$"),
    re.compile(r"^gpg\..*\.program$"), re.compile(r"^guitool\..*\.cmd$"),
    re.compile(r"^http\..*\.proxy$"), re.compile(r"^include\."), re.compile(r"^includeif\."),
    re.compile(r"^man\..*\.(cmd|path)$"), re.compile(r"^mergetool\..*\.(cmd|path)$"),
    re.compile(r"^pager\."),
    re.compile(r"^remote\..*\.(promisor|partialclonefilter|proxy|receivepack|uploadpack)$"),
)


def enable_child_subreaper() -> bool:
    if not sys.platform.startswith("linux"):
        return False
    try:
        return ctypes.CDLL(None, use_errno=True).prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0) == 0
    except (AttributeError, OSError):
        return False


CHILD_SUBREAPER_ENABLED = enable_child_subreaper()


class SnapshotError(ValueError):
    """The snapshot boundary cannot validate its declared input."""


class SnapshotCleanupError(SnapshotError):
    """A snapshot child could not be fully removed."""


class SnapshotMismatch(SnapshotError):
    """A declared snapshot identity did not match the observed project."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


def process_group_exists(group: int) -> bool:
    try:
        os.killpg(group, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def descendant_process_ids(root_pids: set[int]) -> set[int]:
    parents: dict[int, list[int]] = {}
    for status_path in Path("/proc").glob("[0-9]*/status"):
        try:
            pid = int(status_path.parent.name)
            parent_line = next(line for line in status_path.read_text().splitlines() if line.startswith("PPid:"))
            parent = int(parent_line.split()[1])
        except (OSError, StopIteration, ValueError):
            continue
        parents.setdefault(parent, []).append(pid)
    descendants: set[int] = set()
    pending = list(root_pids)
    while pending:
        parent = pending.pop()
        for child in parents.get(parent, []):
            if child not in descendants:
                descendants.add(child)
                pending.append(child)
    return descendants


def owned_descendant_ids(process: subprocess.Popen[bytes] | None = None) -> set[int]:
    roots = {os.getpid()}
    if process is not None:
        roots.add(process.pid)
    descendants = descendant_process_ids(roots)
    descendants.discard(os.getpid())
    if process is not None:
        descendants.discard(process.pid)
    return descendants


def kill_process_ids(process_ids: set[int]) -> bool:
    complete = True
    for pid in process_ids:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except OSError:
            complete = False
    return complete


def reap_process_ids(process_ids: set[int], maximum_seconds: float) -> None:
    pending = set(process_ids)
    deadline = time.monotonic() + maximum_seconds
    while pending and time.monotonic() < deadline:
        for pid in tuple(pending):
            try:
                waited, _ = os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                if not Path(f"/proc/{pid}").exists():
                    pending.discard(pid)
                continue
            if waited == pid:
                pending.discard(pid)
        if pending:
            time.sleep(0.01)


def cleanup_process_group(process: subprocess.Popen[bytes], maximum_seconds: float = 2.0) -> bool:
    if not CHILD_SUBREAPER_ENABLED:
        return False
    complete = True
    owned = owned_descendant_ids(process)
    complete = kill_process_ids(owned)
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
    adopted = owned_descendant_ids()
    complete = kill_process_ids(adopted) and complete
    owned.update(adopted)
    reap_process_ids(owned, maximum_seconds)
    deadline = time.monotonic() + maximum_seconds
    while time.monotonic() < deadline:
        adopted = owned_descendant_ids()
        if not process_group_exists(process.pid) and not adopted:
            return complete
        complete = kill_process_ids(adopted) and complete
        reap_process_ids(adopted, 0.05)
        time.sleep(0.01)
    return complete and not process_group_exists(process.pid) and not owned_descendant_ids()


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
        raise SnapshotMismatch("PATH", "snapshot artifact is unavailable or unsafe") from None
    finally:
        os.close(current)


def digest_file(root: Path, raw: bytes, maximum_bytes: int = MAX_ARTIFACT_BYTES) -> dict[str, Any]:
    descriptor, metadata = open_relative(root, raw)
    try:
        if not stat.S_ISREG(metadata.st_mode):
            raise SnapshotMismatch("TYPE", "snapshot artifact is not a regular file")
        digest = hashlib.sha256()
        size = 0
        while True:
            chunk = os.read(descriptor, min(1_048_576, maximum_bytes + 1 - size))
            if not chunk:
                break
            size += len(chunk)
            if size > maximum_bytes:
                raise SnapshotError("snapshot artifact bytes exceed the aggregate cap")
            digest.update(chunk)
        return {
            "path": os.fsdecode(raw),
            "mode": canonical_mode(metadata),
            "byte_count": size,
            "sha256": digest.hexdigest(),
        }
    finally:
        os.close(descriptor)


def file_expectation_sha256(value: Mapping[str, Any]) -> str:
    raw = (
        value["mode"].encode("ascii") + b" " + os.fsencode(value["path"])
        + b"\0F " + value["sha256"].encode("ascii") + b"\n"
    )
    return hashlib.sha256(raw).hexdigest()


def file_mismatch_code(value: Mapping[str, Any], expected_sha256: str) -> str:
    observed_mode = value["mode"]
    for permissions in range(0o10000):
        mode = f"{stat.S_IFREG | permissions:06o}"
        if mode == observed_mode:
            continue
        candidate = dict(value)
        candidate["mode"] = mode
        if file_expectation_sha256(candidate) == expected_sha256:
            return "MODE"
    return "CONTENT"


def walk_tree(
    root: Path, raw_root: bytes, maximum_entries: int, maximum_bytes: int,
) -> tuple[list[dict[str, Any]], str, int, int]:
    base = root / os.fsdecode(raw_root)
    try:
        physical_directory(base)
    except SnapshotError:
        raise SnapshotMismatch("PATH", "snapshot tree is unavailable or unsafe") from None
    directories: list[bytes] = [raw_root]
    files_found: list[bytes] = []
    if maximum_entries < 1:
        raise SnapshotError("snapshot tree has too many entries")
    pending: list[tuple[Path, bytes]] = [(base, raw_root)]
    while pending:
        directory, relative_directory = pending.pop()
        try:
            entries = os.scandir(directory)
        except OSError:
            raise SnapshotMismatch("PATH", "snapshot tree is unavailable") from None
        with entries:
            for entry in entries:
                raw_entry = relative_directory + b"/" + os.fsencode(entry.name)
                try:
                    metadata = entry.stat(follow_symlinks=False)
                except OSError:
                    raise SnapshotMismatch("PATH", "snapshot tree entry is unavailable") from None
                if stat.S_ISLNK(metadata.st_mode):
                    raise SnapshotMismatch("TYPE", "snapshot tree contains a symlink")
                if stat.S_ISDIR(metadata.st_mode):
                    directories.append(raw_entry)
                    pending.append((Path(entry.path), raw_entry))
                elif stat.S_ISREG(metadata.st_mode):
                    files_found.append(raw_entry)
                else:
                    raise SnapshotMismatch("TYPE", "snapshot tree contains a non-regular entry")
                if len(directories) + len(files_found) > maximum_entries:
                    raise SnapshotError("snapshot tree has too many entries")
    directories.sort()
    files_found.sort()
    file_digests: dict[bytes, dict[str, Any]] = {}
    byte_count = 0
    for entry in files_found:
        value = digest_file(root, entry, maximum_bytes - byte_count)
        byte_count += value["byte_count"]
        file_digests[entry] = value
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
    return values, tree_sha256, len(directories) + len(files_found), byte_count


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


def resolve_git_metadata(repository: Path) -> tuple[Path, Path]:
    root = physical_directory(repository)
    dotgit = root / ".git"
    try:
        metadata = os.lstat(dotgit)
    except OSError:
        raise SnapshotError("task repository Git metadata is unavailable") from None
    if stat.S_ISDIR(metadata.st_mode):
        git_dir = physical_directory(dotgit)
    elif stat.S_ISREG(metadata.st_mode):
        raw = read_bounded(dotgit, 4096)
        if not raw.startswith(b"gitdir: ") or not raw.endswith(b"\n") or raw.count(b"\n") != 1:
            raise SnapshotError("task repository gitdir pointer is malformed")
        candidate = Path(os.fsdecode(raw[8:-1]))
        if not candidate.is_absolute():
            candidate = root / candidate
        git_dir = physical_directory(candidate)
    else:
        raise SnapshotError("task repository .git is unsafe")
    commondir_path = git_dir / "commondir"
    if commondir_path.exists() or commondir_path.is_symlink():
        raw = read_bounded(commondir_path, 4096)
        if not raw.endswith(b"\n") or raw.count(b"\n") != 1 or b"\x00" in raw:
            raise SnapshotError("task repository commondir pointer is malformed")
        candidate = Path(os.fsdecode(raw[:-1]))
        if not candidate.is_absolute():
            candidate = git_dir / candidate
        common_dir = physical_directory(candidate)
    else:
        common_dir = git_dir
    return git_dir, common_dir


def reject_command_bearing_config(raw: bytes) -> None:
    if len(raw) > 4_194_304 or b"\x00" in raw:
        raise SnapshotError("task repository Git config is malformed or too large")
    section = ""
    for source_line in raw.splitlines():
        line = source_line.strip()
        if not line or line.startswith((b"#", b";")):
            continue
        if line.startswith(b"[") and line.endswith(b"]"):
            try:
                header = line[1:-1].decode("utf-8", "strict").strip().lower()
            except UnicodeError:
                raise SnapshotError("task repository Git config section is invalid") from None
            match = re.fullmatch(r'([a-z0-9-]+)(?:\s+"((?:[^"\\]|\\.)*)")?', header)
            if match is None:
                raise SnapshotError("task repository Git config section is malformed")
            section = match.group(1)
            if match.group(2) is not None:
                section += "." + match.group(2).replace('\\"', '"').lower()
            continue
        if not section or b"=" not in line:
            raise SnapshotError("task repository Git config assignment is malformed")
        raw_key, _ = line.split(b"=", 1)
        try:
            key = f"{section}.{raw_key.decode('ascii', 'strict').strip().lower()}"
        except UnicodeError:
            raise SnapshotError("task repository Git config key is invalid") from None
        rejected = key in REJECTED_EXACT_KEYS or any(pattern.match(key) for pattern in REJECTED_KEY_PATTERNS)
        allowed = any(pattern.fullmatch(key) for pattern in ALLOWED_LOCAL_KEYS)
        if rejected and not allowed:
            raise SnapshotError("task repository Git config has a command-bearing key")


def reject_git_extensions(repository: Path) -> None:
    git_dir, common_dir = resolve_git_metadata(repository)
    for config in (common_dir / "config", git_dir / "config.worktree"):
        if config.exists() or config.is_symlink():
            reject_command_bearing_config(read_bounded(config, 4_194_304))
    for candidate in (
        common_dir / "refs" / "replace",
        common_dir / "info" / "grafts",
        common_dir / "objects" / "info" / "alternates",
    ):
        if candidate.exists() or candidate.is_symlink():
            raise SnapshotError("task repository Git replacement metadata is present")


def git_identity(
    repository: Path,
    expected: str,
    require_clean: bool,
    git: Path = Path(os.environ.get("ALIGN_LLM_TOOL_ROOT", "/usr/bin")) / "git",
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
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_PAGER": "cat",
        "GIT_NO_LAZY_FETCH": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_GRAFT_FILE": "/dev/null",
    }
    reject_git_extensions(repository)
    def fixed_git(*arguments: str) -> bytes:
        if not CHILD_SUBREAPER_ENABLED:
            raise SnapshotCleanupError("task repository child containment is unavailable")
        try:
            process = subprocess.Popen(
                [
                    str(git), "--no-pager", "-C", str(repository),
                    "-c", "core.useReplaceRefs=false",
                    "-c", "core.alternateRefsCommand=",
                    "-c", "core.fsmonitor=false",
                    "-c", "core.hooksPath=/dev/null",
                    "-c", "credential.helper=",
                    "-c", "diff.external=",
                    *arguments,
                ],
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
        cleanup_attempted = False
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
            if process_group_exists(process.pid) or owned_descendant_ids(process):
                cleanup_attempted = True
                if not cleanup_process_group(process):
                    raise SnapshotCleanupError("task repository Git command cleanup failed")
                raise SnapshotError("task repository Git command left a descendant")
        except (OSError, subprocess.TimeoutExpired, SnapshotError) as failure:
            if not cleanup_attempted:
                cleanup_attempted = True
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

    replacement = fixed_git("for-each-ref", "--format=%(refname)%00", "refs/replace/")
    if replacement:
        raise SnapshotError("task repository Git replacement namespace is non-empty")
    head = fixed_git("rev-parse", "--verify", "HEAD")
    status = fixed_git("status", "--porcelain=v1", "-z", "--untracked-files=all")
    if head.decode("ascii", "strict").strip() != expected:
        raise SnapshotMismatch("REPO_REVISION", "task repository revision does not match")
    if status:
        raise SnapshotMismatch("DIRTY_REPO", "task repository is dirty")


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
            raise SnapshotMismatch("PATH", "workspace contains an undeclared entry")
        static_expectations = value["static_expectations"]
        additional_files = value["additional_files"]
        if (
            not isinstance(static_expectations, list)
            or len(static_expectations) > MAX_STATIC_EXPECTATIONS
            or not isinstance(additional_files, list)
            or len(additional_files) > MAX_ADDITIONAL_FILES
        ):
            raise SnapshotError("snapshot declaration count exceeds its bound")
        digests: list[dict[str, Any]] = []
        expanded_entries = 0
        expanded_bytes = 0
        for expectation in static_expectations:
            raw = relative_path(expectation["path"])
            if expectation["kind"] == "FILE":
                if expanded_entries >= MAX_EXPANDED_ARTIFACTS:
                    raise SnapshotError("snapshot has too many expanded entries")
                value_digest = digest_file(project, raw, MAX_ARTIFACT_BYTES - expanded_bytes)
                values = [value_digest]
                observed_sha256 = file_expectation_sha256(values[0])
                entry_count = 1
                byte_count = value_digest["byte_count"]
            elif expectation["kind"] == "TREE":
                values, observed_sha256, entry_count, byte_count = walk_tree(
                    project,
                    raw,
                    MAX_EXPANDED_ARTIFACTS - expanded_entries,
                    MAX_ARTIFACT_BYTES - expanded_bytes,
                )
            else:
                raise SnapshotError("snapshot expectation kind is invalid")
            if not values or observed_sha256 != expectation["expected_sha256"]:
                code = (
                    "TREE" if expectation["kind"] == "TREE"
                    else file_mismatch_code(values[0], expectation["expected_sha256"])
                )
                raise SnapshotMismatch(code, "snapshot expectation digest does not match")
            expanded_entries += entry_count
            expanded_bytes += byte_count
            digests.extend(values)
        for item in additional_files:
            value_digest = digest_file(
                project, relative_path(item), MAX_ARTIFACT_BYTES - expanded_bytes,
            )
            expanded_bytes += value_digest["byte_count"]
            digests.append(value_digest)
        result.update(
            status="MATCH",
            error_code="NONE",
            error="",
            environment_probe=environment_probe(),
            artifact_digests=digests,
        )
    except SnapshotMismatch as mismatch:
        result.update(status="MISMATCH", error_code=mismatch.code, error=mismatch.detail)
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


def write_retained_result(path: Path, descriptor: int, value: Mapping[str, Any]) -> None:
    raw = canonical_bytes(value)
    if len(raw) > RESULT_LIMIT:
        raise SnapshotError("snapshot result exceeds its bound")
    descriptor_metadata = os.fstat(descriptor)
    path_metadata = os.stat(path, follow_symlinks=False)
    if (
        not stat.S_ISREG(descriptor_metadata.st_mode)
        or descriptor_metadata.st_size != 0
        or (descriptor_metadata.st_dev, descriptor_metadata.st_ino)
        != (path_metadata.st_dev, path_metadata.st_ino)
    ):
        raise SnapshotError("snapshot result descriptor identity is invalid")
    offset = 0
    while offset < len(raw):
        offset += os.write(descriptor, raw[offset:])
    os.fsync(descriptor)


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
    parser.add_argument("--result-fd", type=int)
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
            result = snapshot(request)
            if values.result_fd is None:
                write_exclusive(values.result, result)
            else:
                write_retained_result(values.result, values.result_fd, result)
        return 0
    except (OSError, SnapshotError):
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
