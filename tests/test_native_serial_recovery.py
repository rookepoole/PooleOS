import unittest
from runtime import native_app_session as apps, native_serial_recovery as serial


class SerialRecoveryTests(unittest.TestCase):
    def fixture(self):
        fields = [(name, 64 if name == 'dispatches' else 0) for name in apps.FIELDS['RUN'].split()]
        run = 'POOLEOS:APPS RUN contract=PAPPSESSION1' + ''.join(f' {k}={v}' for k,v in fields) + ' cpl=3 production=0'
        challenge = ('POOLEOS:APPS SERIAL contract=PAPPSESSION1 dispatches=64 withheld=4096 '
                     f'timeouts=1 pending=0 rejected=0 transmitted={len(run)+2} cpl=3 production=0')
        return [run, challenge]

    def test_exact_record_bound_and_no_input_mutation(self):
        markers = self.fixture()
        before = list(markers)
        ordinary, evidence = serial.separate(markers)
        self.assertEqual(markers, before)
        self.assertEqual(ordinary, markers[:1])
        self.assertEqual(evidence['transmitted'], len(markers[0])+2)
        self.assertFalse(evidence['historical_failure_cause_proven'])

    def test_ten_hostile_challenges_rejected(self):
        self.assertEqual(serial.negative_controls(self.fixture()), 10)

    def test_unknown_or_loss_markers_are_not_filtered(self):
        markers = self.fixture()+['POOLEOS:SERIAL LOSS capacity=1024 production=0']
        ordinary, _ = serial.separate(markers)
        self.assertEqual(ordinary[-1], markers[-1])

    def test_diagnostic_record_does_not_replace_whole_native_oracle(self):
        with self.assertRaises(ValueError):
            serial.validate_markers(self.fixture())

    def test_prior_run_must_be_exact_and_at_dispatch_64(self):
        for mutation in ('dispatches=63', 'dispatches=128', 'dispatches=-1'):
            markers = self.fixture()
            markers[0] = markers[0].replace('dispatches=64', mutation)
            with self.assertRaises(ValueError):
                serial.separate(markers)


if __name__ == '__main__':
    unittest.main()
