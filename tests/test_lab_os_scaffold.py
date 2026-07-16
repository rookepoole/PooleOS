import unittest
import json
import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class LabOSScaffoldTests(unittest.TestCase):
    def test_buildroot_external_tree_files_exist(self) -> None:
        required = [
            ROOT / "lab-os" / "buildroot" / "external" / "external.desc",
            ROOT / "lab-os" / "buildroot" / "external" / "Config.in",
            ROOT / "lab-os" / "buildroot" / "external" / "external.mk",
            ROOT / "lab-os" / "buildroot" / "external" / "configs" / "pooleos_lab_x86_64_defconfig",
            ROOT / "lab-os" / "buildroot" / "external" / "board" / "pooleos_lab" / "post-build.sh",
            ROOT
            / "lab-os"
            / "buildroot"
            / "external"
            / "board"
            / "pooleos_lab"
            / "rootfs_overlay"
            / "usr"
            / "bin"
            / "pooleos-lab-verify-input",
            ROOT
            / "lab-os"
            / "buildroot"
            / "external"
            / "board"
            / "pooleos_lab"
            / "rootfs_overlay"
            / "etc"
            / "init.d"
            / "S99pooleos-lab",
        ]
        missing = [path for path in required if not path.exists()]
        self.assertEqual(missing, [])

    def test_defconfig_declares_python_overlay_and_qemu_console(self) -> None:
        text = (ROOT / "lab-os" / "buildroot" / "external" / "configs" / "pooleos_lab_x86_64_defconfig").read_text(encoding="utf-8")
        self.assertIn("BR2_PACKAGE_PYTHON3=y", text)
        self.assertIn("BR2_ROOTFS_OVERLAY", text)
        self.assertIn('BR2_TARGET_GENERIC_GETTY_PORT="ttyS0"', text)

    def test_guarded_scripts_exist_and_fail_clearly(self) -> None:
        build_script = ROOT / "lab-os" / "buildroot" / "scripts" / "run-build.ps1"
        qemu_script = ROOT / "lab-os" / "qemu" / "scripts" / "run-pooleos-lab.ps1"
        self.assertIn("BuildrootPath does not exist", build_script.read_text(encoding="utf-8"))
        self.assertIn("ProbeOnly", build_script.read_text(encoding="utf-8"))
        self.assertIn("ConfigureOnly", build_script.read_text(encoding="utf-8"))
        self.assertIn("ImagePath does not exist", qemu_script.read_text(encoding="utf-8"))
        self.assertIn("PrepareInputsOnly", qemu_script.read_text(encoding="utf-8"))
        self.assertIn("pooleos_qemu_prepare_inputs.py", qemu_script.read_text(encoding="utf-8"))
        self.assertIn("TrapBundlePath", qemu_script.read_text(encoding="utf-8"))
        smoke = (
            ROOT
            / "lab-os"
            / "buildroot"
            / "external"
            / "board"
            / "pooleos_lab"
            / "rootfs_overlay"
            / "usr"
            / "bin"
            / "pooleos-lab-smoke"
        ).read_text(encoding="utf-8")
        self.assertIn("pooleos_boot_trap_bundle_manifest.json", smoke)
        self.assertIn("POOLEOS_LAB_INPUT_VERIFY_PASS", smoke)
        init_script = (
            ROOT
            / "lab-os"
            / "buildroot"
            / "external"
            / "board"
            / "pooleos_lab"
            / "rootfs_overlay"
            / "etc"
            / "init.d"
            / "S99pooleos-lab"
        ).read_text(encoding="utf-8")
        self.assertIn("mount -t 9p", init_script)
        self.assertIn("pooleos_output", init_script)
        self.assertIn("pooleos-lab-smoke", init_script)

    def test_buildroot_probe_mode_accepts_minimal_fake_tree(self) -> None:
        build_script = ROOT / "lab-os" / "buildroot" / "scripts" / "run-build.ps1"
        with tempfile.TemporaryDirectory() as tmp:
            fake_buildroot = Path(tmp) / "buildroot"
            fake_buildroot.mkdir()
            (fake_buildroot / "Makefile").write_text("export BR2_VERSION := fake\n", encoding="utf-8")
            report = Path(tmp) / "probe.json"
            completed = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(build_script),
                    "-BuildrootPath",
                    str(fake_buildroot),
                    "-ProbeOnly",
                    "-ProbeReport",
                    str(report),
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout)
            data = json.loads(report.read_text(encoding="utf-8-sig"))
            self.assertEqual(data["artifact_kind"], "pooleos.buildroot_probe")
            self.assertEqual(data["status"], "pass")
            self.assertEqual(data["buildroot_version"], "fake")
            self.assertIn("buildroot_git_commit", data)
            self.assertIn("buildroot_git_tag", data)

    def test_buildroot_configure_mode_writes_report_with_fake_make(self) -> None:
        build_script = ROOT / "lab-os" / "buildroot" / "scripts" / "run-build.ps1"
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fake_buildroot = tmp_path / "buildroot"
            fake_buildroot.mkdir()
            (fake_buildroot / "Makefile").write_text("export BR2_VERSION := fake\n", encoding="utf-8")
            fake_bin = tmp_path / "bin"
            fake_bin.mkdir()
            make_cmd = fake_bin / "make.cmd"
            make_cmd.write_text("@echo off\r\necho fake make %*\r\nexit /b 0\r\n", encoding="utf-8")
            report = tmp_path / "configure.json"
            env = os.environ.copy()
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            completed = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(build_script),
                    "-BuildrootPath",
                    str(fake_buildroot),
                    "-ConfigureOnly",
                    "-ConfigureReport",
                    str(report),
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=env,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout)
            data = json.loads(report.read_text(encoding="utf-8-sig"))
            self.assertEqual(data["artifact_kind"], "pooleos.buildroot_configure")
            self.assertEqual(data["status"], "pass")
            self.assertEqual(data["defconfig_name"], "pooleos_lab_x86_64_defconfig")
            self.assertIn("pooleos_lab_x86_64_defconfig", data["command"])
            self.assertIn("fake make", data["stdout_tail"])


if __name__ == "__main__":
    unittest.main()
