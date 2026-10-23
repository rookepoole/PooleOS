import json
import re
from pathlib import Path
import unittest
from runtime import native_shell_process as control, native_shell_cleanup as cleanup, native_prepared_cleanup as prepared

class NativePreparedCleanupTests(unittest.TestCase):
    def fixture(self, bad=False):
        # Transform frozen prior observations only to exercise parsers, not to
        # claim that the previously executed guest tested prepared cancellation.
        receipt = json.loads((Path(__file__).resolve().parents[1]/'runs/native-retained-cleanup-readiness.json').read_bytes())
        original = receipt['native_execution']['retry']['guest_runs'][2 if bad else 0]['markers']
        admitted = next(control.parse(m,'ADMIT') for m in original if m.startswith('POOLEOS:CONTROL ADMIT ') and control.parse(m,'ADMIT')['task'] == 4)
        retired = next(control.parse(m,'RETIRE') for m in original if m.startswith('POOLEOS:CONTROL RETIRE ') and control.parse(m,'RETIRE')['task'] == 4)
        hold = admitted['dispatches']+1
        generation, markers = 0, []
        for marker in original:
            if marker.startswith('POOLEOS:CONTROL ADMIT '):
                v = control.parse(marker,'ADMIT')
                if v['task'] == 4: generation = v['generation']
                markers.append(marker)
                if v == admitted:
                    markers.append(f"POOLEOS:PREPARED HOLD contract=PCANCEL1 task=4 generation=1 root={v['root']} dispatches={hold} cr3_writes={2*(hold-1)} calls=0 ticks=0 state=blocked entered=0 cpl=0 production=0")
                continue
            if marker.startswith('POOLEOS:CONTROL RETIRE ') and control.parse(marker,'RETIRE') == retired:
                marker = re.sub(r' calls=[0-9]+', ' calls=0', marker)
            if marker.startswith('POOLEOS:CONTROL RUN '):
                v = control.parse(marker,'RUN')
                if v['dispatches'] >= hold:
                    v['cr3_writes'] -= 2
                if v['dispatches'] >= retired['dispatches']:
                    v['cr3_writes'] -= 1
                    v['extra_flushes'] -= 1
                if generation == 1: v['calls4'] = v['ticks4'] = 0
                for key in ('cr3_writes','extra_flushes','calls4','ticks4'):
                    marker = re.sub(' '+key+r'=[0-9]+', ' '+key+'='+str(v[key]), marker)
            markers.append(marker)
        return markers

    def test_prepared_stop_requires_zero_entry_retained_retry_and_later_live_generation(self):
        for bad in (False, True):
            markers = self.fixture(bad)
            summary = prepared.validate_markers(markers, bad_owner=bad)
            self.assertEqual(summary['prepared_stops'], 1)
            self.assertTrue(summary['prepared_cleanup_retention'])
            self.assertFalse(summary['prepared_child_entered'] or summary['owner_death_recovery'])
            self.assertGreater(prepared.negative_controls(markers, bad_owner=bad), 250)
            with self.assertRaises(ValueError): cleanup.validate_markers(markers, bad_owner=bad)

    def test_exposure_order_duplicate_fields_and_integer_overflow_fail_closed(self):
        markers = self.fixture()
        i = next(i for i,m in enumerate(markers) if m.startswith(prepared.PREFIX))
        for suffix in (' extra=1', ' entered=0'):
            changed = markers.copy(); changed[i] += suffix
            with self.assertRaises(ValueError): prepared.validate_markers(changed)
        for field in ('root','dispatches','cr3_writes'):
            changed = markers.copy(); changed[i] = re.sub(' '+field+r'=[0-9]+', ' '+field+'='+str(1<<64), changed[i])
            with self.assertRaises(ValueError): prepared.validate_markers(changed)
        changed = markers.copy(); held = changed.pop(i); changed.append(held)
        with self.assertRaises(ValueError): prepared.validate_markers(changed)

if __name__ == '__main__': unittest.main()
