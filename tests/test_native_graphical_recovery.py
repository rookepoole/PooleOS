"""Host controls for the diagnostic runner; fixtures are not native execution."""
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from runtime import native_app_session as apps
from tools import launch_native_userspace_iso as launcher
from tools import qualify_native_launch_desktop as gui


def profile():
    return dict.fromkeys(('file_waits', 'window_surfaces', 'window_capacity',
        'surface_lifecycle', 'surface_input', 'launch_shell_admission',
        'launch_console_admission', 'diagnostic_only', 'launch_failure'), True) | {'serial_recovery': False}


class NativeGraphicalRecoveryTests(unittest.TestCase):
    def test_exact_diagnostic_profile_and_ordinary_boundary(self):
        report = profile()
        self.assertEqual(apps.launch_failure_options(report), dict(gui.OPTIONS, launch_failure=True))
        with self.assertRaises(ValueError):
            apps.profile_options(report)
        for field in report:
            for value in (None, 0, 1, 'true', not report[field]):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    apps.launch_failure_options(dict(report, **{field: value}))
            missing = dict(report)
            del missing[field]
            with self.assertRaises(ValueError):
                apps.launch_failure_options(missing)
        with self.assertRaises(ValueError):
            apps.launch_failure_options([])

    def test_preview_entry_never_opts_into_diagnostics(self):
        with patch.object(launcher, '_check_qualification', return_value='sentinel') as check:
            self.assertEqual(launcher.check_preview(Path('receipt')), 'sentinel')
            check.assert_called_once_with(Path('receipt'), diagnostic_launch_failure=False)
        for value in (None, 0, 1, 'true'):
            with patch.object(launcher, 'local_file') as read, self.assertRaises(ValueError):
                launcher._check_qualification(Path('receipt'), diagnostic_launch_failure=value)
            read.assert_not_called()

    def test_diagnostic_actions_are_fresh_and_terminal_drafts_survive(self):
        case, actions = gui.scenario('0123456789abcdef', launch_failure=True)
        self.assertNotIn(b'start ', case.sent)
        self.assertNotIn(b'launch failed', case.expected)
        self.assertEqual([(v['app'], v['generation'], v.get('failure', False)) for v in actions.values()],
            [('text', 1, False), ('numbers', 1, False), ('numbers', 2, True),
             ('numbers', 3, False), ('text', 2, True), ('text', 3, False)])
        for step, action in actions.items():
            self.assertTrue(case.sent[:step].endswith(b'echo '+action['draft'].encode()))
            self.assertIn(action['draft'].encode()+b'\r\n', case.steps[step][1])
        self.assertGreaterEqual(case.sent.count(b'cat /version.txt'), 2)
        for value in (None, 1, 'true'):
            with self.assertRaises(ValueError):
                gui.scenario('0123456789abcdef', launch_failure=value)

    def test_diagnostic_virtualbox_is_rejected_before_receipt_or_output(self):
        with patch('sys.argv', ['gui', '--receipt', 'absent', '--work-dir', 'absent',
                '--backend', 'virtualbox', '--virtualbox', 'absent', '--launch-failure']), \
                patch('sys.stderr'), patch.object(launcher, '_check_qualification') as check, \
                self.assertRaises(SystemExit) as error:
            gui.main()
        self.assertEqual(error.exception.code, 2)
        check.assert_not_called()

    def probe_case(self, mouse, admitted=False, published=True):
        app, task = ('text', 4) if mouse else ('numbers', 5)
        action = dict(app=app, generation=2, mouse=mouse, draft='GUI', failure=True)
        interaction = SimpleNamespace(ready=True, step=10, completed=set(),
                                      actions={10: action}, inject=Mock())
        probe = gui.Probe(Path('unused'))
        probe.step, probe.phase, probe.deadline = 10, 3, 20
        probe.left = mouse
        capture = Mock()
        capture.name = 'capture.ppm'
        capture.read_bytes.return_value = b'fixture'
        records = ['POOLEOS:APPS FAILED fixture'] if published else []
        if admitted:
            records.append('POOLEOS:APPS ADMIT fixture')
        patches = [patch.object(probe, 'capture', return_value=capture),
            patch.object(gui.time, 'monotonic', side_effect=[1, 2, 3]),
            patch.object(gui.pixels, 'frame', return_value=(1280, 800, b'')),
            patch.object(gui.local.window_frames, 'inspect_ppm', return_value={}),
            patch.object(gui, 'inspect_header', return_value={}),
            patch.object(gui.local, 'digest', return_value='fixture'),
            patch.object(gui.local.native_session, 'extract_markers', return_value=records),
            patch.object(gui.local.apps, 'parse', return_value=dict(task=task, generation=2, published=1))]
        return probe, interaction, patches

    def test_held_mouse_and_key_require_failure_pixels_then_release_and_absent_inspection(self):
        from contextlib import ExitStack
        for mouse in (False, True):
            probe, interaction, patches = self.probe_case(mouse)
            client = Mock()
            with ExitStack() as stack:
                mocks = [stack.enter_context(p) for p in patches]
                for phase in (4, 5, 5):
                    probe.tick(client, interaction, b'')
                    self.assertEqual(probe.phase, phase)
            self.assertEqual(interaction.completed, {10})
            self.assertEqual([v['phase'] for v in probe.evidence], [3, 4, 5])
            name = 'Text' if mouse else 'Numbers'
            self.assertEqual([c.args[1] for c in mocks[4].call_args_list],
                [name+': launch failed / no surface']*2+[name+': absent / no surface'])
            self.assertEqual(sum(e.get('held_repeat', False) for e in probe.events), 1)
            self.assertFalse(probe.left)
            self.assertEqual(sum(e.get('fresh_release', False) for e in probe.events), int(mouse))
            self.assertEqual(mocks[3].call_args.kwargs['expected'], (not mouse, mouse))

    def test_failure_requires_kernel_publication_and_rejects_admitted_image(self):
        from contextlib import ExitStack
        for admitted, published in ((True, True), (False, False)):
            probe, interaction, patches = self.probe_case(False, admitted, published)
            with ExitStack() as stack:
                mocks = [stack.enter_context(p) for p in patches]
                if admitted:
                    with self.assertRaisesRegex(ValueError, 'was admitted'):
                        probe.tick(Mock(), interaction, b'')
                else:
                    probe.tick(Mock(), interaction, b'')
                mocks[4].assert_not_called()
            self.assertFalse(interaction.completed)
            self.assertFalse(probe.evidence)
        probe, interaction, patches = self.probe_case(False, admitted=True)
        probe.phase = 0
        with ExitStack() as stack:
            mocks = [stack.enter_context(p) for p in patches]
            with self.assertRaisesRegex(ValueError, 'before fresh graphical input'):
                probe.tick(Mock(), interaction, b'')
            mocks[0].assert_not_called()
        self.assertFalse(probe.action_boundaries)
        self.assertFalse(probe.events)
        interaction.inject.assert_not_called()

    def test_failure_label_checks_every_pixel_and_blank_padding(self):
        label = 'Numbers: launch failed / no surface'
        width, height = 1000, 600
        raw = bytearray(bytes.fromhex('F7FAF9')*(width*height))
        for i, char in enumerate(label):
            for y in range(14):
                for x in range(10):
                    if gui.HEADER_GLYPHS[char][y//2] & (1 << (4-x//2)):
                        at = ((8+y)*width+144+i*12+x)*3
                        raw[at:at+3] = bytes.fromhex('253E37')
        prefix = b'P6\n1000 600\n255\n'
        self.assertEqual(gui.inspect_header(prefix+raw, label)['pixels_verified'], len(label)*192)
        with self.assertRaises(ValueError):
            gui.inspect_header(prefix+raw, 'Numbers: admitted / surface')
        raw[((8+15)*width+144+11)*3] ^= 1
        with self.assertRaises(ValueError):
            gui.inspect_header(prefix+raw, label)


if __name__ == '__main__':
    unittest.main()
