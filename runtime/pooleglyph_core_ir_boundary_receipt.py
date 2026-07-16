"""Core IR boundary receipt for PooleGlyph-to-PooleOS bridge inputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "0.1"
ARTIFACT_KIND = "pooleos.pooleglyph_core_ir_boundary_receipt"
BRIDGE_ARTIFACT_KIND = "pooleos.pooleglyph_bridge_manifest"
PARSER_PACKAGE = "pooleglyph_v0_5_parser_ast_scaffold_package"
EXPECTED_NEGATIVE_CODES = {"PGCORE100", "PGCORE110", "PGCORE900"}
EXPECTED_NEGATIVE_NAMES = {
    "invalid_k_high.validate.json",
    "missing_halt.validate.json",
    "unknown_instruction.validate.json",
}


def _check(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def _gate(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def _read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _validation_paths(package_root: Path) -> list[Path]:
    if not package_root.exists():
        return []
    paths = []
    for path in package_root.rglob("*.validate.json"):
        text = str(path).lower()
        if "coreir" in text or ".coreir." in path.name.lower():
            paths.append(path)
    return sorted(paths, key=lambda item: str(item).lower())


def _is_expected_negative(path: Path, package_root: Path, diagnostic_codes: set[str]) -> bool:
    relative = _relative(path, package_root).replace("/", "\\").lower()
    if not relative.startswith("outputs_coreir\\"):
        return False
    if path.name.lower() not in EXPECTED_NEGATIVE_NAMES:
        return False
    return bool(diagnostic_codes) and diagnostic_codes.issubset(EXPECTED_NEGATIVE_CODES)


def _public_safe_notes_present(validation: dict[str, Any]) -> bool:
    notes = [str(note) for note in validation.get("notes", []) if isinstance(note, str)]
    return any("Public-safe Core IR structural validator" in note for note in notes) and any(
        "No private PooleMath" in note for note in notes
    )


def _validation_record(path: Path, package_root: Path) -> dict[str, Any]:
    try:
        validation = _read_json(path)
    except Exception as exc:  # pragma: no cover - corrupt external evidence path
        return {
            "path": _relative(path, package_root),
            "exists": True,
            "sha256": _sha256(path),
            "parse_error": str(exc),
            "ok": False,
            "classification": "unexpected_invalid",
            "validator_version": "",
            "module": "",
            "program_count": 0,
            "instruction_count": 0,
            "diagnostic_codes": [],
            "public_safe_notes_present": False,
        }

    diagnostics = validation.get("diagnostics", [])
    diagnostic_codes = {
        str(item.get("code", ""))
        for item in diagnostics
        if isinstance(item, dict) and item.get("code")
    }
    ok = validation.get("ok") is True
    program_count = _int(validation.get("program_count"))
    instruction_count = _int(validation.get("instruction_count"))
    public_safe = _public_safe_notes_present(validation)
    if ok and program_count > 0 and instruction_count > 0:
        classification = "validated_executable_candidate"
    elif ok and program_count == 0:
        classification = "validated_metadata_zero_program"
    elif ok:
        classification = "validated_structural_anomaly"
    elif _is_expected_negative(path, package_root, diagnostic_codes):
        classification = "expected_negative_fixture"
    else:
        classification = "unexpected_invalid"

    return {
        "path": _relative(path, package_root),
        "exists": True,
        "sha256": _sha256(path),
        "ok": ok,
        "classification": classification,
        "validator_version": str(validation.get("version", "")),
        "module": str(validation.get("module", "")),
        "program_count": program_count,
        "instruction_count": instruction_count,
        "diagnostic_codes": sorted(diagnostic_codes),
        "public_safe_notes_present": public_safe,
    }


def make_pooleglyph_core_ir_boundary_receipt(
    *,
    bridge_manifest_path: Path,
    pooleglyph_path: Path | None = None,
) -> dict[str, Any]:
    bridge_manifest = _read_json(bridge_manifest_path)
    source_anchor = bridge_manifest.get("source_anchor", {}) if isinstance(bridge_manifest, dict) else {}
    summary = bridge_manifest.get("summary", {}) if isinstance(bridge_manifest, dict) else {}
    core_boundary = bridge_manifest.get("core_ir_boundary", {}) if isinstance(bridge_manifest, dict) else {}
    language_surface = bridge_manifest.get("language_surface", {}) if isinstance(bridge_manifest, dict) else {}

    resolved_pooleglyph = Path(pooleglyph_path or source_anchor.get("pooleglyph_path", ""))
    package_root = resolved_pooleglyph / PARSER_PACKAGE
    validator_path = package_root / "src" / "pooleglyph_parser" / "core_ir_validator.py"
    verifier_script_path = package_root / "tools" / "verify_coreir_validator.py"
    validation_records = [_validation_record(path, package_root) for path in _validation_paths(package_root)]

    valid_records = [record for record in validation_records if record["ok"] is True]
    expected_negative_records = [
        record for record in validation_records if record["classification"] == "expected_negative_fixture"
    ]
    unexpected_invalid_records = [
        record for record in validation_records if record["classification"] == "unexpected_invalid"
    ]
    executable_records = [
        record for record in validation_records if record["classification"] == "validated_executable_candidate"
    ]
    metadata_zero_records = [
        record for record in validation_records if record["classification"] == "validated_metadata_zero_program"
    ]
    structural_anomaly_records = [
        record for record in validation_records if record["classification"] == "validated_structural_anomaly"
    ]
    validator_versions = sorted(
        {str(record.get("validator_version", "")) for record in validation_records if record.get("validator_version")}
    )
    public_safe_note_count = sum(1 for record in validation_records if record.get("public_safe_notes_present"))
    latest_phase = _int(source_anchor.get("latest_phase"))
    phase66_audit_present = bool(core_boundary.get("phase66_audit_present")) and latest_phase >= 66
    bridge_kind_ok = (not bridge_manifest_path.exists()) or bridge_manifest.get("artifact_kind") == BRIDGE_ARTIFACT_KIND
    bridge_failed_checks = _int(summary.get("failed_check_count"))
    bridge_declarations = [str(item) for item in language_surface.get("stack", [])]

    checks = [
        _check("bridge_manifest_present", bridge_manifest_path.exists(), str(bridge_manifest_path)),
        _check("bridge_manifest_kind_valid", bridge_kind_ok, str(bridge_manifest.get("artifact_kind", ""))),
        _check(
            "bridge_manifest_status_usable",
            bridge_manifest.get("status") in {"pass", "warn"} and bridge_failed_checks == 0,
            f"status={bridge_manifest.get('status', 'missing')}; failed_check_count={bridge_failed_checks}",
        ),
        _check(
            "bridge_core_ir_boundary_present",
            isinstance(core_boundary, dict) and bool(core_boundary.get("receipt_artifact_kind")),
            str(core_boundary.get("receipt_artifact_kind", "")),
        ),
        _check("pooleglyph_package_present", package_root.exists(), str(package_root)),
        _check("core_ir_validator_present", validator_path.exists(), str(validator_path)),
        _check("core_ir_verifier_script_present", verifier_script_path.exists(), str(verifier_script_path)),
        _check(
            "core_ir_validation_outputs_present",
            bool(validation_records),
            f"validation_file_count={len(validation_records)}",
        ),
        _check(
            "core_ir_validator_version_present",
            bool(validator_versions),
            f"versions={validator_versions}",
        ),
        _check(
            "no_unexpected_invalid_core_ir_outputs",
            not unexpected_invalid_records,
            f"unexpected_invalid_count={len(unexpected_invalid_records)}",
        ),
        _check(
            "no_structural_anomaly_core_ir_outputs",
            not structural_anomaly_records,
            f"structural_anomaly_count={len(structural_anomaly_records)}",
        ),
        _check(
            "metadata_boundary_not_kernel_claim",
            core_boundary.get("parser_to_kernel_promotion_allowed") is False,
            f"bridge_parser_to_kernel_promotion_allowed={core_boundary.get('parser_to_kernel_promotion_allowed')}",
        ),
    ]
    failed = [check for check in checks if not check["ok"]]

    promotion_gates = [
        _gate("phase66_audit_present", phase66_audit_present, f"latest_phase={latest_phase}"),
        _gate(
            "validated_executable_candidates_present",
            bool(executable_records),
            f"count={len(executable_records)}",
        ),
        _gate(
            "validated_metadata_zero_program_outputs_present",
            bool(metadata_zero_records),
            f"count={len(metadata_zero_records)}",
        ),
        _gate(
            "expected_negative_core_ir_diagnostics_present",
            len(expected_negative_records) >= 3,
            f"count={len(expected_negative_records)}",
        ),
        _gate(
            "all_validation_reports_public_safe",
            public_safe_note_count == len(validation_records) and bool(validation_records),
            f"public_safe_note_count={public_safe_note_count}; validation_file_count={len(validation_records)}",
        ),
    ]
    failed_promotion_gates = [gate for gate in promotion_gates if not gate["ok"]]
    parser_to_kernel_promotion_allowed = not failed and not failed_promotion_gates and phase66_audit_present

    if failed:
        status = "fail"
    elif parser_to_kernel_promotion_allowed:
        status = "parser_to_kernel_ready"
    elif phase66_audit_present:
        status = "validated_non_promoting"
    else:
        status = "phase66_pending"

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "status": status,
        "bridge_manifest": {
            "artifact_path": str(bridge_manifest_path),
            "exists": bridge_manifest_path.exists(),
            "artifact_kind": str(bridge_manifest.get("artifact_kind", "")),
            "status": str(bridge_manifest.get("status", "")),
            "latest_phase": latest_phase,
            "failed_check_count": bridge_failed_checks,
            "core_ir_boundary_status": str(core_boundary.get("status", "")),
            "phase66_audit_present": phase66_audit_present,
        },
        "pooleglyph": {
            "pooleglyph_path": str(resolved_pooleglyph),
            "package_root": str(package_root),
            "validator_path": str(validator_path),
            "verifier_script_path": str(verifier_script_path),
        },
        "declaration_boundary": {
            "bridge_declaration_count": len(bridge_declarations),
            "bridge_map_count": _int(summary.get("bridge_map_count")),
            "metadata_only_until_phase66": not phase66_audit_present,
            "boundary_rule": str(core_boundary.get("boundary_rule", "")),
        },
        "core_ir_validation_summary": {
            "validation_file_count": len(validation_records),
            "valid_file_count": len(valid_records),
            "validated_executable_candidate_count": len(executable_records),
            "validated_metadata_zero_program_count": len(metadata_zero_records),
            "expected_negative_fixture_count": len(expected_negative_records),
            "unexpected_invalid_count": len(unexpected_invalid_records),
            "structural_anomaly_count": len(structural_anomaly_records),
            "validator_versions": validator_versions,
            "total_program_count": sum(_int(record.get("program_count")) for record in validation_records),
            "total_instruction_count": sum(_int(record.get("instruction_count")) for record in validation_records),
            "public_safe_note_count": public_safe_note_count,
        },
        "validation_records": validation_records,
        "promotion_gates": promotion_gates,
        "parser_to_kernel_promotion_allowed": parser_to_kernel_promotion_allowed,
        "kernel_enforcement_claimed": False,
        "checks": checks,
        "summary": {
            "failed_check_count": len(failed),
            "failed_promotion_gate_count": len(failed_promotion_gates),
            "phase66_audit_present": phase66_audit_present,
            "parser_to_kernel_promotion_allowed": parser_to_kernel_promotion_allowed,
            "kernel_enforcement_claimed": False,
            "validated_executable_candidate_count": len(executable_records),
            "validated_metadata_zero_program_count": len(metadata_zero_records),
            "unexpected_invalid_count": len(unexpected_invalid_records),
        },
        "limitations": [
            "This receipt validates public Core IR boundary evidence; it does not execute Core IR in a PooleOS kernel.",
            "validated_executable_candidate means public structural validation with nonzero programs and instructions, not kernel enforcement.",
            "validated_metadata_zero_program records metadata outputs whose Core IR validation produced no executable programs.",
            "phase66_pending is non-claiming evidence and keeps parser-to-kernel promotion blocked.",
        ],
        "next_steps": [
            "Run the PooleGlyph Phase 66 Core IR boundary audit when it lands in the checkpoint lineage.",
            "Regenerate the PooleGlyph bridge manifest and this receipt after Phase 66 is present.",
            "Only then allow parser-to-kernel readiness claims to depend on this receipt.",
        ],
    }


def write_receipt(receipt: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
