import json
import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import wsl_configure  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import pooleos_wsl_configure  # noqa: E402


class WSLConfigureTests(unittest.TestCase):
    def _fake_buildroot(self, tmp_path: Path) -> Path:
        buildroot = tmp_path / "buildroot"
        buildroot.mkdir()
        (buildroot / "Makefile").write_text("export BR2_VERSION := fake\n", encoding="utf-8")
        return buildroot

    def _prereq_file(self, tmp_path: Path, status: str) -> Path:
        prereq = tmp_path / "wsl_prereqs.json"
        missing = [] if status == "pass" else ["make"]
        prereq.write_text(
            json.dumps(
                {
                    "schema_version": "0.1",
                    "artifact_kind": "pooleos.wsl_prerequisites",
                    "status": status,
                    "distro": "Ubuntu",
                    "source_basis": {
                        "buildroot_version": "fake",
                        "buildroot_git_commit": "",
                        "buildroot_manual_path": "",
                    },
                    "execution_performed": False,
                    "host_modification_required": bool(missing),
                    "package_manager": "apt-get",
                    "install_command": "sudo apt-get install -y make" if missing else "",
                    "missing_packages": missing,
                    "checks": [],
                    "notes": ["test"],
                }
            ),
            encoding="utf-8",
        )
        return prereq

    def test_blocked_prerequisites_do_not_invoke_runner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            buildroot = self._fake_buildroot(tmp_path)
            prereq = self._prereq_file(tmp_path, "blocked")

            def runner(command: list[str], timeout_seconds: int) -> subprocess.CompletedProcess[str]:
                raise AssertionError("runner should not be invoked when prerequisites are blocked")

            report = wsl_configure.make_configure_report(
                buildroot_path=buildroot,
                external_path=ROOT / "lab-os" / "buildroot" / "external",
                prerequisites_path=prereq,
                runner=runner,
            )
            self.assertEqual(report["status"], "blocked")
            self.assertEqual(report["exit_code"], -1)
            self.assertIn("missing_packages=make", report["stdout_tail"])

    def test_pass_prerequisites_invoke_runner_and_emit_pass_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            buildroot = self._fake_buildroot(tmp_path)
            prereq = self._prereq_file(tmp_path, "pass")
            seen: dict[str, list[str]] = {}

            def runner(command: list[str], timeout_seconds: int) -> subprocess.CompletedProcess[str]:
                seen["command"] = command
                return subprocess.CompletedProcess(command, 0, stdout="configured\n")

            report = wsl_configure.make_configure_report(
                buildroot_path=buildroot,
                external_path=ROOT / "lab-os" / "buildroot" / "external",
                prerequisites_path=prereq,
                runner=runner,
            )
            self.assertEqual(report["status"], "pass")
            self.assertIn("configured", report["stdout_tail"])
            self.assertIn("pooleos_lab_x86_64_defconfig", " ".join(seen["command"]))
            schema = json.loads((ROOT / "specs" / "buildroot-configure.schema.json").read_text(encoding="utf-8"))
            self.assertEqual(validate_json(report, schema), [])

    def test_cli_writes_blocked_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            buildroot = self._fake_buildroot(tmp_path)
            prereq = self._prereq_file(tmp_path, "blocked")
            out = tmp_path / "configure.json"
            with redirect_stdout(io.StringIO()):
                code = pooleos_wsl_configure.main(
                    [
                        "--buildroot-path",
                        str(buildroot),
                        "--prerequisites",
                        str(prereq),
                        "--out",
                        str(out),
                    ]
                )
            self.assertEqual(code, 1)
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(data["artifact_kind"], "pooleos.buildroot_configure")
            self.assertEqual(data["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
