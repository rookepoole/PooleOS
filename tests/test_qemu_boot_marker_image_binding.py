import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import boot_log, lab_manifest, qemu_boot_marker_contract, qemu_boot_marker_image_binding  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import emit_qemu_boot_marker_image_binding, pooleos_release_gate  # noqa: E402


def _write_marker_contract(tmp_path: Path, *, dry_run_status: str = "pass", missing_source: bool = False) -> Path:
    markers = boot_log.required_markers_for_profile("trap-input")
    dry_run_path = tmp_path / "qemu_captured_boot_dry_run_checklist.json"
    autostart_path = tmp_path / "lab_guest_autostart.json"
    contract_path = tmp_path / "qemu_boot_marker_contract.json"
    dry_run_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "artifact_kind": "pooleos.qemu_captured_boot_dry_run_checklist",
                "status": dry_run_status,
                "launch_ready": dry_run_status == "pass",
                "execution_performed": False,
                "expected_serial_markers": markers,
                "post_capture_files": [
                    {"role": "serial_log", "path": str(tmp_path / "pooleos-lab-serial.log")},
                    {"role": "boot_validation", "path": str(tmp_path / "boot_log_validation.captured.json")},
                    {"role": "captured_boot_evidence", "path": str(tmp_path / "qemu_boot_evidence.captured.json")},
                    {"role": "captured_boot_receipt", "path": str(tmp_path / "qemu_captured_boot_receipt.json")},
                    {"role": "release_gate", "path": str(tmp_path / "release_gate.json")},
                ],
                "summary": {
                    "failed_check_count": 0,
                    "blocking_check_count": 1 if dry_run_status == "blocked" else 0,
                },
            }
        ),
        encoding="utf-8",
    )
    autostart_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "artifact_kind": "pooleos.lab_guest_autostart",
                "status": "pass",
                "boot_evidence_claimed": False,
                "boot_log_profile": {
                    "profile": "trap-input",
                    "required_markers": markers,
                },
                "summary": {
                    "failed_check_count": 0,
                    "required_marker_count": len(markers),
                },
            }
        ),
        encoding="utf-8",
    )
    contract = qemu_boot_marker_contract.make_qemu_boot_marker_contract(
        root=ROOT,
        dry_run_checklist_path=dry_run_path,
        lab_guest_autostart_path=autostart_path,
    )
    if missing_source:
        contract["marker_mappings"][0]["source_file"] = str(tmp_path / "missing-marker-source")
    qemu_boot_marker_contract.write_contract(contract, contract_path)
    return contract_path


def _write_lab_manifest(tmp_path: Path) -> Path:
    manifest_path = tmp_path / "lab_image_manifest.json"
    lab_manifest.write_lab_manifest(lab_manifest.make_lab_manifest(root=ROOT), manifest_path)
    return manifest_path


class QemuBootMarkerImageBindingTests(unittest.TestCase):
    def test_binding_passes_with_ready_marker_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            marker_contract = _write_marker_contract(tmp_path)
            image_manifest = _write_lab_manifest(tmp_path)
            binding = qemu_boot_marker_image_binding.make_qemu_boot_marker_image_binding(
                root=ROOT,
                marker_contract_path=marker_contract,
                lab_image_manifest_path=image_manifest,
            )
            schema = json.loads((ROOT / "specs" / "qemu-boot-marker-image-binding.schema.json").read_text(encoding="utf-8"))
            self.assertEqual(validate_json(binding, schema), [])
            self.assertEqual(binding["status"], "pass")
            self.assertFalse(binding["execution_performed"])
            self.assertFalse(binding["boot_evidence_claimed"])
            self.assertFalse(binding["security_boundary_claimed"])
            self.assertEqual(binding["summary"]["marker_count"], len(boot_log.required_markers_for_profile("trap-input")))
            self.assertGreaterEqual(binding["summary"]["marker_source_file_count"], 2)
            self.assertEqual(binding["summary"]["support_file_count"], 4)
            self.assertEqual(binding["summary"]["buildroot_manifest_file_count"], 5)
            self.assertGreaterEqual(binding["summary"]["hashed_file_count"], 11)
            bound_markers = {
                marker
                for file_binding in binding["marker_file_bindings"]
                for marker in file_binding["markers"]
            }
            self.assertIn("POOLEOS_LAB_TRAP_ABI_BOUNDARY_PASS", bound_markers)

    def test_binding_blocks_when_marker_contract_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            marker_contract = _write_marker_contract(tmp_path, dry_run_status="blocked")
            image_manifest = _write_lab_manifest(tmp_path)
            binding = qemu_boot_marker_image_binding.make_qemu_boot_marker_image_binding(
                root=ROOT,
                marker_contract_path=marker_contract,
                lab_image_manifest_path=image_manifest,
            )
            self.assertEqual(binding["status"], "blocked")
            self.assertEqual(binding["summary"]["failed_check_count"], 0)
            self.assertGreater(binding["summary"]["blocking_check_count"], 0)

    def test_binding_fails_when_marker_source_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            marker_contract = _write_marker_contract(tmp_path, missing_source=True)
            image_manifest = _write_lab_manifest(tmp_path)
            binding = qemu_boot_marker_image_binding.make_qemu_boot_marker_image_binding(
                root=ROOT,
                marker_contract_path=marker_contract,
                lab_image_manifest_path=image_manifest,
            )
            self.assertEqual(binding["status"], "fail")
            self.assertGreater(binding["summary"]["failed_check_count"], 0)

    def test_cli_writes_valid_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            marker_contract = _write_marker_contract(tmp_path)
            image_manifest = _write_lab_manifest(tmp_path)
            out = tmp_path / "qemu_boot_marker_image_binding.json"
            with redirect_stdout(io.StringIO()):
                code = emit_qemu_boot_marker_image_binding.main(
                    [
                        "--marker-contract",
                        str(marker_contract),
                        "--lab-image-manifest",
                        str(image_manifest),
                        "--out",
                        str(out),
                    ]
                )
            self.assertEqual(code, 0)
            binding = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(binding["artifact_kind"], "pooleos.qemu_boot_marker_image_binding")
            self.assertEqual(binding["status"], "pass")

    def test_release_gate_accepts_blocked_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            marker_contract = _write_marker_contract(tmp_path, dry_run_status="blocked")
            image_manifest = _write_lab_manifest(tmp_path)
            out = tmp_path / "qemu_boot_marker_image_binding.json"
            binding = qemu_boot_marker_image_binding.make_qemu_boot_marker_image_binding(
                root=ROOT,
                marker_contract_path=marker_contract,
                lab_image_manifest_path=image_manifest,
            )
            qemu_boot_marker_image_binding.write_binding(binding, out)
            check = pooleos_release_gate.check_qemu_boot_marker_image_binding(out)
            self.assertEqual(check["name"], "qemu_boot_marker_image_binding")
            self.assertTrue(check["ok"], check)
            self.assertIn("status=blocked", check["detail"])


if __name__ == "__main__":
    unittest.main()
