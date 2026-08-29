#!/usr/bin/env python3
"""The C4-REPAIR-TEMPLATE measurement adapter: `scripts/prompt-repair-adapter.py` plus the refusal.

`docs/specs/c4-repair-template.md` sections 3.1, 3.2, and 3.3 own this contract. This is the third
measurement adapter and the second hop of a two-hop import chain. It exists for one reason: both
gate runs refused ten of twenty-two attempts inside `measurement()`, and the record could not say
which refusal fired, what the model had actually written, or — on the reproduced-unchanged path —
which files it had reproduced. `failure_kind: PATCH` collapses eight distinct raise sites of the
frozen module into one enum value, and three design documents read the surviving free-text string
wrong. This file gives each site a code, keeps the blocks the repair adapter builds one line before
the raise and then discards, and persists a bounded identity for every completion.

It is deliberately **not** a fork of either file. It loads `scripts/prompt-repair-adapter.py` by
path over bytes it verified against a hard-coded digest, executes exactly those bytes as a module,
and reaches the frozen base adapter through **that module's** `base_adapter()` accessor, so exactly
one frozen module object exists in this process and `PR_SET_CHILD_SUBREAPER` keeps exactly one
writer. Only `measurement()` and `assemble()` are near-copies, because only their sequencing
differs, and `scripts/run-prompt-template-adapter-smoke` asserts this hop's divergence from the
repair adapter's originals against a checked-in golden, exactly as that file's own smoke asserts the
first hop. Two goldens, one per hop, each a reviewable artifact.

Two observable differences from the repair adapter, and no others:

1. It emits `TASK_MEASUREMENT` at `schema_version: 3`, adding `edit_refusal`, `completion_bytes`,
   `completion_sha256`, and a conditional `completion_text`, and keeping `edit_set` on the
   reproduced-unchanged refusal instead of discarding it.
2. Its `environment_probe.runtime_identity` is **its own** digest, for the reason section 2.3 of
   `c4-repair-editset.md` fixed: reporting an imported file's digest would persist a false claim
   about which code ran. `producer` names a role and stays `MEASUREMENT_ADAPTER`.

`BASE_ADAPTER_SHA256` is **not** redeclared here. The repair adapter owns that constant and this
file asserts its value against the corpus manifest instead: one constant, one owner, and no second
literal to drift.

This capability consumes undeclared internal APIs of two files whose docstrings describe CLI
adapters, and of the frozen module's exception *messages*. Section 3.3 states that rather than
arguing it away. The mitigation is immutability — both files are digest-verified members of frozen
corpus file-set manifests — plus totality: an unmapped message is `ERROR`/`ADAPTER`, never a silent
`NONE`, and the owner smoke drives every one of the nine raise sites against the real loaded module.
"""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import stat
import sys
import tempfile
import time
from pathlib import Path
from types import ModuleType
from typing import Any, Mapping, Sequence


# The repair adapter, pinned four independent ways (section 3.2): this constant, the
# `canonical-v1t` file-set manifest, `canonical-v1e`'s manifest at the identical digest, and each
# `prompt-v1t` task manifest's `artifacts` entry, which the snapshot helper verifies before and
# after every invocation. All four must agree.
#
# Derived from `agent/c4-repair-editset`'s final head, per section 6.5 prerequisite 1 and section
# 10.3. That branch's review repair moved the edit-set budget to a break-on-first-overflow prefix
# cut, which moved these bytes and re-froze `canonical-v1e`; this constant, the second-hop
# divergence golden, and `canonical-v1t` were all re-derived in the merge commit. Nothing has to
# remember: `scripts/run-prompt-template-adapter-smoke` digests the on-disk file and fails closed
# the moment the two disagree, and ladder rows 3 and 4 bind the same value to the corpus manifests.
#
# This file consumes that budget rule by **calling** `repair.edit_set_blocks`, never by copying it,
# so the widened version-3 `edit_set` persistence inherits the repaired prefix-cut semantics
# automatically and cannot drift from them.
REPAIR_ADAPTER_RELATIVE = "scripts/prompt-repair-adapter.py"
REPAIR_ADAPTER_SHA256 = "fa73f9dc20415bfa59b37ad8a86c971e8d0e9dc5ba228812789e7726685283da"
# The repair adapter is a source file, not an executable artifact; it shares the frozen adapter's
# own `ARTIFACT_LIMIT`. Named here rather than read from a module, because the bound must apply to
# the read that happens *before* any module exists.
REPAIR_ADAPTER_LIMIT = 2_097_152
# Section 3.3: the producer-side whole-field bound on the captured completion, applied by the
# frozen `bounded_text` after `redact_credential` and before the whole-field `RESULT_LIMIT` check.
COMPLETION_LIMIT = 32_768
MEASUREMENT_SCHEMA_VERSION = 3
# Section 3.4's fifth declaration of the edit-set bounds. Declaring them here rather than reading
# `frozen.MAXIMUM_FILE_BLOCKS` through the chain is deliberate: `loaded_modules()` asserts these
# literals against the frozen module's own at load, so the fifth copy is the thing that makes the
# other four *checked* rather than one more place to drift. Nothing in this file consumes them for
# behaviour — the frozen parser enforces them — and that is exactly why an unchecked copy would be
# invisible. The evaluator refuses a declared `edit_policy` that differs from the same two values.
MAXIMUM_FILE_BLOCKS = 32
MAXIMUM_EDIT_BYTES = 262_144

# Section 3.3's ten-code vocabulary. Each code names one raise site of the frozen module. The eight
# `NO_SET` codes are those raised before `validated_edit_set` returned its list, so no structured
# record of the model's blocks exists for them; `UNCHANGED_FILES` is the one refusal that fires
# after the blocks were built, and it is the mode that consumed eight of twenty-two attempts.
EDIT_REFUSAL_PATCH_CODES = (
    "NO_FILE_BLOCK", "HEADER_WITHOUT_BLOCK", "UNTERMINATED_BLOCK", "TOO_MANY_BLOCKS",
    "DUPLICATE_PATH", "BODY_TOO_LARGE", "UNCHANGED_FILES",
)
EDIT_REFUSAL_POLICY_CODES = ("PATH_NOT_EDITABLE", "PATH_ESCAPES_SOURCE")


class TemplateAdapterError(ValueError):
    """The repair adapter could not be loaded as the exact reviewed bytes this file pins.

    Every arm is fail-closed and lands before any request is loaded, so a wrong intermediate file
    can never reach a provider call, a workspace, or a persisted artifact.
    """


# Section 3.2's consumed-name table for the *repair* module, with the kind each name must have.
# Everything else in that module is unused. The frozen module's own consumed-name table is the
# repair adapter's `CONSUMED_NAMES`, which its `base_adapter()` asserts on our behalf; this file
# adds no name to it.
CONSUMED_NAMES: tuple[tuple[str, str], ...] = (
    ("BASE_ADAPTER_SHA256", "str"),
    ("EDIT_SET_LIMIT", "int"),
    ("BaseAdapterError", "class"),
    ("base_adapter", "callable"),
    ("edit_set_blocks", "callable"),
    ("runtime_identity", "callable"),
)


def repair_adapter_path() -> Path:
    """The repair adapter's resolved path, derived from this file's own location.

    All three adapters are corpus members at fixed repository-relative paths, so this is a
    repository fact rather than an input: there is no flag and no environment variable to move it.
    """
    return (Path(__file__).resolve().parent.parent / REPAIR_ADAPTER_RELATIVE).resolve()


def read_repair_adapter(path: Path) -> bytes:
    """One bounded read of the repair adapter, returning the exact bytes that will be executed.

    Verify-then-execute over **one** byte sequence: the digest is taken over what this function
    returns and the module is compiled from the same object, so there is no read-hash-read window
    in which the file could change between the check and the use.
    """
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    except OSError:
        raise TemplateAdapterError("the repair adapter is unavailable") from None
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_size < 0
            or metadata.st_size > REPAIR_ADAPTER_LIMIT
        ):
            raise TemplateAdapterError("the repair adapter type or size is invalid")
        raw = bytearray()
        offset = 0
        while offset < metadata.st_size:
            chunk = os.pread(descriptor, min(65_536, metadata.st_size - offset), offset)
            if not chunk:
                raise TemplateAdapterError("the repair adapter changed while reading")
            raw.extend(chunk)
            offset += len(chunk)
        after = os.fstat(descriptor)
        identity = lambda value: (
            value.st_dev, value.st_ino, value.st_mode, value.st_size, value.st_mtime_ns,
        )
        if identity(metadata) != identity(after):
            raise TemplateAdapterError("the repair adapter identity disagrees")
    finally:
        os.close(descriptor)
    return bytes(raw)


def verified_repair_adapter(path: Path) -> bytes:
    """Ladder row 2: the read bytes are the bytes `REPAIR_ADAPTER_SHA256` names, or nothing runs."""
    raw = read_repair_adapter(path)
    observed = hashlib.sha256(raw).hexdigest()
    if observed != REPAIR_ADAPTER_SHA256:
        raise TemplateAdapterError(
            f"the repair adapter digest disagrees: expected {REPAIR_ADAPTER_SHA256}, read {observed}"
        )
    return raw


def execute_repair_adapter(path: Path, raw: bytes) -> ModuleType:
    """Execute the verified bytes as a module, exactly once, in this process.

    `__file__` is the repair adapter's resolved path, so its own `runtime_identity()` and its
    `Path(__file__).resolve().parent.parent` project idiom resolve exactly as they do when it runs
    standalone — which is also what lets its `base_adapter_path()` find the frozen file.
    `__name__` is not `"__main__"`, so its `raise SystemExit(main())` guard does not fire and
    `main()` is never called.

    Executing this module has **no** module-level effect: the repair adapter sets no `prctl` and
    loads nothing at import time. `PR_SET_CHILD_SUBREAPER` is established later, once, when its
    `base_adapter()` executes the frozen module.
    """
    module = ModuleType("prompt_repair_adapter_hop")
    module.__file__ = str(path)
    try:
        code = compile(raw, str(path), "exec")
        exec(code, module.__dict__)  # noqa: S102 - digest-verified bytes, section 3.2
    except (SyntaxError, ValueError) as failure:
        raise TemplateAdapterError(f"the repair adapter did not execute: {failure}") from None
    return module


def assert_import_contract(module: ModuleType) -> None:
    """Ladder row 6: every consumed name exists with the expected kind, before any external call."""
    for name, kind in CONSUMED_NAMES:
        if not hasattr(module, name):
            raise TemplateAdapterError(f"the repair adapter does not define {name}")
        value = getattr(module, name)
        if kind == "callable":
            valid = callable(value) and not isinstance(value, type)
        elif kind == "class":
            valid = isinstance(value, type)
        elif kind == "int":
            valid = isinstance(value, int) and not isinstance(value, bool)
        else:
            valid = isinstance(value, str)
        if not valid:
            raise TemplateAdapterError(f"the repair adapter's {name} is not a {kind}")


_REPAIR: ModuleType | None = None


def repair_adapter() -> tuple[ModuleType, bytes]:
    """The one loaded repair module of this process, with the exact bytes it was executed from.

    Never reloaded, never mutated, never shared. Each attempt is its own adapter process, so "one
    module per process" is also one module per attempt. A second load in one process is refused
    rather than silently returning the first, exactly as the first hop refuses one.
    """
    global _REPAIR
    if _REPAIR is not None:
        raise TemplateAdapterError("the repair adapter is already loaded in this process")
    path = repair_adapter_path()
    raw = verified_repair_adapter(path)
    module = execute_repair_adapter(path, raw)
    assert_import_contract(module)
    _REPAIR = module
    return module, raw


def repair_runtime_identity(raw: bytes, module: ModuleType) -> str:
    """Ladder row 2's second half: two derivations of one value, and a check that they agree.

    The first is over the bytes this process verified and executed. The second is
    `repair.runtime_identity()`, which re-reads the file. A mismatch means the file changed between
    the two reads, which is exactly the window a single derivation could not see.
    """
    computed = "PYTHON:" + hashlib.sha256(raw).hexdigest()
    reported = module.runtime_identity()
    if computed != reported:
        raise TemplateAdapterError("the repair adapter changed between its two identity derivations")
    return computed


def loaded_modules() -> tuple[ModuleType, ModuleType, str, str]:
    """The two-hop chain, in order, with both cross-derived identities.

    The frozen module is reached through `repair.base_adapter()` and never loaded separately, so
    this process holds exactly one frozen module object and exactly one `prctl` writer (section
    3.2). `repair.BASE_ADAPTER_SHA256` is the single owner of the frozen digest; ladder row 4 binds
    it to the corpus manifests rather than to a second literal here.
    """
    repair, repair_raw = repair_adapter()
    repair_identity = repair_runtime_identity(repair_raw, repair)
    frozen, frozen_raw = repair.base_adapter()
    base_identity = "PYTHON:" + hashlib.sha256(frozen_raw).hexdigest()
    if base_identity != frozen.runtime_identity():
        raise TemplateAdapterError("the base adapter changed between its two identity derivations")
    if base_identity != "PYTHON:" + repair.BASE_ADAPTER_SHA256:
        raise TemplateAdapterError("the base adapter digest disagrees with its declared constant")
    # Ladder row 7. The frozen `measurement()` requires this posture and establishes it itself; this
    # file neither sets nor clears it, and refuses to run without it rather than proceeding
    # uncontained.
    if not frozen.CHILD_SUBREAPER_ENABLED:
        raise TemplateAdapterError("child-subreaper containment is unavailable")
    # Section 3.4's constant parity, asserted at load against the module that actually enforces the
    # bounds. Three scripts had declared these independently since C4-REPAIR-MEASURED with nothing
    # tying them together; a declared `edit_policy` is validated as equal to the same two values,
    # so a silent divergence here would put a number in a model's prompt that no code enforces.
    if (
        frozen.MAXIMUM_FILE_BLOCKS != MAXIMUM_FILE_BLOCKS
        or frozen.MAXIMUM_EDIT_BYTES != MAXIMUM_EDIT_BYTES
    ):
        raise TemplateAdapterError("the frozen edit-set bounds disagree with the declared policy")
    return repair, frozen, repair_identity, base_identity


# --- This adapter's own identity ----------------------------------------------------------------


def runtime_identity() -> str:
    """This file's digest, not either loaded file's. `src/prompt_score.align` requires the persisted
    probe's `runtime_identity` to equal the task manifest's `measurement_adapter_runtime`, and the
    evaluator independently re-verifies the argv helper's bytes against the same value. Reporting an
    imported file's digest here would persist a false claim about which code ran.
    """
    return "PYTHON:" + hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def environment_probe(frozen: ModuleType) -> dict[str, Any]:
    """The frozen probe's shape and field order, with this file's identity.

    `producer` stays `MEASUREMENT_ADAPTER` because it names a **role** and this file fills exactly
    that role; `ENVIRONMENT_PROBE` does not move (section 3.5).
    """
    logical = os.cpu_count()
    value = {
        "schema_version": 1,
        "artifact_kind": "ENVIRONMENT_PROBE",
        "producer": "MEASUREMENT_ADAPTER",
        "os": platform.system().lower(),
        "os_release": platform.release(),
        "architecture": platform.machine().lower(),
        "cpu": platform.processor() or platform.machine().lower(),
        "logical_cpu_count": logical if logical and logical > 0 else None,
        "gpu": "none",
        "runtime_identity": runtime_identity(),
        "content_sha256": "",
    }
    frozen.bind_digest(value)
    return value


# --- The refusal vocabulary -----------------------------------------------------------------


def edit_refusal_code(summary: str) -> str | None:
    """Map one frozen exception message to its section 3.3 code, or `None` when unmapped.

    The frozen exceptions carry no code, so this matches the message by shape. That is fragile
    against a changing message and safe here for exactly one reason: the mapped file is
    digest-pinned byte-identical in four corpus manifests, the same immutability argument section
    3.2 makes for the undeclared API. Two things make it checked rather than assumed. The mapping
    is **total** — an unmapped message becomes `ERROR`/`ADAPTER` at the call site, never a silent
    `NONE` — and `scripts/run-prompt-template-adapter-smoke` drives every one of the nine raise
    sites against the real loaded module and asserts the code this returns.

    Order matters: three messages share the prefix `the response declares `, so the exact forms are
    matched before the parameterized one.
    """
    fixed = {
        "the response declares no file block": "NO_FILE_BLOCK",
        "a FILE header carries no fenced block": "HEADER_WITHOUT_BLOCK",
        "a fenced file block is not terminated": "UNTERMINATED_BLOCK",
        "the response declares too many file blocks": "TOO_MANY_BLOCKS",
        "the response reproduced the pinned files unchanged": "UNCHANGED_FILES",
    }
    if summary in fixed:
        return fixed[summary]
    if summary.startswith("the response declares ") and summary.endswith(" twice"):
        return "DUPLICATE_PATH"
    if summary.startswith("the emitted content for ") and summary.endswith(" exceeds its bound"):
        return "BODY_TOO_LARGE"
    if summary.startswith("the response edits a file outside the editable set: "):
        return "PATH_NOT_EDITABLE"
    if summary.startswith("the editable path escapes the pinned source: "):
        return "PATH_ESCAPES_SOURCE"
    return None


def classified_refusal(summary: str, admitted: Sequence[str]) -> str | None:
    """The code for one refusal, or `None` when the message is unmapped or the wrong class.

    A message that maps into the *other* exception's class is as much a producer defect as an
    unmapped one — it would mean the frozen sequencing changed which site raises which type — so
    both take the same fail-closed exit.
    """
    code = edit_refusal_code(summary)
    return code if code in admitted else None


# --- The near-copies. Section 3.2's bounded-divergence golden asserts this delta. ----------------


def measurement(
    repair: ModuleType,
    frozen: ModuleType,
    base_identity: str,
    request: Mapping[str, Any],
    rendered: Mapping[str, Any],
    policy: Mapping[str, Any],
    control: Mapping[str, Any],
    project: Path,
    scratch: Path,
) -> dict[str, Any]:
    credential_env_name = request["credential_env_name"]
    credential_value = os.environ.get(credential_env_name) if credential_env_name else None
    response: dict[str, Any] | None = None
    retained: list[Any] = []
    outcome = "ERROR"
    cleanup_passed = True
    containment_passed = True
    stdout = b""
    stderr = b""
    patch_byte_count = 0
    patch_sha256: str | None = None
    edit_set: list[dict[str, Any]] | None = None
    edit_set_total_bytes: int | None = None
    edit_refusal = "NONE"
    generation_ns: int | None = None
    applied_edits: list[str] = []
    summary = "provider-backed measurement failed"

    if len(rendered["text"].encode("utf-8")) > policy["max_prompt_bytes"]:
        generation, attestation = frozen.provider_identities(request, rendered, policy, control, None)
        return assemble(
            frozen, base_identity, request, rendered, "POLICY", True, True, b"", b"", 0, None,
            generation, attestation, "prompt exceeds max_prompt_bytes", credential_value,
            None, None, None, "NONE", None,
        )
    try:
        if not frozen.CHILD_SUBREAPER_ENABLED:
            raise frozen.AdapterError("child-subreaper containment is unavailable")
        policy_environment = frozen.child_environment(None, None)
        generation_environment = frozen.child_environment(credential_env_name, credential_value)
        child = frozen.ImmutableInput(
            Path(request["generation_child_path"]), request["generation_child_sha256"],
            "generation-child", executable=True, maximum=frozen.EXECUTABLE_LIMIT,
        )
        retained.append(child)
        runner = frozen.ImmutableInput(
            Path(request["validation_runner_path"]), request["validation_runner_sha256"],
            "validation-runner",
        )
        retained.append(runner)
        task_definition = frozen.ImmutableInput(
            Path(request["task_definition_path"]), request["task_definition_sha256"],
            "task-definition",
        )
        retained.append(task_definition)
        declared_patch: Any | None = None
        if request["patch_path"] is not None:
            declared_patch = frozen.ImmutableInput(
                Path(request["patch_path"]), request["patch_sha256"], "declared-patch",
            )
            retained.append(declared_patch)

        document = frozen.generation_request_document(request, control, policy)
        provider_timeout = max(0.001, control["timeout_ns"] / 1_000_000_000)
        started = time.monotonic_ns()
        response = frozen.run_generation_child(
            child, document, scratch, provider_timeout, generation_environment, project,
            credential_value,
        )
        if declared_patch is not None:
            patch = declared_patch
            # The declared-patch path parses no response, so there is no edit set to keep. The
            # patch digest is still recorded: it is the identity of the bytes the runner applied.
            patch_sha256 = hashlib.sha256(
                frozen.redacted_bytes(patch.read_sealed(), credential_value)
            ).hexdigest()
        else:
            source_root, allowed_edits = frozen.task_edit_policy(task_definition, project)
            edits = frozen.validated_edit_set(response["content"], allowed_edits)
            applied_edits = [path for path, _ in edits]
            # The one assignment the frozen sequencing does not make. Everything below it is the
            # frozen order unchanged.
            edit_set, edit_set_total_bytes = repair.edit_set_blocks(frozen, edits, credential_value)
            raw_patch = frozen.synthesized_patch(edits, source_root)
            # Section 3.10: the digest is taken before `ProducedInput` is constructed, so nothing
            # reads through a descriptor the frozen `finally` may already have closed.
            patch_sha256 = hashlib.sha256(
                frozen.redacted_bytes(raw_patch, credential_value)
            ).hexdigest()
            patch = frozen.ProducedInput(raw_patch, "generated-patch")
            retained.append(patch)
        patch_byte_count = patch.byte_count
        outcome, cleanup_passed, containment_passed, stdout, stderr = frozen.execute_validation(
            request, runner, task_definition, patch, request["task_deadline_ns"],
            policy_environment, project, credential_value,
        )
        if outcome == "PASS":
            generation_ns = time.monotonic_ns() - started
            summary = "provider-backed candidate patch passed validation"
        elif outcome == "TEST_FAIL":
            summary = "provider-backed candidate patch failed validation"
        else:
            summary = "contained validation runner failed"
        summary = f"{summary}; applied edits: {', '.join(applied_edits) or 'declared patch'}"
    except frozen.PolicyViolation as failure:
        # A rejected path never reaches the record, and neither does a path that escaped the pinned
        # source: both are section 3.3's `POLICY` class, and `edit_set` stays `None` for both. The
        # escape arm raises after `validated_edit_set` returned, so this is where the widened
        # presence rule stops: only `UNCHANGED_FILES` keeps its blocks.
        summary = str(failure)
        code = classified_refusal(summary, EDIT_REFUSAL_POLICY_CODES)
        outcome, generation_ns = ("POLICY" if code else "ERROR"), None
        edit_refusal = code or "NONE"
        if code is None:
            summary = f"unmapped edit refusal: {summary}"
        edit_set, edit_set_total_bytes, patch_sha256 = None, None, None
        stderr = frozen.bounded_diagnostic(summary, credential_value)
    except frozen.EditFormatError as failure:
        # Section 3.3's widening, and the whole reason this adapter exists: on `UNCHANGED_FILES`
        # the blocks the line above built are the evidence that explains the mode, so they are
        # kept. Every other refusal in this class raises before they were built, so there is
        # nothing to keep and `edit_set` stays `None` — which is also what makes the code and the
        # presence rule one decision rather than two.
        summary = str(failure)
        code = classified_refusal(summary, EDIT_REFUSAL_PATCH_CODES)
        outcome, generation_ns = ("PATCH" if code else "ERROR"), None
        edit_refusal = code or "NONE"
        if code is None:
            summary = f"unmapped edit refusal: {summary}"
        if code != "UNCHANGED_FILES":
            edit_set, edit_set_total_bytes = None, None
        patch_sha256 = None
        stderr = frozen.bounded_diagnostic(summary, credential_value)
    except frozen.GenerationFailure as failure:
        outcome, response, generation_ns = "ERROR", None, None
        edit_set, edit_set_total_bytes, patch_sha256 = None, None, None
        cleanup_passed = failure.cleanup_passed
        containment_passed = failure.containment_passed
        summary = str(failure)
        stderr = frozen.bounded_diagnostic(str(failure), credential_value)
    except (frozen.AdapterError, OSError, TypeError, ValueError, KeyError) as failure:
        outcome, response, generation_ns = "ERROR", None, None
        edit_set, edit_set_total_bytes, patch_sha256 = None, None, None
        summary = str(failure)
        stderr = frozen.bounded_diagnostic(str(failure), credential_value)
    finally:
        for item in retained:
            try:
                item.close()
            except OSError:
                cleanup_passed = False

    # Section 3.10: the completion is materialized once, from the response document the frozen
    # child already parsed, and is redacted before it is digested or bounded. The digest is over the
    # **full** redacted bytes, so it identifies the answer and any excerpt is a view of it. Nothing
    # is re-read and nothing reaches disk from here.
    completion: bytes | None = None
    if response is not None:
        completion = frozen.redacted_bytes(response["content"].encode("utf-8"), credential_value)
    generation, attestation = frozen.provider_identities(request, rendered, policy, control, response)
    return assemble(
        frozen, base_identity, request, rendered, outcome, cleanup_passed, containment_passed,
        stdout, stderr, patch_byte_count, generation_ns, generation, attestation, summary,
        credential_value, edit_set, edit_set_total_bytes, patch_sha256, edit_refusal, completion,
    )


def assemble(
    frozen: ModuleType,
    base_identity: str,
    request: Mapping[str, Any],
    rendered: Mapping[str, Any],
    outcome: str,
    cleanup_passed: bool,
    containment_passed: bool,
    stdout: bytes,
    stderr: bytes,
    patch_byte_count: int,
    generation_ns: int | None,
    generation: Mapping[str, Any],
    attestation: Mapping[str, Any],
    summary: str,
    credential_value: str | None,
    edit_set: Sequence[Mapping[str, Any]] | None,
    edit_set_total_bytes: int | None,
    patch_sha256: str | None,
    edit_refusal: str,
    completion: bytes | None,
) -> dict[str, Any]:
    passed = outcome == "PASS"
    expected_failure = outcome == "TEST_FAIL"
    policy_violation = outcome == "POLICY"
    patch_absent = outcome == "PATCH"
    not_run = policy_violation or patch_absent
    status = (
        "PASS" if passed else "FAIL" if expected_failure or patch_absent
        else "POLICY_VIOLATION" if policy_violation else "ERROR"
    )
    value = {
        "schema_version": MEASUREMENT_SCHEMA_VERSION,
        "artifact_kind": "TASK_MEASUREMENT",
        "status": "ERROR" if not cleanup_passed or not containment_passed else status,
        "failure_kind": (
            "CONTAINMENT" if not containment_passed
            else "CLEANUP" if not cleanup_passed
            else "NONE" if passed
            else "TEST" if expected_failure
            else "POLICY" if policy_violation
            else "PATCH" if patch_absent
            else "ADAPTER"
        ),
        "build_status": "NOT_RUN" if not_run else "PASS" if outcome != "ERROR" else "ERROR",
        "test_status": (
            "NOT_RUN" if not_run else "PASS" if passed
            else "FAIL" if expected_failure else "ERROR"
        ),
        "repair_loop_count": 0,
        "unrelated_diff_count": 0,
        "patch_size_bytes": patch_byte_count,
        "public_api_change_count": 0,
        "policy_violation_count": 1 if policy_violation else 0,
        "cleanup_passed": cleanup_passed,
        "containment_passed": containment_passed,
        "benchmark_regression_ppm": None,
        "generation_to_passing_patch_ns": (
            generation_ns if status == "PASS" and cleanup_passed and containment_passed else None
        ),
        "rendered_prompt_sha256": rendered["content_sha256"],
        "generation_request": dict(generation),
        "environment_probe": environment_probe(frozen),
        "seed_attestation": dict(attestation),
        "diagnostic_summary": frozen.bounded_text(
            summary.encode("utf-8"), frozen.SUMMARY_LIMIT, credential_value,
        ),
        "diagnostic_stdout": frozen.bounded_text(stdout, frozen.DIAGNOSTIC_LIMIT, credential_value),
        "diagnostic_stderr": frozen.bounded_text(stderr, frozen.DIAGNOSTIC_LIMIT, credential_value),
        "edit_set": [dict(block) for block in edit_set] if edit_set is not None else None,
        "edit_set_total_bytes": edit_set_total_bytes,
        "patch_sha256": patch_sha256,
        "base_adapter_runtime_identity": base_identity,
        # The four version-3 members, appended immediately before `content_sha256` by the same rule
        # version 2 used. `edit_refusal` is always `Some`, so the quantity the corpus aggregate
        # counts is defined for every ran attempt rather than inferred from an absence; the two
        # completion identity members are `Some` whenever a provider response was received, which
        # makes "attempt 2 re-sent attempt 1's whole answer" a measured fact at zero disclosure
        # cost.
        "edit_refusal": edit_refusal,
        "completion_bytes": None if completion is None else len(completion),
        "completion_sha256": (
            None if completion is None else hashlib.sha256(completion).hexdigest()
        ),
        "completion_text": None,
        "content_sha256": "",
    }
    # Section 3.3: the text is persisted **only** where no structured substitute exists — the eight
    # refusal codes for which `validated_edit_set` never returned — because on every other path
    # `edit_set` already carries the model's own bodies. This is `c4-repair-editset.md` section
    # 6.4's deferral taken on its own stated terms, at the smallest disclosure surface that makes
    # the mode explicable.
    carried = (
        None if completion is None or edit_refusal in ("NONE", "UNCHANGED_FILES")
        else frozen.bounded_text(completion, COMPLETION_LIMIT, credential_value)
    )
    if carried is not None:
        # Encode-then-check, whole-field. A control-character-dense completion can expand under JSON
        # escaping past `RESULT_LIMIT` and would otherwise turn a real measurement into `ERROR` — a
        # new failure mode introduced by the capture itself, which is not acceptable. The text is
        # dropped entire, never partially, and `completion_bytes` and `completion_sha256` survive,
        # so the answer stays identified even when it is not shown.
        value["completion_text"] = carried
        frozen.bind_digest(value)
        if len(frozen.canonical_bytes(value)) > frozen.RESULT_LIMIT:
            value["completion_text"] = None
    frozen.bind_digest(value)
    return value


# --- Entry point --------------------------------------------------------------------------------


def main(arguments: Sequence[str] | None = None) -> int:
    """The repair adapter's `main()` sequence, with this file's `measurement()` and both modules.

    Neither loaded module's `main()` is ever called: the repair adapter's would run its own
    `measurement()` and emit a version-2 result carrying its runtime identity, and the frozen one's
    would emit a version-1 result carrying the frozen file's.
    """
    repair, frozen, _repair_identity, base_identity = loaded_modules()
    values = frozen.parse_arguments(sys.argv[1:] if arguments is None else arguments)
    owned: list[Path] = []
    try:
        request = frozen.load_request(values.adapter_request)
        if (
            request["sample_index"] != values.sample_index
            or request["paired_seed"] != values.paired_seed
            or not frozen.same_path(request["variant_path"], values.prompt_variant)
            or not frozen.same_path(request["rendered_prompt_path"], values.rendered_prompt)
            or Path(request["result_path"]) != values.result
        ):
            raise frozen.AdapterError("adapter CLI and request identities disagree")
        variant = frozen.decoded_artifact(values.prompt_variant, frozen.ARTIFACT_LIMIT, "PROMPT_VARIANT")
        rendered = frozen.decoded_artifact(values.rendered_prompt, frozen.ARTIFACT_LIMIT, "RENDERED_PROMPT")
        policy = frozen.decoded_artifact(
            Path(request["generation_policy_path"]), frozen.ARTIFACT_LIMIT, "GENERATION_POLICY",
        )
        control = frozen.decoded_artifact(
            Path(request["provider_control_path"]), frozen.ARTIFACT_LIMIT,
            "EVALUATION_PROVIDER_CONTROL",
        )
        if (
            variant["content_sha256"] != request["variant_sha256"]
            or rendered["content_sha256"] != request["rendered_prompt_sha256"]
            or rendered["variant_sha256"] != variant["content_sha256"]
            or rendered["variant_id"] != variant["variant_id"]
            or policy["content_sha256"] != request["generation_policy_sha256"]
            or control["content_sha256"] != request["provider_control_sha256"]
            or policy["provider_control_sha256"] != control["content_sha256"]
            or policy["evaluation_provider_kind"] != control["provider_kind"]
            or policy["evaluation_provider_model"] != control["model"]
            or policy["seed_mode"] != "PAIRED_FIXED"
        ):
            raise frozen.AdapterError("adapter declared identities disagree")
        if control["provider_kind"] == "FIXTURE":
            raise frozen.AdapterError("the measurement adapter does not admit a FIXTURE provider control")
        project = Path(__file__).resolve().parent.parent
        scratch = Path(tempfile.mkdtemp(prefix="prompt-template-adapter-")).resolve()
        owned.append(scratch)
        result = measurement(
            repair, frozen, base_identity, request, rendered, policy, control, project, scratch,
        )
        if values.result_fd is None:
            frozen.write_exclusive(values.result, result)
        else:
            frozen.write_retained_result(values.result, values.result_fd, result)
        return 0
    except (frozen.AdapterError, repair.BaseAdapterError, TemplateAdapterError, OSError, TypeError,
            ValueError, KeyError):
        return 2
    finally:
        for path in owned:
            shutil.rmtree(path, ignore_errors=True)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except TemplateAdapterError:
        # Neither loaded module exists yet, so no imported error class can catch this. The exit
        # status is the frozen adapter's own invalid-input status, and nothing is written: the
        # evaluator sees a failed adapter process, which is `ERROR`/`ADAPTER`.
        raise SystemExit(2)
