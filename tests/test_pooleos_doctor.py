import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import pooleos_doctor


class PooleOSDoctorTests(unittest.TestCase):
    def test_pooleglyph_conformance_uses_temporary_report(self) -> None:
        calls: list[tuple[str, list[str], Path, int]] = []

        def fake_run_command(name: str, cmd: list[str], cwd: Path, timeout: int) -> pooleos_doctor.CheckResult:
            calls.append((name, cmd, cwd, timeout))
            return pooleos_doctor.CheckResult(name, True, "pass")

        with tempfile.TemporaryDirectory() as temp_dir:
            pooleglyph = Path(temp_dir) / "PooleGlyph"
            pooleglyph.mkdir()
            with mock.patch.object(pooleos_doctor, "run_command", side_effect=fake_run_command):
                results = pooleos_doctor.run_pooleglyph_baseline(pooleglyph, full=False)

        self.assertEqual([result.name for result in results], ["pooleglyph:pgvm_selftest", "pooleglyph:conformance"])
        self.assertEqual(len(calls), 2)
        conformance_command = calls[1][1]
        self.assertIn("--out", conformance_command)
        report_path = Path(conformance_command[conformance_command.index("--out") + 1])
        self.assertNotIn(pooleglyph, report_path.parents)
        self.assertEqual(report_path.name, "conformance_report.json")


if __name__ == "__main__":
    unittest.main()
