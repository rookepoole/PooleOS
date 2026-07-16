"""Parser-to-kernel promotion receipt for PooleGlyph Core IR evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "0.1"
ARTIFACT_KIND = "pooleos.pooleglyph_parser_kernel_promotion_receipt"
AUDIT_KIND = "pooleos.pooleglyph_core_ir_executable_audit"


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


def make_pooleglyph_parser_kernel_promotion_receipt(*, core_ir_executable_audit_path: Path) -> dict[str, Any]:
    audit = _read_json(core_ir_executable_audit_path)
    audit_summary = audit.get("summary", {}) if isinstance(audit.get("summary"), dict) else {}
    audit_source = (
        audit.get("source_boundary_receipt", {})
        if isinstance(audit.get("source_boundary_receipt"), dict)
        else {}
    )
    audit_status = str(audit.get("status", ""))
    audit_failed_checks = _int(audit_summary.get("failed_check_count"))
    phase66_present = audit_summary.get("phase66_audit_present") is True
    audit_promotion_allowed = audit_summary.get("parser_to_kernel_promotion_allowed") is True
    audit_handoff_allowed = audit_summary.get("kernel_handoff_allowed") is True
    audit_kernel_claimed = audit_summary.get("kernel_enforcement_claimed") is True
    executable_candidate_count = _int(audit_summary.get("executable_candidate_count"))
    metadata_zero_count = _int(audit_summary.get("metadata_zero_count"))
    unexpected_invalid_count = _int(audit_summary.get("unexpected_invalid_count"))

    checks = [
        _check("core_ir_executable_audit_present", core_ir_executable_audit_path.exists(), str(core_ir_executable_audit_path)),
        _check("core_ir_executable_audit_kind_valid", audit.get("artifact_kind") == AUDIT_KIND, str(audit.get("artifact_kind", ""))),
        _check(
            "core_ir_executable_audit_status_usable",
            audit_status in {"audited_non_promoting", "parser_to_kernel_ready"},
            audit_status,
        ),
        _check("core_ir_executable_audit_has_no_failed_checks", audit_failed_checks == 0, f"failed={audit_failed_checks}"),
        _check("executable_candidates_present", executable_candidate_count > 0, f"count={executable_candidate_count}"),
        _check("metadata_zero_outputs_present", metadata_zero_count > 0, f"count={metadata_zero_count}"),
        _check("no_unexpected_invalid_outputs", unexpected_invalid_count == 0, f"count={unexpected_invalid_count}"),
        _check("kernel_enforcement_not_claimed", not audit_kernel_claimed, f"kernel_enforcement_claimed={audit_kernel_claimed}"),
        _check(
            "promotion_requires_phase66_audit",
            not audit_promotion_allowed or phase66_present,
            f"phase66={phase66_present}; audit_promotion={audit_promotion_allowed}",
        ),
        _check(
            "handoff_requires_ready_audit",
            not audit_handoff_allowed or audit_status == "parser_to_kernel_ready",
            f"status={audit_status}; handoff={audit_handoff_allowed}",
        ),
        _check(
            "handoff_requires_promotion",
            not audit_handoff_allowed or audit_promotion_allowed,
            f"promotion={audit_promotion_allowed}; handoff={audit_handoff_allowed}",
        ),
    ]
    failed = [check for check in checks if not check["ok"]]
    parser_to_kernel_promotion_allowed = (
        not failed
        and phase66_present
        and audit_promotion_allowed
        and audit_status == "parser_to_kernel_ready"
    )
    kernel_handoff_allowed = parser_to_kernel_promotion_allowed and audit_handoff_allowed

    if failed:
        status = "fail"
    elif kernel_handoff_allowed:
        status = "parser_to_kernel_ready"
    else:
        status = "blocked_until_phase66"

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "status": status,
        "source_executable_audit": {
            "artifact_path": str(core_ir_executable_audit_path),
            "exists": core_ir_executable_audit_path.exists(),
            "artifact_kind": str(audit.get("artifact_kind", "")),
            "status": audit_status,
            "source_boundary_receipt": str(audit_source.get("artifact_path", "")),
            "phase66_audit_present": phase66_present,
            "parser_to_kernel_promotion_allowed": audit_promotion_allowed,
            "kernel_handoff_allowed": audit_handoff_allowed,
            "kernel_enforcement_claimed": audit_kernel_claimed,
            "failed_check_count": audit_failed_checks,
        },
        "promotion_decision": {
            "parser_to_kernel_promotion_allowed": parser_to_kernel_promotion_allowed,
            "kernel_handoff_allowed": kernel_handoff_allowed,
            "kernel_enforcement_claimed": False,
            "decision": "allow_parser_to_kernel_handoff" if kernel_handoff_allowed else "blocked_until_phase66_promotion",
            "reason": (
                "Phase 66 executable audit permits parser-to-kernel handoff."
                if kernel_handoff_allowed
                else "Executable Core IR candidates remain non-promoting until Phase 66 audit evidence permits handoff."
            ),
        },
        "checks": checks,
        "summary": {
            "failed_check_count": len(failed),
            "phase66_audit_present": phase66_present,
            "parser_to_kernel_promotion_allowed": parser_to_kernel_promotion_allowed,
            "kernel_handoff_allowed": kernel_handoff_allowed,
            "kernel_enforcement_claimed": False,
            "executable_candidate_count": executable_candidate_count,
            "metadata_zero_count": metadata_zero_count,
            "unexpected_invalid_count": unexpected_invalid_count,
        },
        "limitations": [
            "This receipt gates parser-to-kernel promotion language; it does not execute code in a kernel.",
            "A blocked receipt is valid evidence that promotion is intentionally unavailable.",
            "Kernel enforcement still requires booted kernel loader output and release-gated handoff evidence.",
        ],
        "next_steps": [
            "Bind this receipt into the permission/capability matrix.",
            "Require trap proof and PGB2 trap encoding to carry the same promotion decision.",
            "Only allow kernel handoff language when this receipt and booted-kernel evidence both agree.",
        ],
    }


def write_receipt(receipt: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
