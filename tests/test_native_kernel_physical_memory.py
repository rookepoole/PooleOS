from __future__ import annotations

import copy
import unittest

from runtime import native_kernel_physical_memory as physical_memory
from tools import pooleos_release_gate, qualify_native_kernel_physical_memory


class NativeKernelPhysicalMemoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = physical_memory.read_json(
            physical_memory.ROOT / physical_memory.CONTRACT_RELATIVE
        )
        cls.readiness = physical_memory.read_json(
            physical_memory.ROOT / physical_memory.READINESS_RELATIVE
        )
        cls.run_evidence = cls.readiness["execution"]["runs"][0]
        cls.markers = cls.run_evidence["markers"]

    def test_contract_and_readiness_are_exact_and_non_promoting(self) -> None:
        self.assertEqual([], physical_memory.contract_errors(self.contract))
        self.assertEqual([], physical_memory.readiness_errors(self.readiness))
        self.assertFalse(self.readiness["production_ready"])
        self.assertFalse(self.readiness["n9_exit_gate_satisfied"])

    def test_live_markers_bind_to_independent_pbp1_accounting(self) -> None:
        observation = physical_memory.validate_markers(self.markers)
        derived = physical_memory.validate_observation_binding(
            observation, self.run_evidence["pbp1_transcript"]
        )
        self.assertEqual(8, observation["transfer_prefix"]["transfer_arm"]["trap_scenario"])
        self.assertEqual(derived["kind_pages"][1] - 1, observation["result"]["managed_pages"])
        self.assertEqual(0, observation["result"]["physical_writes"])
        self.assertEqual(0, observation["result"]["mappings"])
        self.assertEqual(0, observation["result"]["reclaim"])

    def test_oracle_rejects_overlap_source_kind_and_core_escape(self) -> None:
        observation = physical_memory.validate_markers(self.markers)
        candidates = []
        overlap = copy.deepcopy(self.run_evidence["pbp1_transcript"])
        overlap["memory_entries"][1]["physical_start"] = overlap["memory_entries"][0]["physical_start"]
        candidates.append(overlap)
        source_kind = copy.deepcopy(self.run_evidence["pbp1_transcript"])
        source_kind["memory_entries"][0]["source_type"] = 1
        candidates.append(source_kind)
        ownership = copy.deepcopy(self.run_evidence["pbp1_transcript"])
        ownership["core"]["kernel_physical_base"] = ownership["memory_entries"][0]["physical_start"]
        candidates.append(ownership)
        for candidate in candidates:
            with self.assertRaises(physical_memory.KernelPhysicalMemoryError):
                physical_memory.validate_observation_binding(observation, candidate)

    def test_all_hostile_controls_are_exact_and_pass(self) -> None:
        controls = qualify_native_kernel_physical_memory._negative_controls(
            self.markers, self.run_evidence["pbp1_transcript"]
        )
        self.assertEqual(
            list(physical_memory.NEGATIVE_CONTROL_IDS), [item["id"] for item in controls]
        )
        self.assertTrue(all(item["status"] == "pass" for item in controls))

    def test_source_audit_proves_safe_fixed_capacity_manager(self) -> None:
        audit = qualify_native_kernel_physical_memory._source_audit()
        self.assertEqual(0, audit["implementation_unsafe_token_count"])
        self.assertEqual(0, audit["heap_api_token_count"])
        self.assertEqual(2, audit["fixed_capacity_ledger_count"])

    def test_release_gate_accepts_only_the_bound_non_promoting_receipt(self) -> None:
        check = pooleos_release_gate.check_native_kernel_physical_memory_readiness()
        self.assertTrue(check["ok"], check["detail"])
        self.assertIn("physical_writes=0", check["detail"])
        self.assertIn("n9_exit=false", check["detail"])


if __name__ == "__main__":
    unittest.main()
