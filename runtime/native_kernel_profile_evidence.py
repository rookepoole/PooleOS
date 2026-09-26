"""Shared provenance checks for native execution-profile receipts."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Callable

from runtime import native_kernel_entry
from runtime import native_kernel_transfer, native_pooleboot


def kernel_entry_errors(build: Any, root: Path) -> list[str]:
    if not isinstance(build, dict) or not isinstance(build.get("kernel_entry"), dict):
        return ["embedded kernel entry evidence is missing or malformed"]
    try:
        current = native_kernel_entry.read_json(root / native_kernel_entry.READINESS_RELATIVE)
        issues = native_kernel_entry.readiness_errors(current, root)
        if issues:
            return ["embedded kernel entry dependency is invalid: " + "; ".join(issues)]
        # JSON identity also rejects bool/int and float/int equality substitutions.
        embedded_json = json.dumps(build["kernel_entry"], sort_keys=True, allow_nan=False)
        current_json = json.dumps(current, sort_keys=True, allow_nan=False)
        if embedded_json != current_json:
            return ["embedded kernel entry evidence differs from the current validated receipt"]
        return []
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        return [f"embedded kernel entry dependency cannot be validated: {type(error).__name__}"]


def recorded_pair_errors(
    execution: Any,
    run_prefix: str,
    marker_validator: Callable[[list[str]], dict[str, Any]],
    context: str,
) -> list[str]:
    """Validate recorded two-run consistency, not freshness or authentication."""
    if not isinstance(execution, dict):
        return [f"{context} recorded execution is not an object"]
    errors: list[str] = []
    if (
        type(execution.get("run_count")) is not int
        or execution["run_count"] != 2
        or any(execution.get(key) is not True for key in (
            "exact_marker_match", "exact_screenshot_match", "exact_pbp1_match"
        ))
    ):
        errors.append(f"{context} recorded two-run metadata changed")
    runs = execution.get("runs")
    if (
        not isinstance(runs, list)
        or len(runs) != 2
        or any(not isinstance(run, dict) for run in runs)
        or [run.get("run_id") for run in runs] != [f"{run_prefix}-1", f"{run_prefix}-2"]
    ):
        return [*errors, f"{context} recorded run coverage changed"]

    def exact(left: Any, right: Any) -> bool:
        return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(right, sort_keys=True, allow_nan=False)

    for run in runs:
        try:
            if type(run.get("qemu_exit_code")) is not int or run["qemu_exit_code"] != 0:
                raise ValueError("recorded emulator exit is missing, malformed or unsuccessful")
            frame = run.get("screenshot")
            if (
                not isinstance(frame, dict)
                or frame.get("nonblank") is not True
                or not isinstance(frame.get("sha256"), str)
                or re.fullmatch(r"[0-9A-F]{64}", frame["sha256"]) is None
            ):
                raise ValueError("recorded frame is missing or malformed")
            markers = run.get("markers")
            if not isinstance(markers, list) or any(not isinstance(item, str) for item in markers):
                raise ValueError("recorded markers are not a string list")
            parsed = marker_validator(markers)
            if not exact(run.get("marker_summary"), parsed):
                raise ValueError("recorded summary differs from parsed markers or their exact types")
            digest = hashlib.sha256(native_pooleboot.canonical_json_bytes(markers)).hexdigest().upper()
            if run.get("marker_sha256") != digest:
                raise ValueError("recorded digest differs from exact markers")
            transcript = run.get("pbp1_transcript")
            if not isinstance(transcript, dict) or not isinstance(transcript.get("core"), dict):
                raise ValueError("recorded handoff or core is not an object")
            prefix = parsed["transfer_prefix"]
            binding = native_kernel_transfer.validate_transcript_binding(prefix, transcript)
            if not exact(run.get("transcript_binding"), binding):
                raise ValueError("recorded handoff binding changed")
            oracle = run.get("independent_kernel_revalidation")
            guest = prefix["kernel_revalidation"]
            if (
                not isinstance(oracle, dict)
                or oracle.get("contract_id") != "PKREVAL1"
                or oracle.get("guest_host_exact_match") is not True
                or not exact({key: oracle.get(key) for key in guest}, guest)
            ):
                raise ValueError("recorded revalidation differs from guest markers")
            if any(run.get(key) is not True for key in (
                "serial_debugcon_exact_match", "pbp1_serial_debugcon_exact_match"
            )):
                raise ValueError("recorded dual-channel agreement changed")
        except (KeyError, TypeError, ValueError, AttributeError) as error:
            errors.append(f"{context} {run['run_id']} invalid recorded evidence: {error}")
    try:
        if any(not exact(runs[0].get(key), runs[1].get(key)) for key in (
            "markers", "pbp1_transcript", "screenshot"
        )):
            errors.append(f"{context} recorded two-run equality changed")
    except (TypeError, ValueError):
        errors.append(f"{context} recorded two-run evidence is not canonical JSON")
    return errors
