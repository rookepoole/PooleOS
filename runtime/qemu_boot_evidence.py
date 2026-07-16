"""QEMU serial boot evidence for PooleOS Lab."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from runtime import boot_log


SCHEMA_VERSION = "0.1"
ARTIFACT_KIND = "pooleos.qemu_boot_evidence"
FIXTURE_SOURCE = "fixture"
CAPTURED_SOURCE = "captured_qemu_serial"
EVIDENCE_SOURCES = {FIXTURE_SOURCE, CAPTURED_SOURCE}


def default_fixture_path(root: Path) -> Path:
    return root / "lab-os" / "qemu" / "fixtures" / "trap-input-success.serial.log"


def _check(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def _sha256_file(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _read_validation(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def make_qemu_boot_evidence(
    *,
    root: Path,
    log_path: Path | None = None,
    boot_log_validation_path: Path | None = None,
    evidence_source: str = FIXTURE_SOURCE,
    profile: str = "trap-input",
) -> dict[str, Any]:
    resolved_log = log_path or default_fixture_path(root)
    validation = _read_validation(boot_log_validation_path)
    if not validation and resolved_log.exists():
        validation = boot_log.validate_boot_log_file(resolved_log, profile=profile)

    text = resolved_log.read_text(encoding="utf-8", errors="replace") if resolved_log.exists() else ""
    required_markers = list(validation.get("required_markers") or boot_log.required_markers_for_profile(profile))
    missing_markers = list(validation.get("missing_markers") or [])
    validation_ok = validation.get("ok") is True
    validation_profile = str(validation.get("profile", profile))
    boot_evidence_claimed = evidence_source == CAPTURED_SOURCE and validation_ok

    checks = [
        _check("evidence_source_known", evidence_source in EVIDENCE_SOURCES, evidence_source),
        _check("log_path_exists", resolved_log.exists(), str(resolved_log)),
        _check("boot_log_validation_present", bool(validation), str(boot_log_validation_path or "")),
        _check("boot_log_profile_trap_input", validation_profile == "trap-input", f"profile={validation_profile}"),
        _check("boot_log_validation_ok", validation_ok, f"missing={missing_markers}"),
        _check(
            "trap_input_markers_required",
            "POOLEOS_LAB_INPUT_VERIFY_PASS" in required_markers
            and "POOLEOS_LAB_TRAP_ABI_BOUNDARY_PASS" in required_markers
            and "POOLEOS_LAB_SHARED_MOUNT_PASS" in required_markers
            and "POOLEOS_LAB_AUTOSTART_DONE" in required_markers,
            f"required={required_markers}",
        ),
        _check(
            "fixture_does_not_claim_captured_boot",
            evidence_source != FIXTURE_SOURCE or boot_evidence_claimed is False,
            f"source={evidence_source}; boot_evidence_claimed={boot_evidence_claimed}",
        ),
        _check(
            "captured_source_claims_boot_only_when_valid",
            evidence_source != CAPTURED_SOURCE or boot_evidence_claimed is True,
            f"source={evidence_source}; validation_ok={validation_ok}",
        ),
    ]
    failed = [check for check in checks if not check["ok"]]

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "status": "pass" if not failed else "fail",
        "evidence_source": evidence_source,
        "boot_evidence_claimed": boot_evidence_claimed,
        "log": {
            "path": str(resolved_log),
            "exists": resolved_log.exists(),
            "sha256": _sha256_file(resolved_log),
            "byte_count": resolved_log.stat().st_size if resolved_log.exists() else 0,
            "line_count": len(text.splitlines()) if text else 0,
        },
        "boot_log_validation": validation,
        "boot_log_validation_path": str(boot_log_validation_path or ""),
        "checks": checks,
        "summary": {
            "failed_check_count": len(failed),
            "required_marker_count": len(required_markers),
            "missing_marker_count": len(missing_markers),
            "profile": validation_profile,
            "evidence_source": evidence_source,
            "boot_evidence_claimed": boot_evidence_claimed,
        },
        "limitations": [
            "Fixture evidence validates the serial-marker contract but is not a captured QEMU boot.",
            "Captured serial evidence is claimed only when evidence_source is captured_qemu_serial and the trap-input validation passes.",
            "Marker evidence proves the configured smoke path ran; it does not prove production readiness or kernel isolation.",
        ],
        "next_steps": [
            "Boot the Lab image under QEMU with the staged shared folder.",
            "Capture the serial log to a file and emit this artifact with --source captured_qemu_serial.",
            "Bind captured boot evidence into the release gate before claiming guest execution.",
        ],
    }


def write_evidence(evidence: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
