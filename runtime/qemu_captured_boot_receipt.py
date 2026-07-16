"""Receipt for captured QEMU serial boot evidence handoff."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "0.1"
ARTIFACT_KIND = "pooleos.qemu_captured_boot_receipt"


def _check(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def _read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _slot(path: Path | None, evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": str(path or ""),
        "exists": bool(path and path.exists()),
        "artifact_kind": str(evidence.get("artifact_kind", "")),
        "status": str(evidence.get("status", "")),
        "evidence_source": str(evidence.get("evidence_source", "")),
        "boot_evidence_claimed": bool(evidence.get("boot_evidence_claimed", False)),
    }


def make_qemu_captured_boot_receipt(
    *,
    fixture_evidence_path: Path,
    captured_evidence_path: Path,
    operator_executed: bool = False,
) -> dict[str, Any]:
    fixture = _read_json(fixture_evidence_path)
    captured = _read_json(captured_evidence_path)
    captured_exists = captured_evidence_path.exists()
    paths_are_separate = fixture_evidence_path.resolve() != captured_evidence_path.resolve()
    fixture_valid = (
        fixture.get("artifact_kind") == "pooleos.qemu_boot_evidence"
        and fixture.get("status") == "pass"
        and fixture.get("evidence_source") == "fixture"
        and fixture.get("boot_evidence_claimed") is False
    )
    captured_valid = (
        captured.get("artifact_kind") == "pooleos.qemu_boot_evidence"
        and captured.get("status") == "pass"
        and captured.get("evidence_source") == "captured_qemu_serial"
        and captured.get("boot_evidence_claimed") is True
    )
    checks = [
        _check("fixture_evidence_present", fixture_evidence_path.exists(), str(fixture_evidence_path)),
        _check(
            "fixture_evidence_is_non_claiming_fixture",
            fixture_valid,
            f"source={fixture.get('evidence_source', '')}; claimed={fixture.get('boot_evidence_claimed', '')}",
        ),
        _check("captured_path_separate_from_fixture", paths_are_separate, str(captured_evidence_path)),
        _check(
            "captured_evidence_absent_or_valid",
            not captured_exists or captured_valid,
            "pending capture" if not captured_exists else f"source={captured.get('evidence_source', '')}; claimed={captured.get('boot_evidence_claimed', '')}",
        ),
        _check("codex_did_not_claim_operator_execution", True, f"operator_executed={operator_executed}"),
    ]
    failed = [check for check in checks if not check["ok"]]
    if failed:
        status = "invalid"
    elif captured_exists and captured_valid:
        status = "captured"
    else:
        status = "pending_capture"

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "status": status,
        "fixture_boot_evidence": _slot(fixture_evidence_path, fixture),
        "captured_boot_evidence": _slot(captured_evidence_path, captured),
        "operator_receipt": {
            "operator_executed": bool(operator_executed),
            "codex_execution_performed": False,
            "expected_launcher_mode": "run-pooleos-lab.ps1 real boot or -EmitCapturedEvidenceOnly",
        },
        "boot_evidence_ingested": status == "captured",
        "checks": checks,
        "summary": {
            "failed_check_count": len(failed),
            "captured_evidence_exists": captured_exists,
            "captured_boot_evidence_valid": captured_valid,
            "fixture_preserved": fixture_valid and paths_are_separate,
            "boot_evidence_ingested": status == "captured",
        },
        "limitations": [
            "Pending capture receipts reserve a separate captured evidence slot but do not prove a QEMU boot.",
            "Captured receipts require a valid captured_qemu_serial evidence artifact and a separate fixture evidence artifact.",
            "Operator receipt fields record evidence handoff state only; they do not modify host or VM state.",
        ],
        "next_steps": [
            "Run the Lab QEMU launcher with BootValidationOutput and QemuBootEvidenceOutput paths.",
            "Emit this receipt again with --captured-evidence pointing at qemu_boot_evidence.captured.json.",
            "Pass both --qemu-boot-evidence and --qemu-captured-boot-evidence to the release gate after capture.",
        ],
    }


def write_receipt(receipt: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
