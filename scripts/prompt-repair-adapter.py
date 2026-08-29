#!/usr/bin/env python3
"""The C4-REPAIR-EDITSET measurement adapter: `scripts/prompt-measurement-adapter.py` plus the edits.

`docs/specs/c4-repair-editset.md` sections 3.1 and 3.2 own this contract. This is the second
measurement adapter of `eval/prompt/canonical-v1e/`. It exists for one reason: the frozen adapter's
`measurement()` holds the model's realized edit set in a local variable and returns none of it, so
a repair prompt can never show the model what it wrote. This file keeps that value, and nothing
else about the measurement path changes.

It is deliberately **not** a fork. It loads `scripts/prompt-measurement-adapter.py` by path, over
bytes it verified against a hard-coded digest, executes exactly those bytes as a module, and calls
its containment, sealing, redaction, process-ownership, generation, validation, and edit-parsing
functions unchanged. Containment has exactly one copy in this repository. Only `measurement()` and
`assemble()` are near-copies, because only their sequencing differs, and
`scripts/run-prompt-repair-adapter-smoke` asserts their divergence from the frozen originals
against a checked-in golden so the delta is a reviewable artifact rather than a claim.

Two observable differences from the frozen adapter, and no others:

1. It emits `TASK_MEASUREMENT` at `schema_version: 2`, adding `edit_set`, `edit_set_total_bytes`,
   `patch_sha256`, and `base_adapter_runtime_identity`.
2. Its `environment_probe.runtime_identity` is **its own** digest. Reusing the frozen
   `environment_probe()` would persist the imported file's digest while running this file's code —
   a false identity claim that `src/prompt_score.align`'s existing check would accept, because the
   task manifest would have had to declare the same false value. `producer` names a role and stays
   `MEASUREMENT_ADAPTER`; `runtime_identity` names a file and must not.

The frozen module's one module-level effect is `PR_SET_CHILD_SUBREAPER` on the importing process.
That is disclosed, not tolerated: it is the containment posture the frozen `measurement()` demands,
established in the process that will own the children. This file never sets it and never clears it.

This capability consumes an undeclared internal API of a file whose docstring describes a CLI
adapter. Section 3.2 states that rather than arguing it away. The mitigation is immutability: the
base file is a digest-verified member of three frozen corpus file-set manifests, so it cannot change
without minting a new corpus, which is the same event that would require re-reviewing this file.
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


# The base adapter, pinned three independent ways (section 3.2): this constant, the
# `canonical-v1e` file-set manifest, and each `prompt-v1e` task manifest's `artifacts` entry, which
# the snapshot helper verifies before and after every invocation. All three must agree.
BASE_ADAPTER_RELATIVE = "scripts/prompt-measurement-adapter.py"
BASE_ADAPTER_SHA256 = "2d3796dbf1159d4a9528a62bbb9af0f36ccc5878b76d83aa65fa0d39cca7b20c"
# The base adapter is a source file, not an executable artifact; it shares the frozen adapter's own
# `ARTIFACT_LIMIT`. Named here rather than read from the module, because the bound must apply to the
# read that happens *before* the module exists.
BASE_ADAPTER_LIMIT = 2_097_152
# Section 4.3: the producer-side whole-block bound on the carried edit set. It matches
# `DIAGNOSTIC_LIMIT` so the four bounded repair sections sum to a known ceiling.
EDIT_SET_LIMIT = 16_384
MEASUREMENT_SCHEMA_VERSION = 2


class BaseAdapterError(ValueError):
    """The base adapter could not be loaded as the exact reviewed bytes this file pins.

    Every arm is fail-closed and lands before any request is loaded, so a wrong base file can never
    reach a provider call, a workspace, or a persisted artifact.
    """


# Section 3.2's consumed-name table, with the kind each name must have. Row 4 of the section 3.9
# ladder asserts this whole set immediately after execution and before any request is loaded, so a
# renamed or retyped name is an error at startup rather than a silent wrong artifact later.
#
# Some entries are consumed transitively rather than by a call in this file: `RESULT_LIMIT` bounds
# `write_retained_result`, and `TRUNCATION_MARKER` is the marker `bounded_text` appends when this
# file's `assemble()` truncates a diagnostic. Pinning them keeps the near-copy's assumptions checked
# instead of assumed.
CONSUMED_NAMES: tuple[tuple[str, str], ...] = (
    ("REQUEST_LIMIT", "int"),
    ("ARTIFACT_LIMIT", "int"),
    ("RESULT_LIMIT", "int"),
    ("DIAGNOSTIC_LIMIT", "int"),
    ("SUMMARY_LIMIT", "int"),
    ("EXECUTABLE_LIMIT", "int"),
    ("MAXIMUM_FILE_BLOCKS", "int"),
    ("MAXIMUM_EDIT_BYTES", "int"),
    ("TRUNCATION_MARKER", "bytes"),
    ("CHILD_SUBREAPER_ENABLED", "bool"),
    ("AdapterError", "class"),
    ("EditFormatError", "class"),
    ("PolicyViolation", "class"),
    ("GenerationFailure", "class"),
    ("ImmutableInput", "class"),
    ("ProducedInput", "class"),
    ("validated_edit_set", "callable"),
    ("synthesized_patch", "callable"),
    ("task_edit_policy", "callable"),
    ("canonical_bytes", "callable"),
    ("canonical_digest_bytes", "callable"),
    ("bind_digest", "callable"),
    ("valid_digest", "callable"),
    ("decoded_artifact", "callable"),
    ("load_request", "callable"),
    ("same_path", "callable"),
    ("redact", "callable"),
    ("redacted_bytes", "callable"),
    ("bounded_diagnostic", "callable"),
    ("bounded_text", "callable"),
    ("child_environment", "callable"),
    ("generation_request_document", "callable"),
    ("run_generation_child", "callable"),
    ("execute_validation", "callable"),
    ("provider_identities", "callable"),
    ("write_exclusive", "callable"),
    ("write_retained_result", "callable"),
    ("parse_arguments", "callable"),
    ("runtime_identity", "callable"),
)


def base_adapter_path() -> Path:
    """The base adapter's resolved path, derived from this file's own location.

    Both adapters are corpus members at fixed repository-relative paths, so this is a repository
    fact rather than an input: there is no flag and no environment variable that can move it.
    """
    return (Path(__file__).resolve().parent.parent / BASE_ADAPTER_RELATIVE).resolve()


def read_base_adapter(path: Path) -> bytes:
    """One bounded read of the base adapter, returning the exact bytes that will be executed.

    Verify-then-execute over **one** byte sequence: the digest is taken over what this function
    returns and the module is compiled from the same object, so there is no read-hash-read window in
    which the file could change between the check and the use.
    """
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    except OSError:
        raise BaseAdapterError("the base adapter is unavailable") from None
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_size < 0
            or metadata.st_size > BASE_ADAPTER_LIMIT
        ):
            raise BaseAdapterError("the base adapter type or size is invalid")
        raw = bytearray()
        offset = 0
        while offset < metadata.st_size:
            chunk = os.pread(descriptor, min(65_536, metadata.st_size - offset), offset)
            if not chunk:
                raise BaseAdapterError("the base adapter changed while reading")
            raw.extend(chunk)
            offset += len(chunk)
        after = os.fstat(descriptor)
        identity = lambda value: (
            value.st_dev, value.st_ino, value.st_mode, value.st_size, value.st_mtime_ns,
        )
        if identity(metadata) != identity(after):
            raise BaseAdapterError("the base adapter identity disagrees")
    finally:
        os.close(descriptor)
    return bytes(raw)


def verified_base_adapter(path: Path) -> bytes:
    """Ladder row 2: the read bytes are the bytes `BASE_ADAPTER_SHA256` names, or nothing runs."""
    raw = read_base_adapter(path)
    observed = hashlib.sha256(raw).hexdigest()
    if observed != BASE_ADAPTER_SHA256:
        raise BaseAdapterError(
            f"the base adapter digest disagrees: expected {BASE_ADAPTER_SHA256}, read {observed}"
        )
    return raw


def execute_base_adapter(path: Path, raw: bytes) -> ModuleType:
    """Execute the verified bytes as a module, exactly once, in this process.

    `__file__` is the base adapter's resolved path, so the module's own `runtime_identity()` and its
    `Path(__file__).resolve().parent.parent` project idiom resolve exactly as they do when it runs
    standalone. `__name__` is not `"__main__"`, so its `raise SystemExit(main())` guard does not
    fire and `main()` is never called.

    Executing the module sets `PR_SET_CHILD_SUBREAPER` on this process (section 2.2). That is the
    containment posture its `measurement()` requires; this file neither sets nor clears it.
    """
    module = ModuleType("prompt_measurement_adapter_base")
    module.__file__ = str(path)
    try:
        code = compile(raw, str(path), "exec")
        exec(code, module.__dict__)  # noqa: S102 - digest-verified bytes, section 3.2
    except (SyntaxError, ValueError) as failure:
        raise BaseAdapterError(f"the base adapter did not execute: {failure}") from None
    return module


def assert_import_contract(module: ModuleType) -> None:
    """Ladder row 4: every consumed name exists with the expected kind, before any external call."""
    for name, kind in CONSUMED_NAMES:
        if not hasattr(module, name):
            raise BaseAdapterError(f"the base adapter does not define {name}")
        value = getattr(module, name)
        if kind == "callable":
            valid = callable(value) and not isinstance(value, type)
        elif kind == "class":
            valid = isinstance(value, type)
        elif kind == "int":
            valid = isinstance(value, int) and not isinstance(value, bool)
        elif kind == "bool":
            valid = isinstance(value, bool)
        else:
            valid = isinstance(value, bytes)
        if not valid:
            raise BaseAdapterError(f"the base adapter's {name} is not a {kind}")


_BASE: ModuleType | None = None


def base_adapter() -> tuple[ModuleType, bytes]:
    """The one loaded module of this process, with the exact bytes it was executed from.

    Never reloaded, never mutated, never shared. Each attempt is its own adapter process, so "one
    module per process" is also one module per attempt. A second load in one process is refused
    rather than silently returning the first, because a caller asking for a second load is asking
    for something this contract does not offer.

    The verified bytes are returned rather than the file re-read, so `base_runtime_identity` derives
    its first value from the same byte sequence that was executed.
    """
    global _BASE
    if _BASE is not None:
        raise BaseAdapterError("the base adapter is already loaded in this process")
    path = base_adapter_path()
    raw = verified_base_adapter(path)
    module = execute_base_adapter(path, raw)
    assert_import_contract(module)
    _BASE = module
    return module, raw


def base_runtime_identity(raw: bytes, module: ModuleType) -> str:
    """Ladder row 7: two derivations of one value, and a check that they agree.

    The first is over the bytes this process verified and executed. The second is
    `frozen.runtime_identity()`, which re-reads the file. A mismatch means the file changed between
    the two reads, which is exactly the window a single derivation could not see.
    """
    computed = "PYTHON:" + hashlib.sha256(raw).hexdigest()
    reported = module.runtime_identity()
    if computed != reported:
        raise BaseAdapterError("the base adapter changed between its two identity derivations")
    return computed


# --- This adapter's own identity ----------------------------------------------------------------


def runtime_identity() -> str:
    """This file's digest, not the base adapter's. Section 2.3 records why that distinction is load
    bearing: `src/prompt_score.align` requires the persisted probe's `runtime_identity` to equal the
    task manifest's `measurement_adapter_runtime`, and the evaluator independently re-verifies the
    argv helper's bytes against the same value. Reporting the imported file's digest here would
    persist a false claim about which code ran.
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


# --- The edit set -------------------------------------------------------------------------------


def edit_set_blocks(
    frozen: ModuleType, edits: Sequence[tuple[str, str]], credential_value: str | None,
) -> tuple[list[dict[str, Any]], int]:
    """Build the persisted `EDIT_SET_BLOCK` list from `validated_edit_set`'s own return.

    Three rules, all from section 3.3 and section 4.3, and all of them load bearing:

    - **Redaction runs before digesting.** A persisted digest of unredacted bytes is a credential
      oracle: anyone holding a candidate credential could confirm it by recomputing the digest. The
      cost is that with a credential-bearing provider the digest is a function of redaction as well
      as of content, which is the correct trade and is stated rather than discovered.
    - **`body_bytes` is the redacted body's full length**, before any budget omission, so
      `edit_set_total_bytes` is the pre-omission sum and a reader can see what was dropped.
    - **Bounding is whole-block.** Once the running total would exceed `EDIT_SET_LIMIT` every
      remaining block is persisted with `body_text: None` and its identity intact. A half-truncated
      source file would be worse than none: the whole-file answer format makes "complete the file
      you can only half see" a silent data-loss patch.

    The order is `validated_edit_set`'s, which is `sorted(edits.items())`, so paths are unique and
    ascending by construction rather than by a second sort here.
    """
    blocks: list[dict[str, Any]] = []
    total = 0
    carried = 0
    for path, body in edits:
        redacted = frozen.redacted_bytes(body.encode("utf-8"), credential_value)
        length = len(redacted)
        total += length
        keep = carried + length <= EDIT_SET_LIMIT
        if keep:
            carried += length
        value = {
            "schema_version": 1,
            "artifact_kind": "EDIT_SET_BLOCK",
            "path": path,
            "body_bytes": length,
            "body_sha256": hashlib.sha256(redacted).hexdigest(),
            # The carried text is the redacted bytes decoded back, so `body_sha256` digests exactly
            # what `body_text` carries and the two can never disagree.
            "body_text": redacted.decode("utf-8", "replace") if keep else None,
            "content_sha256": "",
        }
        frozen.bind_digest(value)
        blocks.append(value)
    return blocks, total


# --- The near-copies. Section 3.2's bounded-divergence golden asserts this delta. ----------------


def measurement(
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
    generation_ns: int | None = None
    applied_edits: list[str] = []
    summary = "provider-backed measurement failed"

    if len(rendered["text"].encode("utf-8")) > policy["max_prompt_bytes"]:
        generation, attestation = frozen.provider_identities(request, rendered, policy, control, None)
        return assemble(
            frozen, base_identity, request, rendered, "POLICY", True, True, b"", b"", 0, None,
            generation, attestation, "prompt exceeds max_prompt_bytes", credential_value,
            None, None, None,
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
            edit_set, edit_set_total_bytes = edit_set_blocks(frozen, edits, credential_value)
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
        # A rejected path never reaches the record: `validated_edit_set` raises before it returns,
        # so `edit_set` is still `None` here and stays `None`.
        outcome, generation_ns = "POLICY", None
        edit_set, edit_set_total_bytes, patch_sha256 = None, None, None
        summary = str(failure)
        stderr = frozen.bounded_diagnostic(str(failure), credential_value)
    except frozen.EditFormatError as failure:
        outcome, generation_ns = "PATCH", None
        edit_set, edit_set_total_bytes, patch_sha256 = None, None, None
        summary = str(failure)
        stderr = frozen.bounded_diagnostic(str(failure), credential_value)
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

    generation, attestation = frozen.provider_identities(request, rendered, policy, control, response)
    return assemble(
        frozen, base_identity, request, rendered, outcome, cleanup_passed, containment_passed,
        stdout, stderr, patch_byte_count, generation_ns, generation, attestation, summary,
        credential_value, edit_set, edit_set_total_bytes, patch_sha256,
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
        # The four version-2 members, appended immediately before `content_sha256`, which is the
        # position the canonical encoder and every existing consumer already tolerate. An
        # `Option::None` is omitted from the digest preimage, so absence is expressible without a
        # sentinel.
        "edit_set": [dict(block) for block in edit_set] if edit_set is not None else None,
        "edit_set_total_bytes": edit_set_total_bytes,
        "patch_sha256": patch_sha256,
        "base_adapter_runtime_identity": base_identity,
        "content_sha256": "",
    }
    frozen.bind_digest(value)
    return value


# --- Entry point --------------------------------------------------------------------------------


def main(arguments: Sequence[str] | None = None) -> int:
    """The frozen `main()`'s sequence, with this file's `measurement()` and the loaded base module.

    `frozen.main()` is never called: it would run the frozen `measurement()` and emit a version-1
    result carrying the frozen file's runtime identity.
    """
    frozen, raw = base_adapter()
    base_identity = base_runtime_identity(raw, frozen)
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
        scratch = Path(tempfile.mkdtemp(prefix="prompt-repair-adapter-")).resolve()
        owned.append(scratch)
        result = measurement(frozen, base_identity, request, rendered, policy, control, project, scratch)
        if values.result_fd is None:
            frozen.write_exclusive(values.result, result)
        else:
            frozen.write_retained_result(values.result, values.result_fd, result)
        return 0
    except (frozen.AdapterError, BaseAdapterError, OSError, TypeError, ValueError, KeyError):
        return 2
    finally:
        for path in owned:
            shutil.rmtree(path, ignore_errors=True)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BaseAdapterError:
        # The base adapter could not be loaded, so no frozen error class exists to catch it inside
        # `main()`. The exit status is the frozen adapter's own invalid-input status, and nothing is
        # written: the evaluator sees a failed adapter process, which is `ERROR`/`ADAPTER`.
        raise SystemExit(2)
