"""Kernel-owned boot handoff boundary for captured PooleOS Lab evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "0.1"
ARTIFACT_KIND = "pooleos.kernel_boot_handoff"


def _read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _check(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def _requirement(name: str, met: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "met": bool(met), "detail": detail}


def _source(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "artifact_kind": str(data.get("artifact_kind", "")),
        "status": str(data.get("status", "")),
    }


def _bool_from_nested(data: dict[str, Any], key: str) -> bool:
    value = data.get(key)
    return value is True


def make_kernel_boot_handoff(
    *,
    qemu_captured_boot_readiness_path: Path,
    qemu_boot_marker_contract_path: Path,
    boot_trap_bundle_manifest_path: Path,
    guest_loader_verification_path: Path,
) -> dict[str, Any]:
    readiness = _read_json(qemu_captured_boot_readiness_path)
    marker_contract = _read_json(qemu_boot_marker_contract_path)
    boot_manifest = _read_json(boot_trap_bundle_manifest_path)
    guest_verification = _read_json(guest_loader_verification_path)

    readiness_summary = readiness.get("summary", {}) if isinstance(readiness.get("summary"), dict) else {}
    marker_summary = marker_contract.get("summary", {}) if isinstance(marker_contract.get("summary"), dict) else {}
    marker_boundary = (
        marker_contract.get("kernel_pgvm2_boundary", {})
        if isinstance(marker_contract.get("kernel_pgvm2_boundary"), dict)
        else {}
    )
    boot_summary = boot_manifest.get("summary", {}) if isinstance(boot_manifest.get("summary"), dict) else {}
    lab_mount = boot_manifest.get("lab_mount", {}) if isinstance(boot_manifest.get("lab_mount"), dict) else {}
    verification_summary = (
        guest_verification.get("summary", {}) if isinstance(guest_verification.get("summary"), dict) else {}
    )
    expected_execution_count = int(boot_summary.get("expected_executed_instruction_count", 0) or 0)
    actual_execution_count = int(verification_summary.get("expected_executed_instruction_count", 0) or 0)
    loader_output_exists = guest_loader_verification_path.exists()
    marker_mapping_count = len(marker_contract.get("marker_mappings", [])) if isinstance(marker_contract.get("marker_mappings"), list) else 0
    expected_marker_count = int(marker_summary.get("expected_marker_count", 0) or marker_mapping_count or 0)

    readiness_ready = (
        readiness.get("artifact_kind") == "pooleos.qemu_captured_boot_readiness"
        and readiness.get("status") == "ready_for_promotion"
        and readiness.get("promotion_language_allowed") is True
        and readiness_summary.get("failed_check_count") == 0
        and readiness_summary.get("unmet_requirement_count") == 0
        and readiness_summary.get("captured_evidence_valid") is True
    )
    marker_contract_ready = (
        marker_contract.get("artifact_kind") == "pooleos.qemu_boot_marker_contract"
        and marker_contract.get("status") == "pass"
        and marker_contract.get("boot_evidence_claimed") is False
        and marker_contract.get("security_boundary_claimed") is False
        and marker_summary.get("failed_check_count") == 0
        and marker_summary.get("blocking_check_count") == 0
        and expected_marker_count > 0
        and marker_summary.get("marker_count", 0) == expected_marker_count
        and marker_summary.get("boundary_count", expected_marker_count) == expected_marker_count
    )
    boot_manifest_ready = (
        boot_manifest.get("artifact_kind") == "pooleos.boot_trap_bundle_manifest"
        and boot_manifest.get("status") == "pass"
        and boot_summary.get("failed_check_count") == 0
        and boot_summary.get("trap_evidence_present") is True
        and expected_execution_count > 0
    )
    guest_loader_verified = (
        loader_output_exists
        and guest_verification.get("artifact_kind") == "pooleos.boot_trap_bundle_verification"
        and guest_verification.get("status") == "pass"
        and verification_summary.get("failed_check_count") == 0
        and actual_execution_count == expected_execution_count
        and actual_execution_count > 0
    )
    kernel_claim_absent = (
        marker_boundary.get("kernel_boundary_claimed") is False
        and marker_boundary.get("pgvm2_execution_claimed") is False
        and marker_contract.get("security_boundary_claimed") is False
    )

    checks = [
        _check(
            "captured_readiness_absent_or_structural",
            not qemu_captured_boot_readiness_path.exists()
            or readiness.get("artifact_kind") == "pooleos.qemu_captured_boot_readiness",
            f"artifact_kind={readiness.get('artifact_kind', '')}",
        ),
        _check(
            "marker_contract_absent_or_structural",
            not qemu_boot_marker_contract_path.exists()
            or marker_contract.get("artifact_kind") == "pooleos.qemu_boot_marker_contract",
            f"artifact_kind={marker_contract.get('artifact_kind', '')}",
        ),
        _check(
            "boot_manifest_absent_or_structural",
            not boot_trap_bundle_manifest_path.exists()
            or boot_manifest.get("artifact_kind") == "pooleos.boot_trap_bundle_manifest",
            f"artifact_kind={boot_manifest.get('artifact_kind', '')}",
        ),
        _check(
            "guest_loader_output_absent_or_structural",
            not loader_output_exists
            or guest_verification.get("artifact_kind") == "pooleos.boot_trap_bundle_verification",
            "pending guest loader output"
            if not loader_output_exists
            else f"artifact_kind={guest_verification.get('artifact_kind', '')}",
        ),
        _check(
            "no_kernel_or_pgvm2_claim_in_sources",
            kernel_claim_absent,
            f"kernel={marker_boundary.get('kernel_boundary_claimed', '')}; pgvm2={marker_boundary.get('pgvm2_execution_claimed', '')}; security={marker_contract.get('security_boundary_claimed', '')}",
        ),
    ]
    structural_failed = [check for check in checks if not check["ok"]]

    requirements = [
        _requirement(
            "captured_boot_readiness_ready",
            readiness_ready,
            f"status={readiness.get('status', '')}; promotion={readiness.get('promotion_language_allowed', False)}; unmet={readiness_summary.get('unmet_requirement_count', '')}",
        ),
        _requirement(
            "marker_contract_pass",
            marker_contract_ready,
            f"status={marker_contract.get('status', '')}; markers={marker_summary.get('marker_count', 0)}; blockers={marker_summary.get('blocking_check_count', '')}",
        ),
        _requirement(
            "boot_trap_bundle_manifest_pass",
            boot_manifest_ready,
            f"status={boot_manifest.get('status', '')}; executed={expected_execution_count}; trap_evidence={boot_summary.get('trap_evidence_present', False)}",
        ),
        _requirement(
            "guest_loader_verification_present",
            loader_output_exists,
            str(guest_loader_verification_path),
        ),
        _requirement(
            "guest_loader_verification_pass",
            guest_loader_verified,
            "pending guest loader output"
            if not loader_output_exists
            else f"status={guest_verification.get('status', '')}; failed={verification_summary.get('failed_check_count', '')}; executed={actual_execution_count}/{expected_execution_count}",
        ),
        _requirement(
            "kernel_enforcement_not_claimed",
            kernel_claim_absent,
            "kernel/PGVM2 claim remains false",
        ),
    ]
    unmet = [requirement for requirement in requirements if not requirement["met"]]
    if structural_failed:
        status = "invalid"
    elif unmet:
        status = "blocked"
    else:
        status = "ready_for_kernel_handoff"

    handoff_allowed = status == "ready_for_kernel_handoff"
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "status": status,
        "kernel_handoff_allowed": handoff_allowed,
        "kernel_boundary_claimed": False,
        "pgvm2_execution_claimed": False,
        "sources": {
            "qemu_captured_boot_readiness": _source(qemu_captured_boot_readiness_path, readiness),
            "qemu_boot_marker_contract": _source(qemu_boot_marker_contract_path, marker_contract),
            "boot_trap_bundle_manifest": _source(boot_trap_bundle_manifest_path, boot_manifest),
            "guest_loader_verification": _source(guest_loader_verification_path, guest_verification),
        },
        "marker_level_evidence": {
            "captured_readiness_status": str(readiness.get("status", "")),
            "promotion_language_allowed": readiness.get("promotion_language_allowed") is True,
            "marker_contract_status": str(marker_contract.get("status", "")),
            "marker_count": int(marker_summary.get("marker_count", 0) or 0),
            "boot_evidence_claimed_by_marker_contract": marker_contract.get("boot_evidence_claimed") is True,
            "claim_boundary": "serial_marker_and_artifact_routing_only",
        },
        "guest_loader_outputs": [
            {
                "role": "boot_trap_bundle_verification",
                "guest_path": str(lab_mount.get("verification_result_path", "")),
                "host_capture_path": str(guest_loader_verification_path),
                "exists": loader_output_exists,
                "artifact_kind": str(guest_verification.get("artifact_kind", "")),
                "status": str(guest_verification.get("status", "")),
                "expected_executed_instruction_count": expected_execution_count,
                "actual_executed_instruction_count": actual_execution_count,
                "required_for_kernel_handoff": True,
            }
        ],
        "handoff_requirements": requirements,
        "checks": checks,
        "summary": {
            "failed_check_count": len(structural_failed),
            "unmet_requirement_count": len(unmet),
            "captured_readiness_status": str(readiness.get("status", "")),
            "marker_contract_status": str(marker_contract.get("status", "")),
            "boot_manifest_status": str(boot_manifest.get("status", "")),
            "guest_loader_verification_exists": loader_output_exists,
            "guest_loader_verification_status": str(guest_verification.get("status", "")),
            "kernel_handoff_allowed": handoff_allowed,
            "kernel_boundary_claimed": False,
            "pgvm2_execution_claimed": False,
        },
        "limitations": [
            "This handoff ties marker-level captured evidence to guest loader output slots; it does not execute a kernel loader.",
            "Kernel and PGVM2 execution claims remain false until a kernel-owned loader emits enforcement evidence.",
            "A ready handoff is an input to later kernel enforcement work, not production security proof.",
        ],
        "next_steps": [
            "Capture qemu_boot_evidence.captured.json and guest boot_trap_bundle_verification.json from the same QEMU run.",
            "Re-emit captured readiness and this handoff after guest loader output is collected.",
            "Implement a kernel-owned PGVM2 loader evidence artifact that consumes this handoff.",
        ],
    }


def write_handoff(handoff: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(handoff, indent=2, sort_keys=True) + "\n", encoding="utf-8")
