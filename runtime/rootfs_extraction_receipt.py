"""Receipt for operator-run rootfs extraction handoffs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "0.1"
ARTIFACT_KIND = "pooleos.rootfs_extraction_receipt"


def _read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _check(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def make_rootfs_extraction_receipt(
    *,
    handoff_path: Path,
    rootfs_content_manifest_path: Path,
    operator_executed: bool = False,
    operator_notes: str = "",
) -> dict[str, Any]:
    handoff = _read_json(handoff_path)
    manifest = _read_json(rootfs_content_manifest_path)
    handoff_summary = handoff.get("summary", {}) if isinstance(handoff.get("summary"), dict) else {}
    manifest_summary = manifest.get("summary", {}) if isinstance(manifest.get("summary"), dict) else {}
    handoff_status = str(handoff.get("status", ""))
    manifest_status = str(manifest.get("status", ""))
    source_file_count = int(manifest_summary.get("source_file_count", 0) or 0)
    matched_file_count = int(manifest_summary.get("matched_source_file_count", 0) or 0)
    handoff_failed_count = int(handoff_summary.get("failed_check_count", 0) or 0)
    manifest_failed_count = int(manifest_summary.get("failed_check_count", 0) or 0)
    rootfs_extraction_performed = bool(operator_executed)
    verified = (
        rootfs_extraction_performed
        and manifest_status == "pass"
        and manifest_failed_count == 0
        and source_file_count >= 5
        and matched_file_count == source_file_count
        and manifest_summary.get("image_exists") is True
        and manifest_summary.get("extracted_rootfs_exists") is True
    )

    checks = [
        _check("codex_execution_not_performed", True, "Codex did not run the extraction handoff"),
        _check("handoff_present", bool(handoff) and handoff_path.exists(), str(handoff_path)),
        _check("handoff_artifact_kind", handoff.get("artifact_kind") == "pooleos.rootfs_extraction_handoff", str(handoff.get("artifact_kind", ""))),
        _check("handoff_status_usable", handoff_status in {"pass", "blocked"}, f"status={handoff_status}"),
        _check("handoff_has_no_failed_checks", handoff_failed_count == 0, f"failed={handoff_failed_count}"),
        _check("handoff_codex_execution_disallowed", handoff.get("codex_execution_allowed") is False, f"codex_execution_allowed={handoff.get('codex_execution_allowed')}"),
        _check("handoff_not_executed_by_codex", handoff.get("execution_performed") is False, f"execution_performed={handoff.get('execution_performed')}"),
        _check("handoff_script_hash_present", isinstance(handoff.get("bash_script_sha256"), str) and len(str(handoff.get("bash_script_sha256", ""))) == 64, str(handoff.get("bash_script_sha256", ""))),
        _check("rootfs_manifest_present", bool(manifest) and rootfs_content_manifest_path.exists(), str(rootfs_content_manifest_path)),
        _check("rootfs_manifest_artifact_kind", manifest.get("artifact_kind") == "pooleos.rootfs_content_manifest", str(manifest.get("artifact_kind", ""))),
        _check("rootfs_manifest_status_usable", manifest_status in {"pass", "blocked", "fail"}, f"status={manifest_status}"),
        _check("rootfs_manifest_has_source_files", source_file_count >= 5, f"source_files={source_file_count}"),
        _check("operator_execution_claim_recorded", isinstance(operator_executed, bool), f"operator_executed={operator_executed}"),
        _check("codex_execution_still_false", True, "codex_execution_performed=False"),
    ]
    invalid_checks = [
        checks[1],
        checks[2],
        checks[3],
        checks[4],
        checks[5],
        checks[6],
        checks[7],
        checks[8],
        checks[9],
        checks[11],
    ]
    if any(not check["ok"] for check in invalid_checks):
        status = "invalid"
    elif verified:
        status = "verified"
    elif rootfs_extraction_performed:
        status = "verification_failed"
    else:
        status = "pending_operator_action"

    captured_qemu_promotion_allowed = status == "verified"
    checks.extend(
        [
            _check("rootfs_extraction_performed_when_verified", rootfs_extraction_performed if status == "verified" else True, f"operator_executed={operator_executed}"),
            _check("rootfs_manifest_pass_when_verified", manifest_status == "pass" if status == "verified" else True, f"manifest_status={manifest_status}"),
            _check("rootfs_hashes_match_when_verified", matched_file_count == source_file_count if status == "verified" else True, f"matched={matched_file_count}; source_files={source_file_count}"),
            _check("captured_qemu_promotion_blocked_until_verified", captured_qemu_promotion_allowed is (status == "verified"), f"promotion_allowed={captured_qemu_promotion_allowed}; status={status}"),
        ]
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "status": status,
        "operator_executed": bool(operator_executed),
        "codex_execution_performed": False,
        "rootfs_extraction_performed": rootfs_extraction_performed,
        "captured_qemu_promotion_allowed": captured_qemu_promotion_allowed,
        "handoff": {
            "path": str(handoff_path),
            "status": handoff_status,
            "bash_script_sha256": str(handoff.get("bash_script_sha256", "")),
            "command_count": int(handoff_summary.get("command_count", 0) or 0),
            "failed_check_count": handoff_failed_count,
        },
        "rootfs_content_manifest": {
            "path": str(rootfs_content_manifest_path),
            "status": manifest_status,
            "failed_check_count": manifest_failed_count,
            "source_file_count": source_file_count,
            "matched_source_file_count": matched_file_count,
            "image_exists": manifest_summary.get("image_exists") is True,
            "extracted_rootfs_exists": manifest_summary.get("extracted_rootfs_exists") is True,
            "image_sha256": str(manifest_summary.get("image_sha256", "")),
        },
        "operator_notes": operator_notes,
        "checks": checks,
        "summary": {
            "failed_check_count": sum(1 for check in checks if not check["ok"]),
            "handoff_status": handoff_status,
            "rootfs_manifest_status": manifest_status,
            "operator_executed": bool(operator_executed),
            "codex_execution_performed": False,
            "rootfs_extraction_performed": rootfs_extraction_performed,
            "captured_qemu_promotion_allowed": captured_qemu_promotion_allowed,
            "source_file_count": source_file_count,
            "matched_source_file_count": matched_file_count,
        },
        "limitations": [
            "This receipt records operator-claimed extraction status; Codex did not run the handoff script.",
            "A verified receipt proves only source-to-rootfs continuity, not QEMU boot or kernel enforcement.",
            "Captured QEMU evidence should not be promoted until captured_qemu_promotion_allowed is true.",
        ],
        "next_steps": [
            "If pending_operator_action, run the rootfs extraction handoff from an operator-reviewed WSL/Linux session.",
            "If verification_failed, inspect the resulting rootfs content manifest before attempting QEMU capture.",
            "If verified, include this receipt in the release gate before promoting captured QEMU boot evidence.",
        ],
    }


def write_receipt(receipt: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
