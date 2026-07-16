import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import pgb2_trap_abi_boundary_receipt  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import emit_boot_trap_bundle_manifest  # noqa: E402
from tools import emit_capability_trap_fuzz  # noqa: E402
from tools import emit_capability_trap_proof  # noqa: E402
from tools import emit_isolation_proof  # noqa: E402
from tools import emit_pgb2_bundle  # noqa: E402
from tools import emit_pgb2_trap_abi_boundary_receipt  # noqa: E402
from tools import emit_pgb2_trap_encoding  # noqa: E402
from tools import emit_pgb2_trap_execution  # noqa: E402
from tools import emit_replay_proof  # noqa: E402
from tools import pooleos_qemu_prepare_inputs  # noqa: E402
from tools import pooleos_release_gate  # noqa: E402


class PGB2TrapAbiBoundaryReceiptTests(unittest.TestCase):
    def _artifact_paths(self, tmp: str) -> dict[str, Path]:
        tmp_path = Path(tmp)
        paths = {
            "isolation": tmp_path / "microkernel_isolation.json",
            "matrix": tmp_path / "permission_capability_matrix.json",
            "fuzz": tmp_path / "capability_trap_fuzz.json",
            "proof": tmp_path / "capability_trap_proof.json",
            "encoding": tmp_path / "pgb2_trap_encoding.json",
            "execution": tmp_path / "pgb2_trap_execution.json",
            "bundle": tmp_path / "signed_trap_evidence.pgb2.json",
            "replay": tmp_path / "signed_trap_evidence.replay.json",
            "boot_manifest": tmp_path / "pooleos_boot_trap_bundle_manifest.json",
            "qemu_contract": tmp_path / "qemu_shared_folder_contract.json",
        }
        paths["matrix"].write_text(
            json.dumps(
                {
                    "status": "pass",
                    "resources": [{"id": "grid.main_grid"}],
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
            ),
            encoding="utf-8",
        )
        with redirect_stdout(io.StringIO()):
            self.assertEqual(emit_isolation_proof.main(["--out", str(paths["isolation"])]), 0)
            self.assertEqual(
                emit_capability_trap_fuzz.main(
                    [
                        "--isolation-proof",
                        str(paths["isolation"]),
                        "--permission-capability-matrix",
                        str(paths["matrix"]),
                        "--out",
                        str(paths["fuzz"]),
                    ]
                ),
                0,
            )
            self.assertEqual(
                emit_capability_trap_proof.main(
                    [
                        "--isolation-proof",
                        str(paths["isolation"]),
                        "--permission-capability-matrix",
                        str(paths["matrix"]),
                        "--capability-trap-fuzz",
                        str(paths["fuzz"]),
                        "--out",
                        str(paths["proof"]),
                    ]
                ),
                0,
            )
            self.assertEqual(emit_pgb2_trap_encoding.main(["--trap-proof", str(paths["proof"]), "--out", str(paths["encoding"])]), 0)
            self.assertEqual(
                emit_pgb2_trap_execution.main(["--trap-encoding", str(paths["encoding"]), "--out", str(paths["execution"])]),
                0,
            )
            self.assertEqual(
                emit_pgb2_bundle.main(
                    [
                        "--case",
                        "six-support",
                        "--include-signed-metrics",
                        "--trap-encoding",
                        str(paths["encoding"]),
                        "--trap-execution",
                        str(paths["execution"]),
                        "--out",
                        str(paths["bundle"]),
                    ]
                ),
                0,
            )
            self.assertEqual(emit_replay_proof.main(["--bundle", str(paths["bundle"]), "--case", "six-support", "--out", str(paths["replay"])]), 0)
            self.assertEqual(
                emit_boot_trap_bundle_manifest.main(
                    [
                        "--bundle",
                        str(paths["bundle"]),
                        "--replay-proof",
                        str(paths["replay"]),
                        "--trap-execution",
                        str(paths["execution"]),
                        "--out",
                        str(paths["boot_manifest"]),
                    ]
                ),
                0,
            )
            self.assertEqual(
                pooleos_qemu_prepare_inputs.main(
                    [
                        "--shared-dir",
                        str(tmp_path / "shared"),
                        "--bundle",
                        str(paths["bundle"]),
                        "--replay-proof",
                        str(paths["replay"]),
                        "--boot-trap-bundle-manifest",
                        str(paths["boot_manifest"]),
                        "--out",
                        str(paths["qemu_contract"]),
                    ]
                ),
                0,
            )
        return paths

    def _receipt(self, paths: dict[str, Path]) -> dict:
        return pgb2_trap_abi_boundary_receipt.make_pgb2_trap_abi_boundary_receipt(
            trap_encoding_path=paths["encoding"],
            trap_execution_path=paths["execution"],
            bundle_path=paths["bundle"],
            boot_trap_bundle_manifest_path=paths["boot_manifest"],
            qemu_shared_folder_contract_path=paths["qemu_contract"],
            specs_dir=ROOT / "specs",
        )

    def test_draft_receipt_validates_and_blocks_kernel_abi_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._artifact_paths(tmp)
            receipt_path = Path(tmp) / "pgb2_trap_abi_boundary_receipt.json"
            receipt = self._receipt(paths)
            schema = json.loads((ROOT / "specs" / "pgb2-trap-abi-boundary-receipt.schema.json").read_text(encoding="utf-8"))
            self.assertEqual(validate_json(receipt, schema), [])
            self.assertEqual(receipt["status"], "draft_verified")
            self.assertFalse(receipt["abi_boundary"]["abi_frozen"])
            self.assertFalse(receipt["abi_boundary"]["kernel_abi_promotion_allowed"])
            self.assertFalse(receipt["abi_boundary"]["kernel_enforcement_claimed"])
            self.assertEqual(receipt["summary"]["failed_check_count"], 0)
            pgb2_trap_abi_boundary_receipt.write_receipt(receipt, receipt_path)
            self.assertTrue(pooleos_release_gate.check_pgb2_trap_abi_boundary_receipt(receipt_path)["ok"])

    def test_execution_overclaim_fails_receipt_and_release_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._artifact_paths(tmp)
            execution = json.loads(paths["execution"].read_text(encoding="utf-8"))
            execution["security_boundary_claimed"] = True
            paths["execution"].write_text(json.dumps(execution), encoding="utf-8")
            receipt_path = Path(tmp) / "pgb2_trap_abi_boundary_receipt.json"
            receipt = self._receipt(paths)
            pgb2_trap_abi_boundary_receipt.write_receipt(receipt, receipt_path)
            self.assertEqual(receipt["status"], "verification_failed")
            self.assertGreater(receipt["claim_boundaries"]["source_overclaim_count"], 0)
            self.assertFalse(pooleos_release_gate.check_pgb2_trap_abi_boundary_receipt(receipt_path)["ok"])

    def test_cli_writes_draft_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._artifact_paths(tmp)
            out = Path(tmp) / "pgb2_trap_abi_boundary_receipt.json"
            with redirect_stdout(io.StringIO()):
                code = emit_pgb2_trap_abi_boundary_receipt.main(
                    [
                        "--trap-encoding",
                        str(paths["encoding"]),
                        "--trap-execution",
                        str(paths["execution"]),
                        "--bundle",
                        str(paths["bundle"]),
                        "--boot-trap-bundle-manifest",
                        str(paths["boot_manifest"]),
                        "--qemu-shared-folder-contract",
                        str(paths["qemu_contract"]),
                        "--out",
                        str(out),
                    ]
                )
            self.assertEqual(code, 0)
            receipt = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(receipt["artifact_kind"], "pooleos.pgb2_trap_abi_boundary_receipt")
            self.assertEqual(receipt["status"], "draft_verified")


if __name__ == "__main__":
    unittest.main()
