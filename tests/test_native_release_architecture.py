import json
import os
import subprocess
import sys
import tempfile
import unicodedata
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.schema_validation import validate_json  # noqa: E402
from tools import check_native_release_architecture as checker  # noqa: E402


REQUIRED_PATHS = (
    "EFI/BOOT/BOOTX64.EFI",
    "pooleos/PooleKernel.elf",
    "pooleos/system/initial-system.bundle",
    "pooleos/recovery/recovery.bundle",
    "pooleos/manifest.json",
)


def make_clean_tree(root: Path) -> None:
    for relative_path in REQUIRED_PATHS:
        path = root / Path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix == ".json":
            path.write_text('{"system":"PooleOS","architecture":"native"}\n', encoding="ascii")
        else:
            path.write_bytes(b"POOLEOS_NATIVE_TEST_OBJECT\x00")


class NativeReleaseArchitectureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(
            (ROOT / "specs" / "native-release-architecture-report.schema.json").read_text(encoding="utf-8")
        )
        cls.policy = json.loads(
            (ROOT / "specs" / "native-release-architecture-policy.json").read_text(encoding="utf-8")
        )

    def test_clean_native_tree_passes_but_does_not_promote_production(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp) / "release"
            make_clean_tree(tree)
            report = checker.scan_release_tree(tree, input_id="fixture-clean-native")
            self.assertEqual(validate_json(report, self.schema), [])
            self.assertEqual(report["status"], "pass")
            self.assertTrue(report["architecture_conformance_passed"])
            self.assertFalse(report["production_promotion_allowed"])
            self.assertEqual(report["violations"], [])
            self.assertFalse(report["input"]["absolute_path_recorded"])
            self.assertNotIn(str(tree), json.dumps(report))
            self.assertEqual(report, checker.scan_release_tree(tree, input_id="fixture-clean-native"))

    def test_cli_exit_codes_and_report_output_are_machine_readable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp) / "release"
            out = Path(tmp) / "report.json"
            make_clean_tree(tree)
            command = [
                sys.executable,
                str(ROOT / "tools" / "check_native_release_architecture.py"),
                "--root",
                str(tree),
                "--input-id",
                "cli-fixture",
                "--out",
                str(out),
            ]
            completed = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
            self.assertEqual(completed.returncode, 0, completed.stdout)
            self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["status"], "pass")
            (tree / "etc" / "debian_version").parent.mkdir(parents=True)
            (tree / "etc" / "debian_version").write_text("13\n", encoding="ascii")
            completed = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
            self.assertEqual(completed.returncode, 1, completed.stdout)
            self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["status"], "fail")

    def test_missing_and_wrong_type_required_objects_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp) / "release"
            make_clean_tree(tree)
            (tree / "pooleos" / "PooleKernel.elf").unlink()
            (tree / "pooleos" / "PooleKernel.elf").mkdir()
            (tree / "pooleos" / "manifest.json").unlink()
            report = checker.scan_release_tree(tree)
            types = {item["type"] for item in report["violations"]}
            self.assertIn("required_path_missing", types)
            self.assertIn("required_path_wrong_type", types)
            self.assertFalse(report["architecture_conformance_passed"])

    def test_every_forbidden_path_rule_is_executable(self) -> None:
        examples = {
            "boot/vmlinuz*": "boot/vmlinuz-poole",
            "boot/bzimage*": "boot/bzimage-test",
            "boot/grub/**": "boot/grub/grub.cfg",
            "efi/**/grub*.efi": "efi/boot/grubx64.efi",
            "**/limine.cfg": "pooleos/limine.cfg",
            "**/limine.conf": "pooleos/limine.conf",
            "**/limine*.sys": "pooleos/limine-bios.sys",
            "etc/systemd/**": "etc/systemd/system/test.service",
            "usr/lib/systemd/**": "usr/lib/systemd/system/test.service",
            "lib/systemd/**": "lib/systemd/system/test.service",
            "var/lib/dpkg/**": "var/lib/dpkg/status",
            "etc/debian_version": "etc/debian_version",
            "etc/buildroot-release": "etc/buildroot-release",
        }
        self.assertEqual(set(examples), set(self.policy["forbidden_path_globs"]))
        for rule, relative_path in examples.items():
            with self.subTest(rule=rule), tempfile.TemporaryDirectory() as tmp:
                tree = Path(tmp) / "release"
                make_clean_tree(tree)
                path = tree / Path(relative_path)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"substitute")
                report = checker.scan_release_tree(tree)
                self.assertTrue(any(item["type"] == "forbidden_path" and item["rule"] == rule for item in report["violations"]))

    def test_every_forbidden_content_marker_is_executable(self) -> None:
        for marker in self.policy["forbidden_ascii_markers"]:
            with self.subTest(marker=marker), tempfile.TemporaryDirectory() as tmp:
                tree = Path(tmp) / "release"
                make_clean_tree(tree)
                target = tree / "pooleos" / "system" / "marker.bundle"
                target.write_bytes(b"prefix\x00" + marker.encode("ascii") + b"\x00suffix")
                report = checker.scan_release_tree(tree)
                self.assertTrue(
                    any(item["type"] == "forbidden_content_marker" and item["rule"] == marker for item in report["violations"])
                )

    def test_unscanned_documentation_does_not_create_marker_false_positive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp) / "release"
            make_clean_tree(tree)
            (tree / "README.md").write_text("GNU GRUB is prohibited historical context.\n", encoding="ascii")
            report = checker.scan_release_tree(tree)
            self.assertEqual(report["status"], "pass")

    def test_casefold_collision_helper_is_deterministic(self) -> None:
        self.assertEqual(
            checker.casefold_collisions(["PooleOS/A", "pooleos/a", "z", "Z", "unique"]),
            [["PooleOS/A", "pooleos/a"], ["Z", "z"]],
        )

    def test_non_nfc_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp) / "release"
            make_clean_tree(tree)
            decomposed = "cafe\u0301.bundle"
            self.assertNotEqual(decomposed, unicodedata.normalize("NFC", decomposed))
            path = tree / "pooleos" / decomposed
            path.write_bytes(b"test")
            report = checker.scan_release_tree(tree)
            self.assertTrue(any(item["type"] == "non_nfc_path" for item in report["violations"]))

    def test_symbolic_link_is_rejected_when_host_supports_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp) / "release"
            make_clean_tree(tree)
            link = tree / "pooleos" / "linked.bundle"
            try:
                os.symlink(tree / "pooleos" / "system" / "initial-system.bundle", link)
            except (OSError, NotImplementedError) as error:
                self.skipTest(f"symbolic links unavailable: {error}")
            report = checker.scan_release_tree(tree)
            self.assertTrue(any(item["type"] == "symbolic_link" for item in report["violations"]))


if __name__ == "__main__":
    unittest.main()
