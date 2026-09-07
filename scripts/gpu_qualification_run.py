#!/usr/bin/env python3
"""Preparation state and pre-case FAIL evidence for the G1 GPU qualifier."""

from __future__ import annotations

import hashlib
import os
import pathlib
import stat
from collections.abc import Mapping, Sequence

from gpu_backend_recipe import MAX_BUNDLE_ARTIFACT_BYTES, RecipeError, canonical
from gpu_qualification_input import AdmittedInput
from gpu_qualification_publish import RetainedFile
from gpu_qualification_records import case_order_sha256
from gpu_qualifier_process import OwnedCommandResult, run_owned_command


PREPARATION = (
    ("compiler_materialize", "align_compiler", "helper"),
    ("runtime_materialize", "align_runtime", "helper"),
    ("shim_build", "shim", "shim"),
    ("candidate_build", "candidate", "helper"),
    ("cpu_reference_build", "cpu_reference", "helper"),
)


def unavailable_identity() -> dict[str, object]:
    return {"state": "unavailable", "name": "", "version": "", "sha256": ""}


def _artifact(path: pathlib.Path) -> tuple[bytes, str]:
    if not path.is_absolute():
        raise RecipeError("produced artifact path is not absolute")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags)
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 \
                or before.st_size > MAX_BUNDLE_ARTIFACT_BYTES:
            raise RecipeError("produced artifact is not a bounded single-link regular file")
        chunks: list[bytes] = []
        digest = hashlib.sha256()
        total = 0
        while True:
            chunk = os.read(descriptor, min(1024 * 1024, MAX_BUNDLE_ARTIFACT_BYTES - total + 1))
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_BUNDLE_ARTIFACT_BYTES:
                raise RecipeError("produced artifact exceeds its bound")
            chunks.append(chunk)
            digest.update(chunk)
        after = os.fstat(descriptor)
    except OSError as exc:
        raise RecipeError("produced artifact cannot be read") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
    fields = ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")
    if total != before.st_size or any(
        getattr(before, field) != getattr(after, field) for field in fields
    ):
        raise RecipeError("produced artifact changed while it was read")
    return b"".join(chunks), digest.hexdigest()


class PreparationState:
    def __init__(self, qualifier: pathlib.Path, *, name: str, version: str) -> None:
        data, sha256 = _artifact(qualifier.absolute())
        self.identities = {
            key: unavailable_identity() for _, key, _ in PREPARATION
        }
        self.qualifier_identity: dict[str, object] = {
            "state": "available", "name": name, "version": version, "sha256": sha256,
        }
        self.commands: list[dict[str, object]] = []
        self.retained: dict[str, RetainedFile] = {}
        self.failed_result: OwnedCommandResult | None = None
        self.failure_detail = ""
        self.elapsed_ns = 0
        self._retain(f"artifacts/{sha256}", RetainedFile("helper", data))

    def _retain(self, path: str, retained: RetainedFile) -> None:
        previous = self.retained.get(path)
        if previous is not None and previous != retained:
            raise RecipeError("produced artifact content-address collision")
        self.retained[path] = retained

    def run_step(
        self,
        *,
        physical_argv: Sequence[str],
        logical_argv: Sequence[str],
        mappings: Mapping[str, pathlib.Path],
        cwd: pathlib.Path,
        home: pathlib.Path,
        temporary: pathlib.Path,
        timeout_seconds: float,
        output: pathlib.Path,
        name: str,
        version: str,
    ) -> OwnedCommandResult:
        if self.failed_result is not None:
            raise RecipeError("preparation cannot continue after failure")
        ordinal = len(self.commands)
        if ordinal >= len(PREPARATION):
            raise RecipeError("preparation command sequence is complete")
        kind, identity_key, role = PREPARATION[ordinal]
        resolved_cwd = cwd.resolve(strict=True)
        output_absolute = output.absolute()
        try:
            output_parent = output_absolute.parent.resolve(strict=True)
        except OSError as exc:
            raise RecipeError("produced artifact parent is absent") from exc
        if output_parent != resolved_cwd and resolved_cwd not in output_parent.parents:
            raise RecipeError("produced artifact is outside the preparation root")
        if output_absolute.exists() or output_absolute.is_symlink():
            raise RecipeError("produced artifact output is occupied")
        result = run_owned_command(
            kind=kind,
            physical_argv=physical_argv,
            logical_argv=logical_argv,
            mappings=mappings,
            cwd=cwd,
            home=home,
            temporary=temporary,
            timeout_seconds=timeout_seconds,
        )
        self.commands.append(result.command)
        self.elapsed_ns += result.elapsed_ns
        if result.terminal == "PASS":
            try:
                data, sha256 = _artifact(output_absolute)
            except RecipeError:
                self._fail(result, "preparation output is absent or invalid")
            else:
                try:
                    self._retain(f"artifacts/{sha256}", RetainedFile(role, data))
                except RecipeError:
                    self._fail(result, "preparation output identity collides with another role")
                else:
                    self.identities[identity_key] = {
                        "state": "available", "name": name, "version": version, "sha256": sha256,
                    }
                    return result
        else:
            self._fail(result, f"preparation command {ordinal} did not pass")
        return result

    def _fail(self, result: OwnedCommandResult, detail: str) -> None:
        self.failed_result = result
        self.failure_detail = detail
        ordinal = len(self.commands) - 1
        for suffix, role, captured in (
            ("stdout", "stdout", result.stdout),
            ("stderr", "stderr", result.stderr),
        ):
            self._retain(
                f"logs/{ordinal:03d}.{suffix}",
                RetainedFile(
                    role,
                    captured.retained,
                    captured.original_bytes,
                    captured.original_sha256,
                ),
            )

    @property
    def complete(self) -> bool:
        return len(self.commands) == len(PREPARATION) and self.failed_result is None


def failure_evidence(
    admitted: AdmittedInput,
    preparation: PreparationState,
    *,
    align_revision: str,
    host: dict[str, object],
    category: str,
    stage: str,
    detail: str,
    owned_paths_removed: bool = True,
) -> dict[str, object]:
    """Construct a pre-case FAIL result; publication adds its exact retained file rows."""
    failed = preparation.failed_result
    if failed is None and not preparation.complete:
        raise RecipeError("pre-case failure evidence requires complete preparation")
    if failed is not None:
        ordinal = len(preparation.commands) - 1
        expected_stage = {
            "compiler_materialize": "compiler",
            "runtime_materialize": "runtime",
            "candidate_build": "candidate_build",
            "shim_build": "shim_build",
            "cpu_reference_build": "cpu_reference_build",
        }[PREPARATION[ordinal][0]]
        expected_category = "PREPARATION" if ordinal < 2 else "BUILD"
        if stage != expected_stage or category != expected_category:
            raise RecipeError("preparation failure does not match the failed command")
    profile = admitted.records["profile"]
    bundle = admitted.records["bundle"]
    calibrations = admitted.records["calibrations"]
    assert isinstance(profile, dict) and isinstance(bundle, dict) and isinstance(calibrations, list)
    models = profile["models"]
    assert isinstance(models, list)
    return {
        "schema_version": 1,
        "artifact_kind": "GPU_RUNTIME_EVIDENCE",
        "status": "FAIL",
        "suite": "generation",
        "profile_id": profile["profile_id"],
        "source": {
            "commit": admitted.align_source.manifest["commit"],
            "source_manifest_sha256": hashlib.sha256(
                admitted.align_source.manifest_raw,
            ).hexdigest(),
            "source_snapshot_sha256": admitted.align_source.snapshot_sha256,
            "align_revision": align_revision,
            "align_compiler": preparation.identities["align_compiler"],
            "align_runtime": preparation.identities["align_runtime"],
            "qualifier": preparation.qualifier_identity,
            "candidate": preparation.identities["candidate"],
            "shim": preparation.identities["shim"],
            "cpu_reference": preparation.identities["cpu_reference"],
        },
        "host": host,
        "bundle": {
            "manifest_sha256": hashlib.sha256(canonical(bundle)).hexdigest(),
            "bundle_id": bundle["bundle_id"],
            "ggml_source_manifest_sha256": hashlib.sha256(
                admitted.ggml_source.manifest_raw,
            ).hexdigest(),
            "ggml_source_snapshot_sha256": admitted.ggml_source.snapshot_sha256,
            "loaded_artifact_sha256s": [],
        },
        "inputs": {
            "profile_sha256": hashlib.sha256(canonical(profile)).hexdigest(),
            "models": [
                {
                    "model_id": model["model_id"],
                    "model_sha256": model["model_sha256"],
                    "pack_sha256": model["pack_sha256"],
                    "geometry_sha256": model["geometry_sha256"],
                }
                for model in models if isinstance(model, dict)
            ],
            "calibration_ids": [
                calibration["calibration_id"]
                for calibration in calibrations if isinstance(calibration, dict)
            ],
            "case_order_sha256": case_order_sha256(profile),
        },
        "preparation_commands": preparation.commands,
        "files": [],
        "cases": [],
        "aggregate": {
            "case_count": 0,
            "passed_count": 0,
            "failed_count": 0,
            "managed_host_peak_bytes": 0,
            "managed_device_peak_bytes": 0,
            "decision": "unmeasured",
        },
        "cleanup": {
            "descendants_before": 0 if failed is None else failed.descendants_before,
            "descendants_after": 0 if failed is None else failed.descendants_after,
            "owned_paths_removed": owned_paths_removed,
            "invocation_state_safe": True,
            "source_unchanged": True,
            "inputs_unchanged": True,
        },
        "failure": {
            "category": category,
            "stage": stage,
            "case_ordinal": -1,
            "detail": detail,
        },
        "elapsed_ns": max(1, preparation.elapsed_ns),
    }
