import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import pooleos_doctor, pooleos_release_gate


class PooleOSDoctorTests(unittest.TestCase):
    def test_failed_command_retains_early_diagnostics_and_exit_status(self) -> None:
        output = "FAIL: early-test\nTraceback: original-cause\n" + "later output\n" * 30
        with mock.patch.object(pooleos_doctor.subprocess, "run", return_value=subprocess.CompletedProcess([], 7, output)):
            result = pooleos_doctor.run_command("test", ["synthetic"], Path.cwd(), 1)
        self.assertFalse(result.ok)
        self.assertEqual(result.detail, "exit=7\n" + output)

    def test_real_command_retains_stderr_and_all_stdout_on_failure(self) -> None:
        code = "import sys; print('early stderr cause',file=sys.stderr,flush=True); print('later stdout\\n'*20); sys.exit(3)"
        result = pooleos_doctor.run_command("test", [sys.executable, "-c", code], Path.cwd(), 10)
        self.assertFalse(result.ok)
        self.assertTrue(result.detail.startswith("exit=3\n"))
        self.assertIn("early stderr cause", result.detail)
        self.assertEqual(result.detail.count("later stdout"), 20)

    def test_timeout_retains_partial_text_bytes_or_empty_output(self) -> None:
        for output in ("partial cause\n", b"partial cause\n", None):
            with self.subTest(output=output):
                error = subprocess.TimeoutExpired(["synthetic"], 2, output=output)
                with mock.patch.object(pooleos_doctor.subprocess, "run", side_effect=error):
                    result = pooleos_doctor.run_command("test", ["synthetic"], Path.cwd(), 2)
                self.assertFalse(result.ok)
                self.assertTrue(result.detail.startswith("timed out after 2s\n"))
                if output:
                    self.assertIn("partial cause", result.detail)

    def test_empty_failure_and_start_error_cannot_pass(self) -> None:
        with mock.patch.object(pooleos_doctor.subprocess, "run", return_value=subprocess.CompletedProcess([], 2, "")):
            result = pooleos_doctor.run_command("test", ["synthetic"], Path.cwd(), 1)
        self.assertFalse(result.ok)
        self.assertEqual(result.detail, "exit=2\n")
        with mock.patch.object(pooleos_doctor.subprocess, "run", side_effect=OSError("missing executable")):
            result = pooleos_doctor.run_command("test", ["synthetic"], Path.cwd(), 1)
        self.assertFalse(result.ok)
        self.assertIn("failed to start: missing executable", result.detail)

    def test_nested_doctor_failure_survives_later_success_lines(self) -> None:
        output = "FAIL: early-test\nTraceback: original-cause\n" + "later child output\n" * 30
        with mock.patch.object(pooleos_doctor.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, output)):
            inner = pooleos_doctor.run_command("test", ["synthetic"], Path.cwd(), 1)
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            pooleos_doctor.print_result(inner)
        outer = printed.getvalue() + "PASS later: ok\n" * 20
        for include_runtime in (True, False):
            with self.subTest(include_runtime=include_runtime):
                with mock.patch.object(pooleos_release_gate.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, outer)) as run:
                    result = pooleos_release_gate.run_doctor(include_runtime=include_runtime)
                self.assertFalse(result["ok"])
                self.assertEqual(result["detail"], "doctor exit=1\n" + outer)
                self.assertEqual("--no-runtime" in run.call_args.args[0], not include_runtime)

    def test_success_tails_remain_compact_and_empty_doctor_failure_rejects(self) -> None:
        output = "".join(f"line {i}\n" for i in range(20))
        with mock.patch.object(pooleos_doctor.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, output)):
            result = pooleos_doctor.run_command("test", ["synthetic"], Path.cwd(), 1)
            gate = pooleos_release_gate.run_doctor(include_runtime=True)
        self.assertTrue(result.ok)
        self.assertEqual(result.detail, "\n".join(output.splitlines()[-6:]))
        self.assertTrue(gate["ok"])
        self.assertEqual(gate["detail"], "\n".join(output.splitlines()[-8:]))
        with mock.patch.object(pooleos_release_gate.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, "")):
            gate = pooleos_release_gate.run_doctor(include_runtime=True)
        self.assertFalse(gate["ok"])
        self.assertIn("doctor exit=1", gate["detail"])

    def test_pooleglyph_runtime_uses_temporary_outputs(self) -> None:
        calls: list[tuple[str, list[str], Path, int]] = []

        def fake_run_command(name: str, cmd: list[str], cwd: Path, timeout: int) -> pooleos_doctor.CheckResult:
            calls.append((name, cmd, cwd, timeout))
            return pooleos_doctor.CheckResult(name, True, "pass")

        with mock.patch.object(pooleos_doctor, "run_command", side_effect=fake_run_command):
            result = pooleos_doctor.run_pooleos_tests()

        self.assertTrue(result.ok)
        self.assertEqual(
            calls,
            [
                (
                    "pooleos:unittest",
                    [pooleos_doctor.sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                    pooleos_doctor.ROOT,
                    1200,
                )
            ],
        )
        calls.clear()

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
