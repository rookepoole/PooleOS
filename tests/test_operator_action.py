import io
import json
import hashlib
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import operator_action  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import pooleos_operator_action  # noqa: E402
from tools import pooleos_operator_receipt  # noqa: E402


class OperatorActionTests(unittest.TestCase):
    def _write_prerequisites(self, tmp_path: Path, *, status: str, command: str = "") -> Path:
        packages = ["make", "qemu-system-x86"] if status == "blocked" else []
        path = tmp_path / "wsl_prerequisites.json"
        path.write_text(
            json.dumps(
                {
                    "schema_version": "0.1",
                    "artifact_kind": "pooleos.wsl_prerequisites",
                    "status": status,
                    "distro": "Ubuntu",
                    "source_basis": {
                        "buildroot_version": "2026.05",
                        "buildroot_git_commit": "313414b92c2501a2bc123ffa1b6383dca464de05",
                        "buildroot_manual_path": "docs/manual/prerequisite.adoc",
                    },
                    "execution_performed": False,
                    "host_modification_required": bool(packages),
                    "package_manager": "apt-get",
                    "install_command": command,
                    "missing_packages": packages,
                    "checks": [],
                    "notes": ["test"],
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_pending_request_preserves_install_command_without_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            prereq = self._write_prerequisites(
                Path(tmp),
                status="blocked",
                command="sudo apt-get update && sudo apt-get install -y make qemu-system-x86",
            )
            request = operator_action.make_wsl_package_install_request(prerequisites_path=prereq)
            self.assertEqual(request["status"], "pending_approval")
            self.assertTrue(request["requires_operator_approval"])
            self.assertFalse(request["codex_execution_allowed"])
            self.assertFalse(request["execution_performed"])
            self.assertIn("make", request["packages"])
            self.assertEqual(len(request["command_sha256"]), 64)

    def test_no_action_needed_when_prerequisites_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            prereq = self._write_prerequisites(Path(tmp), status="pass")
            request = operator_action.make_wsl_package_install_request(prerequisites_path=prereq)
            self.assertEqual(request["status"], "no_action_needed")
            self.assertFalse(request["requires_operator_approval"])
            schema = json.loads((ROOT / "specs" / "operator-action-request.schema.json").read_text(encoding="utf-8"))
            self.assertEqual(validate_json(request, schema), [])

    def test_cli_writes_valid_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            prereq = self._write_prerequisites(
                tmp_path,
                status="blocked",
                command="sudo apt-get update && sudo apt-get install -y make qemu-system-x86",
            )
            out = tmp_path / "request.json"
            with redirect_stdout(io.StringIO()):
                code = pooleos_operator_action.main(["--wsl-prerequisites", str(prereq), "--out", str(out)])
            self.assertEqual(code, 0)
            request = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(request["artifact_kind"], "pooleos.operator_action_request")
            self.assertEqual(request["status"], "pending_approval")

    def _write_request(self, tmp_path: Path, *, status: str = "pending_approval") -> Path:
        path = tmp_path / "operator_action.json"
        command = "sudo apt-get update && sudo apt-get install -y make qemu-system-x86"
        request = {
            "schema_version": "0.1",
            "artifact_kind": "pooleos.operator_action_request",
            "status": status,
            "action_kind": "wsl_package_install",
            "target": {"environment": "wsl", "distro": "Ubuntu", "package_manager": "apt-get"},
            "source_artifact": "wsl_prerequisites.json",
            "source_status": "blocked" if status == "pending_approval" else "pass",
            "requires_operator_approval": status == "pending_approval",
            "codex_execution_allowed": False,
            "execution_performed": False,
            "command": command,
            "command_sha256": hashlib.sha256(command.encode("utf-8")).hexdigest(),
            "packages": ["make", "qemu-system-x86"] if status == "pending_approval" else [],
            "safety_checks": [{"name": "unit", "ok": True, "detail": "ok"}],
            "next_steps": ["review"],
        }
        path.write_text(json.dumps(request), encoding="utf-8")
        return path

    def test_receipt_pending_when_operator_has_not_executed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            request = self._write_request(tmp_path)
            prereq = self._write_prerequisites(tmp_path, status="blocked", command="sudo apt-get install -y make")
            receipt = operator_action.make_wsl_package_install_receipt(
                operator_action_path=request,
                verification_prerequisites_path=prereq,
            )
            self.assertEqual(receipt["status"], "pending_operator_action")
            self.assertFalse(receipt["operator_executed"])
            self.assertFalse(receipt["codex_execution_performed"])

    def test_receipt_verified_when_operator_executed_and_prereqs_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            request = self._write_request(tmp_path)
            prereq = self._write_prerequisites(tmp_path, status="pass")
            receipt = operator_action.make_wsl_package_install_receipt(
                operator_action_path=request,
                verification_prerequisites_path=prereq,
                operator_executed=True,
            )
            self.assertEqual(receipt["status"], "verified")
            schema = json.loads((ROOT / "specs" / "operator-action-receipt.schema.json").read_text(encoding="utf-8"))
            self.assertEqual(validate_json(receipt, schema), [])

    def test_receipt_fails_when_operator_executed_but_prereqs_still_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            request = self._write_request(tmp_path)
            prereq = self._write_prerequisites(tmp_path, status="blocked", command="sudo apt-get install -y make")
            receipt = operator_action.make_wsl_package_install_receipt(
                operator_action_path=request,
                verification_prerequisites_path=prereq,
                operator_executed=True,
            )
            self.assertEqual(receipt["status"], "verification_failed")

    def test_receipt_cli_writes_pending_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            request = self._write_request(tmp_path)
            prereq = self._write_prerequisites(tmp_path, status="blocked", command="sudo apt-get install -y make")
            out = tmp_path / "receipt.json"
            with redirect_stdout(io.StringIO()):
                code = pooleos_operator_receipt.main(
                    ["--operator-action", str(request), "--wsl-prerequisites", str(prereq), "--out", str(out)]
                )
            self.assertEqual(code, 0)
            receipt = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(receipt["artifact_kind"], "pooleos.operator_action_receipt")
            self.assertEqual(receipt["status"], "pending_operator_action")


if __name__ == "__main__":
    unittest.main()
