import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import wsl_build  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import pooleos_wsl_build  # noqa: E402


class WSLBuildTests(unittest.TestCase):
    def _fake_buildroot(self, tmp_path: Path) -> Path:
        buildroot = tmp_path / "buildroot"
        buildroot.mkdir()
        (buildroot / "Makefile").write_text("export BR2_VERSION := fake\n", encoding="utf-8")
        return buildroot

    def _configure_report(self, tmp_path: Path, *, status: str, output_dir: Path) -> Path:
        report = tmp_path / "buildroot_configure.json"
        report.write_text(
            json.dumps(
                {
                    "schema_version": "0.1",
                    "artifact_kind": "pooleos.buildroot_configure",
                    "status": status,
                    "buildroot_path": str(tmp_path / "buildroot"),
                    "external_path": str(ROOT / "lab-os" / "buildroot" / "external"),
                    "defconfig_name": "pooleos_lab_x86_64_defconfig",
                    "output_dir": str(output_dir),
                    "command": ["make", "pooleos_lab_x86_64_defconfig"],
                    "exit_code": 0 if status == "pass" else -1,
                    "stdout_tail": "configured" if status == "pass" else "blocked",
                    "checks": [{"name": "unit", "ok": status == "pass", "detail": status}],
                }
            ),
            encoding="utf-8",
        )
        return report

    def test_blocked_configure_does_not_invoke_runner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            buildroot = self._fake_buildroot(tmp_path)
            output_dir = tmp_path / "output"
            configure = self._configure_report(tmp_path, status="blocked", output_dir=output_dir)

            def runner(command: list[str], timeout_seconds: int) -> subprocess.CompletedProcess[str]:
                raise AssertionError("runner should not be invoked when configure is blocked")

            report = wsl_build.make_build_report(
                buildroot_path=buildroot,
                external_path=ROOT / "lab-os" / "buildroot" / "external",
                configure_report_path=configure,
                output_dir=output_dir,
                runner=runner,
            )
            self.assertEqual(report["status"], "blocked")
            self.assertFalse(report["execution_performed"])
            self.assertEqual(report["source_configure"]["status"], "blocked")
            self.assertFalse(report["rootfs_image"]["exists"])

    def test_pass_configure_invokes_runner_and_requires_rootfs_image(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            buildroot = self._fake_buildroot(tmp_path)
            output_dir = tmp_path / "output"
            configure = self._configure_report(tmp_path, status="pass", output_dir=output_dir)

            def runner(command: list[str], timeout_seconds: int) -> subprocess.CompletedProcess[str]:
                image = output_dir / "images" / "rootfs.ext4"
                image.parent.mkdir(parents=True)
                image.write_bytes(b"rootfs")
                return subprocess.CompletedProcess(command, 0, stdout="built\n")

            report = wsl_build.make_build_report(
                buildroot_path=buildroot,
                external_path=ROOT / "lab-os" / "buildroot" / "external",
                configure_report_path=configure,
                output_dir=output_dir,
                runner=runner,
            )
            schema = json.loads((ROOT / "specs" / "buildroot-build.schema.json").read_text(encoding="utf-8"))
            self.assertEqual(validate_json(report, schema), [])
            self.assertEqual(report["status"], "pass")
            self.assertTrue(report["execution_performed"])
            self.assertTrue(report["rootfs_image"]["exists"])
            self.assertEqual(len(report["rootfs_image"]["sha256"]), 64)

    def test_cli_writes_blocked_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            buildroot = self._fake_buildroot(tmp_path)
            output_dir = tmp_path / "output"
            configure = self._configure_report(tmp_path, status="blocked", output_dir=output_dir)
            out = tmp_path / "build.json"
            with redirect_stdout(io.StringIO()):
                code = pooleos_wsl_build.main(
                    [
                        "--buildroot-path",
                        str(buildroot),
                        "--configure-report",
                        str(configure),
                        "--output-dir",
                        str(output_dir),
                        "--out",
                        str(out),
                    ]
                )
            self.assertEqual(code, 1)
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(data["artifact_kind"], "pooleos.buildroot_build")
            self.assertEqual(data["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
