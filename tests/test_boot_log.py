import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import boot_log  # noqa: E402
from runtime.schema_validation import validate_json  # noqa: E402
from tools import validate_boot_log  # noqa: E402


class BootLogTests(unittest.TestCase):
    def test_boot_log_contract_accepts_all_markers(self) -> None:
        text = "\n".join(boot_log.REQUIRED_MARKERS)
        result = boot_log.validate_boot_log_text(text)
        self.assertTrue(result["ok"])
        self.assertEqual(result["profile"], "base")
        self.assertEqual(result["missing_markers"], [])

    def test_trap_input_profile_requires_mount_and_input_verify_markers(self) -> None:
        text = "\n".join(boot_log.TRAP_INPUT_REQUIRED_MARKERS)
        result = boot_log.validate_boot_log_text(text, profile="trap-input")
        self.assertTrue(result["ok"])
        self.assertIn("POOLEOS_LAB_INPUT_VERIFY_PASS", result["required_markers"])
        self.assertIn("POOLEOS_LAB_TRAP_ABI_BOUNDARY_PASS", result["required_markers"])
        missing = boot_log.validate_boot_log_text("\n".join(boot_log.REQUIRED_MARKERS), profile="trap-input")
        self.assertFalse(missing["ok"])
        self.assertIn("POOLEOS_LAB_SHARED_MOUNT_PASS", missing["missing_markers"])

    def test_boot_log_contract_rejects_missing_markers(self) -> None:
        result = boot_log.validate_boot_log_text("POOLEOS_LAB_BOOT_START\n")
        self.assertFalse(result["ok"])
        self.assertIn("POOLEOS_LAB_BOOT_DONE", result["missing_markers"])

    def test_validate_boot_log_cli_writes_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "serial.log"
            out = Path(tmp) / "boot_validation.json"
            log.write_text("\n".join(boot_log.TRAP_INPUT_REQUIRED_MARKERS), encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                code = validate_boot_log.main([str(log), "--profile", "trap-input", "--out", str(out)])
            self.assertEqual(code, 0)
            schema = __import__("json").loads((ROOT / "specs" / "boot-log.schema.json").read_text(encoding="utf-8"))
            artifact = __import__("json").loads(out.read_text(encoding="utf-8"))
            self.assertEqual(validate_json(artifact, schema), [])
            self.assertEqual(artifact["profile"], "trap-input")

    def test_overlay_smoke_script_contains_required_markers(self) -> None:
        script = ROOT / "lab-os" / "buildroot" / "external" / "board" / "pooleos_lab" / "rootfs_overlay" / "usr" / "bin" / "pooleos-lab-smoke"
        text = script.read_text(encoding="utf-8")
        for marker in boot_log.REQUIRED_MARKERS:
            self.assertIn(marker, text)
        self.assertIn("POOLEOS_LAB_TRAP_ABI_BOUNDARY_PASS", text)
        init_script = ROOT / "lab-os" / "buildroot" / "external" / "board" / "pooleos_lab" / "rootfs_overlay" / "etc" / "init.d" / "S99pooleos-lab"
        init_text = init_script.read_text(encoding="utf-8")
        for marker in ("POOLEOS_LAB_AUTOSTART_START", "POOLEOS_LAB_SHARED_MOUNT_PASS", "POOLEOS_LAB_AUTOSTART_DONE"):
            self.assertIn(marker, init_text)


if __name__ == "__main__":
    unittest.main()
