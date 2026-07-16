"""Executable PGB2-style capability trap checks for the PooleOS isolation policy."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from runtime import microkernel_isolation


SCHEMA_VERSION = "0.1"
ARTIFACT_KIND = "pooleos.capability_trap_proof"


def _edge(record: dict[str, Any]) -> tuple[str, str, str]:
    return (str(record.get("source", "")), str(record.get("target", "")), str(record.get("capability", "")))


def _check(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _matrix_operations(matrix: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not matrix:
        return []
    operations = []
    for operation in matrix.get("trap_operations", []):
        copied = dict(operation)
        copied.setdefault("reason", "PooleGlyph permission/capability matrix operation.")
        operations.append(copied)
    return operations


def _fuzz_operations(fuzz: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not fuzz:
        return []
    operations = []
    for operation in fuzz.get("operations", []):
        copied = dict(operation)
        copied.setdefault("reason", "Generated capability trap fuzz operation.")
        operations.append(copied)
    return operations


def default_operations() -> list[dict[str, Any]]:
    return [
        {
            "opcode": "ASSERT_REGION_CAP",
            "region": "geometry_exec",
            "source": "pgvm_guest",
            "target": "geometry_kernel",
            "capability": "invoke_rule",
            "expected_trap": False,
            "reason": "Guest execution may invoke mediated geometry rules.",
        },
        {
            "opcode": "ASSERT_REGION_CAP",
            "region": "claim_lane_store",
            "source": "pgvm_guest",
            "target": "provenance_service",
            "capability": "write_claim_lane",
            "expected_trap": True,
            "reason": "Guest code must not directly write provenance records.",
        },
        {
            "opcode": "ASSERT_REGION_CAP",
            "region": "lattice_state",
            "source": "host_bridge",
            "target": "geometry_kernel",
            "capability": "mutate_lattice_state",
            "expected_trap": True,
            "reason": "Host integration must not directly mutate kernel geometry state.",
        },
        {
            "opcode": "ASSERT_REGION_CAP",
            "region": "trace_digest",
            "source": "geometry_kernel",
            "target": "provenance_service",
            "capability": "append_trace_hash",
            "expected_trap": False,
            "reason": "Geometry kernel may append trace hashes after execution.",
        },
        {
            "opcode": "ASSERT_REGION_CAP",
            "region": "signed_metrics",
            "source": "pgvm_guest",
            "target": "signed_metric_service",
            "capability": "set_benchmark_result",
            "expected_trap": True,
            "reason": "Guest code must not directly set benchmark results.",
        },
        {
            "opcode": "SNAPSHOT_REGION",
            "region": "release_manifest",
            "source": "operator_shell",
            "target": "provenance_service",
            "capability": "read_manifest",
            "expected_trap": False,
            "reason": "Operator shell may read release evidence through mediation.",
        },
        {
            "opcode": "ASSERT_REGION_CAP",
            "region": "geometry_exec",
            "source": "signed_metric_service",
            "target": "geometry_kernel",
            "capability": "mutate_region",
            "expected_trap": True,
            "reason": "Metric services cannot feed mutations back into geometry execution.",
        },
    ]


def classify_operation(operation: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    if operation.get("opcode") == "ASSERT_MATRIX_PERMISSION":
        allowed = operation.get("matrix_allowed") is True
        classified = dict(operation)
        classified["allowed"] = allowed
        classified["actual_trapped"] = not allowed
        classified["trap_code"] = "" if allowed else "POOLEGLYPH_PERMISSION_DENIED"
        return classified

    allowed_edges = {_edge(channel) for channel in policy.get("channels", [])}
    denied_by_edge = {_edge(channel): str(channel.get("reason", "")) for channel in policy.get("denied_channels", [])}
    edge = _edge(operation)
    allowed = edge in allowed_edges
    denied = edge in denied_by_edge

    if allowed:
        actual_trapped = False
        trap_code = ""
    elif denied:
        actual_trapped = True
        trap_code = "CAPABILITY_DENIED"
    else:
        actual_trapped = True
        trap_code = "CAPABILITY_UNKNOWN"

    classified = dict(operation)
    classified["allowed"] = allowed
    classified["actual_trapped"] = actual_trapped
    classified["trap_code"] = trap_code
    if denied and not classified.get("reason"):
        classified["reason"] = denied_by_edge[edge]
    return classified


def make_capability_trap_proof(
    *,
    policy: dict[str, Any] | None = None,
    policy_artifact: Path | None = None,
    permission_matrix: dict[str, Any] | None = None,
    permission_matrix_artifact: Path | None = None,
    trap_fuzz: dict[str, Any] | None = None,
    trap_fuzz_artifact: Path | None = None,
) -> dict[str, Any]:
    if policy is None:
        policy = _read_json(policy_artifact) if policy_artifact is not None else microkernel_isolation.make_isolation_proof()
    if permission_matrix is None and permission_matrix_artifact is not None:
        permission_matrix = _read_json(permission_matrix_artifact)
    if trap_fuzz is None and trap_fuzz_artifact is not None:
        trap_fuzz = _read_json(trap_fuzz_artifact)

    matrix_operations = _matrix_operations(permission_matrix)
    fuzz_operations = _fuzz_operations(trap_fuzz)
    operations = [
        classify_operation(operation, policy)
        for operation in [*default_operations(), *matrix_operations, *fuzz_operations]
    ]
    operation_checks = [
        _check(
            f"operation_{index}_{operation['capability']}",
            operation["expected_trap"] == operation["actual_trapped"],
            f"opcode={operation['opcode']}; expected_trap={operation['expected_trap']}; actual_trapped={operation['actual_trapped']}; trap_code={operation['trap_code']}",
        )
        for index, operation in enumerate(operations)
    ]
    matrix_source_summary = permission_matrix.get("summary", {}) if permission_matrix else {}
    matrix_core_receipt = permission_matrix.get("core_ir_boundary_receipt", {}) if permission_matrix else {}
    matrix_core_audit = permission_matrix.get("core_ir_executable_audit", {}) if permission_matrix else {}
    matrix_promotion_receipt = permission_matrix.get("parser_kernel_promotion_receipt", {}) if permission_matrix else {}
    matrix_core_binding_mode = str(matrix_source_summary.get("core_ir_binding_mode", "")) if permission_matrix else ""
    matrix_core_kernel_claimed = matrix_source_summary.get("kernel_enforcement_claimed") is True if permission_matrix else False
    matrix_core_audit_bound = matrix_source_summary.get("core_ir_executable_audit_bound") is True if permission_matrix else False
    matrix_core_audit_status = str(matrix_source_summary.get("core_ir_executable_audit_status", "")) if permission_matrix else ""
    matrix_core_handoff_allowed = matrix_source_summary.get("core_ir_kernel_handoff_allowed") is True if permission_matrix else False
    matrix_promotion_bound = matrix_source_summary.get("parser_kernel_promotion_receipt_bound") is True if permission_matrix else False
    matrix_promotion_status = str(matrix_source_summary.get("parser_kernel_promotion_receipt_status", "")) if permission_matrix else ""
    matrix_promotion_handoff_allowed = (
        matrix_source_summary.get("parser_kernel_promotion_kernel_handoff_allowed") is True
        if permission_matrix
        else False
    )
    checks = [
        _check(
            "policy_passed",
            policy.get("status") == "pass",
            f"policy_status={policy.get('status')}",
        ),
        _check(
            "instruction_family_declared",
            True,
            "DEFINE_REGION, ENTER_REGION, ASSERT_REGION_CAP, SNAPSHOT_REGION",
        ),
        _check(
            "permission_matrix_usable",
            permission_matrix is None
            or (
                permission_matrix.get("status") in {"pass", "warn"}
                and permission_matrix.get("summary", {}).get("failed_check_count") == 0
                and len(matrix_operations) > 0
            ),
            "not provided"
            if permission_matrix is None
            else f"status={permission_matrix.get('status')}; failed_checks={permission_matrix.get('summary', {}).get('failed_check_count')}; matrix_operations={len(matrix_operations)}",
        ),
        _check(
            "permission_matrix_core_ir_boundary_bound",
            permission_matrix is None
            or (
                matrix_core_binding_mode in {"metadata_only_non_promoting", "phase66_parser_to_kernel_promotable"}
                and not matrix_core_kernel_claimed
            ),
            "not provided"
            if permission_matrix is None
            else f"binding_mode={matrix_core_binding_mode}; kernel_claimed={matrix_core_kernel_claimed}",
        ),
        _check(
            "permission_matrix_core_ir_executable_audit_bound",
            permission_matrix is None
            or "core_ir_executable_audit_bound" not in matrix_source_summary
            or (
                matrix_core_audit_bound
                and matrix_core_audit_status in {"audited_non_promoting", "parser_to_kernel_ready"}
                and (
                    not matrix_core_handoff_allowed
                    or matrix_core_binding_mode == "phase66_parser_to_kernel_promotable"
                )
            ),
            "not provided"
            if permission_matrix is None
            else f"audit_bound={matrix_core_audit_bound}; audit_status={matrix_core_audit_status}; kernel_handoff_allowed={matrix_core_handoff_allowed}",
        ),
        _check(
            "permission_matrix_parser_kernel_promotion_receipt_bound",
            permission_matrix is None
            or "parser_kernel_promotion_receipt_bound" not in matrix_source_summary
            or (
                matrix_promotion_bound
                and matrix_promotion_status in {"blocked_until_phase66", "parser_to_kernel_ready"}
                and (
                    not matrix_promotion_handoff_allowed
                    or matrix_core_binding_mode == "phase66_parser_to_kernel_promotable"
                )
            ),
            "not provided"
            if permission_matrix is None
            else (
                f"promotion_bound={matrix_promotion_bound}; promotion_status={matrix_promotion_status}; "
                f"kernel_handoff_allowed={matrix_promotion_handoff_allowed}"
            ),
        ),
        _check(
            "trap_fuzz_usable",
            trap_fuzz is None
            or (
                trap_fuzz.get("status") == "pass"
                and trap_fuzz.get("summary", {}).get("failed_check_count") == 0
                and len(fuzz_operations) > 0
            ),
            "not provided"
            if trap_fuzz is None
            else f"status={trap_fuzz.get('status')}; failed_checks={trap_fuzz.get('summary', {}).get('failed_check_count')}; fuzz_operations={len(fuzz_operations)}",
        ),
        *operation_checks,
        _check(
            "denied_operations_trapped",
            all(operation["actual_trapped"] for operation in operations if operation["expected_trap"]),
            "all expected denials trapped",
        ),
        _check(
            "allowed_operations_not_trapped",
            all(not operation["actual_trapped"] for operation in operations if not operation["expected_trap"]),
            "all expected allowances ran without trap",
        ),
        _check(
            "security_boundary_not_claimed",
            policy.get("security_boundary_claimed") is False,
            f"security_boundary_claimed={policy.get('security_boundary_claimed')}",
        ),
    ]
    failed = [check for check in checks if not check["ok"]]
    matrix_summary = {
        "matrix_bound": permission_matrix is not None,
        "matrix_artifact": str(permission_matrix_artifact or ""),
        "matrix_status": str(permission_matrix.get("status", "")) if permission_matrix else "",
        "matrix_failed_check_count": int(permission_matrix.get("summary", {}).get("failed_check_count", 0) or 0)
        if permission_matrix
        else 0,
        "matrix_operation_count": len(matrix_operations),
        "core_ir_receipt_artifact": str(matrix_core_receipt.get("artifact_path", "")) if permission_matrix else "",
        "core_ir_boundary_status": str(matrix_core_receipt.get("status", "")) if permission_matrix else "",
        "core_ir_binding_mode": matrix_core_binding_mode,
        "core_ir_phase66_audit_present": matrix_source_summary.get("core_ir_phase66_audit_present") is True
        if permission_matrix
        else False,
        "core_ir_executable_audit_artifact": str(matrix_core_audit.get("artifact_path", "")) if permission_matrix else "",
        "core_ir_executable_audit_bound": matrix_core_audit_bound,
        "core_ir_executable_audit_status": matrix_core_audit_status,
        "core_ir_executable_candidate_count": int(matrix_source_summary.get("core_ir_executable_candidate_count", 0) or 0)
        if permission_matrix
        else 0,
        "core_ir_metadata_zero_count": int(matrix_source_summary.get("core_ir_metadata_zero_count", 0) or 0)
        if permission_matrix
        else 0,
        "core_ir_kernel_handoff_allowed": matrix_core_handoff_allowed,
        "parser_kernel_promotion_receipt_artifact": str(matrix_promotion_receipt.get("artifact_path", "")) if permission_matrix else "",
        "parser_kernel_promotion_receipt_bound": matrix_promotion_bound,
        "parser_kernel_promotion_receipt_status": matrix_promotion_status,
        "parser_kernel_promotion_kernel_handoff_allowed": matrix_promotion_handoff_allowed,
        "parser_to_kernel_promotion_allowed": matrix_source_summary.get("parser_to_kernel_promotion_allowed") is True
        if permission_matrix
        else False,
        "kernel_enforcement_claimed": matrix_core_kernel_claimed,
    }
    fuzz_summary = {
        "fuzz_bound": trap_fuzz is not None,
        "fuzz_artifact": str(trap_fuzz_artifact or ""),
        "fuzz_status": str(trap_fuzz.get("status", "")) if trap_fuzz else "",
        "fuzz_failed_check_count": int(trap_fuzz.get("summary", {}).get("failed_check_count", 0) or 0)
        if trap_fuzz
        else 0,
        "fuzz_operation_count": len(fuzz_operations),
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "status": "pass" if not failed else "fail",
        "policy_version": str(policy.get("policy_version", "")),
        "policy_artifact": str(policy_artifact or ""),
        "matrix_artifact": str(permission_matrix_artifact or ""),
        "matrix_summary": matrix_summary,
        "fuzz_artifact": str(trap_fuzz_artifact or ""),
        "fuzz_summary": fuzz_summary,
        "instruction_family": "PGB2 Regions And Capabilities",
        "security_boundary_claimed": False,
        "operations": operations,
        "checks": checks,
        "summary": {
            "operation_count": len(operations),
            "allowed_count": sum(1 for operation in operations if not operation["actual_trapped"]),
            "trapped_count": sum(1 for operation in operations if operation["actual_trapped"]),
            "failed_check_count": len(failed),
        },
        "limitations": [
            "Trap proof is an executable simulator over the static policy, not a booted kernel enforcement result.",
            "Does not prove hardware isolation, process isolation, memory protection, or side-channel resistance.",
            "Opcode names follow the current PGB2 draft and may change before a frozen binary format exists.",
        ],
        "next_steps": [
            "Attach these trap cases to concrete PGB2 bytecode encodings.",
            "Run the same negative cases inside the PooleOS Lab image after QEMU boot evidence exists.",
            "Attach fuzz cases to concrete bytecode encodings after PGB2 freezes.",
        ],
    }


def write_proof(proof: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")
