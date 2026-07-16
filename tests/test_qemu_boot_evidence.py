import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import boot_log, qemu_boot_evidence  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import emit_qemu_boot_evidence  # noqa: E402


class QemuBootEvidenceTests(unittest.TestCase):
    def test_fixture_boot_evidence_validates_without_claiming_captured_boot(self) -> None:
        evidence = qemu_boot_evidence.make_qemu_boot_evidence(root=ROOT)
        schema = json.loads((ROOT / "specs" / "qemu-boot-evidence.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(validate_json(evidence, schema), [])
        self.assertEqual(evidence["status"], "pass")
        self.assertEqual(evidence["evidence_source"], "fixture")
        self.assertFalse(evidence["boot_evidence_claimed"])
        self.assertEqual(evidence["summary"]["profile"], "trap-input")
        self.assertEqual(evidence["summary"]["missing_marker_count"], 0)

    def test_captured_qemu_serial_source_claims_boot_when_validation_passes(self) -> None:
        fixture = qemu_boot_evidence.default_fixture_path(ROOT)
        evidence = qemu_boot_evidence.make_qemu_boot_evidence(
            root=ROOT,
            log_path=fixture,
            evidence_source="captured_qemu_serial",
        )
        self.assertEqual(evidence["status"], "pass")
        self.assertTrue(evidence["boot_evidence_claimed"])

    def test_missing_trap_marker_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "bad.serial.log"
            log.write_text("\n".join(boot_log.REQUIRED_MARKERS), encoding="utf-8")
            evidence = qemu_boot_evidence.make_qemu_boot_evidence(root=ROOT, log_path=log)
            self.assertEqual(evidence["status"], "fail")
            self.assertIn("POOLEOS_LAB_SHARED_MOUNT_PASS", evidence["boot_log_validation"]["missing_markers"])

    def test_cli_writes_qemu_boot_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "qemu_boot_evidence.json"
            with redirect_stdout(io.StringIO()):
                code = emit_qemu_boot_evidence.main(["--out", str(out)])
            self.assertEqual(code, 0)
            evidence = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(evidence["artifact_kind"], "pooleos.qemu_boot_evidence")
            self.assertFalse(evidence["boot_evidence_claimed"])


if __name__ == "__main__":
    unittest.main()
