from __future__ import annotations

import copy
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runtime import native_kernel_interrupt_time as interrupt_time
from tests.test_native_cpu_entry_provenance import pair_mutations
from tools import pooleos_release_gate, qualify_native_kernel_interrupt_time


def clock_marker_mutations(markers):
    cases = (
        ("zero-sample", {"sample_ticks": 0, "sample_ns": 0}),
        ("short-sample", {"sample_ticks": 10, "sample_ns": 100}),
        ("long-sample", {"sample_ticks": 100_000_001, "sample_ns": 1_000_000_010}),
        ("apic-counter-overflow", {"apic_ticks": 0x1_0000_0000}),
        ("low-frequency", {"sample_ticks": 100_000, "sample_ns": 1_000_000,
                           "apic_ticks": 1, "apic_hz": 1_000, "one_shot_initial": 10}),
        ("high-frequency", {"sample_ticks": 100_000, "sample_ns": 1_000_000,
                            "apic_ticks": 100_000_000, "apic_hz": 100_000_000_000,
                            "one_shot_initial": 1_000_000_000}),
    )
    for label, fields in cases:
        candidate = markers.copy()
        for name, value in fields.items():
            candidate[33] = qualify_native_kernel_interrupt_time._set_field(candidate[33], name, str(value))
        yield label, candidate


def recorded_receipt_mutations(baseline):
    for family in ("exit", "coverage", "evidence"):
        for label, pair in pair_mutations(baseline["execution"], family):
            candidate = copy.deepcopy(baseline)
            candidate["execution"] = pair
            yield family, label, candidate

    def changed(path, value):
        candidate = copy.deepcopy(baseline)
        target = candidate
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        return candidate

    for path in (("execution",), ("execution", "observation"), ("summary",)):
        yield "shape", str(path), changed(path, None)
    for section, fields in baseline["execution"]["observation"].items():
        yield "observation", section, changed(("execution", "observation", section), None)
        if section == "transfer_prefix":
            continue
        for key, value in fields.items():
            substitute = float(value) if type(value) is int else "invalid"
            for label, replacement in (("null", None), ("type-or-value", substitute)):
                path = ("execution", "observation", section, key)
                yield "observation", str(path) + label, changed(path, replacement)
    for key, value in baseline["summary"].items():
        for label, replacement in (("null", None), ("type", float(value))):
            yield "summary", key + label, changed(("summary", key), replacement)
    for label, markers in clock_marker_mutations(baseline["execution"]["runs"][0]["markers"]):
        candidate = copy.deepcopy(baseline)
        for run in candidate["execution"]["runs"]:
            run["markers"] = markers.copy()
        yield "clock", label, candidate


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

    def test_recorded_irq_rejects_inconsistent_payloads(self) -> None:
        # Historical payload consistency is not current-source qualification.
        baseline = interrupt_time.read_json(interrupt_time.ROOT / interrupt_time.READINESS_RELATIVE)
        host_tests = baseline["build"]["kernel_entry"]["host_tests"]
        self.assertEqual([], interrupt_time.recorded_interrupt_time_errors(
            baseline["execution"], baseline["summary"], host_tests))
        for family, label, candidate in recorded_receipt_mutations(baseline):
            with self.subTest(family=family, case=label):
                self.assertTrue(interrupt_time.recorded_interrupt_time_errors(
                    candidate["execution"], candidate["summary"], host_tests))

    def test_runtime_and_real_gate_reject_corrupted_records(self) -> None:
        baseline = interrupt_time.read_json(interrupt_time.ROOT / interrupt_time.READINESS_RELATIVE)
        self.assertEqual([], interrupt_time.readiness_errors(baseline))
        self.assertTrue(pooleos_release_gate.check_native_kernel_interrupt_time_readiness()["ok"])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "candidate.json"
            candidates = list(recorded_receipt_mutations(baseline))
            for value in (None, [], "invalid"):
                candidates.append(("root-shape", repr(value), value))
                candidate = copy.deepcopy(baseline)
                candidate["negative_controls"] = value
                candidates.append(("controls-shape", repr(value), candidate))
            for family, label, candidate in candidates:
                with self.subTest(family=family, case=label):
                    self.assertTrue(interrupt_time.readiness_errors(candidate))
                    path.write_text(json.dumps(candidate, allow_nan=False), encoding="utf-8")
                    self.assertFalse(pooleos_release_gate.check_native_kernel_interrupt_time_readiness(path)["ok"])

    def test_clock_markers_reject_invalid_calibration_without_crashing(self) -> None:
        baseline = interrupt_time.read_json(interrupt_time.ROOT / interrupt_time.READINESS_RELATIVE)
        markers = baseline["execution"]["runs"][0]["markers"]
        self.assertEqual(8, interrupt_time.validate_markers(markers)["delivery"]["eois"])
        for label, candidate in clock_marker_mutations(markers):
            with self.subTest(case=label):
                with self.assertRaises(interrupt_time.KernelInterruptTimeError):
                    interrupt_time.validate_markers(candidate)

    def test_qualifier_rejects_invalid_result_before_writing(self) -> None:
        baseline = interrupt_time.read_json(interrupt_time.ROOT / interrupt_time.READINESS_RELATIVE)
        self.assertEqual([], interrupt_time.readiness_errors(baseline))
        baseline["execution"]["runs"][0]["qemu_exit_code"] = False
        with tempfile.TemporaryDirectory() as folder:
            for exists in (False, True):
                path = Path(folder) / ("existing.json" if exists else "absent/result.json")
                if exists:
                    path.write_bytes(b"preserve-existing-output")
                with mock.patch.object(qualify_native_kernel_interrupt_time, "make_readiness", return_value=baseline):
                    with contextlib.redirect_stdout(io.StringIO()):
                        self.assertEqual(1, qualify_native_kernel_interrupt_time.main(["--out", str(path)]))
                if exists:
                    self.assertEqual(b"preserve-existing-output", path.read_bytes())
                else:
                    self.assertFalse(path.parent.exists())


if __name__ == "__main__":
    unittest.main()
