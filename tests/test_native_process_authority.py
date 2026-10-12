"""Parser controls are synthetic; live qualification remains separately bound."""
import unittest
from runtime import native_process_authority as process
from tests.test_native_session import fixture as session_fixture

def markers():
    result=session_fixture()[:29]
    for g in (1,2):
        result.append(f"POOLEOS:KERNEL:PROCESS-ROUND PASS contract=PPROC1 generation={g} waiting={g-1} dispatches=72 controller_calls=18 survivor_calls=1025 survivor_after_stop=65 ticks0=10 ticks1=20 ticks2=30 cr3_writes=145 root0=0x0000000001100000 root1=0x0000000001200000 root2=0x0000000001300000 forged_denied=1 rights_denied=1 permit_invalidated=1 cancelled=1 retirement_flushes=1 released_pages=39 scrubbed_data_pages=18 cpl=3 production=0")
    return result+[process.RESULT]

class NativeProcessAuthorityTests(unittest.TestCase):
    def test_valid_bounded_observation(self):
        result=process.validate_markers(markers())
        self.assertEqual(len(result["rounds"]),2)
        self.assertFalse(result["iso_built"])
        self.assertFalse(result["production_ready"])

    def test_hostile_marker_mutations(self):
        self.assertGreater(process.negative_controls(markers()),70)

    def test_cross_field_accounting_and_roots(self):
        for old,new in [("cr3_writes=145","cr3_writes=144"),("dispatches=72","dispatches=257"),
                        ("survivor_after_stop=65","survivor_after_stop=73"),
                        ("root1=0x0000000001200000","root1=0x0000000001100000"),
                        ("ticks1=20",f"ticks1={1<<64}")]:
            data=markers();data[29]=data[29].replace(old,new)
            with self.assertRaises(ValueError): process.validate_markers(data)

    def test_completion_requires_full_terminal(self):
        self.assertEqual(process.COMPLETION,(process.RESULT+"\r\n").encode())
        data=markers();data[-1]+=" fabricated=1"
        with self.assertRaises(ValueError): process.validate_markers(data)

if __name__=="__main__": unittest.main()
