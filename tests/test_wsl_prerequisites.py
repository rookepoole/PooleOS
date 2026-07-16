import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import wsl_prerequisites  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import pooleos_wsl_prereqs  # noqa: E402


class WSLPrerequisiteTests(unittest.TestCase):
    def test_synthetic_missing_make_blocks_without_execution(self) -> None:
        checks = [
            {
                "name": "make",
                "role": "buildroot_mandatory",
                "command": "make",
                "package": "make",
                "required": True,
                "ok": False,
                "detail": "not found",
            },
            {
                "name": "qemu",
                "role": "pooleos_boot_extra",
                "command": "qemu-system-x86_64",
                "package": "qemu-system-x86",
                "required": True,
                "ok": False,
                "detail": "not found",
            },
        ]
        report = wsl_prerequisites.make_prerequisite_report(distro="Ubuntu", checks=checks)
        self.assertEqual(report["status"], "blocked")
        self.assertFalse(report["execution_performed"])
        self.assertTrue(report["host_modification_required"])
        self.assertIn("make", report["missing_packages"])
        self.assertIn("qemu-system-x86", report["missing_packages"])

    def test_wsl_prerequisite_report_validates_against_schema(self) -> None:
        checks = [
            {
                "name": "make",
                "role": "buildroot_mandatory",
                "command": "make",
                "package": "make",
                "required": True,
                "ok": True,
                "detail": "/usr/bin/make",
            }
        ]
        report = wsl_prerequisites.make_prerequisite_report(distro="Ubuntu", checks=checks)
        schema = json.loads((ROOT / "specs" / "wsl-prerequisites.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(validate_json(report, schema), [])

    def test_cli_writes_non_mutating_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "wsl_prereqs.json"
            with redirect_stdout(io.StringIO()):
                code = pooleos_wsl_prereqs.main(["--out", str(out)])
            self.assertIn(code, {0, 1})
            report = json.loads(out.read_text(encoding="utf-8"))
            self.assertFalse(report["execution_performed"])


if __name__ == "__main__":
    unittest.main()
