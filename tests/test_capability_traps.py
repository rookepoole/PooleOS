import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import capability_traps  # noqa: E402
from runtime import microkernel_isolation  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import emit_capability_trap_proof  # noqa: E402


class CapabilityTrapTests(unittest.TestCase):
    def test_capability_trap_proof_validates(self) -> None:
        policy = microkernel_isolation.make_isolation_proof()
        proof = capability_traps.make_capability_trap_proof(policy=policy)
        schema = json.loads((ROOT / "specs" / "capability-trap-proof.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(validate_json(proof, schema), [])
        self.assertEqual(proof["status"], "pass")
        self.assertEqual(proof["summary"]["failed_check_count"], 0)
        self.assertGreaterEqual(proof["summary"]["trapped_count"], 1)
        self.assertGreaterEqual(proof["summary"]["allowed_count"], 1)

    def test_denied_guest_claim_lane_write_traps(self) -> None:
        policy = microkernel_isolation.make_isolation_proof()
        operation = {
            "opcode": "ASSERT_REGION_CAP",
            "region": "claim_lane_store",
            "source": "pgvm_guest",
            "target": "provenance_service",
            "capability": "write_claim_lane",
            "expected_trap": True,
            "reason": "unit test",
        }
        classified = capability_traps.classify_operation(operation, policy)
        self.assertTrue(classified["actual_trapped"])
        self.assertEqual(classified["trap_code"], "CAPABILITY_DENIED")

    def test_unknown_capability_edge_traps(self) -> None:
        policy = microkernel_isolation.make_isolation_proof()
        operation = {
            "opcode": "ASSERT_REGION_CAP",
            "region": "unknown_region",
            "source": "pgvm_guest",
            "target": "geometry_kernel",
            "capability": "unknown_power",
            "expected_trap": True,
            "reason": "unit test",
        }
        classified = capability_traps.classify_operation(operation, policy)
        self.assertTrue(classified["actual_trapped"])
        self.assertEqual(classified["trap_code"], "CAPABILITY_UNKNOWN")

    def test_cli_writes_valid_capability_trap_proof(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            policy_path = tmp_path / "microkernel_isolation.json"
            microkernel_isolation.write_proof(microkernel_isolation.make_isolation_proof(), policy_path)
            out = tmp_path / "capability_trap_proof.json"
            with redirect_stdout(io.StringIO()):
                code = emit_capability_trap_proof.main(
                    ["--isolation-proof", str(policy_path), "--out", str(out)]
                )
            self.assertEqual(code, 0)
            proof = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(proof["status"], "pass")
            self.assertEqual(proof["policy_artifact"], str(policy_path))

    def test_permission_matrix_operations_bind_into_trap_proof(self) -> None:
        policy = microkernel_isolation.make_isolation_proof()
        matrix = {
            "status": "pass",
            "summary": {
                "failed_check_count": 0,
                "core_ir_binding_mode": "metadata_only_non_promoting",
                "core_ir_phase66_audit_present": False,
                "core_ir_executable_audit_bound": True,
                "core_ir_executable_audit_status": "audited_non_promoting",
                "core_ir_executable_candidate_count": 2,
                "core_ir_metadata_zero_count": 1,
                "core_ir_kernel_handoff_allowed": False,
                "parser_kernel_promotion_receipt_bound": True,
                "parser_kernel_promotion_receipt_status": "blocked_until_phase66",
                "parser_kernel_promotion_kernel_handoff_allowed": False,
                "parser_to_kernel_promotion_allowed": False,
                "kernel_enforcement_claimed": False,
            },
            "core_ir_boundary_receipt": {
                "artifact_path": "core_ir_receipt.json",
                "status": "phase66_pending",
            },
            "core_ir_executable_audit": {
                "artifact_path": "core_ir_executable_audit.json",
                "status": "audited_non_promoting",
            },
            "parser_kernel_promotion_receipt": {
                "artifact_path": "parser_kernel_promotion_receipt.json",
                "status": "blocked_until_phase66",
            },
            "trap_operations": [
                {
                    "opcode": "ASSERT_MATRIX_PERMISSION",
                    "region": "grid.main_grid",
                    "source": "pgvm_guest",
                    "target": "geometry_kernel",
                    "capability": "read_grid",
                    "matrix_allowed": True,
                    "expected_trap": False,
                    "reason": "unit allowed",
                },
                {
                    "opcode": "ASSERT_MATRIX_PERMISSION",
                    "region": "grid.main_grid",
                    "source": "pgvm_guest",
                    "target": "geometry_kernel",
                    "capability": "write_grid",
                    "matrix_allowed": False,
                    "expected_trap": True,
                    "reason": "unit denied",
                },
            ],
        }
        proof = capability_traps.make_capability_trap_proof(policy=policy, permission_matrix=matrix)
        self.assertEqual(proof["status"], "pass")
        self.assertTrue(proof["matrix_summary"]["matrix_bound"])
        self.assertEqual(proof["matrix_summary"]["matrix_operation_count"], 2)
        self.assertEqual(proof["matrix_summary"]["core_ir_binding_mode"], "metadata_only_non_promoting")
        self.assertTrue(proof["matrix_summary"]["core_ir_executable_audit_bound"])
        self.assertEqual(proof["matrix_summary"]["core_ir_executable_audit_status"], "audited_non_promoting")
        self.assertTrue(proof["matrix_summary"]["parser_kernel_promotion_receipt_bound"])
        self.assertEqual(proof["matrix_summary"]["parser_kernel_promotion_receipt_status"], "blocked_until_phase66")
        self.assertFalse(proof["matrix_summary"]["parser_to_kernel_promotion_allowed"])
        self.assertEqual(proof["summary"]["operation_count"], len(capability_traps.default_operations()) + 2)

    def test_fuzz_operations_bind_into_trap_proof(self) -> None:
        policy = microkernel_isolation.make_isolation_proof()
        fuzz = {
            "status": "pass",
            "summary": {"failed_check_count": 0},
            "operations": [
                {
                    "case_id": "unknown_capability_00",
                    "fuzz_kind": "unknown_capability",
                    "opcode": "ASSERT_REGION_CAP",
                    "region": "fuzz_region",
                    "source": "pgvm_guest",
                    "target": "geometry_kernel",
                    "capability": "unknown_power",
                    "expected_trap": True,
                    "reason": "unit fuzz",
                },
                {
                    "case_id": "unknown_permission_00",
                    "fuzz_kind": "unknown_permission",
                    "opcode": "ASSERT_MATRIX_PERMISSION",
                    "region": "grid.main_grid",
                    "source": "pgvm_guest",
                    "target": "geometry_kernel",
                    "capability": "delete_grid",
                    "matrix_allowed": False,
                    "expected_trap": True,
                    "reason": "unit fuzz",
                },
            ],
        }
        proof = capability_traps.make_capability_trap_proof(policy=policy, trap_fuzz=fuzz)
        self.assertEqual(proof["status"], "pass")
        self.assertTrue(proof["fuzz_summary"]["fuzz_bound"])
        self.assertEqual(proof["fuzz_summary"]["fuzz_operation_count"], 2)
        self.assertEqual(proof["summary"]["operation_count"], len(capability_traps.default_operations()) + 2)


if __name__ == "__main__":
    unittest.main()
