import re
import unittest
from pathlib import Path
from unittest import mock
from runtime import native_entered_recovery as entered, native_shell_process as control
from runtime import native_deferred_cleanup as deferred, native_shell_orphan as orphan
from tests import test_native_deferred_cleanup as fixtures


def record(event, values):
    fields = entered.FIELDS.get(event, control.FIELDS.get(event)).split()
    return 'POOLEOS:CONTROL '+event+' contract=PSHELLPROC1'+''.join(' '+k+'='+str(values[k]) for k in fields)+' cpl=3 production=0'


def fixture(persistent=False, bad=False):
    original = fixtures.NativeDeferredCleanupTests().fixture(False, bad)
    runs = [control.parse(m, 'RUN') for m in original if m.startswith('POOLEOS:CONTROL RUN ')]
    last = runs[-1]
    while last['dispatches'] < 1024:
        last = dict(last, dispatches=last['dispatches']+64, cr3_writes=last['cr3_writes']+128)
        for i in range(3):
            last[f'calls{i}'] += 1
            last[f'ticks{i}'] += 1
        original.append(record('RUN', last))
    admission = next(control.parse(m, 'ADMIT') for m in original if m.startswith('POOLEOS:CONTROL ADMIT '))
    pages = admission['owned_pages']
    parked = dict(task=4, generation=1, root=admission['root'], attempts=0, next=364,
        pages=pages, writes=20, calls=last['calls4'], ticks=last['ticks4'], slices=8, dispatches=300)
    recovered = dict(task=4, generation=1, root=admission['root'], attempts=1,
        retained_pages=pages if persistent else 0, recovered=int(not persistent), children=int(persistent), writes=200, dispatches=812)
    delayed, markers = [], []
    independent = sum(12+(n+4095)//4096 for n in [control.parse(original[29], 'START')[k+'_bytes'] for k in ('init','counter','console')])
    for m in original:
        if m.startswith(('POOLEOS:CONTROL RETIRE ', orphan.PREFIX+'CHILD ')) and ' task=4 ' in m:
            delayed.append(m.replace('dispatches=492','dispatches=812')); continue
        if m.startswith(orphan.PREFIX+'DRAINED '):
            delayed.append(m.replace('dispatches=493','dispatches=813')); continue
        if m.startswith(deferred.PREFIX+'COMPLETE '):
            m=m.replace('COMPLETE','RETRY').replace('next=0','next=748').replace('pages=0',f'pages={pages}')
        if m.startswith('POOLEOS:CONTROL RUN '):
            v=control.parse(m,'RUN'); d=v['dispatches']
            if d >= 300:
                retained = persistent or d < 812
                v.update(pages=independent+pages*int(retained), live_mask=23 if retained else 7, retired=1 if retained else 2)
            if d == 768:
                markers.append(f'POOLEOS:CLEANUP EXHAUSTED contract=PCLEANUP2 task=4 generation=1 attempts=3 next=0 pages={pages} dispatches=748 admitted=1 cpl=0 production=0')
            if d == 832:
                markers.append(record('RECOVER',recovered))
                if not persistent: markers.extend(delayed)
            markers.append(record('RUN',v))
            if persistent and d > 812:
                markers.append(record('HELD',dict(parked, attempts=3, next=0, writes=200, dispatches=d)))
        else:
            markers.append(m)
            if m.startswith(deferred.PREFIX+'DEFER '): markers.append(record('PARKED',parked))
    return markers


class NativeEnteredRecoveryTests(unittest.TestCase):
    def test_only_exact_non_graphical_recovery_feature_sets_are_admitted(self):
        from tools import qualify_native_kernel_entry as entry
        with mock.patch('tools.native_build_space.require_space'), mock.patch.object(entry, '_product_environment', return_value={}), mock.patch.object(entry, '_run', side_effect=RuntimeError('build reached')) as run:
            for feature in ('development-shell-orphan-recovery','development-shell-orphan-stuck'):
                for features in ((feature,), (feature,'development-shell-process-bad-owner')):
                    with self.assertRaisesRegex(RuntimeError,'build reached'):
                        entry._build_product(Path('cargo'),{},Path('outputs/test-only'),features=features)
                for extra in ('development-shell-prepared-stop','development-launch-desktop','unreviewed'):
                    with self.assertRaises(entry.QualificationError):
                        entry._build_product(Path('cargo'),{},Path('outputs/test-only'),features=(feature,extra))
            self.assertEqual(run.call_count,4)

    def test_success_and_persistent_retention_with_denied_authority(self):
        for persistent in (False, True):
            for bad in (False, True):
                markers=fixture(persistent,bad)
                result=entered.validate_markers(markers,persistent=persistent,bad_owner=bad)
                self.assertEqual(result['deferred_attempts'],3)
                self.assertEqual(result['recovery_attempts'],1)
                self.assertEqual(result['independent_dispatches_before_recovery'],512)
                self.assertFalse(result['general_owner_death_recovery'] or result['production_ready'])
                self.assertGreater(entered.negative_controls(markers,persistent=persistent,bad_owner=bad),500)

    def test_persistent_runtime_ownership_and_writes_cannot_change(self):
        markers=fixture(True)
        for i,m in enumerate(markers):
            if not m.startswith(entered.PREFIX+'HELD '): continue
            for field in entered.FIELDS['HELD'].split():
                changed=markers.copy()
                changed[i]=re.sub(' '+field+r'=([0-9]+)',lambda n:' '+field+'='+str(int(n.group(1))+1),m)
                with self.assertRaises(ValueError): entered.validate_markers(changed,persistent=True)

    def test_backoff_recovery_identity_and_disposition_cannot_change(self):
        for persistent in (False,True):
            markers=fixture(persistent)
            for i,m in enumerate(markers):
                fields = deferred.FIELDS if m.startswith(deferred.PREFIX) else entered.FIELDS['RECOVER'].split() if m.startswith(entered.PREFIX+'RECOVER ') else []
                for field in fields:
                    if field == 'writes' and not persistent: continue
                    changed=markers.copy()
                    changed[i]=re.sub(' '+field+r'=([0-9]+)',lambda n:' '+field+'='+str(int(n.group(1))+1),m)
                    with self.assertRaises(ValueError): entered.validate_markers(changed,persistent=persistent)

    def test_profiles_cannot_be_substituted(self):
        with self.assertRaises(ValueError): entered.validate_markers(fixture(),persistent=True)
        with self.assertRaises(ValueError): entered.validate_markers(fixture(True))
        with self.assertRaises(ValueError): entered.validate_markers(fixture(),prepared_stop=True)
        for args in ({},dict(owner_death=True),dict(owner_death=True,cleanup_window=(300,812))):
            with self.assertRaises(ValueError): control.validate_markers([],retained_cleanup=True,**args)


if __name__ == '__main__': unittest.main()
