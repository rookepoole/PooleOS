import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from runtime import native_virtualbox_mouse as mouse

IDENTITY = '11111111-2222-4333-8444-555555555555'


def owner(work=None):
    work = work or mouse.ROOT / 'outputs/test-pointer'
    return SimpleNamespace(identity=IDENTITY, name='PooleOS-Preview-' + IDENTITY,
        config=work / 'owned.vbox', work=work, create_completed=True, admission=('iso', 1),
        info=Mock(return_value={'VMState': 'running'}), checked=Mock())


def ack(**changes):
    result = dict(identity=IDENTITY, sequence=0, dx=3, dy=-4, left=1, relative=True, unlocked=True)
    result.update(changes)
    return json.dumps(result)


def client(vm=None, run=None):
    with patch.object(mouse.PointerClient, 'check_shell'):
        result = mouse.PointerClient(vm or owner(), Path('D:/Apps/VirtualBox/VBoxManage.exe'), run=run or Mock())
    result.check_shell = Mock()
    return result


class VirtualBoxMouseTests(unittest.TestCase):
    def test_motion_rejects_out_of_range_aliases_and_noncanonical_types(self):
        for values in [(97,0,False),(0,-97,False),(True,0,False),(0,1.0,False),(0,0,1),('3',0,False)]:
            with self.assertRaises(ValueError):mouse.validate_motion(*values)
        for values in [(-96,96,False),(0,0,True)]:mouse.validate_motion(*values)

    def test_ack_requires_exact_identity_sequence_types_and_unlock(self):
        self.assertTrue(mouse.validate_ack(ack(),IDENTITY,0,3,-4,True)['unlocked'])
        for change in [dict(identity='other'),dict(sequence=1),dict(sequence=False),dict(dx=True),
                       dict(left=True),dict(relative=1),dict(unlocked=False),dict(extra=0)]:
            with self.assertRaises(ValueError):mouse.validate_ack(ack(**change),IDENTITY,0,3,-4,True)
        for text in ['[]','null','{}',' ' * 4097]:
            with self.assertRaises(ValueError):mouse.validate_ack(text,IDENTITY,0,3,-4,True)

    def test_unadmitted_or_stopped_machine_cannot_open_pointer_channel(self):
        for field,value in [('create_completed',False),('admission',None)]:
            vm=owner();setattr(vm,field,value)
            with self.assertRaises(ValueError):mouse.PointerClient(vm,Path('VBoxManage.exe'))
        vm=owner();vm.info.return_value={'VMState':'paused'}
        with self.assertRaises(ValueError):mouse.PointerClient(vm,Path('VBoxManage.exe'))

    def test_event_is_owned_bounded_and_recorded_only_after_unlock(self):
        run=Mock(return_value=SimpleNamespace(returncode=0,stderr=b'',stdout=ack().encode()))
        c=client(run=run);c.move(3,-4,True)
        command=run.call_args.args[0]
        self.assertEqual(command[command.index('-Identity')+1],IDENTITY)
        self.assertEqual(command[command.index('-Name')+1],c.owner.name)
        self.assertEqual(command[command.index('-Config')+1],str(c.owner.config))
        self.assertNotIn('-ExecutionPolicy',command)
        self.assertEqual(run.call_args.kwargs['timeout'],5)
        self.assertEqual(len(c.records),1);self.assertTrue(c.left)
        self.assertNotIn('identity',c.records[0]);self.assertTrue(c.records[0]['unlocked'])

    def test_unknown_effect_failure_prevents_retry_or_false_progress(self):
        bad=[SimpleNamespace(returncode=1,stderr=b'',stdout=b'{}'),
             SimpleNamespace(returncode=0,stderr=b'unexpected',stdout=ack().encode()),
             SimpleNamespace(returncode=0,stderr=b'',stdout=ack(unlocked=False).encode()),
             SimpleNamespace(returncode=0,stderr=b'',stdout=b'x'*4097)]
        for result in bad:
            c=client(run=Mock(return_value=result))
            with self.assertRaises(ValueError):c.move(3,-4,True)
            self.assertTrue(c.failed);self.assertEqual(c.records,[]);self.assertFalse(c.left)
            with self.assertRaises(ValueError):c.move(3,-4,True)
            self.assertEqual(c.run.call_count,1)
        c=client(run=Mock(side_effect=subprocess.TimeoutExpired('owned helper',5)))
        with self.assertRaises(subprocess.TimeoutExpired):c.move(3,-4,True)
        with self.assertRaises(ValueError):c.move(3,-4,True)
        self.assertEqual(c.run.call_count,1)

    def test_event_quota_and_shell_mutation_fail_before_launch(self):
        c=client();c.records=[{}]*96
        with self.assertRaises(ValueError):c.move(0,0,False)
        c.run.assert_not_called()
        c=client();c.check_shell=Mock(side_effect=ValueError('changed shell'))
        with self.assertRaises(ValueError):c.move(0,0,False)
        c.run.assert_not_called()
        with patch.object(mouse.vbox,'bounded_read',return_value=b'not the pinned executable'):
            with self.assertRaises(ValueError):mouse.PointerClient.check_shell(c)

    def test_adapter_accepts_only_two_relative_axes_and_optional_left(self):
        c=client();c.move=Mock()
        base={'events':[{'type':'rel','data':{'axis':'x','value':3}},
                        {'type':'rel','data':{'axis':'y','value':-4}}]}
        c.execute('input-send-event',base);c.move.assert_called_once_with(3,-4,False)
        cases=[]
        v=copy.deepcopy(base);v['events'][0]['type']='abs';cases.append(v)
        v=copy.deepcopy(base);v['events'][1]['data']['axis']='x';cases.append(v)
        v=copy.deepcopy(base);v['events'][0]['data']['extra']=1;cases.append(v)
        v=copy.deepcopy(base);v['events'].append({'type':'key','data':{}});cases.append(v)
        v=copy.deepcopy(base);v['events'].append({'type':'btn','data':{'button':'right','down':True}});cases.append(v)
        for values in cases:
            with self.assertRaises(ValueError):c.execute('input-send-event',values)
        with self.assertRaises(ValueError):c.execute('reset',{})
        self.assertEqual(c.move.call_count,1)

    def test_capture_path_escape_rejects_and_conversion_preserves_every_pixel(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as directory:
            work=Path(directory);vm=owner(work);c=client(vm)
            for path in (work.parent/'pointer-before.ppm',work/'arbitrary.ppm',
                         work.parent/'lifecycle-00.ppm',work/'lifecycle-06.ppm',
                         work/'lifecycle-0.ppm',work/'lifecycle-000.ppm',work/'lifecycle-00.png'):
                with self.assertRaises(ValueError):c.execute('screendump',dict(filename=str(path),format='ppm'))
            vm.checked.assert_not_called()
            raw=bytes([11,43,79])*(1024*768)
            def capture(*args):Image.frombytes('RGB',(1024,768),raw).save(args[-1])
            vm.checked.side_effect=capture
            for name in ['pointer-before.ppm']+[f'lifecycle-{n:02}.ppm' for n in range(6)]:
                target=work/name;c.execute('screendump',dict(filename=str(target),format='ppm'))
                self.assertEqual(target.read_bytes(),b'P6\n1024 768\n255\n'+raw)
                self.assertEqual(vm.checked.call_args.args[:3],('controlvm',IDENTITY,'screenshotpng'))

    @unittest.skipUnless(os.name=='nt','Windows COM helper rejection test')
    def test_actual_helper_rejects_identity_and_registry_mismatch_before_vm_access(self):
        for name,runtime,message in [('not-owned','D:/Apps/VirtualBox','Invalid owned identity'),
                ('PooleOS-Preview-'+IDENTITY,'C:/not-the-admitted-runtime','COM runtime path changed')]:
            result=subprocess.run([str(mouse.SHELL),'-NoProfile','-NonInteractive','-File',str(mouse.SCRIPT),
                '-Identity',IDENTITY,'-Name',name,'-Config',str(mouse.ROOT/'outputs/nonexistent.vbox'),
                '-Runtime',runtime,'-Dx','0','-Dy','0','-Left','0','-Sequence','0'],
                capture_output=True,timeout=5,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            self.assertEqual(result.returncode,1,result.stderr)
            self.assertEqual(json.loads(result.stdout.decode('utf-8-sig'))['error'],message)

    def test_new_helper_and_profile_are_execution_bound(self):
        from tools.qualify_native_user_entry import source_bindings
        bound=source_bindings()
        for path in ('runtime/native_virtualbox_mouse.py','tools/native_virtualbox_mouse.ps1',
                     'specs/native-virtualbox-mouse-profile.json','tests/test_native_virtualbox_mouse.py'):
            self.assertIn(path,bound)

    def test_pointer_callback_failure_still_cleans_only_the_owned_vm(self):
        from tools import qualify_native_local_console as local
        vm=owner();vm.checked.return_value='7.2.20r175154'
        vm.create=Mock();vm.start=Mock()
        vm.cleanup=Mock(return_value=dict(stopped=True,unregistered=True,prior_registrations_unchanged=True,errors=[]))
        listener=Mock();listener.accept.side_effect=BlockingIOError
        listener.getsockname.return_value=('127.0.0.1',12345)
        interaction=SimpleNamespace(sock=None,step=0)
        callback=Mock(side_effect=ValueError('injected pointer failure'));result={}
        with tempfile.TemporaryDirectory() as directory, patch.object(local.vbox,'verify_runtime',return_value={}), \
                patch.object(local.vbox,'Command',return_value=SimpleNamespace(records=[])), \
                patch.object(local.vbox,'OwnedVm',return_value=vm),patch.object(local,'listener_socket',return_value=listener):
            with self.assertRaisesRegex(ValueError,'injected pointer failure'):
                local.vbox_run({'window_surfaces':True},Path('iso'),Path(directory),interaction,result,
                               Path('VBoxManage.exe'),True,callback)
        callback.assert_called_once_with(vm,b'');vm.cleanup.assert_called_once();listener.close.assert_called_once()
        self.assertTrue(result['runtime_unchanged'] and result['cleanup']['unregistered'])


if __name__=='__main__':unittest.main()
