import re
import unittest
from runtime import native_app_session as apps, native_cleanup_exhaustion as probe
from tests.test_native_app_session import fixture as app_fixture


def fixture(bad=False, collision=False):
    # Synthetic oracle inputs only, never native qualification evidence.
    markers = app_fixture(bad)[:31]
    roots = [0x100000+i*0x10000 for i in range(6)]
    calls, ticks, live, stopped, exhausted = [0]*6, [0]*6, set(range(4)), set(), set()
    def emit(event, values):
        markers.append('POOLEOS:APPS '+event+' contract=PAPPSESSION1'+
                       ''.join(' '+n+'='+str(values[n]) for n in apps.FIELDS[event].split())+' cpl=3 production=0')
    events = [(70,'launch',4),(80,'launch',5)]
    for j,d in ((4,200),(5,200 if collision else 220)):
        events += [(d,'DEFER',j),(d+64+(j-4 if collision else 0),'RETRY1',j),
                   (d+192+(j-4 if collision else 0),'RETRY2',j),(d+448+(j-4 if collision else 0),'EXHAUSTED',j)]
    events += [(d,'sample',0) for d in range(64,1217,64)]
    events.sort(key=lambda e:(e[0],e[1] in ('RETRY1','RETRY2','EXHAUSTED')))
    for d,event,j in events:
        if event == 'launch':
            emit('HANDOFF',dict(task=j,generation=1,control=(1<<32)|0x10001,files=(1<<32)|0x10002,
                 startup_files=((1+int(bad and j==5))<<32)|0x10002,bytes=176,entered=0,dispatches=d))
            emit('ADMIT',dict(task=j,generation=1,sequence=1,handle=(1<<32)|0x50000|(j-3),
                 root=roots[j],owned_pages=14,dispatches=d))
            live.add(j)
        elif event != 'sample':
            attempt={'DEFER':0,'RETRY1':1,'RETRY2':2,'EXHAUSTED':3}[event]
            values=dict(task=j,generation=1,attempts=attempt,next=d+(64<<attempt) if attempt<3 else 0,
                        pages=14,dispatches=d,admitted=1)
            markers.append(apps.cleanup.PREFIX+('RETRY' if event.startswith('RETRY') else event)+' contract=PCLEANUP2'+
                           ''.join(' '+n+'='+str(values[n]) for n in apps.cleanup.FIELDS)+' cpl=0 production=0')
            stopped.add(j)
            if event=='EXHAUSTED': exhausted.add(j)
        else:
            for k in live-stopped: calls[k]+=10;ticks[k]+=100
            emit('RUN',dict(dispatches=d,cr3_writes=2*d+len(stopped),extra_flushes=len(stopped),pages=83,
                 live_mask=sum(1<<k for k in live),generation4=int(4 in live),generation5=int(5 in live),retired=0,unused=0,
                 **{f'calls{k}':calls[k] for k in range(6)},**{f'ticks{k}':ticks[k] for k in range(6)}))
            for k in sorted(exhausted):
                values=dict(task=k,generation=1,attempts=3,pages=14,writes=10000+k,calls=calls[k],ticks=ticks[k],dispatches=d,children=2)
                markers.append(probe.HOLD+''.join(' '+n+'='+str(values[n]) for n in probe.FIELDS)+' cpl=0 production=0')
    return markers


class NativeCleanupExhaustionTests(unittest.TestCase):
    def test_two_exhausted_owners_require_live_services_and_unchanged_pages(self):
        for bad in (False,True):
            for collision in (False,True):
                markers=fixture(bad,collision)
                result=probe.validate_markers(markers,bad_file=bad)
                self.assertEqual(result['retained_pages'],28)
                self.assertEqual(len(result['cleanup_events']),8)
                self.assertFalse(result['successful_recovery'] or result['iso_built'] or result['production_ready'])
                self.assertGreater(probe.negative_controls(markers,bad_file=bad),300)

    def test_exhausted_observations_reject_writes_resume_and_false_release(self):
        markers=fixture()
        i=next(i for i,m in enumerate(markers) if m.startswith(probe.HOLD))
        for field in probe.FIELDS:
            changed=markers.copy()
            changed[i]=re.sub(' '+field+r'=([0-9]+)',lambda m:' '+field+'='+str(int(m[1])+1),changed[i])
            with self.subTest(field=field),self.assertRaises(ValueError): probe.validate_markers(changed)

    def test_retry_limits_cannot_be_extended_or_completed(self):
        markers=fixture()
        i=next(i for i,m in enumerate(markers) if 'CLEANUP EXHAUSTED ' in m)
        for old,new in [('EXHAUSTED','COMPLETE'),('attempts=3','attempts=4'),('pages=14','pages=0'),('next=0','next=900')]:
            changed=markers.copy();changed[i]=changed[i].replace(old,new)
            with self.assertRaises(ValueError):probe.validate_markers(changed)
        with self.assertRaises(ValueError):probe.validate_markers(markers[:i])

    def test_retained_parent_refuses_restart_stop_completion_and_exit(self):
        from tools.qualify_native_app_session import Interaction
        for bad in (False,True):
            case=probe.scenario('0123456789abcdef',bad_file=bad)
            interaction=Interaction(case,exhaust_cleanup=True)
            self.assertTrue(case.sent[interaction.exhaustion_barrier:].startswith(b'status text\r'))
            self.assertEqual(case.expected.count(b': retiring\r\n'),6)
            self.assertIn(b'Stop tasks and check status before exit.',case.expected)
            self.assertTrue(case.expected.endswith(b'0123456789abcdef\r\n'+apps.shell.PROMPT))
            self.assertNotIn(b': cancelled',case.expected)
            self.assertFalse(interaction.exhaustion_observed)

    def test_normal_lifecycle_and_wrong_authority_are_not_exhaustion(self):
        with self.assertRaises(ValueError):probe.validate_markers(app_fixture())
        with self.assertRaises(ValueError):probe.validate_markers(fixture(),bad_file=True)
        with self.assertRaises(ValueError):probe.scenario('not-a-challenge')

    def test_post_exhaustion_duration_and_service_progress_are_required(self):
        markers=fixture()
        i=next(i for i,m in enumerate(markers) if 'APPS RUN ' in m and 'dispatches=896 ' in m)
        with self.assertRaises(ValueError):probe.validate_markers(markers[:i])
        changed=markers.copy();changed[-3]=re.sub(r' calls3=[0-9]+',' calls3=0',changed[-3])
        with self.assertRaises(ValueError):probe.validate_markers(changed)


if __name__ == '__main__': unittest.main()
