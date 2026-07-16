import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORK_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(WORK_ROOT / "PooleGlyph"))

import pooleglyph_pgvm as pg  # noqa: E402
from runtime import capability_trap_fuzz  # noqa: E402
from runtime import capability_traps  # noqa: E402
from runtime import microkernel_isolation  # noqa: E402
from runtime import pgb2_bundle as pgb2  # noqa: E402
from runtime import pgb2_trap_encoding  # noqa: E402
from runtime import pgb2_trap_execution  # noqa: E402
from tools import emit_pgb2_bundle, validate_pgb2_bundle  # noqa: E402


class PGB2BundleTests(unittest.TestCase):
    def _trap_artifact_paths(self, tmp: str) -> tuple[Path, Path]:
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
        proof = capability_traps.make_capability_trap_proof(policy=policy, permission_matrix=matrix, trap_fuzz=fuzz)
        proof_path = Path(tmp) / "capability_trap_proof.json"
        encoding_path = Path(tmp) / "pgb2_trap_encoding.json"
        execution_path = Path(tmp) / "pgb2_trap_execution.json"
        capability_traps.write_proof(proof, proof_path)
        encoding = pgb2_trap_encoding.make_pgb2_trap_encoding(trap_proof_path=proof_path)
        pgb2_trap_encoding.write_encoding(encoding, encoding_path)
        execution = pgb2_trap_execution.make_pgb2_trap_execution(trap_encoding_path=encoding_path)
        pgb2_trap_execution.write_execution(execution, execution_path)
        return encoding_path, execution_path

    def test_emit_pgb2_bundle_cli_writes_valid_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "bundle.pgb2.json"
            with redirect_stdout(io.StringIO()):
                code = emit_pgb2_bundle.main(["--case", "six-support", "--out", str(out)])
            self.assertEqual(code, 0)
            bundle = pgb2.read_bundle(out)
            result = pgb2.validate_bundle(bundle, specs_dir=ROOT / "specs")
            self.assertTrue(result.ok, result.errors)
            code_section = pgb2.section_by_name(bundle, "CODE")
            self.assertEqual(code_section["body"]["encoding"], "PGB1_RAW_HEX")
            self.assertEqual(code_section["body"]["raw_hex"], "10 00 20 06 30 01 36 FF")

    def test_bundle_code_section_runs_on_pgvm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "bundle.pgb2.json"
            with redirect_stdout(io.StringIO()):
                emit_pgb2_bundle.main(["--case", "six-support", "--out", str(out)])
            bundle = pgb2.read_bundle(out)
            raw_hex = pgb2.section_by_name(bundle, "CODE")["body"]["raw_hex"]
            vm = pg.PGVM(pg.six_support_demo_lattice())
            final, report = vm.run(pg.bytes_from_hex(raw_hex), input_mode="raw-stream")
            self.assertTrue(report.halted)
            self.assertIsNone(report.trap)
            self.assertIn((0, 0, 0), final.body)

    def test_validator_rejects_tampered_section_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "bundle.pgb2.json"
            with redirect_stdout(io.StringIO()):
                emit_pgb2_bundle.main(["--case", "rectangle-2x2", "--out", str(out)])
            bundle = pgb2.read_bundle(out)
            pgb2.section_by_name(bundle, "TRACE")["body"]["summary"]["births"] = 999
            tampered = Path(tmp) / "tampered.pgb2.json"
            tampered.write_text(json.dumps(bundle), encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                code = validate_pgb2_bundle.main([str(tampered)])
            self.assertEqual(code, 1)

    def test_bundle_can_include_signed_metrics_section(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "signed_bundle.pgb2.json"
            with redirect_stdout(io.StringIO()):
                code = emit_pgb2_bundle.main([
                    "--case",
                    "six-support",
                    "--include-signed-metrics",
                    "--out",
                    str(out),
                ])
            self.assertEqual(code, 0)
            bundle = pgb2.read_bundle(out)
            result = pgb2.validate_bundle(bundle, specs_dir=ROOT / "specs")
            self.assertTrue(result.ok, result.errors)
            signed = pgb2.section_by_name(bundle, "SIGNED_METRICS")
            self.assertGreater(float(signed["body"]["summary"]["membrane_quality"]), 0.0)

    def test_bundle_can_include_trap_evidence_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            encoding_path, execution_path = self._trap_artifact_paths(tmp)
            out = Path(tmp) / "trap_bundle.pgb2.json"
            with redirect_stdout(io.StringIO()):
                code = emit_pgb2_bundle.main(
                    [
                        "--case",
                        "six-support",
                        "--trap-encoding",
                        str(encoding_path),
                        "--trap-execution",
                        str(execution_path),
                        "--out",
                        str(out),
                    ]
                )
            self.assertEqual(code, 0)
            bundle = pgb2.read_bundle(out)
            result = pgb2.validate_bundle(bundle, specs_dir=ROOT / "specs")
            self.assertTrue(result.ok, result.errors)
            trap_encoding = pgb2.section_by_name(bundle, "TRAP_ENCODING")
            trap_execution = pgb2.section_by_name(bundle, "TRAP_EXECUTION")
            self.assertEqual(trap_encoding["media_type"], pgb2.TRAP_ENCODING_MEDIA_TYPE)
            self.assertEqual(trap_execution["media_type"], pgb2.TRAP_EXECUTION_MEDIA_TYPE)
            self.assertEqual(
                trap_encoding["body"]["program"]["sha256"],
                trap_execution["body"]["program"]["sha256"],
            )

    def test_validator_rejects_mismatched_trap_evidence_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            encoding_path, execution_path = self._trap_artifact_paths(tmp)
            out = Path(tmp) / "trap_bundle.pgb2.json"
            with redirect_stdout(io.StringIO()):
                emit_pgb2_bundle.main(
                    [
                        "--case",
                        "six-support",
                        "--trap-encoding",
                        str(encoding_path),
                        "--trap-execution",
                        str(execution_path),
                        "--out",
                        str(out),
                    ]
                )
            bundle = pgb2.read_bundle(out)
            execution = pgb2.section_by_name(bundle, "TRAP_EXECUTION")
            execution["body"]["encoding_artifact"]["sha256"] = "0" * 64
            execution["sha256"] = pgb2.body_hash(execution["body"])
            result = pgb2.validate_bundle(bundle, specs_dir=ROOT / "specs")
            self.assertFalse(result.ok)
            self.assertTrue(any("TRAP_EVIDENCE" in error for error in result.errors), result.errors)


if __name__ == "__main__":
    unittest.main()
