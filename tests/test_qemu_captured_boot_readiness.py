import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import qemu_boot_evidence, qemu_captured_boot_readiness, qemu_captured_boot_receipt, rootfs_extraction_receipt  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import emit_qemu_captured_boot_readiness, pooleos_release_gate  # noqa: E402


def _write_handoff(tmp_path: Path) -> Path:
    path = tmp_path / "rootfs_extraction_handoff.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "artifact_kind": "pooleos.rootfs_extraction_handoff",
                "status": "pass",
                "execution_performed": False,
                "codex_execution_allowed": False,
                "rootfs_extraction_performed": False,
                "bash_script_sha256": "b" * 64,
                "summary": {"failed_check_count": 0, "command_count": 7},
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_rootfs_manifest(tmp_path: Path, *, status: str = "pass", matched: int = 5, extracted: bool = True) -> Path:
    path = tmp_path / "rootfs_content_manifest.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "artifact_kind": "pooleos.rootfs_content_manifest",
                "status": status,
                "summary": {
                    "failed_check_count": 0,
                    "source_file_count": 5,
                    "matched_source_file_count": matched,
                    "image_exists": True,
                    "image_sha256": "a" * 64,
                    "extracted_rootfs_exists": extracted,
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_rootfs_receipt(tmp_path: Path, *, verified: bool) -> Path:
    receipt = rootfs_extraction_receipt.make_rootfs_extraction_receipt(
        handoff_path=_write_handoff(tmp_path),
        rootfs_content_manifest_path=_write_rootfs_manifest(
            tmp_path,
            status="pass" if verified else "blocked",
            matched=5 if verified else 0,
            extracted=verified,
        ),
        operator_executed=verified,
    )
    path = tmp_path / "rootfs_extraction_receipt.json"
    rootfs_extraction_receipt.write_receipt(receipt, path)
    return path


def _write_fixture(tmp_path: Path) -> Path:
    path = tmp_path / "qemu_boot_evidence.json"
    qemu_boot_evidence.write_evidence(qemu_boot_evidence.make_qemu_boot_evidence(root=ROOT), path)
    return path


def _write_captured(tmp_path: Path) -> Path:
    path = tmp_path / "qemu_boot_evidence.captured.json"
    qemu_boot_evidence.write_evidence(
        qemu_boot_evidence.make_qemu_boot_evidence(root=ROOT, evidence_source="captured_qemu_serial"),
        path,
    )
    return path


def _write_captured_receipt(tmp_path: Path, *, captured: bool) -> tuple[Path, Path]:
    fixture_path = _write_fixture(tmp_path)
    captured_path = _write_captured(tmp_path) if captured else tmp_path / "qemu_boot_evidence.captured.json"
    receipt = qemu_captured_boot_receipt.make_qemu_captured_boot_receipt(
        fixture_evidence_path=fixture_path,
        captured_evidence_path=captured_path,
        operator_executed=captured,
    )
    receipt_path = tmp_path / "qemu_captured_boot_receipt.json"
    qemu_captured_boot_receipt.write_receipt(receipt, receipt_path)
    return receipt_path, captured_path


class QemuCapturedBootReadinessTests(unittest.TestCase):
    def test_readiness_blocks_until_rootfs_and_capture_are_verified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            rootfs_path = _write_rootfs_receipt(tmp_path, verified=False)
            receipt_path, captured_path = _write_captured_receipt(tmp_path, captured=False)
            readiness = qemu_captured_boot_readiness.make_qemu_captured_boot_readiness(
                rootfs_extraction_receipt_path=rootfs_path,
                qemu_captured_boot_receipt_path=receipt_path,
                qemu_captured_boot_evidence_path=captured_path,
            )
            schema = json.loads((ROOT / "specs" / "qemu-captured-boot-readiness.schema.json").read_text(encoding="utf-8"))
            self.assertEqual(validate_json(readiness, schema), [])
            self.assertEqual(readiness["status"], "blocked")
            self.assertFalse(readiness["promotion_language_allowed"])
            self.assertGreater(readiness["summary"]["unmet_requirement_count"], 0)
            self.assertEqual(readiness["summary"]["failed_check_count"], 0)

    def test_readiness_allows_promotion_when_all_inputs_agree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            rootfs_path = _write_rootfs_receipt(tmp_path, verified=True)
            receipt_path, captured_path = _write_captured_receipt(tmp_path, captured=True)
            readiness = qemu_captured_boot_readiness.make_qemu_captured_boot_readiness(
                rootfs_extraction_receipt_path=rootfs_path,
                qemu_captured_boot_receipt_path=receipt_path,
                qemu_captured_boot_evidence_path=captured_path,
            )
            self.assertEqual(readiness["status"], "ready_for_promotion")
            self.assertTrue(readiness["promotion_language_allowed"])
            self.assertEqual(readiness["summary"]["unmet_requirement_count"], 0)

    def test_present_non_captured_evidence_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            rootfs_path = _write_rootfs_receipt(tmp_path, verified=True)
            receipt_path, captured_path = _write_captured_receipt(tmp_path, captured=False)
            qemu_boot_evidence.write_evidence(qemu_boot_evidence.make_qemu_boot_evidence(root=ROOT), captured_path)
            readiness = qemu_captured_boot_readiness.make_qemu_captured_boot_readiness(
                rootfs_extraction_receipt_path=rootfs_path,
                qemu_captured_boot_receipt_path=receipt_path,
                qemu_captured_boot_evidence_path=captured_path,
            )
            self.assertEqual(readiness["status"], "invalid")
            failed = [check["name"] for check in readiness["checks"] if not check["ok"]]
            self.assertIn("captured_evidence_absent_or_captured_source", failed)

    def test_cli_writes_blocked_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            rootfs_path = _write_rootfs_receipt(tmp_path, verified=False)
            receipt_path, captured_path = _write_captured_receipt(tmp_path, captured=False)
            out = tmp_path / "qemu_captured_boot_readiness.json"
            with redirect_stdout(io.StringIO()):
                code = emit_qemu_captured_boot_readiness.main(
                    [
                        "--rootfs-extraction-receipt",
                        str(rootfs_path),
                        "--qemu-captured-boot-receipt",
                        str(receipt_path),
                        "--qemu-captured-boot-evidence",
                        str(captured_path),
                        "--out",
                        str(out),
                    ]
                )
            self.assertEqual(code, 0)
            readiness = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(readiness["artifact_kind"], "pooleos.qemu_captured_boot_readiness")
            self.assertEqual(readiness["status"], "blocked")

    def test_release_gate_accepts_blocked_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            rootfs_path = _write_rootfs_receipt(tmp_path, verified=False)
            receipt_path, captured_path = _write_captured_receipt(tmp_path, captured=False)
            readiness = qemu_captured_boot_readiness.make_qemu_captured_boot_readiness(
                rootfs_extraction_receipt_path=rootfs_path,
                qemu_captured_boot_receipt_path=receipt_path,
                qemu_captured_boot_evidence_path=captured_path,
            )
            out = tmp_path / "qemu_captured_boot_readiness.json"
            qemu_captured_boot_readiness.write_readiness(readiness, out)
            check = pooleos_release_gate.check_qemu_captured_boot_readiness(out)
            self.assertTrue(check["ok"], check)
            self.assertEqual(check["name"], "qemu_captured_boot_readiness")
            self.assertIn("status=blocked", check["detail"])


if __name__ == "__main__":
    unittest.main()
