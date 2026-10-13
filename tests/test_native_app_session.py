import re
import unittest
from pathlib import Path
from unittest.mock import patch
from runtime import native_app_session as apps, native_files as files
from tests.test_native_kernel_transfer import valid_markers


def fixture(bad=False, file_controls=False):
    # Synthetic parser fixture only. All six images, pages and roots are distinct
    # logical roles; none of these made-up observations count as guest evidence.
    markers = valid_markers()[:29]
    markers[23] = markers[23].replace('trap_scenario=0', 'trap_scenario=23')
    markers.append(apps.FILE_MARKER)
    sizes, pages = [1800,2800,4000,15136,5877,5884], [13,13,13,16,14,14]
    if file_controls: sizes[4],pages[4]=2809,13
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
        process_slot=6-task if file_controls else task-3
        emit('ADMIT',dict(task=task,generation=gen,sequence=gen,handle=(gen<<32)|0x50000|process_slot,
                         root=roots[task],owned_pages=pages[task],dispatches=dispatch))
        live.add(task); owned.add(task); generations[task-4]=gen
        calls[task]=ticks[task]=0
    def retire(task, dispatch, outcome):
        nonlocal retired, flushes
        if file_controls and task==4:
            emit('REQUESTER',dict(task=task,generation=generations[task-4],queued=1,claimed=0,
                                 completed=0,detached=1,dispatches=dispatch))
        emit('RETIRE',dict(task=task,generation=generations[task-4] if task>=4 else 1,
                          outcome=outcome,calls=calls[task],released_pages=pages[task],dispatches=dispatch))
        live.remove(task);owned.remove(task);retired+=1;flushes+=int(outcome==4<<32)
    for dispatch in range(64,705 if file_controls else 577,64):
        if file_controls:
            if dispatch==128: launch(5,70);launch(4,80)
            if dispatch==256: retire(4,200,(1<<32)|85)
            if dispatch==320: launch(4,270)
            if dispatch==384: retire(4,330,(1<<32)|85)
            if dispatch==448: retire(5,390,(2<<32)|6)
            if dispatch==512: launch(5,460)
            if dispatch==576:
                retire(5,520,4<<32);retire(2,530,1<<32);retire(3,540,1<<32)
        else:
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


def claimed_fixture(bad=False):
    # Synthetic waiting/cancellation observations, not captured native events.
    result=[];extra_flushes=0
    for marker in fixture(bad,file_controls=True):
        if 'APPS REQUESTER ' in marker:
            v=apps.parse(marker,'REQUESTER')
            values=dict(task=4,generation=v['generation'],waiting=1,stale_wait_rejected=1,
                        service_task=1,service_generation=1,dispatches=v['dispatches'])
            result.append('POOLEOS:APPS CLAIMED contract=PAPPSESSION1'+''.join(' '+n+'='+str(values[n]) for n in apps.FIELDS['CLAIMED'].split())+' cpl=3 production=0')
            marker=marker.replace('queued=1 claimed=0','queued=0 claimed=1')
        elif 'APPS RETIRE ' in marker and ' task=4 ' in marker:
            marker=marker.replace('outcome=4294967381','outcome=17179869184');extra_flushes+=1
        elif 'APPS RUN ' in marker:
            for field in ('cr3_writes','extra_flushes'):
                marker=re.sub(' '+field+r'=([0-9]+)',lambda m:' '+field+'='+str(int(m[1])+extra_flushes),marker)
        result.append(marker)
    return result


def deferred_fixture(bad=False, boundary=False):
    markers = fixture(bad)[:31]
    pages, roots = [13,13,13,16,14,14], [0x100000+i*0x10000 for i in range(6)]
    live, owned, generations = set(range(4)), set(range(6)), [0,0]
    calls, ticks, cleaning = [0]*6, [0]*6, set()
    retired = flushes = 0
    def emit(event, values):
        markers.append('POOLEOS:APPS '+event+' contract=PAPPSESSION1'+
                       ''.join(' '+n+'='+str(values[n]) for n in apps.FIELDS[event].split())+' cpl=3 production=0')
    events = [(70,'launch',4),(80,'launch',5),(192 if boundary else 200,'defer',5),
              (470,'launch',5),(530,'defer',4),(790,'launch',4),(860,'defer',4),
              (1120,'defer',5),(1320,'exit',2),(1330,'exit',3)]
    for d,event,j in list(events):
        if event == 'defer': events.extend([(d+64,'retry',j),(d+192,'complete',j)])
    events.extend((d,'sample',0) for d in range(64,1473,64))
    # The dispatcher samples after a stop, but before the next cleanup poll.
    events.sort(key=lambda e:(e[0], 1 if e[1] in ('retry','complete') else 0))
    for d,event,j in events:
        if event == 'launch':
            gen=generations[j-4]+1
            emit('HANDOFF',dict(task=j,generation=gen,control=(gen<<32)|0x10001,
                 files=(gen<<32)|0x10002,startup_files=((gen+int(bad and j==5))<<32)|0x10002,
                 bytes=176,entered=0,dispatches=d))
            emit('ADMIT',dict(task=j,generation=gen,sequence=gen,handle=(gen<<32)|0x50000|(j-3),
                 root=roots[j],owned_pages=pages[j],dispatches=d))
            live.add(j);owned.add(j);generations[j-4]=gen;calls[j]=ticks[j]=0
        elif event in ('defer','retry','complete'):
            attempt={'defer':0,'retry':1,'complete':2}[event]
            value=dict(task=j,generation=generations[j-4],attempts=attempt,
                       next=d+(64 if attempt==0 else 128) if attempt<2 else 0,
                       pages=pages[j] if attempt<2 else 0,dispatches=d,admitted=1)
            markers.append('POOLEOS:CLEANUP '+event.upper()+' contract=PCLEANUP2'+
                           ''.join(' '+n+'='+str(value[n]) for n in apps.cleanup.FIELDS)+' cpl=0 production=0')
            if event=='defer':
                cleaning.add(j);flushes+=int(not (j==5 and generations[j-4]==1))
            if event=='complete': cleaning.remove(j)
        if event in ('complete','exit'):
            outcome=(1<<32) if j<4 else (2<<32)|6 if j==5 and generations[j-4]==1 else 4<<32
            emit('RETIRE',dict(task=j,generation=generations[j-4] if j>=4 else 1,
                 outcome=outcome,calls=calls[j],released_pages=pages[j],dispatches=d))
            live.remove(j);owned.remove(j);retired+=1
        if event=='sample':
            for k in live-cleaning: calls[k]+=10;ticks[k]+=100
            emit('RUN',dict(dispatches=d,cr3_writes=2*d+flushes,extra_flushes=flushes,
                 pages=sum(pages[k] for k in owned),live_mask=sum(1<<k for k in live),
                 generation4=generations[0],generation5=generations[1],retired=retired,unused=0,
                 **{f'calls{k}':calls[k] for k in range(6)},**{f'ticks{k}':ticks[k] for k in range(6)}))
    return markers


class NativeAppSessionTests(unittest.TestCase):
    def test_claimed_waiting_requesters_are_cancelled_and_detached_in_both_generations(self):
        for bad in (False,True):
            markers=claimed_fixture(bad)
            result=apps.validate_markers(markers,bad_file=bad,claimed_requester=True)
            self.assertEqual(len(result['claimed_waiters']),2)
            self.assertEqual([(r['queued'],r['claimed'],r['completed']) for r in result['requester_deaths']],[(0,1,0)]*2)
            self.assertTrue(result['kernel_injected_waiting_cancellation'])
            self.assertFalse(result['diagnostic_requester_is_useful_app'] or result['exhaustive_request_interleavings'])
            self.assertFalse(result['iso_built'] or result['production_ready'])
            self.assertGreater(apps.negative_controls(markers,bad_file=bad,claimed_requester=True),200)
        with self.assertRaises(ValueError):apps.validate_markers(fixture(file_controls=True),claimed_requester=True)
        with self.assertRaises(ValueError):apps.validate_markers(claimed_fixture(),file_controls=True,claimed_requester=True)

    def test_claimed_wait_observation_cannot_be_omitted_forged_or_reordered(self):
        markers=claimed_fixture()
        index=next(i for i,m in enumerate(markers) if 'APPS CLAIMED ' in m)
        candidates=[markers[:index]+markers[index+1:],markers[:index]+[markers[index]]+markers[index:]]
        for field in apps.FIELDS['CLAIMED'].split():
            changed=markers.copy();changed[index]=re.sub(' '+field+r'=([0-9]+)',lambda m:' '+field+'='+str(int(m[1])+1),changed[index]);candidates.append(changed)
        changed=markers.copy();changed[index],changed[index+1]=changed[index+1],changed[index];candidates.append(changed)
        for candidate in candidates:
            with self.assertRaises(ValueError):apps.validate_markers(candidate,claimed_requester=True)

    def test_claimed_requester_requires_pending_claim_not_completed_or_queued(self):
        markers=claimed_fixture()
        index=next(i for i,m in enumerate(markers) if 'APPS REQUESTER ' in m)
        for old,new in [('queued=0 claimed=1','queued=1 claimed=0'),('completed=0','completed=1'),('detached=1','detached=0')]:
            changed=markers.copy();changed[index]=changed[index].replace(old,new)
            with self.assertRaises(ValueError):apps.validate_markers(changed,claimed_requester=True)
        changed=markers.copy();changed[index+1]=changed[index+1].replace('outcome=17179869184','outcome=4294967381')
        with self.assertRaises(ValueError):apps.validate_markers(changed,claimed_requester=True)

    def test_claimed_request_scenario_waits_for_cancelled_diagnostics_and_checks_surviving_files(self):
        from tools.qualify_native_app_session import retirement_barriers
        for bad in (False,True):
            case=apps.file_control_scenario('0123456789abcdef',bad_file=bad,claimed_requester=True)
            self.assertEqual(len(case.sent),293)
            self.assertEqual(list(retirement_barriers(case.sent).values()),[(5,1),(5,2),(4,1),(4,2)])
            self.assertEqual(case.expected.count(b'text: cancelled\r\n'),2)
            self.assertEqual(case.sent.count(b'cat /version.txt\r'),3)
            self.assertNotIn(b'text: exit 0x00000055',case.expected)
            self.assertTrue(case.expected.endswith(b'Bye.\r\n'))

    def test_file_probe_requires_both_outstanding_requester_deaths_and_surviving_services(self):
        for bad in (False,True):
            markers=fixture(bad,file_controls=True)
            result=apps.validate_markers(markers,bad_file=bad,file_controls=True)
            self.assertEqual(len(result['requester_deaths']),2)
            self.assertTrue(result['file_controls'])
            self.assertFalse(result['iso_built'] or result['production_ready'])
            self.assertGreater(apps.negative_controls(markers,bad_file=bad,file_controls=True),200)
            with self.assertRaises(ValueError):apps.validate_markers(markers,bad_file=bad)
            wrong=markers.copy()
            index=next(i for i,m in enumerate(wrong) if 'APPS ADMIT ' in m)
            wrong[index]=wrong[index].replace('handle=4295294977','handle=4295294978')
            with self.assertRaises(ValueError):apps.validate_markers(wrong,bad_file=bad,file_controls=True)
        with self.assertRaises(ValueError):apps.validate_markers(fixture(),file_controls=True)

    def test_file_probe_rejects_completed_missing_forged_or_early_requester_retirement(self):
        markers=fixture(file_controls=True)
        index=next(i for i,m in enumerate(markers) if 'APPS REQUESTER ' in m)
        for old,new in [('queued=1','queued=0'),('claimed=0','claimed=1'),('completed=0','completed=1'),
                        ('detached=1','detached=0'),('task=4','task=5'),('generation=1','generation=2')]:
            changed=markers.copy();changed[index]=changed[index].replace(old,new)
            with self.assertRaises(ValueError):apps.validate_markers(changed,file_controls=True)
        # A genuinely claimed but incomplete request is also outstanding.
        claimed=markers.copy();claimed[index]=claimed[index].replace('queued=1 claimed=0','queued=0 claimed=1')
        self.assertEqual(apps.validate_markers(claimed,file_controls=True)['requester_deaths'][0]['claimed'],1)
        changed=markers.copy();changed[index],changed[index+1]=changed[index+1],changed[index]
        with self.assertRaises(ValueError):apps.validate_markers(changed,file_controls=True)

    def test_file_controls_keep_diagnostic_exit_separate_from_useful_application_results(self):
        from tools.qualify_native_app_session import retirement_barriers
        for bad in (False,True):
            case=apps.file_control_scenario('0123456789abcdef',bad_file=bad)
            self.assertEqual(list(retirement_barriers(case.sent).values()),[(5,1),(5,2),(4,1),(4,2)])
            self.assertEqual(case.expected.count(b'text: exit 0x00000055\r\n'),2)
            self.assertEqual(case.sent.count(b'cat /version.txt\r'),3)
            self.assertEqual(case.expected.count(b'numbers: file service unavailable\r\n' if bad else b'numbers: count=5 sum=50 min=3 max=21\r\n'),4)
            self.assertNotIn(b'text: bytes=',case.expected)
            self.assertTrue(case.expected.endswith(b'Bye.\r\n'))

    def test_interaction_waits_on_exact_cleanup_generation_before_next_command(self):
        from tools.qualify_native_app_session import cleanup_barriers
        case=apps.scenario('0'*16)
        barriers=cleanup_barriers(case.sent)
        self.assertEqual(list(barriers.values()),[(5,1),(4,1),(4,2),(5,2)])
        for offset,(task,_) in barriers.items():
            self.assertTrue(case.sent[offset:].startswith(b'status '+(b'text' if task==4 else b'numbers')+b'\r'))
            self.assertEqual(case.sent[offset-1:offset],b'\r')

    def test_live_parent_deferred_completion_and_both_restarts(self):
        for bad in (False,True):
            for boundary in (False,True):
                markers=deferred_fixture(bad,boundary)
                result=apps.validate_markers(markers,bad_file=bad,deferred_cleanup=True)
                self.assertEqual(len(result['cleanup_events']),12)
                self.assertTrue(result['live_parent_recovery'])
                self.assertFalse(result['native_exhaustion_qualified'])
                self.assertFalse(result['multiple_pending_cleanup_owners_qualified'])
                self.assertGreater(apps.negative_controls(markers,bad_file=bad,deferred_cleanup=True),400)
                with self.assertRaises(ValueError):apps.validate_markers(markers,bad_file=bad)
        with self.assertRaises(ValueError):apps.validate_markers(fixture(),deferred_cleanup=True)

    def test_cleanup_rejects_missing_reordered_early_and_wrong_owner_events(self):
        markers=deferred_fixture()
        positions=[i for i,m in enumerate(markers) if m.startswith(apps.cleanup.PREFIX)]
        cases=[]
        for i in positions:
            cases.extend([markers[:i]+markers[i+1:],markers[:i]+[markers[i]]+markers[i:]])
            for field in apps.cleanup.FIELDS:
                changed=markers.copy();changed[i]=re.sub(' '+field+r'=[0-9]+',' '+field+'=0',changed[i])
                if changed!=markers:cases.append(changed)
        swapped=markers.copy();a,b=positions[:2];swapped[a],swapped[b]=swapped[b],swapped[a];cases.append(swapped)
        for case in cases:
            with self.assertRaises(ValueError):apps.validate_markers(case,deferred_cleanup=True)

    def test_cleanup_freezes_child_pages_and_counters_without_stalling_services(self):
        markers=deferred_fixture()
        i=next(i for i,m in enumerate(markers) if 'APPS RUN contract=PAPPSESSION1 dispatches=320 ' in m)
        for field in ('calls5','ticks5','pages','live_mask','extra_flushes','retired','calls3','ticks3'):
            changed=markers.copy()
            previous=apps.parse(next(m for m in reversed(markers[:i]) if 'APPS RUN ' in m),'RUN')
            value=previous[field] if field in ('calls3','ticks3') else apps.parse(markers[i],'RUN')[field]+1
            changed[i]=re.sub(' '+field+r'=([0-9]+)',' '+field+'='+str(value),changed[i])
            with self.subTest(field=field), self.assertRaises(ValueError):apps.validate_markers(changed,deferred_cleanup=True)
        j=next(i for i,m in enumerate(markers) if 'CLEANUP COMPLETE ' in m)
        early=markers.copy();retire=early.pop(j+1);early.insert(j,retire)
        with self.assertRaises(ValueError):apps.validate_markers(early,deferred_cleanup=True)

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
                     'native/userspace/src/bin/waiting_file_probe.rs',
                     'native/userspace/src/bin/claimed_files.rs',
                     'native/userspace/src/files/claimed.rs',
                     'native/userspace/src/files/claimed/tests.rs',
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
