#!/usr/bin/env python3
"""Image-owned supervisor and bootstrap control plane for Section 9.

The module is bundled into two deterministic Python zip applications.  The
supervisor bundle is embedded byte-for-byte in the installed ELF launcher;
the bootstrap bundle is installed as one immutable executable file.  Runtime
code therefore imports no repository module and no mutable image-side helper.
"""

from __future__ import annotations

import errno
import fcntl
import hashlib
import ctypes
import os
import posixpath
import re
import resource
import selectors
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from fresh_attestation import (
    IMAGE_KEY_ID,
    IMAGE_PREDICATE_TYPE,
    INVOCATION_PREDICATE_TYPE,
    RUN_KEY_ID,
    WireError,
    ed25519_public_key,
    sha256_hex,
    signed_envelope,
    validate_image_predicate,
    validate_invocation_predicate,
    verify_envelope,
)
from fresh_manifest import serialized_digest, structural_digest, validate_manifest_bytes


MAX_WORKER_BYTES = 4_194_304
MAX_ATTESTATION_BYTES = 262_144
MAX_MANIFEST_BYTES = 67_108_864
SNAPSHOT_DEADLINE_SECONDS = 5.0
CONTROLLER_PATH = "scripts/fresh-align-compiler"
SUPERVISOR_PATH = "/usr/local/libexec/align-llm/fresh-supervise"
BOOTSTRAP_PATH = "/usr/local/libexec/align-llm/fresh-bootstrap"
BOUNDARY_DISPATCHER_PATH = (
    "/usr/local/libexec/align-llm/request6-adoption-boundary-entrypoint"
)
DISPATCHER_PATH = "/usr/local/libexec/align-llm/request6-adoption-entrypoint"
ADOPTION_NAMESPACE_PATH = "/usr/bin/adoption-namespace"
MANIFEST_PATH = "/usr/local/share/align-llm/fresh-toolchain.json"
IMAGE_ATTESTATION_PATH = "/run/align-llm-fresh/image-attestation.dsse"
IMAGE_PUBLIC_KEY_PATH = "/usr/local/share/align-llm/image-verifier.pub"
RUN_PUBLIC_KEY_PATH = "/usr/local/share/align-llm/run-verifier.pub"
RUN_SIGNING_SEED_PATH = "/run/align-llm-fresh/run-signing-seed"
IMAGE_DIGEST_PATH = "/run/align-llm-fresh/image-digest"
PROVENANCE_DIGEST_PATH = "/run/align-llm-fresh/provenance-digest"
SELF_TEST_PROJECT_PATH = "/usr/local/share/align-llm/self-test/project"
GIT_PATH = "/runtime/git/bin/git"
PYTHON_PATH = "/usr/bin/python3"
EXPECTED_IMAGE_NAME = "oci://ghcr.io/sanohiro/align-llm-fresh"
SUPERVISOR_VERSION = "1.0.0"
WORKER_INVOCATION_TIMEOUT = 5_000
CONTROL_STREAM_LIMIT = 65_536
CONTROL_CGROUP_PREFIX = "align-llm-control-"
BOUNDARY_WORKER_PATH = "scripts/run-json-scan-row-ownership-adoption"
BOUNDARY_TIMEOUT_SECONDS = 5.0
ORDINARY_PREDICATE_TYPE = "https://align-llm.dev/attestations/ordinary-adoption/v2"
ORDINARY_REQUEST = "json-scan-row-ownership-adoption"
ORDINARY_TICKET_BYTES = 32
ORDINARY_NONCE_BYTES = 32
ORDINARY_WORKER_PATH = "scripts/run-json-scan-row-ownership-adoption"
ORDINARY_WORKER_LIMIT = 4_194_304
ORDINARY_ENVIRONMENT = {
    "PATH": "/usr/bin:/bin",
    "LC_ALL": "C",
    "LANG": "C",
    "HOME": "/nonexistent",
    "TMPDIR": "/tmp",
}
ORDINARY_NAMESPACE_ENVIRONMENT = {
    "PATH": "/tools",
    "LC_ALL": "C",
    "LANG": "C",
    "HOME": "/nonexistent",
    "TMPDIR": "/tmp",
    "PYTHONDONTWRITEBYTECODE": "1",
}

REQUIRED_SEALS = (
    fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL
)
FORBIDDEN_ENVIRONMENT = (
    "ALIGNC",
    "ALIGN_LLM_TOOLCHAIN_MANIFEST",
    "ALIGN_LLM_TOOLCHAIN_MANIFEST_SHA256",
    "ALIGN_LLM_WORK_PARENT",
    "CARGO_HOME",
    "GIT_CONFIG_GLOBAL",
    "GIT_CONFIG_SYSTEM",
    "GIT_CONFIG_COUNT",
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "LD_AUDIT",
    "LD_LIBRARY_PATH",
    "LD_PRELOAD",
    "PYTHONHOME",
    "PYTHONPATH",
    "RUSTC",
    "RUSTFLAGS",
)
CHILD_ENVIRONMENT = {
    "PATH": "/usr/bin:/bin",
    "LC_ALL": "C",
    "LANG": "C",
    "HOME": "/nonexistent",
    "TMPDIR": "/tmp",
}
WORKER_ENVIRONMENT = {
    "PATH": "/usr/bin:/bin",
    "LC_ALL": "C",
    "HOME": "/nonexistent",
    "TMPDIR": "/tmp",
    "PYTHONHOME": "/usr",
    "PYTHONNOUSERSITE": "1",
    "PYTHONDONTWRITEBYTECODE": "1",
}
PUBLIC_CATEGORIES = frozenset(
    {
        "ARGUMENT",
        "TRUST",
        "PLATFORM",
        "TOOL",
        "SOURCE",
        "CACHE",
        "FILESYSTEM",
        "BUILD",
        "COMPILER",
        "CHILD",
        "INTERNAL",
        "CLEANUP",
    }
)
PUBLIC_PHASES = frozenset(
    {
        "supervisor",
        "input",
        "manifest",
        "platform",
        "bwrap",
        "tools",
        "project-source",
        "align-source",
        "cache",
        "concurrency",
        "filesystem",
        "build",
        "compiler",
        "aggregate",
        "internal",
        "cleanup",
    }
)


@dataclass(frozen=True)
class ProfilePaths:
    supervisor: str = SUPERVISOR_PATH
    bootstrap: str = BOOTSTRAP_PATH
    manifest: str = MANIFEST_PATH
    image_attestation: str = IMAGE_ATTESTATION_PATH
    image_public_key: str = IMAGE_PUBLIC_KEY_PATH
    run_public_key: str = RUN_PUBLIC_KEY_PATH
    run_signing_seed: str = RUN_SIGNING_SEED_PATH
    image_digest: str = IMAGE_DIGEST_PATH
    provenance_digest: str = PROVENANCE_DIGEST_PATH
    self_test_project: str = SELF_TEST_PROJECT_PATH
    git: str = GIT_PATH
    python: str = PYTHON_PATH
    image_owner: int = 0
    run_owner: int | None = None


class ControlError(RuntimeError):
    """A bounded public fresh-image failure."""

    def __init__(self, category: str, phase: str, detail: str = "") -> None:
        super().__init__(detail or f"{category} {phase}")
        self.category = category
        self.phase = phase


def _control_cgroup_file_write(leaf_fd: int, name: str, raw: bytes) -> None:
    descriptor = os.open(
        name,
        os.O_WRONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
        dir_fd=leaf_fd,
    )
    try:
        view = memoryview(raw)
        while view:
            count = os.write(descriptor, view)
            if count <= 0:
                raise OSError(errno.EIO, "short control cgroup write")
            view = view[count:]
    finally:
        os.close(descriptor)


def _control_cgroup_file_read(leaf_fd: int, name: str, limit: int = 4096) -> bytes:
    descriptor = os.open(
        name,
        os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
        dir_fd=leaf_fd,
    )
    try:
        chunks: list[bytes] = []
        total = 0
        while True:
            block = os.read(descriptor, min(65_536, limit + 1 - total))
            if not block:
                return b"".join(chunks)
            total += len(block)
            if total > limit:
                raise OSError(errno.EFBIG, "control cgroup file exceeds bound")
            chunks.append(block)
    finally:
        os.close(descriptor)


def _control_cgroup_members(leaf_fd: int, name: str) -> tuple[int, ...]:
    raw = _control_cgroup_file_read(leaf_fd, name)
    members: list[int] = []
    for line in raw.splitlines():
        if not line or not line.isdigit() or int(line) <= 0:
            raise OSError(errno.EPROTO, "control cgroup membership is malformed")
        members.append(int(line))
    if len(set(members)) != len(members):
        raise OSError(errno.EPROTO, "control cgroup membership is duplicated")
    return tuple(sorted(members))


def _control_cgroup_empty(leaf_fd: int) -> None:
    if _control_cgroup_members(leaf_fd, "cgroup.procs") or _control_cgroup_members(
        leaf_fd, "cgroup.threads"
    ):
        raise OSError(errno.EBUSY, "control cgroup is not empty")


def _control_cgroup_populated(leaf_fd: int) -> bool:
    if _control_cgroup_members(leaf_fd, "cgroup.procs"):
        return True
    if _control_cgroup_members(leaf_fd, "cgroup.threads"):
        return True
    return b"populated 1" in _control_cgroup_file_read(leaf_fd, "cgroup.events")


def _control_cgroup_child_membership(leaf_fd: int, pid: int) -> None:
    if _control_cgroup_members(leaf_fd, "cgroup.procs") != (pid,):
        raise OSError(errno.EBUSY, "control cgroup contains an unexpected process")
    try:
        task_names = os.listdir(f"/proc/{pid}/task")
    except OSError as error:
        raise OSError(errno.EBUSY, "control child threads could not be inspected") from error
    expected_threads = tuple(sorted(int(name) for name in task_names if name.isdigit()))
    if _control_cgroup_members(leaf_fd, "cgroup.threads") != expected_threads:
        raise OSError(errno.EBUSY, "control cgroup contains an unexpected thread")


def _control_cgroup_group_is_owned(leaf_fd: int, process_group: int) -> bool:
    members = _control_cgroup_members(leaf_fd, "cgroup.procs") + _control_cgroup_members(
        leaf_fd, "cgroup.threads"
    )
    for pid in members:
        try:
            if os.getpgid(pid) != process_group:
                return False
        except ProcessLookupError:
            return False
    return True


def _control_cgroup_lease() -> tuple[int, int, str, tuple[int, int, int, int, int]]:
    parent_path = f"/sys/fs/cgroup/align-llm-fresh/{os.geteuid()}"
    parent_fd = os.open(
        parent_path,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
    )
    leaf_fd = -1
    leaf_name = ""
    identity: tuple[int, int, int, int, int] | None = None
    try:
        parent = os.fstat(parent_fd)
        if (
            not stat.S_ISDIR(parent.st_mode)
            or parent.st_uid != os.geteuid()
            or stat.S_IMODE(parent.st_mode) != 0o700
        ):
            raise OSError(errno.EPERM, "control cgroup parent rejected")
        for _ in range(8):
            candidate = CONTROL_CGROUP_PREFIX + os.urandom(16).hex()
            try:
                os.mkdir(candidate, 0o700, dir_fd=parent_fd)
            except FileExistsError:
                continue
            leaf_name = candidate
            leaf_fd = os.open(
                candidate,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=parent_fd,
            )
            leaf = os.fstat(leaf_fd)
            identity = (
                leaf.st_dev,
                leaf.st_ino,
                stat.S_IFMT(leaf.st_mode),
                stat.S_IMODE(leaf.st_mode),
                leaf.st_uid,
            )
            current = os.stat(leaf_name, dir_fd=parent_fd, follow_symlinks=False)
            if (
                current.st_dev,
                current.st_ino,
                stat.S_IFMT(current.st_mode),
                stat.S_IMODE(current.st_mode),
                current.st_uid,
            ) != identity:
                raise OSError(errno.ESTALE, "control cgroup leaf replaced")
            _control_cgroup_empty(leaf_fd)
            _control_cgroup_file_write(leaf_fd, "pids.max", b"512\n")
            if _control_cgroup_file_read(leaf_fd, "pids.max").strip() != b"512":
                raise OSError(errno.EIO, "control cgroup pids.max rejected")
            _control_cgroup_empty(leaf_fd)
            return parent_fd, leaf_fd, leaf_name, identity
        raise OSError(errno.EEXIST, "control cgroup leaf name exhaustion")
    except Exception:
        cleanup_error: OSError | None = None
        if leaf_fd >= 0:
            try:
                current = os.stat(leaf_name, dir_fd=parent_fd, follow_symlinks=False)
                leaf = os.fstat(leaf_fd)
                if (current.st_dev, current.st_ino) == (leaf.st_dev, leaf.st_ino):
                    if identity is None:
                        raise OSError(errno.ESTALE, "control cgroup leaf identity unavailable")
                    _control_remove_cgroup_leaf(parent_fd, leaf_fd, leaf_name, identity)
                else:
                    cleanup_error = OSError(errno.ESTALE, "control cgroup leaf was replaced")
            except OSError as error:
                cleanup_error = error
            try:
                os.close(leaf_fd)
            except OSError as error:
                cleanup_error = cleanup_error or error
        try:
            os.close(parent_fd)
        except OSError as error:
            cleanup_error = cleanup_error or error
        if cleanup_error is not None:
            raise cleanup_error
        raise


def _control_cgroup_matches(
    parent_fd: int,
    leaf_fd: int,
    leaf_name: str,
    identity: tuple[int, int, int, int, int],
) -> bool:
    try:
        current = os.stat(leaf_name, dir_fd=parent_fd, follow_symlinks=False)
        leaf = os.fstat(leaf_fd)
    except OSError:
        return False
    current_identity = (
        current.st_dev,
        current.st_ino,
        stat.S_IFMT(current.st_mode),
        stat.S_IMODE(current.st_mode),
        current.st_uid,
    )
    leaf_identity = (
        leaf.st_dev,
        leaf.st_ino,
        stat.S_IFMT(leaf.st_mode),
        stat.S_IMODE(leaf.st_mode),
        leaf.st_uid,
    )
    return current_identity == identity == leaf_identity


def _control_cgroup_entry_present(parent_fd: int, name: str) -> bool:
    try:
        os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    return True


def _control_remove_cgroup_leaf(
    parent_fd: int,
    leaf_fd: int,
    leaf_name: str,
    identity: tuple[int, int, int, int, int],
) -> None:
    if not _control_cgroup_matches(parent_fd, leaf_fd, leaf_name, identity):
        raise OSError(errno.ESTALE, "control cgroup leaf identity changed")
    _control_cgroup_empty(leaf_fd)
    # cgroup-v2 does not implement rename(2). The delegated parent is an
    # exclusive worker/profile writer boundary, so the authenticated leaf name
    # is the only available quarantine identity. No uncooperating same-UID
    # writer may replace it between this proof and the descriptor-relative
    # rmdir; such a writer is outside the profile contract.
    try:
        os.rmdir(leaf_name, dir_fd=parent_fd)
    except OSError as error:
        raise OSError(errno.EIO, "control cgroup removal failed") from error
    if _control_cgroup_entry_present(parent_fd, leaf_name):
        raise OSError(errno.EBUSY, "control cgroup remains after removal")


def _control_cleanup_lease(
    parent_fd: int,
    leaf_fd: int,
    leaf_name: str,
    identity: tuple[int, int, int, int, int],
) -> OSError | None:
    cleanup_error: OSError | None = None
    try:
        if not _control_cgroup_matches(parent_fd, leaf_fd, leaf_name, identity):
            raise OSError(errno.ESTALE, "control cgroup identity changed during cleanup")
        if _control_cgroup_populated(leaf_fd):
            raise OSError(errno.EBUSY, "control cgroup remained populated during cleanup")
        _control_remove_cgroup_leaf(parent_fd, leaf_fd, leaf_name, identity)
    except OSError as error:
        cleanup_error = error
    for descriptor in (leaf_fd, parent_fd):
        try:
            os.close(descriptor)
        except OSError as error:
            cleanup_error = cleanup_error or error
    return cleanup_error


def _control_pid_start(pid: int) -> str:
    raw = Path(f"/proc/{pid}/stat").read_bytes()
    close = raw.rfind(b")")
    fields = raw[close + 2 :].split()
    if close < 0 or len(fields) < 20:
        raise OSError(errno.EINVAL, "control child identity rejected")
    return fields[19].decode("ascii")


def _control_terminate(
    process: subprocess.Popen[bytes],
    *,
    start: str,
    group: int,
    parent_fd: int,
    leaf_fd: int,
    leaf_name: str,
    identity: tuple[int, int, int, int, int],
) -> None:
    populated = _control_cgroup_populated(leaf_fd)
    if process.poll() is None:
        try:
            if _control_pid_start(process.pid) == start and os.getpgid(process.pid) == group:
                os.killpg(group, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 1
    while time.monotonic() < deadline and (process.poll() is None or populated):
        time.sleep(0.01)
        populated = _control_cgroup_populated(leaf_fd)
    if process.poll() is None or populated:
        if not _control_cgroup_matches(parent_fd, leaf_fd, leaf_name, identity):
            raise OSError(errno.ESTALE, "control cgroup identity changed")
        if not _control_cgroup_group_is_owned(leaf_fd, group):
            raise OSError(errno.EPERM, "control cgroup contains a foreign process")
        _control_cgroup_file_write(leaf_fd, "cgroup.kill", b"1\n")
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired as error:
        raise OSError(errno.ETIMEDOUT, "control child did not exit") from error
    if _control_cgroup_populated(leaf_fd):
        raise OSError(errno.EBUSY, "control cgroup remained populated")


def _run_controlled_child(
    arguments: Sequence[str],
    *,
    environment: Mapping[str, str],
    timeout: float,
    pass_fds: Sequence[int] = (),
    executable: str | None = None,
    cwd: str | None = None,
    stdout_limit: int = CONTROL_STREAM_LIMIT,
    stderr_limit: int = CONTROL_STREAM_LIMIT,
) -> subprocess.CompletedProcess[bytes]:
    parent_fd, leaf_fd, leaf_name, identity = _control_cgroup_lease()
    process: subprocess.Popen[bytes] | None = None
    streams: selectors.BaseSelector | None = None
    captures = {"stdout": bytearray(), "stderr": bytearray()}
    start = ""
    group = -1
    timed_out = False
    overflow = False
    result: subprocess.CompletedProcess[bytes] | None = None
    primary_error: BaseException | None = None
    stream_error: BaseException | None = None
    try:
        try:
            def preexec() -> None:
                resource.setrlimit(resource.RLIMIT_NPROC, (512, 512))
                resource.setrlimit(resource.RLIMIT_NOFILE, (4096, 4096))
                resource.setrlimit(resource.RLIMIT_FSIZE, (536_870_912, 536_870_912))
                _control_cgroup_empty(leaf_fd)
                _control_cgroup_file_write(leaf_fd, "cgroup.procs", b"0\n")
                os.set_inheritable(leaf_fd, False)
                os.setsid()

            process = subprocess.Popen(
                list(arguments),
                executable=executable,
                cwd=cwd,
                env=dict(environment),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                pass_fds=tuple(dict.fromkeys((leaf_fd, *pass_fds))),
                close_fds=True,
                preexec_fn=preexec,
            )
            start = _control_pid_start(process.pid)
            group = os.getpgid(process.pid)
            try:
                _control_cgroup_child_membership(leaf_fd, process.pid)
            except OSError:
                if process.poll() is None:
                    raise
                _control_cgroup_empty(leaf_fd)
            assert process.stdout is not None and process.stderr is not None
            streams = selectors.DefaultSelector()
            for stream, label in ((process.stdout, "stdout"), (process.stderr, "stderr")):
                os.set_blocking(stream.fileno(), False)
                streams.register(stream, selectors.EVENT_READ, label)
            deadline = time.monotonic() + timeout
            while streams.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    break
                for key, _ in streams.select(min(remaining, 0.25)):
                    block = os.read(key.fileobj.fileno(), 1_048_576)
                    if not block:
                        streams.unregister(key.fileobj)
                        continue
                    target = captures[key.data]
                    limit = stdout_limit if key.data == "stdout" else stderr_limit
                    if len(target) + len(block) > limit:
                        overflow = True
                        break
                    target.extend(block)
                if timed_out or overflow:
                    break
            if not timed_out and not overflow:
                try:
                    process.wait(timeout=max(0.1, deadline - time.monotonic()))
                except subprocess.TimeoutExpired:
                    timed_out = True
            if (
                timed_out
                or overflow
                or process.poll() is None
                or _control_cgroup_populated(leaf_fd)
            ):
                _control_terminate(
                    process,
                    start=start,
                    group=group,
                    parent_fd=parent_fd,
                    leaf_fd=leaf_fd,
                    leaf_name=leaf_name,
                    identity=identity,
                )
            else:
                process.wait()
            result = subprocess.CompletedProcess(
                list(arguments),
                process.returncode,
                bytes(captures["stdout"]),
                bytes(captures["stderr"]),
            )
        except BaseException as error:
            primary_error = error
            if process is not None:
                try:
                    _control_terminate(
                        process,
                        start=start,
                        group=group,
                        parent_fd=parent_fd,
                        leaf_fd=leaf_fd,
                        leaf_name=leaf_name,
                        identity=identity,
                    )
                except BaseException as terminate_error:
                    primary_error = terminate_error
    finally:
        if streams is not None:
            try:
                streams.close()
            except BaseException as error:
                stream_error = error
        cleanup_error = _control_cleanup_lease(parent_fd, leaf_fd, leaf_name, identity)
    if cleanup_error is not None:
        if primary_error is not None:
            raise cleanup_error from primary_error
        if stream_error is not None:
            raise cleanup_error from stream_error
        raise cleanup_error
    if stream_error is not None:
        if primary_error is not None:
            raise stream_error from primary_error
        raise stream_error
    if primary_error is not None:
        raise primary_error
    if result is None:
        raise OSError(errno.ECHILD, "control child was not started")
    if timed_out:
        raise subprocess.TimeoutExpired(arguments, timeout)
    if overflow:
        raise ValueError("control child output exceeds bound")
    return result


@dataclass(frozen=True)
class FileIdentity:
    device: int
    inode: int
    mode: int
    links: int
    owner: int
    size: int


def _identity(fd: int) -> FileIdentity:
    value = os.fstat(fd)
    return FileIdentity(
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_nlink,
        value.st_uid,
        value.st_size,
    )


def _same_identity(left: FileIdentity, right: FileIdentity) -> bool:
    return left == right


def _close_descriptors_except(allowed: set[int]) -> None:
    try:
        descriptors = [int(name) for name in os.listdir("/proc/self/fd")]
    except (OSError, ValueError) as error:
        raise ControlError("TRUST", "supervisor", "descriptor inventory unavailable") from error
    for descriptor in descriptors:
        if descriptor in allowed:
            continue
        try:
            os.close(descriptor)
        except OSError:
            pass


def _read_exact_bounded(fd: int, *, limit: int, deadline: float) -> bytes:
    identity = _identity(fd)
    if identity.size < 0 or identity.size > limit:
        raise ControlError("TRUST", "input", "file exceeds its byte bound")
    output = bytearray()
    while len(output) < identity.size:
        if time.monotonic() > deadline:
            raise ControlError("TRUST", "input", "file snapshot deadline exceeded")
        chunk = os.read(fd, min(65_536, identity.size - len(output)))
        if not chunk:
            raise ControlError("TRUST", "input", "file snapshot was short")
        output.extend(chunk)
    if os.read(fd, 1):
        raise ControlError("TRUST", "input", "file grew during snapshot")
    return bytes(output)


def _regular_snapshot(
    fd: int,
    *,
    limit: int,
    exact_mode: int | None = None,
    exact_owner: int | None = None,
    deadline: float | None = None,
) -> bytes:
    before = _identity(fd)
    if not stat.S_ISREG(before.mode) or before.links != 1:
        raise ControlError("TRUST", "input", "input is not a single-link regular file")
    if exact_mode is not None and stat.S_IMODE(before.mode) != exact_mode:
        raise ControlError("TRUST", "input", "input has the wrong mode")
    if exact_owner is not None and before.owner != exact_owner:
        raise ControlError("TRUST", "input", "input has the wrong owner")
    os.lseek(fd, 0, os.SEEK_SET)
    raw = _read_exact_bounded(
        fd,
        limit=limit,
        deadline=(
            time.monotonic() + SNAPSHOT_DEADLINE_SECONDS
            if deadline is None
            else deadline
        ),
    )
    after = _identity(fd)
    if not _same_identity(before, after):
        raise ControlError("TRUST", "input", "input changed during snapshot")
    return raw


def _open_regular(
    path: str,
    *,
    limit: int,
    exact_mode: int | None = None,
    exact_owner: int | None = None,
) -> tuple[int, bytes]:
    deadline = time.monotonic() + SNAPSHOT_DEADLINE_SECONDS
    try:
        fd = os.open(
            path,
            os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC,
        )
    except OSError as error:
        raise ControlError("TRUST", "input", f"cannot open {path}") from error
    try:
        return fd, _regular_snapshot(
            fd,
            limit=limit,
            exact_mode=exact_mode,
            exact_owner=exact_owner,
            deadline=deadline,
        )
    except Exception:
        os.close(fd)
        raise


def _read_key(path: str, *, private: bool, owner: int) -> bytes:
    mode = 0o400 if private else 0o444
    fd, raw = _open_regular(
        path,
        limit=32,
        exact_mode=mode,
        exact_owner=owner,
    )
    os.close(fd)
    if len(raw) != 32:
        raise ControlError("TRUST", "supervisor", "key has the wrong size")
    return raw


def _read_digest(path: str, *, owner: int) -> str:
    fd, raw = _open_regular(path, limit=72, exact_mode=0o444, exact_owner=owner)
    os.close(fd)
    try:
        if len(raw) != 72 or raw[-1:] != b"\n":
            raise ValueError("digest file framing")
        value = raw[:-1].decode("ascii")
    except (UnicodeDecodeError, ValueError) as error:
        raise ControlError("TRUST", "supervisor", "digest is not ASCII") from error
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
        raise ControlError("TRUST", "supervisor", "digest file is not canonical")
    return value


def _sealed_memfd(name: str, raw: bytes, target: int) -> int:
    try:
        fd = os.memfd_create(name, os.MFD_ALLOW_SEALING | os.MFD_CLOEXEC)
        view = memoryview(raw)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise OSError(errno.EIO, "short memfd write")
            view = view[written:]
        os.lseek(fd, 0, os.SEEK_SET)
        fcntl.fcntl(fd, fcntl.F_ADD_SEALS, REQUIRED_SEALS)
        if fcntl.fcntl(fd, fcntl.F_GET_SEALS) != REQUIRED_SEALS:
            raise OSError(errno.EPERM, "memfd seals do not match")
        if fd != target:
            os.dup2(fd, target, inheritable=True)
            os.close(fd)
            fd = target
        os.set_inheritable(fd, True)
        return fd
    except OSError as error:
        raise ControlError("TRUST", "supervisor", "cannot create sealed input") from error


def _read_sealed(
    fd: int, *, limit: int, expected_name: str | None = None
) -> bytes:
    try:
        seals = fcntl.fcntl(fd, fcntl.F_GET_SEALS)
    except OSError as error:
        raise ControlError("TRUST", "supervisor", "input is not a sealable memfd") from error
    if seals != REQUIRED_SEALS:
        raise ControlError("TRUST", "supervisor", "input memfd has incomplete seals")
    before = _identity(fd)
    if not stat.S_ISREG(before.mode) or before.links != 0 or before.size > limit:
        raise ControlError("TRUST", "supervisor", "sealed input identity is invalid")
    try:
        fstatfs = ctypes.CDLL(None, use_errno=True).fstatfs
        fstatfs.argtypes = [ctypes.c_int, ctypes.c_void_p]
        fstatfs.restype = ctypes.c_int
        words = (ctypes.c_long * 32)()
        if fstatfs(fd, ctypes.byref(words)) != 0 or words[0] != 0x01021994:
            error_number = ctypes.get_errno()
            raise OSError(error_number, os.strerror(error_number))
    except OSError as error:
        raise ControlError("TRUST", "supervisor", "sealed input filesystem is invalid") from error
    if expected_name is not None:
        try:
            link = os.readlink(f"/proc/self/fd/{fd}")
        except OSError as error:
            raise ControlError("TRUST", "supervisor", "sealed input name is unavailable") from error
        if link != f"/memfd:{expected_name} (deleted)":
            raise ControlError("TRUST", "supervisor", "sealed input name is invalid")
    os.lseek(fd, 0, os.SEEK_SET)
    try:
        raw = _read_exact_bounded(
            fd, limit=limit, deadline=time.monotonic() + SNAPSHOT_DEADLINE_SECONDS
        )
    except ControlError as error:
        raise ControlError("TRUST", "supervisor", "sealed input read rejected") from error
    if not _same_identity(before, _identity(fd)):
        raise ControlError("TRUST", "supervisor", "sealed input identity changed")
    os.lseek(fd, 0, os.SEEK_SET)
    return raw


def _normalize_relative(value: str) -> str:
    if not value or "\x00" in value or value.startswith("/"):
        raise ControlError("ARGUMENT", "input", "ALIGN_REPO is not relative")
    pieces: list[str] = []
    for piece in value.split("/"):
        if piece in ("", "."):
            continue
        if piece == "..":
            if pieces and pieces[-1] != "..":
                pieces.pop()
            else:
                pieces.append(piece)
        else:
            pieces.append(piece)
    if not pieces:
        raise ControlError("ARGUMENT", "input", "ALIGN_REPO normalizes to empty")
    normalized = "/".join(pieces)
    try:
        encoded = normalized.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ControlError("ARGUMENT", "input", "ALIGN_REPO is not valid UTF-8") from error
    if len(encoded) > 4096:
        raise ControlError("ARGUMENT", "input", "ALIGN_REPO exceeds its byte bound")
    return normalized


def _normalize_absolute(value: str) -> str:
    if not value or "\x00" in value or not value.startswith("/"):
        raise ControlError("ARGUMENT", "input", "absolute path is invalid")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ControlError("ARGUMENT", "input", "absolute path is not valid UTF-8") from error
    if any(ord(character) < 0x20 for character in value):
        raise ControlError("ARGUMENT", "input", "absolute path contains a control character")
    pieces = value.split("/")[1:]
    if not pieces or any(piece in ("", ".", "..") for piece in pieces):
        raise ControlError("ARGUMENT", "input", "absolute path is not canonical")
    normalized = "/" + "/".join(pieces)
    if len(normalized.encode("utf-8")) > 4096:
        raise ControlError("ARGUMENT", "input", "absolute path exceeds its byte bound")
    return normalized


def _canonical_relative_from_absolute(absolute: str) -> str:
    try:
        project = _normalize_absolute(os.getcwd())
    except OSError as error:
        raise ControlError("TRUST", "supervisor", "project cwd is unavailable") from error
    normalized = _normalize_absolute(absolute)
    relative = posixpath.relpath(normalized, project)
    if relative == "." or relative.startswith("/"):
        raise ControlError("ARGUMENT", "input", "absolute path is not a sibling path")
    return _normalize_relative(relative)


def _open_absolute_directory(value: str, target: int) -> int:
    """Walk an absolute directory without following a component symlink."""

    normalized = _normalize_absolute(value)
    retained: list[tuple[int, int | None, bytes | None, FileIdentity]] = []
    root_fd = -1
    current_fd = -1

    def identity_from_stat(value: os.stat_result) -> FileIdentity:
        return FileIdentity(
            value.st_dev,
            value.st_ino,
            value.st_mode,
            value.st_nlink,
            value.st_uid,
            value.st_size,
        )

    def close_retained() -> None:
        seen: set[int] = set()
        for descriptor, _, _, _ in reversed(retained):
            if descriptor in seen or descriptor == target:
                continue
            seen.add(descriptor)
            try:
                os.close(descriptor)
            except OSError:
                pass

    try:
        root_fd = os.open(
            "/", os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        )
        os.dup2(root_fd, 17, inheritable=False)
        if root_fd != 17:
            os.close(root_fd)
        root_fd = -1
        current_fd = 17
        retained.append((17, None, None, _identity(17)))
        for component in normalized.split("/")[1:]:
            parent_identity = _identity(current_fd)
            next_fd = os.open(
                os.fsencode(component),
                os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=current_fd,
            )
            opened_identity = _identity(next_fd)
            entry_identity = identity_from_stat(
                os.stat(component, dir_fd=current_fd, follow_symlinks=False)
            )
            if opened_identity != entry_identity or _identity(current_fd) != parent_identity:
                os.close(next_fd)
                raise ControlError("TRUST", "supervisor", "Align path changed during walk")
            retained.append((next_fd, current_fd, os.fsencode(component), opened_identity))
            current_fd = next_fd
        os.dup2(current_fd, target, inheritable=True)
        for descriptor, parent, component, identity in retained:
            if _identity(descriptor) != identity:
                raise ControlError("TRUST", "supervisor", "Align path identity changed")
            if parent is not None and component is not None:
                observed = identity_from_stat(
                    os.stat(component, dir_fd=parent, follow_symlinks=False)
                )
                if observed != identity:
                    raise ControlError("TRUST", "supervisor", "Align path identity changed")
        try:
            observed = _normalize_absolute(os.readlink(f"/proc/self/fd/{target}"))
        except (OSError, ControlError) as error:
            raise ControlError("TRUST", "supervisor", "Align path identity is unavailable") from error
        if observed != normalized:
            raise ControlError("TRUST", "supervisor", "Align path identity changed")
        close_retained()
        try:
            os.close(17)
        except OSError:
            pass
        retained.clear()
        current_fd = -1
        return target
    except ControlError:
        close_retained()
        raise
    except OSError as error:
        close_retained()
        raise ControlError("TRUST", "supervisor", "Align path walk failed") from error
    finally:
        if root_fd >= 0 and root_fd != target:
            try:
                os.close(root_fd)
            except OSError:
                pass
        if current_fd >= 0 and current_fd != target and not retained:
            try:
                os.close(current_fd)
            except OSError:
                pass
        if retained:
            close_retained()
        try:
            os.close(17)
        except OSError:
            pass


def _execveat(fd: int, arguments: Sequence[str], environment: Mapping[str, str]) -> None:
    """Execute one retained ELF descriptor without reopening its pathname."""

    libc = ctypes.CDLL(None, use_errno=True)
    function = libc.execveat
    function.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.POINTER(ctypes.c_char_p),
        ctypes.POINTER(ctypes.c_char_p),
        ctypes.c_int,
    ]
    function.restype = ctypes.c_int
    encoded_arguments = [value.encode("utf-8") for value in arguments]
    encoded_environment = [
        f"{name}={value}".encode("utf-8") for name, value in environment.items()
    ]
    argv = (ctypes.c_char_p * (len(encoded_arguments) + 1))(
        *(encoded_arguments + [None])
    )
    envp = (ctypes.c_char_p * (len(encoded_environment) + 1))(
        *(encoded_environment + [None])
    )
    result = function(fd, b"", argv, envp, 0x1000)  # AT_EMPTY_PATH
    if result != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))


def _runtime_file_binding(
    manifest: Mapping[str, Any],
    target: str,
    *,
    owner: int,
    limit: int = MAX_WORKER_BYTES,
) -> tuple[int, bytes, Mapping[str, Any]]:
    matches = [
        binding
        for binding in manifest["runtime_bindings"]
        if binding.get("target") == target
    ]
    if len(matches) != 1:
        raise ControlError("TRUST", "supervisor", "runtime binding is missing")
    binding = matches[0]
    tree = binding.get("manifest")
    if (
        not isinstance(binding.get("source"), str)
        or not binding.get("source", "/").startswith("/")
        or binding.get("kind") != "file"
        or not isinstance(tree, Mapping)
        or tree.get("kind") != "file"
        or tree.get("mode") != "0755"
    ):
        raise ControlError("TRUST", "supervisor", "runtime binding record is invalid")
    try:
        descriptor, raw = _open_regular(
            binding["source"],
            limit=limit,
            exact_mode=0o755,
            exact_owner=owner,
        )
    except ControlError as error:
        raise ControlError("TRUST", "supervisor", "runtime binding source is unavailable") from error
    if (
        tree.get("size") != len(raw)
        or sha256_hex(raw) != tree.get("sha256")
        or serialized_digest(tree) != binding.get("manifest_sha256")
    ):
        os.close(descriptor)
        raise ControlError("TRUST", "supervisor", "runtime binding digest mismatch")
    return descriptor, raw, binding


def _load_boundary_manifest(raw: bytes) -> Mapping[str, Any]:
    try:
        return validate_manifest_bytes(raw)
    except WireError as error:
        raise ControlError("TRUST", "supervisor", "boundary manifest is invalid") from error


def _boundary_worker_presence(project_fd: int) -> None:
    """Reject the future consumer worker without reading or executing its bytes."""

    scripts_fd = -1
    worker_fd = -1
    try:
        scripts_fd = os.open(
            "scripts",
            os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=project_fd,
        )
        worker_fd = os.open(
            os.fsencode(BOUNDARY_WORKER_PATH.split("/", 1)[1]),
            os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=scripts_fd,
        )
        os.fstat(worker_fd)
    except OSError as error:
        raise ControlError("REVISION", "revision", "boundary worker is absent or invalid") from error
    finally:
        for descriptor in (worker_fd, scripts_fd):
            if descriptor >= 0:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
    raise ControlError("REVISION", "revision", "boundary worker is present")


def _ordinary_worker_snapshot(project_fd: int, *, owner: int) -> tuple[str, int, bytes]:
    scripts_fd = -1
    worker_fd = -1
    try:
        scripts_fd = os.open(
            "scripts",
            os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=project_fd,
        )
        worker_fd = os.open(
            os.fsencode(ORDINARY_WORKER_PATH.split("/", 1)[1]),
            os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=scripts_fd,
        )
        raw = _regular_snapshot(
            worker_fd,
            limit=ORDINARY_WORKER_LIMIT,
            exact_mode=0o755,
            exact_owner=owner,
        )
        return ORDINARY_WORKER_PATH, len(raw), raw
    except OSError as error:
        raise ControlError("REVISION", "revision", "ordinary worker source is unavailable") from error
    finally:
        for descriptor in (worker_fd, scripts_fd):
            if descriptor >= 0:
                try:
                    os.close(descriptor)
                except OSError:
                    pass


def _mode_from_arguments(arguments: Sequence[str]) -> str:
    if list(arguments) == ["make", "--no-print-directory", "ci"]:
        return "ci"
    if list(arguments) == ["--mode", "build"]:
        return "build"
    if list(arguments) == ["--mode", "self-test"]:
        return "self-test"
    if list(arguments) == ["--mode", "ordinary-adoption-boundary"]:
        return "ordinary-adoption-boundary"
    if list(arguments) == ["--mode", "ordinary-adoption"]:
        return "ordinary-adoption"
    raise ControlError("ARGUMENT", "input", "request vector is not accepted")


def _reject_environment(environment: Mapping[str, str], *, mode: str) -> str:
    for name in FORBIDDEN_ENVIRONMENT:
        if name in environment:
            raise ControlError("ARGUMENT", "input", f"forbidden environment: {name}")
    for name in ("MAKEFLAGS", "GNUMAKEFLAGS", "MAKEOVERRIDES"):
        if environment.get(name, ""):
            raise ControlError("ARGUMENT", "input", f"nonempty {name}")
    if mode == "ordinary-adoption-boundary":
        allowed = {"PATH", "LC_ALL", "LANG", "HOME", "TMPDIR", "ALIGN_REPO"}
        unexpected = set(environment) - allowed
        if unexpected:
            raise ControlError("ARGUMENT", "input", "boundary environment is not exact")
        align_repo = environment.get("ALIGN_REPO")
        if align_repo is None:
            raise ControlError("ARGUMENT", "input", "boundary mode requires ALIGN_REPO")
        return _normalize_absolute(align_repo)
    if mode == "ordinary-adoption":
        allowed = {"PATH", "LC_ALL", "LANG", "HOME", "TMPDIR", "ALIGN_REPO"}
        unexpected = set(environment) - allowed
        if unexpected:
            raise ControlError("ARGUMENT", "input", "ordinary environment is not exact")
        align_repo = environment.get("ALIGN_REPO")
        if align_repo is None:
            raise ControlError("ARGUMENT", "input", "ordinary mode requires ALIGN_REPO")
        return _normalize_absolute(align_repo)
    align_repo = environment.get("ALIGN_REPO", "../align")
    if mode == "self-test" and "ALIGN_REPO" in environment:
        raise ControlError("ARGUMENT", "input", "self-test rejects ALIGN_REPO")
    return _normalize_relative(align_repo)


def _git_identity(
    project_fd: int, git_path: str, *, git_fd: int | None = None
) -> tuple[str, str]:
    environment = {
        "PATH": "/usr/bin:/bin",
        "LC_ALL": "C",
        "HOME": "/nonexistent",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_COUNT": "0",
        "GIT_OPTIONAL_LOCKS": "0",
    }
    cwd = f"/proc/self/fd/{project_fd}"

    def run(*arguments: str) -> str:
        try:
            result = _run_controlled_child(
                [git_path, "-c", "safe.directory=*", *arguments],
                cwd=cwd,
                environment=environment,
                pass_fds=() if git_fd is None else (git_fd,),
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ControlError("SOURCE", "project-source", "Git identity probe failed") from error
        if result.returncode != 0 or result.stderr or len(result.stdout) > 128:
            raise ControlError("SOURCE", "project-source", "Git identity probe rejected")
        try:
            return result.stdout.decode("ascii").strip()
        except UnicodeDecodeError as error:
            raise ControlError("SOURCE", "project-source", "Git identity is not ASCII") from error

    object_format = run("rev-parse", "--show-object-format")
    head = run("rev-parse", "--verify", "HEAD")
    if object_format not in ("sha1", "sha256"):
        raise ControlError("SOURCE", "project-source", "unsupported Git object format")
    width = 40 if object_format == "sha1" else 64
    if len(head) != width or not re.fullmatch(r"[0-9a-f]+", head):
        raise ControlError("SOURCE", "project-source", "invalid Git HEAD")
    return object_format, head


def _worker_snapshot(project_fd: int, *, owner: int) -> bytes:
    deadline = time.monotonic() + SNAPSHOT_DEADLINE_SECONDS
    try:
        scripts_fd = os.open(
            "scripts",
            os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=project_fd,
        )
        worker_fd = os.open(
            "fresh-align-compiler",
            os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=scripts_fd,
        )
    except OSError as error:
        raise ControlError("TRUST", "input", "cannot open repository worker") from error
    finally:
        if "scripts_fd" in locals():
            os.close(scripts_fd)
    try:
        return _regular_snapshot(
            worker_fd,
            limit=MAX_WORKER_BYTES,
            exact_mode=0o755,
            exact_owner=owner,
            deadline=deadline,
        )
    finally:
        if "worker_fd" in locals():
            os.close(worker_fd)


def _verify_image_envelope(
    raw: bytes,
    *,
    paths: ProfilePaths,
    supervisor_raw: bytes,
) -> tuple[Mapping[str, object], bytes, bytes, bytes]:
    try:
        image_key = _read_key(
            paths.image_public_key, private=False, owner=paths.image_owner
        )
    except ControlError as error:
        raise ControlError("TRUST", "supervisor", "image verifier unavailable") from error
    try:
        verified = verify_envelope(
            raw,
            expected_payload_type=IMAGE_PREDICATE_TYPE,
            expected_key_id=IMAGE_KEY_ID,
            public_key=image_key,
            predicate_validator=validate_image_predicate,
        )
    except WireError as error:
        raise ControlError("TRUST", "supervisor", "invalid image envelope") from error
    predicate = verified.predicate
    bootstrap_fd = -1
    manifest_fd = -1
    try:
        bootstrap_fd, bootstrap_raw = _open_regular(
            paths.bootstrap,
            limit=MAX_WORKER_BYTES,
            exact_mode=0o755,
            exact_owner=paths.image_owner,
        )
        manifest_fd, manifest_raw = _open_regular(
            paths.manifest,
            limit=MAX_MANIFEST_BYTES,
            exact_mode=0o444,
            exact_owner=paths.image_owner,
        )
    except ControlError as error:
        if bootstrap_fd >= 0:
            os.close(bootstrap_fd)
        if manifest_fd >= 0:
            os.close(manifest_fd)
        raise ControlError("TRUST", "supervisor", "image artifact unavailable") from error
    os.close(bootstrap_fd)
    os.close(manifest_fd)
    try:
        expected = {
            "image_digest": _read_digest(paths.image_digest, owner=paths.image_owner),
            "image_name": EXPECTED_IMAGE_NAME,
            "provenance_digest": _read_digest(
                paths.provenance_digest, owner=paths.image_owner
            ),
            "verifier_key_sha256": sha256_hex(image_key),
            "supervisor_path": SUPERVISOR_PATH,
            "supervisor_sha256": sha256_hex(supervisor_raw),
            "bootstrap_path": BOOTSTRAP_PATH,
            "bootstrap_sha256": sha256_hex(bootstrap_raw),
            "manifest_path": MANIFEST_PATH,
            "manifest_sha256": sha256_hex(manifest_raw),
        }
    except ControlError as error:
        raise ControlError("TRUST", "supervisor", "image tuple unavailable") from error
    for name, value in expected.items():
        if predicate.get(name) != value:
            raise ControlError("TRUST", "supervisor", f"image tuple mismatch: {name}")
    return predicate, image_key, bootstrap_raw, manifest_raw


def _invocation_predicate(
    *,
    image_envelope: bytes,
    manifest_raw: bytes,
    object_format: str,
    head: str,
    align_repo: str,
    worker_raw: bytes,
    run_public_key: bytes,
) -> OrderedDict[str, object]:
    return OrderedDict(
        [
            ("schema_version", 1),
            ("image_attestation_sha256", sha256_hex(image_envelope)),
            ("manifest_sha256", sha256_hex(manifest_raw)),
            ("repository_object_format", object_format),
            ("repository_head", head),
            ("align_repo_relative", align_repo),
            ("controller_path", CONTROLLER_PATH),
            ("controller_sha256", sha256_hex(worker_raw)),
            ("supervisor_identity", IMAGE_KEY_ID),
            ("supervisor_version", SUPERVISOR_VERSION),
            ("supervisor_key_id", RUN_KEY_ID),
            ("supervisor_key_sha256", sha256_hex(run_public_key)),
        ]
    )


def _boundary_dispatch(
    *,
    project_fd: int,
    image_fd: int,
    manifest_fd: int,
    dispatcher_fd: int,
    align_fd: int,
    align_repo_absolute: str,
    align_repo_relative: str,
) -> tuple[int | None, bytes, bytes, bool]:
    """Run one retained boundary dispatcher with bounded stream capture."""

    if (project_fd, image_fd, manifest_fd, dispatcher_fd, align_fd) != (
        4,
        6,
        8,
        14,
        18,
    ):
        raise OSError(errno.EINVAL, "boundary descriptor vector is not fixed")
    stdout_read, stdout_write = os.pipe2(os.O_CLOEXEC)
    stderr_read, stderr_write = os.pipe2(os.O_CLOEXEC)
    child_pid = -1
    child_status: int | None = None
    timed_out = False
    overflow = False
    streams = selectors.DefaultSelector()
    captures = {stdout_read: bytearray(), stderr_read: bytearray()}

    def waitpid_retry(pid: int, options: int) -> tuple[int, int]:
        while True:
            try:
                return os.waitpid(pid, options)
            except InterruptedError:
                continue

    try:
        child_pid = os.fork()
        if child_pid == 0:
            try:
                os.close(stdout_read)
                os.close(stderr_read)
                os.dup2(stdout_write, 1, inheritable=True)
                os.dup2(stderr_write, 2, inheritable=True)
                os.set_inheritable(4, True)
                os.set_inheritable(6, True)
                os.set_inheritable(8, True)
                os.set_inheritable(14, True)
                os.set_inheritable(18, True)
                if stdout_write != 1:
                    os.close(stdout_write)
                if stderr_write != 2:
                    os.close(stderr_write)
                os.chdir("/proc/self/fd/4")
                _close_descriptors_except({0, 1, 2, 4, 6, 8, 14, 18})
                _execveat(
                    14,
                    [
                        "request6-adoption-boundary-entrypoint",
                        "--mode",
                        "ordinary-adoption-boundary",
                        "--project-root-fd",
                        "4",
                        "--image-attestation-fd",
                        "6",
                        "--manifest-fd",
                        "8",
                        "--align-repo-root-fd",
                        "18",
                        "--align-repo-absolute",
                        align_repo_absolute,
                        "--align-repo-relative",
                        align_repo_relative,
                    ],
                    CHILD_ENVIRONMENT,
                )
            except BaseException:
                os._exit(127)

        os.close(stdout_write)
        os.close(stderr_write)
        stdout_write = -1
        stderr_write = -1
        for descriptor in (stdout_read, stderr_read):
            os.set_blocking(descriptor, False)
            streams.register(descriptor, selectors.EVENT_READ)
        deadline = time.monotonic() + BOUNDARY_TIMEOUT_SECONDS
        while streams.get_map() or child_status is None:
            if child_status is None:
                try:
                    waited, status = waitpid_retry(child_pid, os.WNOHANG)
                except OSError:
                    child_status = -1
                    break
                if waited == child_pid:
                    child_status = status
                    child_pid = -1
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                break
            events = streams.select(remaining)
            for event, _ in events:
                descriptor = event.fd
                while True:
                    try:
                        block = os.read(descriptor, 65_536)
                    except BlockingIOError:
                        break
                    except OSError:
                        timed_out = True
                        break
                    if not block:
                        streams.unregister(descriptor)
                        os.close(descriptor)
                        break
                    captures[descriptor].extend(block)
                    if len(captures[descriptor]) > CONTROL_STREAM_LIMIT:
                        overflow = True
                        break
                if timed_out or overflow:
                    break
            if timed_out or overflow:
                break
        if child_pid > 0:
            try:
                os.kill(child_pid, signal.SIGKILL)
            except OSError:
                pass
            try:
                _, child_status = waitpid_retry(child_pid, 0)
            except OSError:
                child_status = -1
            child_pid = -1
        if timed_out or overflow:
            return child_status, bytes(captures[stdout_read]), bytes(captures[stderr_read]), False
        drain_deadline = deadline
        while streams.get_map():
            if time.monotonic() >= drain_deadline:
                timed_out = True
                break
            events = streams.select(0.1)
            if not events:
                timed_out = True
                break
            for event, _ in events:
                descriptor = event.fd
                try:
                    block = os.read(descriptor, 65_536)
                except (BlockingIOError, OSError):
                    timed_out = True
                    break
                if not block:
                    streams.unregister(descriptor)
                    os.close(descriptor)
                    continue
                captures[descriptor].extend(block)
                if len(captures[descriptor]) > CONTROL_STREAM_LIMIT:
                    overflow = True
                    break
            if timed_out or overflow:
                break
        valid = (
            not timed_out
            and not overflow
            and child_status is not None
            and os.WIFEXITED(child_status)
        )
        return child_status, bytes(captures[stdout_read]), bytes(captures[stderr_read]), valid
    finally:
        if child_pid > 0:
            try:
                os.kill(child_pid, signal.SIGKILL)
            except OSError:
                pass
            try:
                waitpid_retry(child_pid, 0)
            except OSError:
                pass
        try:
            streams.close()
        except OSError:
            pass
        for descriptor in (stdout_read, stdout_write, stderr_read, stderr_write):
            if descriptor >= 0:
                try:
                    os.close(descriptor)
                except OSError:
                    pass


def _write_exact(fd: int, raw: bytes) -> None:
    view = memoryview(raw)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise OSError(errno.EIO, "short boundary output")
        view = view[written:]


def _boundary_supervise(
    *, align_repo_absolute: str, self_fd: int, paths: ProfilePaths
) -> int:
    image_fd = -1
    manifest_fd = -1
    project_fd = -1
    align_fd = -1
    dispatcher_fd = -1
    try:
        try:
            attestation_fd, attestation_raw = _open_regular(
                paths.image_attestation,
                limit=MAX_ATTESTATION_BYTES,
                exact_mode=0o444,
                exact_owner=paths.image_owner,
            )
            os.close(attestation_fd)
            image_fd = _sealed_memfd("align-llm-image", attestation_raw, 6)
            manifest_source_fd, manifest_raw = _open_regular(
                paths.manifest,
                limit=MAX_MANIFEST_BYTES,
                exact_mode=0o444,
                exact_owner=paths.image_owner,
            )
            os.close(manifest_source_fd)
            manifest_fd = _sealed_memfd("align-llm-manifest", manifest_raw, 8)
        except ControlError as error:
            raise ControlError("TRUST", "supervisor", "boundary image input unavailable") from error

        try:
            supervisor_raw = _regular_snapshot(
                self_fd,
                limit=MAX_WORKER_BYTES,
                exact_mode=0o755,
                exact_owner=paths.image_owner,
            )
            image_envelope = _read_sealed(image_fd, limit=MAX_ATTESTATION_BYTES)
            _, _, _, verified_manifest_raw = _verify_image_envelope(
                image_envelope,
                paths=paths,
                supervisor_raw=supervisor_raw,
            )
        except ControlError as error:
            raise ControlError("TRUST", "supervisor", "boundary image verification failed") from error
        if verified_manifest_raw != manifest_raw:
            raise ControlError("TRUST", "supervisor", "boundary manifest snapshot changed")
        manifest = _load_boundary_manifest(manifest_raw)
        dispatcher_fd, _, _ = _runtime_file_binding(
            manifest, BOUNDARY_DISPATCHER_PATH, owner=paths.image_owner
        )
        os.dup2(dispatcher_fd, 14, inheritable=True)
        if dispatcher_fd != 14:
            os.close(dispatcher_fd)
            dispatcher_fd = 14

        try:
            project_fd = os.open(
                ".", os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
            )
            os.dup2(project_fd, 4, inheritable=True)
            if project_fd != 4:
                os.close(project_fd)
            project_fd = 4
        except OSError as error:
            raise ControlError("TRUST", "supervisor", "project root cannot be retained") from error
        normalized_absolute = _normalize_absolute(align_repo_absolute)
        relative = _canonical_relative_from_absolute(normalized_absolute)
        align_fd = _open_absolute_directory(normalized_absolute, 18)
        try:
            status, stdout, stderr, valid = _boundary_dispatch(
                project_fd=project_fd,
                image_fd=image_fd,
                manifest_fd=manifest_fd,
                dispatcher_fd=dispatcher_fd,
                align_fd=align_fd,
                align_repo_absolute=normalized_absolute,
                align_repo_relative=relative,
            )
        except (OSError, ValueError, selectors.SelectorError) as error:
            raise ControlError("TRUST", "supervisor", "boundary child launch failed") from error
        if (
            not valid
            or status is None
            or not os.WIFEXITED(status)
            or os.WEXITSTATUS(status) != 1
            or stdout
            or stderr != b"json-scan adoption: ERROR revision\n"
        ):
            raise ControlError("TRUST", "supervisor", "boundary child result is not canonical")
        _write_exact(2, stderr)
        return 1
    finally:
        for descriptor in (4, 6, 8, 14, 18):
            try:
                os.close(descriptor)
            except OSError:
                pass


def _waitpid_retry(pid: int, options: int) -> tuple[int, int]:
    while True:
        try:
            return os.waitpid(pid, options)
        except InterruptedError:
            continue


def _send_packet(channel: socket.socket, payload: bytes) -> None:
    if channel.send(payload) != len(payload):
        raise OSError(errno.EIO, "short supervisor channel packet")


def _recv_packet(channel: socket.socket, limit: int) -> bytes:
    payload, _, flags, _ = channel.recvmsg(limit, 0)
    if flags & socket.MSG_TRUNC:
        raise OSError(errno.EMSGSIZE, "supervisor channel packet is too large")
    return payload


def _ordinary_supervise(
    *, align_repo_absolute: str, self_fd: int, paths: ProfilePaths
) -> int:
    """Admit one ordinary Request 6 dispatcher through the retained image path."""

    image_fd = -1
    manifest_fd = -1
    project_fd = -1
    align_fd = -1
    dispatcher_fd = -1
    nonce_fd = -1
    parent_channel: socket.socket | None = None
    child_channel: socket.socket | None = None
    child_pid = -1
    try:
        try:
            attestation_fd, attestation_raw = _open_regular(
                paths.image_attestation,
                limit=MAX_ATTESTATION_BYTES,
                exact_mode=0o444,
                exact_owner=paths.image_owner,
            )
            os.close(attestation_fd)
            image_fd = _sealed_memfd("align-llm-image", attestation_raw, 6)
            manifest_source_fd, manifest_raw = _open_regular(
                paths.manifest,
                limit=MAX_MANIFEST_BYTES,
                exact_mode=0o444,
                exact_owner=paths.image_owner,
            )
            os.close(manifest_source_fd)
            manifest_fd = _sealed_memfd("align-llm-manifest", manifest_raw, 8)
            supervisor_raw = _regular_snapshot(
                self_fd,
                limit=MAX_WORKER_BYTES,
                exact_mode=0o755,
                exact_owner=paths.image_owner,
            )
            image_envelope = _read_sealed(
                image_fd, limit=MAX_ATTESTATION_BYTES, expected_name="align-llm-image"
            )
            _, _, _, verified_manifest_raw = _verify_image_envelope(
                image_envelope, paths=paths, supervisor_raw=supervisor_raw
            )
            if verified_manifest_raw != manifest_raw:
                raise ControlError("TRUST", "supervisor", "ordinary manifest snapshot changed")
            manifest = validate_manifest_bytes(manifest_raw)
        except (ControlError, WireError) as error:
            raise ControlError("TRUST", "supervisor", "ordinary image input unavailable") from error

        dispatcher_fd, _, _ = _runtime_file_binding(
            manifest, DISPATCHER_PATH, owner=paths.image_owner
        )
        os.dup2(dispatcher_fd, 14, inheritable=True)
        if dispatcher_fd != 14:
            os.close(dispatcher_fd)
        dispatcher_fd = 14

        project_fd = os.open(
            ".", os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        )
        os.dup2(project_fd, 4, inheritable=True)
        if project_fd != 4:
            os.close(project_fd)
        project_fd = 4

        align_repo_absolute = _normalize_absolute(align_repo_absolute)
        align_repo_relative = _canonical_relative_from_absolute(align_repo_absolute)
        align_fd = _open_absolute_directory(align_repo_absolute, 18)
        nonce = os.getrandom(ORDINARY_NONCE_BYTES, 0)
        if len(nonce) != ORDINARY_NONCE_BYTES:
            raise ControlError("TRUST", "supervisor", "ordinary nonce has the wrong size")
        nonce_fd = _sealed_memfd(
            "align-llm-ordinary-adoption-nonce", nonce, 15
        )
        parent_channel, child_channel = socket.socketpair(
            socket.AF_UNIX, socket.SOCK_SEQPACKET | socket.SOCK_CLOEXEC
        )

        child_pid = os.fork()
        if child_pid == 0:
            try:
                if parent_channel is None or child_channel is None:
                    raise OSError(errno.EBADF, "ordinary channel endpoints are unavailable")
                parent_channel.close()
                parent_channel = None
                os.dup2(child_channel.fileno(), 16, inheritable=True)
                child_channel.close()
                child_channel = None
                for source, target in (
                    (project_fd, 4),
                    (image_fd, 6),
                    (manifest_fd, 8),
                    (nonce_fd, 15),
                    (align_fd, 18),
                ):
                    os.dup2(source, target, inheritable=True)
                os.chdir("/proc/self/fd/4")
                _close_descriptors_except({0, 1, 2, 4, 6, 8, 14, 15, 16, 18})
                _execveat(
                    14,
                    [
                        "request6-adoption-entrypoint",
                        "--mode",
                        "ordinary-adoption",
                        "--project-root-fd",
                        "4",
                        "--image-attestation-fd",
                        "6",
                        "--manifest-fd",
                        "8",
                        "--align-repo-root-fd",
                        "18",
                        "--align-repo-absolute",
                        align_repo_absolute,
                        "--align-repo-relative",
                        align_repo_relative,
                        "--invocation-nonce-fd",
                        "15",
                        "--supervisor-channel-fd",
                        "16",
                    ],
                    ORDINARY_ENVIRONMENT,
                )
            except BaseException:
                try:
                    os.write(2, b"fresh compiler: ERROR TRUST supervisor\n")
                except OSError:
                    pass
            os._exit(1)

        if parent_channel is None or child_channel is None:
            raise ControlError("TRUST", "supervisor", "ordinary channel endpoints are unavailable")
        child_channel.close()
        child_channel = None
        admission_deadline = time.monotonic() + WORKER_INVOCATION_TIMEOUT
        parent_channel.settimeout(max(0.0, admission_deadline - time.monotonic()))
        ticket = os.getrandom(ORDINARY_TICKET_BYTES, 0)
        _send_packet(parent_channel, ticket)
        capsule_digest = b""
        try:
            capsule_digest = _recv_packet(parent_channel, ORDINARY_TICKET_BYTES)
        except (socket.timeout, OSError):
            pass
        if len(capsule_digest) == ORDINARY_TICKET_BYTES:
            proof = hashlib.sha256(
                b"align-llm/ordinary-adoption/worker-admission/v2\0"
                + hashlib.sha256(ticket).digest()
                + nonce
                + capsule_digest
            ).digest()
            try:
                _send_packet(parent_channel, proof)
            except OSError:
                pass

        deadline = admission_deadline
        status: int | None = None
        timed_out = False
        while status is None:
            waited, observed = _waitpid_retry(child_pid, os.WNOHANG)
            if waited == child_pid:
                status = observed
                child_pid = -1
                break
            if time.monotonic() >= deadline:
                timed_out = True
                break
            time.sleep(0.01)
        if timed_out:
            try:
                os.kill(child_pid, signal.SIGKILL)
            except OSError:
                pass
            _, status = _waitpid_retry(child_pid, 0)
            child_pid = -1
            _write_exact(2, b"fresh compiler: ERROR TRUST supervisor\n")
            return 1
        if status is None:
            raise ControlError("TRUST", "supervisor", "ordinary child status is unavailable")
        if os.WIFEXITED(status):
            code = os.WEXITSTATUS(status)
            if code == 0:
                return 0
            if 1 <= code <= 7:
                return 1
        _write_exact(2, b"fresh compiler: ERROR TRUST supervisor\n")
        return 1
    except (ControlError, OSError, WireError) as error:
        if child_pid > 0:
            try:
                os.kill(child_pid, signal.SIGKILL)
            except OSError:
                pass
            try:
                _waitpid_retry(child_pid, 0)
            except OSError:
                pass
            child_pid = -1
        if isinstance(error, ControlError):
            raise
        raise ControlError("TRUST", "supervisor", "ordinary dispatch failed") from error
    finally:
        for channel in (parent_channel, child_channel):
            if channel is not None:
                try:
                    channel.close()
                except OSError:
                    pass
        for descriptor in (4, 6, 8, 14, 15, 18):
            try:
                os.close(descriptor)
            except OSError:
                pass


def supervise(
    arguments: Sequence[str],
    *,
    self_fd: int,
    image_fd: int | None = None,
    paths: ProfilePaths = ProfilePaths(),
) -> int | None:
    mode = _mode_from_arguments(arguments)
    align_repo = _reject_environment(os.environ, mode=mode)
    if mode == "ordinary-adoption-boundary":
        return _boundary_supervise(
            align_repo_absolute=align_repo,
            self_fd=self_fd,
            paths=paths,
        )
    if mode == "ordinary-adoption":
        return _ordinary_supervise(
            align_repo_absolute=align_repo,
            self_fd=self_fd,
            paths=paths,
        )
    if image_fd is None:
        try:
            attestation_fd, attestation_raw = _open_regular(
                paths.image_attestation,
                limit=MAX_ATTESTATION_BYTES,
                exact_mode=0o444,
                exact_owner=paths.image_owner,
            )
            os.close(attestation_fd)
            image_fd = _sealed_memfd("align-llm-image", attestation_raw, 6)
        except ControlError as error:
            raise ControlError("TRUST", "supervisor", "image attestation unavailable") from error
    try:
        supervisor_raw = _regular_snapshot(
            self_fd,
            limit=MAX_WORKER_BYTES,
            exact_mode=0o755,
            exact_owner=paths.image_owner,
        )
    except ControlError as error:
        raise ControlError("TRUST", "supervisor", "supervisor identity mismatch") from error
    image_envelope = _read_sealed(image_fd, limit=MAX_ATTESTATION_BYTES)
    _, _, _, manifest_raw = _verify_image_envelope(
        image_envelope, paths=paths, supervisor_raw=supervisor_raw
    )

    project_path = paths.self_test_project if mode == "self-test" else "."
    try:
        project_fd = os.open(
            project_path, os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        )
    except OSError as error:
        raise ControlError("SOURCE", "project-source", "cannot retain project root") from error
    object_format, head = _git_identity(project_fd, paths.git)
    try:
        worker_raw = _worker_snapshot(
            project_fd,
            owner=paths.image_owner if mode == "self-test" else os.geteuid(),
        )
    except ControlError as error:
        raise ControlError("TRUST", "supervisor", "worker snapshot rejected") from error
    run_owner = os.geteuid() if paths.run_owner is None else paths.run_owner
    try:
        run_seed = _read_key(paths.run_signing_seed, private=True, owner=run_owner)
        installed_run_key = _read_key(
            paths.run_public_key, private=False, owner=paths.image_owner
        )
    except ControlError as error:
        raise ControlError("TRUST", "supervisor", "run signer unavailable") from error
    run_public_key = ed25519_public_key(run_seed)
    if run_public_key != installed_run_key:
        raise ControlError("TRUST", "supervisor", "run signing key does not match policy")
    predicate = _invocation_predicate(
        image_envelope=image_envelope,
        manifest_raw=manifest_raw,
        object_format=object_format,
        head=head,
        align_repo=align_repo,
        worker_raw=worker_raw,
        run_public_key=run_public_key,
    )
    run_envelope = signed_envelope(
        predicate,
        payload_type=INVOCATION_PREDICATE_TYPE,
        key_id=RUN_KEY_ID,
        seed=run_seed,
    )
    os.dup2(project_fd, 4, inheritable=True)
    if project_fd != 4:
        os.close(project_fd)
    _sealed_memfd("align-llm-run", run_envelope, 5)
    if image_fd != 6:
        os.dup2(image_fd, 6, inheritable=True)
    os.set_inheritable(6, True)
    os.chdir("/proc/self/fd/4")
    _close_descriptors_except({0, 1, 2, 4, 5, 6})
    os.execve(paths.bootstrap, [paths.bootstrap, "--mode", mode], CHILD_ENVIRONMENT)


def _bootstrap_verify(
    *, paths: ProfilePaths, self_fd: int
) -> tuple[bytes, bytes, bytes, Mapping[str, object]]:
    image_envelope = _read_sealed(6, limit=MAX_ATTESTATION_BYTES)
    run_envelope = _read_sealed(5, limit=MAX_ATTESTATION_BYTES)
    try:
        image_key = _read_key(
            paths.image_public_key, private=False, owner=paths.image_owner
        )
        run_key = _read_key(paths.run_public_key, private=False, owner=paths.image_owner)
    except ControlError as error:
        raise ControlError("TRUST", "supervisor", "bootstrap verifier unavailable") from error
    try:
        image = verify_envelope(
            image_envelope,
            expected_payload_type=IMAGE_PREDICATE_TYPE,
            expected_key_id=IMAGE_KEY_ID,
            public_key=image_key,
            predicate_validator=validate_image_predicate,
        )
        run = verify_envelope(
            run_envelope,
            expected_payload_type=INVOCATION_PREDICATE_TYPE,
            expected_key_id=RUN_KEY_ID,
            public_key=run_key,
            predicate_validator=validate_invocation_predicate,
        )
    except WireError as error:
        raise ControlError("TRUST", "supervisor", "bootstrap attestation rejection") from error
    try:
        bootstrap_raw = _regular_snapshot(
            self_fd,
            limit=MAX_WORKER_BYTES,
            exact_mode=0o755,
            exact_owner=paths.image_owner,
        )
    except ControlError as error:
        raise ControlError("TRUST", "supervisor", "bootstrap identity mismatch") from error
    if image.predicate["bootstrap_path"] != BOOTSTRAP_PATH or image.predicate[
        "bootstrap_sha256"
    ] != sha256_hex(bootstrap_raw):
        raise ControlError("TRUST", "supervisor", "bootstrap identity mismatch")
    predicate = run.predicate
    if predicate["image_attestation_sha256"] != sha256_hex(image_envelope):
        raise ControlError("TRUST", "supervisor", "run/image binding mismatch")
    try:
        manifest_fd, manifest_raw = _open_regular(
            paths.manifest,
            limit=MAX_MANIFEST_BYTES,
            exact_mode=0o444,
            exact_owner=paths.image_owner,
        )
    except ControlError as error:
        raise ControlError("TRUST", "manifest", "manifest snapshot rejected") from error
    os.close(manifest_fd)
    if image.predicate["manifest_sha256"] != sha256_hex(manifest_raw):
        raise ControlError("TRUST", "manifest", "manifest digest mismatch")
    if predicate["manifest_sha256"] != sha256_hex(manifest_raw):
        raise ControlError("TRUST", "manifest", "run/manifest binding mismatch")
    try:
        validate_manifest_bytes(manifest_raw)
    except WireError as error:
        raise ControlError("TRUST", "manifest", "manifest schema rejection") from error
    return image_envelope, run_envelope, manifest_raw, predicate


def _version_tuple(raw: bytes, pattern: bytes) -> tuple[int, ...]:
    match = re.search(pattern, raw)
    if match is None:
        raise ControlError("PLATFORM", "platform", "version probe is not recognized")
    return tuple(int(part) for part in match.group(1).split(b"."))


def _runtime_tree(path: str, *, root: bool = True) -> OrderedDict[str, object]:
    try:
        value = os.stat(path, follow_symlinks=False)
    except OSError as error:
        raise ControlError("TOOL", "tools", "runtime binding is unavailable") from error
    if stat.S_ISLNK(value.st_mode) or not (
        stat.S_ISREG(value.st_mode) or stat.S_ISDIR(value.st_mode)
    ):
        raise ControlError("TOOL", "tools", "runtime binding type is invalid")
    if value.st_uid != 0:
        raise ControlError("TOOL", "tools", "runtime binding owner is invalid")
    fields: list[tuple[str, object]] = []
    if not root:
        fields.append(("name", os.path.basename(path)))
    kind = "dir" if stat.S_ISDIR(value.st_mode) else "file"
    mode = stat.S_IMODE(value.st_mode)
    staged = "0700" if kind == "dir" else ("0555" if mode & 0o111 else "0444")
    fields.extend(
        [
            ("kind", kind),
            ("mode", f"{mode:04o}"),
            ("staged_mode", staged),
            ("size", 0 if kind == "dir" else value.st_size),
            ("sha256", "0" * 64),
            ("entries", []),
        ]
    )
    node: OrderedDict[str, object] = OrderedDict(fields)
    if kind == "file":
        try:
            descriptor = os.open(
                path,
                os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC,
            )
        except OSError as error:
            raise ControlError("TOOL", "tools", "runtime file open rejected") from error
        try:
            before = _identity(descriptor)
            if (
                not stat.S_ISREG(before.mode)
                or before.owner != 0
                or before.size != value.st_size
                or before.size > 536_870_912
            ):
                raise ControlError("TOOL", "tools", "runtime file identity rejected")
            deadline = time.monotonic() + SNAPSHOT_DEADLINE_SECONDS
            remaining = before.size
            hasher = hashlib.sha256()
            while remaining:
                if time.monotonic() > deadline:
                    raise ControlError("TOOL", "tools", "runtime file deadline exceeded")
                block = os.read(descriptor, min(1_048_576, remaining))
                if not block:
                    raise ControlError("TOOL", "tools", "runtime file was short")
                hasher.update(block)
                remaining -= len(block)
            if os.read(descriptor, 1):
                raise ControlError("TOOL", "tools", "runtime file grew")
            if not _same_identity(before, _identity(descriptor)):
                raise ControlError("TOOL", "tools", "runtime file changed")
        finally:
            os.close(descriptor)
        node["sha256"] = hasher.hexdigest()
        return node
    try:
        names = sorted(os.listdir(path), key=os.fsencode)
    except OSError as error:
        raise ControlError("TOOL", "tools", "runtime directory read rejected") from error
    entries = [_runtime_tree(os.path.join(path, name), root=False) for name in names]
    try:
        after = os.stat(path, follow_symlinks=False)
    except OSError as error:
        raise ControlError("TOOL", "tools", "runtime directory changed") from error
    if (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_uid,
    ) != (after.st_dev, after.st_ino, after.st_mode, after.st_uid):
        raise ControlError("TOOL", "tools", "runtime directory changed")
    node["entries"] = entries
    node["sha256"] = structural_digest(node)
    return node


def _run_retained_tool(
    descriptor: int,
    arguments: Sequence[str],
    *,
    timeout: int = 10,
    pass_fds: Sequence[int] = (),
) -> subprocess.CompletedProcess[bytes]:
    return _run_controlled_child(
        list(arguments),
        executable=f"/proc/self/fd/{descriptor}",
        environment={"PATH": "/usr/bin:/bin", "LC_ALL": "C", "HOME": "/nonexistent"},
        pass_fds=tuple(dict.fromkeys((descriptor, *pass_fds))),
        timeout=timeout,
    )


def _namespace_self_test(bwrap_fd: int, bwrap_argv0: str) -> None:
    with tempfile.TemporaryDirectory(prefix="align-llm-fresh-bwrap-", dir="/dev/shm") as name:
        lower = os.path.join(name, "lower")
        upper = os.path.join(name, "upper")
        work = os.path.join(name, "work")
        os.mkdir(lower, 0o700)
        os.mkdir(upper, 0o700)
        os.mkdir(work, 0o700)
        writable = os.path.join(name, "writable")
        os.mkdir(writable, 0o700)
        os.mkdir(os.path.join(lower, "tmp"), 0o700)
        marker = os.open(
            os.path.join(lower, "lower-marker"),
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
            0o600,
        )
        os.close(marker)
        opened_mount_fds: list[int] = []
        try:
            for path in (lower, upper, work, "/opt/align-llm/tool-bin", writable):
                opened_mount_fds.append(
                    os.open(path, os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC)
                )
        except Exception:
            for descriptor in reversed(opened_mount_fds):
                os.close(descriptor)
            raise
        mount_fds = tuple(opened_mount_fds)
        arguments = [
            bwrap_argv0,
            "--unshare-user",
            "--unshare-pid",
            "--unshare-net",
            "--unshare-ipc",
            "--unshare-uts",
            "--die-with-parent",
            "--new-session",
            "--uid",
            "0",
            "--gid",
            "0",
            "--cap-add",
            "CAP_SYS_ADMIN",
            "--cap-add",
            "CAP_SETFCAP",
            "--tmpfs",
            "/",
            "--dir",
            "/target",
            "--dir",
            "/writable",
            "--dir",
            "/fd-hold",
            "--dir",
            "/fd-hold/lower",
            "--dir",
            "/fd-hold/upper",
            "--dir",
            "/fd-hold/work",
            "--bind-fd",
            str(mount_fds[4]),
            "/writable",
            "--overlay-src",
            f"/proc/self/fd/{mount_fds[0]}",
            "--overlay",
            f"/proc/self/fd/{mount_fds[1]}",
            f"/proc/self/fd/{mount_fds[2]}",
            "/target",
            "--ro-bind-fd",
            str(mount_fds[0]),
            "/fd-hold/lower",
            "--ro-bind-fd",
            str(mount_fds[1]),
            "/fd-hold/upper",
            "--ro-bind-fd",
            str(mount_fds[2]),
            "/fd-hold/work",
            "--tmpfs",
            "/fd-hold",
            "--tmpfs",
            "/target/tmp",
            "--ro-bind-fd",
            str(mount_fds[3]),
            "/tools",
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--",
            "/tools/mount-guard",
            "--no-symlink-follow",
            "/target/tmp",
            "--",
            "/tools/mount-guard",
            "--namespace-self-test",
        ]
        try:
            result = _run_retained_tool(
                bwrap_fd, arguments, timeout=20, pass_fds=mount_fds
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ControlError("TRUST", "bwrap", "bubblewrap namespace probe failed") from error
        finally:
            for descriptor in reversed(mount_fds):
                os.close(descriptor)
        if result.returncode != 0 or result.stdout or result.stderr:
            raise ControlError("TRUST", "bwrap", "bubblewrap namespace probe rejected")


def _platform_self_test(manifest_raw: bytes) -> None:
    if os.uname().sysname != "Linux" or os.uname().machine != "x86_64":
        raise ControlError("PLATFORM", "platform", "platform is not Linux x86_64")
    if _version_tuple(os.uname().release.encode("ascii"), rb"^(\d+\.\d+)") < (6, 8):
        raise ControlError("PLATFORM", "platform", "kernel is older than 6.8")
    if sys.version_info[:2] < (3, 12):
        raise ControlError("PLATFORM", "platform", "Python is older than 3.12")
    try:
        manifest = validate_manifest_bytes(manifest_raw)
    except WireError as error:
        raise ControlError("TRUST", "manifest", "manifest is invalid") from error
    for binding in manifest["runtime_bindings"]:
        tree = _runtime_tree(binding["source"])
        if tree != binding["manifest"] or serialized_digest(tree) != binding["manifest_sha256"]:
            raise ControlError("TOOL", "tools", "runtime binding digest mismatch")
    probe_output: dict[str, bytes] = {}
    bwrap_fd = -1
    bwrap_argv0 = ""
    for tool in manifest["tools"]:
        path = tool["path"]
        try:
            fd, raw = _open_regular(
                path, limit=536_870_912, exact_mode=0o755, exact_owner=0
            )
        except ControlError as error:
            raise ControlError("TOOL", "tools", "tool snapshot rejected") from error
        if sha256_hex(raw) != tool["sha256"]:
            os.close(fd)
            raise ControlError("TOOL", "tools", f"tool digest mismatch: {tool['name']}")
        try:
            result = _run_retained_tool(fd, tool["argv"])
        except (OSError, subprocess.TimeoutExpired) as error:
            os.close(fd)
            raise ControlError("TOOL", "tools", f"tool probe failed: {tool['name']}") from error
        if (
            result.returncode != 0
            or result.stdout.hex() != tool["stdout"]
            or result.stderr.hex() != tool["stderr"]
        ):
            os.close(fd)
            raise ControlError("TOOL", "tools", f"tool probe changed: {tool['name']}")
        probe_output[tool["name"]] = result.stdout + result.stderr
        if tool["name"] == "bwrap":
            bwrap_fd = fd
            bwrap_argv0 = tool["argv"][0]
        else:
            os.close(fd)
    if bwrap_fd < 0:
        raise ControlError("TRUST", "bwrap", "bubblewrap descriptor is missing")
    try:
        if _version_tuple(probe_output["git"], rb"git version (\d+\.\d+(?:\.\d+)?)") < (
            2,
            45,
        ):
            raise ControlError("PLATFORM", "platform", "Git is older than 2.45")
        for name in ("cargo", "rustc"):
            if _version_tuple(
                probe_output[name], rb"(?:cargo|rustc) (\d+\.\d+\.\d+)"
            ) != (1, 96, 0):
                raise ControlError("PLATFORM", "platform", f"{name} is not 1.96.0")
        if _version_tuple(
            probe_output["make"], rb"GNU Make (\d+\.\d+(?:\.\d+)?)"
        ) < (4, 3):
            raise ControlError("PLATFORM", "platform", "GNU Make is older than 4.3")
        if _version_tuple(probe_output["clang"], rb"clang version (\d+)")[:1] != (22,):
            raise ControlError("PLATFORM", "platform", "Clang is not major 22")
        try:
            help_result = _run_retained_tool(bwrap_fd, [bwrap_argv0, "--help"])
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ControlError("TRUST", "bwrap", "bubblewrap probe failed") from error
        if help_result.returncode != 0 or not all(
            option in help_result.stdout + help_result.stderr
            for option in (
                b"--overlay-src",
                b"--overlay",
                b"--bind-fd",
                b"--ro-bind-fd",
            )
        ):
            raise ControlError("TRUST", "bwrap", "bubblewrap mount support is missing")
        _namespace_self_test(bwrap_fd, bwrap_argv0)
    finally:
        os.close(bwrap_fd)

    temporary = f"/tmp/align-llm-fresh-exec-{os.getpid()}"
    source_fd = -1
    target_fd = -1
    try:
        source_fd = os.open("/usr/bin/true", os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        target_fd = os.open(
            temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC, 0o700
        )
        while True:
            block = os.read(source_fd, 65_536)
            if not block:
                break
            view = memoryview(block)
            while view:
                count = os.write(target_fd, view)
                if count <= 0:
                    raise OSError(errno.EIO, "short /tmp probe write")
                view = view[count:]
        os.close(source_fd)
        source_fd = -1
        os.close(target_fd)
        target_fd = -1
        result = _run_controlled_child(
            [temporary],
            environment={},
            timeout=5,
        )
        if result.returncode != 0:
            raise ControlError("PLATFORM", "platform", "/tmp is not executable")
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ControlError("PLATFORM", "platform", "/tmp execution probe failed") from error
    finally:
        if source_fd >= 0:
            os.close(source_fd)
        if target_fd >= 0:
            os.close(target_fd)
        try:
            os.unlink(temporary)
        except OSError:
            pass

    runtime_user = f"/run/user/{os.geteuid()}"
    runtime_profile = os.path.join(runtime_user, "align-llm-fresh")
    try:
        for path in (runtime_user, runtime_profile, os.path.join(runtime_profile, "roots")):
            value = os.stat(path, follow_symlinks=False)
            if (
                not stat.S_ISDIR(value.st_mode)
                or value.st_uid != os.geteuid()
                or stat.S_IMODE(value.st_mode) != 0o700
            ):
                raise OSError(errno.EPERM, "runtime directory identity mismatch")
        lock = os.stat(os.path.join(runtime_profile, "lock"), follow_symlinks=False)
        if (
            not stat.S_ISREG(lock.st_mode)
            or lock.st_uid != os.geteuid()
            or lock.st_nlink != 1
            or stat.S_IMODE(lock.st_mode) != 0o600
            or lock.st_size != 0
        ):
            raise OSError(errno.EPERM, "runtime lock identity mismatch")
    except OSError as error:
        raise ControlError("PLATFORM", "platform", "runtime profile is unavailable") from error

    cgroup_parent = f"/sys/fs/cgroup/align-llm-fresh/{os.geteuid()}"
    parent_fd = -1
    leaf_fd = -1
    leaf_name: str | None = None
    leaf_identity: tuple[int, int, int, int, int] | None = None
    try:
        parent_fd = os.open(
            cgroup_parent,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
        )
        parent = os.fstat(parent_fd)
        if (
            not stat.S_ISDIR(parent.st_mode)
            or parent.st_uid != os.geteuid()
            or stat.S_IMODE(parent.st_mode) != 0o700
        ):
            raise OSError(errno.EPERM, "cgroup parent ownership mismatch")
        leaf_name = f"self-test-{os.getpid()}"
        os.mkdir(leaf_name, 0o700, dir_fd=parent_fd)
        leaf_fd = os.open(
            leaf_name,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=parent_fd,
        )
        leaf = os.fstat(leaf_fd)
        leaf_identity = (
            leaf.st_dev,
            leaf.st_ino,
            stat.S_IFMT(leaf.st_mode),
            stat.S_IMODE(leaf.st_mode),
            leaf.st_uid,
        )

        def leaf_matches() -> bool:
            if leaf_identity is None or leaf_name is None:
                return False
            try:
                current = os.stat(leaf_name, dir_fd=parent_fd, follow_symlinks=False)
            except OSError:
                return False
            return (
                (
                    current.st_dev,
                    current.st_ino,
                    stat.S_IFMT(current.st_mode),
                    stat.S_IMODE(current.st_mode),
                    current.st_uid,
                )
                == leaf_identity
            )

        def write_control(name: str, raw: bytes) -> None:
            descriptor = os.open(
                name,
                os.O_WRONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=leaf_fd,
            )
            try:
                if os.write(descriptor, raw) != len(raw):
                    raise OSError(errno.EIO, "short cgroup control write")
            finally:
                os.close(descriptor)

        def read_control(name: str) -> bytes:
            descriptor = os.open(
                name,
                os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=leaf_fd,
            )
            try:
                return os.read(descriptor, 4096)
            finally:
                os.close(descriptor)

        def members(name: str) -> tuple[int, ...]:
            raw = read_control(name)
            values: list[int] = []
            for line in raw.splitlines():
                if not line or not line.isdigit() or int(line) <= 0:
                    raise OSError(errno.EPROTO, "cgroup self-test membership is malformed")
                values.append(int(line))
            if len(set(values)) != len(values):
                raise OSError(errno.EPROTO, "cgroup self-test membership is duplicated")
            return tuple(sorted(values))

        def require_empty() -> None:
            if members("cgroup.procs") or members("cgroup.threads"):
                raise OSError(errno.EBUSY, "cgroup self-test admission is not empty")

        if not leaf_matches():
            raise OSError(errno.ESTALE, "cgroup leaf identity mismatch")
        require_empty()
        write_control("pids.max", b"512\n")
        if read_control("pids.max").strip() != b"512":
            raise OSError(errno.EIO, "cgroup pids.max mismatch")
        require_empty()
        limits = (
            (resource.RLIMIT_NPROC, 512),
            (resource.RLIMIT_NOFILE, 4096),
            (resource.RLIMIT_FSIZE, 536_870_912),
        )

        def admit_limited_child() -> None:
            for kind, limit in limits:
                resource.setrlimit(kind, (limit, limit))
            require_empty()
            write_control("cgroup.procs", b"0\n")
            os.set_inheritable(leaf_fd, False)
            os.setsid()

        child_code = """
import os
import resource
import sys
expected = sys.argv[1]
assert resource.getrlimit(resource.RLIMIT_NPROC) == (512, 512)
assert resource.getrlimit(resource.RLIMIT_NOFILE) == (4096, 4096)
assert resource.getrlimit(resource.RLIMIT_FSIZE) == (536870912, 536870912)
lines = open('/proc/self/cgroup', encoding='ascii').read().splitlines()
assert any(line.startswith('0::') and line.endswith(expected) for line in lines)
os.write(1, b'limited child: PASS\\n')
"""
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-B",
                "-c",
                child_code,
                "/" + cgroup_parent.removeprefix("/sys/fs/cgroup/") + "/" + leaf_name,
            ],
            env={"PATH": "/usr/bin:/bin", "LC_ALL": "C", "HOME": "/nonexistent"},
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            close_fds=True,
            pass_fds=(leaf_fd,),
            preexec_fn=admit_limited_child,
            timeout=10,
            check=False,
        )
        if result.returncode != 0 or result.stdout != b"limited child: PASS\n" or result.stderr:
            raise OSError(errno.EIO, "cgroup/rlimit child rejected")
        if not leaf_matches() or members("cgroup.procs") or members("cgroup.threads"):
            raise OSError(errno.EBUSY, "cgroup child remained attached")
        if leaf_identity is None:
            raise OSError(errno.ESTALE, "cgroup self-test leaf identity is unavailable")
        _control_remove_cgroup_leaf(parent_fd, leaf_fd, leaf_name, leaf_identity)
        leaf_name = None
    except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired) as error:
        raise ControlError("PLATFORM", "platform", "cgroup delegation is unavailable") from error
    finally:
        cleanup_error: OSError | None = None
        if leaf_name is not None and parent_fd >= 0:
            try:
                if not leaf_matches():
                    raise OSError(errno.ESTALE, "cgroup leaf replacement detected")
                if leaf_identity is None:
                    raise OSError(errno.ESTALE, "cgroup self-test leaf identity is unavailable")
                _control_remove_cgroup_leaf(parent_fd, leaf_fd, leaf_name, leaf_identity)
                leaf_name = None
            except OSError as error:
                cleanup_error = error
        for descriptor_name in ("leaf_fd", "parent_fd"):
            descriptor = locals()[descriptor_name]
            if descriptor >= 0:
                try:
                    os.close(descriptor)
                except OSError as error:
                    cleanup_error = cleanup_error or error
        if cleanup_error is not None:
            raise ControlError(
                "PLATFORM",
                "platform",
                "cgroup self-test cleanup failed",
            ) from cleanup_error


def bootstrap(
    mode: str, *, self_fd: int, paths: ProfilePaths = ProfilePaths()
) -> int:
    if mode not in ("ci", "build", "self-test"):
        raise ControlError("ARGUMENT", "input", "bootstrap mode is invalid")
    _, run_envelope, manifest_raw, predicate = _bootstrap_verify(
        paths=paths, self_fd=self_fd
    )
    if mode == "self-test":
        _platform_self_test(manifest_raw)
    try:
        worker_raw = _worker_snapshot(
            4, owner=paths.image_owner if mode == "self-test" else os.geteuid()
        )
    except ControlError as error:
        raise ControlError("TRUST", "supervisor", "worker snapshot rejected") from error
    if predicate["controller_sha256"] != sha256_hex(worker_raw):
        raise ControlError("TRUST", "supervisor", "worker digest mismatch")
    _sealed_memfd("align-llm-worker", worker_raw, 7)
    _sealed_memfd("align-llm-manifest", manifest_raw, 8)
    _sealed_memfd("align-llm-run-snapshot", run_envelope, 9)
    for descriptor in (5, 6):
        try:
            os.close(descriptor)
        except OSError:
            pass
    arguments = [
        paths.python,
        "-I",
        "-B",
        "/proc/self/fd/7",
        "--mode",
        mode,
        "--project-root-fd",
        "4",
        "--image-manifest-fd",
        "8",
        "--run-attestation-fd",
        "9",
    ]
    result = _run_controlled_child(
        arguments,
        environment=WORKER_ENVIRONMENT,
        pass_fds=(4, 7, 8, 9),
        timeout=30 if mode == "self-test" else WORKER_INVOCATION_TIMEOUT,
    )
    expected = {
        "ci": b"fresh compiler and capable checks: PASS\n",
        "build": b"fresh compiler: PASS\n",
        "self-test": b"fresh compiler self-test: PASS\n",
    }[mode]
    if result.returncode != 0 or result.stderr or result.stdout != expected:
        raise ControlError("CHILD", "aggregate", "worker result is not canonical")
    os.write(1, expected)
    return 0


def _emit_error(error: ControlError) -> int:
    if error.category not in PUBLIC_CATEGORIES or error.phase not in PUBLIC_PHASES:
        error = ControlError("INTERNAL", "internal")
    os.write(
        2,
        f"fresh compiler: ERROR {error.category} {error.phase}\n".encode("ascii"),
    )
    return 1


def supervisor_main(arguments: Sequence[str] | None = None) -> int:
    values = list(sys.argv[1:] if arguments is None else arguments)
    if values[:2] != ["--embedded-self-fd", "10"]:
        return _emit_error(ControlError("TRUST", "supervisor", "wrong self descriptor"))
    try:
        result = supervise(values[2:], self_fd=10)
    except ControlError as error:
        return _emit_error(error)
    except Exception:
        return _emit_error(ControlError("INTERNAL", "internal"))
    return 1 if result is None else result


def bootstrap_main(arguments: Sequence[str] | None = None) -> int:
    values = list(sys.argv[1:] if arguments is None else arguments)
    try:
        if len(values) != 4 or values[:3] != ["--embedded-self-fd", "10", "--mode"]:
            raise ControlError("TRUST", "supervisor", "wrong self descriptor")
        return bootstrap(values[3], self_fd=10)
    except ControlError as error:
        return _emit_error(error)
    except Exception:
        return _emit_error(ControlError("INTERNAL", "internal"))


__all__ = [
    "ControlError",
    "ProfilePaths",
    "_mode_from_arguments",
    "_normalize_absolute",
    "_normalize_relative",
    "_reject_environment",
    "_sealed_memfd",
    "_read_sealed",
    "bootstrap_main",
    "supervisor_main",
]
