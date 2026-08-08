#!/usr/bin/env python3
"""Request 6 ordinary-adoption dispatcher.

The native image supervisor is the authenticated parent of this module.  This
module is deliberately data-oriented: it validates the parent and sealed
inputs before opening repository data, snapshots source through retained file
descriptors, creates the signed capsule, and owns the worker's direct child.
The namespace and compiler phases remain explicit owners rather than being
silently folded into the dispatcher.
"""

from __future__ import annotations

import base64
import ctypes
import errno
import fcntl
import hashlib
import os
import posixpath
import resource
import selectors
import signal
import socket
import stat
import subprocess
import time
from collections import OrderedDict
from typing import Any, Mapping, Sequence

from fresh_attestation import (
    IMAGE_KEY_ID,
    ORDINARY_ADOPTION_PREDICATE_TYPE,
    ORDINARY_ADOPTION_REQUEST,
    ORDINARY_WORKER_PATH,
    RUN_KEY_ID,
    WireError,
    canonical_json_bytes,
    canonical_json_value_bytes,
    ed25519_public_key,
    sha256_hex,
    signed_envelope,
    validate_image_predicate,
    validate_ordinary_adoption_predicate,
    verify_envelope,
)
from fresh_image_control import (
    GIT_PATH,
    IMAGE_PUBLIC_KEY_PATH,
    MANIFEST_PATH,
    PYTHON_PATH,
    RUN_PUBLIC_KEY_PATH,
    RUN_SIGNING_SEED_PATH,
    SUPERVISOR_PATH,
    ControlError,
    FileIdentity,
    _canonical_relative_from_absolute,
    _identity,
    _normalize_absolute,
    _read_key,
    _read_sealed,
    _runtime_file_binding,
    _runtime_tree,
    _sealed_memfd,
)
from fresh_manifest import serialized_digest, validate_manifest_bytes


MAX_CAPSULE_BYTES = 1_048_576
MAX_WORKER_BYTES = 4_194_304
MAX_SOURCE_FILE_BYTES = 4_194_304
MAX_PATH_BYTES = 4096
MAX_RAW_ENTRIES = 1_500_000
MAX_RAW_BYTES = 48 * 1024 * 1024 * 1024
MAX_PROC_BYTES = 4096
MAX_STREAM_BYTES = 65_536
ORDINARY_TICKET_BYTES = 32
ORDINARY_NONCE_BYTES = 32
WORKER_TIMEOUT_SECONDS = 5000
REAP_TIMEOUT_SECONDS = 5
PHASE_CODES = {
    "input": 1,
    "toolchain": 2,
    "revision": 3,
    "build": 4,
    "fixture": 5,
    "cleanup": 6,
}
# FD 11 is the sealed Python bundle consumed by the static entrypoint.  It is
# part of the dispatcher process until the worker handoff and is deliberately
# absent from the worker's allowlist.
REQUIRED_DESCRIPTOR_SET = {0, 1, 2, 4, 6, 8, 11, 15, 16, 18}
DISPATCHER_PATH = "/usr/local/libexec/align-llm/request6-adoption-entrypoint"


class AdoptionFailure(Exception):
    """A deterministic ordinary-adoption phase failure."""

    def __init__(self, phase: str, detail: str = "") -> None:
        super().__init__(detail or phase)
        self.phase = phase


def _set_parent_death(parent_pid: int) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0 or os.getppid() != parent_pid:
        os._exit(127)


def _fail(phase: str) -> int:
    if phase == "unobserved":
        os.write(2, b"json-scan adoption: ERROR unobserved\n")
        return 7
    if phase not in PHASE_CODES:
        phase = "toolchain"
    os.write(2, f"json-scan adoption: ERROR {phase}\n".encode("ascii"))
    return PHASE_CODES[phase]


def _descriptor_set() -> set[int]:
    result: set[int] = set()
    directory_fd = os.open("/proc/self/fd", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for name in os.listdir(directory_fd):
            try:
                fd = int(name)
                if fd == directory_fd:
                    continue
                os.fstat(fd)
            except (OSError, ValueError):
                continue
            result.add(fd)
    finally:
        os.close(directory_fd)
    return result


def _strict_arguments(arguments: Sequence[str]) -> tuple[str, str]:
    if len(arguments) != 18:
        raise AdoptionFailure("input")
    fixed = (
        "--mode", "ordinary-adoption", "--project-root-fd", "4",
        "--image-attestation-fd", "6", "--manifest-fd", "8",
        "--align-repo-root-fd", "18", "--align-repo-absolute", None,
        "--align-repo-relative", None, "--invocation-nonce-fd", "15",
        "--supervisor-channel-fd", "16",
    )
    for actual, expected in zip(arguments, fixed):
        if expected is not None and actual != expected:
            raise AdoptionFailure("input")
    absolute = arguments[11]
    relative = arguments[13]
    if not absolute or not relative:
        raise AdoptionFailure("input")
    try:
        normalized = _normalize_absolute(absolute)
    except (ControlError, UnicodeError) as error:
        raise AdoptionFailure("input") from error
    if normalized != absolute:
        raise AdoptionFailure("input")
    if any(component == "" for component in relative.split("/")) or relative.startswith("/"):
        raise AdoptionFailure("input")
    if any(component == "." for component in relative.split("/")):
        raise AdoptionFailure("input")
    return absolute, relative


def _require_environment(absolute: str) -> None:
    expected = {
        "PATH": "/usr/bin:/bin",
        "LC_ALL": "C",
        "LANG": "C",
        "HOME": "/nonexistent",
        "TMPDIR": "/tmp",
        "ALIGN_REPO": absolute,
    }
    if dict(os.environ) != expected:
        raise AdoptionFailure("input")


def _proc_start_time(pid: int) -> str:
    try:
        fd = os.open(f"/proc/{pid}/stat", os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
        try:
            raw = os.read(fd, MAX_PROC_BYTES)
        finally:
            os.close(fd)
    except OSError as error:
        raise AdoptionFailure("input") from error
    closing = raw.rfind(b") ")
    if closing < 0:
        raise AdoptionFailure("input")
    fields = raw[closing + 2 :].split()
    if len(fields) <= 19 or not fields[19].isdigit():
        raise AdoptionFailure("input")
    return fields[19].decode("ascii")


def _proc_cmdline(pid: int) -> bytes:
    try:
        fd = os.open(f"/proc/{pid}/cmdline", os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
        try:
            raw = os.read(fd, MAX_PROC_BYTES)
        finally:
            os.close(fd)
    except OSError as error:
        raise AdoptionFailure("input") from error
    if not raw or len(raw) == MAX_PROC_BYTES:
        raise AdoptionFailure("input")
    return raw


def _read_fd(fd: int, limit: int) -> bytes:
    before = _identity(fd)
    if not stat.S_ISREG(before.mode) or before.size < 0 or before.size > limit:
        raise AdoptionFailure("toolchain")
    os.lseek(fd, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    total = 0
    while total < before.size:
        block = os.read(fd, min(65_536, before.size - total))
        if not block:
            raise AdoptionFailure("toolchain")
        chunks.append(block)
        total += len(block)
    if os.read(fd, 1):
        raise AdoptionFailure("toolchain")
    if _identity(fd) != before:
        raise AdoptionFailure("toolchain")
    os.lseek(fd, 0, os.SEEK_SET)
    return b"".join(chunks)


def _snapshot_memfd(fd: int, name: str, limit: int) -> bytes:
    try:
        seals = fcntl.fcntl(fd, fcntl.F_GET_SEALS)
        link = os.readlink(f"/proc/self/fd/{fd}")
    except OSError as error:
        raise AdoptionFailure("toolchain") from error
    if seals != fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL:
        raise AdoptionFailure("toolchain")
    if link != f"/memfd:{name} (deleted)":
        raise AdoptionFailure("toolchain")
    try:
        raw = _read_sealed(fd, limit=limit, expected_name=name)
    except ControlError as error:
        raise AdoptionFailure("toolchain") from error
    return raw


def _authenticate_parent(channel: socket.socket, image_predicate: Mapping[str, Any]) -> int:
    try:
        credentials = channel.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
    except OSError as error:
        raise AdoptionFailure("input") from error
    if not isinstance(credentials, bytes) or len(credentials) != 12:
        raise AdoptionFailure("input")
    pid = int.from_bytes(credentials[0:4], "little", signed=True)
    uid = int.from_bytes(credentials[4:8], "little", signed=True)
    if pid <= 0 or uid != os.geteuid() or pid != os.getppid():
        raise AdoptionFailure("input")
    start = _proc_start_time(pid)
    command = _proc_cmdline(pid)
    if command != b"fresh-supervise\x00--mode\x00ordinary-adoption\x00":
        raise AdoptionFailure("input")
    try:
        executable = os.open(f"/proc/{pid}/exe", os.O_RDONLY | os.O_CLOEXEC)
    except OSError as error:
        raise AdoptionFailure("input") from error
    try:
        before = _identity(executable)
        raw = _read_fd(executable, 16 * 1024 * 1024)
        after = _identity(executable)
    finally:
        os.close(executable)
    if before != after or sha256_hex(raw) != image_predicate.get("supervisor_sha256"):
        raise AdoptionFailure("input")
    if _proc_start_time(pid) != start or os.getppid() != pid:
        raise AdoptionFailure("input")
    return pid


def _receive_packet(channel: socket.socket, expected: int) -> bytes:
    try:
        data, _, flags, _ = channel.recvmsg(expected + 1, 0)
    except OSError as error:
        raise AdoptionFailure("toolchain") from error
    if flags & socket.MSG_TRUNC or len(data) != expected:
        raise AdoptionFailure("toolchain")
    return data


def _identity_changed(fd: int, before: FileIdentity) -> None:
    try:
        after = _identity(fd)
    except OSError as error:
        raise AdoptionFailure("revision") from error
    if after != before:
        raise AdoptionFailure("revision")


def _walk_directory(root_fd: int, relative: str) -> int:
    encoded = os.fsencode(relative)
    if not encoded or encoded.startswith(b"/") or len(encoded) > MAX_PATH_BYTES:
        raise AdoptionFailure("revision")
    current = os.dup(root_fd)
    try:
        for component in encoded.split(b"/"):
            if component in (b"", b".", b"..") or b"\x00" in component:
                raise AdoptionFailure("revision")
            next_fd = os.open(
                component,
                os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=current,
            )
            os.close(current)
            current = next_fd
        return current
    except OSError as error:
        os.close(current)
        raise AdoptionFailure("revision") from error


def _read_regular_at(root_fd: int, relative: str, *, mode: int | None = None) -> bytes:
    parts = os.fsencode(relative).split(b"/")
    if not parts or any(part in (b"", b".", b"..") for part in parts):
        raise AdoptionFailure("revision")
    parents: list[int] = []
    current = os.dup(root_fd)
    parents.append(current)
    try:
        for component in parts[:-1]:
            current = os.open(
                component,
                os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=current,
            )
            parents.append(current)
        fd = os.open(
            parts[-1], os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=current,
        )
        try:
            value = _identity(fd)
            if not stat.S_ISREG(value.mode) or value.links != 1 or value.owner != os.geteuid():
                raise AdoptionFailure("revision")
            if mode is not None and stat.S_IMODE(value.mode) != mode:
                raise AdoptionFailure("revision")
            raw = _read_fd(fd, MAX_SOURCE_FILE_BYTES)
            if mode is not None and len(raw) > MAX_SOURCE_FILE_BYTES:
                raise AdoptionFailure("revision")
            return raw
        finally:
            os.close(fd)
    except OSError as error:
        raise AdoptionFailure("revision") from error
    finally:
        for fd in reversed(parents):
            try:
                os.close(fd)
            except OSError:
                pass


def _read_relative_regular(root_fd: int, relative: str, *, mode: int | None = None) -> bytes:
    """Read one regular file through a descriptor-relative no-follow walk."""

    return _read_regular_at(root_fd, relative, mode=mode)


def _open_absolute_regular(path: str) -> int:
    """Open an absolute regular path through an O_NOFOLLOW component walk."""

    try:
        normalized = _normalize_absolute(path)
    except (ControlError, UnicodeError) as error:
        raise AdoptionFailure("revision") from error
    current = os.open("/", os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    retained = [current]
    parts = os.fsencode(normalized).split(b"/")[1:]
    if not parts or any(part in (b"", b".", b"..") for part in parts):
        os.close(current)
        raise AdoptionFailure("revision")
    try:
        for part in parts[:-1]:
            current = os.open(
                part,
                os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=current,
            )
            retained.append(current)
        descriptor = os.open(
            parts[-1],
            os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=current,
        )
        value = _identity(descriptor)
        if not stat.S_ISREG(value.mode) or value.links != 1 or value.owner != os.geteuid():
            os.close(descriptor)
            raise AdoptionFailure("revision")
        return descriptor
    except OSError as error:
        raise AdoptionFailure("revision") from error
    finally:
        for descriptor in reversed(retained):
            try:
                os.close(descriptor)
            except OSError:
                pass


def _git_index(root_fd: int) -> bytes:
    """Snapshot Git's resolved index, including linked-worktree layouts."""

    resolved = _git_value(root_fd, "rev-parse", "--git-path", "index")
    if resolved.startswith("/"):
        descriptor = _open_absolute_regular(resolved)
        try:
            return _read_fd(descriptor, MAX_SOURCE_FILE_BYTES)
        finally:
            os.close(descriptor)
    return _read_relative_regular(root_fd, resolved)


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _symlink_stays_inside(path: tuple[bytes, ...], target: bytes) -> bool:
    if target.startswith(b"/"):
        return False
    components = list(path[:-1])
    for component in target.split(b"/"):
        if component in (b"", b"."):
            continue
        if component == b"..":
            if not components:
                return False
            components.pop()
        else:
            components.append(component)
    return True


def _raw_tree(root_fd: int, source: str) -> bytes:
    root = _identity(root_fd)
    entries: list[OrderedDict[str, object]] = []
    total_bytes = 0

    def append(path: bytes, kind: str, mode: int, size: int, raw: bytes, target: bytes = b"") -> None:
        nonlocal total_bytes
        if len(entries) >= MAX_RAW_ENTRIES or total_bytes + len(raw) > MAX_RAW_BYTES:
            raise AdoptionFailure("revision")
        total_bytes += len(raw)
        entries.append(
            OrderedDict(
                [
                    ("path_b64", _b64(path)),
                    ("kind", kind),
                    ("mode", f"{stat.S_IMODE(mode):04o}"),
                    ("size", size),
                    ("sha256", sha256_hex(raw)),
                    ("target_b64", _b64(target)),
                ]
            )
        )

    append(b"", "dir", root.mode, 0, b"")

    def visit(parent: int, prefix: tuple[bytes, ...]) -> None:
        try:
            names = sorted(os.fsencode(name) for name in os.listdir(parent))
        except OSError as error:
            raise AdoptionFailure("revision") from error
        for name in names:
            if not prefix and name in (b".git", b"HANDOFF.md", b"target", b"main"):
                continue
            if name in (b"", b".", b"..") or b"\x00" in name:
                raise AdoptionFailure("revision")
            path = (*prefix, name)
            path_raw = b"/".join(path)
            if len(path_raw) > MAX_PATH_BYTES:
                raise AdoptionFailure("revision")
            try:
                value = os.stat(name, dir_fd=parent, follow_symlinks=False)
            except OSError as error:
                raise AdoptionFailure("revision") from error
            if stat.S_ISDIR(value.st_mode):
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent)
                try:
                    before = _identity(child)
                    if (before.device, before.inode, before.mode, before.owner) != (
                        value.st_dev, value.st_ino, value.st_mode, value.st_uid
                    ):
                        raise AdoptionFailure("revision")
                    append(path_raw, "dir", value.st_mode, 0, b"")
                    visit(child, path)
                    _identity_changed(child, before)
                finally:
                    os.close(child)
            elif stat.S_ISREG(value.st_mode):
                if value.st_nlink != 1 or value.st_uid != os.geteuid():
                    raise AdoptionFailure("revision")
                fd = os.open(name, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent)
                try:
                    before = _identity(fd)
                    raw = _read_fd(fd, MAX_SOURCE_FILE_BYTES)
                    if before != _identity(fd) or before.size != len(raw):
                        raise AdoptionFailure("revision")
                    append(path_raw, "file", value.st_mode, len(raw), raw)
                finally:
                    os.close(fd)
            elif stat.S_ISLNK(value.st_mode):
                try:
                    target = os.fsencode(os.readlink(name, dir_fd=parent))
                except OSError as error:
                    raise AdoptionFailure("revision") from error
                if (
                    not target
                    or len(target) > MAX_PATH_BYTES
                    or target.startswith(b"/")
                    or b"\x00" in target
                    or not _symlink_stays_inside(path, target)
                ):
                    raise AdoptionFailure("revision")
                append(path_raw, "symlink", value.st_mode, len(target), target, target)
            else:
                raise AdoptionFailure("revision")

    scan = os.open(
        ".",
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
        dir_fd=root_fd,
    )
    try:
        visit(scan, ())
    finally:
        os.close(scan)
    document = OrderedDict([("schema", "raw-tree/v1"), ("source", source), ("entries", entries)])
    return canonical_json_bytes(document)


def _exception_row(root_fd: int, source: str, label: str, allow_main: bool) -> OrderedDict[str, object]:
    path = {"git": ".git", "handoff": "HANDOFF.md", "target": "target", "main": "main"}[label]
    parent = os.dup(root_fd)
    descriptor = -1
    try:
        parts = os.fsencode(path).split(b"/")
        try:
            flags = os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC
            if label == "handoff":
                flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC
            descriptor = os.open(parts[-1], flags, dir_fd=parent)
        except FileNotFoundError:
            if label == "git" or label == "handoff":
                raise AdoptionFailure("revision")
            return OrderedDict((key, value) for key, value in (
                ("source", source), ("label", label), ("present", False), ("type", None),
                ("mode", None), ("link_count", None), ("bytes_consumed", False), ("content_sha256", None)
            ))
        value = os.fstat(descriptor)
        mode = f"{stat.S_IMODE(value.st_mode):04o}"
        if label == "git":
            if not (stat.S_ISDIR(value.st_mode) or stat.S_ISREG(value.st_mode)):
                raise AdoptionFailure("revision")
            kind = "directory" if stat.S_ISDIR(value.st_mode) else "regular"
            return OrderedDict((("source", source), ("label", label), ("present", True), ("type", kind),
                                ("mode", mode), ("link_count", None), ("bytes_consumed", False),
                                ("content_sha256", None)))
        if label == "target":
            if not stat.S_ISDIR(value.st_mode) or value.st_mode & 0o7000 or value.st_mode & 0o022 or value.st_mode & 0o700 != 0o700:
                raise AdoptionFailure("revision")
            return OrderedDict((("source", source), ("label", label), ("present", True), ("type", "directory"),
                                ("mode", mode), ("link_count", value.st_nlink), ("bytes_consumed", False),
                                ("content_sha256", None)))
        if label == "main" and not allow_main:
            raise AdoptionFailure("revision")
        if not stat.S_ISREG(value.st_mode) or value.st_nlink != 1 or mode not in ("0644", "0755"):
            raise AdoptionFailure("revision")
        if label == "handoff":
            raw = _read_fd(descriptor, MAX_SOURCE_FILE_BYTES)
            consumed = True
            digest = sha256_hex(raw)
        else:
            consumed = False
            digest = None
        return OrderedDict((("source", source), ("label", label), ("present", True), ("type", "regular"),
                            ("mode", mode), ("link_count", 1), ("bytes_consumed", consumed),
                            ("content_sha256", digest)))
    except OSError as error:
        raise AdoptionFailure("revision") from error
    finally:
        os.close(parent)
        if descriptor >= 0:
            os.close(descriptor)


def _source_exceptions(project_fd: int, align_fd: int) -> bytes:
    rows: list[OrderedDict[str, object]] = []
    for source, fd, allow_main in (("project-source", project_fd, True), ("align-source", align_fd, False)):
        for label in ("git", "handoff", "target", "main"):
            rows.append(_exception_row(fd, source, label, allow_main))
    return canonical_json_value_bytes(rows)


def _git_value(root_fd: int, *arguments: str) -> str:
    status, raw, error = _run_git(root_fd, arguments)
    if status != 0 or error:
        raise AdoptionFailure("revision")
    try:
        if not raw.endswith(b"\n") or b"\n" in raw[:-1]:
            raise AdoptionFailure("revision")
        value = raw[:-1].decode("ascii")
    except UnicodeDecodeError as decode_error:
        raise AdoptionFailure("revision") from decode_error
    if not value or "\n" in value:
        raise AdoptionFailure("revision")
    return value


def _git_environment() -> dict[str, str]:
    return {
        "PATH": "/runtime/git/bin:/usr/bin:/bin",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_ATTR_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "advice.graftFileDeprecated",
        "GIT_CONFIG_VALUE_0": "false",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_GRAFT_FILE": "/dev/null",
        "GIT_OPTIONAL_LOCKS": "0",
        "LC_ALL": "C",
    }


def _run_git(root_fd: int, arguments: Sequence[str]) -> tuple[int, bytes, bytes]:
    parent_pid = os.getpid()
    try:
        process = subprocess.Popen(
            [GIT_PATH, "-C", f"/proc/self/fd/{root_fd}", *arguments],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=_git_environment(),
            close_fds=True,
            pass_fds=(root_fd,),
            start_new_session=True,
            preexec_fn=lambda: _set_parent_death(parent_pid),
        )
    except OSError as error:
        raise AdoptionFailure("revision") from error
    assert process.stdout is not None and process.stderr is not None
    stdout_fd, stderr_fd = process.stdout.fileno(), process.stderr.fileno()
    streams = (process.stdout, process.stderr)
    selector = selectors.DefaultSelector()
    captures = {stdout_fd: bytearray(), stderr_fd: bytearray()}
    for stream in streams:
        os.set_blocking(stream.fileno(), False)
        selector.register(stream, selectors.EVENT_READ)
    deadline = time.monotonic() + 5

    def terminate() -> None:
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except OSError as error:
                raise AdoptionFailure("revision") from error
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired as error:
            raise AdoptionFailure("revision") from error

    try:
        while selector.get_map() or process.poll() is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AdoptionFailure("revision")
            if not selector.get_map():
                time.sleep(min(remaining, 0.25))
                continue
            for key, _ in selector.select(min(remaining, 0.25)):
                fd = key.fileobj.fileno()
                try:
                    block = os.read(fd, 8192)
                except BlockingIOError:
                    continue
                except OSError as error:
                    raise AdoptionFailure("revision") from error
                if not block:
                    selector.unregister(key.fileobj)
                    continue
                captures[fd].extend(block)
                limit = MAX_SOURCE_FILE_BYTES if fd == stdout_fd else 65_536
                if len(captures[fd]) > limit:
                    raise AdoptionFailure("revision")
        try:
            status = process.wait(timeout=0)
        except subprocess.TimeoutExpired as error:
            raise AdoptionFailure("revision") from error
    except AdoptionFailure:
        terminate()
        raise
    finally:
        selector.close()
        for stream in streams:
            stream.close()
    return status, bytes(captures[stdout_fd]), bytes(captures[stderr_fd])


def _git_paths(root_fd: int, *arguments: str) -> list[bytes]:
    status, raw, error = _run_git(root_fd, arguments)
    if status != 0 or error or len(raw) > MAX_SOURCE_FILE_BYTES:
        raise AdoptionFailure("revision")
    return [item for item in raw.split(b"\0") if item]


def _require_clean(root_fd: int, *, project: bool) -> None:
    tracked = _git_paths(root_fd, "diff", "--name-only", "-z", "HEAD", "--")
    allowed_tracked = {b"HANDOFF.md"} if project else set()
    if any(path not in allowed_tracked for path in tracked):
        raise AdoptionFailure("revision")
    untracked = _git_paths(root_fd, "ls-files", "--others", "--exclude-standard", "-z", "--")
    if project:
        if any(
            path != b"main" and path != b"target" and not path.startswith(b"target/")
            for path in untracked
        ):
            raise AdoptionFailure("revision")
    elif untracked:
        raise AdoptionFailure("revision")


def _source_identity(project_fd: int, align_fd: int) -> tuple[str, str, str, str, bytes, bytes]:
    project_head = _git_value(project_fd, "rev-parse", "HEAD")
    project_format = _git_value(project_fd, "rev-parse", "--show-object-format")
    align_head = _git_value(align_fd, "rev-parse", "HEAD")
    align_format = _git_value(align_fd, "rev-parse", "--show-object-format")
    if project_format != "sha1" or align_format != "sha1":
        raise AdoptionFailure("revision")
    if not (len(project_head) == 40 and len(align_head) == 40):
        raise AdoptionFailure("revision")
    _require_clean(project_fd, project=True)
    _require_clean(align_fd, project=False)
    project_index = _git_index(project_fd)
    align_index = _git_index(align_fd)
    return project_head, project_format, align_head, align_format, project_index, align_index


def _read_worker(project_fd: int) -> bytes:
    return _read_relative_regular(project_fd, ORDINARY_WORKER_PATH, mode=0o755)


def _verify_image(image_raw: bytes, manifest_raw: bytes, parent_raw: bytes) -> Mapping[str, Any]:
    try:
        key = _read_key(IMAGE_PUBLIC_KEY_PATH, private=False, owner=0)
        verified = verify_envelope(
            image_raw,
            expected_payload_type="https://align-llm.dev/attestations/runner-image/v1",
            expected_key_id=IMAGE_KEY_ID,
            public_key=key,
            predicate_validator=validate_image_predicate,
        )
        predicate = verified.predicate
        validate_manifest_bytes(manifest_raw)
    except (ControlError, WireError, OSError, ValueError) as error:
        raise AdoptionFailure("toolchain") from error
    expected = {
        "manifest_sha256": sha256_hex(manifest_raw),
        "supervisor_path": SUPERVISOR_PATH,
        "supervisor_sha256": sha256_hex(parent_raw),
    }
    for name, value in expected.items():
        if predicate.get(name) != value:
            raise AdoptionFailure("toolchain")
    return predicate


def _capsule(
    *, image_raw: bytes, manifest_raw: bytes, entrypoint_raw: bytes, nonce: bytes,
    ticket: bytes, project_head: str, project_format: str, project_index: bytes,
    project_tree: bytes, exceptions: bytes, align_head: str, align_format: str,
    relative: str, worker: bytes, image_digest: str,
) -> bytes:
    predicate = OrderedDict([
        ("api", "ordinary-adoption/v2"),
        ("request", ORDINARY_ADOPTION_REQUEST),
        ("invocation_nonce", _b64(nonce)),
        ("dispatch_ticket_sha256", sha256_hex(ticket)),
        ("project_head", project_head),
        ("project_object_format", project_format),
        ("project_index_sha256", sha256_hex(project_index)),
        ("project_raw_tree_sha256", sha256_hex(project_tree)),
        ("source_exception_sha256", sha256_hex(exceptions)),
        ("align_head", align_head),
        ("align_object_format", align_format),
        ("align_repo_relative", relative),
        ("worker_relative", ORDINARY_WORKER_PATH),
        ("worker_size", len(worker)),
        ("worker_sha256", sha256_hex(worker)),
        ("image_digest", image_digest),
        ("image_attestation_sha256", sha256_hex(image_raw)),
        ("manifest_sha256", sha256_hex(manifest_raw)),
        ("entrypoint_sha256", sha256_hex(entrypoint_raw)),
    ])
    try:
        validate_ordinary_adoption_predicate(predicate)
        seed = _read_key(RUN_SIGNING_SEED_PATH, private=True, owner=os.geteuid())
        installed_public = _read_key(RUN_PUBLIC_KEY_PATH, private=False, owner=0)
        public = ed25519_public_key(seed)
        if public != installed_public:
            raise AdoptionFailure("toolchain")
        raw = signed_envelope(
            predicate,
            payload_type=ORDINARY_ADOPTION_PREDICATE_TYPE,
            key_id=RUN_KEY_ID,
            seed=seed,
        )
    except (ControlError, WireError, OSError, ValueError) as error:
        raise AdoptionFailure("toolchain") from error
    if len(raw) > MAX_CAPSULE_BYTES or public is None:
        raise AdoptionFailure("toolchain")
    return raw


def _worker_environment() -> dict[str, str]:
    return {
        "PATH": "/usr/bin:/bin",
        "LC_ALL": "C",
        "HOME": "/nonexistent",
        "TMPDIR": "/tmp",
        "PYTHONHOME": "/usr",
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def _launch_worker(worker_fd: int, arguments: Sequence[str]) -> tuple[int, bytes, bytes]:
    parent_pid = os.getpid()
    os.set_inheritable(worker_fd, True)
    child_argv = [
        PYTHON_PATH, "-I", "-B", f"/proc/self/fd/{worker_fd}",
        *arguments,
        "--project-root-fd", "4", "--align-root-fd", "18",
        "--capsule-fd", "12", "--invocation-nonce-fd", "15",
        "--supervisor-channel-fd", "16",
    ]
    try:
        process = subprocess.Popen(
            child_argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=_worker_environment(),
            close_fds=True,
            pass_fds=(4, 12, 13, 15, 16, 18),
            start_new_session=True,
            preexec_fn=lambda: _set_parent_death(parent_pid),
        )
    except OSError as error:
        raise AdoptionFailure("toolchain") from error
    assert process.stdout is not None and process.stderr is not None
    streams = (process.stdout, process.stderr)
    stdout_fd, stderr_fd = (stream.fileno() for stream in streams)
    selector = selectors.DefaultSelector()
    captures = {stdout_fd: bytearray(), stderr_fd: bytearray()}
    for stream in streams:
        os.set_blocking(stream.fileno(), False)
        selector.register(stream, selectors.EVENT_READ)
    deadline = time.monotonic() + WORKER_TIMEOUT_SECONDS

    def terminate() -> None:
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except OSError as error:
                raise AdoptionFailure("unobserved") from error
        try:
            process.wait(timeout=REAP_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired as error:
            try:
                process.kill()
            except OSError:
                pass
            try:
                process.wait(timeout=REAP_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired as reap_error:
                raise AdoptionFailure("unobserved") from reap_error
            raise AdoptionFailure("unobserved") from error

    try:
        while selector.get_map() or process.poll() is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AdoptionFailure("build")
            if not selector.get_map():
                time.sleep(min(remaining, 0.25))
                continue
            for key, _ in selector.select(min(remaining, 0.25)):
                stream = key.fileobj
                fd = stream.fileno()
                try:
                    block = os.read(fd, 8192)
                except BlockingIOError:
                    continue
                except OSError as error:
                    raise AdoptionFailure("build") from error
                if not block:
                    selector.unregister(stream)
                    continue
                captures[fd].extend(block)
                if len(captures[fd]) > MAX_STREAM_BYTES:
                    raise AdoptionFailure("build")
        try:
            status = process.wait(timeout=0)
        except subprocess.TimeoutExpired as error:
            raise AdoptionFailure("build") from error
    except AdoptionFailure:
        terminate()
        raise
    finally:
        selector.close()
        for stream in streams:
            stream.close()

    stdout = bytes(captures[stdout_fd])
    stderr = bytes(captures[stderr_fd])
    if status < 0:
        raise AdoptionFailure("unobserved")
    if status not in range(0, 7):
        raise AdoptionFailure("unobserved")
    if status == 0:
        if stdout != b"json-scan adoption: PASS\n" or stderr:
            raise AdoptionFailure("toolchain")
    else:
        expected = f"json-scan adoption: ERROR {next(name for name, code in PHASE_CODES.items() if code == status)}\n".encode()
        if stdout or stderr != expected:
            raise AdoptionFailure("toolchain")
    return status, stdout, stderr


def dispatch(arguments: Sequence[str]) -> int:
    project_fd = align_fd = image_fd = manifest_fd = nonce_fd = channel_fd = -1
    capsule_fd = worker_fd = -1
    channel: socket.socket | None = None
    try:
        absolute, relative = _strict_arguments(arguments)
        _require_environment(absolute)
        if _descriptor_set() != REQUIRED_DESCRIPTOR_SET:
            raise AdoptionFailure("input")
        project_fd, image_fd, manifest_fd, nonce_fd, channel_fd, align_fd = 4, 6, 8, 15, 16, 18
        channel = socket.socket(fileno=channel_fd)
        image_raw = _snapshot_memfd(image_fd, "align-llm-image-attestation", 262_144)
        manifest_raw = _snapshot_memfd(manifest_fd, "align-llm-fresh-manifest", 67_108_864)
        parent_fd = os.open(f"/proc/{os.getppid()}/exe", os.O_RDONLY | os.O_CLOEXEC)
        try:
            parent_raw = _read_fd(parent_fd, 16 * 1024 * 1024)
        finally:
            os.close(parent_fd)
        predicate = _verify_image(image_raw, manifest_raw, parent_raw)
        _authenticate_parent(channel, predicate)
        ticket = _receive_packet(channel, ORDINARY_TICKET_BYTES)
        nonce = _snapshot_memfd(nonce_fd, "align-llm-ordinary-adoption-nonce", ORDINARY_NONCE_BYTES)
        if len(nonce) != ORDINARY_NONCE_BYTES:
            raise AdoptionFailure("toolchain")
        align_before = _identity(align_fd)
        project_before = _identity(project_fd)
        align_path = os.readlink(f"/proc/self/fd/{align_fd}")
        project_path = os.readlink(f"/proc/self/fd/{project_fd}")
        if (_normalize_absolute(align_path) != absolute or
            posixpath.relpath(_normalize_absolute(align_path), _normalize_absolute(project_path)) != relative or
            _identity(align_fd) != align_before or _identity(project_fd) != project_before):
            raise AdoptionFailure("revision")
        if _normalize_absolute(project_path) == absolute:
            raise AdoptionFailure("revision")
        project_head, project_format, align_head, align_format, project_index, align_index = _source_identity(project_fd, align_fd)
        project_tree = _raw_tree(project_fd, "project-source")
        exceptions = _source_exceptions(project_fd, align_fd)
        worker = _read_worker(project_fd)
        entrypoint_raw = b""  # Native parent binds this digest in the manifest; dispatcher reads it below.
        manifest = validate_manifest_bytes(manifest_raw)
        try:
            entrypoint_fd, entrypoint_raw, _ = _runtime_file_binding(manifest, DISPATCHER_PATH, owner=0)
        except ControlError as error:
            raise AdoptionFailure("toolchain") from error
        try:
            if not entrypoint_raw:
                raise AdoptionFailure("toolchain")
        finally:
            os.close(entrypoint_fd)
        capsule = _capsule(
            image_raw=image_raw, manifest_raw=manifest_raw, entrypoint_raw=entrypoint_raw,
            nonce=nonce, ticket=ticket, project_head=project_head, project_format=project_format,
            project_index=project_index, project_tree=project_tree, exceptions=exceptions,
            align_head=align_head, align_format=align_format, relative=relative, worker=worker,
            image_digest=str(predicate["image_digest"]),
        )
        capsule_fd = _sealed_memfd("align-llm-ordinary-adoption-capsule", capsule, 12)
        worker_fd = _sealed_memfd("align-llm-ordinary-adoption-worker", worker, 13)
        capsule_digest = hashlib.sha256(capsule).digest()
        channel.sendall(capsule_digest)
        # The native parent queues P on the peer endpoint.  The dispatcher
        # never consumes it; the worker/helper verify it at their boundary.
        worker_status, worker_stdout, worker_stderr = _launch_worker(
            worker_fd, ("--mode", "ordinary-adoption")
        )
        if worker_stdout:
            os.write(1, worker_stdout)
        if worker_stderr:
            os.write(2, worker_stderr)
        return worker_status
    except AdoptionFailure as error:
        return _fail(error.phase)
    except (OSError, ValueError, WireError, ControlError):
        return _fail("toolchain")
    finally:
        if channel is not None:
            channel.close()
        for fd in (capsule_fd, worker_fd):
            if fd >= 0:
                try:
                    os.close(fd)
                except OSError:
                    pass


def main(arguments: Sequence[str] | None = None) -> int:
    return dispatch(tuple(arguments if arguments is not None else os.sys.argv[1:]))


if __name__ == "__main__":
    raise SystemExit(main())
