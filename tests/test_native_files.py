import unittest
from runtime import native_files as files, native_shell

class NativeFilesTests(unittest.TestCase):
    def test_exact_file_challenge_runs_between_worker_start_and_stop(self):
        case = files.scenario('0123456789abcdef')
        self.assertTrue(case.expected.startswith(native_shell.BANNER))
        self.assertIn(files.README, case.expected)
        self.assertIn(files.NUMBERS, case.expected)
        self.assertEqual(case.expected.count(files.LISTING), 2)
        self.assertLess(case.sent.index(b'start worker\r'), case.sent.index(b'ls\r'))
        self.assertLess(case.sent.index(b'ls\r'), case.sent.index(b'stop worker\r'))
        self.assertEqual(case.sent.count(b'start fault\r'), 2)
        self.assertIn(b'echo 0123456789abcdef\r', case.sent)
        self.assertTrue(case.expected.endswith(b'Bye.\r\n'))

    def test_stale_file_grant_preserves_factory_and_console_challenges(self):
        case = files.scenario('0123456789abcdef', bad_owner=True)
        self.assertEqual(case.expected.count(b'File service unavailable.\r\n'), 8)
        self.assertNotIn(files.VERSION, case.expected)
        self.assertNotIn(files.README, case.expected)
        self.assertEqual(case.expected.count(b'fault: admitted\r\n'), 2)
        self.assertEqual(case.expected.count(b'worker: admitted\r\n'), 2)
        self.assertEqual(case.expected.count(b'Invalid path.\r\n'), 2)

    def test_nonce_and_incomplete_or_console_only_evidence_are_rejected(self):
        for nonce in ('', 'A'*16, '0'*15, 'z'*16):
            with self.assertRaises(ValueError): files.scenario(nonce)
        for markers in ([], ['fake']*40, files.scenario('0'*16).expected.decode().splitlines()):
            with self.assertRaises(ValueError): files.validate_markers(markers)

    def test_file_role_marker_requires_exact_authority_and_privilege(self):
        marker = ('POOLEOS:CONTROL FILES contract=PSHELLPROC1 version=1 init_slot=0 '
                  'service_slot=1 shell_slot=3 bad_handle=0 grants=8 cpl=3 production=0')
        for bad in (marker+' extra=1', marker.replace('grants=8','grants=9'),
                    marker.replace('service_slot=1','service_slot=2'), marker.replace('cpl=3','cpl=0'),
                    marker.replace('bad_handle=0','bad_handle=1')):
            with self.assertRaisesRegex(ValueError, 'file roles'):
                files.validate_markers(['prefix']*29+[bad])

if __name__ == '__main__': unittest.main()
