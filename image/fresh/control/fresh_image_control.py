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
import os
import re
import resource
import stat
import subprocess
import sys
import tempfile
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Mapping, Sequence

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


def _read_sealed(fd: int, *, limit: int) -> bytes:
    try:
        seals = fcntl.fcntl(fd, fcntl.F_GET_SEALS)
    except OSError as error:
        raise ControlError("TRUST", "supervisor", "input is not a sealable memfd") from error
    if seals != REQUIRED_SEALS:
        raise ControlError("TRUST", "supervisor", "input memfd has incomplete seals")
    before = _identity(fd)
    if not stat.S_ISREG(before.mode) or before.links != 0 or before.size > limit:
        raise ControlError("TRUST", "supervisor", "sealed input identity is invalid")
    os.lseek(fd, 0, os.SEEK_SET)
    try:
        raw = _read_exact_bounded(
            fd, limit=limit, deadline=time.monotonic() + SNAPSHOT_DEADLINE_SECONDS
        )
    except ControlError as error:
        raise ControlError("TRUST", "supervisor", "sealed input read rejected") from error
    if not _same_identity(before, _identity(fd)):
        raise ControlError("TRUST", "supervisor", "sealed input identity changed")
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
    if len(normalized.encode("utf-8")) > 4096:
        raise ControlError("ARGUMENT", "input", "ALIGN_REPO exceeds its byte bound")
    return normalized


def _mode_from_arguments(arguments: Sequence[str]) -> str:
    if list(arguments) == ["make", "--no-print-directory", "ci"]:
        return "ci"
    if list(arguments) == ["--mode", "build"]:
        return "build"
    if list(arguments) == ["--mode", "self-test"]:
        return "self-test"
    raise ControlError("ARGUMENT", "input", "request vector is not accepted")


def _reject_environment(environment: Mapping[str, str], *, mode: str) -> str:
    for name in FORBIDDEN_ENVIRONMENT:
        if name in environment:
            raise ControlError("ARGUMENT", "input", f"forbidden environment: {name}")
    for name in ("MAKEFLAGS", "GNUMAKEFLAGS", "MAKEOVERRIDES"):
        if environment.get(name, ""):
            raise ControlError("ARGUMENT", "input", f"nonempty {name}")
    align_repo = environment.get("ALIGN_REPO", "../align")
    if mode == "self-test" and "ALIGN_REPO" in environment:
        raise ControlError("ARGUMENT", "input", "self-test rejects ALIGN_REPO")
    return _normalize_relative(align_repo)


def _git_identity(project_fd: int, git_path: str) -> tuple[str, str]:
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
            result = subprocess.run(
                [git_path, "-c", "safe.directory=*", *arguments],
                cwd=cwd,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ControlError("SOURCE", "project-source", "Git identity probe failed") from error
        if result.returncode != 0 or len(result.stdout) > 128:
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


def supervise(
    arguments: Sequence[str],
    *,
    self_fd: int,
    image_fd: int | None = None,
    paths: ProfilePaths = ProfilePaths(),
) -> None:
    mode = _mode_from_arguments(arguments)
    align_repo = _reject_environment(os.environ, mode=mode)
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
    return subprocess.run(
        list(arguments),
        executable=f"/proc/self/fd/{descriptor}",
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C", "HOME": "/nonexistent"},
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        pass_fds=tuple(dict.fromkeys((descriptor, *pass_fds))),
        close_fds=True,
        timeout=timeout,
        check=False,
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
        result = subprocess.run(
            [temporary],
            env={},
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
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
    leaf: str | None = None
    try:
        parent = os.stat(cgroup_parent, follow_symlinks=False)
        if (
            not stat.S_ISDIR(parent.st_mode)
            or parent.st_uid != os.geteuid()
            or stat.S_IMODE(parent.st_mode) != 0o700
        ):
            raise OSError(errno.EPERM, "cgroup parent ownership mismatch")
        leaf = os.path.join(cgroup_parent, f"self-test-{os.getpid()}")
        os.mkdir(leaf, 0o700)
        with open(os.path.join(leaf, "pids.max"), "w", encoding="ascii") as output:
            output.write("512\n")
        with open(os.path.join(leaf, "pids.max"), encoding="ascii") as source:
            if source.read().strip() != "512":
                raise OSError(errno.EIO, "cgroup pids.max mismatch")
        limits = (
            (resource.RLIMIT_NPROC, 512),
            (resource.RLIMIT_NOFILE, 4096),
            (resource.RLIMIT_FSIZE, 536_870_912),
        )

        def admit_limited_child() -> None:
            for kind, limit in limits:
                resource.setrlimit(kind, (limit, limit))
            with open(os.path.join(leaf, "cgroup.procs"), "w", encoding="ascii") as target:
                target.write("0\n")

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
                "/" + leaf.removeprefix("/sys/fs/cgroup/"),
            ],
            env={"PATH": "/usr/bin:/bin", "LC_ALL": "C", "HOME": "/nonexistent"},
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            close_fds=True,
            preexec_fn=admit_limited_child,
            timeout=10,
            check=False,
        )
        if result.returncode != 0 or result.stdout != b"limited child: PASS\n" or result.stderr:
            raise OSError(errno.EIO, "cgroup/rlimit child rejected")
        with open(os.path.join(leaf, "cgroup.procs"), encoding="ascii") as source:
            if source.read().strip():
                raise OSError(errno.EBUSY, "cgroup child remained attached")
        os.rmdir(leaf)
    except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired) as error:
        raise ControlError("PLATFORM", "platform", "cgroup delegation is unavailable") from error
    finally:
        if leaf is not None:
            try:
                os.rmdir(leaf)
            except OSError:
                pass


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
    result = subprocess.run(
        arguments,
        env=WORKER_ENVIRONMENT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        pass_fds=(4, 7, 8, 9),
        close_fds=True,
        check=False,
        timeout=30 if mode == "self-test" else 300,
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
        supervise(values[2:], self_fd=10)
    except ControlError as error:
        return _emit_error(error)
    except Exception:
        return _emit_error(ControlError("INTERNAL", "internal"))
    return 1


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
    "_normalize_relative",
    "_reject_environment",
    "_sealed_memfd",
    "_read_sealed",
    "bootstrap_main",
    "supervisor_main",
]
