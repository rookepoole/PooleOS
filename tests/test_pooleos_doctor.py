import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import pooleos_doctor


class PooleOSDoctorTests(unittest.TestCase):
    def test_pooleglyph_runtime_uses_temporary_outputs(self) -> None:
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

        calls.clear()
        with tempfile.TemporaryDirectory() as temp_dir:
            pooleglyph = Path(temp_dir) / "PooleGlyph"
            report = pooleglyph / "tests" / "reports" / "conformance_report.json"
            report.parent.mkdir(parents=True)
            report.write_bytes(b"preserve-me")
            (pooleglyph / "pooleglyph.bat").write_text("@echo off\n", encoding="ascii")

            def fake_full_command(
                name: str, cmd: list[str], cwd: Path, timeout: int
            ) -> pooleos_doctor.CheckResult:
                calls.append((name, cmd, cwd, timeout))
                (cwd / "tests" / "reports" / "conformance_report.json").write_bytes(b"generated")
                return pooleos_doctor.CheckResult(name, True, "pass")

            with mock.patch.object(pooleos_doctor, "run_command", side_effect=fake_full_command):
                results = pooleos_doctor.run_pooleglyph_baseline(pooleglyph, full=True)

            self.assertEqual(report.read_bytes(), b"preserve-me")

        self.assertEqual([result.name for result in results], ["pooleglyph:full_test"])
        self.assertEqual(len(calls), 1)
        self.assertNotEqual(calls[0][2], pooleglyph)
        self.assertEqual(calls[0][1][1], "test")


if __name__ == "__main__":
    unittest.main()
