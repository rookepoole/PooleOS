"""Executable Core IR audit for the PooleGlyph-to-PooleOS boundary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "0.1"
ARTIFACT_KIND = "pooleos.pooleglyph_core_ir_executable_audit"
BOUNDARY_KIND = "pooleos.pooleglyph_core_ir_boundary_receipt"


def _check(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def _read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _record(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": str(value.get("path", "")),
        "sha256": str(value.get("sha256", "")),
        "classification": str(value.get("classification", "")),
        "ok": value.get("ok") is True,
        "module": str(value.get("module", "")),
        "program_count": _int(value.get("program_count")),
        "instruction_count": _int(value.get("instruction_count")),
        "validator_version": str(value.get("validator_version", "")),
        "public_safe_notes_present": value.get("public_safe_notes_present") is True,
        "diagnostic_codes": [
            str(code)
            for code in value.get("diagnostic_codes", [])
            if isinstance(code, str) and code
        ],
    }


def _records_by_class(records: list[dict[str, Any]], classification: str) -> list[dict[str, Any]]:
    return sorted(
        [_record(record) for record in records if record.get("classification") == classification],
        key=lambda item: item["path"].lower(),
    )


def make_pooleglyph_core_ir_executable_audit(*, core_ir_boundary_receipt_path: Path) -> dict[str, Any]:
    receipt = _read_json(core_ir_boundary_receipt_path)
    receipt_summary = receipt.get("summary", {}) if isinstance(receipt.get("summary"), dict) else {}
    validation_summary = (
        receipt.get("core_ir_validation_summary", {})
        if isinstance(receipt.get("core_ir_validation_summary"), dict)
        else {}
    )
    validation_records = [
        record
        for record in receipt.get("validation_records", [])
        if isinstance(record, dict)
    ]
    executable_candidates = _records_by_class(validation_records, "validated_executable_candidate")
    metadata_zero_outputs = _records_by_class(validation_records, "validated_metadata_zero_program")
    expected_negative_fixtures = _records_by_class(validation_records, "expected_negative_fixture")
    structural_anomalies = _records_by_class(validation_records, "validated_structural_anomaly")
    unexpected_invalid = _records_by_class(validation_records, "unexpected_invalid")

    phase66_present = receipt_summary.get("phase66_audit_present") is True
    receipt_promotion_allowed = receipt_summary.get("parser_to_kernel_promotion_allowed") is True
    kernel_claimed = receipt.get("kernel_enforcement_claimed") is True
    receipt_failed_checks = _int(receipt_summary.get("failed_check_count"))
    failed_promotion_gates = _int(receipt_summary.get("failed_promotion_gate_count"))
    public_safe_count = _int(validation_summary.get("public_safe_note_count"))
    validation_count = _int(validation_summary.get("validation_file_count"))

    checks = [
        _check("core_ir_boundary_receipt_present", core_ir_boundary_receipt_path.exists(), str(core_ir_boundary_receipt_path)),
        _check("core_ir_boundary_receipt_kind_valid", receipt.get("artifact_kind") == BOUNDARY_KIND, str(receipt.get("artifact_kind", ""))),
        _check(
            "core_ir_boundary_receipt_status_usable",
            receipt.get("status") in {"phase66_pending", "validated_non_promoting", "parser_to_kernel_ready"},
            str(receipt.get("status", "")),
        ),
        _check("core_ir_boundary_receipt_has_no_failed_checks", receipt_failed_checks == 0, f"failed={receipt_failed_checks}"),
        _check("validation_records_present", bool(validation_records), f"count={len(validation_records)}"),
        _check("executable_candidates_present", bool(executable_candidates), f"count={len(executable_candidates)}"),
        _check("metadata_zero_outputs_present", bool(metadata_zero_outputs), f"count={len(metadata_zero_outputs)}"),
        _check("expected_negative_fixtures_present", len(expected_negative_fixtures) >= 3, f"count={len(expected_negative_fixtures)}"),
        _check("no_structural_anomalies", not structural_anomalies, f"count={len(structural_anomalies)}"),
        _check("no_unexpected_invalid_outputs", not unexpected_invalid, f"count={len(unexpected_invalid)}"),
        _check(
            "all_validation_reports_public_safe",
            validation_count > 0 and public_safe_count == validation_count,
            f"public_safe={public_safe_count}; validation={validation_count}",
        ),
        _check("kernel_enforcement_not_claimed", not kernel_claimed, f"kernel_enforcement_claimed={kernel_claimed}"),
    ]
    failed = [check for check in checks if not check["ok"]]
    parser_to_kernel_promotion_allowed = (
        not failed
        and phase66_present
        and receipt_promotion_allowed
        and failed_promotion_gates == 0
        and not kernel_claimed
    )
    kernel_handoff_allowed = parser_to_kernel_promotion_allowed and receipt.get("status") == "parser_to_kernel_ready"

    if failed:
        status = "fail"
    elif kernel_handoff_allowed:
        status = "parser_to_kernel_ready"
    else:
        status = "audited_non_promoting"

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "status": status,
        "source_boundary_receipt": {
            "artifact_path": str(core_ir_boundary_receipt_path),
            "exists": core_ir_boundary_receipt_path.exists(),
            "artifact_kind": str(receipt.get("artifact_kind", "")),
            "status": str(receipt.get("status", "")),
            "phase66_audit_present": phase66_present,
            "parser_to_kernel_promotion_allowed": receipt_promotion_allowed,
            "kernel_enforcement_claimed": kernel_claimed,
            "failed_check_count": receipt_failed_checks,
            "failed_promotion_gate_count": failed_promotion_gates,
        },
        "audit_scope": {
            "validation_file_count": validation_count,
            "valid_file_count": _int(validation_summary.get("valid_file_count")),
            "validator_versions": [
                str(version)
                for version in validation_summary.get("validator_versions", [])
                if isinstance(version, str)
            ],
            "total_program_count": _int(validation_summary.get("total_program_count")),
            "total_instruction_count": _int(validation_summary.get("total_instruction_count")),
            "public_safe_note_count": public_safe_count,
        },
        "executable_candidates": executable_candidates,
        "metadata_zero_outputs": metadata_zero_outputs,
        "expected_negative_fixtures": expected_negative_fixtures,
        "structural_anomalies": structural_anomalies,
        "unexpected_invalid_outputs": unexpected_invalid,
        "boundary_decisions": {
            "executable_candidate_decision": "structural_candidate_only",
            "metadata_zero_decision": "metadata_only_not_kernel_program",
            "parser_to_kernel_decision": (
                "allowed_by_phase66_audit"
                if parser_to_kernel_promotion_allowed
                else "blocked_until_phase66_promotion_receipt"
            ),
            "kernel_handoff_allowed": kernel_handoff_allowed,
            "kernel_enforcement_claimed": False,
            "reason": (
                "Phase 66 audit and parser-to-kernel promotion gates are satisfied."
                if parser_to_kernel_promotion_allowed
                else "Current PooleGlyph evidence separates candidates but remains non-promoting for PooleOS kernel handoff."
            ),
        },
        "checks": checks,
        "summary": {
            "failed_check_count": len(failed),
            "phase66_audit_present": phase66_present,
            "parser_to_kernel_promotion_allowed": parser_to_kernel_promotion_allowed,
            "kernel_handoff_allowed": kernel_handoff_allowed,
            "kernel_enforcement_claimed": False,
            "executable_candidate_count": len(executable_candidates),
            "metadata_zero_count": len(metadata_zero_outputs),
            "expected_negative_fixture_count": len(expected_negative_fixtures),
            "structural_anomaly_count": len(structural_anomalies),
            "unexpected_invalid_count": len(unexpected_invalid),
            "validation_file_count": len(validation_records),
        },
        "limitations": [
            "Executable candidate means public Core IR validation found nonzero programs and instructions; it does not prove PooleOS kernel execution.",
            "Metadata-zero outputs remain declaration evidence and must not be promoted as kernel programs.",
            "This audit is non-promoting until a Phase 66 parser-to-kernel promotion receipt is present and release-gated.",
        ],
        "next_steps": [
            "Bind this audit into the permission/capability matrix.",
            "Propagate the audit binding through capability trap proof and PGB2 trap encoding evidence.",
            "Require kernel handoff language to remain blocked unless this audit reports parser_to_kernel_ready.",
        ],
    }


def write_audit(audit: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
