import unittest
from runtime import native_shell_process as probe, native_shell

class NativeShellProcessTests(unittest.TestCase):
    def test_challenges_require_exact_tokens_and_independent_nonce(self):
        for bad in ('', 'A'*16, '0'*15, '0'*17, 'z'*16):
            with self.assertRaises(ValueError): probe.scenario(bad)
        for bad in (False, True):
            case = probe.scenario('0123456789abcdef', bad_owner=bad)
            self.assertTrue(case.expected.startswith(native_shell.BANNER))
            self.assertIn(b'echo 0123456789abcdef\r', case.sent)
            self.assertEqual(case.sent.count(b'start worker\r'), 2)
            self.assertEqual(case.sent.count(b'start fault\r'), 1 if bad else 2)
            self.assertIn(b'Stop tasks and check status before exit.', case.expected)
            self.assertTrue(case.expected.endswith(b'Bye.\r\n'))

    def test_marker_parser_rejects_duplicate_extra_overflow_or_wrong_privilege(self):
        line = 'POOLEOS:CONTROL UNUSED contract=PSHELLPROC1 task=5 released_pages=13 dispatches=200 cpl=3 production=0'
        self.assertEqual(probe.parse(line, 'UNUSED'), dict(task=5,released_pages=13,dispatches=200))
        for bad in (line+' task=5', line.replace('cpl=3','cpl=0'), line.replace('production=0','production=1'),
            line.replace('task=5','task='+str(1<<64)), line.replace('task=5','task=-1')):
            with self.assertRaises(ValueError): probe.parse(bad, 'UNUSED')

    def test_incomplete_or_console_only_evidence_is_not_native_qualification(self):
        for markers in ([], ['POOLEOS:CONTROL RUN']*50, probe.scenario('0'*16).expected.decode().splitlines()):
            with self.assertRaises(ValueError): probe.validate_markers(markers)

if __name__ == '__main__': unittest.main()
