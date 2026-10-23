"""Synthetic oracle fixtures never count as native execution evidence."""
import re
import unittest
from unittest.mock import patch
from runtime import native_app_session as apps
from tests.test_native_launch_admission import markers, OPTIONS, PROFILE
from tools import qualify_native_app_session as qualifier

def emit(event, values):
    return ('POOLEOS:APPS '+event+' contract=PAPPSESSION1'
            + ''.join(f' {key}={values[key]}' for key in apps.FIELDS[event].split())
            + ' cpl=3 production=0')

def fixture(bad=False):
    source = markers(bad)
    start = apps.parse(source[30], 'START')
    pages = {i:12+(start[n+'_bytes']+4095)//4096 for i,n in enumerate(
        ('init','files','console','shell','text','numbers'))}
    def rejected(task, dispatch):
        return emit('REJECT', dict(task=task,generation=2,sequence=2,root=start[f'root{task}'],
            owned_pages=pages[task],reason=1,syscalls=0,dispatches=dispatch))
    def failed(task, dispatch):
        return emit('FAILED',dict(task=task,generation=2,sequence=2,root=start[f'root{task}'],
            published=1,dispatches=dispatch))
    def cleanup(event, dispatch, attempts, count, next_dispatch):
        return (f'POOLEOS:CLEANUP {event} contract=PCLEANUP2 task=5 generation=2 attempts={attempts}'
                f' next={next_dispatch} pages={count} dispatches={dispatch} admitted=0 cpl=0 production=0')
    result=[]
    for line in source:
        event = next((e for e in apps.FIELDS if line.startswith('POOLEOS:APPS '+e+' ')), None)
        if event is None or event == 'START':
            result.append(line); continue
        value = apps.parse(line,event)
        d = value['dispatches']
        if event=='RUN' and d==256:
            result += [rejected(5,201), cleanup('DEFER',201,0,pages[5],265)]
        if event=='HANDOFF' and value['task']==5 and value['generation']==2:
            result += [cleanup('COMPLETE',265,1,0,0), failed(5,265)]
        if event=='HANDOFF' and value['task']==4 and value['generation']==2:
            result += [rejected(4,389), failed(4,389)]
        if event=='RUN':
            value['unused'] = int(d>=320)+int(d>=448)
            if d==256:
                value.update(generation5=2,calls5=0,ticks5=0,pages=value['pages']+pages[5])
            if d>=320: value['generation5']=3
            if d>=448: value['generation4']=3
        elif value.get('task') in (4,5) and value.get('generation')==2:
            value['generation']=3
            if event=='ADMIT': value['sequence']=3
            if event=='HANDOFF':
                for name in ('control','files','startup_files'): value[name]+=1<<32
        result.append(emit(event,value))
    return result

class LaunchFailureTests(unittest.TestCase):
    def test_immediate_and_deferred_failures_have_distinct_identity_domains(self):
        for bad in (False,True):
            report=apps.validate_markers(fixture(bad),bad_file=bad,launch_failure=True,**OPTIONS)
            self.assertEqual(len(report['failed_launches']),2)
            self.assertEqual([r['generation'] for r in report['admits']],[1,1,3,3])
            self.assertFalse(report['graphical_failure_retry_verified'])
            self.assertGreater(apps.negative_controls(fixture(bad),bad_file=bad,launch_failure=True,**OPTIONS),200)

    def test_ordinary_preview_and_invalid_diagnostic_types_reject(self):
        with self.assertRaises(ValueError): apps.validate_markers(fixture(),**OPTIONS)
        for value in (True,1,None,'true'):
            with self.assertRaises(ValueError): apps.profile_options(dict(PROFILE,launch_failure=value))
        for value in (1,None,'true'):
            with self.assertRaises(ValueError): apps.validate_markers(fixture(),launch_failure=value,**OPTIONS)
        with self.assertRaises(ValueError): apps.validate_markers(fixture(),launch_failure=True)

    def test_no_early_completion_dispatch_or_fabricated_process_generation(self):
        source=fixture()
        candidates=[]
        for i,line in enumerate(source):
            changes=[]
            if 'APPS FAILED ' in line: changes += [('published=1','published=0'),('generation=2','generation=1')]
            if 'APPS ADMIT ' in line and 'generation=3' in line:
                v=apps.parse(line,'ADMIT'); changes.append((f"handle={v['handle']}",f"handle={v['handle']+(1<<32)}"))
            if 'APPS RUN dispatches=256 ' in line: changes.append(('calls5=0','calls5=1'))
            for old,new in changes: candidates.append(source[:i]+[line.replace(old,new)]+source[i+1:])
        for candidate in candidates:
            with self.assertRaises(ValueError): apps.validate_markers(candidate,launch_failure=True,**OPTIONS)
        self.assertGreater(len(candidates),5)

    def test_scenario_has_explicit_fresh_retry_after_each_failed_attempt(self):
        case=apps.scenario('0123456789abcdef',launch_failure=True)
        for app in (b'text',b'numbers'):
            self.assertEqual(case.sent.count(b'start '+app+b'\r'),3)
            self.assertEqual(case.expected.count(app+b': launch failed\r\n'),1)

    def test_diagnostic_cli_requires_complete_profile_before_output(self):
        with patch('sys.argv',['qualifier','--launch-failure','--work-dir','outputs/absent',
                              '--program-dir','outputs/absent']), patch('sys.stderr'), \
                patch.object(qualifier,'require_space') as storage, self.assertRaises(SystemExit):
            qualifier.main()
        storage.assert_not_called()
