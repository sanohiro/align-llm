#!/usr/bin/env python3
"""Image-owned Request 6 dispatcher for the ordinary adoption profile.

This module is embedded in the installed dispatcher ELF.  It deliberately
stops at the revision boundary when the future consumer worker is absent; the
profile gate must still prove that an untrusted direct or incomplete request
cannot reach Make.
"""

from __future__ import annotations

import base64
import hashlib
import os
import posixpath
import socket
import stat
import subprocess
import sys
from collections import OrderedDict
from typing import Any, Mapping, Sequence

from fresh_attestation import (
    ORDINARY_ADOPTION_PREDICATE_TYPE,
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
    ADOPTION_NAMESPACE_PATH,
    ControlError,
    DISPATCHER_PATH,
    GIT_PATH,
    IMAGE_PUBLIC_KEY_PATH,
    ORDINARY_ENVIRONMENT,
    ORDINARY_NONCE_BYTES,
    ORDINARY_PREDICATE_TYPE,
    ORDINARY_REQUEST,
    ORDINARY_TICKET_BYTES,
    ORDINARY_WORKER_PATH,
    _canonical_relative_from_absolute,
    _identity,
    _open_regular,
    _read_key,
    _read_sealed,
    _regular_snapshot,
    _runtime_file_binding,
    _run_controlled_child,
    _sealed_memfd,
    _normalize_absolute,
    _git_identity,
    _ordinary_worker_snapshot,
    _runtime_tree,
)
from fresh_manifest import serialized_digest, validate_manifest_bytes


MAX_CAPSULE_BYTES = 262_144
MAX_SOURCE_FILE_BYTES = 4_194_304
MAX_PATH_BYTES = 4096
MAX_PROC_BYTES = 4096
PHASE_CODES = {
    "input": 1,
    "toolchain": 2,
    "revision": 3,
    "build": 4,
    "fixture": 5,
    "cleanup": 6,
}


class AdoptionFailure(Exception):
    def __init__(self, phase: str) -> None:
        super().__init__(phase)
        self.phase = phase


def _runtime_tree_binding(manifest: Mapping[str, Any], source: str) -> Mapping[str, Any]:
    matches = [
        binding
        for binding in manifest["runtime_bindings"]
        if binding.get("source") == source and binding.get("target") == source
    ]
    if len(matches) != 1:
        raise AdoptionFailure("toolchain")
    binding = matches[0]
    if binding.get("kind") != "tree" or not isinstance(binding.get("manifest"), Mapping):
        raise AdoptionFailure("toolchain")
    try:
        actual = _runtime_tree(source)
    except ControlError as error:
        raise AdoptionFailure("toolchain") from error
    if actual != binding["manifest"] or serialized_digest(actual) != binding.get(
        "manifest_sha256"
    ):
        raise AdoptionFailure("toolchain")
    return binding


def _runtime_tree_file(
    binding: Mapping[str, Any], source: str, target: str
) -> Mapping[str, Any]:
    prefix = source.rstrip("/") + "/"
    if not target.startswith(prefix):
        raise AdoptionFailure("toolchain")
    node: Mapping[str, Any] = binding["manifest"]
    for component in target[len(prefix) :].split("/"):
        entries = node.get("entries")
        if not isinstance(entries, list):
            raise AdoptionFailure("toolchain")
        matches = [
            entry
            for entry in entries
            if isinstance(entry, Mapping) and entry.get("name") == component
        ]
        if len(matches) != 1:
            raise AdoptionFailure("toolchain")
        node = matches[0]
    if node.get("kind") != "file" or node.get("mode") != "0755":
        raise AdoptionFailure("toolchain")
    return node


def fail(phase: str) -> int:
    if phase == "unobserved":
        os.write(2, b"json-scan adoption: ERROR unobserved\n")
        return 7
    if phase not in PHASE_CODES:
        phase = "toolchain"
    os.write(2, f"json-scan adoption: ERROR {phase}\n".encode("ascii"))
    return PHASE_CODES[phase]


def _strict_arguments(arguments: Sequence[str]) -> tuple[int, int, int, int, str, str, int, int]:
    expected = (
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
        None,
        "--align-repo-relative",
        None,
        "--invocation-nonce-fd",
        "15",
        "--supervisor-channel-fd",
        "16",
    )
    values = list(arguments)
    if len(values) != len(expected):
        raise AdoptionFailure("input")
    for actual, wanted in zip(values, expected):
        if wanted is not None and actual != wanted:
            raise AdoptionFailure("input")
    absolute = values[11]
    relative = values[13]
    if not isinstance(absolute, str) or not isinstance(relative, str):
        raise AdoptionFailure("input")
    try:
        absolute = _normalize_absolute(absolute)
        if _canonical_relative_from_absolute(absolute) != relative:
            raise AdoptionFailure("input")
    except Exception as error:
        if isinstance(error, AdoptionFailure):
            raise
        raise AdoptionFailure("input") from error
    return 4, 6, 8, 18, absolute, relative, 15, 16


def _descriptor_set() -> set[int]:
    descriptors: set[int] = set()
    for name in os.listdir("/proc/self/fd"):
        try:
            descriptor = int(name)
            os.fstat(descriptor)
            descriptors.add(descriptor)
        except (OSError, ValueError):
            pass
    return descriptors


def _require_environment() -> None:
    if dict(os.environ) != ORDINARY_ENVIRONMENT:
        raise AdoptionFailure("input")


def _validate_align_descriptor(
    project_fd: int, align_fd: int, absolute: str, relative: str
) -> None:
    try:
        project_before = _identity(project_fd)
        align_before = _identity(align_fd)
        project_path = os.readlink(f"/proc/self/fd/{project_fd}")
        align_path = os.readlink(f"/proc/self/fd/{align_fd}")
        if " (deleted)" in project_path or " (deleted)" in align_path:
            raise AdoptionFailure("revision")
        project_path = _normalize_absolute(project_path)
        align_path = _normalize_absolute(align_path)
        if align_path != absolute or posixpath.relpath(align_path, project_path) != relative:
            raise AdoptionFailure("revision")
        if align_before == project_before:
            raise AdoptionFailure("revision")
        if _identity(project_fd) != project_before or _identity(align_fd) != align_before:
            raise AdoptionFailure("revision")
    except (OSError, ControlError) as error:
        raise AdoptionFailure("revision") from error


def _read_relative_regular(root_fd: int, relative: str, *, limit: int) -> bytes:
    raw = os.fsencode(relative)
    if (
        not raw
        or raw.startswith(b"/")
        or b"\x00" in raw
        or len(raw) > MAX_PATH_BYTES
    ):
        raise AdoptionFailure("revision")
    parts = raw.split(b"/")
    if any(part in (b"", b".", b"..") for part in parts):
        raise AdoptionFailure("revision")
    current = os.dup(root_fd)
    retained = [current]
    descriptor = -1
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
        raw_value = _regular_snapshot(
            descriptor,
            limit=limit,
            exact_mode=0o755 if relative == ORDINARY_WORKER_PATH else None,
            exact_owner=os.geteuid(),
        )
        return raw_value
    except (OSError, ControlError, WireError) as error:
        raise AdoptionFailure("revision") from error
    finally:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass
        for value in reversed(retained):
            try:
                os.close(value)
            except OSError:
                pass


def _open_relative_identity(root_fd: int, relative: str) -> int | None:
    parts = os.fsencode(relative).split(b"/")
    if not parts or any(part in (b"", b".", b"..") for part in parts):
        raise AdoptionFailure("revision")
    retained = [os.dup(root_fd)]
    descriptor = -1
    try:
        current = retained[0]
        for part in parts[:-1]:
            current = os.open(
                part,
                os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=current,
            )
            retained.append(current)
        try:
            # The handoff row is the one exception whose bounded bytes are
            # part of the source-exception digest.  Keep its no-follow
            # identity descriptor readable so the snapshot is taken from the
            # same opened object rather than reopening the pathname.
            final_flags = (
                os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC
                if relative == "HANDOFF.md"
                else os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC
            )
            descriptor = os.open(
                parts[-1],
                final_flags,
                dir_fd=current,
            )
        except FileNotFoundError:
            return None
        return descriptor
    except OSError as error:
        raise AdoptionFailure("revision") from error
    finally:
        for value in reversed(retained):
            try:
                os.close(value)
            except OSError:
                pass


def _source_exception_row(
    root_fd: int, source: str, label: str, *, allow_main: bool
) -> OrderedDict[str, object]:
    descriptor = _open_relative_identity(root_fd, label)
    if descriptor is None:
        if label in ("git", "handoff"):
            raise AdoptionFailure("revision")
        if label == "main" and not allow_main:
            return OrderedDict(
                [
                    ("source", source),
                    ("label", label),
                    ("present", False),
                    ("type", None),
                    ("mode", None),
                    ("link_count", None),
                    ("bytes_consumed", False),
                    ("content_sha256", None),
                ]
            )
        return OrderedDict(
            [
                ("source", source),
                ("label", label),
                ("present", False),
                ("type", None),
                ("mode", None),
                ("link_count", None),
                ("bytes_consumed", False),
                ("content_sha256", None),
            ]
        )
    try:
        value = os.fstat(descriptor)
        mode = f"{stat.S_IMODE(value.st_mode):04o}"
        if label == "git":
            if not (stat.S_ISDIR(value.st_mode) or stat.S_ISREG(value.st_mode)):
                raise AdoptionFailure("revision")
            return OrderedDict(
                [
                    ("source", source),
                    ("label", label),
                    ("present", True),
                    ("type", "directory" if stat.S_ISDIR(value.st_mode) else "regular"),
                    ("mode", mode),
                    ("link_count", None),
                    ("bytes_consumed", False),
                    ("content_sha256", None),
                ]
            )
        if label == "handoff":
            if not stat.S_ISREG(value.st_mode) or value.st_nlink != 1 or mode not in ("0644", "0755"):
                raise AdoptionFailure("revision")
            raw = _regular_snapshot(
                descriptor,
                limit=MAX_SOURCE_FILE_BYTES,
                exact_mode=stat.S_IMODE(value.st_mode),
                exact_owner=os.geteuid(),
            )
            return OrderedDict(
                [
                    ("source", source),
                    ("label", label),
                    ("present", True),
                    ("type", "regular"),
                    ("mode", mode),
                    ("link_count", 1),
                    ("bytes_consumed", True),
                    ("content_sha256", sha256_hex(raw)),
                ]
            )
        if label == "target":
            if (
                not stat.S_ISDIR(value.st_mode)
                or value.st_mode & 0o7000
                or value.st_mode & 0o022
                or value.st_mode & 0o700 != 0o700
            ):
                raise AdoptionFailure("revision")
            return OrderedDict(
                [
                    ("source", source),
                    ("label", label),
                    ("present", True),
                    ("type", "directory"),
                    ("mode", mode),
                    ("link_count", value.st_nlink),
                    ("bytes_consumed", False),
                    ("content_sha256", None),
                ]
            )
        if label == "main":
            if not allow_main:
                raise AdoptionFailure("revision")
            if not stat.S_ISREG(value.st_mode) or value.st_nlink != 1 or mode not in ("0644", "0755"):
                raise AdoptionFailure("revision")
            return OrderedDict(
                [
                    ("source", source),
                    ("label", label),
                    ("present", True),
                    ("type", "regular"),
                    ("mode", mode),
                    ("link_count", 1),
                    ("bytes_consumed", False),
                    ("content_sha256", None),
                ]
            )
        raise AdoptionFailure("revision")
    finally:
        os.close(descriptor)


def _source_exception_vector(project_fd: int, align_fd: int) -> list[OrderedDict[str, object]]:
    rows: list[OrderedDict[str, object]] = []
    for source, root_fd, allow_main in (
        ("project-source", project_fd, True),
        ("align-source", align_fd, False),
    ):
        for label in ("git", "handoff", "target", "main"):
            rows.append(
                _source_exception_row(
                    root_fd, source, label, allow_main=allow_main
                )
            )
    return rows


def _raw_tree(root_fd: int, source: str) -> bytes:
    root_identity = _identity(root_fd)
    scan_fd = os.open(
        ".", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
        dir_fd=root_fd,
    )
    if _identity(scan_fd) != root_identity:
        os.close(scan_fd)
        raise AdoptionFailure("revision")
    entries: list[OrderedDict[str, object]] = [
        OrderedDict(
            [
                ("path_b64", ""),
                ("kind", "dir"),
                ("mode", f"{stat.S_IMODE(root_identity.mode):04o}"),
                ("size", 0),
                ("sha256", hashlib.sha256(b"").hexdigest()),
                ("target_b64", ""),
            ]
        )
    ]

    def visit(parent_fd: int, prefix: tuple[bytes, ...]) -> None:
        try:
            names = sorted((os.fsencode(name) for name in os.listdir(parent_fd)))
        except OSError as error:
            raise AdoptionFailure("revision") from error
        for name in names:
            if name in (b"", b".", b"..") or b"\x00" in name:
                raise AdoptionFailure("revision")
            path = (*prefix, name)
            if not prefix and name in (b".git", b"HANDOFF.md", b"target", b"main"):
                continue
            try:
                path_raw = b"/".join(path)
                if len(path_raw) > MAX_PATH_BYTES:
                    raise AdoptionFailure("revision")
                value = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            except OSError as error:
                raise AdoptionFailure("revision") from error
            if stat.S_ISDIR(value.st_mode):
                entries.append(
                    OrderedDict(
                        [
                            ("path_b64", base64.urlsafe_b64encode(path_raw).rstrip(b"=").decode("ascii")),
                            ("kind", "dir"),
                            ("mode", f"{stat.S_IMODE(value.st_mode):04o}"),
                            ("size", 0),
                            ("sha256", hashlib.sha256(b"").hexdigest()),
                            ("target_b64", ""),
                        ]
                    )
                )
                child_fd = os.open(
                    name,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                    dir_fd=parent_fd,
                )
                try:
                    child_identity = _identity(child_fd)
                    if (
                        child_identity.device != value.st_dev
                        or child_identity.inode != value.st_ino
                        or child_identity.mode != value.st_mode
                        or child_identity.owner != value.st_uid
                    ):
                        raise AdoptionFailure("revision")
                    visit(child_fd, path)
                    if _identity(child_fd) != child_identity:
                        raise AdoptionFailure("revision")
                finally:
                    os.close(child_fd)
            elif stat.S_ISREG(value.st_mode):
                if value.st_nlink != 1:
                    raise AdoptionFailure("revision")
                descriptor = os.open(
                    name,
                    os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC,
                    dir_fd=parent_fd,
                )
                try:
                    opened = _identity(descriptor)
                    if (
                        opened.device != value.st_dev
                        or opened.inode != value.st_ino
                        or opened.mode != value.st_mode
                        or opened.links != value.st_nlink
                        or opened.owner != value.st_uid
                        or opened.size != value.st_size
                    ):
                        raise AdoptionFailure("revision")
                    raw = _regular_snapshot(
                        descriptor,
                        limit=MAX_SOURCE_FILE_BYTES,
                        exact_mode=stat.S_IMODE(value.st_mode),
                        exact_owner=os.geteuid(),
                    )
                except (OSError, ControlError) as error:
                    raise AdoptionFailure("revision") from error
                finally:
                    os.close(descriptor)
                entries.append(
                    OrderedDict(
                        [
                            ("path_b64", base64.urlsafe_b64encode(path_raw).rstrip(b"=").decode("ascii")),
                            ("kind", "file"),
                            ("mode", f"{stat.S_IMODE(value.st_mode):04o}"),
                            ("size", len(raw)),
                            ("sha256", sha256_hex(raw)),
                            ("target_b64", ""),
                        ]
                    )
                )
            elif stat.S_ISLNK(value.st_mode):
                target = os.readlink(name, dir_fd=parent_fd)
                target_raw = os.fsencode(target)
                if len(target_raw) > MAX_PATH_BYTES:
                    raise AdoptionFailure("revision")
                after = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
                if (
                    after.st_dev != value.st_dev
                    or after.st_ino != value.st_ino
                    or after.st_mode != value.st_mode
                    or after.st_uid != value.st_uid
                    or after.st_size != value.st_size
                ):
                    raise AdoptionFailure("revision")
                entries.append(
                    OrderedDict(
                        [
                            ("path_b64", base64.urlsafe_b64encode(path_raw).rstrip(b"=").decode("ascii")),
                            ("kind", "symlink"),
                            ("mode", "0777"),
                            ("size", len(target_raw)),
                            ("sha256", sha256_hex(target_raw)),
                            ("target_b64", base64.urlsafe_b64encode(target_raw).rstrip(b"=").decode("ascii")),
                        ]
                    )
                )
            else:
                raise AdoptionFailure("revision")

    try:
        visit(scan_fd, ())
        entries.sort(key=lambda entry: base64.urlsafe_b64decode(entry["path_b64"] + "=="))
        if _identity(root_fd) != root_identity:
            raise AdoptionFailure("revision")
        return canonical_json_bytes(
            OrderedDict(
                [("schema", "raw-tree/v1"), ("source", source), ("entries", entries)]
            )
        )
    except (OSError, WireError) as error:
        raise AdoptionFailure("revision") from error
    finally:
        os.close(scan_fd)


def _peer_stat(pid: int) -> tuple[str, tuple[int, int]]:
    descriptor = -1
    try:
        descriptor = os.open(
            f"/proc/{pid}/stat", os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
        )
        raw = os.read(descriptor, MAX_PROC_BYTES)
        close = raw.rfind(b")")
        if close < 0:
            raise ValueError("stat framing")
        fields = raw[close + 2 :].split()
        if len(fields) < 20:
            raise ValueError("stat fields")
        start = fields[19].decode("ascii")
        return start, (0, 0)
    except (OSError, ValueError, UnicodeDecodeError) as error:
        raise AdoptionFailure("input") from error
    finally:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass


def _authenticate_parent(
    channel: socket.socket,
    image_predicate: Mapping[str, Any],
    python_sha256: str,
) -> bytes:
    credentials = channel.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
    pid = int.from_bytes(credentials[4:8], sys.byteorder, signed=True)
    uid = int.from_bytes(credentials[0:4], sys.byteorder, signed=True)
    if pid != os.getppid() or uid != os.geteuid():
        raise AdoptionFailure("input")
    start, _ = _peer_stat(pid)
    cmd_fd = -1
    exe_fd = -1
    try:
        cmd_fd = os.open(
            f"/proc/{pid}/cmdline", os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
        )
        cmdline = os.read(cmd_fd, MAX_PROC_BYTES + 1)
        exe_fd = os.open(f"/proc/{pid}/exe", os.O_RDONLY | os.O_CLOEXEC)
        exe_before = _identity(exe_fd)
        executable = bytearray()
        while len(executable) <= MAX_SOURCE_FILE_BYTES:
            block = os.read(exe_fd, min(65_536, MAX_SOURCE_FILE_BYTES + 1 - len(executable)))
            if not block:
                break
            executable.extend(block)
        exe_after = _identity(exe_fd)
    except (OSError, ValueError) as error:
        raise AdoptionFailure("input") from error
    finally:
        for descriptor in (cmd_fd, exe_fd):
            if descriptor >= 0:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
    if len(cmdline) > MAX_PROC_BYTES or len(executable) > MAX_SOURCE_FILE_BYTES:
        raise AdoptionFailure("input")
    exact = b"fresh-supervise\0--mode\0ordinary-adoption\0"
    launcher_bundle = (
        b"/usr/bin/python3\0-I\0-B\0/proc/self/fd/11\0"
        b"--embedded-self-fd\0"
        b"10\0--mode\0ordinary-adoption\0"
    )
    if cmdline != exact and cmdline != launcher_bundle:
        raise AdoptionFailure("input")
    if _peer_stat(pid)[0] != start or exe_before != exe_after:
        raise AdoptionFailure("input")
    digest = sha256_hex(bytes(executable))
    if digest != image_predicate["supervisor_sha256"]:
        # The native launcher has transferred control to the image-owned
        # Python carrier.  Its bytes must equal the manifest's fixed Python
        # runtime binding; the supervisor ELF digest remains the normative
        # image-owned identity for the native spelling.
        if digest != python_sha256:
            raise AdoptionFailure("input")
    ticket, _, flags, _ = channel.recvmsg(ORDINARY_TICKET_BYTES, 0)
    if flags & socket.MSG_TRUNC or len(ticket) != ORDINARY_TICKET_BYTES:
        raise AdoptionFailure("input")
    return ticket


def _validate_status_bytes(raw: bytes, *, allow_main: bool) -> None:
    if not raw:
        return
    if not raw.endswith(b"\0"):
        raise AdoptionFailure("revision")
    for record in raw[:-1].split(b"\0"):
        if len(record) < 4 or record[2:3] != b" ":
            raise AdoptionFailure("revision")
        status = record[:2]
        path = record[3:]
        if status in (b"??", b"!!"):
            if path == b"HANDOFF.md" or path == b"target" or (
                path == b"main" and allow_main
            ):
                continue
            if path.startswith(b"target/"):
                continue
            raise AdoptionFailure("revision")
        if path == b"HANDOFF.md" and status in (b" M", b"M ", b"MM"):
            continue
        raise AdoptionFailure("revision")


def _validate_clean_checkout(
    root_fd: int, git_fd: int, *, allow_main: bool
) -> None:
    environment = {
        "PATH": "/usr/bin:/bin",
        "LC_ALL": "C",
        "HOME": "/nonexistent",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_COUNT": "0",
        "GIT_OPTIONAL_LOCKS": "0",
    }
    git_path = f"/proc/self/fd/{git_fd}"
    try:
        result = _run_controlled_child(
            [
                git_path,
                "-c",
                "safe.directory=*",
                "-c",
                "core.fsmonitor=false",
                "-c",
                "core.untrackedCache=false",
                "status",
                "--porcelain=v1",
                "-z",
                "--untracked-files=all",
                "--ignored=matching",
                "--",
            ],
            cwd=f"/proc/self/fd/{root_fd}",
            environment=environment,
            pass_fds=(git_fd,),
            timeout=5,
            stdout_limit=CONTROL_STREAM_LIMIT,
            stderr_limit=CONTROL_STREAM_LIMIT,
        )
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise AdoptionFailure("revision") from error
    if result.returncode != 0 or result.stderr:
        raise AdoptionFailure("revision")
    _validate_status_bytes(result.stdout, allow_main=allow_main)


def _predicate(
    *,
    nonce: bytes,
    ticket: bytes,
    project_fd: int,
    align_fd: int,
    git_fd: int,
    absolute: str,
    relative: str,
    worker_raw: bytes,
    image_predicate: Mapping[str, Any],
    image_envelope: bytes,
    manifest_raw: bytes,
    entrypoint_raw: bytes,
) -> OrderedDict[str, object]:
    try:
        project_before = _identity(project_fd)
        git_before = _identity(git_fd)
        project_format, project_head = _git_identity(
            project_fd, f"/proc/self/fd/{git_fd}", git_fd=git_fd
        )
        if _identity(project_fd) != project_before or _identity(git_fd) != git_before:
            raise AdoptionFailure("revision")
        align_before = _identity(align_fd)
        git_before = _identity(git_fd)
        align_format, align_head = _git_identity(
            align_fd, f"/proc/self/fd/{git_fd}", git_fd=git_fd
        )
        if _identity(align_fd) != align_before or _identity(git_fd) != git_before:
            raise AdoptionFailure("revision")
    except AdoptionFailure:
        raise
    except (ControlError, OSError) as error:
        raise AdoptionFailure("revision") from error
    if project_format != "sha1" or align_format != "sha1":
        raise AdoptionFailure("revision")
    try:
        _validate_clean_checkout(project_fd, git_fd, allow_main=True)
        _validate_clean_checkout(align_fd, git_fd, allow_main=False)
        project_index_raw = _read_relative_regular(
            project_fd, ".git/index", limit=MAX_SOURCE_FILE_BYTES
        )
        raw_tree_raw = _raw_tree(project_fd, "project-source")
        source_exception_raw = canonical_json_value_bytes(
            _source_exception_vector(project_fd, align_fd)
        )
    except AdoptionFailure:
        raise
    return OrderedDict(
        [
            ("api", "ordinary-adoption/v2"),
            ("request", ORDINARY_REQUEST),
            (
                "invocation_nonce",
                base64.urlsafe_b64encode(nonce).rstrip(b"=").decode("ascii"),
            ),
            ("dispatch_ticket_sha256", sha256_hex(ticket)),
            ("project_head", project_head),
            ("project_object_format", project_format),
            ("project_index_sha256", sha256_hex(project_index_raw)),
            ("project_raw_tree_sha256", sha256_hex(raw_tree_raw)),
            ("source_exception_sha256", sha256_hex(source_exception_raw)),
            ("align_head", align_head),
            ("align_object_format", align_format),
            ("align_repo_relative", relative),
            ("worker_relative", ORDINARY_WORKER_PATH),
            ("worker_size", len(worker_raw)),
            ("worker_sha256", sha256_hex(worker_raw)),
            ("image_digest", image_predicate["image_digest"]),
            ("image_attestation_sha256", sha256_hex(image_envelope)),
            ("manifest_sha256", sha256_hex(manifest_raw)),
            ("entrypoint_sha256", sha256_hex(entrypoint_raw)),
        ]
    )


def dispatch(arguments: Sequence[str]) -> int:
    project_fd, image_fd, manifest_fd, align_fd, absolute, relative, nonce_fd, channel_fd = (
        _strict_arguments(arguments)
    )
    _require_environment()
    if _descriptor_set() != {0, 1, 2, 4, 6, 8, 15, 16, 18}:
        raise AdoptionFailure("input")
    image_envelope = _read_sealed(
        image_fd, limit=262_144, expected_name="align-llm-image"
    )
    manifest_raw = _read_sealed(
        manifest_fd, limit=67_108_864, expected_name="align-llm-manifest"
    )
    nonce = _read_sealed(
        nonce_fd,
        limit=ORDINARY_NONCE_BYTES,
        expected_name="align-llm-ordinary-adoption-nonce",
    )
    if len(nonce) != ORDINARY_NONCE_BYTES:
        raise AdoptionFailure("input")
    try:
        manifest = validate_manifest_bytes(manifest_raw)
    except WireError as error:
        raise AdoptionFailure("toolchain") from error
    image_key = _read_key(IMAGE_PUBLIC_KEY_PATH, private=False, owner=0)
    try:
        verified_image = verify_envelope(
            image_envelope,
            expected_payload_type="https://align-llm.dev/attestations/runner-image/v1",
            expected_key_id="align-llm-runner-image-v1",
            public_key=image_key,
            predicate_validator=validate_image_predicate,
        )
    except WireError as error:
        raise AdoptionFailure("toolchain") from error
    image_predicate = verified_image.predicate
    if image_predicate.get("manifest_sha256") != sha256_hex(manifest_raw):
        raise AdoptionFailure("toolchain")
    entrypoint_fd, entrypoint_raw, _ = _runtime_file_binding(
        manifest, DISPATCHER_PATH, owner=0
    )
    helper_fd = -1
    try:
        helper_fd, helper_raw, helper_binding = _runtime_file_binding(
            manifest, ADOPTION_NAMESPACE_PATH, owner=0
        )
        if not helper_raw or sha256_hex(helper_raw) != helper_binding["manifest"]["sha256"]:
            raise AdoptionFailure("toolchain")
    finally:
        os.close(entrypoint_fd)
        if helper_fd >= 0:
            os.close(helper_fd)
    try:
        bwrap_fd, bwrap_raw, bwrap_binding = _runtime_file_binding(
            manifest, "/usr/bin/bwrap", owner=0, limit=536_870_912
        )
    except Exception:
        raise
    try:
        if not bwrap_raw or sha256_hex(bwrap_raw) != bwrap_binding["manifest"]["sha256"]:
            raise AdoptionFailure("toolchain")
    finally:
        os.close(bwrap_fd)
    try:
        python_fd, python_raw, _ = _runtime_file_binding(
            manifest, "/usr/bin/python3", owner=0, limit=536_870_912
        )
    except Exception:
        raise
    python_sha256 = sha256_hex(python_raw)
    channel = socket.socket(fileno=channel_fd)
    _validate_align_descriptor(project_fd, align_fd, absolute, relative)
    ticket = _authenticate_parent(channel, image_predicate, python_sha256)
    try:
        if os.fstat(align_fd).st_ino == os.fstat(project_fd).st_ino:
            raise AdoptionFailure("revision")
        worker_path, worker_size, worker_raw = _ordinary_worker_snapshot(
            project_fd, owner=os.geteuid()
        )
        if worker_path != ORDINARY_WORKER_PATH or worker_size != len(worker_raw):
            raise AdoptionFailure("revision")
    except Exception as error:
        if isinstance(error, AdoptionFailure):
            raise
        raise AdoptionFailure("revision") from error
    git_binding = _runtime_tree_binding(manifest, "/runtime/git")
    git_node = _runtime_tree_file(git_binding, "/runtime/git", GIT_PATH)
    try:
        git_fd, git_raw = _open_regular(
            GIT_PATH,
            limit=MAX_SOURCE_FILE_BYTES,
            exact_mode=0o755,
            exact_owner=0,
        )
    except ControlError as error:
        raise AdoptionFailure("toolchain") from error
    try:
        if (
            git_node.get("size") != len(git_raw)
            or git_node.get("sha256") != sha256_hex(git_raw)
        ):
            raise AdoptionFailure("toolchain")
        predicate = _predicate(
            nonce=nonce,
            ticket=ticket,
            project_fd=project_fd,
            align_fd=align_fd,
            git_fd=git_fd,
            absolute=absolute,
            relative=relative,
            worker_raw=worker_raw,
            image_predicate=image_predicate,
            image_envelope=image_envelope,
            manifest_raw=manifest_raw,
            entrypoint_raw=entrypoint_raw,
        )
    finally:
        os.close(git_fd)
    try:
        validate_ordinary_adoption_predicate(predicate)
    except WireError as error:
        raise AdoptionFailure("toolchain") from error
    seed = _read_key(
        "/run/align-llm-fresh/run-signing-seed", private=True, owner=os.geteuid()
    )
    if ed25519_public_key(seed) != _read_key(
        "/usr/local/share/align-llm/run-verifier.pub", private=False, owner=0
    ):
        raise AdoptionFailure("toolchain")
    capsule = signed_envelope(
        predicate,
        payload_type=ORDINARY_PREDICATE_TYPE,
        key_id=RUN_KEY_ID,
        seed=seed,
    )
    capsule_fd = _sealed_memfd(
        "align-llm-ordinary-adoption-capsule", capsule, 12
    )
    worker_fd = _sealed_memfd(
        "align-llm-ordinary-adoption-worker", worker_raw, 13
    )
    try:
        capsule_digest = hashlib.sha256(capsule).digest()
        if channel.send(capsule_digest) != len(capsule_digest):
            raise AdoptionFailure("toolchain")
        worker_arguments = [
            "/usr/bin/python3",
            "-I",
            "-B",
            "/proc/self/fd/13",
            "--project-root-fd",
            "4",
            "--align-root-fd",
            "18",
            "--capsule-fd",
            "12",
            "--invocation-nonce-fd",
            "15",
            "--supervisor-channel-fd",
            "16",
        ]
        result = _run_controlled_child(
            worker_arguments,
            environment=ORDINARY_ENVIRONMENT,
            timeout=5_000,
            pass_fds=(4, 6, 8, 12, 13, 15, 16, 18, python_fd),
            executable=f"/proc/self/fd/{python_fd}",
            cwd="/proc/self/fd/4",
        )
    except AdoptionFailure:
        raise
    except subprocess.TimeoutExpired as error:
        raise AdoptionFailure("cleanup") from error
    except Exception as error:
        raise AdoptionFailure("toolchain") from error
    finally:
        os.close(python_fd)
        for descriptor in (12, 13):
            try:
                os.close(descriptor)
            except OSError:
                pass
    if result.returncode != 0:
        if result.stderr.count(b"\n") == 1 and result.stderr.startswith(
            b"json-scan adoption: ERROR "
        ):
            try:
                phase = result.stderr.decode("ascii").strip().rsplit(" ", 1)[1]
            except (UnicodeDecodeError, IndexError):
                phase = "toolchain"
            raise AdoptionFailure(phase)
        raise AdoptionFailure("unobserved")
    if result.stderr or result.stdout != b"json-scan adoption: PASS\n":
        raise AdoptionFailure("toolchain")
    os.write(1, result.stdout)
    return 0


def main(arguments: Sequence[str] | None = None) -> int:
    try:
        return dispatch(list(sys.argv[1:] if arguments is None else arguments))
    except AdoptionFailure as error:
        return fail(error.phase)
    except Exception:
        return fail("toolchain")


if __name__ == "__main__":
    raise SystemExit(main())
