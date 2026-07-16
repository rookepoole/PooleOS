"""Captured-QEMU promotion readiness reconciler."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "0.1"
ARTIFACT_KIND = "pooleos.qemu_captured_boot_readiness"


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


def make_qemu_captured_boot_readiness(
    *,
    rootfs_extraction_receipt_path: Path,
    qemu_captured_boot_receipt_path: Path,
    qemu_captured_boot_evidence_path: Path,
) -> dict[str, Any]:
    rootfs_receipt = _read_json(rootfs_extraction_receipt_path)
    captured_receipt = _read_json(qemu_captured_boot_receipt_path)
    captured_evidence = _read_json(qemu_captured_boot_evidence_path)

    rootfs_summary = rootfs_receipt.get("summary", {}) if isinstance(rootfs_receipt.get("summary"), dict) else {}
    rootfs_manifest = (
        rootfs_receipt.get("rootfs_content_manifest", {})
        if isinstance(rootfs_receipt.get("rootfs_content_manifest"), dict)
        else {}
    )
    captured_summary = (
        captured_receipt.get("summary", {}) if isinstance(captured_receipt.get("summary"), dict) else {}
    )
    captured_slot = (
        captured_receipt.get("captured_boot_evidence", {})
        if isinstance(captured_receipt.get("captured_boot_evidence"), dict)
        else {}
    )
    evidence_summary = (
        captured_evidence.get("summary", {}) if isinstance(captured_evidence.get("summary"), dict) else {}
    )
    evidence_validation = (
        captured_evidence.get("boot_log_validation", {})
        if isinstance(captured_evidence.get("boot_log_validation"), dict)
        else {}
    )

    rootfs_source_count = int(rootfs_manifest.get("source_file_count", 0) or 0)
    rootfs_matched_count = int(rootfs_manifest.get("matched_source_file_count", 0) or 0)
    evidence_exists = qemu_captured_boot_evidence_path.exists()
    expected_evidence_path = str(qemu_captured_boot_evidence_path)
    receipt_evidence_path = str(captured_slot.get("path", ""))
    paths_match = (
        captured_receipt.get("status") == "captured"
        and evidence_exists
        and Path(receipt_evidence_path).resolve() == qemu_captured_boot_evidence_path.resolve()
        if receipt_evidence_path
        else False
    )

    rootfs_verified = (
        rootfs_receipt.get("artifact_kind") == "pooleos.rootfs_extraction_receipt"
        and rootfs_receipt.get("status") == "verified"
        and rootfs_receipt.get("captured_qemu_promotion_allowed") is True
        and rootfs_receipt.get("rootfs_extraction_performed") is True
        and rootfs_summary.get("failed_check_count") == 0
        and rootfs_source_count >= 5
        and rootfs_matched_count == rootfs_source_count
        and rootfs_manifest.get("extracted_rootfs_exists") is True
    )
    receipt_captured = (
        captured_receipt.get("artifact_kind") == "pooleos.qemu_captured_boot_receipt"
        and captured_receipt.get("status") == "captured"
        and captured_receipt.get("boot_evidence_ingested") is True
        and captured_summary.get("failed_check_count") == 0
        and captured_summary.get("fixture_preserved") is True
        and captured_summary.get("captured_boot_evidence_valid") is True
        and captured_slot.get("exists") is True
        and captured_slot.get("evidence_source") == "captured_qemu_serial"
        and captured_slot.get("boot_evidence_claimed") is True
    )
    captured_evidence_valid = (
        evidence_exists
        and captured_evidence.get("artifact_kind") == "pooleos.qemu_boot_evidence"
        and captured_evidence.get("status") == "pass"
        and captured_evidence.get("evidence_source") == "captured_qemu_serial"
        and captured_evidence.get("boot_evidence_claimed") is True
        and evidence_summary.get("failed_check_count") == 0
        and evidence_summary.get("profile") == "trap-input"
        and evidence_summary.get("missing_marker_count") == 0
        and evidence_validation.get("ok") is True
        and evidence_validation.get("profile") == "trap-input"
    )

    checks = [
        _check(
            "rootfs_receipt_absent_or_structural",
            not rootfs_extraction_receipt_path.exists()
            or rootfs_receipt.get("artifact_kind") == "pooleos.rootfs_extraction_receipt",
            f"artifact_kind={rootfs_receipt.get('artifact_kind', '')}",
        ),
        _check(
            "captured_receipt_absent_or_structural",
            not qemu_captured_boot_receipt_path.exists()
            or captured_receipt.get("artifact_kind") == "pooleos.qemu_captured_boot_receipt",
            f"artifact_kind={captured_receipt.get('artifact_kind', '')}",
        ),
        _check(
            "captured_evidence_absent_or_structural",
            not evidence_exists or captured_evidence.get("artifact_kind") == "pooleos.qemu_boot_evidence",
            "pending capture" if not evidence_exists else f"artifact_kind={captured_evidence.get('artifact_kind', '')}",
        ),
        _check(
            "captured_evidence_absent_or_captured_source",
            not evidence_exists or captured_evidence.get("evidence_source") == "captured_qemu_serial",
            "pending capture" if not evidence_exists else f"source={captured_evidence.get('evidence_source', '')}",
        ),
        _check(
            "captured_evidence_absent_or_claiming",
            not evidence_exists or captured_evidence.get("boot_evidence_claimed") is True,
            "pending capture"
            if not evidence_exists
            else f"claimed={captured_evidence.get('boot_evidence_claimed', '')}",
        ),
    ]
    structural_failed = [check for check in checks if not check["ok"]]

    requirements = [
        _requirement(
            "rootfs_extraction_receipt_verified",
            rootfs_verified,
            f"status={rootfs_receipt.get('status', '')}; promotion={rootfs_receipt.get('captured_qemu_promotion_allowed', False)}; matched={rootfs_matched_count}/{rootfs_source_count}",
        ),
        _requirement(
            "qemu_captured_boot_receipt_captured",
            receipt_captured,
            f"status={captured_receipt.get('status', '')}; ingested={captured_receipt.get('boot_evidence_ingested', False)}; fixture_preserved={captured_summary.get('fixture_preserved', False)}",
        ),
        _requirement(
            "qemu_captured_boot_evidence_present",
            evidence_exists,
            expected_evidence_path,
        ),
        _requirement(
            "qemu_captured_boot_evidence_valid",
            captured_evidence_valid,
            "pending capture"
            if not evidence_exists
            else f"status={captured_evidence.get('status', '')}; source={captured_evidence.get('evidence_source', '')}; claimed={captured_evidence.get('boot_evidence_claimed', False)}; missing={evidence_summary.get('missing_marker_count', '')}",
        ),
        _requirement(
            "captured_receipt_matches_evidence_path",
            paths_match,
            f"receipt={receipt_evidence_path}; evidence={expected_evidence_path}",
        ),
    ]
    unmet = [requirement for requirement in requirements if not requirement["met"]]
    if structural_failed:
        status = "invalid"
    elif unmet:
        status = "blocked"
    else:
        status = "ready_for_promotion"

    promotion_language_allowed = status == "ready_for_promotion"
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "status": status,
        "promotion_language_allowed": promotion_language_allowed,
        "sources": {
            "rootfs_extraction_receipt": _source(rootfs_extraction_receipt_path, rootfs_receipt),
            "qemu_captured_boot_receipt": _source(qemu_captured_boot_receipt_path, captured_receipt),
            "qemu_captured_boot_evidence": _source(qemu_captured_boot_evidence_path, captured_evidence),
        },
        "requirements": requirements,
        "checks": checks,
        "summary": {
            "failed_check_count": len(structural_failed),
            "unmet_requirement_count": len(unmet),
            "rootfs_receipt_status": str(rootfs_receipt.get("status", "")),
            "qemu_captured_boot_receipt_status": str(captured_receipt.get("status", "")),
            "captured_evidence_exists": evidence_exists,
            "captured_evidence_valid": captured_evidence_valid,
            "promotion_language_allowed": promotion_language_allowed,
        },
        "limitations": [
            "This artifact reconciles proof readiness only; it does not run QEMU, mount rootfs, or create evidence.",
            "Promotion language is allowed only when rootfs continuity, captured boot receipt, and captured evidence all agree.",
            "Kernel enforcement and production readiness still require later kernel-owned loader and isolation evidence.",
        ],
        "next_steps": [
            "If blocked on rootfs, run the rootfs extraction handoff and re-emit the rootfs extraction receipt with --operator-executed.",
            "If blocked on capture, run the captured-QEMU launch bundle and emit qemu_boot_evidence.captured.json.",
            "If ready_for_promotion, include this artifact in the release gate before using captured-QEMU promotion language.",
        ],
    }


def write_readiness(readiness: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(readiness, indent=2, sort_keys=True) + "\n", encoding="utf-8")
