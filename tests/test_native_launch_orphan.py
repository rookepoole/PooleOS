"""Synthetic orphan observations exercise the parser, never native execution."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from runtime import native_app_session as apps, native_shell_orphan as job
from tests.test_native_launch_quota import fixture as quota
from tests.test_native_launch_failure import emit, OPTIONS
from tests.test_native_graphical_recovery import profile
from tools import qualify_native_app_session as qualifier

OPTS = dict(OPTIONS, launch_failure=True, launch_quota=True, launch_orphan=True)


def fixture(bad=False, stuck=False):
    source = quota(bad)
    end = next(i for i,v in enumerate(source) if 'CLEANUP DEFER ' in v)
    result = source[:end+1]
    start = apps.parse(source[30], 'START')
    pages = [12+(start[n+'_bytes']+4095)//4096 for n in ('init','files','console','shell','text','numbers')]
    sample = next(apps.parse(v,'RUN') for v in source if 'APPS RUN ' in v and 'dispatches=256 ' in v)
    held = dict(task=5,generation=2,root=start['root5'],pages=pages[5],children=1,writes=40960,calls=0,ticks=0)
    def job_line(event, **values):
        return (job.PREFIX+event+' contract=PJOB1'+''.join(f' {n}={values[n]}' for n in job.FIELDS[event].split())+' cpl=0 production=0')
    for d in range(202,1281):
        if d in (265,393,649):
            attempt = (265,393,649).index(d)+1
            event = 'EXHAUSTED' if attempt == 3 else 'RETRY'
            result.append(f'POOLEOS:CLEANUP {event} contract=PCLEANUP2 task=5 generation=2 attempts={attempt}'
                f' next={0 if attempt == 3 else d+(64<<attempt)} pages={pages[5]} dispatches={d} admitted=0 cpl=0 production=0')
        if d == 650:
            result.append(job_line('OWNER',task=3,generation=1,root=start['root3'],children=2,dispatches=d))
            for task in (3,4):
                result.append(emit('RETIRE',dict(task=task,generation=1,outcome=4<<32,
                    calls=sample[f'calls{task}'],released_pages=pages[task],dispatches=d)))
            result.append(job_line('CHILD',task=4,generation=1,root=start['root4'],prepared=0,remaining=1,published=0,dispatches=d))
        if d == 713:
            result.append(emit('RECOVER',dict(task=5,generation=2,root=start['root5'],attempts=1,
                retained_pages=pages[5] if stuck else 0,recovered=int(not stuck),children=int(stuck),writes=40960,dispatches=d)))
            if not stuck:
                result.append(emit('FAILED',dict(task=5,generation=2,sequence=2,root=start['root5'],published=0,dispatches=d)))
        if d == 714 and not stuck:
            result.append(job_line('DRAINED',children=0,owned_pages=sum(pages[:3]),dispatches=d))
        if d % 64 == 0:
            sample.update(dispatches=d,cr3_writes=2*d+2*int(d>650),extra_flushes=2*int(d>650),
                live_mask=7 if d>650 else 31,retired=3 if d>650 else 1,unused=int(d>713 and not stuck),
                pages=sum(pages) if d<650 else sum(pages[:3])+(pages[5] if stuck or d<713 else 0))
            for task in range(5):
                if task < 3 or d<650:
                    sample[f'calls{task}'] += 10
                    sample[f'ticks{task}'] += 100
            result.append(emit('RUN',sample))
            if d>713 and stuck: result.append(emit('HELD',dict(held,dispatches=d)))
    return result


class NativeLaunchOrphanTests(unittest.TestCase):
    def test_recovered_and_persistently_retained_lifecycles(self):
        for bad in (False,True):
            for stuck in (False,True):
                r = apps.validate_markers(fixture(bad,stuck),bad_file=bad,orphan_stuck=stuck,**OPTS)
                self.assertEqual(r['orphan_cleanup_recovered'],not stuck)
                self.assertEqual(r['repeated_recovery_writes_rejected'],stuck)
                self.assertTrue(r['supervisor_cancelled_owner'])
                self.assertFalse(r['actual_owner_ud2'])
                self.assertFalse(r['general_owner_death_recovery'])
                self.assertFalse(r['native_process_quota_recovery'])
                self.assertGreater(apps.negative_controls(fixture(bad,stuck),bad_file=bad,orphan_stuck=stuck,**OPTS),200)

    def test_diagnostic_profiles_are_not_interchangeable(self):
        for stuck in (False,True):
            for flags in ({},dict(launch_failure=True),dict(launch_failure=True,launch_quota=True),
                          dict(launch_failure=True,launch_quota=True,launch_orphan=True,orphan_stuck=not stuck)):
                with self.assertRaises(ValueError): apps.validate_markers(fixture(stuck=stuck),**OPTIONS,**flags)
            p = dict(profile(),launch_quota=True,launch_orphan=True,orphan_stuck=stuck)
            self.assertEqual(apps.launch_orphan_options(p),dict(OPTS,orphan_stuck=stuck))
            for select in (apps.profile_options,apps.launch_failure_options):
                with self.assertRaises(ValueError): select(p)
        for name in ('launch_orphan','orphan_stuck'):
            for value in (1,None,'true'):
                with self.assertRaises(ValueError): apps.validate_markers(fixture(),**dict(OPTS,**{name:value}))
                with self.assertRaises(ValueError): apps.launch_orphan_options(dict(dict(profile(),launch_quota=True,launch_orphan=True,orphan_stuck=False),**{name:value}))

    def test_exact_owner_cooldown_budget_and_single_rescue(self):
        for stuck in (False,True):
            source=fixture(stuck=stuck)
            positions=[i for i,v in enumerate(source) if v.startswith(job.PREFIX) or 'APPS RECOVER ' in v or 'CLEANUP ' in v]
            candidates=[]
            for i in positions:
                candidates += [source[:i]+source[i+1:],source[:i]+[source[i]]+source[i:]]
                for old,new in [('dispatches=713','dispatches=712'),('dispatches=650','dispatches=649'),
                                ('generation=2','generation=3'),('children=2','children=1'),
                                ('attempts=3','attempts=2'),('next=0','next=777')]:
                    if old in source[i]: candidates.append(source[:i]+[source[i].replace(old,new)]+source[i+1:])
            for candidate in candidates:
                with self.assertRaises(ValueError): apps.validate_markers(candidate,orphan_stuck=stuck,**OPTS)

    def test_dead_parent_completion_reentry_and_repeated_writes_rejected(self):
        for stuck in (False,True):
            source=fixture(stuck=stuck)
            for field in ('calls5','ticks5'):
                forged=[line.replace(field+'=0',field+'=1') if 'APPS RUN ' in line and 'generation5=2 ' in line else line for line in source]
                with self.assertRaisesRegex(ValueError,'rejected image executed'):
                    apps.validate_markers(forged,orphan_stuck=stuck,**OPTS)
            for i,line in enumerate(source):
                if i <= next(j for j,v in enumerate(source) if 'CLEANUP DEFER ' in v): continue
                for old,new in [('published=0','published=1'),('calls5=0','calls5=1'),
                                ('live_mask=7','live_mask=39'),('writes=40960','writes=40961')]:
                    if old not in line or ('writes=' in old and 'APPS HELD ' not in line): continue
                    with self.assertRaises(ValueError):
                        apps.validate_markers(source[:i]+[line.replace(old,new)]+source[i+1:],orphan_stuck=stuck,**OPTS)

    def test_input_stops_at_rejected_request_without_dead_shell_reply(self):
        for bad in (False,True):
            case=apps.orphan_scenario('0123456789abcdef',bad_file=bad)
            self.assertEqual(case.sent.count(b'start numbers\r'),2)
            self.assertTrue(case.sent.endswith(b'start numbers\r'))
            self.assertTrue(case.expected.endswith(b'start numbers\r\n'))
            self.assertNotIn(b'launch failed',case.expected)
        with self.assertRaises(ValueError): apps.orphan_scenario('untrusted')

    def test_cli_requires_complete_profile_before_storage(self):
        for flags in (['--launch-orphan'],['--orphan-stuck']):
            with patch('sys.argv',['qualifier',*flags,'--work-dir','outputs/absent','--program-dir','outputs/absent']), \
                    patch('sys.stderr'),patch.object(qualifier,'require_space') as storage,self.assertRaises(SystemExit):
                qualifier.main()
            storage.assert_not_called()

    def test_builder_accepts_only_complete_explicit_orphan_profiles(self):
        from tools import qualify_native_kernel_entry as entry
        with tempfile.TemporaryDirectory() as temp:
            target=Path(temp)/'unbuilt'
            for bad in (False,True):
                for stuck in (False,True):
                    features=('development-launch-desktop',)+(('development-applications-bad-file',) if bad else ())
                    features+=('development-launch-failure','development-launch-quota','development-launch-orphan')
                    if stuck: features+=('development-launch-orphan-stuck',)
                    with patch('tools.native_build_space.require_space',return_value={}),patch.object(entry,'_run') as run:
                        with self.assertRaisesRegex(entry.QualificationError,'artifact is missing'):
                            entry._build_product(Path('cargo'),{},target,features=features)
                        self.assertIn(','.join(features),run.call_args.args[0])
            for features in [('development-launch-orphan',),('development-launch-orphan-stuck',),
                             ('development-launch-desktop','development-launch-orphan')]:
                with patch('tools.native_build_space.require_space',return_value={}),patch.object(entry,'_run') as run:
                    with self.assertRaisesRegex(entry.QualificationError,'unreviewed'):
                        entry._build_product(Path('cargo'),{},target,features=features)
                    run.assert_not_called()


if __name__ == '__main__': unittest.main()
