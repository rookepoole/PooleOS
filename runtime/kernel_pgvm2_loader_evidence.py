"""Kernel PGVM2 loader evidence boundary for PooleOS."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "0.1"
ARTIFACT_KIND = "pooleos.kernel_pgvm2_loader_evidence"
LOADER_OUTPUT_KIND = "pooleos.kernel_pgvm2_loader_output"

PLANNED_KERNEL_CHECKS: tuple[dict[str, str], ...] = (
    {
        "name": "handoff_digest_lock",
        "required_input": "kernel_boot_handoff.source_handoff_sha256",
        "expected_kernel_action": "Verify the loader input bytes match the handoff digest before using any guest evidence.",
        "evidence_field": "source_handoff_sha256",
    },
    {
        "name": "trap_bundle_signature_verify",
        "required_input": "boot_trap_bundle_manifest bundle and replay hashes",
        "expected_kernel_action": "Verify the PGB2 bundle, replay proof, signed metric section, and trap sections before loading.",
        "evidence_field": "kernel_checks.trap_bundle_signature_verify",
    },
    {
        "name": "pgvm2_bytecode_decode",
        "required_input": "PGB2 TRAP_ENCODING section",
        "expected_kernel_action": "Decode the trap byte stream with the frozen PGVM2 kernel ABI decoder.",
        "evidence_field": "kernel_checks.pgvm2_bytecode_decode",
    },
    {
        "name": "capability_table_install",
        "required_input": "PooleGlyph permission/capability matrix",
        "expected_kernel_action": "Install a closed-by-default capability table before any PGVM2 instruction executes.",
        "evidence_field": "kernel_checks.capability_table_install",
    },
    {
        "name": "memory_isolation_map",
        "required_input": "microkernel isolation policy",
        "expected_kernel_action": "Map PGVM2 code, data, trace, and capability regions into isolated kernel-owned ranges.",
        "evidence_field": "kernel_checks.memory_isolation_map",
    },
    {
        "name": "trap_instruction_execution",
        "required_input": "handoff expected_executed_instruction_count",
        "expected_kernel_action": "Execute exactly the expected trap instruction count and record every trap outcome.",
        "evidence_field": "summary.actual_executed_instruction_count",
    },
    {
        "name": "serial_evidence_bind",
        "required_input": "captured serial evidence and kernel build id",
        "expected_kernel_action": "Emit a booted kernel receipt binding the serial evidence, handoff digest, and kernel build id.",
        "evidence_field": "kernel_checks.serial_evidence_bind",
    },
    {
        "name": "pooleglyph_source_anchor_digest_bind",
        "required_input": "pooleglyph_source_anchor",
        "expected_kernel_action": "Bind the booted kernel transcript to the PooleGlyph source anchor used by the release gate.",
        "evidence_field": "kernel_loader_output.pooleglyph_source_anchor_sha256",
    },
    {
        "name": "parser_promotion_receipt_digest_bind",
        "required_input": "pooleglyph_parser_kernel_promotion_receipt",
        "expected_kernel_action": "Bind the booted kernel transcript to the parser promotion receipt used by the release gate.",
        "evidence_field": "kernel_loader_output.pooleglyph_parser_kernel_promotion_receipt_sha256",
    },
    {
        "name": "parser_promotion_receipt_bind",
        "required_input": "pooleglyph_parser_kernel_promotion_receipt",
        "expected_kernel_action": "Refuse parser-backed PGVM2 enforcement unless the PooleGlyph parser-to-kernel promotion receipt is ready.",
        "evidence_field": "parser_promotion_summary.parser_promotion_ready_for_enforcement",
    },
    {
        "name": "negative_claim_guard",
        "required_input": "all previous kernel checks",
        "expected_kernel_action": "Keep kernel_enforcement_claimed false unless every required kernel check passes.",
        "evidence_field": "kernel_enforcement_claimed",
    },
)


def _read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha256(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _handoff_expected_count(handoff: dict[str, Any]) -> int:
    outputs = handoff.get("guest_loader_outputs", [])
    if not isinstance(outputs, list) or not outputs:
        return 0
    first = outputs[0] if isinstance(outputs[0], dict) else {}
    return _int(first.get("expected_executed_instruction_count"))


def _output_check_satisfied(loader_output: dict[str, Any], name: str) -> bool:
    checks = loader_output.get("kernel_checks", [])
    if not isinstance(checks, list):
        return False
    for check in checks:
        if isinstance(check, dict) and check.get("name") == name and check.get("ok") is True:
            return True
    return False


def _planned_checks(loader_output: dict[str, Any]) -> list[dict[str, Any]]:
    planned: list[dict[str, Any]] = []
    for check in PLANNED_KERNEL_CHECKS:
        satisfied = _output_check_satisfied(loader_output, check["name"])
        planned.append(
            {
                **check,
                "satisfied": satisfied,
                "detail": "satisfied by booted kernel loader output" if satisfied else "pending booted kernel loader output",
            }
        )
    return planned


def make_kernel_pgvm2_loader_evidence(
    *,
    kernel_boot_handoff_path: Path,
    kernel_loader_output_path: Path,
    pooleglyph_source_anchor_path: Path | None = None,
    parser_kernel_promotion_receipt_path: Path | None = None,
) -> dict[str, Any]:
    handoff = _read_json(kernel_boot_handoff_path)
    loader_output = _read_json(kernel_loader_output_path)
    source_anchor = _read_json(pooleglyph_source_anchor_path)
    parser_promotion = _read_json(parser_kernel_promotion_receipt_path)

    handoff_summary = handoff.get("summary", {}) if isinstance(handoff.get("summary"), dict) else {}
    loader_summary = (
        loader_output.get("summary", {}) if isinstance(loader_output.get("summary"), dict) else {}
    )
    source_anchor_summary = (
        source_anchor.get("summary", {}) if isinstance(source_anchor.get("summary"), dict) else {}
    )
    parser_promotion_summary = (
        parser_promotion.get("summary", {}) if isinstance(parser_promotion.get("summary"), dict) else {}
    )
    source_handoff_sha256 = _sha256(kernel_boot_handoff_path)
    source_anchor_sha256 = _sha256(pooleglyph_source_anchor_path)
    parser_promotion_sha256 = _sha256(parser_kernel_promotion_receipt_path)
    loader_output_exists = kernel_loader_output_path.exists()
    source_anchor_exists = pooleglyph_source_anchor_path is not None and pooleglyph_source_anchor_path.exists()
    source_anchor_bound = (
        source_anchor_exists
        and source_anchor.get("artifact_kind") == "pooleos.pooleglyph_source_anchor"
        and source_anchor.get("status") in {"pass", "warn"}
        and _int(source_anchor_summary.get("failed_check_count")) == 0
    )
    parser_promotion_exists = parser_kernel_promotion_receipt_path is not None and parser_kernel_promotion_receipt_path.exists()
    parser_promotion_status = str(parser_promotion.get("status", ""))
    parser_promotion_bound = (
        parser_promotion_exists
        and parser_promotion.get("artifact_kind") == "pooleos.pooleglyph_parser_kernel_promotion_receipt"
        and parser_promotion_status in {"blocked_until_phase66", "parser_to_kernel_ready"}
        and _int(parser_promotion_summary.get("failed_check_count")) == 0
        and parser_promotion_summary.get("kernel_enforcement_claimed") is False
    )
    parser_promotion_ready = (
        parser_promotion_bound
        and parser_promotion_status == "parser_to_kernel_ready"
        and parser_promotion_summary.get("phase66_audit_present") is True
        and parser_promotion_summary.get("parser_to_kernel_promotion_allowed") is True
        and parser_promotion_summary.get("kernel_handoff_allowed") is True
    )
    expected_count = _handoff_expected_count(handoff)
    actual_count = _int(loader_summary.get("actual_executed_instruction_count"))
    output_expected_count = _int(loader_summary.get("expected_executed_instruction_count"))
    output_handoff_hash = str(loader_output.get("source_handoff_sha256", ""))
    output_source_anchor_hash = str(loader_output.get("pooleglyph_source_anchor_sha256", ""))
    output_parser_promotion_hash = str(
        loader_output.get("pooleglyph_parser_kernel_promotion_receipt_sha256", "")
    )
    handoff_hash_matches = bool(
        loader_output_exists and source_handoff_sha256 and output_handoff_hash == source_handoff_sha256
    )
    source_anchor_hash_matches = bool(
        loader_output_exists and source_anchor_sha256 and output_source_anchor_hash == source_anchor_sha256
    )
    parser_promotion_hash_matches = bool(
        loader_output_exists and parser_promotion_sha256 and output_parser_promotion_hash == parser_promotion_sha256
    )

    handoff_ready = (
        handoff.get("artifact_kind") == "pooleos.kernel_boot_handoff"
        and handoff.get("status") == "ready_for_kernel_handoff"
        and handoff.get("kernel_handoff_allowed") is True
        and handoff.get("kernel_boundary_claimed") is False
        and handoff.get("pgvm2_execution_claimed") is False
        and handoff_summary.get("failed_check_count") == 0
        and handoff_summary.get("unmet_requirement_count") == 0
    )

    planned_checks = _planned_checks(loader_output)
    all_kernel_checks_satisfied = all(check["satisfied"] for check in planned_checks)
    claimed_enforcement = (
        loader_output.get("kernel_enforcement_claimed") is True
        or loader_output.get("pgvm2_execution_claimed") is True
    )

    loader_output_valid = (
        loader_output_exists
        and loader_output.get("artifact_kind") == LOADER_OUTPUT_KIND
        and loader_output.get("status") == "pass"
        and loader_output.get("booted_kernel_path") is True
        and loader_output.get("kernel_enforcement_claimed") is True
        and loader_output.get("pgvm2_execution_claimed") is True
        and loader_summary.get("failed_check_count") == 0
        and _int(loader_summary.get("kernel_check_count")) >= len(PLANNED_KERNEL_CHECKS)
        and _int(loader_summary.get("satisfied_kernel_check_count")) >= len(PLANNED_KERNEL_CHECKS)
        and expected_count > 0
        and output_expected_count == expected_count
        and actual_count == expected_count
        and handoff_hash_matches
        and source_anchor_hash_matches
        and parser_promotion_hash_matches
        and all_kernel_checks_satisfied
        and parser_promotion_ready
    )

    checks = [
        _check(
            "kernel_handoff_absent_or_structural",
            not kernel_boot_handoff_path.exists() or handoff.get("artifact_kind") == "pooleos.kernel_boot_handoff",
            f"artifact_kind={handoff.get('artifact_kind', '')}",
        ),
        _check(
            "kernel_loader_output_absent_or_structural",
            not loader_output_exists or loader_output.get("artifact_kind") == LOADER_OUTPUT_KIND,
            "pending booted kernel output"
            if not loader_output_exists
            else f"artifact_kind={loader_output.get('artifact_kind', '')}",
        ),
        _check(
            "pooleglyph_source_anchor_absent_or_structural",
            not source_anchor_exists
            or source_anchor.get("artifact_kind") == "pooleos.pooleglyph_source_anchor",
            "not provided"
            if not source_anchor_exists
            else f"artifact_kind={source_anchor.get('artifact_kind', '')}",
        ),
        _check(
            "parser_promotion_receipt_absent_or_structural",
            not parser_promotion_exists
            or parser_promotion.get("artifact_kind") == "pooleos.pooleglyph_parser_kernel_promotion_receipt",
            "not provided"
            if not parser_promotion_exists
            else f"artifact_kind={parser_promotion.get('artifact_kind', '')}",
        ),
        _check(
            "handoff_does_not_preclaim_kernel_or_pgvm2",
            not kernel_boot_handoff_path.exists()
            or (
                handoff.get("kernel_boundary_claimed") is False
                and handoff.get("pgvm2_execution_claimed") is False
            ),
            f"kernel={handoff.get('kernel_boundary_claimed', '')}; pgvm2={handoff.get('pgvm2_execution_claimed', '')}",
        ),
        _check(
            "kernel_loader_output_absent_or_booted_kernel_source",
            not loader_output_exists or loader_output.get("booted_kernel_path") is True or not claimed_enforcement,
            "pending booted kernel output"
            if not loader_output_exists
            else f"booted_kernel_path={loader_output.get('booted_kernel_path', '')}; claimed={claimed_enforcement}",
        ),
        _check(
            "kernel_loader_output_absent_or_handoff_hash_matches",
            not loader_output_exists or handoff_hash_matches,
            "pending booted kernel output"
            if not loader_output_exists
            else f"output={output_handoff_hash}; expected={source_handoff_sha256}",
        ),
        _check(
            "kernel_loader_output_absent_or_pooleglyph_source_anchor_hash_matches",
            not loader_output_exists or source_anchor_hash_matches,
            "pending booted kernel output"
            if not loader_output_exists
            else f"output={output_source_anchor_hash}; expected={source_anchor_sha256}",
        ),
        _check(
            "kernel_loader_output_absent_or_parser_promotion_receipt_hash_matches",
            not loader_output_exists or parser_promotion_hash_matches,
            "pending booted kernel output"
            if not loader_output_exists
            else f"output={output_parser_promotion_hash}; expected={parser_promotion_sha256}",
        ),
        _check(
            "no_enforcement_claim_without_valid_output",
            not claimed_enforcement or loader_output_valid,
            f"claimed={claimed_enforcement}; output_valid={loader_output_valid}",
        ),
        _check(
            "no_enforcement_claim_without_parser_promotion_ready",
            not claimed_enforcement or parser_promotion_ready,
            f"claimed={claimed_enforcement}; promotion_status={parser_promotion_status}; promotion_ready={parser_promotion_ready}",
        ),
    ]
    structural_failed = [check for check in checks if not check["ok"]]

    requirements = [
        _requirement(
            "kernel_boot_handoff_present",
            kernel_boot_handoff_path.exists(),
            str(kernel_boot_handoff_path),
        ),
        _requirement(
            "kernel_boot_handoff_ready",
            handoff_ready,
            f"status={handoff.get('status', '')}; allowed={handoff.get('kernel_handoff_allowed', False)}; unmet={handoff_summary.get('unmet_requirement_count', '')}",
        ),
        _requirement(
            "booted_kernel_loader_output_present",
            loader_output_exists,
            str(kernel_loader_output_path),
        ),
        _requirement(
            "booted_kernel_loader_output_valid",
            loader_output_valid,
            "pending booted kernel output"
            if not loader_output_exists
            else f"status={loader_output.get('status', '')}; booted={loader_output.get('booted_kernel_path', False)}; failed={loader_summary.get('failed_check_count', '')}",
        ),
        _requirement(
            "pooleglyph_source_anchor_present",
            source_anchor_exists,
            str(pooleglyph_source_anchor_path or ""),
        ),
        _requirement(
            "pooleglyph_source_anchor_bound",
            source_anchor_bound,
            f"status={source_anchor.get('status', '')}; failed={source_anchor_summary.get('failed_check_count', '')}",
        ),
        _requirement(
            "pooleglyph_parser_promotion_receipt_present",
            parser_promotion_exists,
            str(parser_kernel_promotion_receipt_path or ""),
        ),
        _requirement(
            "pooleglyph_parser_promotion_receipt_bound",
            parser_promotion_bound,
            f"status={parser_promotion_status}; failed={parser_promotion_summary.get('failed_check_count', '')}",
        ),
        _requirement(
            "pooleglyph_parser_promotion_ready_for_enforcement",
            parser_promotion_ready,
            f"status={parser_promotion_status}; phase66={parser_promotion_summary.get('phase66_audit_present', False)}; promotion={parser_promotion_summary.get('parser_to_kernel_promotion_allowed', False)}; handoff={parser_promotion_summary.get('kernel_handoff_allowed', False)}",
        ),
        _requirement(
            "handoff_hash_bound",
            handoff_hash_matches,
            "pending booted kernel output"
            if not loader_output_exists
            else f"output={output_handoff_hash}; expected={source_handoff_sha256}",
        ),
        _requirement(
            "pooleglyph_source_anchor_hash_bound",
            source_anchor_hash_matches,
            "pending booted kernel output"
            if not loader_output_exists
            else f"output={output_source_anchor_hash}; expected={source_anchor_sha256}",
        ),
        _requirement(
            "pooleglyph_parser_promotion_receipt_hash_bound",
            parser_promotion_hash_matches,
            "pending booted kernel output"
            if not loader_output_exists
            else f"output={output_parser_promotion_hash}; expected={parser_promotion_sha256}",
        ),
        _requirement(
            "all_planned_kernel_checks_satisfied",
            all_kernel_checks_satisfied,
            f"satisfied={sum(1 for check in planned_checks if check['satisfied'])}/{len(planned_checks)}",
        ),
        _requirement(
            "kernel_enforcement_claim_guard",
            not claimed_enforcement or loader_output_valid,
            f"claimed={claimed_enforcement}; output_valid={loader_output_valid}",
        ),
    ]
    unmet = [requirement for requirement in requirements if not requirement["met"]]

    if structural_failed:
        status = "invalid"
    elif loader_output_valid and handoff_ready and source_anchor_bound and parser_promotion_ready:
        status = "kernel_enforced"
    elif handoff_ready and source_anchor_bound and parser_promotion_bound:
        status = "ready_for_kernel_loader"
    else:
        status = "blocked"

    kernel_enforcement_claimed = status == "kernel_enforced"
    kernel_loader_ready = status in {"ready_for_kernel_loader", "kernel_enforced"}
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "status": status,
        "kernel_loader_ready": kernel_loader_ready,
        "kernel_enforcement_claimed": kernel_enforcement_claimed,
        "pgvm2_execution_claimed": kernel_enforcement_claimed,
        "booted_kernel_path_claimed": kernel_enforcement_claimed,
        "sources": {
            "kernel_boot_handoff": _source(kernel_boot_handoff_path, handoff),
            "kernel_loader_output": _source(kernel_loader_output_path, loader_output),
            "pooleglyph_source_anchor": _source(pooleglyph_source_anchor_path or Path(""), source_anchor),
            "pooleglyph_parser_kernel_promotion_receipt": _source(
                parser_kernel_promotion_receipt_path or Path(""),
                parser_promotion,
            ),
        },
        "source_handoff_sha256": source_handoff_sha256,
        "pooleglyph_source_anchor_sha256": source_anchor_sha256,
        "pooleglyph_parser_kernel_promotion_receipt_sha256": parser_promotion_sha256,
        "handoff_summary": {
            "status": str(handoff.get("status", "")),
            "kernel_handoff_allowed": handoff.get("kernel_handoff_allowed") is True,
            "failed_check_count": _int(handoff_summary.get("failed_check_count")),
            "unmet_requirement_count": _int(handoff_summary.get("unmet_requirement_count")),
            "expected_executed_instruction_count": expected_count,
        },
        "pooleglyph_source_summary": {
            "status": str(source_anchor.get("status", "")),
            "anchor_bound": source_anchor_bound,
            "dirty_file_count": _int(source_anchor_summary.get("dirty_file_count")),
            "failed_check_count": _int(source_anchor_summary.get("failed_check_count")),
            "source_anchor_digest_matches_loader_output": source_anchor_hash_matches,
        },
        "parser_promotion_summary": {
            "status": parser_promotion_status,
            "receipt_bound": parser_promotion_bound,
            "phase66_audit_present": parser_promotion_summary.get("phase66_audit_present") is True,
            "parser_to_kernel_promotion_allowed": parser_promotion_summary.get("parser_to_kernel_promotion_allowed") is True,
            "kernel_handoff_allowed": parser_promotion_summary.get("kernel_handoff_allowed") is True,
            "parser_promotion_ready_for_enforcement": parser_promotion_ready,
        },
        "planned_kernel_checks": planned_checks,
        "enforcement_requirements": requirements,
        "checks": checks,
        "summary": {
            "failed_check_count": len(structural_failed),
            "unmet_requirement_count": len(unmet),
            "planned_kernel_check_count": len(planned_checks),
            "satisfied_kernel_check_count": sum(1 for check in planned_checks if check["satisfied"]),
            "kernel_boot_handoff_status": str(handoff.get("status", "")),
            "kernel_handoff_allowed": handoff.get("kernel_handoff_allowed") is True,
            "kernel_loader_output_exists": loader_output_exists,
            "kernel_loader_output_status": str(loader_output.get("status", "")),
            "pooleglyph_source_anchor_bound": source_anchor_bound,
            "pooleglyph_source_anchor_digest_matches": source_anchor_hash_matches,
            "parser_promotion_receipt_bound": parser_promotion_bound,
            "parser_promotion_receipt_status": parser_promotion_status,
            "parser_promotion_ready_for_enforcement": parser_promotion_ready,
            "parser_promotion_receipt_digest_matches": parser_promotion_hash_matches,
            "output_handoff_hash_matches": handoff_hash_matches,
            "all_kernel_checks_satisfied": all_kernel_checks_satisfied,
            "expected_executed_instruction_count": expected_count,
            "actual_executed_instruction_count": actual_count,
            "kernel_loader_ready": kernel_loader_ready,
            "kernel_enforcement_claimed": kernel_enforcement_claimed,
            "pgvm2_execution_claimed": kernel_enforcement_claimed,
            "booted_kernel_path_claimed": kernel_enforcement_claimed,
        },
        "limitations": [
            "This artifact defines the kernel PGVM2 loader evidence contract; it does not execute a kernel loader.",
            "kernel_enforcement_claimed remains false until a booted kernel output satisfies every planned kernel check.",
            "Parser-backed PGVM2 enforcement remains impossible until the PooleGlyph parser-to-kernel promotion receipt is parser_to_kernel_ready.",
            "A ready_for_kernel_loader status is only a work queue signal, not production security proof.",
        ],
        "next_steps": [
            "Implement the booted kernel PGVM2 loader output producer with the kernel_checks fields listed here.",
            "Bind the PooleGlyph parser-to-kernel promotion receipt to the booted kernel loader transcript before allowing parser-backed PGVM2 enforcement.",
            "Bind the loader output to source_handoff_sha256 before allowing any enforcement claim.",
            "Promote to kernel_enforced only after the booted kernel output passes every planned check.",
        ],
    }


def write_evidence(evidence: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
