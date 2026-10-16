import json
from pathlib import Path
import unittest
from runtime import native_shell_process as control, native_shell_cleanup as cleanup

class NativeShellCleanupTests(unittest.TestCase):
    def fixture(self, bad):
        # Synthetic parser controls, never new guest-execution evidence.
        receipt = json.loads((Path(__file__).resolve().parents[1]/'runs/native-shell-process-readiness.json').read_bytes())
        original = receipt['native_execution']['guest_runs'][2 if bad else 0]['markers']
        markers = []
        for marker in original:
            if marker.startswith('POOLEOS:CONTROL RETIRE '):
                v = control.parse(marker, 'RETIRE')
                if v['task'] >= 4:
                    mode = 1+(v['task']-4)*2+v['generation']-1
                    markers.append(f"POOLEOS:RECLAIM RETRY contract=PRECLAIM1 task={v['task']} generation={v['generation']} mode={mode} retained_pages={v['released_pages']} dispatches={v['dispatches']} released_pages=0 ordinary_free_denials=5 no_reentry=1 early_completion_rejected=1 cpl=0 production=0")
            markers.append(marker)
        return markers

    def test_complete_session_and_ordered_retained_retry_are_both_required(self):
        for bad in (False, True):
            markers = self.fixture(bad)
            result = cleanup.validate_markers(markers, bad_owner=bad)
            self.assertEqual(result['retained_cleanup_retries'], 2 if bad else 4)
            self.assertFalse(result['asynchronous_cleanup_recovery'] or result['production_ready'])
            self.assertGreater(cleanup.negative_controls(markers, bad_owner=bad), 250)
            with self.assertRaises(ValueError):
                cleanup.validate_markers([m for m in markers if m.startswith(cleanup.PREFIX)], bad_owner=bad)

    def test_retry_failure_fields_cannot_be_missing_forged_or_duplicated(self):
        markers = self.fixture(False)
        index = next(i for i,m in enumerate(markers) if m.startswith(cleanup.PREFIX))
        for suffix in (' extra=1', ' cpl=0'):
            changed = markers.copy(); changed[index] += suffix
            with self.assertRaises(ValueError): cleanup.validate_markers(changed)
        changed = markers.copy(); changed[index] = changed[index].replace('dispatches=', 'dispatches=999999999999999999999999')
        with self.assertRaises(ValueError): cleanup.validate_markers(changed)

if __name__ == '__main__': unittest.main()
