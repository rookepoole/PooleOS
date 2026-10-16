import json
import re
import unittest
from pathlib import Path
from runtime import native_shell_orphan as orphan, native_shell_process as control

class NativeShellOrphanTests(unittest.TestCase):
    def fixture(self, held=False, bad=False):
        # Synthetic schedule for parser tests only. It is never guest evidence.
        path=Path(__file__).resolve().parents[1]/'runs/native-retained-cleanup-readiness.json'
        original=json.loads(path.read_bytes())['native_execution']['retry']['guest_runs'][2 if bad else 0]['markers']
        markers=original[:30]
        start=control.parse(markers[29],'START')
        sizes=[start[n+'_bytes'] for n in ('init','counter','console','shell','worker')]
        pages=[12+(v+4095)//4096 for v in sizes+[sizes[-1]]]
        def record(event,**fields):
            return 'POOLEOS:CONTROL '+event+' contract=PSHELLPROC1'+''.join(' '+n+'='+str(fields[n]) for n in control.FIELDS[event].split())+' cpl=3 production=0'
        def job(event,**fields):
            return 'POOLEOS:JOB '+event+' contract=PJOB1'+''.join(' '+n+'='+str(fields[n]) for n in orphan.FIELDS[event].split())+' cpl=0 production=0'
        for n in range(1,9):
            d=n*64
            if n==2:
                markers.append(record('ADMIT',task=4,generation=1,sequence=1,handle=0x100050001,root=start['root4'],owned_pages=pages[4],dispatches=100))
                if held:
                    markers.append(f"POOLEOS:PREPARED HOLD contract=PCANCEL1 task=4 generation=1 root={start['root4']} dispatches=101 cr3_writes=200 calls=0 ticks=0 state=blocked entered=0 cpl=0 production=0")
            if n==5:
                markers.append(job('OWNER',task=3,generation=1,root=start['root3'],children=2,dispatches=300))
                markers.append(record('RETIRE',task=3,generation=1,outcome=(2<<32)|6,calls=5,released_pages=pages[3],dispatches=300))
                markers.append(f"POOLEOS:RECLAIM RETRY contract=PRECLAIM1 task=4 generation=1 mode=1 retained_pages={pages[4]} dispatches=300 released_pages=0 ordinary_free_denials=5 no_reentry=1 early_completion_rejected=1 cpl=0 production=0")
                markers.append(record('RETIRE',task=4,generation=1,outcome=4<<32,calls=0 if held else 4,released_pages=pages[4],dispatches=300))
                markers.append(job('CHILD',task=4,generation=1,root=start['root4'],prepared=int(held),remaining=1,published=0,dispatches=300))
                markers.append(record('UNUSED',task=5,released_pages=pages[5],dispatches=300))
                markers.append(job('DRAINED',children=0,owned_pages=sum(pages[:3]),dispatches=300))
            counts=[n,n,n,n if n<5 else 5,0 if held else max(0,min(n-1,4)),0]
            fields=dict(dispatches=d,cr3_writes=2*(d-int(held and n>=2))+int(not held and n>=5),
                extra_flushes=int(not held and n>=5),pages=sum(pages) if n<5 else sum(pages[:3]),
                live_mask=15 if n==1 else 31 if n<5 else 7,generation4=int(n>=2),generation5=0,
                retired=0 if n<5 else 2,unused=int(n>=5))
            fields.update({kind+str(i):v for kind in ('calls','ticks') for i,v in enumerate(counts)})
            markers.append(record('RUN',**fields))
        return markers

    def test_owner_and_child_cleanup_require_full_lifecycle_and_independent_survival(self):
        for held in (False,True):
            for bad in (False,True):
                markers=self.fixture(held,bad)
                result=orphan.validate_markers(markers,prepared_stop=held,bad_owner=bad)
                self.assertTrue(result['owner_death_recovery'])
                self.assertFalse(result['general_owner_death_recovery'] or result['asynchronous_cleanup_recovery'] or result['supervisor_restart'])
                self.assertEqual(result['drained']['children'],0)
                self.assertGreater(orphan.negative_controls(markers,prepared_stop=held,bad_owner=bad),100)
                with self.assertRaises(ValueError): control.validate_markers(markers,bad_owner=bad)

    def test_exact_fields_order_hold_exposure_and_duplicate_records_are_required(self):
        markers=self.fixture(True)
        for i,m in enumerate(markers):
            if not m.startswith('POOLEOS:JOB '): continue
            for tail in (' extra=0',' cpl=0'):
                changed=markers.copy(); changed[i]+=tail
                with self.assertRaises(ValueError): orphan.validate_markers(changed,prepared_stop=True)
            for field in orphan.FIELDS[m.split()[1]].split():
                changed=markers.copy(); changed[i]=re.sub(' '+field+r'=[0-9]+',' '+field+'=99',m)
                with self.assertRaises(ValueError): orphan.validate_markers(changed,prepared_stop=True)
        i=next(i for i,m in enumerate(markers) if m.startswith('POOLEOS:PREPARED HOLD '))
        changed=markers.copy(); hold=changed.pop(i); changed.insert(i+1,hold)
        with self.assertRaises(ValueError): orphan.validate_markers(changed,prepared_stop=True)
        for field in ('calls2','ticks2'):
            changed=markers.copy()
            changed[-1]=re.sub(' '+field+r'=[0-9]+',' '+field+'=7',changed[-1])
            with self.assertRaises(ValueError): orphan.validate_markers(changed,prepared_stop=True)
        changed=markers.copy()
        changed[-1]=changed[-1].replace('live_mask=7','live_mask=3')
        with self.assertRaises(ValueError): orphan.validate_markers(changed,prepared_stop=True)

    def test_challenge_includes_exact_self_fault_and_rejects_near_matches_first(self):
        a,b=[orphan.scenario(n) for n in ('0123456789abcdef','fedcba9876543210')]
        self.assertNotEqual(a.sent,b.sent)
        self.assertIn(b'fault shell \r',a.sent)
        self.assertIn(b'fault shellx\r',a.sent)
        self.assertTrue(a.sent.endswith(b'fault shell\r'))
        self.assertTrue(a.expected.endswith(b'fault shell\r\n'))
        with self.assertRaises(ValueError): orphan.scenario('not-a-nonce')

if __name__=='__main__': unittest.main()
