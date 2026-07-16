"""Permission/capability/resource matrix from public PooleGlyph metadata."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "0.1"
ARTIFACT_KIND = "pooleos.permission_capability_matrix"
PARSER_PACKAGE = "pooleglyph_v0_5_parser_ast_scaffold_package"

DEFAULT_SYMBOL_SOURCES = {
    "capabilities": Path("outputs_capabilities") / "capability_demo.symbols.json",
    "resources": Path("outputs_resources") / "resource_demo.symbols.json",
    "permissions": Path("outputs_permissions") / "permission_demo.symbols.json",
    "policies": Path("outputs_policies") / "policy_demo.symbols.json",
    "contracts": Path("outputs_contracts") / "contract_demo.symbols.json",
}


def _check(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sorted_unique(values: list[str]) -> list[str]:
    return sorted({value for value in values if value})


def _merge_named(target: dict[str, dict[str, Any]], name: str, module: str, path: Path) -> None:
    record = target.setdefault(name, {"name": name, "source_modules": [], "source_paths": []})
    record["source_modules"] = _sorted_unique([*record["source_modules"], module])
    record["source_paths"] = _sorted_unique([*record["source_paths"], str(path)])


def _access_hint(permission: str) -> str:
    for prefix in ("read", "write", "mutate", "append", "execute", "load"):
        if permission == prefix or permission.startswith(f"{prefix}_"):
            return prefix
    return "unspecified"


def _resource_kind_hint(permission: str) -> str:
    parts = permission.split("_", 1)
    return parts[1] if len(parts) == 2 and parts[1] else ""


def _fields(record: dict[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for field in record.get("fields", []):
        key = str(field.get("key", ""))
        if key:
            fields[key] = field.get("value")
    return fields


def _source_paths(pooleglyph_path: Path) -> dict[str, Path]:
    package_root = pooleglyph_path / PARSER_PACKAGE
    return {kind: package_root / relative for kind, relative in DEFAULT_SYMBOL_SOURCES.items()}


def _symbol_source_record(kind: str, path: Path) -> dict[str, Any]:
    module = ""
    if path.exists():
        try:
            module = str(_read_json(path).get("module", ""))
        except json.JSONDecodeError:
            module = ""
    return {"kind": kind, "path": str(path), "exists": path.exists(), "module": module}


def make_permission_capability_matrix(
    *,
    bridge_manifest_path: Path,
    core_ir_boundary_receipt_path: Path | None = None,
    core_ir_executable_audit_path: Path | None = None,
    parser_kernel_promotion_receipt_path: Path | None = None,
    pooleglyph_path: Path | None = None,
) -> dict[str, Any]:
    bridge_manifest = _read_json(bridge_manifest_path) if bridge_manifest_path.exists() else {}
    core_ir_receipt = (
        _read_json(core_ir_boundary_receipt_path)
        if core_ir_boundary_receipt_path is not None and core_ir_boundary_receipt_path.exists()
        else {}
    )
    core_ir_audit = (
        _read_json(core_ir_executable_audit_path)
        if core_ir_executable_audit_path is not None and core_ir_executable_audit_path.exists()
        else {}
    )
    promotion_receipt = (
        _read_json(parser_kernel_promotion_receipt_path)
        if parser_kernel_promotion_receipt_path is not None and parser_kernel_promotion_receipt_path.exists()
        else {}
    )
    bridge_source = bridge_manifest.get("source_anchor", {}) if isinstance(bridge_manifest, dict) else {}
    resolved_pooleglyph = Path(pooleglyph_path or bridge_source.get("pooleglyph_path", ""))
    symbol_paths = _source_paths(resolved_pooleglyph)
    symbol_sources = [_symbol_source_record(kind, path) for kind, path in symbol_paths.items()]
    core_summary = core_ir_receipt.get("summary", {}) if isinstance(core_ir_receipt.get("summary", {}), dict) else {}
    core_validation = (
        core_ir_receipt.get("core_ir_validation_summary", {})
        if isinstance(core_ir_receipt.get("core_ir_validation_summary", {}), dict)
        else {}
    )
    core_status = str(core_ir_receipt.get("status", ""))
    core_phase66 = core_summary.get("phase66_audit_present") is True
    core_promotion_allowed = core_summary.get("parser_to_kernel_promotion_allowed") is True
    core_kernel_claimed = core_ir_receipt.get("kernel_enforcement_claimed") is True
    core_failed_checks = int(core_summary.get("failed_check_count", 0) or 0)
    core_unexpected_invalid = int(core_summary.get("unexpected_invalid_count", 0) or 0)
    audit_summary = core_ir_audit.get("summary", {}) if isinstance(core_ir_audit.get("summary", {}), dict) else {}
    audit_source = (
        core_ir_audit.get("source_boundary_receipt", {})
        if isinstance(core_ir_audit.get("source_boundary_receipt", {}), dict)
        else {}
    )
    audit_status = str(core_ir_audit.get("status", ""))
    audit_bound = bool(core_ir_audit)
    audit_failed_checks = int(audit_summary.get("failed_check_count", 0) or 0)
    audit_kernel_handoff_allowed = audit_summary.get("kernel_handoff_allowed") is True
    audit_kernel_claimed = audit_summary.get("kernel_enforcement_claimed") is True
    audit_promotion_allowed = audit_summary.get("parser_to_kernel_promotion_allowed") is True
    audit_source_matches_receipt = (
        not audit_bound
        or not core_ir_boundary_receipt_path
        or Path(str(audit_source.get("artifact_path", ""))).name == core_ir_boundary_receipt_path.name
    )
    promotion_summary = (
        promotion_receipt.get("summary", {})
        if isinstance(promotion_receipt.get("summary", {}), dict)
        else {}
    )
    promotion_source = (
        promotion_receipt.get("source_executable_audit", {})
        if isinstance(promotion_receipt.get("source_executable_audit", {}), dict)
        else {}
    )
    promotion_status = str(promotion_receipt.get("status", ""))
    promotion_bound = bool(promotion_receipt)
    promotion_failed_checks = int(promotion_summary.get("failed_check_count", 0) or 0)
    promotion_allowed = promotion_summary.get("parser_to_kernel_promotion_allowed") is True
    promotion_kernel_handoff_allowed = promotion_summary.get("kernel_handoff_allowed") is True
    promotion_kernel_claimed = promotion_summary.get("kernel_enforcement_claimed") is True
    promotion_source_matches_audit = (
        not promotion_bound
        or not core_ir_executable_audit_path
        or Path(str(promotion_source.get("artifact_path", ""))).name == core_ir_executable_audit_path.name
    )
    promotion_phase66 = promotion_summary.get("phase66_audit_present") is True
    promotion_consistent_with_audit = (
        not promotion_bound
        or (
            promotion_phase66 == (audit_summary.get("phase66_audit_present") is True)
            and promotion_allowed == (
                audit_promotion_allowed and audit_status == "parser_to_kernel_ready"
            )
            and promotion_kernel_handoff_allowed == audit_kernel_handoff_allowed
            and not promotion_kernel_claimed
        )
    )
    combined_parser_to_kernel_promotion_allowed = (
        core_promotion_allowed
        and audit_promotion_allowed
        and promotion_allowed
        and promotion_kernel_handoff_allowed
    )
    combined_kernel_claimed = core_kernel_claimed or audit_kernel_claimed or promotion_kernel_claimed
    core_integration_mode = (
        "phase66_parser_to_kernel_promotable"
        if combined_parser_to_kernel_promotion_allowed
        else "metadata_only_non_promoting"
        if core_status in {"phase66_pending", "validated_non_promoting", "parser_to_kernel_ready"}
        else "unbound_or_invalid"
    )
    binding_source = (
        "PooleGlyph Core IR boundary receipt permits parser-to-kernel promotion; resource links remain release-gated"
        if combined_parser_to_kernel_promotion_allowed
        else "name-derived PooleGlyph metadata; Core IR boundary receipt is non-promoting"
    )

    capabilities_by_name: dict[str, dict[str, Any]] = {}
    resources_by_id: dict[str, dict[str, Any]] = {}
    permissions_by_name: dict[str, dict[str, Any]] = {}
    raw_policies: dict[str, dict[str, Any]] = {}
    raw_contracts: dict[str, dict[str, Any]] = {}

    for kind, path in symbol_paths.items():
        if not path.exists():
            continue
        data = _read_json(path)
        module = str(data.get("module", ""))
        for capability in data.get("capabilities", []):
            _merge_named(capabilities_by_name, str(capability.get("name", "")), module, path)
        for permission in data.get("permissions", []):
            name = str(permission.get("name", ""))
            if not name:
                continue
            _merge_named(permissions_by_name, name, module, path)
            permissions_by_name[name]["access_hint"] = _access_hint(name)
            permissions_by_name[name]["resource_kind_hint"] = _resource_kind_hint(name)
        for resource in data.get("resources", []):
            resource_kind = str(resource.get("kind", ""))
            name = str(resource.get("name", ""))
            if not resource_kind or not name:
                continue
            resource_id = f"{resource_kind}.{name}"
            record = resources_by_id.setdefault(
                resource_id,
                {
                    "id": resource_id,
                    "kind": resource_kind,
                    "name": name,
                    "fields": {},
                    "source_modules": [],
                    "source_paths": [],
                },
            )
            record["fields"].update(_fields(resource))
            record["source_modules"] = _sorted_unique([*record["source_modules"], module])
            record["source_paths"] = _sorted_unique([*record["source_paths"], str(path)])
        for policy in data.get("policies", []):
            name = str(policy.get("name", ""))
            if not name:
                continue
            record = raw_policies.setdefault(name, {"steps": [], "source_modules": [], "source_paths": []})
            record["steps"].extend(policy.get("steps", []))
            record["source_modules"] = _sorted_unique([*record["source_modules"], module])
            record["source_paths"] = _sorted_unique([*record["source_paths"], str(path)])
        for contract in data.get("contracts", []):
            name = str(contract.get("name", ""))
            if not name:
                continue
            record = raw_contracts.setdefault(name, {"steps": [], "source_modules": [], "source_paths": []})
            record["steps"].extend(contract.get("steps", []))
            record["source_modules"] = _sorted_unique([*record["source_modules"], module])
            record["source_paths"] = _sorted_unique([*record["source_paths"], str(path)])

    permission_names = set(permissions_by_name)
    policy_names = set(raw_policies)
    policies = []
    for name, raw in sorted(raw_policies.items()):
        allowed = _sorted_unique(
            [
                str(step.get("target", ""))
                for step in raw["steps"]
                if step.get("action") == "allow" and step.get("kind") == "permission"
            ]
        )
        missing = [permission for permission in allowed if permission not in permission_names]
        policies.append(
            {
                "name": name,
                "allowed_permissions": allowed,
                "missing_permissions": missing,
                "source_modules": raw["source_modules"],
                "source_paths": raw["source_paths"],
            }
        )

    contracts = []
    for name, raw in sorted(raw_contracts.items()):
        required = _sorted_unique(
            [
                str(step.get("target", ""))
                for step in raw["steps"]
                if step.get("action") == "require" and step.get("kind") == "policy"
            ]
        )
        missing = [policy for policy in required if policy not in policy_names]
        contracts.append(
            {
                "name": name,
                "required_policies": required,
                "missing_policies": missing,
                "source_modules": raw["source_modules"],
                "source_paths": raw["source_paths"],
            }
        )

    policy_by_permission: dict[str, list[str]] = {}
    for policy in policies:
        for permission in policy["allowed_permissions"]:
            policy_by_permission.setdefault(permission, []).append(policy["name"])
    contract_by_policy: dict[str, list[str]] = {}
    for contract in contracts:
        for policy in contract["required_policies"]:
            contract_by_policy.setdefault(policy, []).append(contract["name"])

    resource_permissions: list[dict[str, Any]] = []
    for permission in sorted(permissions_by_name.values(), key=lambda item: item["name"]):
        resource_kind_hint = permission.get("resource_kind_hint", "")
        candidate_resources = [
            resource
            for resource in resources_by_id.values()
            if resource_kind_hint and resource["kind"] == resource_kind_hint
        ]
        for resource in sorted(candidate_resources, key=lambda item: item["id"]):
            policy_names_for_permission = _sorted_unique(policy_by_permission.get(permission["name"], []))
            contract_names = _sorted_unique(
                [
                    contract
                    for policy_name in policy_names_for_permission
                    for contract in contract_by_policy.get(policy_name, [])
                ]
            )
            allowed = bool(policy_names_for_permission)
            resource_permissions.append(
                {
                    "resource_id": resource["id"],
                    "permission": permission["name"],
                    "access_hint": permission.get("access_hint", "unspecified"),
                    "binding_source": binding_source,
                    "binding_mode": core_integration_mode,
                    "core_ir_boundary_status": core_status,
                    "parser_to_kernel_promotion_allowed": combined_parser_to_kernel_promotion_allowed,
                    "policy_allowed": allowed,
                    "policy_names": policy_names_for_permission,
                    "contract_names": contract_names,
                    "expected_trap": not allowed,
                    "reason": (
                        f"{permission['name']} is allowed for {resource['id']} by policy metadata"
                        if allowed
                        else f"{permission['name']} has no allowing policy for {resource['id']}"
                    ),
                }
            )

    trap_operations = [
        {
            "opcode": "ASSERT_MATRIX_PERMISSION",
            "region": item["resource_id"],
            "source": "pgvm_guest",
            "target": "geometry_kernel",
            "capability": item["permission"],
            "matrix_allowed": item["policy_allowed"],
            "expected_trap": item["expected_trap"],
            "binding_mode": item["binding_mode"],
            "core_ir_boundary_status": item["core_ir_boundary_status"],
            "parser_to_kernel_promotion_allowed": item["parser_to_kernel_promotion_allowed"],
            "reason": item["reason"],
        }
        for item in resource_permissions
    ]

    source_anchor = bridge_manifest.get("source_anchor", {}) if isinstance(bridge_manifest, dict) else {}
    bridge_summary = bridge_manifest.get("summary", {}) if isinstance(bridge_manifest, dict) else {}
    bridge_maps = bridge_manifest.get("bridge_maps", {}) if isinstance(bridge_manifest, dict) else {}
    capability_security = bridge_maps.get("capability_security", {}) if isinstance(bridge_maps, dict) else {}
    service_graph = bridge_maps.get("service_graph", {}) if isinstance(bridge_maps, dict) else {}
    bridge_failed = int(bridge_summary.get("failed_check_count", 0) or 0)
    bridge_latest_phase = int(source_anchor.get("latest_phase", 0) or 0)

    missing_policy_permissions = [missing for policy in policies for missing in policy["missing_permissions"]]
    missing_contract_policies = [missing for contract in contracts for missing in contract["missing_policies"]]
    allowed_count = sum(1 for item in resource_permissions if item["policy_allowed"])
    denied_count = sum(1 for item in resource_permissions if not item["policy_allowed"])
    checks = [
        _check("bridge_manifest_present", bridge_manifest_path.exists(), str(bridge_manifest_path)),
        _check(
            "bridge_manifest_usable",
            bridge_manifest.get("status") in {"pass", "warn"} and bridge_failed == 0 and bridge_latest_phase >= 65,
            f"status={bridge_manifest.get('status', 'missing')}; latest_phase={bridge_latest_phase}; failed_check_count={bridge_failed}",
        ),
        _check(
            "capability_security_bridge_covered",
            capability_security.get("coverage") == "covered",
            f"coverage={capability_security.get('coverage')}",
        ),
        _check(
            "resource_bridge_covered",
            service_graph.get("coverage") == "covered",
            f"coverage={service_graph.get('coverage')}",
        ),
        _check(
            "core_ir_boundary_receipt_present",
            core_ir_boundary_receipt_path is not None and core_ir_boundary_receipt_path.exists(),
            str(core_ir_boundary_receipt_path or ""),
        ),
        _check(
            "core_ir_boundary_receipt_usable",
            core_status in {"phase66_pending", "validated_non_promoting", "parser_to_kernel_ready"}
            and core_failed_checks == 0
            and core_unexpected_invalid == 0
            and not core_kernel_claimed,
            f"status={core_status}; failed={core_failed_checks}; unexpected_invalid={core_unexpected_invalid}; kernel_claimed={core_kernel_claimed}",
        ),
        _check(
            "core_ir_boundary_binding_mode_declared",
            core_integration_mode in {"metadata_only_non_promoting", "phase66_parser_to_kernel_promotable"},
            f"binding_mode={core_integration_mode}; promotion={combined_parser_to_kernel_promotion_allowed}",
        ),
        _check(
            "core_ir_executable_audit_bound",
            audit_bound,
            str(core_ir_executable_audit_path or ""),
        ),
        _check(
            "core_ir_executable_audit_usable",
            audit_status in {"audited_non_promoting", "parser_to_kernel_ready"}
            and audit_failed_checks == 0
            and not audit_kernel_claimed
            and audit_source_matches_receipt,
            (
                f"status={audit_status}; failed={audit_failed_checks}; kernel_claimed={audit_kernel_claimed}; "
                f"source_matches_receipt={audit_source_matches_receipt}"
            ),
        ),
        _check(
            "core_ir_executable_audit_non_promoting_consistent",
            (not audit_kernel_handoff_allowed) or (core_integration_mode == "phase66_parser_to_kernel_promotable"),
            f"kernel_handoff_allowed={audit_kernel_handoff_allowed}; binding_mode={core_integration_mode}",
        ),
        _check(
            "parser_kernel_promotion_receipt_bound",
            promotion_bound,
            str(parser_kernel_promotion_receipt_path or ""),
        ),
        _check(
            "parser_kernel_promotion_receipt_usable",
            promotion_status in {"blocked_until_phase66", "parser_to_kernel_ready"}
            and promotion_failed_checks == 0
            and not promotion_kernel_claimed
            and promotion_source_matches_audit,
            (
                f"status={promotion_status}; failed={promotion_failed_checks}; "
                f"kernel_claimed={promotion_kernel_claimed}; source_matches_audit={promotion_source_matches_audit}"
            ),
        ),
        _check(
            "parser_kernel_promotion_receipt_consistent",
            promotion_consistent_with_audit
            and (
                not promotion_kernel_handoff_allowed
                or core_integration_mode == "phase66_parser_to_kernel_promotable"
            ),
            (
                f"phase66={promotion_phase66}; promotion={promotion_allowed}; "
                f"handoff={promotion_kernel_handoff_allowed}; binding_mode={core_integration_mode}"
            ),
        ),
        _check(
            "all_symbol_sources_present",
            all(source["exists"] for source in symbol_sources),
            f"missing={[source['kind'] for source in symbol_sources if not source['exists']]}",
        ),
        _check("capabilities_present", bool(capabilities_by_name), f"count={len(capabilities_by_name)}"),
        _check("resources_present", bool(resources_by_id), f"count={len(resources_by_id)}"),
        _check("permissions_present", bool(permissions_by_name), f"count={len(permissions_by_name)}"),
        _check("policies_present", bool(policies), f"count={len(policies)}"),
        _check("contracts_present", bool(contracts), f"count={len(contracts)}"),
        _check(
            "policy_permission_refs_resolve",
            not missing_policy_permissions,
            "all policy permission references resolve" if not missing_policy_permissions else f"missing={missing_policy_permissions}",
        ),
        _check(
            "contract_policy_refs_resolve",
            not missing_contract_policies,
            "all contract policy references resolve" if not missing_contract_policies else f"missing={missing_contract_policies}",
        ),
        _check(
            "resource_permission_links_present",
            bool(resource_permissions),
            f"count={len(resource_permissions)}",
        ),
        _check(
            "matrix_has_allowed_and_denied_paths",
            allowed_count > 0 and denied_count > 0,
            f"allowed={allowed_count}; denied={denied_count}",
        ),
        _check(
            "trap_operations_present",
            bool(trap_operations),
            f"count={len(trap_operations)}",
        ),
    ]
    failed = [check for check in checks if not check["ok"]]
    warnings = []
    if bridge_manifest.get("status") == "warn":
        warnings.append("bridge manifest is warn, usually from a dirty live PooleGlyph source anchor")

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "status": "fail" if failed else "warn" if warnings else "pass",
        "bridge_manifest": {
            "artifact_path": str(bridge_manifest_path),
            "status": str(bridge_manifest.get("status", "")),
            "latest_phase": bridge_latest_phase,
            "failed_check_count": bridge_failed,
            "pooleglyph_path": str(resolved_pooleglyph),
        },
        "core_ir_boundary_receipt": {
            "artifact_path": str(core_ir_boundary_receipt_path or ""),
            "exists": bool(core_ir_boundary_receipt_path and core_ir_boundary_receipt_path.exists()),
            "status": core_status,
            "phase66_audit_present": core_phase66,
            "parser_to_kernel_promotion_allowed": core_promotion_allowed,
            "kernel_enforcement_claimed": combined_kernel_claimed,
            "failed_check_count": core_failed_checks,
            "failed_promotion_gate_count": int(core_summary.get("failed_promotion_gate_count", 0) or 0),
            "validated_executable_candidate_count": int(core_summary.get("validated_executable_candidate_count", 0) or 0),
            "validated_metadata_zero_program_count": int(core_summary.get("validated_metadata_zero_program_count", 0) or 0),
            "unexpected_invalid_count": core_unexpected_invalid,
            "validation_file_count": int(core_validation.get("validation_file_count", 0) or 0),
            "binding_mode": core_integration_mode,
        },
        "core_ir_executable_audit": {
            "artifact_path": str(core_ir_executable_audit_path or ""),
            "exists": audit_bound,
            "status": audit_status,
            "source_boundary_receipt": str(audit_source.get("artifact_path", "")),
            "source_matches_receipt": audit_source_matches_receipt,
            "phase66_audit_present": audit_summary.get("phase66_audit_present") is True,
            "parser_to_kernel_promotion_allowed": audit_promotion_allowed,
            "kernel_handoff_allowed": audit_kernel_handoff_allowed,
            "kernel_enforcement_claimed": audit_kernel_claimed,
            "failed_check_count": audit_failed_checks,
            "executable_candidate_count": int(audit_summary.get("executable_candidate_count", 0) or 0),
            "metadata_zero_count": int(audit_summary.get("metadata_zero_count", 0) or 0),
            "unexpected_invalid_count": int(audit_summary.get("unexpected_invalid_count", 0) or 0),
        },
        "parser_kernel_promotion_receipt": {
            "artifact_path": str(parser_kernel_promotion_receipt_path or ""),
            "exists": promotion_bound,
            "status": promotion_status,
            "source_executable_audit": str(promotion_source.get("artifact_path", "")),
            "source_matches_audit": promotion_source_matches_audit,
            "phase66_audit_present": promotion_phase66,
            "parser_to_kernel_promotion_allowed": promotion_allowed,
            "kernel_handoff_allowed": promotion_kernel_handoff_allowed,
            "kernel_enforcement_claimed": promotion_kernel_claimed,
            "failed_check_count": promotion_failed_checks,
        },
        "symbol_sources": symbol_sources,
        "capabilities": sorted(capabilities_by_name.values(), key=lambda item: item["name"]),
        "resources": sorted(resources_by_id.values(), key=lambda item: item["id"]),
        "permissions": sorted(permissions_by_name.values(), key=lambda item: item["name"]),
        "policies": policies,
        "contracts": contracts,
        "resource_permissions": resource_permissions,
        "trap_operations": trap_operations,
        "checks": checks,
        "summary": {
            "capability_count": len(capabilities_by_name),
            "resource_count": len(resources_by_id),
            "permission_count": len(permissions_by_name),
            "policy_count": len(policies),
            "contract_count": len(contracts),
            "resource_permission_count": len(resource_permissions),
            "allowed_resource_permission_count": allowed_count,
            "denied_resource_permission_count": denied_count,
            "trap_operation_count": len(trap_operations),
            "failed_check_count": len(failed),
            "warning_count": len(warnings),
            "core_ir_binding_mode": core_integration_mode,
            "core_ir_phase66_audit_present": core_phase66,
            "core_ir_executable_audit_bound": audit_bound,
            "core_ir_executable_audit_status": audit_status,
            "core_ir_executable_candidate_count": int(audit_summary.get("executable_candidate_count", 0) or 0),
            "core_ir_metadata_zero_count": int(audit_summary.get("metadata_zero_count", 0) or 0),
            "core_ir_kernel_handoff_allowed": audit_kernel_handoff_allowed,
            "parser_kernel_promotion_receipt_bound": promotion_bound,
            "parser_kernel_promotion_receipt_status": promotion_status,
            "parser_kernel_promotion_kernel_handoff_allowed": promotion_kernel_handoff_allowed,
            "parser_to_kernel_promotion_allowed": combined_parser_to_kernel_promotion_allowed,
            "kernel_enforcement_claimed": core_kernel_claimed,
        },
        "limitations": [
            "Matrix is derived from public PooleGlyph metadata and symbol outputs; it is not a frozen PooleOS ABI.",
            "Resource-permission links use declaration naming hints while the parser-to-kernel promotion receipt is non-promoting.",
            "Trap operations are simulator inputs for PooleOS proof artifacts and do not claim booted-kernel enforcement.",
        ],
        "next_steps": [
            "Bind matrix trap operations into the capability trap proof.",
            "Replace name-derived resource links with Core IR linkage after the boundary receipt permits parser-to-kernel promotion.",
            "Emit a signed capability manifest after the matrix schema stabilizes.",
        ],
    }


def write_matrix(matrix: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(matrix, indent=2, sort_keys=True) + "\n", encoding="utf-8")
