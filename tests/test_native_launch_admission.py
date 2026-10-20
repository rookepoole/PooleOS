import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, call, patch

from runtime import native_app_session as apps
from tests.test_native_surface_lifecycle import lifecycle_markers
from tools import qualify_native_app_session as qualification, qualify_native_kernel_entry as entry

ROOT = Path(__file__).resolve().parents[1]
OPTIONS = dict(file_waits=True, windows=True, window_capacity=True,
               surface_lifecycle=True, launch_session=True)
PROFILE = dict(file_waits=True, window_surfaces=True, window_capacity=True,
               surface_lifecycle=True, surface_input=True,
               launch_shell_admission=True, launch_console_admission=True)


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
    def test_profile_adapter_preserves_ordinary_and_explicit_launch_accounting(self):
        self.assertEqual(apps.profile_options(PROFILE), OPTIONS)
        self.assertEqual(apps.profile_options({}), dict(file_waits=False, windows=False,
            window_capacity=False, surface_lifecycle=False, launch_session=False))
        self.assertTrue(apps.validate_markers(markers(), **apps.profile_options(PROFILE))["launch_session"])
        ordinary = dict(PROFILE, launch_shell_admission=False, launch_console_admission=False)
        with self.assertRaises(ValueError):
            apps.validate_markers(markers(), **apps.profile_options(ordinary))
        shell_only = dict(PROFILE, launch_console_admission=False)
        self.assertEqual(apps.profile_options(shell_only), OPTIONS)
        self.assertEqual(PROFILE["launch_console_admission"], True)

    def test_profile_adapter_rejects_missing_prerequisites_wrong_types_and_diagnostics(self):
        for key in ("file_waits", "window_surfaces", "window_capacity", "surface_lifecycle",
                    "surface_input", "launch_shell_admission"):
            for candidate in (dict(PROFILE, **{key: False}), {k:v for k,v in PROFILE.items() if k != key}):
                with self.subTest(key=key), self.assertRaises(ValueError):
                    apps.profile_options(candidate)
        for key in (*PROFILE, "diagnostic_only", "serial_recovery"):
            for wrong in (1, 0, "true", None, []):
                with self.subTest(key=key, wrong=wrong), self.assertRaises(ValueError):
                    apps.profile_options(dict(PROFILE, **{key: wrong}))
        for key in ("diagnostic_only", "serial_recovery"):
            for candidate in ({key: True}, dict(PROFILE, **{key: True})):
                with self.assertRaises(ValueError):
                    apps.profile_options(candidate)
        for wrong in (None, [], True):
            with self.assertRaises(ValueError):
                apps.profile_options(wrong)

    def test_all_desktop_callers_use_the_explicit_profile_for_positive_and_hostile_oracles(self):
        import ast
        for path in ("launch_native_userspace_iso", "launch_native_virtualbox",
                     "qualify_native_local_console", "qualify_native_windows",
                     "qualify_native_input_lifetime", "qualify_native_launch_desktop"):
            tree = ast.parse((ROOT/"tools"/(path+".py")).read_text())
            calls = 0
            for function in (v for v in tree.body if isinstance(v, ast.FunctionDef)):
                selected = []
                for node in ast.walk(function):
                    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                        continue
                    owner = node.func.value
                    is_apps = (isinstance(owner, ast.Name) and owner.id == "apps" or
                               isinstance(owner, ast.Attribute) and owner.attr == "apps")
                    if is_apps and node.func.attr in ("validate_markers", "negative_controls"):
                        selected.append(node)
                if selected:
                    self.assertTrue(any(isinstance(n, ast.Assign) and
                        any(isinstance(t, ast.Name) and t.id == "options" for t in n.targets) and
                        isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Attribute) and
                        n.value.func.attr == "profile_options" for n in ast.walk(function)), path)
                for node in selected:
                    self.assertTrue(any(k.arg is None and isinstance(k.value, ast.Name) and
                                        k.value.id == "options" for k in node.keywords), path)
                calls += len(selected)
            self.assertGreater(calls, 0, path)

    def test_application_hold_probe_uses_no_desktop_shortcut_as_neutral_key(self):
        from tools.native_application_input_probe import actions
        hold, = [a for a in actions() if a["label"] == "hold-key-and-shift"]
        self.assertEqual(hold["codes"], [0x2a, 0x1e, 0x58, 0xd8])
        self.assertEqual(hold["expected"][0][6], "draftA")

    def test_gui_backend_validation_precedes_preview_or_output_access(self):
        from tools import qualify_native_launch_desktop as gui
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)/"absent"
            base = ["qualifier", "--receipt", str(output), "--work-dir", str(output)]
            for flags in (["--backend", "virtualbox"], ["--visible"]):
                with patch("sys.argv", base+flags), patch("sys.stderr"), \
                        patch.object(gui.local, "check_preview") as preview, \
                        self.assertRaises(SystemExit) as error:
                    gui.main()
                self.assertEqual(error.exception.code, 2)
                preview.assert_not_called()
                self.assertFalse(output.exists())

    def test_gui_repeat_probe_keeps_key_held_until_observed_and_then_releases_for_inspect(self):
        from types import SimpleNamespace
        from tools import qualify_native_launch_desktop as gui
        action = dict(app="numbers", generation=1, mouse=False, draft="GUI")
        interaction = SimpleNamespace(ready=True, step=10, completed=set(),
                                      actions={10: action}, inject=Mock())
        probe = gui.Probe(Path("unused"))
        probe.step, probe.phase, probe.deadline = 10, 3, 20
        frame = Mock(name="frame")
        frame.name = "capture.ppm"
        frame.read_bytes.return_value = b"fixture"
        with patch.object(probe, "capture", return_value=frame), \
                patch.object(gui.time, "monotonic", side_effect=[1, 2, 3]), \
                patch.object(gui.pixels, "frame", return_value=(1280, 800, b"")), \
                patch.object(gui.pixels, "inspect_rows", return_value={}), \
                patch.object(gui, "inspect_header", return_value={}) as header, \
                patch.object(gui.local, "digest", return_value="fixture"), \
                patch.object(gui.local.native_session, "extract_markers", return_value=["POOLEOS:APPS ADMIT fixture"]), \
                patch.object(gui.local.apps, "parse", return_value=dict(task=5, generation=1)):
            probe.tick(Mock(), interaction, b"")
            self.assertEqual(probe.phase, 4)
            interaction.inject.assert_called_once_with([0x3d])
            probe.tick(Mock(), interaction, b"")
            self.assertEqual(probe.phase, 5)
            self.assertEqual(interaction.completed, set())
            interaction.inject.assert_called_with([0xbd, 0x2a, 0x3d, 0xbd, 0xaa])
            probe.tick(Mock(), interaction, b"")
        self.assertEqual(interaction.completed, {10})
        self.assertEqual([v["phase"] for v in probe.evidence], [3, 4, 5])
        self.assertEqual([c.args[1] for c in header.call_args_list],
                         ["Numbers: admitted / surface"]*2+["Numbers: running / surface"])

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
        self.assertEqual(manifest["features"]["development-launch-desktop"], ["development-launch-session"])
        self.assertEqual(manifest["features"]["default"], [])
        startup = (ROOT / "native/kernel/src/user_entry/startup.rs").read_text()
        self.assertIn("Self::bounded(code, entry_offset, MAX_CODE_PAGES)", startup)
        self.assertIn("Self::bounded(code, entry_offset, super::LAUNCH_SHELL_CODE_PAGES)", startup)
        dispatch = (ROOT / "native/kernel/src/user_root_probe/peer_driver/interactive.rs").read_text()
        self.assertIn('if i == 3 {\n            return checked!(Program::launch_shell', dispatch)
        arguments = (ROOT / "native/kernel/src/user_root_probe/peer_driver/interactive/applications.rs").read_text()
        self.assertIn('cfg!(feature = "development-launch-session")', arguments)
        self.assertIn('b"launch-shell"', arguments)
        self.assertIn('cfg!(feature = "development-launch-desktop")', arguments)
        self.assertIn('b"launch-console"', arguments)
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

    def test_desktop_selector_preserves_linker_limits_and_rejects_diagnostics(self):
        with tempfile.TemporaryDirectory() as temp:
            for features in (("development-launch-desktop",),
                             ("development-launch-desktop", "development-applications-bad-file")):
                with patch("tools.native_build_space.require_space", return_value={}), patch.object(entry, "_run") as run:
                    with self.assertRaisesRegex(entry.QualificationError, "artifact is missing"):
                        entry._build_product(Path("cargo"), {}, Path(temp)/str(len(features)), features=features)
                flags = run.call_args.kwargs["env"]["CARGO_ENCODED_RUSTFLAGS"]
                for symbol in ("launch_session", "window_input", "window_capacity", "windows", "desktop", "apps"):
                    self.assertIn(f"--defsym=__poole_{symbol}_profile=1", flags)
            with patch("tools.native_build_space.require_space", return_value={}), patch.object(entry, "_run") as run:
                with self.assertRaisesRegex(entry.QualificationError, "unreviewed"):
                    entry._build_product(Path("cargo"), {}, Path(temp)/"bad",
                        features=("development-launch-desktop", "development-serial-recovery"))
                run.assert_not_called()

    def test_console_requires_separately_qualified_shell_before_output(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)/"absent"
            base = ["qualifier", "--work-dir", str(output), "--program-dir", str(output),
                    "--launch-console-dir", str(output), "--optical", "--windows",
                    "--window-capacity", "--surface-lifecycle", "--surface-input"]
            with patch("sys.argv", base), patch("sys.stderr"), self.assertRaises(SystemExit) as error:
                qualification.main()
            self.assertEqual(error.exception.code, 2)
            self.assertFalse(output.exists())

    def test_three_independent_builds_are_all_revalidated(self):
        sources = [(Path(n), [(n, key)], {n: True}) for n, key in
                   (("ordinary", "CONSOLE"), ("shell", "CONSOLE_CLIENT"), ("console", "CONSOLE"))]
        for changed in range(3):
            values = [v[2] for v in sources]
            values[changed] = {"drift": True}
            with patch.object(qualification, "program_inputs", side_effect=values), self.assertRaises(ValueError):
                qualification.revalidate_program_inputs(sources, {})
        with patch.object(qualification, "program_inputs", side_effect=[v[2] for v in sources]) as check:
            qualification.revalidate_program_inputs(sources, {})
            self.assertEqual(check.call_count, 3)

    def test_gui_scenario_removes_all_start_commands_and_preserves_drafts(self):
        from tools.qualify_native_launch_desktop import scenario
        case, actions = scenario("0123456789abcdef")
        self.assertEqual(len(actions), 4)
        self.assertNotIn(b"start ", case.sent)
        self.assertEqual([(v["app"], v["generation"], v["mouse"]) for v in actions.values()],
                         [("text", 1, True), ("numbers", 1, False),
                          ("numbers", 2, False), ("text", 2, True)])
        for step, action in actions.items():
            self.assertTrue(case.sent[:step].endswith(b"echo "+action["draft"].encode()))
            self.assertEqual(case.steps[step][0], b"\r")
            self.assertIn(action["draft"].encode()+b"\r\n", case.steps[step][1])
        with self.assertRaises(ValueError):
            scenario("not-a-nonce")

    def test_launch_pixel_oracle_checks_every_label_pixel(self):
        from tools.qualify_native_launch_desktop import HEADER_GLYPHS, inspect_header
        width, height = 1000, 600
        raw = bytearray(bytes.fromhex("F7FAF9")*(width*height))
        label = "Numbers: running / surface"
        for i, char in enumerate(label):
            for y in range(14):
                for x in range(10):
                    if HEADER_GLYPHS[char][y//2] & (1 << (4-x//2)):
                        at = ((8+y)*width+144+i*12+x)*3
                        raw[at:at+3] = bytes.fromhex("253E37")
        prefix = b"P6\n1000 600\n255\n"
        self.assertEqual(inspect_header(prefix+raw, label)["pixels_verified"], len(label)*192)
        for wrong in ("Numbers: admitted / surface", "Text: running / surface", "", "?"*36):
            with self.assertRaises(ValueError):
                inspect_header(prefix+raw, wrong)
        raw[((8+15)*width+144+11)*3] ^= 1
        with self.assertRaises(ValueError):
            inspect_header(prefix+raw, label)

    def test_gui_barrier_waits_without_serial_or_key_injection(self):
        from tools.qualify_native_launch_desktop import Interaction
        interaction = Interaction()
        try:
            interaction.step = next(iter(interaction.actions))
            interaction.inject = lambda _: self.fail("blocked draft injected a key")
            interaction.send_ready()
            self.assertTrue(interaction.ready)
            self.assertEqual(interaction.sent, 0)
            self.assertEqual(interaction.completed, set())
        finally:
            interaction.close()

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
