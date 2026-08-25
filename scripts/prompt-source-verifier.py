#!/usr/bin/env python3
"""Bounded, non-ambient source verifier for C6 evaluation evidence."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import re
import selectors
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence


REQUEST_LIMIT = 65_536
RESULT_LIMIT = 262_144
MANIFEST_LIMIT = 8_388_608
GIT_OUTPUT_LIMIT = 262_144
PR_SET_CHILD_SUBREAPER = 36


def enable_child_subreaper() -> bool:
    if not sys.platform.startswith("linux"):
        return False
    try:
        return ctypes.CDLL(None, use_errno=True).prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0) == 0
    except (AttributeError, OSError):
        return False


CHILD_SUBREAPER_ENABLED = enable_child_subreaper()
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
DECIMAL = re.compile(rb"^(0|[1-9][0-9]*)$")
MODE = re.compile(rb"^[0-7]{6}$")
REQUEST_FIELDS = (
    "schema_version",
    "artifact_kind",
    "mode",
    "align_llm_repository_path",
    "expected_align_llm_commit",
    "tested_align_llm_head",
    "align_repository_path",
    "expected_align_revision",
    "corpus_source_path",
    "corpus_source_kind",
    "corpus_file_set_manifest_path",
    "expected_corpus_source_repository_id",
    "expected_corpus_source_sha256",
    "git_executable_path",
    "git_executable_sha256",
    "content_sha256",
)
REQUEST_FIELDS_OMITTED = tuple(
    name for name in REQUEST_FIELDS if name != "corpus_file_set_manifest_path"
)
RESULT_FIELDS = (
    "schema_version",
    "artifact_kind",
    "status",
    "error_code",
    "error",
    "align_llm_reachability",
    "align_llm_observed_head",
    "align_reachability",
    "align_observed_revision",
    "corpus_reachability",
    "corpus_observed_source_sha256",
    "content_sha256",
)
ALLOWED_LOCAL_KEYS = (
    re.compile(r"^remote\.[^.]+\.(url|pushurl|fetch)$"),
    re.compile(r"^branch\.[^.]+\.(remote|merge)$"),
)
REJECTED_EXACT_KEYS = frozenset(
    {
        "core.alternaterefscommand",
        "core.askpass",
        "core.attributesfile",
        "core.editor",
        "core.excludesfile",
        "core.fsmonitor",
        "core.fsmonitorhookversion",
        "core.gitproxy",
        "core.hookspath",
        "core.pager",
        "core.sshcommand",
        "core.worktree",
        "credential.helper",
        "diff.external",
        "gpg.program",
        "sequence.editor",
        "uploadpack.packobjectshook",
    }
)
REJECTED_KEY_PATTERNS = (
    re.compile(r"^alias\."),
    re.compile(r"^browser\..*\.(cmd|path)$"),
    re.compile(r"^credential\."),
    re.compile(r"^diff\..*\.(command|textconv)$"),
    re.compile(r"^difftool\..*\.(cmd|path)$"),
    re.compile(r"^filter\..*\.(clean|smudge|process)$"),
    re.compile(r"^gpg\..*\.program$"),
    re.compile(r"^guitool\..*\.cmd$"),
    re.compile(r"^http\..*\.proxy$"),
    re.compile(r"^include\."),
    re.compile(r"^includeif\."),
    re.compile(r"^man\..*\.(cmd|path)$"),
    re.compile(r"^mergetool\..*\.(cmd|path)$"),
    re.compile(r"^pager\."),
    re.compile(r"^remote\..*\.(promisor|partialclonefilter|proxy|receivepack|uploadpack)$"),
)


class VerificationError(ValueError):
    """The verifier request or a trusted source boundary is malformed."""


class VerificationCleanupError(VerificationError):
    """A source-verifier child could not be fully removed."""


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


def read_bounded(path: Path, limit: int) -> bytes:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    except OSError as error:
        raise VerificationError("bounded input is not a regular readable file") from None
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size < 0 or metadata.st_size > limit:
            raise VerificationError("bounded input has an invalid type or size")
        data = bytearray()
        while len(data) <= limit:
            chunk = os.read(descriptor, min(65_536, limit + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
        if len(data) > limit:
            raise VerificationError("bounded input exceeds its limit")
        return bytes(data)
    finally:
        os.close(descriptor)


def json_object(raw: bytes, label: str) -> dict[str, Any]:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, child in pairs:
            if key in value:
                raise VerificationError(f"{label} has a duplicate field")
            value[key] = child
        return value

    try:
        value = json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=unique_object)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise VerificationError(f"{label} is not valid UTF-8 JSON") from None
    if not isinstance(value, dict):
        raise VerificationError(f"{label} is not an object")
    return value


def sha256_file(path: Path, limit: int = 268_435_456) -> str:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    except OSError as error:
        raise VerificationError("declared executable is not a regular readable file") from None
    digest = hashlib.sha256()
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size < 0 or metadata.st_size > limit:
            raise VerificationError("declared executable has an invalid type or size")
        remaining = metadata.st_size
        while remaining:
            chunk = os.read(descriptor, min(1_048_576, remaining))
            if not chunk:
                raise VerificationError("declared executable changed while reading")
            digest.update(chunk)
            remaining -= len(chunk)
        return digest.hexdigest()
    finally:
        os.close(descriptor)


class RetainedExecutable:
    """A regular executable pinned by descriptor for every Git child."""

    def __init__(self, path: Path, maximum: int = 268_435_456) -> None:
        try:
            flags = os.O_RDONLY | os.O_CLOEXEC
            if path.parent != Path("/proc/self/fd") or not path.name.isdigit():
                flags |= os.O_NOFOLLOW
            self.descriptor = os.open(path, flags)
        except OSError:
            raise VerificationError("declared executable is unavailable") from None
        self.maximum = maximum
        try:
            self.identity = self._identity()
        except BaseException:
            os.close(self.descriptor)
            raise

    def _identity(self) -> tuple[int, int, int, int]:
        metadata = os.fstat(self.descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size < 0 or metadata.st_size > self.maximum:
            raise VerificationError("declared executable has an invalid type or size")
        return metadata.st_dev, metadata.st_ino, metadata.st_mode, metadata.st_size

    def sha256(self) -> str:
        hasher = hashlib.sha256()
        offset = 0
        while offset < self.identity[3]:
            chunk = os.pread(self.descriptor, min(1_048_576, self.identity[3] - offset), offset)
            if not chunk:
                raise VerificationError("declared executable changed while reading")
            hasher.update(chunk)
            offset += len(chunk)
        return hasher.hexdigest()

    def process_path(self) -> Path:
        path = Path(f"/proc/self/fd/{self.descriptor}")
        if not path.exists():
            raise VerificationError("retained Git execution is unavailable")
        return path

    def verify_unchanged(self, expected: str) -> None:
        if self._identity() != self.identity or self.sha256() != expected:
            raise VerificationError("Git executable changed during source observation")

    def close(self) -> None:
        os.close(self.descriptor)


def process_group_exists(group: int) -> bool:
    try:
        os.killpg(group, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def zombie_without_live_task(status_lines: list[str]) -> bool:
    """Report whether `/proc/PID/status` text describes a fully terminated entry.

    A `State: Z` thread-group leader whose group still holds another task is a
    live process: its leader thread exited, but a worker thread keeps running
    under the zombie leader and can still act. Only `Threads: 1` proves that no
    task in the group can execute again. A missing or malformed
    `State:`/`Threads:` line fails closed and reports the entry as live.
    """
    try:
        state = next(line for line in status_lines if line.startswith("State:")).split()[1]
        tasks = int(next(line for line in status_lines if line.startswith("Threads:")).split()[1])
    except (IndexError, StopIteration, ValueError):
        return False
    return state == "Z" and tasks == 1


def descendant_process_ids(root_pids: set[int]) -> set[int]:
    """Return the live descendants of `root_pids` from the /proc parent links.

    An entry is omitted only when it has fully terminated: `State: Z` with
    `Threads: 1`, a zombie thread-group leader whose group holds no other task.
    It keeps a process-table slot until someone waits for it and can never
    execute again, so it cannot escape containment. Under
    `PR_SET_CHILD_SUBREAPER` an adopted orphan that has already exited becomes a
    permanent zombie child of this process, and counting it would report a
    containment failure for a process that no longer runs. A zombie leader whose
    group still holds a live worker thread is a running process and is reported.
    Terminated entries are still traversed, so a live entry parented to one is
    still reported.

    The two parse failures are deliberately asymmetric. An entry that exits
    between the directory scan and the status read, or whose `PPid:` line is
    absent or malformed, is dropped by the shared `OSError`/`IndexError` path
    exactly as a vanished process is. That arm fails open for a single
    unparseable entry, a tradeoff consciously accepted for parse robustness
    because without a parent link the entry cannot be placed in the tree at all.
    A missing or malformed `State:`/`Threads:` line instead fails closed and
    reports the entry, because its parent link is already known and only the
    justification for skipping it is missing.
    """
    parents: dict[int, list[int]] = {}
    terminated: set[int] = set()
    for status_path in Path("/proc").glob("[0-9]*/status"):
        try:
            pid = int(status_path.parent.name)
            status_lines = status_path.read_text().splitlines()
            parent_line = next(line for line in status_lines if line.startswith("PPid:"))
            parent = int(parent_line.split()[1])
        except (IndexError, OSError, StopIteration, ValueError):
            continue
        if zombie_without_live_task(status_lines):
            terminated.add(pid)
        parents.setdefault(parent, []).append(pid)
    descendants: set[int] = set()
    visited: set[int] = set()
    pending = list(root_pids)
    while pending:
        parent = pending.pop()
        for child in parents.get(parent, []):
            if child not in visited:
                visited.add(child)
                pending.append(child)
                if child not in terminated:
                    descendants.add(child)
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


def require_text(value: Any, label: str, *, maximum: int = 4096, empty: bool = False) -> str:
    if not isinstance(value, str) or (not empty and not value) or "\x00" in value:
        raise VerificationError(f"{label} is not bounded text")
    if len(value.encode("utf-8", "strict")) > maximum:
        raise VerificationError(f"{label} exceeds its bound")
    return value


def require_absolute(value: Any, label: str) -> Path:
    text = require_text(value, label)
    path = Path(text)
    if not path.is_absolute():
        raise VerificationError(f"{label} is not absolute")
    return path


def full_revision(value: Any) -> bool:
    return isinstance(value, str) and (HEX40.fullmatch(value) is not None or HEX64.fullmatch(value) is not None)


def validate_request(value: dict[str, Any]) -> None:
    fields = tuple(value)
    option_fields_valid = (
        fields == REQUEST_FIELDS
        and (
            value.get("corpus_source_kind") == "FILE_SET"
            or value.get("corpus_file_set_manifest_path") is None
        )
    ) or (
        fields == REQUEST_FIELDS_OMITTED
        and value.get("corpus_source_kind") != "FILE_SET"
    )
    if not option_fields_valid:
        raise VerificationError("source verifier request has the wrong fields or order")
    if value["schema_version"] != 1 or value["artifact_kind"] != "PROMPT_SOURCE_VERIFIER_REQUEST":
        raise VerificationError("source verifier request header is invalid")
    if value["mode"] not in ("EVALUATION", "GATE"):
        raise VerificationError("source verifier mode is invalid")
    if value["mode"] == "EVALUATION" and value["tested_align_llm_head"] is not None:
        raise VerificationError("evaluation mode has a tested head")
    if value["mode"] == "GATE" and not isinstance(value["tested_align_llm_head"], str):
        raise VerificationError("gate mode is missing its tested head")
    for name in ("expected_align_llm_commit", "expected_align_revision"):
        if not full_revision(value[name]):
            raise VerificationError(f"{name} is not a full lowercase commit")
    if value["tested_align_llm_head"] is not None and not full_revision(value["tested_align_llm_head"]):
        raise VerificationError("tested align-llm head is invalid")
    for name in (
        "align_llm_repository_path",
        "align_repository_path",
        "corpus_source_path",
        "git_executable_path",
    ):
        require_absolute(value[name], name)
    if value["corpus_source_kind"] == "GIT_COMMIT":
        if value.get("corpus_file_set_manifest_path") is not None:
            raise VerificationError("Git corpus has a file-set manifest")
        require_text(value["expected_corpus_source_repository_id"], "corpus repository id", maximum=256)
        if not full_revision(value["expected_corpus_source_sha256"]):
            raise VerificationError("Git corpus identity is not a full commit")
    elif value["corpus_source_kind"] == "FILE_SET":
        if not isinstance(value.get("corpus_file_set_manifest_path"), str):
            raise VerificationError("file-set corpus is missing its manifest")
        require_absolute(value["corpus_file_set_manifest_path"], "corpus manifest path")
        if value["expected_corpus_source_repository_id"] != "":
            raise VerificationError("file-set corpus has a repository id")
        if not isinstance(value["expected_corpus_source_sha256"], str) or not HEX64.fullmatch(value["expected_corpus_source_sha256"]):
            raise VerificationError("file-set corpus identity is not SHA-256")
    else:
        raise VerificationError("corpus source kind is invalid")
    if not isinstance(value["git_executable_sha256"], str) or not HEX64.fullmatch(value["git_executable_sha256"]):
        raise VerificationError("Git executable digest is invalid")
    claimed = value["content_sha256"]
    if not isinstance(claimed, str) or not HEX64.fullmatch(claimed):
        raise VerificationError("source verifier request digest is invalid")
    normalized = dict(value)
    normalized["content_sha256"] = ""
    if hashlib.sha256(canonical_digest_bytes(normalized)).hexdigest() != claimed:
        raise VerificationError("source verifier request digest does not match")


def physical_directory(path: Path) -> Path:
    absolute = path
    current = Path("/")
    for component in absolute.parts[1:]:
        current = current / component
        try:
            metadata = os.lstat(current)
        except OSError as error:
            raise VerificationError("source directory is unavailable") from None
        if stat.S_ISLNK(metadata.st_mode):
            raise VerificationError("source directory has a symlink component")
    if not stat.S_ISDIR(os.stat(absolute, follow_symlinks=False).st_mode):
        raise VerificationError("source path is not a directory")
    return absolute.resolve(strict=True)


def read_metadata_file(path: Path, maximum: int) -> bytes:
    return read_bounded(path, maximum)


def resolve_git_metadata(repository: Path) -> tuple[Path, Path]:
    root = physical_directory(repository)
    dotgit = root / ".git"
    try:
        metadata = os.lstat(dotgit)
    except OSError as error:
        raise VerificationError("Git metadata is unavailable") from None
    if stat.S_ISDIR(metadata.st_mode):
        git_dir = dotgit.resolve(strict=True)
    elif stat.S_ISREG(metadata.st_mode):
        raw = read_metadata_file(dotgit, 4096)
        if not raw.startswith(b"gitdir: ") or not raw.endswith(b"\n") or raw.count(b"\n") != 1:
            raise VerificationError("gitdir pointer is malformed")
        try:
            pointer = os.fsdecode(raw[8:-1])
        except UnicodeError as error:
            raise VerificationError("gitdir pointer is not decodable") from None
        candidate = Path(pointer)
        if not candidate.is_absolute():
            candidate = root / candidate
        git_dir = physical_directory(candidate)
    else:
        raise VerificationError(".git is not a directory or pointer file")
    commondir_path = git_dir / "commondir"
    if commondir_path.exists():
        raw = read_metadata_file(commondir_path, 4096)
        if not raw.endswith(b"\n") or raw.count(b"\n") != 1 or b"\x00" in raw:
            raise VerificationError("commondir pointer is malformed")
        candidate = Path(os.fsdecode(raw[:-1]))
        if not candidate.is_absolute():
            candidate = git_dir / candidate
        common_dir = physical_directory(candidate)
    else:
        common_dir = git_dir
    return git_dir, common_dir


def parse_config(raw: bytes) -> None:
    if len(raw) > 4_194_304 or b"\x00" in raw:
        raise VerificationError("local Git config is malformed or too large")
    section = ""
    for source_line in raw.splitlines():
        line = source_line.strip()
        if not line or line.startswith((b"#", b";")):
            continue
        if line.startswith(b"[") and line.endswith(b"]"):
            try:
                header = line[1:-1].decode("utf-8", "strict").strip().lower()
            except UnicodeError as error:
                raise VerificationError("local Git config section is invalid") from None
            match = re.fullmatch(r'([a-z0-9-]+)(?:\s+"((?:[^"\\]|\\.)*)")?', header)
            if match is None:
                raise VerificationError("local Git config section is malformed")
            section = match.group(1)
            if match.group(2) is not None:
                section += "." + match.group(2).replace('\\"', '"').lower()
            continue
        if not section or b"=" not in line:
            raise VerificationError("local Git config assignment is malformed")
        raw_key, _ = line.split(b"=", 1)
        try:
            key = f"{section}.{raw_key.decode('ascii', 'strict').strip().lower()}"
        except UnicodeError as error:
            raise VerificationError("local Git config key is invalid") from None
        rejected = key in REJECTED_EXACT_KEYS or any(pattern.match(key) for pattern in REJECTED_KEY_PATTERNS)
        allowed = any(pattern.fullmatch(key) for pattern in ALLOWED_LOCAL_KEYS)
        if rejected and not allowed:
            raise VerificationError("local Git config has a command-bearing key")


def fixed_git(git: Path, git_descriptor: int, repository: Path, *arguments: str) -> bytes:
    if not CHILD_SUBREAPER_ENABLED:
        raise VerificationCleanupError("fixed Git process containment is unavailable")
    command = [
        str(git),
        "--no-pager",
        "-C",
        str(repository),
        "-c",
        "core.useReplaceRefs=false",
        "-c",
        "core.alternateRefsCommand=",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "credential.helper=",
        "-c",
        "diff.external=",
        *arguments,
    ]
    environment = {
        "LANG": "C",
        "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_PAGER": "cat",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_GRAFT_FILE": "/dev/null",
        "GIT_NO_LAZY_FETCH": "1",
    }
    try:
        process = subprocess.Popen(
            command,
            cwd=repository,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            start_new_session=True,
            pass_fds=(git_descriptor,),
        )
    except OSError:
        raise VerificationError("fixed Git command is unavailable") from None
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
                raise VerificationError("fixed Git command timed out")
            events = selector.select(remaining)
            if not events:
                raise VerificationError("fixed Git command timed out")
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
                    raise VerificationError("fixed Git command exceeded its output cap")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise VerificationError("fixed Git command timed out")
        process.wait(timeout=remaining)
        if process_group_exists(process.pid) or owned_descendant_ids(process):
            cleanup_attempted = True
            if not cleanup_process_group(process):
                raise VerificationCleanupError("fixed Git command cleanup failed")
            raise VerificationError("fixed Git command left a descendant")
    except (OSError, subprocess.TimeoutExpired, VerificationError) as failure:
        if not cleanup_attempted:
            cleanup_attempted = True
            if not cleanup_process_group(process):
                raise VerificationCleanupError("fixed Git command cleanup failed") from None
        if isinstance(failure, VerificationCleanupError):
            raise failure
        raise VerificationError("fixed Git command failed or exceeded its boundary") from None
    finally:
        selector.close()
        if process.stdout is not None and not process.stdout.closed:
            process.stdout.close()
    if process.returncode != 0:
        raise VerificationError("fixed Git command failed or exceeded its output cap")
    return bytes(output)


def reject_git_extensions(common_dir: Path, git_dir: Path, git: Path, git_descriptor: int, repository: Path) -> None:
    for config in (common_dir / "config", git_dir / "config.worktree"):
        if config.exists() or config.is_symlink():
            parse_config(read_metadata_file(config, 4_194_304))
    for candidate in (
        common_dir / "refs" / "replace",
        common_dir / "info" / "grafts",
        common_dir / "objects" / "info" / "alternates",
    ):
        if candidate.exists() or candidate.is_symlink():
            raise VerificationError("Git replacement, graft, or alternate metadata is present")
    replacement = fixed_git(git, git_descriptor, repository, "for-each-ref", "--format=%(refname)%00", "refs/replace/")
    if replacement:
        raise VerificationError("Git replacement namespace is non-empty")


def observe_git(repository: Path, expected: str, git: Path, git_descriptor: int) -> tuple[str, bool]:
    git_dir, common_dir = resolve_git_metadata(repository)
    reject_git_extensions(common_dir, git_dir, git, git_descriptor, repository)
    observed_raw = fixed_git(git, git_descriptor, repository, "rev-parse", "--verify", "HEAD")
    try:
        observed = observed_raw.decode("ascii", "strict").strip()
    except UnicodeError as error:
        raise VerificationError("Git HEAD is not ASCII") from None
    if not full_revision(observed):
        raise VerificationError("Git HEAD is not a full lowercase commit")
    status = fixed_git(git, git_descriptor, repository, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    return observed, observed == expected and status == b""


def read_manifest(path: Path) -> tuple[bytes, os.stat_result, int]:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    except OSError:
        raise VerificationError("file-set manifest is unavailable") from None
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size < 0 or metadata.st_size > MANIFEST_LIMIT:
            raise VerificationError("file-set manifest has an invalid type or size")
        raw = bytearray()
        while len(raw) <= MANIFEST_LIMIT:
            chunk = os.read(descriptor, min(65_536, MANIFEST_LIMIT + 1 - len(raw)))
            if not chunk:
                break
            raw.extend(chunk)
        if len(raw) > MANIFEST_LIMIT:
            raise VerificationError("file-set manifest exceeds its limit")
        return bytes(raw), metadata, descriptor
    except BaseException:
        os.close(descriptor)
        raise


def parse_file_set_manifest(raw: bytes, root: Path, manifest_metadata: os.stat_result) -> None:
    prefix = b"ALIGN-LLM-CORPUS-FILE-SET-V1\n"
    if not raw.startswith(prefix):
        raise VerificationError("file-set manifest header is invalid")
    cursor = len(prefix)
    newline = raw.find(b"\n", cursor)
    count_raw = raw[cursor:newline]
    if newline < 0 or len(count_raw) > 7 or not DECIMAL.fullmatch(count_raw):
        raise VerificationError("file-set entry count is invalid")
    count = int(count_raw)
    if count < 1 or count > 1_048_576:
        raise VerificationError("file-set entry count is out of range")
    cursor = newline + 1
    prior: bytes | None = None
    resolved_root = physical_directory(root)
    try:
        root_descriptor = os.open(
            resolved_root, os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW
        )
    except OSError:
        raise VerificationError("file-set root is unavailable") from None
    try:
      for _ in range(count):
        mode_end = raw.find(b" ", cursor)
        count_end = raw.find(b" ", mode_end + 1)
        path_count_raw = raw[mode_end + 1:count_end]
        if (
            mode_end < 0
            or count_end < 0
            or not MODE.fullmatch(raw[cursor:mode_end])
            or len(path_count_raw) > 4
            or not DECIMAL.fullmatch(path_count_raw)
        ):
            raise VerificationError("file-set entry prefix is malformed")
        mode = int(raw[cursor:mode_end], 8)
        path_count = int(path_count_raw)
        if path_count < 1 or path_count > 4096:
            raise VerificationError("file-set path length is out of range")
        path_start = count_end + 1
        path_end = path_start + path_count
        # NUL + "F " + 64-byte digest + newline.
        suffix_end = path_end + 68
        if suffix_end > len(raw) or raw[path_end:path_end + 3] != b"\x00F " or raw[suffix_end - 1:suffix_end] != b"\n":
            raise VerificationError("file-set entry suffix is malformed")
        relative = raw[path_start:path_end]
        digest = raw[path_end + 3:suffix_end - 1]
        if len(digest) != 64 or any(byte not in b"0123456789abcdef" for byte in digest):
            raise VerificationError("file-set entry digest is invalid")
        components = relative.split(b"/")
        if relative.startswith(b"/") or any(
            not part or b"\0" in part or part in (b".", b"..") for part in components
        ):
            raise VerificationError("file-set path is invalid")
        if prior is not None and relative <= prior:
            raise VerificationError("file-set paths are not strictly sorted")
        prior = relative
        parent_descriptor = os.dup(root_descriptor)
        try:
            for component in components[:-1]:
                next_descriptor = os.open(
                    component,
                    os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=parent_descriptor,
                )
                os.close(parent_descriptor)
                parent_descriptor = next_descriptor
            descriptor = os.open(
                components[-1],
                os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK,
                dir_fd=parent_descriptor,
            )
        except OSError as error:
            raise VerificationError("file-set entry is unavailable") from None
        finally:
            os.close(parent_descriptor)
        try:
            metadata = os.fstat(descriptor)
            observed_mode = stat.S_IFMT(metadata.st_mode) | stat.S_IMODE(metadata.st_mode)
            if not stat.S_ISREG(metadata.st_mode) or observed_mode != mode:
                raise VerificationError("file-set entry type or mode disagrees")
            if metadata.st_dev == manifest_metadata.st_dev and metadata.st_ino == manifest_metadata.st_ino:
                raise VerificationError("file-set manifest lists itself")
            hasher = hashlib.sha256()
            while True:
                chunk = os.read(descriptor, 1_048_576)
                if not chunk:
                    break
                hasher.update(chunk)
            post_metadata = os.fstat(descriptor)
            identity = (metadata.st_dev, metadata.st_ino, metadata.st_mode, metadata.st_size, metadata.st_mtime_ns)
            post_identity = (
                post_metadata.st_dev, post_metadata.st_ino, post_metadata.st_mode,
                post_metadata.st_size, post_metadata.st_mtime_ns,
            )
            if post_identity != identity or hasher.hexdigest().encode("ascii") != digest:
                raise VerificationError("file-set entry digest disagrees")
        finally:
            os.close(descriptor)
        cursor = suffix_end
    finally:
        os.close(root_descriptor)
    if cursor != len(raw):
        raise VerificationError("file-set manifest has trailing bytes")


def complete_result(
    *,
    align_llm: tuple[str | None, bool],
    align: tuple[str | None, bool],
    corpus: tuple[str | None, bool],
) -> dict[str, Any]:
    value: dict[str, Any] = dict.fromkeys(RESULT_FIELDS)
    value.update(
        {
            "schema_version": 1,
            "artifact_kind": "PROMPT_SOURCE_VERIFIER_RESULT",
            "status": "COMPLETE",
            "error_code": "NONE",
            "error": "",
            "align_llm_reachability": "VERIFIED" if align_llm[1] else "UNVERIFIED",
            "align_llm_observed_head": align_llm[0],
            "align_reachability": "VERIFIED" if align[1] else "UNVERIFIED",
            "align_observed_revision": align[0],
            "corpus_reachability": "VERIFIED" if corpus[1] else "UNVERIFIED",
            "corpus_observed_source_sha256": corpus[0],
            "content_sha256": "",
        }
    )
    bind_digest(value)
    return value


def unavailable_result(code: str, message: str) -> dict[str, Any]:
    value: dict[str, Any] = dict.fromkeys(RESULT_FIELDS)
    value.update(
        {
            "schema_version": 1,
            "artifact_kind": "PROMPT_SOURCE_VERIFIER_RESULT",
            "status": "UNAVAILABLE",
            "error_code": code,
            "error": message[:4096],
            "align_llm_reachability": "UNVERIFIED",
            "align_llm_observed_head": None,
            "align_reachability": "UNVERIFIED",
            "align_observed_revision": None,
            "corpus_reachability": "UNVERIFIED",
            "corpus_observed_source_sha256": None,
            "content_sha256": "",
        }
    )
    bind_digest(value)
    return value


def optional_git_observation(
    repository: Path, expected: str, git: Path, git_descriptor: int
) -> tuple[str | None, bool]:
    try:
        observed, verified = observe_git(repository, expected, git, git_descriptor)
        return observed, verified
    except VerificationCleanupError:
        raise
    except VerificationError:
        return None, False


def evaluate(request: dict[str, Any]) -> dict[str, Any]:
    git_path = require_absolute(request["git_executable_path"], "Git executable path")
    git_owner = RetainedExecutable(git_path)
    try:
        expected_git = request["git_executable_sha256"]
        if git_owner.sha256() != expected_git:
            raise VerificationError("Git executable digest does not match")
        git = git_owner.process_path()
        git_descriptor = git_owner.descriptor
        expected_llm = request["expected_align_llm_commit"] if request["mode"] == "EVALUATION" else request["tested_align_llm_head"]
        align_llm = optional_git_observation(Path(request["align_llm_repository_path"]), expected_llm, git, git_descriptor)
        if request["mode"] == "GATE" and align_llm[0] is not None and align_llm[1]:
            try:
                fixed_git(
                    git,
                    git_descriptor,
                    Path(request["align_llm_repository_path"]),
                    "merge-base",
                    "--is-ancestor",
                    request["expected_align_llm_commit"],
                    request["tested_align_llm_head"],
                )
            except VerificationError:
                align_llm = (align_llm[0], False)
        align = optional_git_observation(
            Path(request["align_repository_path"]), request["expected_align_revision"], git, git_descriptor
        )
        if request["corpus_source_kind"] == "GIT_COMMIT":
            corpus = optional_git_observation(
                Path(request["corpus_source_path"]), request["expected_corpus_source_sha256"], git, git_descriptor
            )
        else:
            manifest = Path(request["corpus_file_set_manifest_path"])
            manifest_descriptor = -1
            try:
                raw, manifest_metadata, manifest_descriptor = read_manifest(manifest)
                observed = hashlib.sha256(raw).hexdigest()
                parse_file_set_manifest(raw, Path(request["corpus_source_path"]), manifest_metadata)
                post_metadata = os.fstat(manifest_descriptor)
                post_identity = (
                    post_metadata.st_dev, post_metadata.st_ino, post_metadata.st_mode,
                    post_metadata.st_size, post_metadata.st_mtime_ns,
                )
                initial_identity = (
                    manifest_metadata.st_dev, manifest_metadata.st_ino, manifest_metadata.st_mode,
                    manifest_metadata.st_size, manifest_metadata.st_mtime_ns,
                )
                post_hasher = hashlib.sha256()
                offset = 0
                while offset < post_metadata.st_size:
                    chunk = os.pread(
                        manifest_descriptor, min(1_048_576, post_metadata.st_size - offset), offset
                    )
                    if not chunk:
                        raise VerificationError("file-set manifest changed while reading")
                    post_hasher.update(chunk)
                    offset += len(chunk)
                if post_identity != initial_identity or post_hasher.hexdigest() != observed:
                    raise VerificationError("file-set manifest changed during observation")
                corpus = (observed, observed == request["expected_corpus_source_sha256"])
            except (OSError, VerificationError):
                corpus = (None, False)
            finally:
                if manifest_descriptor >= 0:
                    os.close(manifest_descriptor)
        git_owner.verify_unchanged(expected_git)
        return complete_result(align_llm=align_llm, align=align, corpus=corpus)
    finally:
        git_owner.close()


def write_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    raw = canonical_bytes(value)
    if len(raw) > RESULT_LIMIT:
        raise VerificationError("source verifier result exceeds its bound")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
    try:
        offset = 0
        while offset < len(raw):
            offset += os.write(descriptor, raw[offset:])
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def parse_arguments(arguments: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-verifier-request", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    values = parse_arguments(sys.argv[1:] if arguments is None else arguments)
    try:
        request = json_object(read_bounded(values.source_verifier_request, REQUEST_LIMIT), "source verifier request")
        validate_request(request)
        try:
            result = evaluate(request)
        except VerificationCleanupError:
            return 3
        except VerificationError as error:
            result = unavailable_result("GIT_UNAVAILABLE", str(error))
        write_exclusive(values.result, result)
        return 0
    except (OSError, VerificationError) as error:
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
