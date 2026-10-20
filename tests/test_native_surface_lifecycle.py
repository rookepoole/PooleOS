import ast
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime import native_app_session as apps, native_windows as frames
from tools import qualify_native_windows as windows
from tests.test_native_windows import markers

ROOT=Path(__file__).resolve().parents[1]


def lifecycle_markers(bad=False):
    result=[]
    for line in markers(bad):
        event=next((e for e in ('START','RUN','RETIRE','ADMIT') if line.startswith('POOLEOS:APPS '+e+' ')),None)
        if event:
            v=apps.parse(line,event)
            if event=='START':v.update(console_bytes=24577,image_pages=v['image_pages']+6)
            elif event=='RUN' and v['live_mask']&4:v['pages']+=6
            elif event=='RETIRE' and v['task']==2:v['released_pages']+=6
            elif event=='ADMIT':v['handle']=(v['generation']<<32)|0x50000|(2*(v['task']-4)+1)
            line='POOLEOS:APPS '+event+' contract=PAPPSESSION1'+''.join(f' {k}={v[k]}' for k in apps.FIELDS[event].split())+' cpl=3 production=0'
        result.append(line)
    return result


def synthetic_frame(visible):
    # Synthetic regions test the independent oracle, never native rendering.
    w,h=1024,768
    pixels=bytearray(bytes.fromhex('D3DFDF')*(w*h))
    def fill(x,y,width,height,color):
        for yy in range(y,y+height):
            a=(yy*w+x)*3;pixels[a:a+width*3]=bytes.fromhex(color)*width
    fill(0,0,w,32,'F7FAF9');fill(0,h-32,w,32,'F7FAF9');fill(24,84,100,2,'DCE9E3')
    for present,(x,y) in zip(visible,((w-320,72),(w-336,264))):
        if present:
            fill(x+1,y+28,302,147,'F8FAF9');fill(x+10,y+6,108,2,'253E37');fill(x+8,y+36,100,2,'293B35')
    return f'P6\n{w} {h}\n255\n'.encode()+pixels


class SurfaceLifecycleTests(unittest.TestCase):
    def test_profile_requires_exact_observer_aware_parent_handles(self):
        for bad in (False,True):
            m=lifecycle_markers(bad)
            options=dict(bad_file=bad,file_waits=True,windows=True,window_capacity=True,surface_lifecycle=True)
            self.assertTrue(apps.validate_markers(m,**options)['surface_lifecycle'])
            self.assertGreater(apps.negative_controls(m,**options),100)
            with self.assertRaises(ValueError):apps.validate_markers(m,**dict(options,surface_lifecycle=False))
            with self.assertRaises(ValueError):apps.validate_markers(m,**dict(options,window_capacity=False))
            for invalid in (None,1,'true'):
                with self.assertRaises(ValueError):apps.validate_markers(m,**dict(options,surface_lifecycle=invalid))

    def test_frame_requires_each_live_peer_and_no_retired_pixels(self):
        for visibility in ((True,True),(True,False),(False,True),(False,False)):
            data=synthetic_frame(visibility)
            self.assertEqual(len(frames.inspect_ppm(data,expected=visibility)['application_surfaces_observed']),sum(visibility))
            for other in ((True,True),(True,False),(False,True),(False,False)):
                if other!=visibility:
                    with self.assertRaises(ValueError):frames.inspect_ppm(data,expected=other)
        data=synthetic_frame((False,False));header,pixels=data.rsplit(b'\n',1)
        for x,y,color in ((704,72,'508D78'),(714,78,'253E37'),(712,108,'293B35'),(705,100,'F8FAF9')):
            changed=bytearray(pixels);at=(y*1024+x)*3;changed[at:at+3]=bytes.fromhex(color)
            with self.assertRaises(ValueError):frames.inspect_ppm(header+b'\n'+changed,expected=(False,False))
        for invalid in ([False,False],(0,0),(),None):
            with self.assertRaises(ValueError):frames.inspect_ppm(data,expected=invalid)

    def test_six_barriers_block_single_and_batched_injection_until_observed(self):
        class Socket:
            def close(self):pass
        for batch in (1,4):
            i=windows.WindowInteraction(batch,True);injected=[]
            try:
                i.inject=injected.append;i.wrap(Socket());i.pointer_done=True
                self.assertEqual(len(i.surface_barriers),6)
                self.assertEqual([(v['event'],v['task'],v['generation']) for v in i.surface_barriers.values()],
                    [('RETIRE',5,1),('ADMIT',5,2),('RETIRE',4,1),('ADMIT',4,2),('RETIRE',4,2),('RETIRE',5,2)])
                while i.step<len(i.case.steps):
                    if i.step in i.surface_barriers:
                        before=(i.step,i.sent,i.expected,len(injected))
                        i.send_ready();self.assertEqual(i.sock.send(b'x'),0)
                        self.assertEqual((i.step,i.sent,i.expected,len(injected)),before)
                        self.assertEqual(i.case.sent[i.step-1:i.step],b'\r')
                        i.observed_surfaces.add(i.step)
                    i.send_ready()
                self.assertEqual(i.observed_surfaces,set(i.surface_barriers))
                self.assertEqual((i.sent,i.keyboard_bytes),(573,573));self.assertEqual(i.expected,i.case.expected)
            finally:i.close()
        i=windows.WindowInteraction()
        try:self.assertEqual(i.surface_barriers,{})
        finally:i.close()

    def test_probe_requires_exact_generation_pixels_and_acknowledged_transcript(self):
        i=windows.WindowInteraction(4,True)
        try:
            i.step=next(iter(i.surface_barriers));i.expected=b'expected';i.received=bytearray()
            barrier=i.surface_barriers[i.step]
            good=(next(m for m in lifecycle_markers() if 'APPS RETIRE ' in m and ' task=5 generation=1 ' in m)+'\n').encode()
            wrong=good.replace(b'generation=1',b'generation=2')
            with tempfile.TemporaryDirectory() as temporary:
                probe=windows.SurfaceProbe(Path(temporary))
                class Client:
                    data=synthetic_frame((True,True))
                    calls=0
                    def execute(self,command,args):
                        self.calls+=1
                        self.assert_command=command
                        Path(args['filename']).write_bytes(self.data)
                client=Client()
                with patch.object(windows.local.native_console,'split_output',return_value=(b'',b'expect')),patch.object(windows.time,'monotonic',return_value=1):
                    probe.tick(client,i,good)
                self.assertEqual(client.calls,0)
                with patch.object(windows.local.native_console,'split_output',return_value=(b'',b'expected')),patch.object(windows.time,'monotonic',return_value=2):
                    probe.tick(client,i,wrong);self.assertEqual(client.calls,0)
                    probe.tick(client,i,good);self.assertEqual(client.calls,1)
                self.assertEqual(i.observed_surfaces,set())
                client.data=synthetic_frame(barrier['visible'])
                with patch.object(windows.local.native_console,'split_output',return_value=(b'',b'expected')),patch.object(windows.time,'monotonic',return_value=3):
                    probe.tick(client,i,good);probe.tick(client,i,good)
                self.assertEqual(client.calls,2);self.assertEqual(len(probe.evidence),1)
                self.assertEqual(i.observed_surfaces,{i.step})
                self.assertEqual(probe.evidence[0]['generation'],1)
                i.observed_surfaces.clear()
                with patch.object(windows.time,'monotonic',return_value=14):
                    with self.assertRaises(TimeoutError):probe.tick(client,i,good)
                with patch.object(windows.local.native_console,'split_output',return_value=(b'',b'forged')),patch.object(windows.time,'monotonic',return_value=4):
                    with self.assertRaises(ValueError):probe.tick(client,i,good)
        finally:i.close()

    def test_all_positive_and_hostile_oracles_propagate_opt_in(self):
        from runtime import native_app_session as apps
        for name in ('qualify_native_windows','qualify_native_local_console','qualify_native_app_session',
                     'launch_native_virtualbox','launch_native_userspace_iso',
                     'qualify_native_input_lifetime','qualify_native_launch_desktop'):
            tree=ast.parse((ROOT/f'tools/{name}.py').read_text())
            calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in ('validate_markers','negative_controls') and isinstance(n.func.value,ast.Name) and n.func.value.id in ('apps','probe')]
            # The window runner accesses the same oracle through local.apps.
            calls += [n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in ('validate_markers','negative_controls') and isinstance(n.func.value,ast.Attribute) and n.func.value.attr=='apps']
            self.assertTrue(calls,name)
            for call in calls:
                if name=='qualify_native_app_session':
                    self.assertEqual(len([k for k in call.keywords if k.arg=='surface_lifecycle']),1,name)
                else:
                    self.assertFalse(any(k.arg=='surface_lifecycle' for k in call.keywords),name)
                    unpacked=[k.value for k in call.keywords if k.arg is None]
                    self.assertEqual(len(unpacked),1,name)
                    self.assertIsInstance(unpacked[0],ast.Name)
                    self.assertEqual(unpacked[0].id,'options',name)
            if name!='qualify_native_app_session':
                adapters=[n.value for n in ast.walk(tree) if isinstance(n,ast.Assign)
                    and any(isinstance(t,ast.Name) and t.id=='options' for t in n.targets)]
                self.assertTrue(adapters,name)
                expected={'profile_options','launch_failure_options'} if name in (
                    'launch_native_userspace_iso','qualify_native_launch_desktop') else {'profile_options'}
                self.assertEqual({a.func.attr for a in adapters},expected,name)
                for adapter in adapters:
                    self.assertIsInstance(adapter,ast.Call)
                    self.assertIsInstance(adapter.func,ast.Attribute)
                    self.assertIn(adapter.func.attr,expected,name)
                    self.assertEqual([ast.dump(a) for a in adapter.args],[ast.dump(ast.Name(id='report',ctx=ast.Load()))])
        for report,expected in (({},False),({'surface_lifecycle':False},False),({'surface_lifecycle':True},True)):
            self.assertIs(apps.profile_options(report)['surface_lifecycle'],expected)
        for bad in (None,0,1,'true'):
            with self.assertRaises(ValueError):apps.profile_options({'surface_lifecycle':bad})

    def test_new_sources_are_bound_and_service_profile_is_not_generalized(self):
        from tools.qualify_native_user_entry import source_bindings
        from tools.qualify_native_user_programs import bindings
        from runtime.native_user_program import profile_for
        execution=source_bindings();programs=bindings()
        for path in ('native/userspace/src/desktop/lifecycle.rs','native/userspace/src/bin/window_lifecycle.rs'):
            self.assertIn(path,execution);self.assertIn(path,programs)
        for path in ('tests/test_native_surface_lifecycle.py','native/kernel/src/capability_ipc/process/observer_tests.rs','runtime/native_surface_lifecycle.py'):
            self.assertIn(path,execution)
        self.assertEqual(profile_for('PooleWindowLifecycle'),'PWCODE1')
        self.assertEqual(profile_for('PooleWindowLifecycle.exe'),'PUSERBIN1')
        self.assertEqual(profile_for('PooleWindowConsole'),'PUSERBIN1')


if __name__=='__main__':unittest.main()
