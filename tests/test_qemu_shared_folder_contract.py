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
from tools import pooleos_qemu_prepare_inputs  # noqa: E402


class QemuSharedFolderContractTests(unittest.TestCase):
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
            "manifest": tmp_path / "pooleos_boot_trap_bundle_manifest.json",
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
            self.assertEqual(emit_pgb2_trap_execution.main(["--trap-encoding", str(paths["encoding"]), "--out", str(paths["execution"])]), 0)
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
            self.assertEqual(
                emit_replay_proof.main(["--bundle", str(paths["bundle"]), "--case", "six-support", "--out", str(paths["replay"])]),
                0,
            )
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
                        str(paths["manifest"]),
                    ]
                ),
                0,
            )
        return paths

    def test_qemu_shared_folder_contract_stages_expected_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._artifact_paths(tmp)
            shared = Path(tmp) / "shared"
            contract = qemu_shared_folder_contract.make_qemu_shared_folder_contract(
                shared_dir=shared,
                bundle_path=paths["bundle"],
                replay_proof_path=paths["replay"],
                boot_trap_manifest_path=paths["manifest"],
                specs_dir=ROOT / "specs",
            )
            schema = json.loads((ROOT / "specs" / "qemu-shared-folder-contract.schema.json").read_text(encoding="utf-8"))
            self.assertEqual(validate_json(contract, schema), [])
            self.assertEqual(contract["status"], "pass")
            self.assertTrue((shared / boot_trap_bundle_manifest.DEFAULT_BUNDLE_NAME).is_file())
            self.assertTrue((shared / boot_trap_bundle_manifest.DEFAULT_REPLAY_NAME).is_file())
            self.assertTrue((shared / boot_trap_bundle_manifest.DEFAULT_MANIFEST_NAME).is_file())
            self.assertIn("-virtfs", contract["shared_folder"]["qemu_args"])
            self.assertEqual(contract["summary"]["staged_file_count"], 3)

    def test_qemu_shared_folder_contract_stages_abi_boundary_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._artifact_paths(tmp)
            tmp_path = Path(tmp)
            base_contract_path = tmp_path / "qemu_shared_folder_contract.base.json"
            receipt_path = tmp_path / "pgb2_trap_abi_boundary_receipt.json"
            base_contract = qemu_shared_folder_contract.make_qemu_shared_folder_contract(
                shared_dir=tmp_path / "shared_base",
                bundle_path=paths["bundle"],
                replay_proof_path=paths["replay"],
                boot_trap_manifest_path=paths["manifest"],
                specs_dir=ROOT / "specs",
            )
            qemu_shared_folder_contract.write_contract(base_contract, base_contract_path)
            receipt = pgb2_trap_abi_boundary_receipt.make_pgb2_trap_abi_boundary_receipt(
                trap_encoding_path=paths["encoding"],
                trap_execution_path=paths["execution"],
                bundle_path=paths["bundle"],
                boot_trap_bundle_manifest_path=paths["manifest"],
                qemu_shared_folder_contract_path=base_contract_path,
                specs_dir=ROOT / "specs",
            )
            pgb2_trap_abi_boundary_receipt.write_receipt(receipt, receipt_path)
            shared = tmp_path / "shared"
            contract = qemu_shared_folder_contract.make_qemu_shared_folder_contract(
                shared_dir=shared,
                bundle_path=paths["bundle"],
                replay_proof_path=paths["replay"],
                boot_trap_manifest_path=paths["manifest"],
                trap_abi_boundary_receipt_path=receipt_path,
                specs_dir=ROOT / "specs",
            )
            schema = json.loads((ROOT / "specs" / "qemu-shared-folder-contract.schema.json").read_text(encoding="utf-8"))
            self.assertEqual(validate_json(contract, schema), [])
            self.assertEqual(contract["status"], "pass")
            self.assertEqual(contract["summary"]["staged_file_count"], 4)
            self.assertTrue(contract["summary"]["abi_boundary_receipt_staged"])
            self.assertTrue((shared / boot_trap_bundle_manifest.DEFAULT_ABI_BOUNDARY_RECEIPT_NAME).is_file())
            self.assertIn("pgb2_trap_abi_boundary_receipt", {item["role"] for item in contract["staged_files"]})

    def test_cli_writes_contract_and_copies_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._artifact_paths(tmp)
            shared = Path(tmp) / "shared"
            out = Path(tmp) / "qemu_shared_folder_contract.json"
            with redirect_stdout(io.StringIO()):
                code = pooleos_qemu_prepare_inputs.main(
                    [
                        "--shared-dir",
                        str(shared),
                        "--bundle",
                        str(paths["bundle"]),
                        "--replay-proof",
                        str(paths["replay"]),
                        "--boot-trap-bundle-manifest",
                        str(paths["manifest"]),
                        "--out",
                        str(out),
                    ]
                )
            self.assertEqual(code, 0)
            contract = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(contract["artifact_kind"], "pooleos.qemu_shared_folder_contract")
            self.assertEqual(contract["status"], "pass")
            self.assertEqual(len(contract["staged_files"]), 3)

    def test_contract_rejects_stale_manifest_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._artifact_paths(tmp)
            stale_bundle = Path(tmp) / "stale_bundle.pgb2.json"
            shutil.copyfile(paths["bundle"], stale_bundle)
            stale_bundle.write_text(stale_bundle.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            contract = qemu_shared_folder_contract.make_qemu_shared_folder_contract(
                shared_dir=Path(tmp) / "shared",
                bundle_path=stale_bundle,
                replay_proof_path=paths["replay"],
                boot_trap_manifest_path=paths["manifest"],
                specs_dir=ROOT / "specs",
            )
            self.assertEqual(contract["status"], "fail")
            failed = [check["name"] for check in contract["checks"] if not check["ok"]]
            self.assertIn("staged_bundle_hash_matches", failed)

    def test_qemu_launcher_contains_prepare_inputs_contract(self) -> None:
        script = (ROOT / "lab-os" / "qemu" / "scripts" / "run-pooleos-lab.ps1").read_text(encoding="utf-8")
        self.assertIn("PrepareInputsOnly", script)
        self.assertIn("pooleos_qemu_prepare_inputs.py", script)
        self.assertIn("TrapBundlePath", script)
        self.assertIn("Pgb2TrapAbiBoundaryReceiptPath", script)
        self.assertIn("-virtfs", script)

    def test_qemu_launcher_contains_captured_boot_evidence_contract(self) -> None:
        script = (ROOT / "lab-os" / "qemu" / "scripts" / "run-pooleos-lab.ps1").read_text(encoding="utf-8")
        self.assertIn("EmitCapturedEvidenceOnly", script)
        self.assertIn("SkipBootEvidence", script)
        self.assertIn("BootValidationOutput", script)
        self.assertIn("QemuBootEvidenceOutput", script)
        self.assertIn("validate_boot_log.py", script)
        self.assertIn("emit_qemu_boot_evidence.py", script)
        self.assertIn("captured_qemu_serial", script)
        self.assertIn("qemu_boot_evidence.captured.json", script)
        self.assertIn("-serial", script)
        self.assertIn("file:$SerialLog", script)


if __name__ == "__main__":
    unittest.main()
