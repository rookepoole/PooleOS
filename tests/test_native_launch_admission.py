import tempfile
import unittest
from pathlib import Path
from unittest.mock import call, patch

from runtime import native_app_session as apps
from tests.test_native_surface_lifecycle import lifecycle_markers
from tools import qualify_native_app_session as qualification, qualify_native_kernel_entry as entry

ROOT = Path(__file__).resolve().parents[1]
OPTIONS = dict(file_waits=True, windows=True, window_capacity=True,
               surface_lifecycle=True, launch_session=True)


def markers(bad=False):
    result = []
    for line in lifecycle_markers(bad):
        event = next((e for e in ("START", "RUN", "RETIRE")
                      if line.startswith("POOLEOS:APPS " + e + " ")), None)
        if event:
            value = apps.parse(line, event)
            if event == "START":
                value.update(shell_bytes=19464, image_pages=value["image_pages"] + 1)
            elif event == "RUN" and value["live_mask"] & 8:
                value["pages"] += 1
            elif event == "RETIRE" and value["task"] == 3:
                value["released_pages"] += 1
            line = ("POOLEOS:APPS " + event + " contract=PAPPSESSION1"
                    + "".join(f" {k}={value[k]}" for k in apps.FIELDS[event].split())
                    + " cpl=3 production=0")
        result.append(line)
    return result


class NativeLaunchAdmissionTests(unittest.TestCase):
    def test_opt_in_parser_requires_fifth_page_and_exact_accounting(self):
        for bad in (False, True):
            candidate = markers(bad)
            options = dict(OPTIONS, bad_file=bad)
            report = apps.validate_markers(candidate, **options)
            self.assertTrue(report["launch_session"])
            self.assertEqual(report["launch_shell_code_pages"], 5)
            self.assertFalse(report["native_plc1_control_verified"])
            self.assertGreater(apps.negative_controls(candidate, **options), 100)
            with self.assertRaises(ValueError):
                apps.validate_markers(candidate, **dict(options, launch_session=False))
            with self.assertRaises(ValueError):
                apps.validate_markers(lifecycle_markers(bad), **options)
            for replacement in ("shell_bytes=16384", "shell_bytes=20481"):
                changed = [line.replace("shell_bytes=19464", replacement) for line in candidate]
                with self.assertRaises(ValueError):
                    apps.validate_markers(changed, **options)
            for key in ("file_waits", "windows", "window_capacity", "surface_lifecycle"):
                with self.assertRaises(ValueError):
                    apps.validate_markers(candidate, **dict(options, **{key: False}))
            for invalid in (1, "true", None):
                with self.assertRaises(ValueError):
                    apps.validate_markers(candidate, **dict(options, launch_session=invalid))

    def test_fifth_page_cannot_disappear_from_start_running_or_retirement_totals(self):
        original = markers()
        for index, line in enumerate(original):
            event = next((e for e in ("START", "RUN", "RETIRE")
                          if line.startswith("POOLEOS:APPS " + e + " ")), None)
            if not event:
                continue
            values = apps.parse(line, event)
            key = "image_pages" if event == "START" else "pages" if event == "RUN" else "released_pages"
            if event == "RUN" and not values["live_mask"] & 8 or event == "RETIRE" and values["task"] != 3:
                continue
            values[key] -= 1
            changed = list(original)
            changed[index] = ("POOLEOS:APPS " + event + " contract=PAPPSESSION1"
                              + "".join(f" {k}={values[k]}" for k in apps.FIELDS[event].split())
                              + " cpl=3 production=0")
            with self.assertRaises(ValueError):
                apps.validate_markers(changed, **OPTIONS)

    def test_kernel_feature_selects_only_explicit_shell_slot_and_preserves_limits(self):
        import tomllib
        manifest = tomllib.loads((ROOT / "native/kernel/Cargo.toml").read_text())
        self.assertEqual(manifest["features"]["development-launch-session"], ["development-window-input"])
        self.assertEqual(manifest["features"]["default"], [])
        startup = (ROOT / "native/kernel/src/user_entry/startup.rs").read_text()
        self.assertIn("Self::bounded(code, entry_offset, MAX_CODE_PAGES)", startup)
        self.assertIn("Self::bounded(code, entry_offset, super::LAUNCH_SHELL_CODE_PAGES)", startup)
        dispatch = (ROOT / "native/kernel/src/user_root_probe/peer_driver/interactive.rs").read_text()
        self.assertIn('if i == 3 {\n            return checked!(Program::launch_shell', dispatch)
        arguments = (ROOT / "native/kernel/src/user_root_probe/peer_driver/interactive/applications.rs").read_text()
        self.assertIn('cfg!(feature = "development-launch-session")', arguments)
        self.assertIn('b"launch-shell"', arguments)
        user = (ROOT / "native/kernel/src/user_entry.rs").read_text()
        self.assertIn("MAX_CODE_PAGES: u64 = 4", user)
        self.assertIn("LAUNCH_SHELL_CODE_PAGES: u64 = 5", user)
        self.assertIn("MAX_IMAGE_CODE_PAGES: u64 = 7", user)
        linker = (ROOT / "native/kernel/linker.ld").read_text()
        self.assertIn("DEFINED(__poole_launch_session_profile) ? 0x1D000", linker)
        self.assertIn("DEFINED(__poole_window_input_profile) ? 0x1C000", linker)

    def test_build_selector_is_allowlisted_and_uses_matching_linker_feature(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "target"
            with patch("tools.native_build_space.require_space", return_value={}), patch.object(entry, "_run") as run:
                with self.assertRaisesRegex(entry.QualificationError, "artifact is missing"):
                    entry._build_product(Path("cargo"), {}, target, features=("development-launch-session",))
            self.assertIn("development-launch-session", run.call_args.args[0])
            flags = run.call_args.kwargs["env"]["CARGO_ENCODED_RUSTFLAGS"]
            for symbol in ("launch_session", "window_input", "window_capacity", "windows", "desktop", "apps"):
                self.assertIn(f"--defsym=__poole_{symbol}_profile=1", flags)
            with patch("tools.native_build_space.require_space", return_value={}), patch.object(entry, "_run") as run:
                with self.assertRaisesRegex(entry.QualificationError, "unreviewed"):
                    entry._build_product(Path("cargo"), {}, target,
                        features=("development-launch-session", "development-serial-recovery"))
                run.assert_not_called()

    def test_launch_qualifier_rejects_missing_input_and_mixed_diagnostics_before_output(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "uncreated"
            base = ["qualifier", "--work-dir", str(output), "--program-dir", str(output),
                    "--launch-shell-dir", str(output)]
            for flags in ([], ["--optical", "--windows", "--window-capacity",
                               "--surface-lifecycle", "--surface-input", "--serial-recovery"]):
                with patch("sys.argv", base + flags), patch("sys.stderr"), \
                        self.assertRaises(SystemExit) as error:
                    qualification.main()
                self.assertEqual(error.exception.code, 2)
                self.assertFalse(output.exists())

    def test_final_revalidation_keeps_original_and_replacement_builds_separate(self):
        ordinary = (Path("ordinary"), [("PooleAppShell", "CONSOLE_CLIENT")], {"build": "ordinary"})
        launch = (Path("launch"), [("PooleLaunchShell", "CONSOLE_CLIENT")], {"build": "launch"})
        env = {}
        with patch.object(qualification, "program_inputs", side_effect=[ordinary[2], launch[2]]) as check:
            qualification.revalidate_program_inputs([ordinary, launch], env)
            self.assertEqual(check.call_args_list, [call(ordinary[0], env, ordinary[1]),
                                                   call(launch[0], env, launch[1])])
        for results in ([{"changed": True}], [ordinary[2], {"changed": True}]):
            with patch.object(qualification, "program_inputs", side_effect=results), \
                    self.assertRaisesRegex(ValueError, "program input drift"):
                qualification.revalidate_program_inputs([ordinary, launch], env)
        with patch.object(qualification, "program_inputs", side_effect=FileNotFoundError("candidate")):
            with self.assertRaises(FileNotFoundError):
                qualification.revalidate_program_inputs([launch], env)
        with patch.object(qualification, "program_inputs", return_value=ordinary[2]) as check:
            qualification.revalidate_program_inputs([ordinary], env)
            check.assert_called_once_with(ordinary[0], env, ordinary[1])


if __name__ == "__main__":
    unittest.main()
