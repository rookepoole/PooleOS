import io
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import boot_trap_bundle_manifest  # noqa: E402
from runtime import pgb2_trap_abi_boundary_receipt  # noqa: E402
from runtime import qemu_shared_folder_contract  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import emit_boot_trap_bundle_manifest  # noqa: E402
from tools import emit_capability_trap_fuzz  # noqa: E402
from tools import emit_capability_trap_proof  # noqa: E402
from tools import emit_isolation_proof  # noqa: E402
from tools import emit_pgb2_bundle  # noqa: E402
from tools import emit_pgb2_trap_encoding  # noqa: E402
from tools import emit_pgb2_trap_execution  # noqa: E402
from tools import emit_replay_proof  # noqa: E402
from tools import pooleos_lab_verify_input  # noqa: E402


class BootTrapBundleManifestTests(unittest.TestCase):
    def _trap_bundle_paths(self, tmp: str) -> tuple[Path, Path, Path]:
        tmp_path = Path(tmp)
        isolation = tmp_path / "microkernel_isolation.json"
        matrix = tmp_path / "permission_capability_matrix.json"
        fuzz = tmp_path / "capability_trap_fuzz.json"
        proof = tmp_path / "capability_trap_proof.json"
        encoding = tmp_path / "pgb2_trap_encoding.json"
        execution = tmp_path / "pgb2_trap_execution.json"
        bundle = tmp_path / "signed_trap_evidence.pgb2.json"
        replay = tmp_path / "signed_trap_evidence.replay.json"
        with redirect_stdout(io.StringIO()):
            self.assertEqual(emit_isolation_proof.main(["--out", str(isolation)]), 0)
            matrix.write_text(
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
            self.assertEqual(
                emit_capability_trap_fuzz.main(
                    ["--isolation-proof", str(isolation), "--permission-capability-matrix", str(matrix), "--out", str(fuzz)]
                ),
                0,
            )
            self.assertEqual(
                emit_capability_trap_proof.main(
                    [
                        "--isolation-proof",
                        str(isolation),
                        "--permission-capability-matrix",
                        str(matrix),
                        "--capability-trap-fuzz",
                        str(fuzz),
                        "--out",
                        str(proof),
                    ]
                ),
                0,
            )
            self.assertEqual(emit_pgb2_trap_encoding.main(["--trap-proof", str(proof), "--out", str(encoding)]), 0)
            self.assertEqual(
                emit_pgb2_trap_execution.main(["--trap-encoding", str(encoding), "--out", str(execution)]),
                0,
            )
            self.assertEqual(
                emit_pgb2_bundle.main(
                    [
                        "--case",
                        "six-support",
                        "--include-signed-metrics",
                        "--trap-encoding",
                        str(encoding),
                        "--trap-execution",
                        str(execution),
                        "--out",
                        str(bundle),
                    ]
                ),
                0,
            )
            self.assertEqual(
                emit_replay_proof.main(["--bundle", str(bundle), "--case", "six-support", "--out", str(replay)]),
                0,
            )
        return bundle, replay, execution

    def test_manifest_validates_for_trap_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle, replay, execution = self._trap_bundle_paths(tmp)
            manifest = boot_trap_bundle_manifest.make_boot_trap_bundle_manifest(
                bundle_path=bundle,
                replay_proof_path=replay,
                trap_execution_path=execution,
                specs_dir=ROOT / "specs",
            )
            schema = json.loads((ROOT / "specs" / "boot-trap-bundle-manifest.schema.json").read_text(encoding="utf-8"))
            self.assertEqual(validate_json(manifest, schema), [])
            self.assertEqual(manifest["status"], "pass")
            self.assertTrue(manifest["summary"]["trap_evidence_present"])
            self.assertGreater(manifest["summary"]["expected_executed_instruction_count"], 0)
            self.assertTrue(manifest["bundle"]["target_path"].endswith("/input.pgb2.json"))

    def test_cli_manifest_and_mounted_verifier_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bundle, replay, execution = self._trap_bundle_paths(tmp)
            mount_dir = tmp_path / "mnt"
            mount_dir.mkdir()
            manifest_path = mount_dir / boot_trap_bundle_manifest.DEFAULT_MANIFEST_NAME
            result_path = tmp_path / "boot_trap_bundle_verification.json"
            with redirect_stdout(io.StringIO()):
                code = emit_boot_trap_bundle_manifest.main(
                    [
                        "--bundle",
                        str(bundle),
                        "--replay-proof",
                        str(replay),
                        "--trap-execution",
                        str(execution),
                        "--mount-dir",
                        str(mount_dir),
                        "--out",
                        str(manifest_path),
                    ]
                )
            self.assertEqual(code, 0)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            shutil.copyfile(bundle, Path(manifest["bundle"]["target_path"]))
            shutil.copyfile(replay, Path(manifest["replay_proof"]["target_path"]))
            with redirect_stdout(io.StringIO()):
                verify_code = pooleos_lab_verify_input.main(["--manifest", str(manifest_path), "--out", str(result_path)])
            self.assertEqual(verify_code, 0)
            verification = json.loads(result_path.read_text(encoding="utf-8"))
            self.assertEqual(verification["status"], "pass")
            self.assertEqual(verification["summary"]["failed_check_count"], 0)

    def test_mounted_verifier_accepts_non_promoting_abi_boundary_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bundle, replay, execution = self._trap_bundle_paths(tmp)
            encoding = tmp_path / "pgb2_trap_encoding.json"
            mount_dir = tmp_path / "mnt"
            mount_dir.mkdir()
            manifest_path = mount_dir / boot_trap_bundle_manifest.DEFAULT_MANIFEST_NAME
            result_path = tmp_path / "boot_trap_bundle_verification.json"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(
                    emit_boot_trap_bundle_manifest.main(
                        [
                            "--bundle",
                            str(bundle),
                            "--replay-proof",
                            str(replay),
                            "--trap-execution",
                            str(execution),
                            "--mount-dir",
                            str(mount_dir),
                            "--out",
                            str(manifest_path),
                        ]
                    ),
                    0,
                )
            base_contract_path = tmp_path / "qemu_shared_folder_contract.base.json"
            base_contract = qemu_shared_folder_contract.make_qemu_shared_folder_contract(
                shared_dir=tmp_path / "shared_base",
                bundle_path=bundle,
                replay_proof_path=replay,
                boot_trap_manifest_path=manifest_path,
                specs_dir=ROOT / "specs",
            )
            qemu_shared_folder_contract.write_contract(base_contract, base_contract_path)
            receipt = pgb2_trap_abi_boundary_receipt.make_pgb2_trap_abi_boundary_receipt(
                trap_encoding_path=encoding,
                trap_execution_path=execution,
                bundle_path=bundle,
                boot_trap_bundle_manifest_path=manifest_path,
                qemu_shared_folder_contract_path=base_contract_path,
                specs_dir=ROOT / "specs",
            )
            pgb2_trap_abi_boundary_receipt.write_receipt(
                receipt,
                mount_dir / boot_trap_bundle_manifest.DEFAULT_ABI_BOUNDARY_RECEIPT_NAME,
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            shutil.copyfile(bundle, Path(manifest["bundle"]["target_path"]))
            shutil.copyfile(replay, Path(manifest["replay_proof"]["target_path"]))
            with redirect_stdout(io.StringIO()):
                verify_code = pooleos_lab_verify_input.main(["--manifest", str(manifest_path), "--out", str(result_path)])
            self.assertEqual(verify_code, 0)
            verification = json.loads(result_path.read_text(encoding="utf-8"))
            self.assertEqual(verification["status"], "pass")
            self.assertTrue(verification["summary"]["abi_boundary_receipt_present"])
            self.assertTrue(verification["summary"]["abi_boundary_receipt_verified"])

    def test_mounted_verifier_rejects_tampered_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bundle, replay, execution = self._trap_bundle_paths(tmp)
            mount_dir = tmp_path / "mnt"
            mount_dir.mkdir()
            manifest_path = mount_dir / boot_trap_bundle_manifest.DEFAULT_MANIFEST_NAME
            result_path = tmp_path / "boot_trap_bundle_verification.json"
            with redirect_stdout(io.StringIO()):
                emit_boot_trap_bundle_manifest.main(
                    [
                        "--bundle",
                        str(bundle),
                        "--replay-proof",
                        str(replay),
                        "--trap-execution",
                        str(execution),
                        "--mount-dir",
                        str(mount_dir),
                        "--out",
                        str(manifest_path),
                    ]
                )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            shutil.copyfile(bundle, Path(manifest["bundle"]["target_path"]))
            shutil.copyfile(replay, Path(manifest["replay_proof"]["target_path"]))
            mounted_bundle = Path(manifest["bundle"]["target_path"])
            mounted_bundle.write_text(mounted_bundle.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                verify_code = pooleos_lab_verify_input.main(["--manifest", str(manifest_path), "--out", str(result_path)])
            self.assertEqual(verify_code, 1)
            verification = json.loads(result_path.read_text(encoding="utf-8"))
            self.assertEqual(verification["status"], "fail")
            failed = [check["name"] for check in verification["checks"] if not check["ok"]]
            self.assertIn("bundle_hash_matches", failed)


if __name__ == "__main__":
    unittest.main()
