import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from runtime import native_input_lifetime as oracle
from tools import native_input_lifetime_probe as probe


def fixture(retired, focused=False):
    w,h=1024,768
    pixels=bytearray(bytes.fromhex('D3DFDF')*(w*h))
    def fill(x,y,width,height,color):
        row=bytes.fromhex(color)*width
        for yy in range(y,y+height):
            at=(yy*w+x)*3;pixels[at:at+len(row)]=row
    fill(0,0,w,40,'F7FAF9');fill(0,h-32,w,32,'F7FAF9')
    fill(16,48,592,352,'508D78' if focused else '829090')
    fill(17,49,590,350,'172B24');fill(24,84,16,12,'DCE9E3')
    peer=1-retired;x,y=(704,72) if peer==0 else (688,264)
    fill(x,y,304,176,'829090');fill(x+1,y+28,302,147,'F8FAF9')
    fill(x+10,y+6,20,8,'253E37');fill(x+8,y+36,16,10,'293B35')
    if focused:fill(12,h-3,120,3,'508D78')
    return f'P6\n{w} {h}\n255\n'.encode()+pixels


class InputLifetimeTests(unittest.TestCase):
    def test_boundary_requires_no_implicit_focus_and_empty_surviving_draft(self):
        for target in (0,1):
            for focused in (False,True):
                data=fixture(target,focused)
                result=oracle.boundary(data,target,focused)
                self.assertEqual(result['peer_draft']['rows_verified'],2)
                self.assertEqual(result['implicit_focus_absent'],not focused)
                with self.assertRaises(ValueError):oracle.boundary(data,target,not focused)
        data=fixture(1)
        for x,y,color in ((16,48,'508D78'),(704,72,'508D78'),(12,765,'508D78'),
                           (688,264,'F8FAF9'),(712,204,'293B35'),(607,399,'172B24')):
            raw=bytearray(data);at=data.index(b'255\n')+4+(y*1024+x)*3
            raw[at:at+3]=bytes.fromhex(color)
            with self.assertRaises(ValueError):oracle.boundary(bytes(raw),1)

    def test_oracle_rejects_ambiguous_targets_focus_and_bad_pixels(self):
        for target,focused in ((True,False),(2,False),(0,1),(0,None)):
            with self.assertRaises(ValueError):oracle.boundary(fixture(0),target,focused)
        for data in (fixture(0)[:-1],b'P5\n1024 768\n255\n'+bytes(1024*768*3)):
            with self.assertRaises(ValueError):oracle.boundary(data,0)
        for x,y in ((-1,0),(1024,0),(0,768),(False,1)):
            with self.assertRaises(ValueError):oracle.pixel(fixture(0),x,y)

    def test_only_two_exact_command_ranges_use_serial_and_keep_device_counts_distinct(self):
        for batch in (1,4):
            interaction=probe.LifetimeInteraction(batch)
            connection=Mock();connection.send.side_effect=lambda data:len(data)
            injected=[];interaction.inject=lambda codes:injected.extend(codes)
            try:
                interaction.wrap(connection)
                controls=interaction.controls
                self.assertEqual([c['target'] for c in controls],[1,0])
                self.assertEqual(b''.join(c['command'] for c in controls),b'fault numbers\rstop text\r')
                for n,c in enumerate(controls):
                    interaction.step=interaction.sent=c['start']
                    interaction.send_ready();connection.send.assert_not_called()
                    interaction.allowed.add(n)
                    before=len(interaction.serial_controls)
                    for _ in c['command']:interaction.send_ready()
                    self.assertEqual(bytes(interaction.serial_controls[before:]),c['command'])
                    self.assertEqual(interaction.step,c['end'])
                    self.assertEqual(interaction.keyboard_bytes,0)
                    self.assertEqual(injected,[])
                    connection.send.reset_mock()
                    interaction.send_ready();connection.send.assert_not_called()
                self.assertEqual(len(interaction.serial_controls),24)
            finally:interaction.close()

    def test_control_ranges_require_ordered_immediate_status_commands(self):
        payload=b'fault numbers\rstatus numbers\rstop text\rstatus text\r'
        self.assertEqual(len(oracle.controls(payload)),2)
        for bad in (payload.replace(b'status numbers',b'echo x'),b'X'+payload,
                    b'stop text\rstatus text\rfault numbers\rstatus numbers\r'):
            with self.assertRaises(ValueError):oracle.controls(bad)

    def test_native_key_is_sent_once_and_failed_observation_does_not_reinject(self):
        state=probe.LifetimeProbe(Path('unused'))
        state.step=4;state.width=1024;state.height=768;state.x=788;state.y=276;state.left=True
        interaction=SimpleNamespace(sustained_evidence=True,step=0,controls=[dict(start=0,target=1)],inject=Mock())
        client=Mock()
        with patch.object(probe.time,'monotonic',return_value=1):state.tick(client,interaction,b'')
        interaction.inject.assert_called_once_with([0x2a,0x1e,0x9e])
        with patch.object(probe.time,'monotonic',return_value=1.3):state.tick(client,interaction,b'')
        client.execute.assert_not_called()
        with patch.object(probe.time,'monotonic',return_value=1.7),patch.object(Path,'read_bytes',return_value=b'partial'):
            state.tick(client,interaction,b'')
        self.assertEqual(state.step,4);self.assertTrue(state.pending)
        interaction.inject.assert_called_once()
        state.captures=state.MAX_CAPTURES
        with patch.object(probe.time,'monotonic',return_value=2.1):
            with self.assertRaisesRegex(ValueError,'capture bound'):state.tick(client,interaction,b'')
        with patch.object(probe.time,'monotonic',return_value=14):
            with self.assertRaises(TimeoutError):state.tick(client,interaction,b'')
        self.assertEqual(state.deadline,13)

    def test_all_new_execution_inputs_are_bound_without_kernel_authority_growth(self):
        from tools.qualify_native_user_entry import source_bindings
        bound=source_bindings()
        for path in ('native/userspace/src/desktop/input_lifetime_tests.rs',
                     'runtime/native_input_lifetime.py','tools/native_input_lifetime_probe.py',
                     'tools/qualify_native_input_lifetime.py','tests/test_native_input_lifetime.py'):
            self.assertIn(path,bound)
        root=Path(__file__).resolve().parents[1]
        adapter=(root/'native/userspace/src/process/windows.rs').read_text()
        self.assertIn('self.input',adapter)
        self.assertIn('.lifetime_boundary(queues, &mut self.manager, old_focus)',adapter)
        self.assertEqual(probe.LifetimeProbe.MAX_CAPTURES,192)
        self.assertEqual(probe.LifetimeProbe.ACTION_SECONDS,12)


if __name__=='__main__':unittest.main()
