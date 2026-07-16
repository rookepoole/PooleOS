import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import lab_guest_autostart  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import emit_lab_guest_autostart  # noqa: E402


class LabGuestAutostartTests(unittest.TestCase):
    def _qemu_contract(self, tmp: str) -> Path:
        path = Path(tmp) / "qemu_shared_folder_contract.json"
        path.write_text(
            json.dumps(
                {
                    "status": "pass",
                    "shared_folder": {
                        "mount_tag": "pooleos_output",
                        "host_path": str(Path(tmp) / "qemu_shared"),
                    },
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_lab_guest_autostart_validates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            contract = self._qemu_contract(tmp)
            manifest = lab_guest_autostart.make_lab_guest_autostart(
                root=ROOT,
                qemu_shared_folder_contract_path=contract,
            )
            schema = json.loads((ROOT / "specs" / "lab-guest-autostart.schema.json").read_text(encoding="utf-8"))
            self.assertEqual(validate_json(manifest, schema), [])
            self.assertEqual(manifest["status"], "pass")
            self.assertFalse(manifest["boot_evidence_claimed"])
            self.assertEqual(manifest["guest_autostart"]["mount_tag"], "pooleos_output")
            self.assertIn("POOLEOS_LAB_INPUT_VERIFY_PASS", manifest["boot_log_profile"]["required_markers"])
            self.assertIn("POOLEOS_LAB_TRAP_ABI_BOUNDARY_PASS", manifest["boot_log_profile"]["required_markers"])
            self.assertTrue(manifest["summary"]["qemu_contract_bound"])

    def test_cli_writes_autostart_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            contract = self._qemu_contract(tmp)
            out = Path(tmp) / "lab_guest_autostart.json"
            with redirect_stdout(io.StringIO()):
                code = emit_lab_guest_autostart.main(
                    ["--qemu-shared-folder-contract", str(contract), "--out", str(out)]
                )
            self.assertEqual(code, 0)
            manifest = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(manifest["artifact_kind"], "pooleos.lab_guest_autostart")
            self.assertEqual(manifest["status"], "pass")

    def test_wrong_qemu_mount_tag_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            contract = Path(tmp) / "qemu_shared_folder_contract.json"
            contract.write_text(
                json.dumps({"status": "pass", "shared_folder": {"mount_tag": "wrong", "host_path": str(Path(tmp))}}),
                encoding="utf-8",
            )
            manifest = lab_guest_autostart.make_lab_guest_autostart(
                root=ROOT,
                qemu_shared_folder_contract_path=contract,
            )
            self.assertEqual(manifest["status"], "fail")
            failed = [check["name"] for check in manifest["checks"] if not check["ok"]]
            self.assertIn("qemu_contract_mount_tag_matches", failed)


if __name__ == "__main__":
    unittest.main()
