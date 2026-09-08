#!/usr/bin/env python3
"""CLI admission and invocation lifetime for the G1 GPU qualifier."""

from __future__ import annotations

import dataclasses
import pathlib
import shutil
import stat
import tempfile
import sys
from collections.abc import Sequence

from gpu_backend_recipe import RecipeError, canonical
from gpu_qualification_backend import StagedBackend, stage, _write
from gpu_qualification_input import AdmittedInput, admit
from gpu_qualification_publish import validate_output
from gpu_qualification_source import MaterializedSources, materialize
from gpu_compiler_materialize import managed_owner
from gpu_qualification_build import grouped_commands
from gpu_qualification_host import admit_host, _find
from gpu_qualification_run import PreparationState, run_preparation, _artifact
from gpu_qualification_native import prepare
from gpu_qualification_native_sequence import Plan
from gpu_qualification_records import parse_json_object
from gpu_qualifier_process import ToolchainExecutable


@dataclasses.dataclass(frozen=True)
class Arguments:
    profile: pathlib.Path
    suite: str
    output: pathlib.Path


@dataclasses.dataclass(frozen=True)
class Invocation:
    arguments: Arguments
    admitted: AdmittedInput
    root: pathlib.Path
    home: pathlib.Path
    temporary: pathlib.Path
    work: pathlib.Path
    sources: MaterializedSources
    backend: StagedBackend

    def cleanup(self) -> None:
        try:
            shutil.rmtree(self.root)
        except FileNotFoundError:
            pass


def parse_arguments(arguments: Sequence[str]) -> Arguments:
    values: dict[str, str] = {}
    ordinal = 0
    while ordinal < len(arguments):
        flag = arguments[ordinal]
        if flag not in {"--profile", "--suite", "--output"}:
            raise RecipeError("gpu qualifier argument is unknown")
        if flag in values:
            raise RecipeError("gpu qualifier argument is duplicated")
        ordinal += 1
        if ordinal >= len(arguments) or arguments[ordinal].startswith("--"):
            raise RecipeError("gpu qualifier argument has no value")
        value = arguments[ordinal]
        if not value or "\x00" in value:
            raise RecipeError("gpu qualifier argument value is invalid")
        values[flag] = value
        ordinal += 1
    if set(values) != {"--profile", "--suite", "--output"}:
        raise RecipeError("gpu qualifier arguments are incomplete")
    if values["--suite"] != "generation":
        raise RecipeError("gpu qualifier suite is unsupported")
    return Arguments(
        pathlib.Path(values["--profile"]),
        values["--suite"],
        pathlib.Path(values["--output"]),
    )


def _private_child(parent: pathlib.Path, name: str) -> pathlib.Path:
    child = parent / name
    child.mkdir(mode=0o700)
    metadata = child.stat(follow_symlinks=False)
    if not stat.S_ISDIR(metadata.st_mode) or metadata.st_mode & 0o077:
        raise RecipeError("gpu qualifier invocation child is not private")
    return child


def open_invocation(arguments: Arguments) -> Invocation:
    """Admit all retained input before creating one private, output-sibling invocation root."""
    admitted = admit(arguments.profile.absolute())
    destination, parent = validate_output(admitted, arguments.output)
    root: pathlib.Path | None = None
    try:
        root = pathlib.Path(tempfile.mkdtemp(prefix=f".{destination.name}.invoke-", dir=parent))
        root.chmod(0o700)
        home = _private_child(root, "home")
        temporary = _private_child(root, "tmp")
        work = _private_child(root, "work")
        sources = materialize(admitted, work)
        backend = stage(admitted, work)
        return Invocation(arguments, admitted, root, home, temporary, work, sources, backend)
    except BaseException:
        if root is not None and root.exists() and not root.is_symlink():
            shutil.rmtree(root)
        raise


def prepare_invocation(
    invocation: Invocation, state: PreparationState, *, entry_relative: str = "src/main.align",
) -> None:
    """Build the admitted source with the exact host bundle and its managed Align revision."""
    if state.commands or state.failure_ordinal is not None:
        raise RecipeError("invocation preparation requires a fresh state")
    try:
        profile = invocation.admitted.records["profile"]
        bundle = invocation.admitted.records["bundle"]
        host = admit_host(
            platform=profile["platform"], expected=bundle["toolchain"], work=invocation.work,
            home=invocation.home, temporary=invocation.temporary, deadline_ns=state.deadline_ns,
        )
        app = invocation.sources.align_llm
        owner = managed_owner(app / "scripts/align-toolchain")
        revision = owner.read_revision()
        compiler = owner.selected_path(owner.source_path(owner.cache_root(), revision), "compiler")
        entry = app / entry_relative
        if not entry.is_file() or app.resolve(strict=True) not in entry.resolve(strict=True).parents:
            raise RecipeError("qualification entry is outside its admitted source")
        planned = grouped_commands(
            work=invocation.work, compiler=compiler,
            python=ToolchainExecutable.admit(pathlib.Path(sys.executable)),
            helper=app / "scripts/gpu_compiler_materialize.py", git=_find("git"), copier=_find("cp"),
            entry=entry, shim_source=app / "scripts/ggml_shim.c",
            reference_shim_source=app / "scripts/ggml_shim.c",
            reference_project=app / "scripts/gpu_cpu_reference", ggml_source=invocation.sources.ggml,
            platform=host.platform, align_revision=revision, source_commit=profile["source"]["commit"],
            ggml_commit=bundle["ggml"]["commit"], tools=host.tools, sdk=host.sdk,
            support_archives=host.support_archives, ggml_include=invocation.sources.ggml / "ggml/include",
            backend_library=invocation.backend.root,
        )
    except (RecipeError, OSError, RuntimeError) as error:
        state.fail_unstarted("qualification preparation admission failed: " + str(error))
        return
    run_preparation(state, planned, cwd=invocation.work, home=invocation.home, temporary=invocation.temporary)


def native_plans(invocation: Invocation, state: PreparationState) -> tuple[Plan, ...]:
    """Bind frozen profile rows to the two completed native case executables."""
    if not state.complete:
        raise RecipeError("native cases require completed preparation")
    invocation.admitted.recheck()
    profile = invocation.admitted.records["profile"]
    bundle = invocation.admitted.records["bundle"]
    executables = {
        "cpu": ("cpu_reference", invocation.work / "cpu-reference/runtime_case"),
        "gpu_resident": ("candidate", invocation.work / "runtime_case"),
    }
    for key, path in executables.values():
        identity = state.identities[key]
        if identity["state"] != "available" or identity["version"] != profile["source"]["commit"] \
                or _artifact(path)[1] != identity["sha256"]:
            raise RecipeError("native executable differs from completed preparation")
    models = {model["model_id"]: model for model in profile["models"]}
    geometries = {key: parse_json_object(invocation.admitted.read_retained(
        model["geometry_path"], 16 * 1024 * 1024), 16 * 1024 * 1024)
        for key, model in models.items()}
    calibrations = {calibration["model"]["model_id"]: calibration
                    for calibration in invocation.admitted.records["calibrations"]}
    option = profile["runtime_options"][0]
    options_path = invocation.work / "runtime-case-options.json"
    plans = []
    for ordinal, row in enumerate(profile["cases"]):
        model = models[row["model_id"]]
        calibration = calibrations[row["model_id"]]
        frozen = next(case for case in calibration["cases"]
                      if case["case_id"] == row["calibration_case_id"])
        gpu = row["execution"] == "gpu_resident"
        key, executable = executables[row["execution"]]
        native = prepare(
            model_id=row["model_id"], geometry=geometries[row["model_id"]], calibration_case=frozen,
            model_path=invocation.admitted.root / model["model_path"],
            pack_path=invocation.admitted.root / model["pack_path"],
            geometry_path=invocation.admitted.root / model["geometry_path"],
            options_path=options_path if gpu else None,
            cache_budget_bytes=model["runtime_cache_budget_bytes"],
            stream_root=invocation.work / f"case-{ordinal:03d}", stream_name="numeric",
        )
        plans.append(Plan((row["model_id"], row["calibration_case_id"], row["repeat_index"]),
                          native, executable, state.identities[key]["sha256"],
                          dict(calibration["comparison"]), bundle["bundle_id"] if gpu else None,
                          option["device"] if gpu else None))
    resolved_option = {key: value for key, value in option.items() if key != "option_id"}
    resolved_option["backend_bundle"] = str(invocation.backend.root)
    _write(invocation.work, options_path.name, canonical(resolved_option))
    return tuple(plans)
