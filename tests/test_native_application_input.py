import copy
import unittest
from pathlib import Path
from runtime import native_application_input as frames, native_app_session as apps
from tools import native_application_input_probe as probe

ROOT=Path(__file__).resolve().parents[1]


def fixture(expected,w=1280,h=800):
    pixels=bytearray(frames.PAPER*(w*h))
    for app,rows in expected.items():
        x,y=(w-312,108) if app==0 else (w-328,300)
        for row,text in rows.items():
            bitmap=frames.row_bytes(text)
            for line in range(16):
                at=((y+row*16+line)*w+x)*3
                pixels[at:at+864]=bitmap[line*864:(line+1)*864]
    return f'P6\n{w} {h}\n255\n'.encode()+pixels


class ApplicationInputTests(unittest.TestCase):
    def test_exact_pixels_include_both_drafts_results_and_blank_padding(self):
        expected=probe.actions()[-1]['expected'];data=fixture(expected)
        result=frames.inspect_rows(data,expected)
        self.assertEqual(result['rows_verified'],16)
        self.assertEqual(result['pixels_verified'],73728)
        for position in (0,10,287):
            bad=bytearray(data);offset=data.index(b'255\n')+4+((108+6*16)*1280+968+position)*3
            bad[offset]^=1
            with self.assertRaises(ValueError):frames.inspect_rows(bytes(bad),expected)
        bad=copy.deepcopy(expected);bad[1][6]='4 7'
        with self.assertRaises(ValueError):frames.inspect_rows(data,bad)
        bad=copy.deepcopy(expected);bad[0][2]='Bytes                  4'
        with self.assertRaises(ValueError):frames.inspect_rows(data,bad)

    def test_oracle_rejects_wrong_types_dimensions_truncation_and_unknown_glyphs(self):
        data=fixture({0:{6:'new',7:''}})
        for expected in ({},[],{True:{6:'new'}},{2:{0:''}},{0:{8:''}},{0:{0:'Z'}},{0:{0:'x'*25}}):
            with self.assertRaises(ValueError):frames.inspect_rows(data,expected)
        for raw in (data[:-1],b'P5\n1280 800\n255\n'+data.split(b'\n',3)[-1],b'P6\n10 10\n255\n'+bytes(300)):
            with self.assertRaises(ValueError):frames.inspect_rows(raw,{0:{6:'new'}})

    def test_challenge_checks_held_repeat_overflow_recovery_and_app_state_independence(self):
        actions=probe.actions()
        self.assertLess(len(actions),128)
        self.assertEqual([a['focus'] for a in actions if a['focus'] is not None],[1,0])
        hold=next(a for a in actions if a['label']=='hold-key-and-shift')
        self.assertEqual(hold['codes'],[0x2a,0x1e,0x3b,0xbb])
        self.assertNotIn(0x9e,hold['codes']);self.assertNotIn(0xaa,hold['codes'])
        self.assertEqual(next(a for a in actions if a['label']=='release-held-keys')['codes'],[0x9e,0xaa])
        held=next(a for a in actions if a['label']=='held-repeat-suppressed')
        self.assertEqual(held['codes'],[0x1e,0x2a,0x04,0x84])
        self.assertEqual(held['expected'][0][6],'draftA')
        self.assertEqual(held['expected'][1][6],'3')
        self.assertTrue(any(a['expected'][1][0]=='Job failed' and a['expected'][1][6]=='Input limit' for a in actions))
        self.assertEqual(actions[-1]['expected'][1][3],'Sum                   10')
        for action in actions:frames.inspect_rows(fixture(action['expected']),action['expected'])

    def test_compact_shell_case_preserves_four_wait_jobs_and_both_lifetimes(self):
        from tools.qualify_native_windows import lifecycle_barriers, WindowInteraction
        case=frames.compact_scenario(apps.scenario('0123456789abcdef'))
        self.assertLess(len(case.sent),400)
        self.assertEqual(case.sent.count(b'start text\r'),2)
        self.assertEqual(case.sent.count(b'start numbers\r'),2)
        self.assertEqual(case.sent.count(b'numbers /numbers.csv\r'),2)
        self.assertIn(b'text /numbers.csv\r',case.sent)
        self.assertEqual(len(lifecycle_barriers(case.sent)),6)
        self.assertTrue(case.sent.endswith(b'exit\r'))
        for batch in (1,4):
            interaction=WindowInteraction(batch,True,True)
            try:
                self.assertEqual(interaction.payload,interaction.case.sent)
                self.assertEqual(interaction.sustained_barrier,interaction.case.sent.index(b'start numbers\r')+len(b'start numbers\r'))
            finally:interaction.close()
        with self.assertRaises(ValueError):WindowInteraction(1,False,True)

    def test_native_profile_and_all_new_execution_inputs_are_bound(self):
        from tools.qualify_native_user_entry import source_bindings
        from runtime.native_user_program import profile_for
        self.assertEqual(profile_for('PooleWindowInput'),'PWCODE1')
        self.assertEqual(profile_for('PooleInputText'),'PUSERBIN1')
        self.assertEqual(profile_for('PooleInputNumbers'),'PUSERBIN1')
        bound=source_bindings()
        for path in ('runtime/native_application_input.py','tools/native_application_input_probe.py',
                     'tests/test_native_application_input.py','native/userspace/src/bin/window_input.rs',
                     'native/userspace/src/bin/input_text.rs','native/userspace/src/bin/input_numbers.rs',
                     'native/userspace/src/desktop/application_input/tests.rs','native/userspace/src/desktop/publisher/interactive/tests.rs'):
            self.assertIn(path,bound)
        source=(ROOT/'tools/qualify_native_app_session.py').read_text()
        self.assertIn('if args.surface_input and not args.surface_lifecycle:',source)
        self.assertIn("'CONSOLE':'PooleWindowInput','TEXT':'PooleInputText','NUMBERS':'PooleInputNumbers'",source)

    def test_input_kernel_layout_is_explicit_without_changing_legacy_or_total_budget(self):
        from unittest.mock import patch
        from tools import qualify_native_kernel_entry as entry
        class Captured(Exception):pass
        for features,enabled in (((),False),(('development-window-lifecycle',),False),
                                 (('development-window-input',),True),
                                 (('development-window-input','development-applications-bad-file'),True)):
            with patch.object(entry,'_run',side_effect=Captured) as run:
                with self.assertRaises(Captured):entry._build_product(Path('cargo'),{},Path('unused'),features=features)
                flags=run.call_args.kwargs['env']['CARGO_ENCODED_RUSTFLAGS']
                self.assertEqual('__poole_window_input_profile=1' in flags,enabled)
        with patch.object(entry,'_run') as run:
            with self.assertRaises(entry.QualificationError):entry._build_product(Path('cargo'),{},Path('unused'),features=('development-window-input','unreviewed'))
            run.assert_not_called()
        linker=(ROOT/'native/kernel/linker.ld').read_text()
        self.assertIn('DEFINED(__poole_window_input_profile) ? 0x1C000',linker)
        self.assertIn('DEFINED(__poole_window_capacity_profile) ? 0x1A000',linker)
        self.assertIn('__poole_image_end <= 0xD0000',linker)
        self.assertIn('development-window-input = ["development-window-lifecycle"]',(ROOT/'native/kernel/Cargo.toml').read_text())

    def test_completed_focus_motion_is_not_reinjected_while_waiting_for_paint(self):
        from types import SimpleNamespace
        from unittest.mock import Mock, patch
        state=probe.InputProbe(Path('unused'))
        state.actions=[next(a for a in probe.actions() if a['focus']==1)]
        state.sent=True;state.focus_phase=3;state.deadline=100
        client=Mock();interaction=Mock();pointer=SimpleNamespace(w=1280,x=1044,y=276,left=False)
        capture=Mock();capture.read_bytes.return_value=b'partial repaint'
        with patch.object(probe.time,'monotonic',return_value=1), patch.object(state,'capture',return_value=capture) as take, patch.object(probe.oracle,'inspect_rows',side_effect=ValueError):
            state.tick(client,interaction,pointer)
            take.assert_called_once_with(client)
        client.execute.assert_not_called()
        interaction.inject.assert_not_called()
        self.assertEqual(state.focus_phase,3)
        self.assertEqual(state.index,0)
        self.assertEqual(state.deadline,100)

    def test_keyboard_action_is_sent_once_and_capture_budget_stays_bounded(self):
        from unittest.mock import Mock, patch
        state=probe.InputProbe(Path('unused'));client=Mock();interaction=Mock()
        with patch.object(probe.time,'monotonic',return_value=1):state.tick(client,interaction,None)
        interaction.inject.assert_called_once_with(state.actions[0]['codes'])
        self.assertEqual(state.sample,1.6)
        with patch.object(probe.time,'monotonic',return_value=1.3):state.tick(client,interaction,None)
        interaction.inject.assert_called_once()
        client.execute.assert_not_called()
        state.captures=256
        with self.assertRaisesRegex(ValueError,'capture bound'):state.capture(client)
        with patch.object(probe.time,'monotonic',return_value=14):
            with self.assertRaises(TimeoutError):state.tick(client,interaction,None)
        self.assertEqual(state.deadline,13)


if __name__=='__main__':unittest.main()
