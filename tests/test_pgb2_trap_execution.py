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
from runtime import pgb2_trap_execution  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import emit_pgb2_trap_execution  # noqa: E402


class PGB2TrapExecutionTests(unittest.TestCase):
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

    def _encoding_path(self, tmp: str) -> Path:
        proof_path = Path(tmp) / "capability_trap_proof.json"
        encoding_path = Path(tmp) / "pgb2_trap_encoding.json"
        proof_path.write_text(json.dumps(self._proof()), encoding="utf-8")
        encoding = pgb2_trap_encoding.make_pgb2_trap_encoding(trap_proof_path=proof_path)
        pgb2_trap_encoding.write_encoding(encoding, encoding_path)
        return encoding_path

    def test_offset_decoder_walks_concatenated_program(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            encoding = json.loads(self._encoding_path(tmp).read_text(encoding="utf-8"))
            program = bytes.fromhex(encoding["program"]["raw_hex"])
            offset = 0
            decoded_count = 0
            while offset < len(program):
                decoded, offset = pgb2_trap_encoding.decode_instruction_at(program, offset)
                self.assertIn(decoded["opcode"], pgb2_trap_encoding.OPCODE_TABLE)
                decoded_count += 1
            self.assertEqual(decoded_count, encoding["summary"]["instruction_count"])
            self.assertEqual(offset, len(program))

    def test_trap_execution_validates_and_matches_encoding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            encoding_path = self._encoding_path(tmp)
            execution = pgb2_trap_execution.make_pgb2_trap_execution(trap_encoding_path=encoding_path)
            schema = json.loads((ROOT / "specs" / "pgb2-trap-execution.schema.json").read_text(encoding="utf-8"))
            self.assertEqual(validate_json(execution, schema), [])
            self.assertEqual(execution["status"], "pass")
            self.assertEqual(execution["summary"]["failed_check_count"], 0)
            self.assertEqual(
                execution["summary"]["encoded_instruction_count"],
                execution["summary"]["executed_instruction_count"],
            )
            self.assertGreater(execution["summary"]["fuzz_instruction_count"], 0)
            self.assertTrue(all(item["outcome_match"] for item in execution["executed_instructions"]))
            self.assertTrue(execution["program"]["all_bytes_consumed"])
            self.assertEqual(execution["encoding_artifact"]["core_ir_binding_mode"], "metadata_only_non_promoting")
            self.assertTrue(execution["encoding_artifact"]["parser_kernel_promotion_receipt_bound"])
            self.assertEqual(execution["encoding_artifact"]["parser_kernel_promotion_receipt_status"], "blocked_until_phase66")
            self.assertFalse(execution["encoding_artifact"]["parser_to_kernel_promotion_allowed"])

    def test_tampered_program_hash_fails_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            encoding_path = self._encoding_path(tmp)
            encoding = json.loads(encoding_path.read_text(encoding="utf-8"))
            encoding["program"]["sha256"] = "0" * 64
            encoding_path.write_text(json.dumps(encoding), encoding="utf-8")
            execution = pgb2_trap_execution.make_pgb2_trap_execution(trap_encoding_path=encoding_path)
            self.assertEqual(execution["status"], "fail")
            self.assertGreater(execution["summary"]["failed_check_count"], 0)
            self.assertIn("program_hash_matches", [check["name"] for check in execution["checks"] if not check["ok"]])

    def test_cli_writes_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            encoding_path = self._encoding_path(tmp)
            out = Path(tmp) / "pgb2_trap_execution.json"
            with redirect_stdout(io.StringIO()):
                code = emit_pgb2_trap_execution.main(["--trap-encoding", str(encoding_path), "--out", str(out)])
            self.assertEqual(code, 0)
            execution = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(execution["artifact_kind"], "pooleos.pgb2_trap_execution")


if __name__ == "__main__":
    unittest.main()
