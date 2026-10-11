from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from tools import native_build_space as space
from tools import qualify_native_user_programs as programs


class NativeBuildSpaceTests(unittest.TestCase):
    def test_available_floor_is_inclusive_and_never_claims_reservation(self):
        with mock.patch.object(space.shutil, "disk_usage", return_value=SimpleNamespace(free=512)):
            record = space.require_space(Path.cwd(), 512)
        self.assertEqual(record["available_bytes"], 512)
        self.assertFalse(record["space_reserved"] or record["retention_performed"])

    def test_shortfall_rejects_without_creating_destination(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "no" / "build"
            with mock.patch.object(space.shutil, "disk_usage", return_value=SimpleNamespace(free=511)):
                with self.assertRaisesRegex(ValueError, "insufficient build storage"):
                    space.require_space(path, 512)
            self.assertFalse(path.parent.exists())

    def test_uses_existing_destination_ancestor_not_unrelated_current_volume(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            with mock.patch.object(space.shutil, "disk_usage", return_value=SimpleNamespace(free=1024)) as usage:
                space.require_space(root / "nested" / "new", 512)
                usage.assert_called_once_with(root)
            self.assertFalse((root / "nested").exists())

    def test_invalid_floor_and_disk_observation_error_fail_closed(self):
        for invalid in (True, False, 0, -1, 1.5):
            with self.assertRaises(ValueError):
                space.require_space(Path.cwd(), invalid)
        with mock.patch.object(space.shutil, "disk_usage", side_effect=OSError("unavailable")):
            with self.assertRaises(OSError):
                space.require_space(Path.cwd())

    def test_user_qualifier_rejects_before_creating_output_and_binds_preflight(self):
        with tempfile.TemporaryDirectory(dir=programs.ROOT / "outputs") as temp:
            output = Path(temp) / "uncreated"
            with mock.patch("sys.argv", ["qualify", "--work-dir", str(output)]), \
                    mock.patch.object(programs, "require_space", side_effect=ValueError("insufficient build storage")), \
                    mock.patch.object(programs, "_toolchain") as toolchain:
                with self.assertRaisesRegex(ValueError, "insufficient build storage"):
                    programs.main()
                toolchain.assert_not_called()
            self.assertFalse(output.exists())
        self.assertIn("tools/native_build_space.py", programs.bindings())
        self.assertIn("tests/test_native_build_space.py", programs.bindings())


if __name__ == "__main__":
    unittest.main()
