import tempfile
import unittest
from pathlib import Path

from runtime import native_kernel_scheduler as scheduler
from tools import qualify_native_kernel_scheduler as qualify


PROBE_OUTPUT = """\
PKSCHED1:STRESS PASS sequence=6660 tasks=8 runnable=4 running=4 blocked=0 dead=0 dispatches=1761 migrations=2334 wakes=0 teardowns=0 inheritance=0 checksum=0x23B76E2F80E2B747 task_dispatches=87,165,245,420,78,133,230,403 runtime_ticks=53,99,127,261,30,90,187,256
PKSCHED1:WAIT PASS sequence=14 wakes=2 cancel_reason=1 timeout_reason=2 duplicate_rejected=1
PKSCHED1:INHERIT PASS owner_slot=0 waiter_slot=1 inherited=30 restored=2 granted_slot=1 inheritance_events=1
PKSCHED1:CONTEXT PASS valid=1 hostile_rejected=8 alignment=16 callee_saved=6
"""


def linked_switch_fixture() -> str:
    instructions = (
        "    1000: 9c pushfq",
        "    1001: 55 pushq %rbp",
        "    1002: 53 pushq %rbx",
        "    1003: 41 54 pushq %r12",
        "    1005: 41 55 pushq %r13",
        "    1007: 41 56 pushq %r14",
        "    1009: 41 57 pushq %r15",
        "    100b: 48 89 27 movq %rsp, (%rdi)",
        "    100e: 48 ff 05 00 00 00 00 incq 0x0(%rip)",
        "    1015: 48 8b 26 movq (%rsi), %rsp",
        "    1018: 41 5f popq %r15",
        "    101a: 41 5e popq %r14",
        "    101c: 41 5d popq %r13",
        "    101e: 41 5c popq %r12",
        "    1020: 5b popq %rbx",
        "    1021: 5d popq %rbp",
        "    1022: 9d popfq",
        "    1023: c3 retq",
    )
    return (
        "0000000000001000 <poole_scheduler_context_switch>:\n"
        + "\n".join(instructions)
        + "\n0000000000001024 <poole_scheduler_context_switch_end>:\n"
    )


class NativeKernelSchedulerTests(unittest.TestCase):
    def test_readiness_writer_emits_canonical_lf_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "readiness.json"
            qualify._write_readiness(path, {"status": "pass", "values": [1, 2]})
            data = path.read_bytes()
        self.assertNotIn(b"\r\n", data)
        self.assertTrue(data.endswith(b"\n"))

    def test_contract_schema_claims_and_hostile_count(self) -> None:
        contract = scheduler.read_json(scheduler.ROOT / scheduler.CONTRACT_RELATIVE)
        self.assertEqual([], scheduler.contract_errors(contract))
        self.assertEqual(28, len(scheduler.NEGATIVE_CONTROL_IDS))
        self.assertEqual(115, contract["qualification"]["hostile_case_count"])
        self.assertFalse(contract["production_ready"])
        self.assertFalse(contract["claims"]["general_scheduler_implemented"])

    def test_independent_stress_oracle_is_frozen(self) -> None:
        receipt = scheduler.stress_oracle()
        self.assertEqual(6660, receipt["sequence"])
        self.assertEqual(1761, receipt["dispatches"])
        self.assertEqual(2334, receipt["migrations"])
        self.assertEqual(0x23B7_6E2F_80E2_B747, receipt["checksum"])
        self.assertEqual((87, 165, 245, 420, 78, 133, 230, 403), receipt["task_dispatches"])

    def test_probe_parser_requires_exact_rust_python_agreement(self) -> None:
        observed = scheduler.parse_probe_output(PROBE_OUTPUT)
        self.assertEqual(4, len(observed["lines"]))
        self.assertEqual(8, observed["context"]["hostile_rejected"])
        with self.assertRaises(scheduler.KernelSchedulerError):
            scheduler.parse_probe_output(PROBE_OUTPUT.replace("dispatches=1761", "dispatches=1760", 1))

    def test_neutral_oracle_rejects_generation_priority_and_queue_drift(self) -> None:
        model = scheduler.NeutralSchedulerOracle()
        model.create(0, 10)
        with self.assertRaises(scheduler.KernelSchedulerError):
            model.create(0, 10)
        with self.assertRaises(scheduler.KernelSchedulerError):
            scheduler.NeutralSchedulerOracle().create(0, 0)
        model.activate(0, 0)
        model.queues[0].append(0)
        with self.assertRaises(scheduler.KernelSchedulerError):
            model.validate()

    def test_source_audit_binds_core_switch_and_selector(self) -> None:
        audit = qualify._source_audit()
        self.assertEqual(14, audit["scheduler_test_count"])
        self.assertTrue(audit["allocation_free_core"])
        self.assertEqual(1, audit["context_switch_source_scope_count"])
        self.assertEqual(5, audit["live_marker_count"])

    def test_linked_switch_scope_has_exact_instruction_boundary(self) -> None:
        fixture = linked_switch_fixture()
        audit = qualify._linked_switch_scope(fixture)
        self.assertEqual(18, audit["instruction_count"])
        self.assertEqual(0, audit["forbidden_instruction_count"])
        with self.assertRaises(scheduler.KernelSchedulerError):
            qualify._linked_switch_scope(fixture.replace(" retq", " sti", 1))
        with self.assertRaises(scheduler.KernelSchedulerError):
            qualify._linked_switch_scope(fixture.replace("\n0000000000001024", "\n    1024: 90 nop\n0000000000001025", 1))

    def test_input_bindings_cover_implementation_and_proof_sources(self) -> None:
        inputs = scheduler.expected_inputs()
        paths = {item["path"] for item in inputs["implementation"]}
        self.assertIn("native/kernel/src/scheduler.rs", paths)
        self.assertIn("native/bootexit/src/lib.rs", paths)
        self.assertIn("tools/qualify_native_kernel_scheduler.py", paths)
        self.assertIn("tests/test_native_kernel_scheduler.py", paths)
        self.assertIn("models/tla/PooleScheduler.tla", paths)

    def test_generated_readiness_when_available(self) -> None:
        path = scheduler.ROOT / scheduler.READINESS_RELATIVE
        if not path.is_file():
            self.skipTest("PKSCHED1 readiness has not been generated yet")
        readiness = scheduler.read_json(path)
        self.assertEqual([], scheduler.readiness_errors(readiness))
        observation = scheduler.validate_markers(readiness["execution"]["runs"][0]["markers"])
        self.assertEqual(16, observation["switch"]["transitions"])
        controls = qualify._negative_controls(
            readiness["execution"]["runs"][0]["markers"],
            readiness["build"]["host_probe"]["lines"],
        )
        self.assertEqual(list(scheduler.NEGATIVE_CONTROL_IDS), [item["id"] for item in controls])
        self.assertEqual(115, sum(item["case_count"] for item in controls))


if __name__ == "__main__":
    unittest.main()
