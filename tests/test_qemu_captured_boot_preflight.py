import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import qemu_captured_boot_preflight  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import emit_qemu_captured_boot_preflight  # noqa: E402


class QemuCapturedBootPreflightTests(unittest.TestCase):
    def test_preflight_passes_when_launch_inputs_are_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            image = tmp_path / "rootfs.ext4"
            image.write_text("fake image", encoding="utf-8")
            shared = tmp_path / "qemu_shared"
            shared.mkdir()
            report = qemu_captured_boot_preflight.make_qemu_captured_boot_preflight(
                root=ROOT,
                image_path=image,
                shared_output_path=shared,
                serial_log_path=tmp_path / "serial.log",
                boot_validation_output=tmp_path / "boot_validation.json",
                qemu_boot_evidence_output=tmp_path / "qemu_boot_evidence.captured.json",
                qemu_captured_boot_receipt_output=tmp_path / "qemu_captured_boot_receipt.json",
                qemu_command="python",
            )
            schema = json.loads((ROOT / "specs" / "qemu-captured-boot-preflight.schema.json").read_text(encoding="utf-8"))
            self.assertEqual(validate_json(report, schema), [])
            self.assertEqual(report["status"], "pass")
            self.assertTrue(report["launch_ready"])
            self.assertFalse(report["execution_performed"])

    def test_preflight_blocks_when_image_or_shared_folder_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            report = qemu_captured_boot_preflight.make_qemu_captured_boot_preflight(
                root=ROOT,
                image_path=tmp_path / "missing.ext4",
                shared_output_path=tmp_path / "missing_shared",
                serial_log_path=tmp_path / "serial.log",
                boot_validation_output=tmp_path / "boot_validation.json",
                qemu_boot_evidence_output=tmp_path / "qemu_boot_evidence.captured.json",
                qemu_captured_boot_receipt_output=tmp_path / "qemu_captured_boot_receipt.json",
                qemu_command="python",
            )
            self.assertEqual(report["status"], "blocked")
            self.assertFalse(report["launch_ready"])
            self.assertGreater(report["summary"]["blocking_check_count"], 0)

    def test_preflight_fails_when_output_paths_collide(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            image = tmp_path / "rootfs.ext4"
            image.write_text("fake image", encoding="utf-8")
            shared = tmp_path / "qemu_shared"
            shared.mkdir()
            output = tmp_path / "captured.json"
            report = qemu_captured_boot_preflight.make_qemu_captured_boot_preflight(
                root=ROOT,
                image_path=image,
                shared_output_path=shared,
                serial_log_path=tmp_path / "serial.log",
                boot_validation_output=output,
                qemu_boot_evidence_output=output,
                qemu_command="python",
            )
            self.assertEqual(report["status"], "fail")
            self.assertEqual(report["summary"]["safety_failure_count"], 1)

    def test_cli_writes_valid_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            image = tmp_path / "rootfs.ext4"
            image.write_text("fake image", encoding="utf-8")
            shared = tmp_path / "qemu_shared"
            shared.mkdir()
            out = tmp_path / "preflight.json"
            with redirect_stdout(io.StringIO()):
                code = emit_qemu_captured_boot_preflight.main(
                    [
                        "--image",
                        str(image),
                        "--shared-output",
                        str(shared),
                        "--serial-log",
                        str(tmp_path / "serial.log"),
                        "--boot-validation-output",
                        str(tmp_path / "boot_validation.json"),
                        "--qemu-boot-evidence-output",
                        str(tmp_path / "qemu_boot_evidence.captured.json"),
                        "--qemu-captured-boot-receipt-output",
                        str(tmp_path / "qemu_captured_boot_receipt.json"),
                        "--qemu-command",
                        "python",
                        "--out",
                        str(out),
                    ]
                )
            self.assertEqual(code, 0)
            report = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(report["artifact_kind"], "pooleos.qemu_captured_boot_preflight")
            self.assertEqual(report["status"], "pass")


if __name__ == "__main__":
    unittest.main()
