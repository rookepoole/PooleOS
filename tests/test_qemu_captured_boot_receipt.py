import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import qemu_boot_evidence, qemu_captured_boot_receipt  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import emit_qemu_captured_boot_receipt  # noqa: E402


class QemuCapturedBootReceiptTests(unittest.TestCase):
    def _write_fixture(self, path: Path) -> Path:
        evidence = qemu_boot_evidence.make_qemu_boot_evidence(root=ROOT)
        qemu_boot_evidence.write_evidence(evidence, path)
        return path

    def _write_captured(self, path: Path) -> Path:
        evidence = qemu_boot_evidence.make_qemu_boot_evidence(
            root=ROOT,
            evidence_source="captured_qemu_serial",
        )
        qemu_boot_evidence.write_evidence(evidence, path)
        return path

    def test_receipt_is_pending_when_captured_slot_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = self._write_fixture(tmp_path / "qemu_boot_evidence.json")
            captured = tmp_path / "qemu_boot_evidence.captured.json"
            receipt = qemu_captured_boot_receipt.make_qemu_captured_boot_receipt(
                fixture_evidence_path=fixture,
                captured_evidence_path=captured,
            )
            schema = json.loads((ROOT / "specs" / "qemu-captured-boot-receipt.schema.json").read_text(encoding="utf-8"))
            self.assertEqual(validate_json(receipt, schema), [])
            self.assertEqual(receipt["status"], "pending_capture")
            self.assertFalse(receipt["boot_evidence_ingested"])
            self.assertTrue(receipt["summary"]["fixture_preserved"])

    def test_receipt_is_captured_when_captured_evidence_is_valid_and_separate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = self._write_fixture(tmp_path / "qemu_boot_evidence.json")
            captured = self._write_captured(tmp_path / "qemu_boot_evidence.captured.json")
            receipt = qemu_captured_boot_receipt.make_qemu_captured_boot_receipt(
                fixture_evidence_path=fixture,
                captured_evidence_path=captured,
                operator_executed=True,
            )
            self.assertEqual(receipt["status"], "captured")
            self.assertTrue(receipt["boot_evidence_ingested"])
            self.assertTrue(receipt["captured_boot_evidence"]["boot_evidence_claimed"])

    def test_receipt_rejects_same_path_for_fixture_and_captured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_fixture(Path(tmp) / "qemu_boot_evidence.json")
            receipt = qemu_captured_boot_receipt.make_qemu_captured_boot_receipt(
                fixture_evidence_path=path,
                captured_evidence_path=path,
            )
            self.assertEqual(receipt["status"], "invalid")
            failed = [check["name"] for check in receipt["checks"] if not check["ok"]]
            self.assertIn("captured_path_separate_from_fixture", failed)

    def test_cli_writes_pending_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = self._write_fixture(tmp_path / "qemu_boot_evidence.json")
            out = tmp_path / "receipt.json"
            with redirect_stdout(io.StringIO()):
                code = emit_qemu_captured_boot_receipt.main(
                    ["--fixture-evidence", str(fixture), "--captured-evidence", str(tmp_path / "missing.json"), "--out", str(out)]
                )
            self.assertEqual(code, 0)
            receipt = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(receipt["artifact_kind"], "pooleos.qemu_captured_boot_receipt")
            self.assertEqual(receipt["status"], "pending_capture")


if __name__ == "__main__":
    unittest.main()
