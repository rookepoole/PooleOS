from __future__ import annotations

import copy
import unittest

from runtime import native_kernel_interrupt_time as interrupt_time
from tools import pooleos_release_gate, qualify_native_kernel_interrupt_time


class NativeKernelInterruptTimeTests(unittest.TestCase):
    def test_contract_is_exact_and_non_promoting(self) -> None:
        contract = interrupt_time.read_json(interrupt_time.ROOT / interrupt_time.CONTRACT_RELATIVE)
        self.assertEqual([], interrupt_time.contract_errors(contract))
        self.assertFalse(contract["production_ready"])
        self.assertFalse(contract["claims"]["flag_n8_irq_001_closed"])
        self.assertFalse(contract["claims"]["application_processor_started"])

    def test_independent_madt_oracle_walks_known_and_unknown_records(self) -> None:
        data = qualify_native_kernel_interrupt_time._canonical_madt()
        topology = interrupt_time.parse_madt_table(bytes(data))
        self.assertEqual(1, topology["processor_count"])
        self.assertEqual(1, topology["enabled_processor_count"])
        self.assertEqual(1, topology["io_apic_count"])
        self.assertEqual(1, topology["override_count"])
        self.assertEqual(1, topology["local_nmi_count"])
        self.assertEqual(1, topology["unknown_structure_count"])
        self.assertEqual(0xFEE0_0000, topology["local_apic_address"])

    def test_madt_oracle_rejects_shape_duplicate_and_reserved_bits(self) -> None:
        candidates = []
        malformed = qualify_native_kernel_interrupt_time._canonical_madt()
        malformed[45] = 7
        candidates.append(malformed)
        duplicate = qualify_native_kernel_interrupt_time._canonical_madt()
        duplicate.extend(bytes([0, 8, 1, 0, 1, 0, 0, 0]))
        duplicate[4:8] = len(duplicate).to_bytes(4, "little")
        candidates.append(duplicate)
        reserved = qualify_native_kernel_interrupt_time._canonical_madt()
        reserved[48:52] = (4).to_bytes(4, "little")
        candidates.append(reserved)
        for candidate in candidates:
            with self.assertRaises(interrupt_time.KernelInterruptTimeError):
                interrupt_time.parse_madt_table(bytes(candidate))

    def test_vector_ledger_is_collision_free_and_bounded(self) -> None:
        owners = interrupt_time.vector_ledger()
        self.assertEqual(51, len(owners))
        self.assertEqual("timer", owners[interrupt_time.TIMER_VECTOR])
        self.assertEqual("future_ipi", owners[interrupt_time.IPI_VECTOR_FIRST])
        self.assertEqual("apic_error", owners[interrupt_time.APIC_ERROR_VECTOR])
        self.assertEqual("spurious", owners[interrupt_time.SPURIOUS_VECTOR])
        with self.assertRaises(interrupt_time.KernelInterruptTimeError):
            interrupt_time.reserve_vector(owners, interrupt_time.TIMER_VECTOR, "timer")

    def test_hpet_wrap_calibration_and_timer_math_are_checked(self) -> None:
        clock = interrupt_time.HpetClock(32, 100_000_000, 0xFFFF_FFF0, 1_000)
        self.assertEqual(3_200, clock.sample(0x10))
        with self.assertRaises(interrupt_time.KernelInterruptTimeError):
            clock.sample(0x1000)
        calibration = interrupt_time.calibrate_apic_timer(
            0xFFFF_FFFF, 0xFFFF_0000, 100_000, 100_000_000
        )
        self.assertEqual(10_000_000, calibration["sample_nanoseconds"])
        self.assertEqual(6_553_500, calibration["apic_ticks_per_second"])
        self.assertEqual(65_535, interrupt_time.timer_initial_count(6_553_500, 10_000_000))

    def test_source_scope_audit_is_bounded(self) -> None:
        audit = qualify_native_kernel_interrupt_time._source_audit()
        self.assertEqual(0, audit["heap_api_token_count"])
        self.assertEqual(8, audit["madt_known_structure_type_count"])
        self.assertEqual(3, audit["irq_mmio_guard_count"])

    def test_live_readiness_markers_and_hostile_controls(self) -> None:
        readiness_path = interrupt_time.ROOT / interrupt_time.READINESS_RELATIVE
        if not readiness_path.is_file():
            self.skipTest("PKIRQ1 readiness has not been generated yet")
        readiness = interrupt_time.read_json(readiness_path)
        self.assertEqual([], interrupt_time.readiness_errors(readiness))
        markers = readiness["execution"]["runs"][0]["markers"]
        observation = interrupt_time.validate_markers(markers)
        self.assertEqual(8, observation["delivery"]["timer_deliveries"])
        self.assertEqual(8, observation["delivery"]["eois"])
        self.assertEqual(0, observation["result"]["ap_start"])
        controls = qualify_native_kernel_interrupt_time._negative_controls(markers)
        self.assertEqual(list(interrupt_time.NEGATIVE_CONTROL_IDS), [item["id"] for item in controls])
        hostile = copy.deepcopy(markers)
        hostile[35] = hostile[35].replace("smp=0", "smp=1")
        with self.assertRaises(interrupt_time.KernelInterruptTimeError):
            interrupt_time.validate_markers(hostile)

    def test_release_gate_accepts_only_the_bound_non_promoting_receipt(self) -> None:
        check = pooleos_release_gate.check_native_kernel_interrupt_time_readiness()
        self.assertTrue(check["ok"], check["detail"])
        self.assertIn("timer=8/8", check["detail"])
        self.assertIn("eoi=8/8", check["detail"])
        self.assertIn("ap_start=0", check["detail"])
        self.assertIn("n8_exit=false", check["detail"])


if __name__ == "__main__":
    unittest.main()
