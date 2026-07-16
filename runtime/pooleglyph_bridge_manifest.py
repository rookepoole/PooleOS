"""PooleGlyph-to-PooleOS bridge manifest generation."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "0.1"
ARTIFACT_KIND = "pooleos.pooleglyph_bridge_manifest"

PARSER_PACKAGE = "pooleglyph_v0_5_parser_ast_scaffold_package"

BRIDGE_MAP_DEFINITIONS: dict[str, dict[str, Any]] = {
    "abi_and_package": {
        "declarations": ["version", "requires", "package", "package surface export/import", "entrypoint"],
        "pooleos_targets": [
            "PGB2 bundle ABI/version section",
            "PooleOS package surface manifest",
            "entrypoint import/export gate",
        ],
        "next_artifact": "pooleos.pgb2_abi_package_surface",
    },
    "capability_security": {
        "declarations": ["capability", "permission", "policy", "contract"],
        "pooleos_targets": [
            "capability trap proof policy input",
            "permission/resource matrix",
            "signed capability manifest",
        ],
        "next_artifact": "pooleos.permission_capability_matrix",
    },
    "boot_graph": {
        "declarations": ["profile", "environment", "target", "deployment", "entrypoint", "service", "lifecycle", "schedule"],
        "pooleos_targets": [
            "lab image target profile",
            "boot graph manifest",
            "service startup order",
        ],
        "next_artifact": "pooleos.boot_graph_manifest",
    },
    "service_graph": {
        "declarations": [
            "config",
            "resource",
            "service",
            "interface",
            "adapter",
            "binding",
            "route",
            "channel",
            "endpoint",
            "port",
            "gateway",
        ],
        "pooleos_targets": [
            "resource inventory",
            "IPC/channel route map",
            "service graph evidence",
        ],
        "next_artifact": "pooleos.service_graph_manifest",
    },
    "topology": {
        "declarations": [
            "node",
            "cluster",
            "mesh",
            "fabric",
            "domain",
            "realm",
            "space",
            "universe",
            "multiverse",
            "omniverse",
            "cosmos",
            "macrocosm",
            "metacosm",
            "hypercosm",
        ],
        "pooleos_targets": [
            "node/cluster topology descriptors",
            "deployment domain labels",
            "public-safe mesh/fabric metadata",
        ],
        "next_artifact": "pooleos.topology_manifest",
    },
    "diagnostics": {
        "declarations": [],
        "pooleos_targets": [
            "PGB2 source-map diagnostic evidence",
            "trap-report source positions",
            "release-gate diagnostic coverage ledger",
        ],
        "next_artifact": "pooleos.diagnostic_evidence_manifest",
    },
}


def _check(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig") if path.exists() else ""


def _phase_number(text: str) -> int:
    match = re.search(r"Phase\s+(\d+)", text)
    return int(match.group(1)) if match else 0


def _required_inputs(*, source_anchor_path: Path, pooleglyph_path: Path) -> dict[str, Path]:
    package_root = pooleglyph_path / PARSER_PACKAGE
    return {
        "source_anchor": source_anchor_path,
        "language_surface_inventory": package_root / "tests" / "language_surface_inventory.json",
        "diagnostic_hardening_manifest": package_root / "tests" / "diagnostic_hardening_manifest.json",
        "v0_5_language_spec": package_root / "docs" / "POOLEGLYPH_V0_5_DEV_LANGUAGE_SPEC.md",
        "spec_sync_matrix": package_root / "docs" / "POOLEGLYPH_V0_5_SPEC_SYNC_MATRIX.md",
        "pooleos_reoriented_plan": package_root / "docs" / "POOLEGLYPH_POOLEOS_REORIENTED_PLAN.md",
    }


def _input_record(name: str, path: Path, role: str) -> dict[str, Any]:
    return {"name": name, "path": str(path), "exists": path.exists(), "role": role}


def _coverage(required: list[str], stack: set[str]) -> tuple[str, list[str]]:
    if not required:
        return "covered", []
    missing = [declaration for declaration in required if declaration not in stack]
    if not missing:
        return "covered", []
    if len(missing) == len(required):
        return "missing", missing
    return "partial", missing


def _make_bridge_maps(stack: list[str]) -> dict[str, dict[str, Any]]:
    stack_set = set(stack)
    bridge_maps: dict[str, dict[str, Any]] = {}
    for name, definition in BRIDGE_MAP_DEFINITIONS.items():
        required = list(definition["declarations"] or stack)
        coverage, missing = _coverage(required, stack_set)
        bridge_maps[name] = {
            "pooleglyph_declarations": required,
            "missing_declarations": missing,
            "pooleos_targets": list(definition["pooleos_targets"]),
            "coverage": coverage,
            "boundary": "metadata-only bridge input; no runtime enforcement or performance claim",
            "next_artifact": str(definition["next_artifact"]),
        }
    return bridge_maps


def _core_ir_boundary(*, latest_phase: int) -> dict[str, Any]:
    phase66_audit_present = latest_phase >= 66
    return {
        "status": "phase66_audit_present" if phase66_audit_present else "phase66_pending",
        "receipt_artifact_kind": "pooleos.pooleglyph_core_ir_boundary_receipt",
        "phase66_audit_present": phase66_audit_present,
        "parser_to_kernel_promotion_allowed": False,
        "boundary_rule": (
            "PooleGlyph metadata declarations remain metadata-only PooleOS bridge inputs until a "
            "Core IR boundary receipt proves which outputs are executable Core IR and which are "
            "metadata-only zero-program outputs."
        ),
        "current_scope": [
            "bridge manifest declaration coverage",
            "public Core IR structural validation",
            "metadata-only versus executable-candidate distinction",
        ],
        "blocked_claims": [
            "parser-to-kernel readiness",
            "kernel PGVM2 execution",
            "frozen PooleOS ABI",
        ],
    }


def make_bridge_manifest(*, source_anchor_path: Path, pooleglyph_path: Path | None = None) -> dict[str, Any]:
    source_anchor = _read_json(source_anchor_path) if source_anchor_path.exists() else {}
    resolved_pooleglyph = Path(pooleglyph_path or source_anchor.get("pooleglyph_path", ""))
    inputs = _required_inputs(source_anchor_path=source_anchor_path, pooleglyph_path=resolved_pooleglyph)
    input_records = [
        _input_record("source_anchor", inputs["source_anchor"], "PooleOS source/checkpoint anchor"),
        _input_record("language_surface_inventory", inputs["language_surface_inventory"], "verified v0.5-dev declaration stack"),
        _input_record("diagnostic_hardening_manifest", inputs["diagnostic_hardening_manifest"], "diagnostic case/code coverage ledger"),
        _input_record("v0_5_language_spec", inputs["v0_5_language_spec"], "public language contract"),
        _input_record("spec_sync_matrix", inputs["spec_sync_matrix"], "metadata-only declaration sync proof"),
        _input_record("pooleos_reoriented_plan", inputs["pooleos_reoriented_plan"], "PooleOS bridge roadmap boundary"),
    ]

    inventory = _read_json(inputs["language_surface_inventory"]) if inputs["language_surface_inventory"].exists() else {}
    diagnostics = _read_json(inputs["diagnostic_hardening_manifest"]) if inputs["diagnostic_hardening_manifest"].exists() else {}
    spec_sync_text = _read_text(inputs["spec_sync_matrix"])
    plan_text = _read_text(inputs["pooleos_reoriented_plan"])

    latest_checkpoint = source_anchor.get("latest_checkpoint", {}) if isinstance(source_anchor, dict) else {}
    latest_checkpoint_name = str(latest_checkpoint.get("checkpoint", ""))
    latest_phase = _phase_number(latest_checkpoint_name)
    anchor_summary = source_anchor.get("summary", {}) if isinstance(source_anchor, dict) else {}
    dirty_file_count = int(anchor_summary.get("dirty_file_count", 0) or 0)
    failed_anchor_checks = int(anchor_summary.get("failed_check_count", 0) or 0)

    stack = [str(item) for item in inventory.get("language_stack_through_phase_60", [])]
    source_map_node_kinds = [str(item) for item in inventory.get("required_source_map_node_kinds", [])]
    semantic_root_fields = [str(item) for item in inventory.get("semantic_root_fields_to_audit", [])]
    stack_case_map = diagnostics.get("stack_to_case_file", {})
    missing_stack_case_files = [
        declaration
        for declaration in stack
        if declaration not in stack_case_map
    ]
    bridge_maps = _make_bridge_maps(stack)

    checks = [
        _check("source_anchor_present", source_anchor_path.exists(), str(source_anchor_path)),
        _check(
            "source_anchor_status_usable",
            source_anchor.get("status") in {"pass", "warn"},
            f"status={source_anchor.get('status', 'missing')}",
        ),
        _check(
            "source_anchor_has_no_failed_checks",
            failed_anchor_checks == 0,
            f"failed_check_count={failed_anchor_checks}",
        ),
        _check(
            "latest_checkpoint_phase65_or_later",
            latest_phase >= 65,
            latest_checkpoint_name or "missing",
        ),
        _check(
            "all_required_inputs_present",
            all(record["exists"] for record in input_records),
            f"missing={[record['name'] for record in input_records if not record['exists']]}",
        ),
        _check(
            "language_stack_present",
            len(stack) >= 48,
            f"stack_count={len(stack)}",
        ),
        _check(
            "source_map_nodes_present",
            bool(source_map_node_kinds),
            f"source_map_node_kind_count={len(source_map_node_kinds)}",
        ),
        _check(
            "semantic_root_fields_present",
            bool(semantic_root_fields),
            f"semantic_root_field_count={len(semantic_root_fields)}",
        ),
        _check(
            "diagnostic_manifest_phase65_or_later",
            int(diagnostics.get("phase", 0) or 0) >= 65,
            f"phase={diagnostics.get('phase', 'missing')}",
        ),
        _check(
            "diagnostic_cases_present",
            int(diagnostics.get("diagnostic_case_count", 0) or 0) > 0,
            f"diagnostic_case_count={diagnostics.get('diagnostic_case_count', 0)}",
        ),
        _check(
            "diagnostic_stack_case_files_cover_language_stack",
            not missing_stack_case_files,
            f"missing={missing_stack_case_files}",
        ),
        _check(
            "bridge_maps_fully_covered",
            all(record["coverage"] == "covered" for record in bridge_maps.values()),
            "; ".join(f"{name}={record['coverage']}" for name, record in bridge_maps.items()),
        ),
        _check(
            "metadata_only_boundary_documented",
            "Metadata-only boundary" in spec_sync_text and "metadata-only" in plan_text.lower(),
            "spec sync and reoriented plan document public-safe metadata boundary",
        ),
    ]
    failed = [check for check in checks if not check["ok"]]
    warnings = []
    if source_anchor.get("status") == "warn":
        warnings.append("source anchor is warn, usually from a dirty live PooleGlyph worktree")
    if dirty_file_count:
        warnings.append(f"live PooleGlyph dirty_file_count={dirty_file_count}")

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "status": "fail" if failed else "warn" if warnings else "pass",
        "source_anchor": {
            "artifact_path": str(source_anchor_path),
            "status": str(source_anchor.get("status", "")),
            "pooleglyph_path": str(resolved_pooleglyph),
            "commit": str(source_anchor.get("git", {}).get("commit", "")),
            "dirty_file_count": dirty_file_count,
            "latest_checkpoint": latest_checkpoint_name,
            "latest_phase": latest_phase,
            "failed_check_count": failed_anchor_checks,
        },
        "required_inputs": input_records,
        "language_surface": {
            "phase": int(inventory.get("phase", 0) or 0),
            "phase_name": str(inventory.get("phase_name", "")),
            "stack_count": len(stack),
            "stack": stack,
            "source_map_node_kind_count": len(source_map_node_kinds),
            "source_map_node_kinds": source_map_node_kinds,
            "semantic_root_field_count": len(semantic_root_fields),
            "semantic_root_fields": semantic_root_fields,
        },
        "core_ir_boundary": _core_ir_boundary(latest_phase=latest_phase),
        "bridge_maps": bridge_maps,
        "diagnostic_summary": {
            "phase": int(diagnostics.get("phase", 0) or 0),
            "phase_name": str(diagnostics.get("phase_name", "")),
            "diagnostic_case_count": int(diagnostics.get("diagnostic_case_count", 0) or 0),
            "case_file_count": int(diagnostics.get("case_file_count", 0) or 0),
            "parse_diagnostic_code_count": int(diagnostics.get("parse_diagnostic_code_count", 0) or 0),
            "semantic_diagnostic_code_count": int(diagnostics.get("semantic_diagnostic_code_count", 0) or 0),
            "lexer_diagnostic_code_count": int(diagnostics.get("lexer_diagnostic_code_count", 0) or 0),
            "stack_case_coverage_count": len(stack_case_map) if isinstance(stack_case_map, dict) else 0,
            "missing_stack_case_files": missing_stack_case_files,
            "next_recommended_phase": str(diagnostics.get("next_recommended_phase", "")),
        },
        "checks": checks,
        "summary": {
            "bridge_map_count": len(bridge_maps),
            "fully_covered_bridge_map_count": sum(1 for record in bridge_maps.values() if record["coverage"] == "covered"),
            "language_stack_count": len(stack),
            "diagnostic_case_count": int(diagnostics.get("diagnostic_case_count", 0) or 0),
            "failed_check_count": len(failed),
            "warning_count": len(warnings),
        },
        "limitations": [
            "PooleGlyph v0.5-dev bridge inputs are metadata-only and do not prove PooleOS runtime behavior.",
            "This manifest maps declarations to PooleOS artifact lanes; it is not a frozen ABI, boot graph, permission matrix, or kernel enforcement result.",
            "Public Core IR validation does not become parser-to-kernel readiness until a Core IR boundary receipt permits that promotion.",
            "A warn status is acceptable release-gate evidence only when failed_check_count is zero and the warning is limited to live-worktree dirtiness.",
        ],
        "next_steps": [
            "Emit a PooleGlyph Core IR boundary receipt before promoting bridge metadata toward parser-to-kernel readiness.",
            "Emit a PooleOS permission/capability/resource matrix from capability, permission, policy, contract, and resource declarations.",
            "Emit a boot graph artifact from target, deployment, entrypoint, service, lifecycle, and schedule declarations.",
            "After PooleGlyph Phase 66 lands, regenerate the Core IR boundary receipt before claiming parser-to-kernel readiness.",
        ],
    }


def write_bridge_manifest(manifest: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
