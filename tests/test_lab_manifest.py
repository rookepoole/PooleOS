import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import boot_log, lab_manifest, readiness  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import emit_lab_manifest  # noqa: E402


class LabManifestTests(unittest.TestCase):
    def test_scaffold_manifest_records_defconfig_hash(self) -> None:
        manifest = lab_manifest.make_lab_manifest(root=ROOT)
        self.assertEqual(manifest["status"], "scaffold")
        self.assertEqual(len(manifest["buildroot"]["defconfig_sha256"]), 64)
        self.assertFalse(manifest["validations"]["buildroot_probe_ok"])
        self.assertFalse(manifest["validations"]["buildroot_configure_ok"])
        self.assertFalse(manifest["validations"]["buildroot_build_ok"])
        self.assertEqual(manifest["validations"]["wsl_missing_package_count"], 0)

    def test_manifest_promotes_to_boot_validated_with_image_and_boot_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            image = tmp_path / "rootfs.ext4"
            image.write_text("fake image placeholder", encoding="utf-8")
            boot_validation = tmp_path / "boot.json"
            boot_log.write_validation(boot_log.validate_boot_log_text("\n".join(boot_log.REQUIRED_MARKERS)), boot_validation)
            release_gate = tmp_path / "release.json"
            readiness.write_readiness_report(
                readiness.make_readiness_report(checks=[readiness.make_check("unit", True, "ok")], artifacts=[]),
                release_gate,
            )
            buildroot_probe = tmp_path / "buildroot_probe.json"
            buildroot_probe.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1",
                        "artifact_kind": "pooleos.buildroot_probe",
                        "status": "pass",
                        "buildroot_path": str(tmp_path / "buildroot"),
                        "buildroot_version": "fake",
                        "buildroot_git_commit": "",
                        "buildroot_git_tag": "",
                        "external_path": str(ROOT / "lab-os" / "buildroot" / "external"),
                        "defconfig_path": str(
                            ROOT
                            / "lab-os"
                            / "buildroot"
                            / "external"
                            / "configs"
                            / "pooleos_lab_x86_64_defconfig"
                        ),
                        "checks": [{"name": "unit", "ok": True, "detail": "ok"}],
                    }
                ),
                encoding="utf-8",
            )
            buildroot_configure = tmp_path / "buildroot_configure.json"
            buildroot_configure.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1",
                        "artifact_kind": "pooleos.buildroot_configure",
                        "status": "pass",
                        "buildroot_path": str(tmp_path / "buildroot"),
                        "external_path": str(ROOT / "lab-os" / "buildroot" / "external"),
                        "defconfig_name": "pooleos_lab_x86_64_defconfig",
                        "output_dir": str(tmp_path / "build"),
                        "command": ["make", "pooleos_lab_x86_64_defconfig"],
                        "exit_code": 0,
                        "stdout_tail": "configured",
                        "checks": [{"name": "unit", "ok": True, "detail": "ok"}],
                    }
                ),
                encoding="utf-8",
            )
            wsl_prerequisites = tmp_path / "wsl_prerequisites.json"
            wsl_prerequisites.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1",
                        "artifact_kind": "pooleos.wsl_prerequisites",
                        "status": "pass",
                        "distro": "Ubuntu",
                        "source_basis": {
                            "buildroot_version": "fake",
                            "buildroot_git_commit": "",
                            "buildroot_manual_path": "",
                        },
                        "execution_performed": False,
                        "host_modification_required": False,
                        "package_manager": "apt-get",
                        "install_command": "",
                        "missing_packages": [],
                        "checks": [],
                        "notes": ["test"],
                    }
                ),
                encoding="utf-8",
            )
            buildroot_build = tmp_path / "buildroot_build.json"
            buildroot_build.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1",
                        "artifact_kind": "pooleos.buildroot_build",
                        "status": "pass",
                        "execution_performed": True,
                        "buildroot_path": str(tmp_path / "buildroot"),
                        "external_path": str(ROOT / "lab-os" / "buildroot" / "external"),
                        "output_dir": str(tmp_path / "output"),
                        "command": ["make"],
                        "exit_code": 0,
                        "stdout_tail": "built",
                        "source_configure": {
                            "path": str(buildroot_configure),
                            "exists": True,
                            "status": "pass",
                            "output_dir": str(tmp_path / "build"),
                            "exit_code": 0,
                        },
                        "rootfs_image": {
                            "path": str(image),
                            "exists": True,
                            "sha256": "a" * 64,
                            "byte_count": image.stat().st_size,
                        },
                        "checks": [{"name": "unit", "ok": True, "detail": "ok"}],
                        "summary": {
                            "failed_check_count": 0,
                            "execution_performed": True,
                            "configure_status": "pass",
                            "rootfs_image_exists": True,
                            "rootfs_image_sha256": "a" * 64,
                        },
                        "limitations": ["test"],
                        "next_steps": ["test"],
                    }
                ),
                encoding="utf-8",
            )
            manifest = lab_manifest.make_lab_manifest(
                root=ROOT,
                image_path=image,
                boot_log_validation_path=boot_validation,
                release_gate_path=release_gate,
                buildroot_probe_path=buildroot_probe,
                buildroot_configure_path=buildroot_configure,
                buildroot_build_path=buildroot_build,
                wsl_prerequisites_path=wsl_prerequisites,
            )
            self.assertEqual(manifest["status"], "boot_validated")
            self.assertTrue(manifest["validations"]["boot_log_ok"])
            self.assertEqual(manifest["validations"]["release_gate_status"], "pass")
            self.assertTrue(manifest["validations"]["buildroot_probe_ok"])
            self.assertEqual(manifest["validations"]["buildroot_probe_status"], "pass")
            self.assertTrue(manifest["validations"]["buildroot_configure_ok"])
            self.assertEqual(manifest["validations"]["buildroot_configure_status"], "pass")
            self.assertTrue(manifest["validations"]["buildroot_build_ok"])
            self.assertEqual(manifest["validations"]["buildroot_build_status"], "pass")
            self.assertEqual(manifest["validations"]["buildroot_build_rootfs_image_path"], str(image))
            self.assertEqual(manifest["validations"]["wsl_prerequisites_status"], "pass")
            self.assertEqual(manifest["validations"]["wsl_missing_package_count"], 0)

    def test_manifest_records_blocked_configure_and_wsl_packages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            buildroot_configure = tmp_path / "buildroot_configure.json"
            buildroot_configure.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1",
                        "artifact_kind": "pooleos.buildroot_configure",
                        "status": "blocked",
                        "buildroot_path": str(tmp_path / "buildroot"),
                        "external_path": str(ROOT / "lab-os" / "buildroot" / "external"),
                        "defconfig_name": "pooleos_lab_x86_64_defconfig",
                        "output_dir": "",
                        "command": ["make", "pooleos_lab_x86_64_defconfig"],
                        "exit_code": -1,
                        "stdout_tail": "missing prerequisites",
                        "checks": [{"name": "wsl_prerequisites", "ok": False, "detail": "blocked"}],
                    }
                ),
                encoding="utf-8",
            )
            wsl_prerequisites = tmp_path / "wsl_prerequisites.json"
            wsl_prerequisites.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1",
                        "artifact_kind": "pooleos.wsl_prerequisites",
                        "status": "blocked",
                        "distro": "Ubuntu",
                        "source_basis": {
                            "buildroot_version": "fake",
                            "buildroot_git_commit": "",
                            "buildroot_manual_path": "",
                        },
                        "execution_performed": False,
                        "host_modification_required": True,
                        "package_manager": "apt-get",
                        "install_command": "sudo apt-get install -y make qemu-system-x86",
                        "missing_packages": ["make", "qemu-system-x86"],
                        "checks": [],
                        "notes": ["test"],
                    }
                ),
                encoding="utf-8",
            )
            buildroot_build = tmp_path / "buildroot_build.json"
            buildroot_build.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1",
                        "artifact_kind": "pooleos.buildroot_build",
                        "status": "blocked",
                        "execution_performed": False,
                        "buildroot_path": str(tmp_path / "buildroot"),
                        "external_path": str(ROOT / "lab-os" / "buildroot" / "external"),
                        "output_dir": str(tmp_path / "output"),
                        "command": ["make"],
                        "exit_code": -1,
                        "stdout_tail": "blocked",
                        "source_configure": {
                            "path": str(buildroot_configure),
                            "exists": True,
                            "status": "blocked",
                            "output_dir": "",
                            "exit_code": -1,
                        },
                        "rootfs_image": {
                            "path": str(tmp_path / "output" / "images" / "rootfs.ext4"),
                            "exists": False,
                            "sha256": "",
                            "byte_count": 0,
                        },
                        "checks": [{"name": "configure_status_pass", "ok": False, "detail": "blocked"}],
                        "summary": {
                            "failed_check_count": 1,
                            "execution_performed": False,
                            "configure_status": "blocked",
                            "rootfs_image_exists": False,
                            "rootfs_image_sha256": "",
                        },
                        "limitations": ["test"],
                        "next_steps": ["test"],
                    }
                ),
                encoding="utf-8",
            )
            manifest = lab_manifest.make_lab_manifest(
                root=ROOT,
                buildroot_configure_path=buildroot_configure,
                buildroot_build_path=buildroot_build,
                wsl_prerequisites_path=wsl_prerequisites,
            )
            schema = json.loads((ROOT / "specs" / "lab-image-manifest.schema.json").read_text(encoding="utf-8"))
            self.assertEqual(validate_json(manifest, schema), [])
            self.assertFalse(manifest["validations"]["buildroot_configure_ok"])
            self.assertEqual(manifest["validations"]["buildroot_configure_status"], "blocked")
            self.assertFalse(manifest["validations"]["buildroot_build_ok"])
            self.assertEqual(manifest["validations"]["buildroot_build_status"], "blocked")
            self.assertEqual(manifest["validations"]["wsl_prerequisites_status"], "blocked")
            self.assertEqual(manifest["validations"]["wsl_missing_package_count"], 2)

    def test_emit_lab_manifest_cli_writes_valid_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "manifest.json"
            with redirect_stdout(io.StringIO()):
                code = emit_lab_manifest.main(["--out", str(out)])
            self.assertEqual(code, 0)
            manifest = json.loads(out.read_text(encoding="utf-8"))
            schema = json.loads((ROOT / "specs" / "lab-image-manifest.schema.json").read_text(encoding="utf-8"))
            self.assertEqual(validate_json(manifest, schema), [])


if __name__ == "__main__":
    unittest.main()
