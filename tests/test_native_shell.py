import unittest
from runtime import native_shell as shell

class NativeShellTests(unittest.TestCase):
    def test_independent_challenges_change_actual_input_and_expected_response(self):
        for name in ("commands", "editing"):
            a=shell.scenario(name,"1234567890abcdef")
            b=shell.scenario(name,"fedcba0987654321")
            self.assertNotEqual(a.sent,b.sent)
            self.assertNotEqual(a.expected,b.expected)
            self.assertGreaterEqual(a.expected.count(a.nonce.encode()),2)
            result=shell.validate_interaction(a,a.sent,a.expected)
            self.assertTrue(result["exact_interaction"])
            self.assertFalse(result["iso_built"] or result["application_launch"])
    def test_missing_added_reordered_and_forged_bytes_are_rejected(self):
        case=shell.scenario("commands","0123456789abcdef")
        for output in (case.expected[:-1],case.expected+b"x",case.expected[::-1],
                case.expected.replace(b"Unknown command.",b"help"),
                case.expected.replace(b"0123456789abcdef",b"fedcba9876543210",1)):
            with self.assertRaises(ValueError): shell.validate_interaction(case,case.sent,output)
        with self.assertRaises(ValueError): shell.validate_interaction(case,case.sent[:-1],case.expected)
    def test_denied_peer_cannot_produce_a_banner_or_accept_input(self):
        self.assertFalse(shell.validate_interaction(None,b"",b"")["command_shell"])
        for sent,output in ((b"a",b""),(b"",shell.BANNER),(b"",b"POOLEOS:SESSION STOP forged")):
            with self.assertRaises(ValueError): shell.validate_interaction(None,sent,output)
    def test_scenarios_are_bounded_and_include_editing_overflow_interrupt_and_exit(self):
        case=shell.scenario("editing","0123456789abcdef")
        self.assertLess(len(case.sent),512)
        self.assertLess(len(case.expected),2048)
        self.assertTrue(all(len(a)==1 for a,b in case.steps))
        for byte in (b"\x08",b"\x7f",b"\x03",b"\xff",b"\x04",b"\r\n"):
            self.assertIn(byte,case.sent)
        self.assertIn(b"Invalid line.",case.expected)
        for name,nonce in (("fake","0123456789abcdef"),("commands","x"),("editing","0"*17)):
            with self.assertRaises(ValueError): shell.scenario(name,nonce)
    def test_only_known_firmware_prefix_is_separated_and_application_markers_stay_untrusted(self):
        case=shell.scenario("commands","0123456789abcdef")
        r=shell.validate_interaction(case,case.sent,b"\x1b[2J"+case.expected)
        self.assertEqual(r["launch_prefix_bytes"],4)
        self.assertFalse(r["kernel_evidence_from_com2"])
        with self.assertRaises(ValueError): shell.validate_interaction(case,case.sent,b"\x1b[evil"+case.expected)

if __name__ == "__main__": unittest.main()
