import unittest
from pathlib import Path
from unittest.mock import patch
from runtime import native_app_session as apps, native_files as files
from tests.test_native_kernel_transfer import valid_markers


def fixture(bad=False):
    # Synthetic parser fixture only. All six images, pages and roots are distinct
    # logical roles; none of these made-up observations count as guest evidence.
    markers = valid_markers()[:29]
    markers[23] = markers[23].replace('trap_scenario=0', 'trap_scenario=23')
    markers.append(apps.FILE_MARKER)
    sizes, pages = [1800,2800,4000,15136,5877,5884], [13,13,13,16,14,14]
    roots = [0x100000+i*0x10000 for i in range(6)]
    def emit(event, values):
        markers.append('POOLEOS:APPS '+event+' contract=PAPPSESSION1'+
                       ''.join(' '+n+'='+str(values[n]) for n in apps.FIELDS[event].split())+' cpl=3 production=0')
    emit('START', dict(bad_file=int(bad), image_pages=sum(pages), firmware_pages=6,
                      **dict(zip((n+'_bytes' for n in ('init','files','console','shell','text','numbers')),sizes)),
                      **{f'root{i}':roots[i] for i in range(6)}))
    live, owned, generations, retired, flushes = set(range(4)), set(range(6)), [0,0], 0, 0
    calls, ticks = [0]*6, [0]*6
    def launch(task, dispatch):
        gen = generations[task-4]+1
        emit('HANDOFF', dict(task=task,generation=gen,control=(gen<<32)|0x10001,
                            files=(gen<<32)|0x10002,startup_files=((gen+int(bad and task==5))<<32)|0x10002,
                            bytes=176,entered=0,dispatches=dispatch))
        emit('ADMIT',dict(task=task,generation=gen,sequence=gen,handle=(gen<<32)|0x50000|(task-3),
                         root=roots[task],owned_pages=pages[task],dispatches=dispatch))
        live.add(task); owned.add(task); generations[task-4]=gen
        calls[task]=ticks[task]=0
    def retire(task, dispatch, outcome):
        nonlocal retired, flushes
        emit('RETIRE',dict(task=task,generation=generations[task-4] if task>=4 else 1,
                          outcome=outcome,calls=calls[task],released_pages=pages[task],dispatches=dispatch))
        live.remove(task);owned.remove(task);retired+=1;flushes+=int(outcome==4<<32)
    for dispatch in range(64,577,64):
        if dispatch==128: launch(4,70);launch(5,80)
        if dispatch==256: retire(5,200,(2<<32)|6)
        if dispatch==320: launch(5,270)
        if dispatch==384: retire(4,330,4<<32)
        if dispatch==448: launch(4,390)
        if dispatch==512:
            retire(4,460,4<<32);retire(5,461,4<<32)
            retire(2,470,1<<32);retire(3,480,1<<32)
        for j in live: calls[j]+=10;ticks[j]+=100
        emit('RUN',dict(dispatches=dispatch,cr3_writes=2*dispatch+flushes,extra_flushes=flushes,
                        pages=sum(pages[j] for j in owned),live_mask=sum(1<<j for j in live),
                        generation4=generations[0],generation5=generations[1],retired=retired,unused=0,
                        **{f'calls{i}':calls[i] for i in range(6)},**{f'ticks{i}':ticks[i] for i in range(6)}))
    return markers


class NativeAppSessionTests(unittest.TestCase):
    def test_six_roles_exact_handoff_restart_fault_and_survival_are_required(self):
        for bad in (False,True):
            result=apps.validate_markers(fixture(bad),bad_file=bad)
            self.assertEqual(len(result['handoffs']),4)
            self.assertEqual(len(result['retires']),6)
            self.assertEqual(result['program_bytes'],[1800,2800,4000,15136,5877,5884])
            self.assertEqual(result['useful_applications'],0)
            self.assertTrue(result['native_execution_requires_guest_binding'])
            self.assertFalse(result['iso_built'] or result['production_ready'])
            self.assertGreater(apps.negative_controls(fixture(bad),bad_file=bad),150)
            with self.assertRaises(ValueError): apps.validate_markers(fixture(bad),bad_file=not bad)

    def test_startup_grants_cannot_be_omitted_duplicated_reordered_or_substituted(self):
        markers=fixture();i=next(i for i,m in enumerate(markers) if 'APPS HANDOFF ' in m)
        cases=[markers[:i]+markers[i+1:],markers[:i]+[markers[i]]+markers[i:]]
        swapped=markers.copy();swapped[i],swapped[i+1]=swapped[i+1],swapped[i];cases.append(swapped)
        for old,new in [('entered=0','entered=1'),('bytes=176','bytes=184'),
                        ('generation=1','generation=2'),('control=4295032833','control=0')]:
            changed=markers.copy();self.assertIn(old,changed[i]);changed[i]=changed[i].replace(old,new);cases.append(changed)
        for case in cases:
            with self.assertRaises(ValueError): apps.validate_markers(case)

    def test_console_close_reply_can_precede_shell_exit_but_not_live_app_cleanup(self):
        markers=fixture()
        result=apps.validate_markers(markers)
        self.assertEqual([r['task'] for r in result['retires'][-2:]],[2,3])
        i=next(i for i,m in enumerate(markers) if 'APPS RETIRE ' in m and ' task=2 ' in m)
        j=next(i for i,m in enumerate(markers) if 'APPS RETIRE ' in m and ' task=4 generation=2 ' in m)
        early=markers.copy();entry=early.pop(i).replace('dispatches=470','dispatches=459');early.insert(j,entry)
        with self.assertRaisesRegex(ValueError,'live children'):apps.validate_markers(early)

    def test_retired_image_cannot_resume_or_retain_pages_and_root_alias_rejects(self):
        markers=fixture()
        for old,new in [('live_mask=3 ','live_mask=7 '),('pages=26 ','pages=40 '),
                        ('calls5=30 ','calls5=31 '),('root5=1376256','root5=1048576')]:
            changed=markers.copy()
            if old.startswith('root'):
                self.assertIn(old,changed[30]);changed[30]=changed[30].replace(old,new)
            else:
                self.assertIn(old,changed[-1]);changed[-1]=changed[-1].replace(old,new)
            with self.assertRaises(ValueError): apps.validate_markers(changed)

    def test_exact_challenge_exercises_changed_inputs_and_continues_after_fault(self):
        case=apps.scenario('0123456789abcdef')
        self.assertIn(b'text: bytes=24 words=6 lf=6\r\n',case.expected)
        self.assertIn(b'numbers: count=5 sum=50 min=3 max=21\r\n',case.expected)
        self.assertIn(b'text: bytes=0 words=0 lf=0\r\n',case.expected)
        self.assertIn(b'numbers: invalid data\r\n',case.expected)
        self.assertIn(b'echo 0123456789abcdef\r',case.sent)
        self.assertLess(case.sent.index(b'fault numbers\r'),case.sent.rindex(b'text /readme.txt\r'))
        for name in (b'text',b'numbers'):self.assertEqual(case.sent.count(b'start '+name+b'\r'),2)
        self.assertTrue(case.expected.endswith(b'Bye.\r\n'))
        self.assertEqual(apps.text_result(files.NUMBERS),b'text: bytes=24 words=6 lf=6\r\n')

    def test_stale_file_grant_preserves_text_shell_and_numbers_lifecycle(self):
        case=apps.scenario('0'*16,bad_file=True)
        self.assertEqual(case.expected.count(b'numbers: file service unavailable\r\n'),6)
        self.assertNotIn(b'numbers: count=',case.expected)
        self.assertIn(b'numbers: fault 0x00000006\r\n',case.expected)
        self.assertIn(apps.text_result(files.README),case.expected)
        self.assertIn(files.VERSION,case.expected)

    def test_nonce_malformed_extra_overflow_and_console_only_observations_reject(self):
        for nonce in ('','A'*16,'0'*15,'z'*16):
            with self.assertRaises(ValueError):apps.scenario(nonce)
        line=fixture()[30]
        for bad in (line+' extra=1',line.replace('cpl=3','cpl=0'),line.replace('production=0','production=1'),
                    line.replace('bad_file=0','bad_file=-1'),line.replace('bad_file=0','bad_file='+str(1<<64))):
            with self.assertRaises(ValueError):apps.parse(bad,'START')
        for markers in ([],['fake']*54,apps.scenario('0'*16).expected.decode().splitlines()):
            with self.assertRaises(ValueError):apps.validate_markers(markers)

    def test_sources_are_bound_even_before_new_native_files_are_staged(self):
        from tools.qualify_native_user_entry import source_bindings
        with patch('tools.qualify_native_user_entry.subprocess.check_output',return_value=''):
            bound=source_bindings()
        for name in ('native/kernel/src/development_apps.rs',
                     'native/kernel/src/user_root_probe/peer_driver/interactive/applications.rs',
                     'runtime/native_app_session.py','tools/qualify_native_app_session.py',
                     'tests/test_native_app_session.py'):
            self.assertIn(name,bound)
        self.assertEqual(len(apps.PROGRAMS),6)
        self.assertEqual(len({name for name,_ in apps.PROGRAMS}),6)

    def test_restart_session_enables_fresh_owner_calibration_cache_like_first_launch(self):
        source=(Path(__file__).resolve().parents[1]/'native/kernel/src/user_root_probe/peer_driver.rs').read_text()
        for name in ('new_program','restart_program'):
            body=source.split('fn '+name+'(',1)[1].split('spawn_driver::build_program(',1)[0]
            self.assertEqual(body.count('Timer::new('),1)
            self.assertEqual(body.count('.reuse_session_calibration()'),1)
            self.assertLess(body.index('Timer::new('),body.index('.reuse_session_calibration()'))


if __name__=='__main__':unittest.main()
