"""Synthetic pressure fixtures are host checks, not native quota evidence."""
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from runtime import native_app_session as apps
from tests.test_native_launch_failure import fixture as denied, emit, OPTIONS
from tests.test_native_graphical_recovery import profile
from tools import qualify_native_app_session as qualifier


def fixture(bad=False):
    result = []
    for line in denied(bad):
        if 'APPS REJECT ' in line and 'task=5 ' in line:
            v = apps.parse(line, 'REJECT')
            values = dict(task=5,generation=2,owner=3,owner_generation=1,target=0,
                target_generation=1,handle=(2<<32)|0x50003,owner_limit=2,dispatches=v['dispatches'])
            result.extend((emit('PRESSURE', values), emit('REJECT', dict(v,reason=2)), emit('RELIEF', values)))
        elif 'task=5 generation=3 ' in line and ('APPS SURFACE ' in line or 'APPS ADMIT ' in line):
            event, field = ('SURFACE','send') if 'APPS SURFACE ' in line else ('ADMIT','handle')
            v = apps.parse(line,event)
            v[field] += 1<<32
            result.append(emit(event,v))
        else:
            result.append(line)
    return result


class NativeLaunchQuotaTests(unittest.TestCase):
    def test_actual_quota_profile_requires_pressure_relief_and_fresh_generations(self):
        for bad in (False, True):
            r = apps.validate_markers(fixture(bad),bad_file=bad,launch_failure=True,launch_quota=True,**OPTIONS)
            self.assertEqual([v['reason'] for v in r['rejections']], [2,1])
            self.assertEqual([v['event'] for v in r['pressure_events']], ['PRESSURE','RELIEF'])
            self.assertTrue(r['native_process_quota_recovery'])
            self.assertGreater(apps.negative_controls(fixture(bad),bad_file=bad,launch_failure=True,launch_quota=True,**OPTIONS),200)

    def test_historical_denied_and_ordinary_profiles_do_not_accept_quota(self):
        with self.assertRaises(ValueError): apps.validate_markers(fixture(),launch_failure=True,**OPTIONS)
        with self.assertRaises(ValueError): apps.validate_markers(denied(),launch_failure=True,launch_quota=True,**OPTIONS)
        for value in (True,1,None,'true'):
            with self.assertRaises(ValueError): apps.profile_options(dict(profile(),diagnostic_only=False,launch_failure=False,launch_quota=value))
        for value in (1,None,'true'):
            with self.assertRaises(ValueError): apps.validate_markers(fixture(),launch_failure=True,launch_quota=value,**OPTIONS)
            with self.assertRaises(ValueError): apps.launch_failure_options(dict(profile(),launch_quota=value))
        with self.assertRaises(ValueError): apps.validate_markers(fixture(),launch_quota=True,**OPTIONS)
        self.assertTrue(apps.launch_failure_options(dict(profile(),launch_quota=True))['launch_quota'])
        self.assertNotIn('launch_quota',apps.launch_failure_options(profile()))

    def test_pressure_cannot_be_missing_reordered_rebound_or_relabelled(self):
        source = fixture()
        positions = [i for i,v in enumerate(source) if 'APPS PRESSURE ' in v or 'APPS RELIEF ' in v]
        candidates = [source[:i]+source[i+1:] for i in positions]
        for i in positions:
            for old,new in [('owner=3','owner=2'),('target=0','target=1'),('owner_limit=2','owner_limit=3'),
                            ('generation=2','generation=3'),('handle=8590262275','handle=4295294979')]:
                self.assertIn(old,source[i])
                candidates.append(source[:i]+[source[i].replace(old,new)]+source[i+1:])
        swapped = list(source)
        a,b = positions
        swapped[a],swapped[b] = swapped[b],swapped[a]
        candidates.append(swapped)
        for i,v in enumerate(source):
            if 'APPS REJECT ' in v and 'reason=2' in v:
                candidates.append(source[:i]+[v.replace('reason=2','reason=1')]+source[i+1:])
            if 'task=5 generation=3 ' in v and ('APPS SURFACE ' in v or 'APPS ADMIT ' in v):
                event,field = ('SURFACE','send') if 'APPS SURFACE ' in v else ('ADMIT','handle')
                record = apps.parse(v,event);record[field] -= 1<<32
                candidates.append(source[:i]+[emit(event,record)]+source[i+1:])
        for candidate in candidates:
            with self.assertRaises(ValueError): apps.validate_markers(candidate,launch_failure=True,launch_quota=True,**OPTIONS)

    def test_quota_cli_rejects_missing_diagnostic_before_storage(self):
        with patch('sys.argv',['qualifier','--launch-quota','--work-dir','outputs/absent',
                              '--program-dir','outputs/absent']),patch('sys.stderr'), \
                patch.object(qualifier,'require_space') as storage,self.assertRaises(SystemExit):
            qualifier.main()
        storage.assert_not_called()

    def test_builder_accepts_only_complete_quota_feature_combinations(self):
        from tools import qualify_native_kernel_entry as entry
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)/'unbuilt'
            for bad in (False, True):
                features = ('development-launch-desktop',) + (('development-applications-bad-file',) if bad else ())
                features += ('development-launch-failure','development-launch-quota')
                with patch('tools.native_build_space.require_space',return_value={}),patch.object(entry,'_run') as run:
                    with self.assertRaisesRegex(entry.QualificationError,'artifact is missing'):
                        entry._build_product(Path('cargo'),{},target,features=features)
                    self.assertIn(','.join(features),run.call_args.args[0])
                    flags = run.call_args.kwargs['env']['CARGO_ENCODED_RUSTFLAGS']
                    self.assertIn('__poole_launch_session_profile=1',flags)
            for features in [('development-launch-quota',),('development-launch-desktop','development-launch-quota'),
                             ('development-launch-failure','development-launch-quota')]:
                with patch('tools.native_build_space.require_space',return_value={}),patch.object(entry,'_run') as run:
                    with self.assertRaisesRegex(entry.QualificationError,'unreviewed'):
                        entry._build_product(Path('cargo'),{},target,features=features)
                    run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
