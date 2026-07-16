"""Deterministic fuzz proof for PooleOS closed-by-default trap behavior."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from runtime import capability_traps
from runtime import microkernel_isolation


SCHEMA_VERSION = "0.1"
ARTIFACT_KIND = "pooleos.capability_trap_fuzz"
DEFAULT_SEED = "pooleos-cycle34-closed-by-default-v0"

UNKNOWN_CAPABILITIES = [
    "unknown_power",
    "rewrite_geometry",
    "direct_memory_write",
    "kernel_escape",
    "shadow_append",
    "unbounded_mutate",
    "side_channel_probe",
    "raw_host_write",
    "private_runtime_entry",
    "signed_metric_override",
    "boot_manifest_rewrite",
    "capability_escalate",
]

UNKNOWN_PERMISSIONS = [
    "delete_grid",
    "rewrite_grid",
    "export_grid_raw",
    "mount_grid",
    "elevate_grid",
    "bypass_grid",
    "shadow_grid",
    "override_grid",
]


def _check(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _edge(record: dict[str, Any]) -> tuple[str, str, str]:
    return (str(record.get("source", "")), str(record.get("target", "")), str(record.get("capability", "")))


def _compartment_ids(policy: dict[str, Any]) -> list[str]:
    ids = [str(compartment.get("id", "")) for compartment in policy.get("compartments", [])]
    return [item for item in ids if item] or ["pgvm_guest", "geometry_kernel"]


def _resource_ids(matrix: dict[str, Any] | None) -> list[str]:
    if not matrix:
        return ["grid.main_grid"]
    ids = [str(resource.get("id", "")) for resource in matrix.get("resources", [])]
    return [item for item in ids if item] or ["grid.main_grid"]


def _unknown_capability_operations(policy: dict[str, Any], count: int) -> list[dict[str, Any]]:
    compartments = _compartment_ids(policy)
    known_edges = {
        *{_edge(channel) for channel in policy.get("channels", [])},
        *{_edge(channel) for channel in policy.get("denied_channels", [])},
    }
    operations: list[dict[str, Any]] = []
    index = 0
    candidate = 0
    while len(operations) < count:
        source = compartments[candidate % len(compartments)]
        target = compartments[(candidate * 2 + 1) % len(compartments)]
        capability = UNKNOWN_CAPABILITIES[candidate % len(UNKNOWN_CAPABILITIES)]
        candidate += 1
        if source == target or (source, target, capability) in known_edges:
            continue
        operations.append(
            {
                "case_id": f"unknown_capability_{index:02d}",
                "fuzz_kind": "unknown_capability",
                "opcode": "ASSERT_REGION_CAP",
                "region": f"fuzz_region_{index:02d}",
                "source": source,
                "target": target,
                "capability": capability,
                "expected_trap": True,
                "reason": "Generated unknown capability edge must trap closed.",
            }
        )
        index += 1
    return operations


def _unknown_permission_operations(matrix: dict[str, Any] | None, count: int) -> list[dict[str, Any]]:
    resources = _resource_ids(matrix)
    operations = []
    for index in range(count):
        resource_id = resources[index % len(resources)]
        permission = UNKNOWN_PERMISSIONS[index % len(UNKNOWN_PERMISSIONS)]
        operations.append(
            {
                "case_id": f"unknown_permission_{index:02d}",
                "fuzz_kind": "unknown_permission",
                "opcode": "ASSERT_MATRIX_PERMISSION",
                "region": resource_id,
                "source": "pgvm_guest",
                "target": "geometry_kernel",
                "capability": permission,
                "matrix_allowed": False,
                "expected_trap": True,
                "reason": "Generated unknown PooleGlyph permission path must trap closed.",
            }
        )
    return operations


def make_capability_trap_fuzz(
    *,
    policy: dict[str, Any] | None = None,
    policy_artifact: Path | None = None,
    permission_matrix: dict[str, Any] | None = None,
    permission_matrix_artifact: Path | None = None,
    seed: str = DEFAULT_SEED,
    unknown_capability_count: int = 12,
    unknown_permission_count: int = 8,
) -> dict[str, Any]:
    if policy is None:
        policy = _read_json(policy_artifact) if policy_artifact is not None else microkernel_isolation.make_isolation_proof()
    if permission_matrix is None and permission_matrix_artifact is not None:
        permission_matrix = _read_json(permission_matrix_artifact)

    generated = [
        *_unknown_capability_operations(policy, unknown_capability_count),
        *_unknown_permission_operations(permission_matrix, unknown_permission_count),
    ]
    operations = [capability_traps.classify_operation(operation, policy) for operation in generated]
    for index, operation in enumerate(operations):
        operation.setdefault("case_id", generated[index]["case_id"])
        operation.setdefault("fuzz_kind", generated[index]["fuzz_kind"])

    case_ids = [str(operation.get("case_id", "")) for operation in operations]
    unknown_capability_ops = [operation for operation in operations if operation.get("fuzz_kind") == "unknown_capability"]
    unknown_permission_ops = [operation for operation in operations if operation.get("fuzz_kind") == "unknown_permission"]
    checks = [
        _check("policy_passed", policy.get("status") == "pass", f"policy_status={policy.get('status')}"),
        _check(
            "permission_matrix_usable",
            permission_matrix is not None
            and permission_matrix.get("status") in {"pass", "warn"}
            and permission_matrix.get("summary", {}).get("failed_check_count") == 0,
            "not provided"
            if permission_matrix is None
            else f"status={permission_matrix.get('status')}; failed_checks={permission_matrix.get('summary', {}).get('failed_check_count')}",
        ),
        _check("case_ids_unique", len(case_ids) == len(set(case_ids)), f"cases={len(case_ids)}"),
        _check(
            "all_generated_cases_expect_trap",
            all(operation.get("expected_trap") is True for operation in operations),
            f"operation_count={len(operations)}",
        ),
        _check(
            "all_generated_cases_trapped",
            all(operation.get("actual_trapped") is True for operation in operations),
            f"trapped={sum(1 for operation in operations if operation.get('actual_trapped') is True)}",
        ),
        _check(
            "unknown_capabilities_trap_unknown",
            all(operation.get("trap_code") == "CAPABILITY_UNKNOWN" for operation in unknown_capability_ops),
            f"unknown_capability_count={len(unknown_capability_ops)}",
        ),
        _check(
            "unknown_permissions_trap_denied",
            all(operation.get("trap_code") == "POOLEGLYPH_PERMISSION_DENIED" for operation in unknown_permission_ops),
            f"unknown_permission_count={len(unknown_permission_ops)}",
        ),
        _check("security_boundary_not_claimed", True, "security_boundary_claimed=False"),
    ]
    failed = [check for check in checks if not check["ok"]]

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "status": "pass" if not failed else "fail",
        "seed": seed,
        "policy_artifact": str(policy_artifact or ""),
        "matrix_artifact": str(permission_matrix_artifact or ""),
        "security_boundary_claimed": False,
        "operations": operations,
        "checks": checks,
        "summary": {
            "operation_count": len(operations),
            "unknown_capability_count": len(unknown_capability_ops),
            "unknown_permission_count": len(unknown_permission_ops),
            "trapped_count": sum(1 for operation in operations if operation.get("actual_trapped") is True),
            "failed_check_count": len(failed),
        },
        "limitations": [
            "Fuzzing is deterministic and bounded; it is not exhaustive formal verification.",
            "Unknown permission cases use matrix-denied PooleGlyph metadata paths, not a booted kernel substrate.",
            "This artifact proves closed-by-default simulator behavior only.",
        ],
        "next_steps": [
            "Attach fuzz cases to concrete PGB2 bytecode encodings after the binary format freezes.",
            "Run the same generated cases inside the PooleOS Lab image after boot evidence exists.",
            "Expand the generator after PooleGlyph Phase 66 Core IR boundary evidence lands.",
        ],
    }


def write_fuzz(fuzz: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fuzz, indent=2, sort_keys=True) + "\n", encoding="utf-8")
