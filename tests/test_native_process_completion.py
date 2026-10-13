import unittest
from runtime import native_process_completion as completion
from tests.test_native_process_launch import markers as launch_markers

def markers():
    result = launch_markers()
    for sequence, index in ((1, 32), (2, 35)):
        result.insert(index, f"POOLEOS:KERNEL:LAUNCH-COMPLETED PASS contract=PLAUNCH1 sequence={sequence} child_generation={sequence} outcome_word={(1 << 32) | 100} observers=1 held_dispatches=1")
    return result

class NativeProcessCompletionTests(unittest.TestCase):
    def test_deferred_completion_preserves_full_launch_oracle(self):
        result = completion.validate_markers(markers())
        self.assertEqual(len(result['completions']), 2)
        self.assertEqual(result['completion_contract_id'], 'PCOMP1')
        self.assertFalse(result['iso_built'] or result['production_ready'])
        self.assertGreater(completion.negative_controls(markers()), 100)

    def test_completion_cannot_be_inferred_from_retirement_alone(self):
        with self.assertRaises(ValueError): completion.validate_markers(launch_markers())
        data = markers(); data[31], data[32] = data[32], data[31]
        with self.assertRaises(ValueError): completion.validate_markers(data)

    def test_generation_exit_code_observer_count_and_dispatch_bound(self):
        for before, after in [('sequence=2', 'sequence=1'), ('child_generation=2', 'child_generation=3'),
            (f'outcome_word={(1 << 32) | 100}', 'outcome_word=100'), ('observers=1', 'observers=2'),
            ('held_dispatches=1', 'held_dispatches=0'), ('held_dispatches=1', 'held_dispatches=513')]:
            data = markers(); self.assertIn(before, data[35]); data[35] = data[35].replace(before, after)
            with self.assertRaises(ValueError): completion.validate_markers(data)

    def test_denied_owner_has_no_admission_or_completion(self):
        self.assertEqual(completion.validate_markers(launch_markers(True), bad_owner=True)['completions'], [])
        with self.assertRaises(ValueError): completion.validate_markers(markers(), bad_owner=True)
