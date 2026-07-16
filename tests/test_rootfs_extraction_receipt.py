import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import rootfs_extraction_receipt  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import emit_rootfs_extraction_receipt, pooleos_release_gate  # noqa: E402


def _write_handoff(tmp_path: Path, *, status: str = "pass", failed: int = 0) -> Path:
    path = tmp_path / "rootfs_extraction_handoff.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "artifact_kind": "pooleos.rootfs_extraction_handoff",
                "status": status,
                "execution_performed": False,
                "codex_execution_allowed": False,
                "rootfs_extraction_performed": False,
                "bash_script": "sudo mount -o ro,loop rootfs.ext4 mnt\npython3 tools/emit_rootfs_content_manifest.py\n",
                "bash_script_sha256": "b" * 64,
                "operator_receipt_template": {
                    "operator_executed": False,
                    "codex_execution_performed": False,
                },
                "summary": {
                    "failed_check_count": failed,
                    "blocking_check_count": 0 if status == "pass" else 1,
                    "command_count": 7,
                    "source_manifest_status": "blocked",
                    "source_manifest_failed_check_count": 0,
                    "source_file_count": 5,
                    "rootfs_image_exists": status == "pass",
                    "extracted_rootfs_exists": False,
                    "bash_script_sha256": "b" * 64,
                    "operator_executed": False,
                    "execution_performed": False,
                    "rootfs_extraction_performed": False,
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_rootfs_manifest(tmp_path: Path, *, status: str = "blocked", failed: int = 0, matched: int = 0, extracted: bool = False) -> Path:
    path = tmp_path / "rootfs_content_manifest.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "artifact_kind": "pooleos.rootfs_content_manifest",
                "status": status,
                "execution_performed": False,
                "rootfs_extraction_performed": False,
                "boot_evidence_claimed": False,
                "security_boundary_claimed": False,
                "summary": {
                    "failed_check_count": failed,
                    "blocking_check_count": 0 if status == "pass" else 1,
                    "source_file_count": 5,
                    "source_hashed_file_count": 5,
                    "rootfs_file_count": matched,
                    "matched_source_file_count": matched,
                    "image_exists": True,
                    "image_sha256": "a" * 64,
                    "extracted_rootfs_exists": extracted,
                    "image_binding_status": "pass",
                    "execution_performed": False,
                    "rootfs_extraction_performed": False,
                    "boot_evidence_claimed": False,
                    "security_boundary_claimed": False,
                },
            }
        ),
        encoding="utf-8",
    )
    return path


class RootfsExtractionReceiptTests(unittest.TestCase):
    def test_receipt_pending_until_operator_executes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            handoff = _write_handoff(tmp_path, status="blocked")
            manifest = _write_rootfs_manifest(tmp_path, status="blocked")
            receipt = rootfs_extraction_receipt.make_rootfs_extraction_receipt(
                handoff_path=handoff,
                rootfs_content_manifest_path=manifest,
            )
            schema = json.loads((ROOT / "specs" / "rootfs-extraction-receipt.schema.json").read_text(encoding="utf-8"))
            self.assertEqual(validate_json(receipt, schema), [])
            self.assertEqual(receipt["status"], "pending_operator_action")
            self.assertFalse(receipt["operator_executed"])
            self.assertFalse(receipt["captured_qemu_promotion_allowed"])

    def test_receipt_verifies_when_operator_executed_and_manifest_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            handoff = _write_handoff(tmp_path)
            manifest = _write_rootfs_manifest(tmp_path, status="pass", matched=5, extracted=True)
            receipt = rootfs_extraction_receipt.make_rootfs_extraction_receipt(
                handoff_path=handoff,
                rootfs_content_manifest_path=manifest,
                operator_executed=True,
                operator_notes="operator ran handoff",
            )
            self.assertEqual(receipt["status"], "verified")
            self.assertTrue(receipt["rootfs_extraction_performed"])
            self.assertTrue(receipt["captured_qemu_promotion_allowed"])
            self.assertEqual(receipt["rootfs_content_manifest"]["matched_source_file_count"], 5)

    def test_receipt_verification_fails_when_manifest_does_not_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            handoff = _write_handoff(tmp_path)
            manifest = _write_rootfs_manifest(tmp_path, status="blocked", matched=3, extracted=True)
            receipt = rootfs_extraction_receipt.make_rootfs_extraction_receipt(
                handoff_path=handoff,
                rootfs_content_manifest_path=manifest,
                operator_executed=True,
            )
            self.assertEqual(receipt["status"], "verification_failed")
            self.assertFalse(receipt["captured_qemu_promotion_allowed"])

    def test_cli_writes_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            handoff = _write_handoff(tmp_path)
            manifest = _write_rootfs_manifest(tmp_path, status="pass", matched=5, extracted=True)
            out = tmp_path / "rootfs_extraction_receipt.json"
            with redirect_stdout(io.StringIO()):
                code = emit_rootfs_extraction_receipt.main(
                    [
                        "--handoff",
                        str(handoff),
                        "--rootfs-content-manifest",
                        str(manifest),
                        "--operator-executed",
                        "--operator-notes",
                        "unit",
                        "--out",
                        str(out),
                    ]
                )
            self.assertEqual(code, 0)
            receipt = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(receipt["artifact_kind"], "pooleos.rootfs_extraction_receipt")
            self.assertEqual(receipt["status"], "verified")

    def test_release_gate_accepts_pending_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            handoff = _write_handoff(tmp_path, status="blocked")
            manifest = _write_rootfs_manifest(tmp_path, status="blocked")
            out = tmp_path / "rootfs_extraction_receipt.json"
            receipt = rootfs_extraction_receipt.make_rootfs_extraction_receipt(
                handoff_path=handoff,
                rootfs_content_manifest_path=manifest,
            )
            rootfs_extraction_receipt.write_receipt(receipt, out)
            check = pooleos_release_gate.check_rootfs_extraction_receipt(out)
            self.assertEqual(check["name"], "rootfs_extraction_receipt")
            self.assertTrue(check["ok"], check)
            self.assertIn("status=pending_operator_action", check["detail"])

    def test_captured_promotion_gate_requires_verified_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pending_path = tmp_path / "pending.json"
            verified_path = tmp_path / "verified.json"
            captured_path = tmp_path / "qemu_boot_evidence.captured.json"
            captured_path.write_text("{}", encoding="utf-8")
            pending = rootfs_extraction_receipt.make_rootfs_extraction_receipt(
                handoff_path=_write_handoff(tmp_path, status="blocked"),
                rootfs_content_manifest_path=_write_rootfs_manifest(tmp_path, status="blocked"),
            )
            rootfs_extraction_receipt.write_receipt(pending, pending_path)
            failed_check = pooleos_release_gate.check_captured_qemu_rootfs_promotion(captured_path, pending_path)
            self.assertFalse(failed_check["ok"])
            verified = rootfs_extraction_receipt.make_rootfs_extraction_receipt(
                handoff_path=_write_handoff(tmp_path),
                rootfs_content_manifest_path=_write_rootfs_manifest(tmp_path, status="pass", matched=5, extracted=True),
                operator_executed=True,
            )
            rootfs_extraction_receipt.write_receipt(verified, verified_path)
            passed_check = pooleos_release_gate.check_captured_qemu_rootfs_promotion(captured_path, verified_path)
            self.assertTrue(passed_check["ok"], passed_check)


if __name__ == "__main__":
    unittest.main()
