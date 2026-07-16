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

from runtime import boot_log, lab_manifest, qemu_boot_marker_contract, qemu_boot_marker_image_binding, rootfs_content_manifest  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import emit_rootfs_content_manifest, pooleos_release_gate  # noqa: E402


def _write_marker_contract(tmp_path: Path, *, dry_run_status: str = "pass") -> Path:
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
    qemu_boot_marker_contract.write_contract(contract, contract_path)
    return contract_path


def _write_image_binding(tmp_path: Path, *, dry_run_status: str = "pass") -> Path:
    marker_contract = _write_marker_contract(tmp_path, dry_run_status=dry_run_status)
    image_manifest_path = tmp_path / "lab_image_manifest.json"
    image_binding_path = tmp_path / "qemu_boot_marker_image_binding.json"
    lab_manifest.write_lab_manifest(lab_manifest.make_lab_manifest(root=ROOT), image_manifest_path)
    binding = qemu_boot_marker_image_binding.make_qemu_boot_marker_image_binding(
        root=ROOT,
        marker_contract_path=marker_contract,
        lab_image_manifest_path=image_manifest_path,
    )
    qemu_boot_marker_image_binding.write_binding(binding, image_binding_path)
    return image_binding_path


def _copy_bound_files_to_rootfs(image_binding_path: Path, extracted_rootfs: Path) -> None:
    binding = json.loads(image_binding_path.read_text(encoding="utf-8"))
    for source in binding["marker_file_bindings"] + binding["support_file_bindings"]:
        guest_path = source["guest_path"].lstrip("/")
        destination = extracted_rootfs.joinpath(*guest_path.split("/"))
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source["path"], destination)


class RootfsContentManifestTests(unittest.TestCase):
    def test_manifest_blocks_without_image_or_extracted_rootfs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            image_binding = _write_image_binding(tmp_path)
            manifest = rootfs_content_manifest.make_rootfs_content_manifest(
                root=ROOT,
                image_binding_path=image_binding,
                image_path=tmp_path / "missing-rootfs.ext4",
            )
            schema = json.loads((ROOT / "specs" / "rootfs-content-manifest.schema.json").read_text(encoding="utf-8"))
            self.assertEqual(validate_json(manifest, schema), [])
            self.assertEqual(manifest["status"], "blocked")
            self.assertEqual(manifest["summary"]["failed_check_count"], 0)
            self.assertGreater(manifest["summary"]["blocking_check_count"], 0)
            self.assertFalse(manifest["boot_evidence_claimed"])
            self.assertFalse(manifest["security_boundary_claimed"])

    def test_manifest_passes_when_extracted_rootfs_matches_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            image = tmp_path / "rootfs.ext4"
            image.write_text("fake rootfs image", encoding="utf-8")
            extracted = tmp_path / "extracted-rootfs"
            extracted.mkdir()
            image_binding = _write_image_binding(tmp_path)
            _copy_bound_files_to_rootfs(image_binding, extracted)
            manifest = rootfs_content_manifest.make_rootfs_content_manifest(
                root=ROOT,
                image_binding_path=image_binding,
                image_path=image,
                extracted_rootfs_path=extracted,
            )
            self.assertEqual(manifest["status"], "pass")
            self.assertEqual(manifest["summary"]["source_file_count"], 6)
            self.assertEqual(manifest["summary"]["rootfs_file_count"], 6)
            self.assertEqual(manifest["summary"]["matched_source_file_count"], 6)
            self.assertEqual(manifest["summary"]["failed_check_count"], 0)

    def test_manifest_fails_when_extracted_file_hash_mismatches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            image = tmp_path / "rootfs.ext4"
            image.write_text("fake rootfs image", encoding="utf-8")
            extracted = tmp_path / "extracted-rootfs"
            extracted.mkdir()
            image_binding = _write_image_binding(tmp_path)
            _copy_bound_files_to_rootfs(image_binding, extracted)
            (extracted / "usr" / "bin" / "pooleos-lab-doctor").write_text("changed", encoding="utf-8")
            manifest = rootfs_content_manifest.make_rootfs_content_manifest(
                root=ROOT,
                image_binding_path=image_binding,
                image_path=image,
                extracted_rootfs_path=extracted,
            )
            self.assertEqual(manifest["status"], "fail")
            self.assertGreater(manifest["summary"]["failed_check_count"], 0)
            self.assertLess(manifest["summary"]["matched_source_file_count"], manifest["summary"]["source_file_count"])

    def test_cli_writes_valid_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            image = tmp_path / "rootfs.ext4"
            image.write_text("fake rootfs image", encoding="utf-8")
            extracted = tmp_path / "extracted-rootfs"
            extracted.mkdir()
            image_binding = _write_image_binding(tmp_path)
            _copy_bound_files_to_rootfs(image_binding, extracted)
            out = tmp_path / "rootfs_content_manifest.json"
            with redirect_stdout(io.StringIO()):
                code = emit_rootfs_content_manifest.main(
                    [
                        "--image-binding",
                        str(image_binding),
                        "--image",
                        str(image),
                        "--extracted-rootfs",
                        str(extracted),
                        "--out",
                        str(out),
                    ]
                )
            self.assertEqual(code, 0)
            manifest = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(manifest["artifact_kind"], "pooleos.rootfs_content_manifest")
            self.assertEqual(manifest["status"], "pass")

    def test_release_gate_accepts_blocked_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            image_binding = _write_image_binding(tmp_path, dry_run_status="blocked")
            out = tmp_path / "rootfs_content_manifest.json"
            manifest = rootfs_content_manifest.make_rootfs_content_manifest(
                root=ROOT,
                image_binding_path=image_binding,
                image_path=tmp_path / "missing-rootfs.ext4",
            )
            rootfs_content_manifest.write_manifest(manifest, out)
            check = pooleos_release_gate.check_rootfs_content_manifest(out)
            self.assertEqual(check["name"], "rootfs_content_manifest")
            self.assertTrue(check["ok"], check)
            self.assertIn("status=blocked", check["detail"])


if __name__ == "__main__":
    unittest.main()
