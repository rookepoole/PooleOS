import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import host_preflight  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import pooleos_preflight  # noqa: E402


class HostPreflightTests(unittest.TestCase):
    def test_preflight_passes_required_scaffold_checks(self) -> None:
        report = host_preflight.build_preflight_report(root=ROOT, qemu_command="definitely-missing-qemu")
        required_failures = [check for check in report["checks"] if check["required"] and not check["ok"]]
        self.assertEqual(required_failures, [])
        self.assertEqual(report["status"], "warn")
        self.assertEqual(report["readiness_stage"], "scaffold_ready")

    def test_preflight_fails_missing_buildroot_path_when_provided(self) -> None:
        report = host_preflight.build_preflight_report(
            root=ROOT,
            buildroot_path=ROOT / "missing-buildroot-tree",
            qemu_command="definitely-missing-qemu",
        )
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["readiness_stage"], "blocked")
        self.assertTrue(any(check["name"] == "buildroot_tree" and not check["ok"] for check in report["checks"]))

    def test_preflight_cli_writes_valid_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "preflight.json"
            with redirect_stdout(io.StringIO()):
                code = pooleos_preflight.main([
                    "--qemu-command",
                    "definitely-missing-qemu",
                    "--out",
                    str(out),
                ])
            self.assertEqual(code, 0)
            report = json.loads(out.read_text(encoding="utf-8"))
            schema = json.loads((ROOT / "specs" / "host-preflight.schema.json").read_text(encoding="utf-8"))
            self.assertEqual(validate_json(report, schema), [])
            self.assertIn(report["readiness_stage"], {"scaffold_ready", "configure_ready", "build_ready"})

    def test_preflight_can_include_wsl_checks(self) -> None:
        report = host_preflight.build_preflight_report(
            root=ROOT,
            qemu_command="definitely-missing-qemu",
            include_wsl=True,
            wsl_distro="Ubuntu",
        )
        names = {check["name"] for check in report["checks"]}
        self.assertIn("wsl", names)
        self.assertIn("wsl_python3", names)
        self.assertIn("wsl_gnu_make", names)
        self.assertIn("wsl_qemu", names)
        schema = json.loads((ROOT / "specs" / "host-preflight.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(validate_json(report, schema), [])


if __name__ == "__main__":
    unittest.main()
