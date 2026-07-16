import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import capability_trap_fuzz  # noqa: E402
from runtime import capability_traps  # noqa: E402
from runtime import microkernel_isolation  # noqa: E402
from runtime import pgb2_trap_encoding  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import emit_pgb2_trap_encoding  # noqa: E402


class PGB2TrapEncodingTests(unittest.TestCase):
    def _proof(self) -> dict:
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
                }
            ],
        }
        fuzz = capability_trap_fuzz.make_capability_trap_fuzz(
            policy=policy,
            permission_matrix={"status": "pass", "summary": {"failed_check_count": 0}, "resources": [{"id": "grid.main_grid"}]},
            unknown_capability_count=2,
            unknown_permission_count=1,
        )
        return capability_traps.make_capability_trap_proof(policy=policy, permission_matrix=matrix, trap_fuzz=fuzz)

    def test_operation_roundtrip_preserves_trap_metadata(self) -> None:
        operation = {
            "opcode": "ASSERT_REGION_CAP",
            "region": "claim_lane_store",
            "source": "pgvm_guest",
            "target": "provenance_service",
            "capability": "write_claim_lane",
            "expected_trap": True,
            "trap_code": "CAPABILITY_DENIED",
        }
        encoded = pgb2_trap_encoding.encode_operation(operation)
        decoded = pgb2_trap_encoding.decode_instruction(encoded)
        self.assertEqual(decoded["opcode"], operation["opcode"])
        self.assertEqual(decoded["region"], operation["region"])
        self.assertEqual(decoded["expected_trap"], operation["expected_trap"])
        self.assertEqual(decoded["trap_code"], operation["trap_code"])

    def test_trap_encoding_validates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proof_path = Path(tmp) / "capability_trap_proof.json"
            proof_path.write_text(json.dumps(self._proof()), encoding="utf-8")
            encoding = pgb2_trap_encoding.make_pgb2_trap_encoding(trap_proof_path=proof_path)
            schema = json.loads((ROOT / "specs" / "pgb2-trap-encoding.schema.json").read_text(encoding="utf-8"))
            self.assertEqual(validate_json(encoding, schema), [])
            self.assertEqual(encoding["status"], "pass")
            self.assertEqual(encoding["summary"]["failed_check_count"], 0)
            self.assertEqual(encoding["summary"]["source_operation_count"], encoding["summary"]["instruction_count"])
            self.assertGreater(encoding["summary"]["fuzz_instruction_count"], 0)
            self.assertGreater(encoding["program"]["byte_length"], 0)
            self.assertEqual(encoding["source_trap_proof"]["core_ir_binding_mode"], "metadata_only_non_promoting")
            self.assertTrue(encoding["source_trap_proof"]["core_ir_executable_audit_bound"])
            self.assertEqual(encoding["source_trap_proof"]["core_ir_executable_audit_status"], "audited_non_promoting")
            self.assertTrue(encoding["source_trap_proof"]["parser_kernel_promotion_receipt_bound"])
            self.assertEqual(encoding["source_trap_proof"]["parser_kernel_promotion_receipt_status"], "blocked_until_phase66")
            self.assertFalse(encoding["source_trap_proof"]["parser_to_kernel_promotion_allowed"])

    def test_cli_writes_encoding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proof_path = Path(tmp) / "capability_trap_proof.json"
            out = Path(tmp) / "pgb2_trap_encoding.json"
            proof_path.write_text(json.dumps(self._proof()), encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                code = emit_pgb2_trap_encoding.main(["--trap-proof", str(proof_path), "--out", str(out)])
            self.assertEqual(code, 0)
            encoding = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(encoding["artifact_kind"], "pooleos.pgb2_trap_encoding")


if __name__ == "__main__":
    unittest.main()
