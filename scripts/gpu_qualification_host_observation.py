#!/usr/bin/env python3
"""Observe host facts and bind driver identity to the device used by native generation."""
from __future__ import annotations

import csv
import io
import os
import pathlib
import platform
import re
import stat
import time
from collections.abc import Callable, Mapping

from gpu_backend_recipe import RecipeError, bounded_i64
from gpu_qualification_host import _find, _platform
from gpu_qualifier_process import run_owned_command

I64_MAX = (1 << 63) - 1
Probe = Callable[..., str]
DEVICE_IDENTITY = ("bundle_id", "device_name", "device_description", "device_id", "device_total_bytes")


def probe_owner(*, work: pathlib.Path, home: pathlib.Path, temporary: pathlib.Path,
                deadline_ns: int) -> Probe:
    def probe(name: str, *arguments: str) -> str:
        tool = _find(name)
        token = "<host-probe>:sha256:" + tool.sha256
        result = run_owned_command(kind="compiler_materialize",
            physical_argv=(str(tool.path), *arguments), logical_argv=(token, *arguments),
            mappings={token: tool}, cwd=work, home=home, temporary=temporary,
            timeout_seconds=15, deadline_ns=deadline_ns)
        if result.terminal != "PASS" or result.stdout.truncated \
                or result.descendants_before or result.descendants_after:
            raise RecipeError("host observation probe did not complete")
        return _text(result.stdout.retained, 65536)
    return probe


def _text(raw: bytes, limit: int) -> str:
    try:
        value = raw.decode("utf-8", errors="strict").strip()
    except UnicodeDecodeError as error:
        raise RecipeError("host observation is not UTF-8") from error
    if not value or len(raw) > limit or "\x00" in value:
        raise RecipeError("host observation is empty or outside its bound")
    return value


def _system_text(path: pathlib.Path) -> str:
    descriptor = os.open(path.resolve(strict=True), os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise RecipeError("host observation source is not a regular system file")
        data = bytearray()
        while len(data) <= 4 * 1024 * 1024:
            chunk = os.read(descriptor, min(65536, 4 * 1024 * 1024 + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
        return _text(bytes(data), 4 * 1024 * 1024)
    finally:
        os.close(descriptor)


def _positive(text: str) -> int:
    if not re.fullmatch(r"[0-9]+", text):
        raise RecipeError("host integer observation is malformed")
    return bounded_i64(int(text), 1, I64_MAX, "host integer observation")


def observe_host(*, expected_platform: str, backend: str, probe: Probe,
                 deadline_ns: int) -> dict[str, object]:
    actual_platform = _platform()
    arch = {"arm64": "aarch64", "aarch64": "aarch64", "x86_64": "x86_64"}.get(platform.machine())
    if actual_platform != expected_platform or arch is None or backend not in {"metal", "cuda"}:
        raise RecipeError("observed host does not match a supported profile")
    if actual_platform == "macos":
        version = probe("/usr/bin/sw_vers", "-productVersion")
        build = probe("/usr/bin/sw_vers", "-buildVersion")
        os_version = version + " (" + build + ")"
        cpu = probe("/usr/sbin/sysctl", "-n", "machdep.cpu.brand_string")
        total = _positive(probe("/usr/sbin/sysctl", "-n", "hw.memsize"))
        memory = probe("/usr/bin/vm_stat")
        sizes = re.findall(r"\(page size of ([0-9]+) bytes\)", memory)
        free_pages = re.findall(r"^Pages free:\s+([0-9]+)\.\s*$", memory, re.MULTILINE)
        if len(sizes) != 1 or len(free_pages) != 1:
            raise RecipeError("host free-page observation is malformed")
        free = _positive(sizes[0]) * int(free_pages[0])
    else:
        release = _system_text(pathlib.Path("/etc/os-release"))
        versions = re.findall(r'^PRETTY_NAME=(.*)$', release, re.MULTILINE)
        if len(versions) != 1:
            raise RecipeError("host OS identity is absent or ambiguous")
        os_version = versions[0].strip('"')
        cpus = re.findall(r"^model name\s*:\s*(.+)$", _system_text(pathlib.Path("/proc/cpuinfo")), re.MULTILINE)
        if not cpus or len(set(cpus)) != 1:
            raise RecipeError("host CPU identity is absent or inconsistent")
        cpu = cpus[0]
        page = bounded_i64(os.sysconf("SC_PAGE_SIZE"), 1, I64_MAX, "host page size")
        total = page * bounded_i64(os.sysconf("SC_PHYS_PAGES"), 1, I64_MAX, "host total pages")
        free = page * bounded_i64(os.sysconf("SC_AVPHYS_PAGES"), 0, I64_MAX, "host free pages")
    kernel = platform.release()
    for value in (os_version, cpu, kernel):
        _text(value.encode(), 4096)
        if "\n" in value or "\r" in value:
            raise RecipeError("host identity has multiple lines")
    bounded_i64(total, 1, I64_MAX, "host total bytes")
    bounded_i64(free, 0, total, "host free bytes")
    logical = bounded_i64(os.cpu_count(), 1, I64_MAX, "host logical CPUs")
    if time.monotonic_ns() >= deadline_ns:
        raise RecipeError("host observation deadline expired")
    return dict(platform=actual_platform, os_version=os_version, kernel=kernel, arch=arch,
        wsl=actual_platform == "wsl2", cpu=cpu, logical_cpus=logical,
        host_total_bytes=total, host_free_bytes=free, backend=backend, device_state="unavailable",
        registry_device="", device_description="", driver="", gpu_architecture="",
        device_total_bytes=0, device_free_bytes=0)


def pci_id(value: str) -> str:
    match = re.fullmatch(r"([0-9a-fA-F]{4}|[0-9a-fA-F]{8}):([0-9a-fA-F]{2}):([0-9a-fA-F]{2})\.([0-7])", value)
    if match is None:
        raise RecipeError("native CUDA PCI identity is malformed")
    domain, bus, device, function = (int(part, 16) for part in match.groups())
    if domain > 65535 or device > 31:
        raise RecipeError("native CUDA PCI identity is out of range")
    return f"{domain:04x}:{bus:02x}:{device:02x}.{function}"


def observe_device(host: Mapping[str, object], observation: Mapping[str, object], *,
                   bundle: Mapping[str, object], probe: Probe, deadline_ns: int) -> dict[str, object]:
    if observation.get("available") is not True or observation["bundle_id"] != bundle["bundle_id"] \
            or host["backend"] != bundle["backend"]:
        raise RecipeError("host device lacks its native bundle observation")
    description = observation["device_description"]
    if bundle["backend"] == "metal":
        match = re.fullmatch(r"Apple M([1-9][0-9]*)(?: (Pro|Max|Ultra))?", description)
        if host["platform"] != "macos" or match is None:
            raise RecipeError("observed Metal architecture is unsupported")
        architecture = "apple_m" + match[1] + ("_" + match[2].lower() if match[2] else "")
        driver = "macOS integrated " + str(host["os_version"]) + "; kernel " + str(host["kernel"])
    else:
        requested = pci_id(observation["device_id"])
        raw = probe("nvidia-smi", "--query-gpu=pci.bus_id,name,driver_version,compute_cap",
                    "--format=csv,noheader,nounits")
        found = {}
        try:
            for row in csv.reader(io.StringIO(raw), strict=True):
                if len(row) != 4 or len(found) >= 256:
                    raise RecipeError("CUDA device probe row is malformed")
                identity, name, version, capability = (field.strip() for field in row)
                identity = pci_id(identity)
                if identity in found or not name or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)+", version) \
                        or not re.fullmatch(r"[1-9][0-9]*\.[0-9]", capability):
                    raise RecipeError("CUDA device probe identity is malformed or ambiguous")
                found[identity] = (name, version, "sm_" + capability.replace(".", ""))
        except csv.Error as error:
            raise RecipeError("CUDA device probe CSV is malformed") from error
        if requested not in found or found[requested][0] != description:
            raise RecipeError("CUDA probe does not identify the native device")
        _, driver, architecture = found[requested]
    if architecture not in bundle["target"]["gpu_architectures"]:
        raise RecipeError("native device architecture is outside the bundle target")
    total = bounded_i64(observation["device_total_bytes"], 1, I64_MAX, "device total bytes")
    free = bounded_i64(observation["device_free_bytes"], 0, total, "device free bytes")
    if time.monotonic_ns() >= deadline_ns:
        raise RecipeError("device observation deadline expired")
    return {**host, "device_state": "available", "registry_device": observation["device_name"],
            "device_description": description, "driver": driver, "gpu_architecture": architecture,
            "device_total_bytes": total, "device_free_bytes": free}


def same_device(first: Mapping[str, object], current: Mapping[str, object]) -> None:
    if any(first[key] != current[key] for key in DEVICE_IDENTITY):
        raise RecipeError("native GPU identity changed between generation cases")
