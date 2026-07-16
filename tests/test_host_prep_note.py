import hashlib
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import host_prep_note  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import pooleos_host_prep_note  # noqa: E402


class HostPrepNoteTests(unittest.TestCase):
    def _write_request(self, tmp_path: Path, *, command: str | None = None) -> Path:
        command = command or "sudo apt-get update && sudo apt-get install -y make qemu-system-x86"
        path = tmp_path / "operator_action.json"
        path.write_text(
            json.dumps(
                {
                    "schema_version": "0.1",
                    "artifact_kind": "pooleos.operator_action_request",
                    "status": "pending_approval",
                    "action_kind": "wsl_package_install",
                    "target": {"environment": "wsl", "distro": "Ubuntu", "package_manager": "apt-get"},
                    "source_artifact": "wsl_prerequisites.json",
                    "source_status": "blocked",
                    "requires_operator_approval": True,
                    "codex_execution_allowed": False,
                    "execution_performed": False,
                    "command": command,
                    "command_sha256": hashlib.sha256(command.encode("utf-8")).hexdigest(),
                    "packages": ["make", "qemu-system-x86"],
                    "safety_checks": [{"name": "unit", "ok": True, "detail": "ok"}],
                    "next_steps": ["review"],
                }
            ),
            encoding="utf-8",
        )
        return path

    def _write_receipt(self, tmp_path: Path, *, command: str | None = None, hash_value: str | None = None) -> Path:
        command = command or "sudo apt-get update && sudo apt-get install -y make qemu-system-x86"
        path = tmp_path / "operator_receipt.json"
        path.write_text(
            json.dumps(
                {
                    "schema_version": "0.1",
                    "artifact_kind": "pooleos.operator_action_receipt",
                    "status": "pending_operator_action",
                    "action_kind": "wsl_package_install",
                    "target": {"environment": "wsl", "distro": "Ubuntu", "package_manager": "apt-get"},
                    "operator_action_request": "operator_action.json",
                    "verification_prerequisites": "wsl_prerequisites.json",
                    "operator_executed": False,
                    "codex_execution_performed": False,
                    "command": command,
                    "command_sha256": hash_value or hashlib.sha256(command.encode("utf-8")).hexdigest(),
                    "packages": ["make", "qemu-system-x86"],
                    "checks": [{"name": "unit", "ok": True, "detail": "ok"}],
                    "next_steps": ["review"],
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_manifest_validates_and_note_quotes_command_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            request = self._write_request(tmp_path)
            receipt = self._write_receipt(tmp_path)
            note_path = tmp_path / "host_prep_note.md"
            manifest = host_prep_note.make_host_prep_note_manifest(
                operator_action_path=request,
                operator_receipt_path=receipt,
                note_path=note_path,
            )
            schema = json.loads((ROOT / "specs" / "host-prep-note.schema.json").read_text(encoding="utf-8"))
            self.assertEqual(validate_json(manifest, schema), [])
            self.assertEqual(manifest["status"], "ready_for_operator")
            markdown = host_prep_note.render_host_prep_markdown(manifest)
            self.assertIn(manifest["command"], markdown)
            self.assertIn(manifest["command_sha256"], markdown)
            self.assertIn("Codex did not execute", markdown)

    def test_cli_writes_note_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            request = self._write_request(tmp_path)
            receipt = self._write_receipt(tmp_path)
            note_out = tmp_path / "host_prep_note.md"
            manifest_out = tmp_path / "host_prep_note.json"
            with redirect_stdout(io.StringIO()):
                code = pooleos_host_prep_note.main(
                    [
                        "--operator-action",
                        str(request),
                        "--operator-receipt",
                        str(receipt),
                        "--note-out",
                        str(note_out),
                        "--manifest-out",
                        str(manifest_out),
                    ]
                )
            self.assertEqual(code, 0)
            self.assertTrue(note_out.exists())
            manifest = json.loads(manifest_out.read_text(encoding="utf-8"))
            self.assertEqual(manifest["artifact_kind"], "pooleos.host_prep_note")
            self.assertEqual(manifest["status"], "ready_for_operator")

    def test_manifest_invalid_when_receipt_hash_differs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            request = self._write_request(tmp_path)
            receipt = self._write_receipt(tmp_path, hash_value="0" * 64)
            manifest = host_prep_note.make_host_prep_note_manifest(
                operator_action_path=request,
                operator_receipt_path=receipt,
                note_path=tmp_path / "host_prep_note.md",
            )
            self.assertEqual(manifest["status"], "invalid")
            self.assertFalse(next(check for check in manifest["checks"] if check["name"] == "command_hash_match")["ok"])


if __name__ == "__main__":
    unittest.main()
