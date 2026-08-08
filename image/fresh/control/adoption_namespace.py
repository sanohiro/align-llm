#!/usr/bin/env python3
"""PID-1 authority and fixed-row supervisor for ordinary adoption.

The worker owns the bwrap setup edge.  This module owns only the inner
authority verification, the queued admission proof, and the three fixed Make
children once bwrap has transferred the live channel into the private PID
namespace.
"""

from __future__ import annotations

import base64
import ctypes
import hashlib
import json
import os
import selectors
import signal
import socket
import stat
import subprocess
import time
from collections import OrderedDict
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Mapping

from fresh_attestation import (
    RUN_KEY_ID,
    WireError,
    validate_ordinary_adoption_predicate,
    verify_envelope,
)


PHASE_CODES = {
    "input": 1,
    "toolchain": 2,
    "revision": 3,
    "build": 4,
    "fixture": 5,
    "cleanup": 6,
}
CAPSULE_PATH = "/authority/capsule"
WORKER_PATH = "/authority/worker"
NONCE_PATH = "/authority/nonce"
MAX_CAPSULE_BYTES = 1_048_576
MAX_WORKER_BYTES = 4_194_304
MAX_NONCE_BYTES = 32
MAX_STREAM_BYTES = 65_536
ROW_TIMEOUT_SECONDS = 1_800
REVISION_TIMEOUT_SECONDS = 10
FOCUSED_TIMEOUT_SECONDS = 120
HELPER_ENVIRONMENT = {
    "PATH": "/usr/bin:/bin",
    "ALIGN_REPO": "/private-align",
    "CARGO_NET_OFFLINE": "true",
    "HOME": "/nonexistent",
    "LANG": "C",
    "LC_ALL": "C",
    "MAKEFLAGS": "",
    "GNUMAKEFLAGS": "",
    "MAKEOVERRIDES": "",
    "PYTHONDONTWRITEBYTECODE": "1",
    "TMPDIR": "/tmp",
}
RUNTIME_SEARCH_ROOTS = (
    "/runtime/git",
    "/runtime/rust",
    "/runtime/cc-suite",
    "/runtime/bwrap",
    "/usr/lib/x86_64-linux-gnu",
    "/lib/x86_64-linux-gnu",
    "/usr/lib/gcc/x86_64-linux-gnu",
    "/usr/lib/python3.12",
    "/usr/include",
    "/usr/share/git-core",
    "/usr/share/perl5",
    "/lib64",
)


class NamespaceFailure(Exception):
    def __init__(self, phase: str) -> None:
        super().__init__(phase)
        self.phase = phase


def _fail(phase: str) -> int:
    if phase == "unobserved":
        os.write(2, b"json-scan adoption: ERROR unobserved\n")
        return 7
    if phase not in PHASE_CODES:
        phase = "toolchain"
    os.write(2, f"json-scan adoption: ERROR {phase}\n".encode("ascii"))
    return PHASE_CODES[phase]


def _debug(message: str) -> None:
    os.write(2, ("namespace debug: " + message + "\n").encode("ascii", "backslashreplace"))


def _descriptor_set() -> set[int]:
    result: set[int] = set()
    for name in os.listdir("/proc/self/fd"):
        try:
            fd = int(name)
            os.fstat(fd)
        except (OSError, ValueError):
            continue
        result.add(fd)
    return result


def _read_authority(path: str, limit: int) -> bytes:
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError as error:
        raise NamespaceFailure("toolchain") from error
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size < 0 or before.st_size > limit:
            raise NamespaceFailure("toolchain")
        raw = bytearray()
        offset = 0
        while offset < before.st_size:
            block = os.pread(fd, min(65_536, before.st_size - offset), offset)
            if not block:
                raise NamespaceFailure("toolchain")
            raw.extend(block)
            offset += len(block)
        after = os.fstat(fd)
        if (before.st_dev, before.st_ino, before.st_mode, before.st_nlink, before.st_size) != (
            after.st_dev, after.st_ino, after.st_mode, after.st_nlink, after.st_size
        ):
            raise NamespaceFailure("toolchain")
        return bytes(raw)
    except OSError as error:
        raise NamespaceFailure("toolchain") from error
    finally:
        os.close(fd)


def _read_key() -> bytes:
    fd = -1
    try:
        fd = os.open(
            "/usr/local/share/align-llm/run-verifier.pub",
            os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
        )
        value = os.fstat(fd)
        raw = os.pread(fd, 32, 0)
        after = os.fstat(fd)
    except OSError as error:
        raise NamespaceFailure("toolchain") from error
    finally:
        if fd >= 0:
            os.close(fd)
    if (
        not stat.S_ISREG(value.st_mode)
        or value.st_uid != 0
        or value.st_nlink != 1
        or stat.S_IMODE(value.st_mode) != 0o444
        or value.st_size != 32
        or len(raw) != 32
        or (value.st_dev, value.st_ino, value.st_mode, value.st_nlink, value.st_size)
        != (after.st_dev, after.st_ino, after.st_mode, after.st_nlink, after.st_size)
    ):
        raise NamespaceFailure("toolchain")
    return raw


def _read_open_file(fd: int, size: int) -> bytes:
    if size < 0 or size > 536_870_912:
        raise NamespaceFailure("build")
    chunks: list[bytes] = []
    offset = 0
    while offset < size:
        block = os.pread(fd, min(65_536, size - offset), offset)
        if not block:
            raise NamespaceFailure("build")
        chunks.append(block)
        offset += len(block)
    raw = b"".join(chunks)
    if len(raw) != size:
        raise NamespaceFailure("build")
    return raw


def _stat_and_read(path: str, mode: int) -> tuple[os.stat_result, bytes]:
    fd = -1
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        before = os.fstat(fd)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or stat.S_IMODE(before.st_mode) != mode
        ):
            raise NamespaceFailure("build")
        raw = _read_open_file(fd, before.st_size)
        after = os.fstat(fd)
        if (
            before.st_dev,
            before.st_ino,
            before.st_mode,
            before.st_nlink,
            before.st_size,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_mode,
            after.st_nlink,
            after.st_size,
        ):
            raise NamespaceFailure("build")
        return before, raw
    except OSError as error:
        raise NamespaceFailure("build") from error
    finally:
        if fd >= 0:
            os.close(fd)


def _stat_tuple(value: os.stat_result) -> tuple[int, int, int, int, int, int, int, int]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_uid,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _symlink_stays_inside(source_root: Path, source_entry: Path, target: str) -> bool:
    if os.path.isabs(target):
        return False
    components = list(source_entry.relative_to(source_root).parts[:-1])
    for component in target.split("/"):
        if component in ("", "."):
            continue
        if component == "..":
            if not components:
                return False
            components.pop()
        else:
            components.append(component)
    return True


def _copy_tree(source: str, destination: str, *, writable: bool = False) -> None:
    """Copy one already read-only input tree without following source links."""

    source_path = Path(source)
    destination_path = Path(destination)
    try:
        source_value = source_path.lstat()
    except OSError as error:
        raise NamespaceFailure("toolchain") from error
    if not stat.S_ISDIR(source_value.st_mode):
        raise NamespaceFailure("toolchain")
    try:
        destination_value = destination_path.lstat()
    except FileNotFoundError:
        destination_path.mkdir(mode=0o700, parents=False, exist_ok=False)
    except OSError as error:
        raise NamespaceFailure("toolchain") from error
    else:
        if not stat.S_ISDIR(destination_value.st_mode) or any(destination_path.iterdir()):
            raise NamespaceFailure("toolchain")
        destination_path.chmod(0o700)

    def visit(source_directory: Path, destination_directory: Path, depth: int = 0) -> None:
        if depth > 64:
            raise NamespaceFailure("toolchain")
        try:
            directory_before = source_directory.lstat()
        except OSError as error:
            raise NamespaceFailure("toolchain") from error
        if not stat.S_ISDIR(directory_before.st_mode):
            raise NamespaceFailure("toolchain")
        try:
            names = sorted(source_directory.iterdir(), key=lambda item: os.fsencode(item.name))
        except OSError as error:
            raise NamespaceFailure("toolchain") from error
        for source_entry in names:
            destination_entry = destination_directory / source_entry.name
            try:
                value = source_entry.lstat()
            except OSError as error:
                raise NamespaceFailure("toolchain") from error
            if stat.S_ISDIR(value.st_mode):
                destination_entry.mkdir(mode=0o700)
                visit(source_entry, destination_entry, depth + 1)
                destination_entry.chmod(0o700 if writable else 0o555)
            elif stat.S_ISREG(value.st_mode):
                if value.st_nlink != 1 or value.st_size > 536_870_912:
                    raise NamespaceFailure("toolchain")
                source_fd = -1
                try:
                    source_fd = os.open(
                        source_entry,
                        os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC,
                    )
                    opened = os.fstat(source_fd)
                    if _stat_tuple(opened) != _stat_tuple(value):
                        raise NamespaceFailure("toolchain")
                    raw = _read_open_file(source_fd, opened.st_size)
                    after = os.fstat(source_fd)
                    if _stat_tuple(after) != _stat_tuple(opened):
                        raise NamespaceFailure("toolchain")
                    fd = os.open(
                        destination_entry,
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                        0o600,
                    )
                    try:
                        view = memoryview(raw)
                        while view:
                            written = os.write(fd, view)
                            if written <= 0:
                                raise NamespaceFailure("toolchain")
                            view = view[written:]
                    finally:
                        os.close(fd)
                except OSError as error:
                    raise NamespaceFailure("toolchain") from error
                finally:
                    if source_fd >= 0:
                        os.close(source_fd)
                destination_entry.chmod(
                    0o600 if writable else (0o555 if value.st_mode & 0o111 else 0o444)
                )
            elif stat.S_ISLNK(value.st_mode):
                target = ""
                try:
                    target = os.readlink(source_entry)
                    if (
                        not target
                        or os.path.isabs(target)
                        or "\x00" in target
                        or not _symlink_stays_inside(source_path, source_entry, target)
                    ):
                        raise NamespaceFailure("toolchain")
                    after = source_entry.lstat()
                    if _stat_tuple(after) != _stat_tuple(value):
                        raise NamespaceFailure("toolchain")
                    destination_entry.symlink_to(target)
                except OSError as error:
                    raise NamespaceFailure("toolchain") from error
            else:
                raise NamespaceFailure("toolchain")
        try:
            directory_after = source_directory.lstat()
        except OSError as error:
            raise NamespaceFailure("toolchain") from error
        if _stat_tuple(directory_after) != _stat_tuple(directory_before):
            raise NamespaceFailure("toolchain")

    visit(source_path, destination_path)
    try:
        source_after = source_path.lstat()
    except OSError as error:
        raise NamespaceFailure("toolchain") from error
    if _stat_tuple(source_after) != _stat_tuple(source_value):
        raise NamespaceFailure("toolchain")
    destination_path.chmod(0o700 if writable else 0o555)


def _copy_file(source: str, destination: str, mode: int) -> None:
    source_fd = -1
    try:
        value = os.stat(source, follow_symlinks=False)
        if not stat.S_ISREG(value.st_mode) or value.st_nlink != 1 or value.st_size > 536_870_912:
            raise NamespaceFailure("toolchain")
        source_fd = os.open(source, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC)
        opened = os.fstat(source_fd)
        if _stat_tuple(opened) != _stat_tuple(value):
            raise NamespaceFailure("toolchain")
        raw = _read_open_file(source_fd, opened.st_size)
        if _stat_tuple(os.fstat(source_fd)) != _stat_tuple(opened):
            raise NamespaceFailure("toolchain")
        fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, mode)
        try:
            view = memoryview(raw)
            while view:
                written = os.write(fd, view)
                if written <= 0:
                    raise NamespaceFailure("toolchain")
                view = view[written:]
            os.fchmod(fd, mode)
        finally:
            os.close(fd)
    except OSError as error:
        raise NamespaceFailure("toolchain") from error
    finally:
        if source_fd >= 0:
            os.close(source_fd)


def _write_bytes(destination: str, raw: bytes, mode: int) -> None:
    try:
        fd = os.open(
            destination,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
            mode,
        )
        try:
            view = memoryview(raw)
            while view:
                written = os.write(fd, view)
                if written <= 0:
                    raise NamespaceFailure("build")
                view = view[written:]
            os.fchmod(fd, mode)
        finally:
            os.close(fd)
    except OSError as error:
        raise NamespaceFailure("build") from error


def _descriptor_json(value: Mapping[str, Any]) -> bytes:
    try:
        return (json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n").encode(
            "utf-8", "strict"
        )
    except (TypeError, ValueError, UnicodeEncodeError) as error:
        raise NamespaceFailure("build") from error


def _stage_inputs() -> None:
    for source, destination in (
        ("/input-project", "/private-project"),
        ("/input-align", "/private-align"),
        ("/input-rust", "/private-rust"),
        ("/input-llvm", "/private-llvm"),
        ("/input-native", "/private-native"),
        ("/input-cargo-cache", "/private-cargo-home"),
        ("/input-launcher-source", "/private-launcher-source"),
        ("/input-tools", "/private-tool-inventory"),
    ):
        _debug(f"stage tree start source={source}")
        _copy_tree(source, destination, writable=source == "/input-cargo-cache")
        _debug(f"stage tree passed source={source}")
    Path("/tools").mkdir(mode=0o700, exist_ok=True)
    _debug("stage tools directory passed")
    for entry in sorted(Path("/private-tool-inventory").iterdir(), key=lambda item: os.fsencode(item.name)):
        if not entry.is_file() or entry.is_symlink():
            raise NamespaceFailure("toolchain")
        _copy_file(str(entry), f"/tools/{entry.name}", 0o555)
    _debug("stage tool inventory copied")
    Path("/private-native/bin").chmod(0o755)
    for source, name in (("clang", "cc"), ("clang++", "cxx"), ("ar", "ar"), ("ranlib", "ranlib"), ("linker", "linker")):
        _debug(f"stage native tool start source={source} destination={name}")
        _copy_file(f"/tools/{source}", f"/private-native/bin/{name}", 0o555)
        _debug(f"stage native tool passed source={source}")
    _debug("stage native tools copied")
    Path("/private-native/bin").chmod(0o555)
    _debug("stage native bin sealed")
    try:
        Path("/private-tool-inventory").chmod(0o700)
        _debug("stage tool inventory writable")
        for entry in Path("/private-tool-inventory").iterdir():
            entry.unlink()
        _debug("stage tool inventory entries removed")
        _debug("stage tool inventory emptied")
    except OSError as error:
        raise NamespaceFailure("toolchain") from error


def _handoff(project_head: str, align_revision: str) -> str:
    compiler = "/private-cargo-target/release/alignc"
    archive = "/private-cargo-target/release/libalign_runtime.a"
    launcher = "/private-launcher-source/adoption-alignc"
    compiler_stat: os.stat_result
    archive_stat: os.stat_result
    launcher_stat: os.stat_result
    compiler_raw: bytes
    archive_raw: bytes
    launcher_raw: bytes
    compiler_fd = archive_fd = launcher_fd = -1
    try:
        compiler_fd = os.open(compiler, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        archive_fd = os.open(archive, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        launcher_fd = os.open(launcher, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        compiler_stat = os.fstat(compiler_fd)
        archive_stat = os.fstat(archive_fd)
        launcher_stat = os.fstat(launcher_fd)
        compiler_raw = _read_open_file(compiler_fd, compiler_stat.st_size)
        archive_raw = _read_open_file(archive_fd, archive_stat.st_size)
        launcher_raw = _read_open_file(launcher_fd, launcher_stat.st_size)
        if (
            _stat_tuple(os.fstat(compiler_fd)) != _stat_tuple(compiler_stat)
            or _stat_tuple(os.fstat(archive_fd)) != _stat_tuple(archive_stat)
            or _stat_tuple(os.fstat(launcher_fd)) != _stat_tuple(launcher_stat)
        ):
            raise NamespaceFailure("build")
    except OSError as error:
        raise NamespaceFailure("build") from error
    finally:
        for descriptor in (compiler_fd, archive_fd, launcher_fd):
            if descriptor >= 0:
                os.close(descriptor)
    if (
        not stat.S_ISREG(compiler_stat.st_mode) or compiler_stat.st_nlink != 1 or stat.S_IMODE(compiler_stat.st_mode) != 0o755
        or len(compiler_raw) != compiler_stat.st_size
        or not stat.S_ISREG(archive_stat.st_mode) or archive_stat.st_nlink != 1 or stat.S_IMODE(archive_stat.st_mode) not in (0o444, 0o644)
        or len(archive_raw) != archive_stat.st_size
        or not stat.S_ISREG(launcher_stat.st_mode) or launcher_stat.st_nlink != 1 or stat.S_IMODE(launcher_stat.st_mode) != 0o755
        or len(launcher_raw) != launcher_stat.st_size
    ):
        raise NamespaceFailure("build")
    _write_bytes("/private-tool-bin/alignc", compiler_raw, 0o555)
    _write_bytes("/private-tool-bin/libalign_runtime.a", archive_raw, 0o444)
    _write_bytes("/private-tool-bin/adoption-alignc", launcher_raw, 0o555)
    final_compiler = _stat_and_read("/private-tool-bin/alignc", 0o555)
    final_archive = _stat_and_read("/private-tool-bin/libalign_runtime.a", 0o444)
    final_launcher = _stat_and_read("/private-tool-bin/adoption-alignc", 0o555)
    descriptor = OrderedDict(
        [
            ("schema_version", 1),
            ("compiler_path", "/private-tool-bin/alignc"),
            ("compiler_dev", final_compiler[0].st_dev),
            ("compiler_ino", final_compiler[0].st_ino),
            ("compiler_mode", stat.S_IMODE(final_compiler[0].st_mode)),
            ("compiler_nlink", final_compiler[0].st_nlink),
            ("compiler_size", final_compiler[0].st_size),
            ("compiler_sha256", hashlib.sha256(final_compiler[1]).hexdigest()),
            ("archive_path", "/private-tool-bin/libalign_runtime.a"),
            ("archive_dev", final_archive[0].st_dev),
            ("archive_ino", final_archive[0].st_ino),
            ("archive_mode", stat.S_IMODE(final_archive[0].st_mode)),
            ("archive_nlink", final_archive[0].st_nlink),
            ("archive_size", final_archive[0].st_size),
            ("archive_sha256", hashlib.sha256(final_archive[1]).hexdigest()),
            ("launcher_sha256", hashlib.sha256(final_launcher[1]).hexdigest()),
            ("align_revision", align_revision),
            ("project_head", project_head),
        ]
    )
    raw = _descriptor_json(descriptor)
    _write_bytes("/private-tool-bin/adoption-handoff", raw, 0o444)
    descriptor_stat, descriptor_raw = _stat_and_read("/private-tool-bin/adoption-handoff", 0o444)
    if descriptor_stat.st_nlink != 1 or descriptor_raw != raw:
        raise NamespaceFailure("build")
    return hashlib.sha256(launcher_raw).hexdigest()


def _receive_proof(channel: socket.socket) -> bytes:
    try:
        _debug("proof receive start")
        channel.settimeout(10)
        proof, _, flags, _ = channel.recvmsg(33, 0)
    except socket.timeout as error:
        _debug(f"proof receive timeout {error!r}")
        raise NamespaceFailure("toolchain") from error
    except OSError as error:
        _debug(f"proof receive error {type(error).__name__} errno={error.errno} {error!r}")
        raise NamespaceFailure("toolchain") from error
    finally:
        channel.settimeout(None)
    _debug(f"proof packet length={len(proof)} flags={flags}")
    if flags & socket.MSG_TRUNC or len(proof) != 32:
        _debug("proof packet shape rejected")
        raise NamespaceFailure("toolchain")
    channel.setblocking(False)
    try:
        try:
            extra, _, flags, _ = channel.recvmsg(1, 0, socket.MSG_PEEK)
        except BlockingIOError:
            extra = b""
            flags = 0
            _debug("proof extra check would block")
        else:
            _debug(f"proof extra check length={len(extra)} flags={flags}")
        if extra or flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC):
            _debug("proof extra packet rejected")
            raise NamespaceFailure("toolchain")
    except OSError as error:
        _debug(f"proof extra check error {type(error).__name__} errno={error.errno} {error!r}")
        raise NamespaceFailure("toolchain") from error
    finally:
        channel.setblocking(True)
    return proof


def _drop_child_capabilities() -> None:
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(38, 1, 0, 0, 0) != 0:  # PR_SET_NO_NEW_PRIVS
            error = ctypes.get_errno()
            raise OSError(error, "no_new_privs")
        header = (ctypes.c_uint32 * 2)(0x20080522, 0)
        data = (ctypes.c_uint32 * 2)(0, 0)
        if libc.capset(ctypes.byref(header), ctypes.byref(data)) != 0:
            error = ctypes.get_errno()
            raise OSError(error, "capset")
    except BaseException as error:
        try:
            status = {}
            with open("/proc/self/status", encoding="ascii") as stream:
                for line in stream:
                    name, separator, value = line.partition(":")
                    if separator and name in ("CapEff", "CapPrm", "CapBnd", "NoNewPrivs"):
                        status[name] = value.strip()
            os.write(
                2,
                f"namespace debug: capability drop uid={os.getuid()} euid={os.geteuid()} "
                f"{status!r} {type(error).__name__}: {error!r}\n".encode("ascii", "backslashreplace"),
            )
        except BaseException:
            pass
        os._exit(127)


def _set_subreaper() -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
        raise NamespaceFailure("toolchain")


def _channel_alive(channel: socket.socket) -> None:
    channel.setblocking(False)
    try:
        data, _, flags, _ = channel.recvmsg(1, 0, socket.MSG_PEEK | socket.MSG_DONTWAIT)
    except BlockingIOError:
        return
    except OSError as error:
        raise NamespaceFailure("toolchain") from error
    finally:
        channel.setblocking(True)
    if data or flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC):
        raise NamespaceFailure("toolchain")
    raise NamespaceFailure("toolchain")


def _run_row(
    arguments: Sequence[str],
    environment: Mapping[str, str],
    phase: str,
    timeout: int,
    channel: socket.socket,
) -> None:
    try:
        process = subprocess.Popen(
            list(arguments),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=dict(environment),
            close_fds=True,
            pass_fds=(),
            start_new_session=True,
            preexec_fn=_drop_child_capabilities,
        )
    except OSError as error:
        raise NamespaceFailure(phase) from error
    assert process.stdout is not None and process.stderr is not None
    streams = (process.stdout, process.stderr)
    stream_fds = tuple(stream.fileno() for stream in streams)
    selector = selectors.DefaultSelector()
    captures = {fd: bytearray() for fd in stream_fds}
    for stream in (process.stdout, process.stderr):
        os.set_blocking(stream.fileno(), False)
        selector.register(stream, selectors.EVENT_READ)
    deadline = time.monotonic() + timeout
    descendants_active = False
    descendant_failure = False

    def reap_descendants() -> tuple[bool, bool]:
        active = False
        failed = False
        while True:
            try:
                child, child_status = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                return active, failed
            except OSError as error:
                raise NamespaceFailure("unobserved") from error
            if child == 0:
                return True, failed
            if child == process.pid:
                continue
            if not os.WIFEXITED(child_status) or os.WEXITSTATUS(child_status) != 0:
                failed = True

    def terminate() -> None:
        descendants_live, _ = reap_descendants()
        if process.poll() is None or descendants_live:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except OSError as error:
                raise NamespaceFailure("unobserved") from error
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired as error:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except OSError:
                pass
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired as reap_error:
                raise NamespaceFailure("unobserved") from reap_error
            raise NamespaceFailure("unobserved") from error
        reap_deadline = time.monotonic() + 5
        while time.monotonic() < reap_deadline:
            active, _ = reap_descendants()
            if not active:
                return
            time.sleep(0.01)
        raise NamespaceFailure("unobserved")

    try:
        while selector.get_map() or process.poll() is None or descendants_active:
            _channel_alive(channel)
            if process.poll() is not None:
                descendants_active, failed = reap_descendants()
                descendant_failure = descendant_failure or failed
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise NamespaceFailure(phase)
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
                    raise NamespaceFailure(phase) from error
                if not block:
                    selector.unregister(key.fileobj)
                    continue
                captures[fd].extend(block)
                if len(captures[fd]) > MAX_STREAM_BYTES:
                    raise NamespaceFailure(phase)
        try:
            status = process.wait(timeout=0)
        except subprocess.TimeoutExpired as error:
            raise NamespaceFailure(phase) from error
    except NamespaceFailure:
        terminate()
        raise
    finally:
        selector.close()
        for stream in streams:
            stream.close()
    if status < 0:
        raise NamespaceFailure("unobserved")
    if descendant_failure:
        raise NamespaceFailure(phase)
    if status != 0:
        _debug(f"row failure phase={phase} status={status} stdout={bytes(captures[stream_fds[0]])!r} stderr={bytes(captures[stream_fds[1]])!r}")
        raise NamespaceFailure(phase if status > 0 else "unobserved")
    if any(captures.values()):
        raise NamespaceFailure(phase)


def _runtime_paths() -> tuple[str, str, str]:
    libraries: list[str] = []
    loaders: list[str] = []
    pkgconfig: list[str] = []
    for search_root in RUNTIME_SEARCH_ROOTS:
        for root, directories, files in os.walk(search_root):
            directories.sort(key=os.fsencode)
            files.sort(key=os.fsencode)
            for name in files:
                path = os.path.join(root, name)
                directory = os.path.dirname(path)
                if (name.endswith(".a") or name.endswith(".so") or ".so." in name) and directory not in libraries:
                    libraries.append(directory)
                if (name.endswith(".so") or ".so." in name) and directory not in loaders:
                    loaders.append(directory)
                if name.endswith(".pc") and directory not in pkgconfig:
                    pkgconfig.append(directory)
    if not libraries or not loaders or not pkgconfig:
        _debug(
            f"runtime paths missing libraries={len(libraries)} loaders={len(loaders)} "
            f"pkgconfig={len(pkgconfig)}"
        )
        raise NamespaceFailure("toolchain")
    return ":".join(libraries), ":".join(loaders), ":".join(pkgconfig)


def _environment(
    *, build: bool, focused: bool, library_path: str, loader_path: str, pkgconfig_path: str
) -> dict[str, str]:
    result = {
        "PATH": "/usr/bin:/bin",
        "ALIGN_REPO": "/private-align",
        "CARGO_NET_OFFLINE": "true",
        "HOME": "/nonexistent",
        "LANG": "C",
        "LC_ALL": "C",
        "MAKEFLAGS": "",
        "GNUMAKEFLAGS": "",
        "MAKEOVERRIDES": "",
        "PYTHONDONTWRITEBYTECODE": "1",
        "TMPDIR": "/tmp",
    }
    if build:
        result.update(
            {
                "CARGO": "/private-rust/bin/cargo",
                "RUSTC": "/private-rust/bin/rustc",
                "CARGO_HOME": "/private-cargo-home",
                "CARGO_TARGET_DIR": "/private-cargo-target",
                "LLVM_CONFIG": "/private-llvm/bin/llvm-config",
                "LLVM_SYS_221_PREFIX": "/private-llvm",
                "CC": "/private-native/bin/cc",
                "CXX": "/private-native/bin/cxx",
                "AR": "/private-native/bin/ar",
                "RANLIB": "/private-native/bin/ranlib",
                "LD": "/private-llvm/bin/ld.lld",
                "LIBRARY_PATH": library_path,
                "LD_LIBRARY_PATH": loader_path,
                "PKG_CONFIG_PATH": pkgconfig_path,
            }
        )
    result["PATH"] = "/private-native/bin:/private-rust/bin:/private-llvm/bin:/tools:/usr/bin:/bin"
    if focused:
        result.update(
            {
                "ALIGNC": "/private-tool-bin/adoption-alignc",
                "ALIGNC_DESCRIPTOR": "/private-tool-bin/adoption-handoff",
                "ALIGNC_CACHE": "/private-compiler-cache",
            }
        )
    return result


def _rows(
    *, launcher_sha256: str, align_revision: str, project_head: str,
    library_path: str, loader_path: str, pkgconfig_path: str,
) -> tuple[tuple[tuple[str, ...], dict[str, str], str, int], ...]:
    common = ("/tools/make", "--no-print-directory", "-C", "/private-project", "-f", "/private-project/Makefile")
    rows = (
        (
            ("/usr/bin/adoption-namespace", "--child-index", "1", "--no-compiler-handoff", "--", *common, "align-revision"),
            _environment(build=False, focused=False, library_path=library_path, loader_path=loader_path, pkgconfig_path=pkgconfig_path),
            "revision",
            REVISION_TIMEOUT_SECONDS,
        ),
        (
            ("/usr/bin/adoption-namespace", "--child-index", "2", "--no-compiler-handoff", "--", *common, "align-build-only"),
            _environment(build=True, focused=False, library_path=library_path, loader_path=loader_path, pkgconfig_path=pkgconfig_path),
            "build",
            ROW_TIMEOUT_SECONDS,
        ),
        (
            (
                "/usr/bin/adoption-namespace", "--child-index", "3", "--compiler-handoff",
                "/private-cargo-target/release/alignc", "/private-cargo-target/release/libalign_runtime.a",
                "/private-launcher-source/adoption-alignc", launcher_sha256, align_revision, project_head, "--",
                *common, "json-scan-row-ownership-adoption",
            ),
            _environment(build=True, focused=True, library_path=library_path, loader_path=loader_path, pkgconfig_path=pkgconfig_path),
            "fixture",
            FOCUSED_TIMEOUT_SECONDS,
        ),
    )
    return rows


def run(arguments: Sequence[str]) -> int:
    expected = (
        "--capsule-path", CAPSULE_PATH,
        "--worker-path", WORKER_PATH,
        "--nonce-path", NONCE_PATH,
        "--supervisor-channel-fd", "16",
        "--mode", "ordinary-adoption",
    )
    if (
        tuple(arguments) != expected
        or dict(os.environ) != HELPER_ENVIRONMENT
        or _descriptor_set() != {0, 1, 2, 11, 16}
    ):
        _debug(
            f"input mismatch arguments={tuple(arguments)!r} environment={dict(os.environ)!r} "
            f"descriptors={sorted(_descriptor_set())!r}"
        )
        raise NamespaceFailure("input")
    _set_subreaper()
    _debug("input boundary passed")
    capsule = _read_authority(CAPSULE_PATH, MAX_CAPSULE_BYTES)
    _debug(f"capsule authority passed size={len(capsule)}")
    worker = _read_authority(WORKER_PATH, MAX_WORKER_BYTES)
    _debug(f"worker authority passed size={len(worker)}")
    nonce = _read_authority(NONCE_PATH, MAX_NONCE_BYTES)
    _debug(f"nonce authority passed size={len(nonce)}")
    if len(nonce) != MAX_NONCE_BYTES:
        raise NamespaceFailure("toolchain")
    try:
        key = _read_key()
        verified = verify_envelope(
            capsule,
            expected_payload_type="https://align-llm.dev/attestations/ordinary-adoption/v2",
            expected_key_id=RUN_KEY_ID,
            public_key=key,
            predicate_validator=validate_ordinary_adoption_predicate,
        )
    except (OSError, ValueError, WireError) as error:
        raise NamespaceFailure("toolchain") from error
    _debug("capsule verification passed")
    predicate = verified.predicate
    if predicate["worker_size"] != len(worker) or predicate["worker_sha256"] != hashlib.sha256(worker).hexdigest():
        raise NamespaceFailure("revision")
    _debug("worker predicate passed")
    if predicate["invocation_nonce"] != base64.urlsafe_b64encode(nonce).rstrip(b"=").decode("ascii"):
        raise NamespaceFailure("input")
    _debug("nonce predicate passed")
    channel = socket.socket(fileno=16)
    try:
        proof = _receive_proof(channel)
    except NamespaceFailure as error:
        _debug(f"proof receive failure phase={error.phase}")
        raise
    _debug(f"proof received sha256={hashlib.sha256(proof).hexdigest()}")
    expected_proof = hashlib.sha256(
        b"align-llm/ordinary-adoption/worker-admission/v2\x00"
        + bytes.fromhex(predicate["dispatch_ticket_sha256"])
        + nonce
        + hashlib.sha256(capsule).digest()
    ).digest()
    if proof != expected_proof:
        _debug(
            f"proof mismatch received={proof.hex()} expected={expected_proof.hex()} "
            f"ticket_digest={predicate['dispatch_ticket_sha256']} capsule_digest={hashlib.sha256(capsule).hexdigest()}"
        )
        raise NamespaceFailure("toolchain")
    _debug("worker proof passed")
    _stage_inputs()
    _debug("staging passed")
    library_path, loader_path, pkgconfig_path = _runtime_paths()
    _debug("runtime paths passed")
    rows = _rows(
        launcher_sha256="",
        align_revision=predicate["align_head"],
        project_head=predicate["project_head"],
        library_path=library_path,
        loader_path=loader_path,
        pkgconfig_path=pkgconfig_path,
    )
    _run_row(rows[0][0][5:], rows[0][1], rows[0][2], rows[0][3], channel)
    _run_row(rows[1][0][5:], rows[1][1], rows[1][2], rows[1][3], channel)
    launcher_sha256 = _handoff(predicate["project_head"], predicate["align_head"])
    focused = _rows(
        launcher_sha256=launcher_sha256,
        align_revision=predicate["align_head"],
        project_head=predicate["project_head"],
        library_path=library_path,
        loader_path=loader_path,
        pkgconfig_path=pkgconfig_path,
    )[2]
    _run_row(focused[0][5:], focused[1], focused[2], focused[3], channel)
    _channel_alive(channel)
    os.write(1, b"json-scan adoption: PASS\n")
    return 0


def main(arguments: Sequence[str] | None = None) -> int:
    try:
        return run(tuple(arguments if arguments is not None else os.sys.argv[1:]))
    except NamespaceFailure as error:
        _debug(f"failure phase={error.phase}")
        return _fail(error.phase)
    except Exception as error:
        _debug(f"unexpected {type(error).__name__}: {error}")
        return _fail("toolchain")


if __name__ == "__main__":
    raise SystemExit(main())
