#!/usr/bin/env python3
"""Descriptor-relative source identity capture for the Section 9 worker.

The source-manifest wire validator deliberately has no filesystem or Git
behavior.  This module is the read-only worker boundary that supplies it with
an identity captured from retained Linux file descriptors.  It does not create
private roots or copy source bytes.
"""

from __future__ import annotations

import hashlib
import os
import re
import stat
import subprocess
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from fresh_source import (
    MAX_DEPTH,
    MAX_ENTRIES,
    MAX_FILE_BYTES,
    MAX_PATH_BYTES,
    MAX_RAW_PATH_LINK_BYTES,
    MAX_SYMLINK_BYTES,
    MAX_TOTAL_SOURCE_BYTES,
    canonical_source_manifest_bytes,
    serialized_source_manifest_digest,
    validate_source_manifest,
)


MAX_INDEX_BYTES = 4 * 1024 * 1024 * 1024
MAX_GITDIR_BYTES = 4096
MAX_REVISION_BYTES = 128
MAX_GIT_CONFIG_BYTES = 4 * 1024 * 1024
MAX_GIT_LIST_BYTES = 192 * 1024 * 1024
MAX_OBJECT_IDS = MAX_ENTRIES * 2
READ_CHUNK = 1024 * 1024
GIT_BINARY = "/usr/bin/git"
HEX = re.compile(rb"^[0-9a-f]+$")
REVISION = re.compile(r"^[0-9a-f]{40}$")

O_PATH = getattr(os, "O_PATH", 0)
if not O_PATH:  # pragma: no cover - the Section 9 profile is Linux.
    raise RuntimeError("descriptor-relative source identity requires Linux O_PATH")
DIR_FLAGS = O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
PATH_FLAGS = O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC
READ_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC


class SourceIdentityError(ValueError):
    """A source identity cannot be accepted."""


@dataclass(frozen=True)
class DescriptorSnapshot:
    device: int
    inode: int
    file_type: int
    mode: int
    links: int
    size: int
    mtime_ns: int
    ctime_ns: int


def _snapshot(fd: int) -> DescriptorSnapshot:
    try:
        value = os.fstat(fd)
    except OSError as error:
        raise SourceIdentityError("source descriptor is not readable") from error
    return DescriptorSnapshot(
        value.st_dev,
        value.st_ino,
        stat.S_IFMT(value.st_mode),
        stat.S_IMODE(value.st_mode),
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


class _OwnedFD:
    def __init__(self, fd: int, label: str) -> None:
        self.fd = fd
        self.label = label
        self.initial = _snapshot(fd)
        self.closed = False
        os.set_inheritable(fd, False)

    def current(self) -> DescriptorSnapshot:
        if self.closed:
            raise SourceIdentityError("source descriptor is closed")
        return _snapshot(self.fd)

    def assert_stable(self) -> None:
        if self.current() != self.initial:
            raise SourceIdentityError("source descriptor changed")

    def close(self) -> None:
        if not self.closed:
            self.closed = True
            try:
                os.close(self.fd)
            except OSError as error:
                raise SourceIdentityError("source descriptor close failed") from error


class DirectoryHandle:
    """An owned descriptor resolution returned by ``open_relative_directory``."""

    def __init__(self, descriptors: list[_OwnedFD], final: _OwnedFD) -> None:
        self._descriptors = descriptors
        self._final = final
        self._closed = False

    @property
    def fd(self) -> int:
        if self._closed:
            raise SourceIdentityError("directory handle is closed")
        return self._final.fd

    @property
    def descriptors(self) -> tuple[int, ...]:
        if self._closed:
            raise SourceIdentityError("directory handle is closed")
        return tuple(item.fd for item in self._descriptors)

    def assert_stable(self) -> None:
        if self._closed:
            raise SourceIdentityError("directory handle is closed")
        for item in self._descriptors:
            item.assert_stable()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        first: SourceIdentityError | None = None
        for item in reversed(self._descriptors):
            try:
                item.close()
            except SourceIdentityError as error:
                first = first or error
        if first is not None:
            raise first

    def __enter__(self) -> "DirectoryHandle":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def _duplicate(fd: int, label: str) -> _OwnedFD:
    try:
        duplicate = os.dup(fd)
    except OSError as error:
        raise SourceIdentityError("source descriptor duplication failed") from error
    return _OwnedFD(duplicate, label)


def _open_at(directory_fd: int, name: bytes, flags: int, label: str) -> _OwnedFD:
    try:
        fd = os.open(name, flags, dir_fd=directory_fd)
    except OSError as error:
        raise SourceIdentityError("source path could not be opened") from error
    return _OwnedFD(fd, label)


def _raw_path(value: str | bytes, label: str) -> bytes:
    if isinstance(value, bytes):
        raw = value
    elif isinstance(value, str):
        try:
            raw = value.encode("utf-8", "strict")
        except UnicodeEncodeError as error:
            raise SourceIdentityError(f"{label} is not UTF-8") from error
    else:
        raise SourceIdentityError(f"{label} is not a path")
    if not raw or b"\x00" in raw or len(raw) > MAX_PATH_BYTES:
        raise SourceIdentityError(f"{label} is not a bounded path")
    return raw


def _components(value: str | bytes, label: str, *, absolute: bool = False) -> list[bytes]:
    raw = _raw_path(value, label)
    if raw.startswith(b"/"):
        if not absolute:
            raise SourceIdentityError(f"{label} is absolute")
        raw = raw[1:]
    elif absolute:
        raise SourceIdentityError(f"{label} is not absolute")
    parts = raw.split(b"/")
    if len(parts) > MAX_DEPTH or any(not part or part == b"." for part in parts):
        raise SourceIdentityError(f"{label} has an invalid component")
    return parts


def _assert_all(descriptors: Iterable[_OwnedFD]) -> None:
    for descriptor in descriptors:
        descriptor.assert_stable()


def open_relative_directory(project_root_fd: int, relative: str | bytes) -> DirectoryHandle:
    """Open a relative directory without following any path component symlink."""

    parts = _components(relative, "relative directory")
    owned: list[_OwnedFD] = [_duplicate(project_root_fd, "relative-root")]
    current = owned[0]
    try:
        if current.initial.file_type != stat.S_IFDIR:
            raise SourceIdentityError("relative root descriptor is not a directory")
        for index, part in enumerate(parts):
            _assert_all(owned)
            next_descriptor = _open_at(
                current.fd,
                b".." if part == b".." else part,
                DIR_FLAGS,
                f"relative-component-{index}",
            )
            if (
                part == b".."
                and next_descriptor.initial.device == current.initial.device
                and next_descriptor.initial.inode == current.initial.inode
            ):
                next_descriptor.close()
                raise SourceIdentityError("relative directory escapes the retained ancestor chain")
            current = next_descriptor
            owned.append(current)
        _assert_all(owned)
        return DirectoryHandle(owned, current)
    except Exception:
        for descriptor in reversed(owned):
            try:
                descriptor.close()
            except SourceIdentityError:
                pass
        raise


def _open_absolute_directory(absolute: bytes) -> DirectoryHandle:
    parts = _components(absolute, "absolute directory", absolute=True)
    try:
        root = _OwnedFD(os.open(b"/", DIR_FLAGS), "filesystem-root")
    except OSError as error:
        raise SourceIdentityError("filesystem root could not be opened") from error
    owned = [root]
    current = root
    try:
        for index, part in enumerate(parts):
            _assert_all(owned)
            current = _open_at(current.fd, part, DIR_FLAGS, f"absolute-component-{index}")
            owned.append(current)
        return DirectoryHandle(owned, current)
    except Exception:
        for descriptor in reversed(owned):
            try:
                descriptor.close()
            except SourceIdentityError:
                pass
        raise


def _read_fd(fd: int, limit: int, label: str) -> bytes:
    try:
        size = os.fstat(fd).st_size
        if size < 0 or size > limit:
            raise SourceIdentityError(f"{label} is too large")
        chunks: list[bytes] = []
        offset = 0
        while offset < size:
            chunk = os.pread(fd, min(READ_CHUNK, size - offset), offset)
            if not chunk:
                raise SourceIdentityError(f"{label} changed while reading")
            chunks.append(chunk)
            offset += len(chunk)
        if offset != size:
            raise SourceIdentityError(f"{label} has an unstable size")
        return b"".join(chunks)
    except OSError as error:
        raise SourceIdentityError(f"{label} is not readable") from error


def _read_child_file(directory_fd: int, name: bytes, limit: int, label: str) -> tuple[_OwnedFD, bytes]:
    descriptor = _open_at(directory_fd, name, READ_FLAGS, label)
    try:
        if descriptor.initial.file_type != stat.S_IFREG or descriptor.initial.links != 1:
            raise SourceIdentityError(f"{label} is not an ordinary file")
        content = _read_fd(descriptor.fd, limit, label)
        descriptor.assert_stable()
        return descriptor, content
    except Exception:
        descriptor.close()
        raise


def _optional_child_file(directory_fd: int, name: bytes, limit: int, label: str) -> tuple[_OwnedFD, bytes] | None:
    try:
        return _read_child_file(directory_fd, name, limit, label)
    except SourceIdentityError as error:
        # A missing optional file is the only accepted absence.  Reopen with a
        # no-follow descriptor to distinguish it from malformed metadata.
        try:
            probe = os.open(name, PATH_FLAGS, dir_fd=directory_fd)
        except FileNotFoundError:
            return None
        except OSError as open_error:
            raise error from open_error
        try:
            os.close(probe)
        except OSError:
            pass
        raise


@dataclass
class _GitView:
    worktree: DirectoryHandle
    root_git: _OwnedFD
    git_dir: DirectoryHandle
    common_dir: DirectoryHandle
    head: _OwnedFD
    index: _OwnedFD
    objects: _OwnedFD
    commondir: _OwnedFD | None
    gitdir_bytes: bytes | None
    extras: tuple[_OwnedFD, ...] = ()

    def descriptors(self) -> tuple[_OwnedFD, ...]:
        values: list[_OwnedFD] = []
        values.extend(self.worktree._descriptors)
        values.append(self.root_git)
        values.extend(self.git_dir._descriptors)
        values.extend(self.common_dir._descriptors)
        values.extend([self.head, self.index, self.objects])
        if self.commondir is not None:
            values.append(self.commondir)
        values.extend(self.extras)
        # A descriptor can occur in more than one resolution after a dup or a
        # shared common directory.  Preserve order but check each fd once.
        unique: list[_OwnedFD] = []
        seen: set[int] = set()
        for value in values:
            if value.fd not in seen:
                seen.add(value.fd)
                unique.append(value)
        return tuple(unique)

    def assert_stable(self) -> None:
        _assert_all(self.descriptors())

    def pass_fds(self) -> tuple[int, ...]:
        return tuple(value.fd for value in self.descriptors())


def _close_view(view: _GitView) -> None:
    descriptors = list(view.descriptors())
    # DirectoryHandle.close also closes descriptors that are included above.
    # Close through one identity set to avoid double close and accidental fd
    # reuse during error cleanup.
    closed: set[int] = set()
    first: SourceIdentityError | None = None
    for descriptor in reversed(descriptors):
        if descriptor.fd in closed:
            continue
        closed.add(descriptor.fd)
        try:
            descriptor.close()
        except SourceIdentityError as error:
            first = first or error
    for handle in (view.worktree, view.git_dir, view.common_dir):
        handle._closed = True
    if first is not None:
        raise first


def _fixed_git_environment(view: _GitView) -> dict[str, str]:
    return {
        "GIT_WORK_TREE": f"/proc/self/fd/{view.worktree.fd}",
        "GIT_DIR": f"/proc/self/fd/{view.git_dir.fd}",
        "GIT_COMMON_DIR": f"/proc/self/fd/{view.common_dir.fd}",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_ATTR_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_GRAFT_FILE": "/dev/null",
        "GIT_NO_LAZY_FETCH": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "XDG_CONFIG_HOME": "/dev/null",
        "LC_ALL": "C",
    }


def _git(
    view: _GitView,
    arguments: list[str],
    *,
    input_bytes: bytes | None = None,
    max_output: int = MAX_GIT_CONFIG_BYTES,
) -> bytes:
    view.assert_stable()
    process: subprocess.Popen[bytes] | None = None
    try:
        process = subprocess.Popen(
            [GIT_BINARY, *arguments],
            cwd=f"/proc/self/fd/{view.worktree.fd}",
            env=_fixed_git_environment(view),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.PIPE if input_bytes is not None else subprocess.DEVNULL,
            close_fds=True,
            pass_fds=view.pass_fds(),
        )
        assert process.stdout is not None
        if input_bytes is not None:
            assert process.stdin is not None
            process.stdin.write(input_bytes)
            process.stdin.close()
        chunks: list[bytes] = []
        size = 0
        while True:
            chunk = process.stdout.read(min(READ_CHUNK, max_output + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if size > max_output:
                process.kill()
                process.wait()
                raise SourceIdentityError("Git source query output is too large")
        return_code = process.wait()
    except (OSError, ValueError) as error:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait()
        raise SourceIdentityError("Git child could not be started") from error
    view.assert_stable()
    if return_code != 0:
        raise SourceIdentityError("Git source query failed")
    return b"".join(chunks)


def _open_git_view(worktree: DirectoryHandle, *, kind: str) -> _GitView:
    owned: list[_OwnedFD] = []
    handles: list[DirectoryHandle] = []
    root_fd = worktree.fd
    root_git = _open_at(root_fd, b".git", os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, "root-git")
    owned.append(root_git)
    try:
        if root_git.initial.file_type == stat.S_IFDIR:
            git_dir_fd = _duplicate(root_git.fd, "git-dir")
            git_dir = DirectoryHandle([git_dir_fd], git_dir_fd)
            gitdir_bytes = None
        elif root_git.initial.file_type == stat.S_IFREG:
            gitdir_bytes = _read_fd(root_git.fd, MAX_GITDIR_BYTES, "root-git")
            if not gitdir_bytes.startswith(b"gitdir: ") or not gitdir_bytes.endswith(b"\n"):
                raise SourceIdentityError("linked-worktree Git control file is malformed")
            path = gitdir_bytes[len(b"gitdir: ") : -1]
            if not path or b"\x00" in path or b"\n" in path or b"\r" in path:
                raise SourceIdentityError("linked-worktree Git directory is invalid")
            if path.startswith(b"/"):
                git_dir = _open_absolute_directory(path)
            else:
                git_dir = open_relative_directory(root_fd, path)
        else:
            raise SourceIdentityError("root Git control entry has an invalid type")
        handles.append(git_dir)

        commondir = None
        common_dir = git_dir
        optional = _optional_child_file(git_dir.fd, b"commondir", MAX_GITDIR_BYTES, "commondir")
        if optional is not None:
            commondir, raw = optional
            if (
                not raw.endswith(b"\n")
                or raw[:-1].startswith(b"/")
                or not raw[:-1]
                or b"\n" in raw[:-1]
                or b"\r" in raw[:-1]
            ):
                raise SourceIdentityError("commondir metadata is invalid")
            common_dir = open_relative_directory(git_dir.fd, raw[:-1])
            handles.append(common_dir)

        head, _ = _read_child_file(git_dir.fd, b"HEAD", MAX_REVISION_BYTES, "HEAD")
        index, _ = _read_child_file(git_dir.fd, b"index", MAX_INDEX_BYTES, "index")
        objects = _open_at(common_dir.fd, b"objects", DIR_FLAGS, "objects")
        if objects.initial.file_type != stat.S_IFDIR:
            raise SourceIdentityError("Git object store is not a directory")
        owned.extend([head, index, objects])
        if common_dir is git_dir:
            handles.append(common_dir)
        return _GitView(
            worktree,
            root_git,
            git_dir,
            common_dir,
            head,
            index,
            objects,
            commondir,
            gitdir_bytes,
        )
    except Exception:
        closed_handles: set[int] = set()
        for handle in reversed(handles):
            if id(handle) in closed_handles:
                continue
            closed_handles.add(id(handle))
            try:
                handle.close()
            except SourceIdentityError:
                pass
        for descriptor in reversed(owned):
            try:
                descriptor.close()
            except SourceIdentityError:
                pass
        try:
            root_git.close()
        except SourceIdentityError:
            pass
        raise


def _parse_lines(raw: bytes, label: str) -> list[bytes]:
    if not raw.endswith(b"\n"):
        raise SourceIdentityError(f"{label} has an invalid line ending")
    return raw[:-1].split(b"\n") if raw[:-1] else []


def _reject_present(directory_fd: int, path: bytes, label: str) -> None:
    parts = path.split(b"/")
    opened: list[int] = []
    current = directory_fd
    try:
        for index, part in enumerate(parts):
            flags = PATH_FLAGS if index == len(parts) - 1 else DIR_FLAGS
            try:
                descriptor = os.open(part, flags, dir_fd=current)
            except FileNotFoundError:
                return
            except OSError as error:
                raise SourceIdentityError(f"{label} cannot be checked") from error
            opened.append(descriptor)
            current = descriptor
        raise SourceIdentityError(f"{label} is present")
    finally:
        for descriptor in reversed(opened):
            try:
                os.close(descriptor)
            except OSError:
                pass


def _reject_promisor_packs(objects_fd: int) -> None:
    try:
        pack_fd = os.open(b"pack", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=objects_fd)
    except FileNotFoundError:
        return
    except OSError as error:
        raise SourceIdentityError("Git pack directory cannot be checked") from error
    try:
        with os.scandir(pack_fd) as entries:
            for entry in entries:
                if os.fsencode(entry.name).endswith(b".promisor"):
                    raise SourceIdentityError("promisor Git object metadata is present")
    finally:
        os.close(pack_fd)


def _validate_repository_policy(view: _GitView) -> None:
    shallow = _git(view, ["rev-parse", "--is-shallow-repository"])
    if shallow.strip() != b"false":
        raise SourceIdentityError("shallow Git repository is not accepted")
    bare = _git(view, ["rev-parse", "--is-bare-repository"])
    if bare.strip() != b"false":
        raise SourceIdentityError("bare Git repository is not accepted")
    config = _git(view, ["config", "--local", "--no-includes", "--null", "--list"])
    for record in config.split(b"\x00"):
        if not record:
            continue
        if b"\n" not in record:
            raise SourceIdentityError("Git configuration is malformed")
        key, value = record.split(b"\n", 1)
        lowered = key.lower()
        value_lower = value.strip().lower()
        if (
            lowered == b"core.worktree"
            or lowered == b"core.fsmonitor"
            or lowered == b"core.hookspath"
            or lowered.startswith(b"filter.")
            or lowered.startswith(b"include.")
            or lowered.startswith(b"includeif.")
            or (lowered.endswith(b".promisor") and value_lower in (b"true", b"yes", b"on", b"1"))
            or lowered == b"extensions.partialclone"
            or lowered == b"extensions.worktreeconfig"
            or (lowered == b"core.bare" and value_lower in (b"true", b"yes", b"on", b"1"))
        ):
            raise SourceIdentityError("Git configuration policy is not accepted")

    # These are deliberately checked by descriptor-relative directory entries,
    # not by ambient pathname lookups.  Any presence means the object view is
    # not a complete local repository snapshot.
    checked: set[tuple[int, bytes]] = set()
    for directory_fd, name, label in (
        (view.git_dir.fd, b"shallow", "shallow metadata"),
        (view.common_dir.fd, b"shallow", "shallow metadata"),
        (view.git_dir.fd, b"info/grafts", "grafts metadata"),
        (view.common_dir.fd, b"info/grafts", "grafts metadata"),
        (view.common_dir.fd, b"objects/info/alternates", "alternate metadata"),
    ):
        key = (directory_fd, name)
        if key not in checked:
            checked.add(key)
            _reject_present(directory_fd, name, label)
    _reject_promisor_packs(view.objects.fd)
    replace = _git(view, ["for-each-ref", "--format=%(refname)", "refs/replace/"])
    if replace:
        raise SourceIdentityError("replacement refs are not accepted")


def _object_format(view: _GitView) -> str:
    raw = _git(view, ["rev-parse", "--show-object-format"])
    values = _parse_lines(raw, "object format")
    if len(values) != 1 or values[0] not in (b"sha1", b"sha256"):
        raise SourceIdentityError("Git object format is invalid")
    return values[0].decode("ascii")


def _revision(view: _GitView) -> str:
    object_type = _git(view, ["cat-file", "-t", "HEAD"])
    if _parse_lines(object_type, "HEAD object type") != [b"commit"]:
        raise SourceIdentityError("Git HEAD does not name a commit")
    raw = _git(view, ["rev-parse", "--verify", "HEAD"])
    values = _parse_lines(raw, "HEAD")
    if len(values) != 1 or not HEX.fullmatch(values[0]) or len(values[0]) not in (40, 64):
        raise SourceIdentityError("Git HEAD is invalid")
    return values[0].decode("ascii")


def _tree_id(view: _GitView) -> str:
    raw = _git(view, ["rev-parse", "--verify", "HEAD^{tree}"])
    values = _parse_lines(raw, "tree")
    if len(values) != 1 or not HEX.fullmatch(values[0]) or len(values[0]) not in (40, 64):
        raise SourceIdentityError("Git tree is invalid")
    return values[0].decode("ascii")


def _read_index(view: _GitView) -> str:
    view.index.assert_stable()
    size = view.index.initial.size
    if size < 12 or size > MAX_INDEX_BYTES:
        raise SourceIdentityError("Git index preimage has an invalid size")
    digest = hashlib.sha256()
    header = b""
    offset = 0
    try:
        while offset < size:
            chunk = os.pread(view.index.fd, min(READ_CHUNK, size - offset), offset)
            if not chunk:
                raise SourceIdentityError("Git index changed while reading")
            if len(header) < 12:
                header += chunk[: 12 - len(header)]
            digest.update(chunk)
            offset += len(chunk)
    except OSError as error:
        raise SourceIdentityError("Git index is not readable") from error
    view.index.assert_stable()
    if offset != size or not header.startswith(b"DIRC"):
        raise SourceIdentityError("Git index preimage is invalid")
    return digest.hexdigest()


def _parse_ls_tree(raw: bytes, width: int) -> list[tuple[bytes, str, str, str]]:
    entries: list[tuple[bytes, str, str, str]] = []
    seen: set[bytes] = set()
    for record in raw.split(b"\x00"):
        if not record:
            continue
        try:
            metadata, path = record.split(b"\t", 1)
            mode, kind, object_id = metadata.split(b" ", 2)
        except ValueError as error:
            raise SourceIdentityError("Git tree record is malformed") from error
        if not path or b"\x00" in path or path.startswith(b"/") or b"//" in path:
            raise SourceIdentityError("Git tree path is invalid")
        if path in seen:
            raise SourceIdentityError("Git tree path is duplicated")
        seen.add(path)
        if len(object_id) != width or not HEX.fullmatch(object_id):
            raise SourceIdentityError("Git tree object ID is invalid")
        if kind not in (b"tree", b"blob"):
            raise SourceIdentityError("Git tree contains an unsupported object")
        if mode not in (b"040000", b"100644", b"100755", b"120000"):
            raise SourceIdentityError("Git tree mode is invalid")
        expected_kind = "dir" if kind == b"tree" else "file"
        if mode == b"120000":
            expected_kind = "symlink"
        entries.append((path, expected_kind, mode.decode("ascii"), object_id.decode("ascii")))
    if len(entries) > MAX_ENTRIES:
        raise SourceIdentityError("Git tree has too many entries")
    entries.sort(key=lambda entry: entry[0])
    return entries


@dataclass(frozen=True)
class OutputExceptionMetadata:
    label: str
    present: bool
    kind: str | None
    mode: str | None
    link_count: int | None
    bytes_consumed: bool = False


@dataclass(frozen=True)
class SourceEntrySnapshot:
    path: bytes
    kind: str
    descriptor: DescriptorSnapshot
    symlink_target: bytes | None


@dataclass(frozen=True)
class SourceIdentity:
    kind: str
    revision: str
    tree_id: str
    object_format: str
    index_sha256: str
    manifest_bytes: bytes
    manifest_sha256: str
    exceptions: tuple[OutputExceptionMetadata, ...]
    descriptor_snapshots: tuple[tuple[str, DescriptorSnapshot], ...]
    entry_snapshots: tuple[SourceEntrySnapshot, ...]


def _stat_snapshot(value: os.stat_result) -> DescriptorSnapshot:
    return DescriptorSnapshot(
        value.st_dev,
        value.st_ino,
        stat.S_IFMT(value.st_mode),
        stat.S_IMODE(value.st_mode),
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _mode(value: int) -> str:
    return f"{stat.S_IMODE(value):04o}"


def _hash_object(object_format: str, kind: str, content: bytes) -> str:
    if object_format == "sha1":
        digest = hashlib.sha1()
    elif object_format == "sha256":
        digest = hashlib.sha256()
    else:  # defensive: callers validate the format before object lookup.
        raise SourceIdentityError("Git object format is invalid")
    digest.update(kind.encode("ascii"))
    digest.update(b" ")
    digest.update(str(len(content)).encode("ascii"))
    digest.update(b"\x00")
    digest.update(content)
    return digest.hexdigest()


def _read_source_file(parent_fd: int, name: bytes) -> tuple[DescriptorSnapshot, bytes]:
    descriptor = _open_at(parent_fd, name, READ_FLAGS, "source file")
    try:
        if descriptor.initial.file_type != stat.S_IFREG or descriptor.initial.links != 1:
            raise SourceIdentityError("source file is not a single-link regular file")
        if descriptor.initial.size > MAX_FILE_BYTES:
            raise SourceIdentityError("source file exceeds its byte bound")
        content = _read_fd(descriptor.fd, MAX_FILE_BYTES, "source file")
        descriptor.assert_stable()
        return descriptor.initial, content
    finally:
        descriptor.close()


def _directory_mode(snapshot: DescriptorSnapshot, label: str) -> str:
    mode = snapshot.mode
    if snapshot.file_type != stat.S_IFDIR or mode & 0o7000 or mode & 0o700 != 0o700:
        raise SourceIdentityError(f"{label} mode is not accepted")
    return f"{mode:04o}"


def _exception_metadata(view: _GitView, kind: str, tree_paths: set[bytes]) -> tuple[OutputExceptionMetadata, ...]:
    git_snapshot = view.root_git.initial
    git_kind = "directory" if git_snapshot.file_type == stat.S_IFDIR else "regular"
    values = [
        OutputExceptionMetadata("git", True, git_kind, f"{git_snapshot.mode:04o}", git_snapshot.links)
    ]

    def optional(name: bytes, label: str, expected: str) -> OutputExceptionMetadata:
        if name in tree_paths:
            raise SourceIdentityError(f"tracked root {label} output is not accepted")
        try:
            value = os.stat(name, dir_fd=view.worktree.fd, follow_symlinks=False)
        except FileNotFoundError:
            return OutputExceptionMetadata(label, False, None, None, None)
        except OSError as error:
            raise SourceIdentityError(f"root {label} output cannot be checked") from error
        snapshot = _stat_snapshot(value)
        if expected == "directory":
            if (
                snapshot.file_type != stat.S_IFDIR
                or snapshot.mode & 0o7000
                or snapshot.mode & 0o700 != 0o700
                or snapshot.mode & 0o022
            ):
                raise SourceIdentityError(f"root {label} output has an invalid type or mode")
        elif (
            snapshot.file_type != stat.S_IFREG
            or snapshot.links != 1
            or snapshot.mode not in (0o644, 0o755)
        ):
            raise SourceIdentityError(f"root {label} output has an invalid type, link count, or mode")
        return OutputExceptionMetadata(label, True, expected, f"{snapshot.mode:04o}", snapshot.links)

    values.append(optional(b"target", "target", "directory"))
    if kind == "project-source":
        values.append(optional(b"main", "main", "regular"))
    else:
        values.append(OutputExceptionMetadata("main", False, None, None, None))
    return tuple(values)


def _tracked_index_paths(view: _GitView, expected: set[bytes]) -> None:
    staged = _git(
        view,
        ["diff-index", "--cached", "--name-only", "-z", "HEAD", "--"],
        max_output=MAX_GIT_LIST_BYTES,
    )
    if staged:
        raise SourceIdentityError("Git index does not match HEAD")
    raw = _git(view, ["ls-files", "-v", "-z", "--"], max_output=MAX_GIT_LIST_BYTES)
    paths: set[bytes] = set()
    for record in raw.split(b"\x00"):
        if not record:
            continue
        if len(record) < 3 or record[1:2] != b" " or record[:1] != b"H":
            raise SourceIdentityError("Git index flags are not accepted")
        path = record[2:]
        if not path or path in paths:
            raise SourceIdentityError("Git index path is invalid")
        paths.add(path)
    if paths != expected:
        raise SourceIdentityError("Git index paths do not match HEAD")


def _list_directory(fd: int, remaining: int) -> list[bytes]:
    names: list[bytes] = []
    try:
        with os.scandir(fd) as entries:
            for entry in entries:
                if len(names) > remaining + 3:
                    raise SourceIdentityError("source root has too many directory entries")
                name = os.fsencode(entry.name)
                if not name or b"/" in name or b"\x00" in name:
                    raise SourceIdentityError("source directory entry name is invalid")
                names.append(name)
    except OSError as error:
        raise SourceIdentityError("source directory cannot be enumerated") from error
    names.sort()
    return names


def _resolve_symlink(path: bytes, target: bytes, entries: Mapping[bytes, SourceEntrySnapshot]) -> None:
    if not target or target.startswith(b"/") or b"\x00" in target:
        raise SourceIdentityError("source symlink target is not contained")
    resolved = path.split(b"/")[:-1]
    pending = target.split(b"/")
    followed: set[bytes] = set()
    while pending:
        component = pending.pop(0)
        if component in (b"", b"."):
            continue
        if component == b"..":
            if not resolved:
                raise SourceIdentityError("source symlink target escapes its root")
            resolved.pop()
            continue
        resolved.append(component)
        candidate = b"/".join(resolved)
        entry = entries.get(candidate)
        if entry is None:
            raise SourceIdentityError("source symlink target is not tracked")
        if entry.kind == "symlink":
            if candidate in followed or entry.symlink_target is None:
                raise SourceIdentityError("source symlink target is cyclic")
            followed.add(candidate)
            nested = entry.symlink_target
            if nested.startswith(b"/"):
                raise SourceIdentityError("source symlink target is absolute")
            resolved.pop()
            pending = nested.split(b"/") + pending
        elif pending and entry.kind != "dir":
            raise SourceIdentityError("source symlink traverses a non-directory")


def _verify_tree_objects(
    entries: list[tuple[bytes, str, str, str]], object_format: str, tree_id: str
) -> None:
    by_path = {path: (kind, mode, object_id) for path, kind, mode, object_id in entries}
    children: dict[bytes, list[bytes]] = {b"": []}
    for path, kind, _, _ in entries:
        parent = path.rsplit(b"/", 1)[0] if b"/" in path else b""
        children.setdefault(parent, []).append(path)
        if kind == "dir":
            children.setdefault(path, [])
    computed: dict[bytes, str] = {}
    directories = sorted(
        children,
        key=lambda value: value.count(b"/") + (1 if value else 0),
        reverse=True,
    )
    for directory in directories:
        body = bytearray()
        ordered = sorted(
            children[directory],
            key=lambda path: path.rsplit(b"/", 1)[-1]
            + (b"/" if by_path[path][0] == "dir" else b"\x00"),
        )
        for path in ordered:
            child_kind, git_mode, object_id = by_path[path]
            if child_kind == "dir":
                object_id = computed[path]
                mode_bytes = b"40000"
            else:
                mode_bytes = git_mode.encode("ascii")
            name = path.rsplit(b"/", 1)[-1]
            body.extend(mode_bytes + b" " + name + b"\x00" + bytes.fromhex(object_id))
        object_id = _hash_object(object_format, "tree", bytes(body))
        computed[directory] = object_id
        if directory:
            expected = by_path[directory][2]
            if object_id != expected:
                raise SourceIdentityError("Git directory object does not match its entries")
    if computed[b""] != tree_id:
        raise SourceIdentityError("Git root tree object does not match its entries")


def _verify_object_store(
    view: _GitView,
    tree_entries: list[tuple[bytes, str, str, str]],
    tree_id: str,
    manifest_entries: list[OrderedDict[str, Any]],
) -> None:
    sizes = {bytes.fromhex(entry["path_hex"]): entry["size"] for entry in manifest_entries}
    expected: dict[str, tuple[str, int | None]] = {tree_id: ("tree", None)}
    for path, kind, _, object_id in tree_entries:
        value = ("tree", None) if kind == "dir" else ("blob", sizes[path])
        prior = expected.get(object_id)
        if prior is not None and prior != value:
            raise SourceIdentityError("Git object is used with conflicting semantics")
        expected[object_id] = value
    object_ids = sorted(expected)
    if len(object_ids) > MAX_OBJECT_IDS:
        raise SourceIdentityError("Git source has too many object identities")
    for offset in range(0, len(object_ids), 32):
        batch = object_ids[offset : offset + 32]
        raw = _git(
            view,
            ["cat-file", "--batch-check=%(objectname) %(objecttype) %(objectsize)"],
            input_bytes=b"".join(object_id.encode("ascii") + b"\n" for object_id in batch),
            max_output=64 * 1024,
        )
        lines = _parse_lines(raw, "Git object query")
        if len(lines) != len(batch):
            raise SourceIdentityError("Git object query is incomplete")
        for requested, line in zip(batch, lines, strict=True):
            fields = line.split(b" ")
            if len(fields) != 3:
                raise SourceIdentityError("Git source object is missing")
            object_id, object_type, size_bytes = fields
            try:
                object_size = int(size_bytes)
            except ValueError as error:
                raise SourceIdentityError("Git object size is invalid") from error
            expected_type, expected_size = expected[requested]
            if (
                object_id.decode("ascii", "strict") != requested
                or object_type.decode("ascii", "strict") != expected_type
                or object_size < 0
                or (expected_size is not None and object_size != expected_size)
            ):
                raise SourceIdentityError("Git object type or size does not match the source")


def _enumerate_source(
    view: _GitView,
    kind: str,
    tree_entries: list[tuple[bytes, str, str, str]],
    object_format: str,
) -> tuple[list[OrderedDict[str, Any]], tuple[SourceEntrySnapshot, ...], tuple[OutputExceptionMetadata, ...]]:
    tree = {path: (entry_kind, mode, object_id) for path, entry_kind, mode, object_id in tree_entries}
    tree_paths = set(tree)
    exceptions = _exception_metadata(view, kind, tree_paths)
    manifest_entries: list[OrderedDict[str, Any]] = []
    snapshots: list[SourceEntrySnapshot] = []
    observed: set[bytes] = set()
    folded: set[bytes] = set()
    total_file_bytes = 0
    raw_path_link_bytes = 0

    root_fd = os.open(
        b".", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=view.worktree.fd
    )
    root = _OwnedFD(root_fd, "source-enumeration-root")
    try:
        if root.initial != view.worktree._final.initial:
            raise SourceIdentityError("source root descriptor identity changed")

        def walk(directory_fd: int, prefix: bytes, depth: int) -> None:
            nonlocal total_file_bytes, raw_path_link_bytes
            if depth > MAX_DEPTH:
                raise SourceIdentityError("source tree exceeds its depth bound")
            for name in _list_directory(directory_fd, MAX_ENTRIES - len(observed)):
                path = prefix + b"/" + name if prefix else name
                if not prefix and name == b".git":
                    continue
                if name == b".git":
                    raise SourceIdentityError("nested Git control entry is not accepted")
                if not prefix and name == b"target":
                    continue
                if not prefix and kind == "project-source" and name == b"main":
                    continue
                if path in observed or len(observed) >= MAX_ENTRIES or len(path) > MAX_PATH_BYTES:
                    raise SourceIdentityError("source path count or length is invalid")
                folded_path = path.lower()
                if folded_path in folded:
                    raise SourceIdentityError("case-fold-colliding source paths are not accepted")
                folded.add(folded_path)
                observed.add(path)
                raw_path_link_bytes += len(path)
                if raw_path_link_bytes > MAX_RAW_PATH_LINK_BYTES:
                    raise SourceIdentityError("source paths exceed their byte bound")
                expected = tree.get(path)
                if expected is None:
                    raise SourceIdentityError("untracked or ignored source input is not accepted")
                try:
                    raw_stat = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                except OSError as error:
                    raise SourceIdentityError("source entry cannot be inspected") from error
                before = _stat_snapshot(raw_stat)
                entry_kind, git_mode, git_object = expected
                mode_value: str | None
                staged_mode: str | None
                size: int
                digest: str | None
                target_hex: str | None
                target: bytes | None = None
                if before.file_type == stat.S_IFDIR:
                    if entry_kind != "dir":
                        raise SourceIdentityError("source directory does not match Git")
                    mode_value = _directory_mode(before, "source directory")
                    staged_mode = "0700"
                    size = 0
                    digest = None
                    target_hex = None
                    child_fd = os.open(
                        name,
                        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                        dir_fd=directory_fd,
                    )
                    child = _OwnedFD(child_fd, "source directory")
                    try:
                        if child.initial != before:
                            raise SourceIdentityError("source directory changed while opening")
                        walk(child.fd, path, depth + 1)
                        child.assert_stable()
                    finally:
                        child.close()
                elif before.file_type == stat.S_IFREG:
                    if entry_kind != "file" or before.mode not in (0o644, 0o755):
                        raise SourceIdentityError("source file type or mode does not match Git")
                    opened, content = _read_source_file(directory_fd, name)
                    if opened != before:
                        raise SourceIdentityError("source file changed while opening")
                    total_file_bytes += len(content)
                    if total_file_bytes > MAX_TOTAL_SOURCE_BYTES:
                        raise SourceIdentityError("source files exceed their byte bound")
                    digest = hashlib.sha256(content).hexdigest()
                    if _hash_object(object_format, "blob", content) != git_object:
                        raise SourceIdentityError("source file bytes do not match the Git object")
                    mode_value = f"{before.mode:04o}"
                    staged_mode = "0444" if before.mode == 0o644 else "0555"
                    size = len(content)
                    target_hex = None
                elif before.file_type == stat.S_IFLNK:
                    if entry_kind != "symlink":
                        raise SourceIdentityError("source symlink does not match Git")
                    try:
                        target = os.readlink(name, dir_fd=directory_fd)
                        target = os.fsencode(target) if isinstance(target, str) else target
                        after = _stat_snapshot(os.stat(name, dir_fd=directory_fd, follow_symlinks=False))
                    except OSError as error:
                        raise SourceIdentityError("source symlink cannot be read") from error
                    if before != after or not target or len(target) > MAX_SYMLINK_BYTES or b"\x00" in target:
                        raise SourceIdentityError("source symlink changed or exceeds its bound")
                    raw_path_link_bytes += len(target)
                    if raw_path_link_bytes > MAX_RAW_PATH_LINK_BYTES:
                        raise SourceIdentityError("source paths and links exceed their byte bound")
                    digest = hashlib.sha256(target).hexdigest()
                    if _hash_object(object_format, "blob", target) != git_object:
                        raise SourceIdentityError("source symlink target does not match the Git object")
                    mode_value = None
                    staged_mode = None
                    size = len(target)
                    target_hex = target.hex()
                else:
                    raise SourceIdentityError("special source entries are not accepted")
                snapshots.append(SourceEntrySnapshot(path, entry_kind, before, target))
                manifest_entries.append(
                    OrderedDict(
                        (
                            ("path_hex", path.hex()),
                            ("kind", entry_kind),
                            ("mode", mode_value),
                            ("staged_mode", staged_mode),
                            ("git_mode", git_mode),
                            ("git_object", git_object),
                            ("size", size),
                            ("sha256", digest),
                            ("symlink_target_hex", target_hex),
                        )
                    )
                )

        walk(root.fd, b"", 1)
        root.assert_stable()
    except OSError as error:
        raise SourceIdentityError("source root cannot be enumerated") from error
    finally:
        root.close()
    if observed != tree_paths:
        raise SourceIdentityError("source worktree paths do not match Git")
    combined = {entry.path: entry for entry in snapshots}
    for entry in snapshots:
        if entry.kind == "symlink" and entry.symlink_target is not None:
            _resolve_symlink(entry.path, entry.symlink_target, combined)
    manifest_entries.sort(key=lambda value: bytes.fromhex(value["path_hex"]))
    snapshots.sort(key=lambda value: value.path)
    return manifest_entries, tuple(snapshots), exceptions


def _descriptor_snapshots(view: _GitView) -> tuple[tuple[str, DescriptorSnapshot], ...]:
    return tuple(
        (f"{descriptor.label}:{index}", descriptor.initial)
        for index, descriptor in enumerate(view.descriptors())
    )


def _capture_identity(
    view: _GitView,
    *,
    kind: str,
    expected_revision: str,
    expected_object_format: str,
) -> SourceIdentity:
    view.assert_stable()
    _validate_repository_policy(view)
    object_format = _object_format(view)
    if object_format != expected_object_format or (kind == "align-source" and object_format != "sha1"):
        raise SourceIdentityError("Git object format does not match the expected source identity")
    revision = _revision(view)
    width = 40 if object_format == "sha1" else 64
    if len(revision) != width or revision != expected_revision:
        raise SourceIdentityError("Git HEAD does not match the expected source identity")
    tree_id = _tree_id(view)
    if len(tree_id) != width:
        raise SourceIdentityError("Git tree has the wrong object format")
    index_sha256 = _read_index(view)
    raw_tree = _git(
        view,
        ["ls-tree", "-r", "-t", "-z", "--full-tree", "HEAD"],
        max_output=MAX_GIT_LIST_BYTES,
    )
    tree_entries = _parse_ls_tree(raw_tree, width)
    leaf_paths = {path for path, entry_kind, _, _ in tree_entries if entry_kind != "dir"}
    _tracked_index_paths(view, leaf_paths)
    _verify_tree_objects(tree_entries, object_format, tree_id)
    entries, entry_snapshots, exceptions = _enumerate_source(view, kind, tree_entries, object_format)
    _verify_object_store(view, tree_entries, tree_id, entries)
    root_mode = _directory_mode(view.worktree._final.initial, "source root")
    manifest: OrderedDict[str, Any] = OrderedDict(
        (
            ("schema_version", 1),
            ("kind", kind),
            ("revision", revision),
            ("tree_id", tree_id),
            ("object_format", object_format),
            ("index_sha256", index_sha256),
            ("root_mode", root_mode),
            ("root_staged_mode", "0700"),
            ("entries", entries),
            (
                "exceptions",
                OrderedDict(
                    (
                        ("git", "root-git-control"),
                        ("target", "root-directory-output"),
                        ("main", "root-file-output" if kind == "project-source" else None),
                    )
                ),
            ),
        )
    )
    validate_source_manifest(manifest)
    manifest_bytes = canonical_source_manifest_bytes(manifest)
    manifest_sha256 = serialized_source_manifest_digest(manifest)
    view.assert_stable()
    return SourceIdentity(
        kind,
        revision,
        tree_id,
        object_format,
        index_sha256,
        manifest_bytes,
        manifest_sha256,
        exceptions,
        _descriptor_snapshots(view),
        entry_snapshots,
    )


class SourceIdentityHandle:
    def __init__(
        self,
        view: _GitView,
        identity: SourceIdentity,
        expected_revision: str,
        expected_object_format: str,
    ) -> None:
        self._view = view
        self.identity = identity
        self._expected_revision = expected_revision
        self._expected_object_format = expected_object_format
        self._closed = False

    def recheck(self) -> None:
        if self._closed:
            raise SourceIdentityError("source identity handle is closed")
        current = _capture_identity(
            self._view,
            kind=self.identity.kind,
            expected_revision=self._expected_revision,
            expected_object_format=self._expected_object_format,
        )
        if current != self.identity:
            raise SourceIdentityError("source identity changed")

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        _close_view(self._view)

    def __enter__(self) -> "SourceIdentityHandle":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def _capture(
    worktree: DirectoryHandle,
    *,
    kind: str,
    expected_revision: str,
    expected_object_format: str,
) -> SourceIdentityHandle:
    view: _GitView | None = None
    try:
        view = _open_git_view(worktree, kind=kind)
        identity = _capture_identity(
            view,
            kind=kind,
            expected_revision=expected_revision,
            expected_object_format=expected_object_format,
        )
        return SourceIdentityHandle(view, identity, expected_revision, expected_object_format)
    except Exception:
        if view is not None:
            try:
                _close_view(view)
            except SourceIdentityError:
                pass
        else:
            try:
                worktree.close()
            except SourceIdentityError:
                pass
        raise


def capture_project_source(
    root_fd: int, expected_head: str, expected_object_format: str
) -> SourceIdentityHandle:
    if expected_object_format not in ("sha1", "sha256"):
        raise SourceIdentityError("expected project object format is invalid")
    width = 40 if expected_object_format == "sha1" else 64
    try:
        encoded = expected_head.encode("ascii")
    except (AttributeError, UnicodeEncodeError) as error:
        raise SourceIdentityError("expected project HEAD is invalid") from error
    if len(encoded) != width or not HEX.fullmatch(encoded):
        raise SourceIdentityError("expected project HEAD is invalid")
    descriptor = _duplicate(root_fd, "project-root")
    worktree = DirectoryHandle([descriptor], descriptor)
    return _capture(
        worktree,
        kind="project-source",
        expected_revision=expected_head,
        expected_object_format=expected_object_format,
    )


def capture_align_source(
    project_root_fd: int, align_repo_relative: str | bytes, expected_revision: str
) -> SourceIdentityHandle:
    if not isinstance(expected_revision, str) or not REVISION.fullmatch(expected_revision):
        raise SourceIdentityError("expected Align revision is invalid")
    worktree = open_relative_directory(project_root_fd, align_repo_relative)
    return _capture(
        worktree,
        kind="align-source",
        expected_revision=expected_revision,
        expected_object_format="sha1",
    )
