import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import permission_capability_matrix  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import emit_permission_capability_matrix  # noqa: E402


class PermissionCapabilityMatrixTests(unittest.TestCase):
    def _write_symbols(self, package_root: Path) -> tuple[Path, Path, Path, Path]:
        source_anchor = {
            "pooleglyph_path": str(package_root.parents[1]),
            "latest_phase": 65,
            "failed_check_count": 0,
        }
        bridge = {
            "artifact_kind": "pooleos.pooleglyph_bridge_manifest",
            "status": "warn",
            "source_anchor": source_anchor,
            "summary": {"failed_check_count": 0},
            "bridge_maps": {
                "capability_security": {"coverage": "covered"},
                "service_graph": {"coverage": "covered"},
            },
        }
        bridge_path = package_root.parents[1] / "bridge.json"
        bridge_path.write_text(json.dumps(bridge), encoding="utf-8")
        receipt = {
            "artifact_kind": "pooleos.pooleglyph_core_ir_boundary_receipt",
            "status": "phase66_pending",
            "kernel_enforcement_claimed": False,
            "summary": {
                "failed_check_count": 0,
                "failed_promotion_gate_count": 1,
                "phase66_audit_present": False,
                "parser_to_kernel_promotion_allowed": False,
                "kernel_enforcement_claimed": False,
                "validated_executable_candidate_count": 2,
                "validated_metadata_zero_program_count": 1,
                "unexpected_invalid_count": 0,
            },
            "core_ir_validation_summary": {
                "validation_file_count": 6,
            },
        }
        receipt_path = package_root.parents[1] / "core_ir_receipt.json"
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        audit = {
            "artifact_kind": "pooleos.pooleglyph_core_ir_executable_audit",
            "status": "audited_non_promoting",
            "source_boundary_receipt": {
                "artifact_path": str(receipt_path),
            },
            "summary": {
                "failed_check_count": 0,
                "phase66_audit_present": False,
                "parser_to_kernel_promotion_allowed": False,
                "kernel_handoff_allowed": False,
                "kernel_enforcement_claimed": False,
                "executable_candidate_count": 2,
                "metadata_zero_count": 1,
                "unexpected_invalid_count": 0,
            },
        }
        audit_path = package_root.parents[1] / "core_ir_executable_audit.json"
        audit_path.write_text(json.dumps(audit), encoding="utf-8")
        promotion_receipt = {
            "artifact_kind": "pooleos.pooleglyph_parser_kernel_promotion_receipt",
            "status": "blocked_until_phase66",
            "source_executable_audit": {
                "artifact_path": str(audit_path),
            },
            "summary": {
                "failed_check_count": 0,
                "phase66_audit_present": False,
                "parser_to_kernel_promotion_allowed": False,
                "kernel_handoff_allowed": False,
                "kernel_enforcement_claimed": False,
                "executable_candidate_count": 2,
                "metadata_zero_count": 1,
                "unexpected_invalid_count": 0,
            },
        }
        promotion_receipt_path = package_root.parents[1] / "parser_kernel_promotion_receipt.json"
        promotion_receipt_path.write_text(json.dumps(promotion_receipt), encoding="utf-8")

        files = {
            "outputs_capabilities/capability_demo.symbols.json": {
                "module": "examples.capability_demo",
                "capabilities": [{"name": "geometry"}, {"name": "rulesets"}],
            },
            "outputs_resources/resource_demo.symbols.json": {
                "module": "examples.resource_demo",
                "resources": [
                    {
                        "kind": "grid",
                        "name": "main_grid",
                        "fields": [{"key": "kind", "value": "cellular"}],
                    }
                ],
            },
            "outputs_permissions/permission_demo.symbols.json": {
                "module": "snapshots.permission",
                "permissions": [{"name": "read_grid"}, {"name": "write_grid"}],
            },
            "outputs_policies/policy_demo.symbols.json": {
                "module": "snapshots.policy",
                "permissions": [{"name": "read_grid"}, {"name": "write_grid"}],
                "policies": [
                    {
                        "name": "safe_public",
                        "steps": [{"action": "allow", "kind": "permission", "target": "read_grid"}],
                    }
                ],
            },
            "outputs_contracts/contract_demo.symbols.json": {
                "module": "snapshots.contract",
                "permissions": [{"name": "read_grid"}, {"name": "write_grid"}],
                "policies": [
                    {
                        "name": "safe_public",
                        "steps": [{"action": "allow", "kind": "permission", "target": "read_grid"}],
                    }
                ],
                "contracts": [
                    {
                        "name": "public_api",
                        "steps": [{"action": "require", "kind": "policy", "target": "safe_public"}],
                    }
                ],
            },
        }
        for relative, data in files.items():
            path = package_root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data), encoding="utf-8")
        return bridge_path, receipt_path, audit_path, promotion_receipt_path

    def test_matrix_validates_and_has_allow_and_deny_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pooleglyph = Path(tmp) / "PooleGlyph"
            package_root = pooleglyph / "pooleglyph_v0_5_parser_ast_scaffold_package"
            bridge_path, receipt_path, audit_path, promotion_receipt_path = self._write_symbols(package_root)
            matrix = permission_capability_matrix.make_permission_capability_matrix(
                bridge_manifest_path=bridge_path,
                core_ir_boundary_receipt_path=receipt_path,
                core_ir_executable_audit_path=audit_path,
                parser_kernel_promotion_receipt_path=promotion_receipt_path,
                pooleglyph_path=pooleglyph,
            )
            schema = json.loads((ROOT / "specs" / "permission-capability-matrix.schema.json").read_text(encoding="utf-8"))
            self.assertEqual(validate_json(matrix, schema), [])
            self.assertEqual(matrix["status"], "warn")
            self.assertEqual(matrix["summary"]["failed_check_count"], 0)
            self.assertEqual(matrix["summary"]["allowed_resource_permission_count"], 1)
            self.assertEqual(matrix["summary"]["denied_resource_permission_count"], 1)
            self.assertEqual(matrix["summary"]["trap_operation_count"], 2)
            self.assertEqual(matrix["core_ir_boundary_receipt"]["status"], "phase66_pending")
            self.assertEqual(matrix["core_ir_executable_audit"]["status"], "audited_non_promoting")
            self.assertEqual(matrix["parser_kernel_promotion_receipt"]["status"], "blocked_until_phase66")
            self.assertTrue(matrix["summary"]["core_ir_executable_audit_bound"])
            self.assertTrue(matrix["summary"]["parser_kernel_promotion_receipt_bound"])
            self.assertEqual(matrix["summary"]["core_ir_executable_candidate_count"], 2)
            self.assertEqual(matrix["summary"]["core_ir_binding_mode"], "metadata_only_non_promoting")
            self.assertFalse(matrix["summary"]["parser_to_kernel_promotion_allowed"])
            self.assertTrue(
                all(
                    operation["binding_mode"] == "metadata_only_non_promoting"
                    and operation["parser_to_kernel_promotion_allowed"] is False
                    for operation in matrix["trap_operations"]
                )
            )

    def test_cli_writes_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pooleglyph = Path(tmp) / "PooleGlyph"
            package_root = pooleglyph / "pooleglyph_v0_5_parser_ast_scaffold_package"
            bridge_path, receipt_path, audit_path, promotion_receipt_path = self._write_symbols(package_root)
            out = Path(tmp) / "matrix.json"
            with redirect_stdout(io.StringIO()):
                code = emit_permission_capability_matrix.main(
                    [
                        "--bridge-manifest",
                        str(bridge_path),
                        "--core-ir-boundary-receipt",
                        str(receipt_path),
                        "--core-ir-executable-audit",
                        str(audit_path),
                        "--parser-kernel-promotion-receipt",
                        str(promotion_receipt_path),
                        "--pooleglyph",
                        str(pooleglyph),
                        "--out",
                        str(out),
                    ]
                )
            self.assertEqual(code, 0)
            matrix = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(matrix["artifact_kind"], "pooleos.permission_capability_matrix")


if __name__ == "__main__":
    unittest.main()
