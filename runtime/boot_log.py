"""PooleOS Lab boot-log marker validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "0.1"
ARTIFACT_KIND = "pooleos.boot_log_validation"
REQUIRED_MARKERS = [
    "POOLEOS_LAB_BOOT_START",
    "POOLEOS_LAB_DOCTOR_PASS",
    "POOLEOS_LAB_RELEASE_GATE_PASS",
    "POOLEOS_LAB_ARTIFACT_EXPORT_PASS",
    "POOLEOS_LAB_BOOT_DONE",
]
TRAP_INPUT_REQUIRED_MARKERS = [
    "POOLEOS_LAB_AUTOSTART_START",
    "POOLEOS_LAB_SHARED_MOUNT_PASS",
    "POOLEOS_LAB_INPUT_VERIFY_PASS",
    "POOLEOS_LAB_TRAP_ABI_BOUNDARY_PASS",
    *REQUIRED_MARKERS,
    "POOLEOS_LAB_AUTOSTART_DONE",
]


def required_markers_for_profile(profile: str = "base") -> list[str]:
    if profile == "trap-input":
        return list(TRAP_INPUT_REQUIRED_MARKERS)
    return list(REQUIRED_MARKERS)


def validate_boot_log_text(text: str, *, log_path: str = "<memory>", profile: str = "base") -> dict[str, Any]:
    markers = required_markers_for_profile(profile)
    missing = [marker for marker in markers if marker not in text]
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "log_path": log_path,
        "profile": profile,
        "ok": not missing,
        "required_markers": markers,
        "missing_markers": missing,
    }


def validate_boot_log_file(path: Path, *, profile: str = "base") -> dict[str, Any]:
    return validate_boot_log_text(path.read_text(encoding="utf-8", errors="replace"), log_path=str(path), profile=profile)


def write_validation(result: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
