import re
import unittest
from runtime import native_deferred_cleanup as deferred, native_shell_orphan as orphan, native_shell_process as control
from tests import test_native_shell_orphan as fixture

class NativeDeferredCleanupTests(unittest.TestCase):
    def fixture(self,held=False,bad=False):
        original=fixture.NativeShellOrphanTests().fixture(held,bad)
        markers=[]; delayed=[]
        for m in original:
            if m.startswith('POOLEOS:RECLAIM RETRY '):
                pages=int(re.search(r'retained_pages=([0-9]+)',m).group(1))
                markers.append(f'POOLEOS:CLEANUP DEFER contract=PCLEANUP2 task=4 generation=1 attempts=0 next=364 pages={pages} dispatches=300 admitted=1 cpl=0 production=0')
                continue
            if m.startswith(('POOLEOS:CONTROL RETIRE ',orphan.PREFIX+'CHILD ')) and ' task=4 ' in m:
                delayed.append(m.replace('dispatches=300','dispatches=492').replace('remaining=1','remaining=0')); continue
            if m.startswith(orphan.PREFIX+'DRAINED '):
                delayed.append(m.replace('dispatches=300','dispatches=493')); continue
            if m.startswith('POOLEOS:CONTROL RUN '):
                v=control.parse(m,'RUN'); d=v['dispatches']
                if 300<d<492:
                    m=m.replace('live_mask=7','live_mask=23').replace('retired=2','retired=1')
                    m=re.sub(r' pages=[0-9]+',' pages='+str(v['pages']+pages),m)
                if d==384: markers.append(f'POOLEOS:CLEANUP RETRY contract=PCLEANUP2 task=4 generation=1 attempts=1 next=492 pages={pages} dispatches=364 admitted=1 cpl=0 production=0')
                if d==512:
                    markers.append('POOLEOS:CLEANUP COMPLETE contract=PCLEANUP2 task=4 generation=1 attempts=2 next=0 pages=0 dispatches=492 admitted=1 cpl=0 production=0')
                    markers.extend(delayed)
            markers.append(m)
        v=control.parse(markers[-1],'RUN'); v['dispatches']+=64; v['cr3_writes']+=128
        for i in range(3):
            v[f'calls{i}']+=1;v[f'ticks{i}']+=1
        markers.append('POOLEOS:CONTROL RUN contract=PSHELLPROC1'+''.join(' '+n+'='+str(v[n]) for n in control.FIELDS['RUN'].split())+' cpl=3 production=0')
        return markers

    def test_exact_backoff_and_survivor_progress_for_prepared_and_suspended_children(self):
        for held in (False,True):
            for bad in (False,True):
                m=self.fixture(held,bad)
                v=deferred.validate_markers(m,bad_owner=bad,prepared_stop=held)
                self.assertEqual(v['deferred_attempts'],2)
                self.assertTrue(v['asynchronous_cleanup_recovery'])
                self.assertFalse(v['exhaustion_native_qualified'] or v['production_ready'])
                self.assertGreater(deferred.negative_controls(m,bad_owner=bad,prepared_stop=held),100)

    def test_early_retry_and_completion_resume_and_missing_retention_reject(self):
        m=self.fixture()
        for field in ('calls4','ticks4'):
            for i,line in enumerate(m):
                if line.startswith('POOLEOS:CONTROL RUN ') and control.parse(line,'RUN')['dispatches'] >= 300:
                    v=m.copy(); v[i]=re.sub(' '+field+r'=([0-9]+)',lambda x:' '+field+'='+str(int(x.group(1))+1),line)
                    with self.assertRaises(ValueError): deferred.validate_markers(v)
        for i,line in enumerate(m):
            if not line.startswith(deferred.PREFIX): continue
            for field in deferred.FIELDS:
                v=m.copy();v[i]=re.sub(' '+field+r'=([0-9]+)',lambda x:' '+field+'='+str(int(x.group(1))+1),line)
                with self.assertRaises(ValueError): deferred.validate_markers(v)

if __name__=='__main__': unittest.main()
